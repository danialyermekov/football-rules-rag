"""Score frozen response snapshots with four Ragas metrics, without generation."""

import argparse
import hashlib
import json
import os
from collections import Counter
from importlib.metadata import version
from pathlib import Path

import mlflow
from dotenv import load_dotenv
from mlflow.entities import Feedback
from mlflow.genai.datasets import create_dataset, get_dataset
from mlflow.genai.scorers import scorer
from ragas.metrics.collections import (
    AnswerRelevancy,
    ContextPrecision,
    ContextRecall,
    FactualCorrectness,
    Faithfulness,
)

from football_rules.api_budget import ApiBudget
from football_rules.embeddings import BGEEmbedder
from football_rules.generation import MODEL
from football_rules.ragas_evaluation import (
    LocalMetricEmbeddings,
    evaluate_ragas_metric,
    metric_applicability,
)
from football_rules.tracking import configure_tracking

SOURCES = {
    "G0": "aaf7ea28d5bf459db7271fbbf8cdd970",
    "G2": "689a6dae0f6648e09d9573f83d575f47",
}
METRICS = {
    "context_precision": ContextPrecision,
    "context_recall": ContextRecall,
    "faithfulness": Faithfulness,
    "answer_relevancy": AnswerRelevancy,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--verify-trace", action="store_true")
    parser.add_argument("--sources", nargs="+", metavar="LABEL=RUN_ID")
    parser.add_argument(
        "--condition", help="Exact condition label in the frozen source"
    )
    parser.add_argument("--run-name", default="G3-ragas-four-metrics")
    parser.add_argument("--factual-correctness", action="store_true")
    parser.add_argument("--max-new-judge-usd", type=float)
    parser.add_argument("--budget-ledger", type=Path)
    args = parser.parse_args()
    if (args.max_new_judge_usd is None) != (args.budget_ledger is None):
        parser.error("Use --max-new-judge-usd and --budget-ledger together")
    budget = (
        ApiBudget(args.budget_ledger, args.max_new_judge_usd, 0.10, 0.40)
        if args.max_new_judge_usd is not None
        else None
    )
    metrics = dict(METRICS)
    if args.factual_correctness:
        metrics["factual_correctness"] = FactualCorrectness
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    load_dotenv(".env")
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise ValueError("Configure GEMINI_API_KEY in environment or .env")

    experiment_id = configure_tracking()
    tracker = mlflow.MlflowClient()
    folder = Path("tmp/g3").resolve()
    cache_folder = folder / "score-cache"
    cache_folder.mkdir(parents=True, exist_ok=True)
    sources = (
        dict(item.split("=", 1) for item in args.sources) if args.sources else SOURCES
    )
    records = []
    for label, identifier in sources.items():
        if tracker.get_run(identifier).info.status != "FINISHED":
            raise ValueError(f"Source run {label} is not FINISHED")
        destination = folder / identifier
        destination.mkdir(exist_ok=True)
        path = Path(
            tracker.download_artifacts(
                identifier, "per-question-results.json", str(destination)
            )
        )
        for row in json.loads(path.read_text(encoding="utf-8"))["records"]:
            condition = row["inputs"].get("condition", "original")
            if args.condition and condition != args.condition:
                continue
            sid, language = row["inputs"]["scenario_id"], row["inputs"]["language"]
            records.append(
                {
                    "inputs": {
                        "snapshot_id": f"{label}-{sid}-{language}-{condition}",
                        "source": label,
                        "condition": condition,
                        "query": row["inputs"]["query"],
                        "language": language,
                        "scenario_id": sid,
                    },
                    "outputs": row["outputs"],
                    "expectations": row["expectations"],
                }
            )
    if not args.sources and not args.condition and len(records) != 60:
        raise ValueError("Expected 12 G0 and 48 G2 frozen responses")
    if not records:
        raise ValueError("No matching frozen responses")
    records = records[: args.limit]
    embedder = BGEEmbedder()
    embeddings = LocalMetricEmbeddings(embedder)
    config = {
        "ragas": version("ragas"),
        "judge_model": MODEL,
        "judge_temperature": 0,
        "judge_max_output_tokens": 2048,
        "judge_response_mode": "json_schema",
        "answer_relevancy_strictness": 3,
        "context_precision_variant": "with_reference_average_precision",
        "embeddings": embedder.parameters(),
        "evaluator_sha256": hashlib.sha256(
            Path("src/football_rules/ragas_evaluation.py").read_bytes()
        ).hexdigest(),
    }
    scores = {}
    evaluations = {}
    api_usage = Counter()

    def score_metric(name, inputs, outputs, expectations):
        identity = inputs["snapshot_id"]
        reason = metric_applicability(name, outputs["documents"])
        if reason:
            data = {"value": None, "status": "not_applicable", "reason": reason}
        else:
            arguments = (
                {} if name == "factual_correctness" else {"user_input": inputs["query"]}
            )
            if name in {"context_precision", "context_recall", "faithfulness"}:
                arguments["retrieved_contexts"] = [
                    document["text"] for document in outputs["documents"]
                ]
            if name in {"context_precision", "context_recall"}:
                arguments["reference"] = expectations["reference"]
            else:
                arguments["response"] = outputs["answer"]
            if name == "factual_correctness":
                arguments["reference"] = expectations["reference"]
            payload = {"config": config, "metric": name, "inputs": arguments}
            digest = hashlib.sha256(
                json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest()
            path = cache_folder / f"{digest}.json"
            if path.exists():
                cached = json.loads(path.read_text(encoding="utf-8"))
                if cached["payload"] != payload:
                    raise ValueError("Cached evaluation inputs do not match")
                data = {
                    **cached["result"],
                    "reused": True,
                    "computed_in_run_id": cached["run_id"],
                }
            else:
                options = (
                    {"embeddings": embeddings, "strictness": 3}
                    if name == "answer_relevancy"
                    else {}
                )
                reservation = None
                if budget is not None:
                    # Bound the fixed metric recipe's calls and intermediate claim text.
                    requests_bound = max(12, len(outputs["documents"]) + 4)
                    input_bound = (
                        len(json.dumps(arguments, ensure_ascii=False).encode()) + 32768
                    )
                    reservation = budget.reserve(
                        input_bound * requests_bound, 2048 * requests_bound
                    )
                result = evaluate_ragas_metric(
                    metrics[name],
                    name,
                    key,
                    MODEL,
                    metric_options=options,
                    **arguments,
                )
                if budget is not None and reservation is not None:
                    usages = [r.get("usage_metadata", {}) for r in result["responses"]]
                    budget.settle(
                        reservation,
                        {
                            "prompt_token_count": sum(
                                u.get("prompt_token_count", 0) for u in usages
                            ),
                            "candidates_token_count": sum(
                                u.get("candidates_token_count", 0)
                                + u.get("thoughts_token_count", 0)
                                for u in usages
                            ),
                        },
                    )
                cached = {
                    "payload": payload,
                    "result": result,
                    "run_id": run.info.run_id,
                }
                path.write_text(
                    json.dumps(cached, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                data = {
                    **result,
                    "reused": False,
                    "computed_in_run_id": run.info.run_id,
                }
                for response in result["responses"]:
                    usage = response.get("usage_metadata", {})
                    api_usage["requests"] += 1
                    api_usage["prompt_tokens"] += usage.get("prompt_token_count", 0)
                    api_usage["output_and_thought_tokens"] += usage.get(
                        "candidates_token_count", 0
                    ) + usage.get("thoughts_token_count", 0)
            tracker.log_artifact(
                run.info.run_id, str(path), artifact_path="judgment-cache"
            )
            data = {k: v for k, v in data.items() if k != "responses"}
            data["cache_key"] = digest
        scores.setdefault(identity, {})[name] = data
        evaluations[identity, name] = data
        tracker.log_dict(run.info.run_id, data, f"judgments/{identity}-{name}.json")
        return Feedback(value=data["value"], rationale=data.get("reason"))

    def make_scorer(name):
        @scorer(name=name)
        def evaluate(inputs, outputs, expectations):
            return score_metric(name, inputs, outputs, expectations)

        return evaluate

    os.environ.setdefault("MLFLOW_GENAI_EVAL_MAX_WORKERS", "1")
    mlflow.gemini.autolog()
    with mlflow.start_run(
        run_name=args.run_name + ("-dry-run" if args.limit else "")
    ) as run:
        mlflow.set_tags(
            {
                "stage": "generation_evaluation",
                "run_kind": "smoke" if args.limit else "pilot",
                "mode": "frozen_response_rescore",
            }
        )
        mlflow.log_params(
            {
                "questions": len(records),
                "generation_requests": 0,
                "judge_model": MODEL,
                "ragas_version": config["ragas"],
                "answer_relevancy_strictness": 3,
                "split": "dev",
                "factual_correctness": args.factual_correctness,
            }
        )
        mlflow.log_dict(config, "evaluation-config.json")
        mlflow.log_dict(sources, "source-runs.json")
        mlflow.log_dict({"records": records}, "frozen-inputs.json")
        for path in [
            __file__,
            "src/football_rules/ragas_evaluation.py",
            "src/football_rules/embeddings.py",
            "uv.lock",
            "pyproject.toml",
        ]:
            mlflow.log_artifact(path, artifact_path="code")
        name = (
            "football-G3-frozen-"
            + hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()[
                :16
            ]
        )
        found = next(
            (
                item
                for item in tracker.search_datasets(experiment_ids=[experiment_id])
                if item.name == name
            ),
            None,
        )
        if found:
            dataset = get_dataset(dataset_id=found.dataset_id)
        else:
            dataset = create_dataset(
                name=name, experiment_id=[experiment_id], tags={"split": "dev"}
            )
            dataset.merge_records(records)
        if args.verify_trace:
            # Cache hits have no new LLM trace; verify the first fresh assessment.
            fresh = False
            for row in records:
                for metric in metrics:
                    score_metric(
                        metric, row["inputs"], row["outputs"], row["expectations"]
                    )
                    assessment = evaluations[row["inputs"]["snapshot_id"], metric]
                    if assessment.get("status") == "ok" and not assessment.get(
                        "reused", False
                    ):
                        fresh = True
                        break
                if fresh:
                    break
            if not fresh:
                raise ValueError("All assessments cached; no new judge trace to verify")
            identity = mlflow.get_last_active_trace_id()
            print("Starting trace readback", identity, flush=True)
            mlflow.flush_trace_async_logging()
            trace = mlflow.get_trace(identity)
            if trace is None or not any(
                span.span_type == "LLM" for span in trace.data.spans
            ):
                raise ValueError("Ragas judge trace verification failed")
            print(
                "Verified spans:",
                [(span.name, span.span_type) for span in trace.data.spans],
                flush=True,
            )
        result = mlflow.genai.evaluate(
            data=dataset, scorers=[make_scorer(name) for name in metrics]
        )
        rows = [
            {**record, "scores": scores.get(record["inputs"]["snapshot_id"], {})}
            for record in records
        ]
        mlflow.log_dict({"records": rows}, "per-question-results.json")
        summary = {
            "run_id": run.info.run_id,
            "records": len(rows),
            "metrics": result.metrics,
            "groups": {},
            "new_judge_usage": dict(api_usage),
        }
        keys = sorted(
            {
                (
                    row["inputs"]["source"],
                    row["inputs"]["condition"],
                    row["inputs"]["language"],
                )
                for row in rows
            }
        )
        for source, condition, language in keys:
            group = [
                row
                for row in rows
                if (
                    row["inputs"]["source"],
                    row["inputs"]["condition"],
                    row["inputs"]["language"],
                )
                == (source, condition, language)
            ]
            stats = {
                "n": len(group),
                "status_counts": dict(
                    Counter(row["outputs"]["status"] for row in group)
                ),
                "metrics": {},
            }
            for metric in metrics:
                values = [
                    row["scores"][metric]["value"]
                    for row in group
                    if metric in row["scores"]
                    and row["scores"][metric]["value"] is not None
                ]
                statuses = Counter(
                    row["scores"].get(metric, {}).get("status", "error")
                    for row in group
                )
                answered = [
                    row["scores"][metric]["value"]
                    for row in group
                    if row["outputs"]["status"] == "answered"
                    and metric in row["scores"]
                    and row["scores"][metric]["value"] is not None
                ]
                stats["metrics"][metric] = {
                    "mean": sum(values) / len(values) if values else None,
                    "n_valid": len(values),
                    "states": dict(statuses),
                    "answered_mean": (
                        sum(answered) / len(answered) if answered else None
                    ),
                    "n_answered_valid": len(answered),
                }
            summary["groups"][f"{source}_{condition}_{language}"] = stats
        summary["new_judge_usage"]["estimated_standard_usd"] = (
            api_usage["prompt_tokens"] * 0.1
            + api_usage["output_and_thought_tokens"] * 0.4
        ) / 1e6
        mlflow.log_dict(summary, "summary.json")
        print(json.dumps(summary, ensure_ascii=True, indent=2), flush=True)
        if len(evaluations) != len(records) * len(metrics):
            raise RuntimeError(
                "Some scorers failed; inspect assessments before using means"
            )


if __name__ == "__main__":
    main()
