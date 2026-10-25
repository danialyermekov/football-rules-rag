"""Evaluate a small dev pilot against frozen retrieval artifacts, using Ragas scorers."""

import argparse
import hashlib
import json
import os
from pathlib import Path

import mlflow
from dotenv import load_dotenv
from google import genai
from google.genai import types
from mlflow.entities import Feedback
from mlflow.genai.scorers import scorer
from ragas.metrics.collections import FactualCorrectness, Faithfulness
from ragas.metrics.result import MetricResult

from football_rules.context_controls import citation_integrity
from football_rules.generation import (
    FOCUSED_PROMPT,
    MODEL,
    SOURCE_ID_PROMPT,
    SYSTEM_PROMPT,
    cited_documents,
    generate_answer,
    metric_value,
    valid_citations,
)
from football_rules.ragas_evaluation import evaluate_ragas_metric
from football_rules.tracking import configure_tracking

CONTROL = "b50e71e2d39d4145ae2f7e08fd49416e"
PILOT = ["FR001", "FR005", "FR009", "FR055", "FR085", "FR094"]
NEGATIVE_CONTROL_RUN = "13bca0d6da334de58f200846cac3fbbf"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retrieval-run", default=CONTROL)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--judge-model", default=MODEL)
    parser.add_argument("--scenario-ids", nargs="+", default=PILOT)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--verify-trace", action="store_true")
    parser.add_argument(
        "--citation-mode", choices=["legacy", "source_ids"], default="legacy"
    )
    parser.add_argument("--generate-only", action="store_true")
    parser.add_argument("--run-name")
    parser.add_argument("--policy", choices=["baseline", "focused"], default="baseline")
    parser.add_argument("--irrelevant-context", action="store_true")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    if args.policy == "focused" and args.citation_mode != "legacy":
        parser.error("Focused prompt comparison uses legacy citations")
    if args.irrelevant_context and not args.generate_only:
        parser.error(
            "Irrelevant contexts use --generate-only and separate refusal checks"
        )
    if (args.policy == "focused" or args.irrelevant_context) and not args.run_name:
        parser.error("Experimental policies require an explicit --run-name")

    load_dotenv(".env")
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise ValueError("Configure GEMINI_API_KEY in .env; never paste it into logs")

    prompt = SOURCE_ID_PROMPT if args.citation_mode == "source_ids" else SYSTEM_PROMPT
    if args.policy == "focused":
        prompt = FOCUSED_PROMPT
    experiment_id = configure_tracking()
    tracker = mlflow.MlflowClient()
    source_run = tracker.get_run(args.retrieval_run)
    if source_run.info.status != "FINISHED":
        raise ValueError("Retrieval run must be FINISHED")
    scenarios_path = Path("data/evaluation/scenarios.jsonl")
    digest = hashlib.sha256(scenarios_path.read_bytes()).hexdigest()
    if digest != source_run.data.params["scenarios_sha256"]:
        raise ValueError("Reference dataset differs from the retrieval run")
    scenarios = {
        row["id"]: row
        for row in map(
            json.loads, scenarios_path.read_text(encoding="utf-8").splitlines()
        )
    }
    if any(scenarios[sid]["split"] != "dev" for sid in args.scenario_ids):
        raise ValueError("This pilot accepts dev scenarios only")

    destination = (
        Path("tmp/generation")
        / args.retrieval_run
        / args.policy
        / ("irrelevant" if args.irrelevant_context else "original")
    )
    destination.mkdir(parents=True, exist_ok=True)
    artifact = Path(
        tracker.download_artifacts(
            args.retrieval_run, "per-question-results.json", str(destination.resolve())
        )
    )
    retrieval = json.loads(artifact.read_text(encoding="utf-8"))["records"]
    selected = [
        row
        for row in retrieval
        if row["expectations"]["scenario_id"] in args.scenario_ids
    ]
    if len(selected) != 2 * len(set(args.scenario_ids)):
        raise ValueError("Expected both RU and EN retrieval records for each scenario")
    selected = selected[: args.limit]
    negative = None
    if args.irrelevant_context:
        negative_run = tracker.get_run(NEGATIVE_CONTROL_RUN)
        if negative_run.info.status != "FINISHED":
            raise ValueError("Frozen negative control must be FINISHED")
        if (
            negative_run.data.params["corpus_sha256"]
            != hashlib.sha256(
                Path("data/processed/chunks.jsonl").read_bytes()
            ).hexdigest()
        ):
            raise ValueError("Corpus differs from the audited negative controls")
        negative_path = tracker.download_artifacts(
            NEGATIVE_CONTROL_RUN, "preparation.json", str(destination.resolve())
        )
        negative = json.loads(Path(negative_path).read_text(encoding="utf-8"))
    contexts = {}
    records = []
    for row in selected:
        sid = row["expectations"]["scenario_id"]
        inputs = {**row["inputs"], "scenario_id": sid}
        language = inputs["language"]
        reference = scenarios[sid]
        if reference["questions"][language] != inputs["query"]:
            raise ValueError("Retrieval question differs from the reference")
        contexts[sid, language] = row["outputs"]["context"]
        if negative is not None:
            case_id = f"{sid}-{language}-irrelevant"
            saved = next(
                r for r in negative["records"] if r["inputs"]["case_id"] == case_id
            )
            if saved["inputs"]["query"] != inputs["query"]:
                raise ValueError(
                    "Negative control question differs from this experiment"
                )
            context = negative["contexts"][case_id]
            if not context["text"].strip() or any(
                d["language"] != language or d["edition"] != "2026/27"
                for d in context["documents"]
            ):
                raise ValueError("Invalid frozen distractor")
            contexts[sid, language] = {**context, "token_count": None}
            inputs["condition"] = "irrelevant"
        records.append(
            {
                "inputs": inputs,
                "expectations": {
                    "reference": reference["reference_answers"][language],
                    "must_include": reference["must_include"][language],
                    "must_not_claim": reference["must_not_claim"][language],
                    "question_type": reference["question_type"],
                    **(
                        {"insufficient_context_expected": True}
                        if args.irrelevant_context
                        else {
                            "retrieval_complete_evidence": row["metrics"][
                                "complete_evidence"
                            ]
                        }
                    ),
                },
            }
        )

    client = genai.Client(
        api_key=key,
        http_options=types.HttpOptions(
            timeout=60000, retry_options=types.HttpRetryOptions(attempts=1)
        ),
    )
    mlflow.gemini.autolog()

    def ragas_score(metric_class, **kwargs):
        result = evaluate_ragas_metric(
            metric_class, metric_class.__name__.lower(), key, args.judge_model, **kwargs
        )
        return MetricResult(
            value=result["value"],
            reason=result["reason"],
            traces={"output": result["responses"]},
        )

    observations = {}
    judged = {}

    @mlflow.trace(name="generation_from_saved_retrieval", span_type="CHAIN")
    def predict(query, language, scenario_id, condition="original"):
        identity = scenario_id, language
        if identity in observations:
            return observations[identity]
        context = contexts[identity]
        with mlflow.start_span(
            name="replay_saved_context", span_type="RETRIEVER"
        ) as span:
            span.set_inputs(
                {
                    "retrieval_run_id": args.retrieval_run,
                    "citation_mode": args.citation_mode,
                    "generate_only": args.generate_only,
                    "query": query,
                    "condition": condition,
                }
            )
            span.set_outputs(context["documents"])
        output = generate_answer(
            client,
            query,
            language,
            context["text"],
            model=args.model,
            system_prompt=FOCUSED_PROMPT if args.policy == "focused" else SYSTEM_PROMPT,
            citation_documents=(
                context["documents"] if args.citation_mode == "source_ids" else None
            ),
        )
        output["documents"] = context["documents"]
        output["context_tokens_bge"] = context["token_count"]
        observations[identity] = output
        # Preserve successful API responses even if a later judge fails.
        tracker.log_dict(
            run.info.run_id, output, f"answers/{scenario_id}-{language}.json"
        )
        return output

    def save_judgment(inputs, name, result):
        identity = inputs["scenario_id"], inputs["language"]
        value = metric_value(result.value)
        judged.setdefault(identity, {})[name] = value
        tracker.log_dict(
            run.info.run_id,
            {"value": value, "reason": result.reason, "traces": result.traces},
            f"judgments/{identity[0]}-{identity[1]}-{name}.json",
        )
        return Feedback(value=value, rationale=result.reason)

    @scorer
    def factual_correctness(inputs, outputs, expectations):
        result = ragas_score(
            FactualCorrectness,
            response=outputs["answer"],
            reference=expectations["reference"],
        )
        return save_judgment(inputs, "factual_correctness", result)

    @scorer
    def context_faithfulness(inputs, outputs):
        result = ragas_score(
            Faithfulness,
            user_input=inputs["query"],
            response=outputs["answer"],
            retrieved_contexts=[document["text"] for document in outputs["documents"]],
        )
        return save_judgment(inputs, "context_faithfulness", result)

    @scorer
    def citation_validity(outputs):
        return valid_citations(outputs)

    @scorer
    def declares_insufficient_context(outputs):
        return outputs["status"] == "insufficient_context"

    @scorer
    def citations_within_context(outputs):
        return citation_integrity(outputs)

    @scorer
    def cited_context_faithfulness(inputs, outputs):
        if not valid_citations(outputs):
            identity = inputs["scenario_id"], inputs["language"]
            judged.setdefault(identity, {})["cited_context_faithfulness"] = 0.0
            return Feedback(
                value=0.0, rationale="Missing, duplicate or unavailable citation"
            )
        documents = cited_documents(outputs["citations"], outputs["documents"])
        result = ragas_score(
            Faithfulness,
            user_input=inputs["query"],
            response=outputs["answer"],
            retrieved_contexts=[document["text"] for document in documents],
        )
        return save_judgment(inputs, "cited_context_faithfulness", result)

    os.environ.setdefault("MLFLOW_GENAI_EVAL_MAX_WORKERS", "1")
    with (
        client,
        mlflow.start_run(
            run_name=(
                args.run_name
                or (
                    "G4-source-ids-e10-pilot"
                    if args.citation_mode == "source_ids"
                    else "G0-gemini-e10-pilot"
                )
            )
            + ("-dry-run" if args.limit else "")
        ) as run,
    ):
        mlflow.set_tags(
            {"stage": "generation", "run_kind": "smoke" if args.limit else "pilot"}
        )
        mlflow.log_params(
            {
                "retrieval_run_id": args.retrieval_run,
                "policy": args.policy,
                "negative_control_run_id": (
                    NEGATIVE_CONTROL_RUN if args.irrelevant_context else "none"
                ),
                "citation_mode": args.citation_mode,
                "generate_only": args.generate_only,
                "retrieval_mode": (
                    "frozen_irrelevant_context_intervention"
                    if args.irrelevant_context
                    else "frozen_context_replay"
                ),
                "model": args.model,
                "judge_model": args.judge_model,
                "temperature": 0,
                "questions": len(records),
                "split": "dev",
                "scenarios_sha256": digest,
                "retrieval_artifact_sha256": hashlib.sha256(
                    artifact.read_bytes()
                ).hexdigest(),
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "ragas_version": "0.4.3",
                "sampling": "diagnostic_selected_not_representative",
            }
        )
        for path in [
            __file__,
            "src/football_rules/generation.py",
            "pyproject.toml",
            "uv.lock",
        ]:
            mlflow.log_artifact(path, artifact_path="code")
        mlflow.log_dict({"system_prompt": prompt}, "prompt.json")
        mlflow.log_dict({"records": selected}, "retrieval-inputs.json")
        mlflow.log_dict({"records": records}, "evaluation-records.json")
        if negative is not None:
            mlflow.log_dict(
                {"contexts": list(contexts.values())}, "negative-contexts.json"
            )
        dataset_name = (
            "football-generation-dev-pilot-"
            + hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()[
                :12
            ]
        )
        datasets = tracker.search_datasets(experiment_ids=[experiment_id])
        existing = next((item for item in datasets if item.name == dataset_name), None)
        if existing is None:
            dataset = mlflow.genai.datasets.create_dataset(
                name=dataset_name, experiment_id=[experiment_id], tags={"split": "dev"}
            )
            dataset.merge_records(records)
        else:
            dataset = mlflow.genai.datasets.get_dataset(dataset_id=existing.dataset_id)

        if args.verify_trace:
            predict(**records[0]["inputs"])
            trace_id = mlflow.get_last_active_trace_id()
            print("Starting trace readback", trace_id, flush=True)
            mlflow.flush_trace_async_logging()
            trace = mlflow.get_trace(trace_id)
            if trace is None or not any(s.span_type == "LLM" for s in trace.data.spans):
                raise ValueError("Generation LLM trace readback failed")
            print(
                "Verified spans:",
                [(s.name, s.span_type) for s in trace.data.spans],
                flush=True,
            )

        result = mlflow.genai.evaluate(
            data=dataset,
            predict_fn=predict,
            scorers=(
                (
                    [declares_insufficient_context, citations_within_context]
                    if args.irrelevant_context
                    else [citation_validity]
                )
                if args.generate_only
                else [
                    factual_correctness,
                    context_faithfulness,
                    citation_validity,
                    cited_context_faithfulness,
                ]
            ),
        )
        rows = [
            {
                **record,
                "outputs": observations[
                    record["inputs"]["scenario_id"], record["inputs"]["language"]
                ],
                "judge_scores": judged.get(
                    (record["inputs"]["scenario_id"], record["inputs"]["language"]), {}
                ),
            }
            for record in records
        ]
        mlflow.log_dict({"records": rows}, "per-question-results.json")
        summary = {
            "run_id": run.info.run_id,
            "questions": len(rows),
            "metrics": result.metrics,
        }
        summary["by_language"] = {}
        for language in ("ru", "en"):
            language_rows = [
                row for row in rows if row["inputs"]["language"] == language
            ]
            if not language_rows:
                continue
            summary["by_language"][language] = {
                "questions": len(language_rows),
                "completed_judgments": sum(
                    len(row["judge_scores"]) for row in language_rows
                ),
                "citation_validity": sum(
                    valid_citations(row["outputs"]) for row in language_rows
                )
                / len(language_rows),
                "answered": sum(
                    row["outputs"]["status"] == "answered" for row in language_rows
                ),
                "generation_prompt_tokens": sum(
                    row["outputs"]["usage"].get("prompt_token_count", 0)
                    for row in language_rows
                ),
                "generation_output_tokens": sum(
                    row["outputs"]["usage"].get("candidates_token_count", 0)
                    for row in language_rows
                ),
            }
            for metric in (
                "factual_correctness",
                "context_faithfulness",
                "cited_context_faithfulness",
            ):
                values = [
                    row["judge_scores"][metric]
                    for row in language_rows
                    if metric in row["judge_scores"]
                ]
                if values:
                    summary["by_language"][language][metric] = sum(values) / len(values)
            mlflow.log_metrics(
                {
                    f"generation_{language}_{name}": value
                    for name, value in summary["by_language"][language].items()
                }
            )
        mlflow.log_dict(summary, "summary.json")
        print(json.dumps(summary, ensure_ascii=True, indent=2), flush=True)
        if not args.generate_only and any(
            len(row["judge_scores"]) != 3 for row in rows
        ):
            raise RuntimeError(
                "Incomplete judge scores; inspect MLflow errors before interpreting means"
            )


if __name__ == "__main__":
    main()
