"""Frozen G9 Flash3.8 replay; --argon adds G10 against both saved baselines."""

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
from mlflow.genai.datasets import create_dataset, get_dataset
from mlflow.genai.scorers import scorer

from football_rules.api_budget import ApiBudget
from football_rules.generation import (
    SYSTEM_PROMPT,
    Answer,
    generate_answer,
    valid_citations,
)
from football_rules.tracking import configure_tracking

G7 = "200753af02644870a17e0cee46c6f7fd"
G8 = "723b81f1dd964c358b2ed399b6763231"
MODEL = "gemini-3.8-flash"
G9 = "1717c12dcac84a11a76a6de9039a27ee"
SMOKE = {"FR005-ru-e10", "FR095-en-e10", "FR069-ru-sufficient"}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(tracker, folder):
    def read(rid, name):
        if tracker.get_run(rid).info.status != "FINISHED":
            raise ValueError("Source run must be FINISHED")
        target = folder / rid
        target.mkdir(exist_ok=True)
        path = tracker.download_artifacts(rid, name, str(target))
        return json.loads(Path(path).read_text(encoding="utf-8"))

    manifest = json.loads(
        Path("docs/generation-g7-context-selection.json").read_text(encoding="utf-8")
    )
    for path, key in [
        ("data/processed/pages.jsonl", "source_pages_sha256"),
        ("data/evaluation/scenarios.jsonl", "scenarios_sha256"),
    ]:
        if digest(path) != manifest[key]:
            raise ValueError("G7 source/annotation hashes changed")
    source = tracker.get_run(G7)
    if (
        source.data.params["prompt_sha256"]
        != hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()
    ):
        raise ValueError("Baseline prompt differs from G7")
    scenarios = {
        r["id"]: r
        for r in map(
            json.loads,
            Path("data/evaluation/scenarios.jsonl")
            .read_text(encoding="utf-8")
            .splitlines(),
        )
    }
    g7prep = read(G7, "preparation.json")
    g8prep = read(G8, "preparation.json")
    normal = read(G7, "per-question-results.json")["records"]
    controls = [
        r
        for r in read(G8, "control-results.json")["records"]
        if r["inputs"]["condition"].startswith("baseline_")
    ]
    records, contexts, baseline = [], {}, {}
    for row, is_control in [(r, False) for r in normal] + [(r, True) for r in controls]:
        i = row["inputs"]
        sid, lang = i["scenario_id"], i["language"]
        if (
            scenarios[sid]["split"] != "dev"
            or i["query"] != scenarios[sid]["questions"][lang]
        ):
            raise ValueError("G9 accepts unchanged dev questions only")
        condition = i["condition"].split("_", 1)[1] if is_control else i["condition"]
        context_id = f"{sid}-{lang}-{condition}"
        context = (g8prep if is_control else g7prep)["contexts"][context_id]
        if row["outputs"]["documents"] != context["documents"]:
            raise ValueError("Frozen documents differ from source outputs")
        contexts[context_id] = context
        for model in ("flash", "lite"):
            case = f"{context_id}-{model}"
            records.append(
                {
                    "inputs": {
                        "query": i["query"],
                        "language": lang,
                        "scenario_id": sid,
                        "condition": f"{model}_{condition}",
                        "case_id": case,
                    },
                    "expectations": row["expectations"],
                }
            )
            if model == "lite":
                baseline[case] = {
                    **row["outputs"],
                    "reused_generation": True,
                    "source_generation_run": G8 if is_control else G7,
                }
    assert len(normal) == 64 and len(controls) == 14
    assert len(records) == 156 and len(contexts) == len(baseline) == 78
    return records, contexts, baseline


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--verify-trace", action="store_true")
    parser.add_argument("--argon", action="store_true")
    args = parser.parse_args()
    label = "G10" if args.argon else "G9"
    candidate = "argon" if args.argon else "flash"
    model = "gemini-4-argon" if args.argon else MODEL
    output_limit = 32768 if args.argon else 2048
    temperature = None if args.argon else 0
    generation_cap, judge_cap = (1.25, 0.25) if args.argon else (0.75, 0.75)
    input_rate, output_rate = (2.0, 10.0) if args.argon else (0.75, 3.75)
    experiment = configure_tracking()
    tracker = mlflow.MlflowClient()
    folder = Path("tmp/g10" if args.argon else "tmp/g9").resolve()
    folder.mkdir(exist_ok=True, parents=True)
    records, contexts, baselines = prepare(tracker, folder)
    if args.argon:
        if tracker.get_run(G9).info.status != "FINISHED":
            raise ValueError("G9 must be FINISHED")
        destination = folder / G9
        destination.mkdir(exist_ok=True)
        previous = []
        for filename in ("per-question-results.json", "control-results.json"):
            path = tracker.download_artifacts(G9, filename, str(destination))
            previous.extend(
                json.loads(Path(path).read_text(encoding="utf-8"))["records"]
            )
        previous = {r["inputs"]["case_id"]: r for r in previous}
        argon_records = []
        for record in records:
            inputs = record["inputs"]
            saved = previous[inputs["case_id"]]
            if (
                saved["expectations"] != record["expectations"]
                or saved["inputs"] != inputs
            ):
                raise ValueError("G9 inputs or expectations changed")
            context_id = inputs["case_id"].rsplit("-", 1)[0]
            if saved["outputs"]["documents"] != contexts[context_id]["documents"]:
                raise ValueError("G9 frozen documents changed")
            baselines[inputs["case_id"]] = {
                **saved["outputs"],
                "reused_generation": True,
                "source_generation_run": G9,
            }
            if inputs["condition"].startswith("flash_"):
                argon_records.append(
                    {
                        "inputs": {
                            **inputs,
                            "case_id": context_id + "-argon",
                            "condition": inputs["condition"].replace(
                                "flash_", "argon_", 1
                            ),
                        },
                        "expectations": record["expectations"],
                    }
                )
        records.extend(argon_records)
        assert len(records) == 234 and len(baselines) == 156
    preparation = {"records": records, "contexts": contexts}
    (folder / "preparation.json").write_text(
        json.dumps(preparation, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if args.prepare_only:
        print("Validated", len(records), "snapshots", flush=True)
        return
    if args.smoke:
        records = [
            r for r in records if r["inputs"]["case_id"].rsplit("-", 1)[0] in SMOKE
        ]
        assert len(records) == (9 if args.argon else 6)
    load_dotenv(".env")
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise ValueError("Configure Gemini key locally, never in logs")
    budget = ApiBudget(
        folder / "generation-ledger.jsonl", generation_cap, input_rate, output_rate
    )
    client = genai.Client(
        api_key=key,
        http_options=types.HttpOptions(
            timeout=900000 if args.argon else 60000,
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )
    mlflow.gemini.autolog()
    cache_folder = folder / "answer-cache"
    cache_folder.mkdir(exist_ok=True)
    observations = {}

    @mlflow.trace(name=label + "_" + candidate + "_replay", span_type="CHAIN")
    def predict(query, language, scenario_id, condition, case_id):
        if case_id in observations:
            return observations[case_id]
        context = contexts[case_id.rsplit("-", 1)[0]]
        if case_id in baselines:
            output = baselines[case_id]
        else:
            payload = {
                "model": model,
                "query": query,
                "language": language,
                "context": context["text"],
                "system_prompt": SYSTEM_PROMPT,
                "schema": Answer.model_json_schema(),
                "temperature": temperature,
                "thinking_level": "LOW",
                "max_output_tokens": output_limit,
                "generation_sha256": digest("src/football_rules/generation.py"),
            }
            serialized = json.dumps(
                payload, sort_keys=True, ensure_ascii=False
            ).encode()
            cache = cache_folder / (hashlib.sha256(serialized).hexdigest() + ".json")
            with mlflow.start_span(
                name=label + "_frozen_context", span_type="RETRIEVER"
            ) as span:
                span.set_inputs({"case_id": case_id})
                span.set_outputs(context["documents"])
            if cache.exists():
                saved = json.loads(cache.read_text(encoding="utf-8"))
                if saved["payload"] != payload:
                    raise ValueError("Cached inputs differ")
                output = {**saved["output"], "reused_generation": True}
            else:
                reservation = budget.reserve(len(serialized), output_limit)
                output = generate_answer(
                    client,
                    query,
                    language,
                    context["text"],
                    model=model,
                    thinking_level=types.ThinkingLevel.LOW,
                    max_output_tokens=output_limit,
                    temperature=temperature,
                )
                budget.settle(reservation, output["usage"])
                output.update(
                    {"reused_generation": False, "computed_in_run_id": run.info.run_id}
                )
                cache.write_text(
                    json.dumps(
                        {"payload": payload, "output": output}, ensure_ascii=False
                    ),
                    encoding="utf-8",
                )
        output = {
            **output,
            "documents": context["documents"],
            "context_tokens_bge": context["token_count"],
        }
        observations[case_id] = output
        tracker.log_dict(run.info.run_id, output, f"answers/{case_id}.json")
        print(
            "Saved",
            case_id,
            "local_generation_usd",
            round(budget.charged(), 6),
            flush=True,
        )
        return output

    @scorer
    def citation_validity(outputs):
        return valid_citations(outputs)

    @scorer
    def declares_insufficient_context(outputs, expectations):
        if not expectations.get("insufficient_context_expected"):
            return Feedback(
                value=None, rationale="No forced abstention on normal questions"
            )
        return outputs["status"] == "insufficient_context"

    os.environ["MLFLOW_GENAI_EVAL_MAX_WORKERS"] = "1"
    with (
        client,
        mlflow.start_run(
            run_name=label + "-" + candidate + ("-smoke" if args.smoke else "")
        ) as run,
    ):
        print("RUN_ID", run.info.run_id, flush=True)
        mlflow.set_tags(
            {"stage": "generation", "run_kind": "smoke" if args.smoke else "pilot"}
        )
        mlflow.log_params(
            {
                "model": model,
                "thinking_level": "LOW",
                "max_output_tokens": output_limit,
                "temperature": temperature if temperature is not None else "omitted",
                "split": "dev",
                "snapshots": len(records),
                "baseline_g7": G7,
                "controls_g8": G8,
                "generation_cap_usd": generation_cap,
                "judge_cap_usd": judge_cap,
                "input_usd_per_million": input_rate,
                "output_usd_per_million": output_rate,
                "baseline_g9": G9 if args.argon else "not_used",
                "prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest(),
            }
        )
        for filename in [
            __file__,
            "src/football_rules/generation.py",
            "src/football_rules/api_budget.py",
            (
                "docs/generation-g10-protocol.md"
                if args.argon
                else "docs/generation-g9-protocol.md"
            ),
            "uv.lock",
            "pyproject.toml",
        ]:
            mlflow.log_artifact(filename, artifact_path="reproduction")
        mlflow.log_dict(preparation, "preparation.json")
        name = (
            "football-"
            + label
            + "-"
            + hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()[
                :16
            ]
        )
        found = next(
            (
                d
                for d in tracker.search_datasets(experiment_ids=[experiment])
                if d.name == name
            ),
            None,
        )
        if found:
            dataset = get_dataset(dataset_id=found.dataset_id)
        else:
            dataset = create_dataset(
                name=name, experiment_id=[experiment], tags={"split": "dev"}
            )
            dataset.merge_records(records)
        if args.verify_trace:
            row = next(
                r
                for r in records
                if r["inputs"]["condition"].startswith(candidate + "_")
            )
            predict(**row["inputs"])
            identity = mlflow.get_last_active_trace_id()
            print("Starting trace readback", identity, flush=True)
            mlflow.flush_trace_async_logging()
            trace = mlflow.get_trace(identity)
            kinds = {s.span_type for s in trace.data.spans} if trace else set()
            if not {"CHAIN", "RETRIEVER", "LLM"} <= kinds:
                raise ValueError(f"Missing trace spans: {kinds}")
            print("Verified", sorted(kinds), flush=True)
        result = mlflow.genai.evaluate(
            data=dataset,
            predict_fn=predict,
            scorers=[citation_validity, declares_insufficient_context],
        )
        missing = [
            r["inputs"]["case_id"]
            for r in records
            if r["inputs"]["case_id"] not in observations
        ]
        if missing:
            raise RuntimeError(
                f"Generation failed for {missing}; rerun to reuse saved answers"
            )
        rows = [{**r, "outputs": observations[r["inputs"]["case_id"]]} for r in records]
        normal = [
            r
            for r in rows
            if r["inputs"]["condition"].endswith(("_e10", "_sufficient"))
        ]
        controls = [r for r in rows if r not in normal]
        mlflow.log_dict({"records": normal}, "per-question-results.json")
        mlflow.log_dict({"records": controls}, "control-results.json")
        mlflow.log_artifact(str(budget.path), artifact_path="usage")
        mlflow.log_dict(
            {
                "run_id": run.info.run_id,
                "normal": len(normal),
                "controls": len(controls),
                "new_generation_spending_usd": budget.charged(),
                "metrics": result.metrics,
            },
            "summary.json",
        )
        print(
            "FINISHED",
            run.info.run_id,
            len(normal),
            len(controls),
            "usd",
            budget.charged(),
            flush=True,
        )


if __name__ == "__main__":
    main()
