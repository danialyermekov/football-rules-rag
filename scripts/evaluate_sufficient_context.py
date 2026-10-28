"""G7: compare frozen E10 with manually selected, source-checked excerpts."""

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
from transformers import AutoTokenizer

from football_rules.evidence_evaluation import render_context
from football_rules.generation import (
    MODEL,
    SYSTEM_PROMPT,
    generate_answer,
    valid_citations,
)
from football_rules.tracking import configure_tracking

CONTROL = "b50e71e2d39d4145ae2f7e08fd49416e"
SELECTION = Path("docs/generation-g7-context-selection.json")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(tracker, folder):
    selection = json.loads(SELECTION.read_text(encoding="utf-8"))
    for filename, key in [
        ("data/processed/pages.jsonl", "source_pages_sha256"),
        ("data/evaluation/scenarios.jsonl", "scenarios_sha256"),
    ]:
        if digest(filename) != selection[key]:
            raise ValueError(f"Frozen selection input changed: {filename}")
    source = tracker.get_run(CONTROL)
    if source.info.status != "FINISHED":
        raise ValueError("E10 must be FINISHED")
    for name, filename in [
        ("scenarios", "data/evaluation/scenarios.jsonl"),
        ("evidence", "data/evaluation/evidence.jsonl"),
        ("chunks", "data/processed/chunks.jsonl"),
        ("cleaned_pages", "data/processed/cleaned-pages.jsonl"),
    ]:
        if source.data.params[f"{name}_sha256"] != digest(filename):
            raise ValueError(f"E10 input changed: {name}")
    source_path = Path(
        tracker.download_artifacts(CONTROL, "per-question-results.json", str(folder))
    )
    retrieval = {
        (r["expectations"]["scenario_id"], r["inputs"]["language"]): r
        for r in json.loads(source_path.read_text(encoding="utf-8"))["records"]
    }
    scenarios = {
        r["id"]: r
        for r in map(
            json.loads,
            Path("data/evaluation/scenarios.jsonl")
            .read_text(encoding="utf-8")
            .splitlines(),
        )
    }
    pages = {
        (r["language"], r["pdf_page"]): r
        for r in map(
            json.loads,
            Path("data/processed/pages.jsonl").read_text(encoding="utf-8").splitlines(),
        )
    }
    tokenizer = AutoTokenizer.from_pretrained(
        "data/models/bge-m3", local_files_only=True
    )
    records, contexts = [], {}
    for index, item in enumerate(selection["selection"]):
        sid = item["scenario_id"]
        scenario = scenarios[sid]
        if scenario["split"] != "dev":
            raise ValueError("G7 accepts dev scenarios only")
        for language in ("ru", "en"):
            base = retrieval[sid, language]
            if base["inputs"]["query"] != scenario["questions"][language]:
                raise ValueError("Question differs from E10")
            documents = []
            for position, selected in enumerate(item[language]):
                page = pages[language, selected["pdf_page"]]
                start, end = selected["start"], selected["end"]
                if not 0 <= start < end <= len(page["text"]):
                    raise ValueError("Selected source range is outside its page")
                if page["edition"] != "2026/27":
                    raise ValueError("Unexpected source edition")
                documents.append(
                    {
                        "chunk_id": f"G7-{sid}-{language}-{position}",
                        "document_id": page["document_id"],
                        "pdf_page": page["pdf_page"],
                        "printed_page": page["printed_page"],
                        "language": language,
                        "edition": page["edition"],
                        "text": page["text"][start:end],
                        "source_spans": [{"start": start, "end": end}],
                    }
                )
            if not documents:
                raise ValueError("Sufficient-source context cannot be empty")
            text = render_context(documents)
            variants = {
                "e10": base["outputs"]["context"],
                "sufficient": {
                    "documents": documents,
                    "text": text,
                    "token_count": len(
                        tokenizer.encode(text, add_special_tokens=False)
                    ),
                },
            }
            # Alternate request order, without selecting among repeated answers.
            order = ("e10", "sufficient") if index % 2 == 0 else ("sufficient", "e10")
            for condition in order:
                case = f"{sid}-{language}-{condition}"
                contexts[case] = variants[condition]
                records.append(
                    {
                        "inputs": {
                            **base["inputs"],
                            "scenario_id": sid,
                            "condition": condition,
                            "case_id": case,
                        },
                        "expectations": {
                            "reference": scenario["reference_answers"][language],
                            "must_include": scenario["must_include"][language],
                            "must_not_claim": scenario["must_not_claim"][language],
                            "question_type": scenario["question_type"],
                            "retrieval_complete_evidence": base["metrics"][
                                "complete_evidence"
                            ],
                        },
                    }
                )
    assert len(records) == len(contexts) == len(selection["selection"]) * 4
    return records, contexts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--limit", type=int, help="Number of paired RU/EN questions")
    parser.add_argument("--verify-trace", action="store_true")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    experiment = configure_tracking()
    tracker = mlflow.MlflowClient()
    folder = Path("tmp/g7").resolve()
    folder.mkdir(exist_ok=True, parents=True)
    records, contexts = prepare(tracker, folder)
    preparation = {"records": records, "contexts": contexts}
    (folder / "preparation.json").write_text(
        json.dumps(preparation, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if args.prepare_only:
        print(json.dumps({"cases": len(records), "validation": "passed"}), flush=True)
        return
    records = records[: args.limit * 2] if args.limit else records
    load_dotenv(".env")
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise ValueError("Configure GEMINI_API_KEY locally; never put it in logs")
    mlflow.gemini.autolog()
    client = genai.Client(
        api_key=key,
        http_options=types.HttpOptions(
            timeout=60000, retry_options=types.HttpRetryOptions(attempts=1)
        ),
    )
    observations = {}
    cache_folder = folder / "answer-cache"
    cache_folder.mkdir(exist_ok=True)

    @mlflow.trace(name="G7_context_diagnostic", span_type="CHAIN")
    def predict(query, language, scenario_id, condition, case_id):
        if case_id in observations:
            return observations[case_id]
        context = contexts[case_id]
        payload = {
            "query": query,
            "language": language,
            "context": context["text"],
            "model": MODEL,
            "prompt": SYSTEM_PROMPT,
            "generation_code_sha256": digest("src/football_rules/generation.py"),
            "temperature": 0,
            "max_output_tokens": 1024,
        }
        fingerprint = hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        cache = cache_folder / f"{fingerprint}.json"
        with mlflow.start_span(name="G7_frozen_context", span_type="RETRIEVER") as span:
            span.set_inputs({"case_id": case_id, "retrieval_run": CONTROL})
            span.set_outputs(context["documents"])
        if cache.exists():
            saved = json.loads(cache.read_text(encoding="utf-8"))
            if saved["payload"] != payload:
                raise ValueError("Cached request fingerprint mismatch")
            output = {**saved["output"], "reused": True}
        else:
            output = generate_answer(client, query, language, context["text"])
            output.update({"reused": False, "computed_in_run_id": run.info.run_id})
            cache.write_text(
                json.dumps({"payload": payload, "output": output}, ensure_ascii=False),
                encoding="utf-8",
            )
        output.update(
            {
                "documents": context["documents"],
                "context_tokens_bge": context["token_count"],
            }
        )
        observations[case_id] = output
        tracker.log_dict(run.info.run_id, output, f"answers/{case_id}.json")
        print(f"Saved {case_id}; reused={output['reused']}", flush=True)
        return output

    @scorer(name="g7_citation_validity")
    def citation_validity(outputs):
        return valid_citations(outputs)

    os.environ.setdefault("MLFLOW_GENAI_EVAL_MAX_WORKERS", "1")
    with (
        client,
        mlflow.start_run(
            run_name="G7-sufficient-source-diagnostic"
            + ("-smoke" if args.limit else "")
        ) as run,
    ):
        print("RUN_ID", run.info.run_id, flush=True)
        mlflow.set_tags(
            {"stage": "generation", "run_kind": "smoke" if args.limit else "pilot"}
        )
        mlflow.log_params(
            {
                "retrieval_run_id": CONTROL,
                "model": MODEL,
                "temperature": 0,
                "max_output_tokens": 1024,
                "split": "dev",
                "questions": len(records),
                "selection_sha256": digest(SELECTION),
                "prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest(),
                "scenarios_sha256": digest("data/evaluation/scenarios.jsonl"),
                "mode": "privileged_source_intervention_not_retrieval_policy",
            }
        )
        for filename in [
            __file__,
            str(SELECTION),
            "docs/generation-g7-protocol.md",
            "src/football_rules/generation.py",
            "uv.lock",
            "pyproject.toml",
        ]:
            mlflow.log_artifact(filename, artifact_path="reproduction")
        mlflow.log_dict(preparation, "preparation.json")
        mlflow.log_dict({"system_prompt": SYSTEM_PROMPT}, "prompt.json")
        name = (
            "football-G7-"
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
            predict(**records[0]["inputs"])
            trace_id = mlflow.get_last_active_trace_id()
            print("Starting trace readback", trace_id, flush=True)
            mlflow.flush_trace_async_logging()
            trace = mlflow.get_trace(trace_id)
            span_types = (
                {span.span_type for span in trace.data.spans} if trace else set()
            )
            if not {"CHAIN", "RETRIEVER", "LLM"}.issubset(span_types):
                raise ValueError(f"Missing expected trace spans: {span_types}")
            print("Verified trace span types", sorted(span_types), flush=True)
        result = mlflow.genai.evaluate(
            data=dataset, predict_fn=predict, scorers=[citation_validity]
        )
        rows = [{**r, "outputs": observations[r["inputs"]["case_id"]]} for r in records]
        assert len(rows) == len(records)
        mlflow.log_dict({"records": rows}, "per-question-results.json")
        mlflow.log_dict(
            {"run_id": run.info.run_id, "cases": len(rows), "metrics": result.metrics},
            "summary.json",
        )
        print("FINISHED", run.info.run_id, len(rows), flush=True)


if __name__ == "__main__":
    main()
