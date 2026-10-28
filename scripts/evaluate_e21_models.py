"""G13: bounded Flash/Argon comparison on exact E21 contexts and G8 controls."""

import argparse
import hashlib
import json
import os
from pathlib import Path

import mlflow
from dotenv import load_dotenv
from google import genai
from google.genai import types
from mlflow.genai.datasets import create_dataset, get_dataset
from mlflow.genai.scorers import scorer

from football_rules.api_budget import ApiBudget
from football_rules.evidence_evaluation import render_context
from football_rules.generation import (
    SYSTEM_PROMPT,
    Answer,
    generate_answer,
    valid_citations,
)
from football_rules.tracking import configure_tracking

NORMAL = "7644cccdb9634aa0a7a13896bb844a8c"
CONTROLS = "723b81f1dd964c358b2ed399b6763231"
IDS = {
    "FR001",
    "FR005",
    "FR009",
    "FR010",
    "FR050",
    "FR065",
    "FR069",
    "FR085",
    "FR094",
    "FR095",
}
SMOKE = {"FR005-ru-normal", "FR094-en-normal", "FR069-en-normal"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    experiment = configure_tracking()
    tracker = mlflow.MlflowClient()
    folder = Path("tmp/g13").resolve()
    folder.mkdir(exist_ok=True, parents=True)

    def read(rid, name):
        if tracker.get_run(rid).info.status != "FINISHED":
            raise ValueError("Frozen source must be FINISHED")
        target = folder / rid
        target.mkdir(exist_ok=True)
        path = tracker.download_artifacts(rid, name, str(target))
        return json.loads(Path(path).read_text(encoding="utf-8"))

    prompt_hash = hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()
    assert tracker.get_run(NORMAL).data.params["prompt_sha256"] == prompt_hash
    retrieval_id = tracker.get_run(NORMAL).data.params["retrieval_run_id"]
    retrieval_run = tracker.get_run(retrieval_id)
    assert retrieval_run.info.status == "FINISHED"
    for parameter, filename in [
        ("chunks_sha256", "data/processed/chunks.jsonl"),
        ("evidence_sha256", "data/evaluation/evidence.jsonl"),
        ("cleaned_pages_sha256", "data/processed/cleaned-pages.jsonl"),
    ]:
        assert (
            hashlib.sha256(Path(filename).read_bytes()).hexdigest()
            == retrieval_run.data.params[parameter]
        )
    scenarios_path = Path("data/evaluation/scenarios.jsonl")
    assert (
        hashlib.sha256(scenarios_path.read_bytes()).hexdigest()
        == tracker.get_run(NORMAL).data.params["scenarios_sha256"]
    )
    scenarios = {
        r["id"]: r
        for r in map(
            json.loads, scenarios_path.read_text(encoding="utf-8").splitlines()
        )
    }
    normal = [
        r
        for r in read(NORMAL, "per-question-results.json")["records"]
        if r["inputs"]["scenario_id"] in IDS
    ]
    controls = [
        r
        for r in read(CONTROLS, "control-results.json")["records"]
        if r["inputs"]["condition"] in {"baseline_partial", "baseline_irrelevant"}
        and (r["inputs"]["scenario_id"], r["inputs"]["condition"])
        in {("FR005", "baseline_partial"), ("FR009", "baseline_irrelevant")}
    ]
    prep = read(CONTROLS, "preparation.json")
    assert len(normal) == 20 and len(controls) == 4
    retrieval_rows = read(retrieval_id, "per-question-results.json")["records"]
    contexts_by_question = {
        (r["inputs"]["query"], r["inputs"]["language"]): r["outputs"]["context"]
        for r in retrieval_rows
    }
    contexts, baselines, records = {}, {}, []
    for row in normal + controls:
        i = row["inputs"]
        sid, lang = i["scenario_id"], i["language"]
        assert (
            scenarios[sid]["split"] == "dev"
            and scenarios[sid]["questions"][lang] == i["query"]
        )
        condition = (
            "normal" if row in normal else i["condition"].removeprefix("baseline_")
        )
        context_id = f"{sid}-{lang}-{condition}"
        if condition == "normal":
            docs = row["outputs"]["documents"]
            context = {
                "text": render_context(docs),
                "documents": docs,
                "token_count": row["outputs"]["context_tokens_bge"],
            }
            original = contexts_by_question[i["query"], lang]
            assert context["documents"] == original["documents"]
            assert context["text"] == original["text"]
            assert context["token_count"] == original["token_count"]
        else:
            context = prep["contexts"][context_id]
            assert context["documents"] == row["outputs"]["documents"]
        assert context_id not in contexts and context["text"].strip()
        contexts[context_id] = context
        baselines[context_id] = row["outputs"]
        for model in ["lite", "flash", "argon"]:
            records.append(
                {
                    "inputs": {
                        "query": i["query"],
                        "language": lang,
                        "scenario_id": sid,
                        "condition": f"{model}_{condition}",
                        "case_id": context_id + "-" + model,
                    },
                    "expectations": row["expectations"],
                }
            )
    assert len(records) == 72 and len(contexts) == 24
    preparation = {"records": records, "contexts": contexts}
    (folder / "preparation.json").write_text(
        json.dumps(preparation, ensure_ascii=False), encoding="utf-8"
    )
    if args.prepare_only:
        print("Validated72 snapshots/24 contexts/20 dev normal inputs")
        return
    if args.smoke:
        records = [
            r for r in records if r["inputs"]["case_id"].rsplit("-", 1)[0] in SMOKE
        ]
        assert len(records) == 9
    load_dotenv(".env")
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise ValueError("Configure Gemini credential locally")
    budgets = {
        "flash": ApiBudget(folder / "flash-ledger.jsonl", 0.10, 0.75, 3.75),
        "argon": ApiBudget(folder / "argon-ledger.jsonl", 0.50, 2, 10),
    }
    cache_folder = folder / "answers"
    cache_folder.mkdir(exist_ok=True)
    observations = {}
    mlflow.gemini.autolog()

    @mlflow.trace(name="G13_E21_models", span_type="CHAIN")
    def predict(query, language, scenario_id, condition, case_id):
        if case_id in observations:
            return observations[case_id]
        context_id, label = case_id.rsplit("-", 1)
        context = contexts[context_id]
        if label == "lite":
            output = {**baselines[context_id], "reused_generation": True}
        else:
            model = "gemini-4-argon" if label == "argon" else "gemini-3.8-flash"
            ceiling = 32768 if label == "argon" else 2048
            temperature = None if label == "argon" else 0
            payload = {
                "model": model,
                "query": query,
                "language": language,
                "context": context["text"],
                "prompt": SYSTEM_PROMPT,
                "schema": Answer.model_json_schema(),
                "thinking_level": "LOW",
                "max_output_tokens": ceiling,
                "temperature": temperature,
            }
            serialized = json.dumps(
                payload, sort_keys=True, ensure_ascii=False
            ).encode()
            cache = cache_folder / (hashlib.sha256(serialized).hexdigest() + ".json")
            if cache.exists():
                saved = json.loads(cache.read_text(encoding="utf-8"))
                assert saved["payload"] == payload
                output = {**saved["output"], "reused_generation": True}
            else:
                with mlflow.start_span(
                    name="E21_frozen_context", span_type="RETRIEVER"
                ) as span:
                    span.set_inputs({"case_id": case_id})
                    span.set_outputs(context["documents"])
                reservation = budgets[label].reserve(len(serialized), ceiling)
                with genai.Client(
                    api_key=key,
                    http_options=types.HttpOptions(
                        timeout=900000 if label == "argon" else 60000,
                        retry_options=types.HttpRetryOptions(attempts=1),
                    ),
                ) as client:
                    output = generate_answer(
                        client,
                        query,
                        language,
                        context["text"],
                        model=model,
                        thinking_level=types.ThinkingLevel.LOW,
                        max_output_tokens=ceiling,
                        temperature=temperature,
                    )
                budgets[label].settle(reservation, output["usage"])
                output.update(
                    reused_generation=False, computed_in_run_id=run.info.run_id
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
        return output

    @scorer
    def citation_validity(outputs):
        return valid_citations(outputs)

    with mlflow.start_run(
        run_name="G13-E21-models" + ("-smoke" if args.smoke else "")
    ) as run:
        print("RUN_ID", run.info.run_id, flush=True)
        mlflow.set_tags(
            {"stage": "generation", "run_kind": "smoke" if args.smoke else "pilot"}
        )
        mlflow.log_params(
            {
                "split": "dev",
                "snapshots": len(records),
                "prompt_sha256": prompt_hash,
                "normal_source": NORMAL,
                "control_source": CONTROLS,
                "generation_cap_usd": 0.60,
                "judge_cap_usd": 0.25,
                "thinking_level": "LOW",
                "retrieval": "frozen_E21",
            }
        )
        mlflow.log_dict(preparation, "preparation.json")
        for f in [
            __file__,
            "src/football_rules/generation.py",
            "src/football_rules/api_budget.py",
            "docs/generation-g13-protocol.md",
            "docs/evaluation-diagnosis-g13.md",
            "uv.lock",
        ]:
            mlflow.log_artifact(f, artifact_path="reproduction")
        name = (
            "football-G13-"
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
        if args.smoke:
            predict(
                **next(
                    r["inputs"]
                    for r in records
                    if r["inputs"]["case_id"].endswith("-argon")
                )
            )
            identity = mlflow.get_last_active_trace_id()
            mlflow.flush_trace_async_logging()
            trace = mlflow.get_trace(identity)
            assert trace and {"CHAIN", "RETRIEVER", "LLM"} <= {
                s.span_type for s in trace.data.spans
            }
            print("Verified trace", identity, flush=True)
        mlflow.genai.evaluate(
            data=dataset, predict_fn=predict, scorers=[citation_validity]
        )
        missing = [
            r["inputs"]["case_id"]
            for r in records
            if r["inputs"]["case_id"] not in observations
        ]
        if missing:
            raise RuntimeError(f"Missing answers; successful cache retained: {missing}")
        rows = [{**r, "outputs": observations[r["inputs"]["case_id"]]} for r in records]
        mlflow.log_dict(
            {
                "records": [
                    r for r in rows if r["inputs"]["condition"].endswith("_normal")
                ]
            },
            "per-question-results.json",
        )
        mlflow.log_dict(
            {
                "records": [
                    r for r in rows if not r["inputs"]["condition"].endswith("_normal")
                ]
            },
            "control-results.json",
        )
        for label, budget in budgets.items():
            mlflow.log_artifact(str(budget.path), artifact_path="usage")
            mlflow.log_metric(label + "_generation_guard_usd", budget.charged())
        print("FINISHED", run.info.run_id, flush=True)


if __name__ == "__main__":
    main()
