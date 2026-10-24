"""G1: hold the G0 prompt fixed and test empty, ablated and irrelevant contexts."""

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

from football_rules.context_controls import citation_integrity, retain_context_pages
from football_rules.evidence_evaluation import render_context
from football_rules.generation import MODEL, SYSTEM_PROMPT, generate_answer
from football_rules.tracking import configure_tracking

G0 = "aaf7ea28d5bf459db7271fbbf8cdd970"
# Full remaining texts were inspected before calling Gemini. These are experiment
# interventions using gold, never a retrieval policy or input to the generator.
KEEP_PAGES = {
    "FR001": {"ru": [244], "en": [56]},
    "FR005": {"ru": [22], "en": [142]},
    "FR009": {"ru": [112], "en": [137]},
    "FR055": {"ru": [244], "en": [136]},
    "FR085": {"ru": [244], "en": [233]},
    "FR094": {"ru": [112], "en": [110]},
}
DISTRACTORS = {
    "en": "b5f6034428eeb149dcf3e27caea86463decc1a7a12fea8d5b1b4908e7a5f6f56",
    "ru": "f4ffd9251361e702cf103ca363020c62e4b76851a6202fd1a98ef32c5742d40d",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--verify-trace", action="store_true")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")

    experiment_id = configure_tracking()
    tracker = mlflow.MlflowClient()
    source = tracker.get_run(G0)
    if source.info.status != "FINISHED":
        raise ValueError("G0 must be FINISHED")
    if (
        source.data.params["prompt_sha256"]
        != hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()
    ):
        raise ValueError("Prompt changed since G0")
    if source.data.params["model"] != MODEL:
        raise ValueError("Model differs from G0")
    folder = Path("tmp/g1").resolve()
    folder.mkdir(parents=True, exist_ok=True)

    def read_artifact(run_id, name):
        target = folder / run_id
        target.mkdir(exist_ok=True)
        path = Path(tracker.download_artifacts(run_id, name, str(target)))
        return json.loads(path.read_text(encoding="utf-8"))

    original = read_artifact(G0, "per-question-results.json")["records"]
    retrieval = read_artifact(
        source.data.params["retrieval_run_id"], "per-question-results.json"
    )["records"]
    evidence_by_id = {
        (row["expectations"]["scenario_id"], row["inputs"]["language"]): row
        for row in retrieval
    }
    corpus_path = Path("data/processed/chunks.jsonl")
    corpus = {
        row["chunk_id"]: row
        for row in map(json.loads, corpus_path.read_text(encoding="utf-8").splitlines())
    }
    contexts = {}
    originals = {}
    records = []
    audit = []
    for row in original:
        sid, language = row["inputs"]["scenario_id"], row["inputs"]["language"]
        base = evidence_by_id[sid, language]
        if row["outputs"]["documents"] != base["outputs"]["context"]["documents"]:
            raise ValueError("Saved G0 documents differ from E10")
        documents = row["outputs"]["documents"]
        required_pages = {
            (locator["document_id"], locator["pdf_page"])
            for unit in base["expectations"]["required_evidence"]
            for locator in unit["locators"]
        }
        remaining = retain_context_pages(
            documents, KEEP_PAGES[sid][language], required_pages
        )
        distractor = corpus[DISTRACTORS[language]]
        if distractor["language"] != language or distractor["edition"] != "2026/27":
            raise ValueError("Distractor language or edition mismatch")
        variants = {
            "empty": [],
            "removed_evidence": remaining,
            "irrelevant": [distractor],
            "original": documents,
        }
        originals[sid, language] = row["outputs"]
        eligible = bool(base["metrics"]["complete_evidence"])
        audit.append(
            {
                "scenario_id": sid,
                "language": language,
                "original_complete_evidence": eligible,
                "clean_removal_comparison_eligible": eligible,
                "kept_pages": KEEP_PAGES[sid][language],
                "remaining_text": render_context(remaining),
                "remaining_chunk_ids": [document["chunk_id"] for document in remaining],
                "removed_chunk_ids": [
                    document["chunk_id"]
                    for document in documents
                    if document not in remaining
                ],
                "review": "coding_agent_inspected_no_rule_supports_target_ruling_not_expert_reviewed",
            }
        )
        for condition, selected in variants.items():
            identity = f"{sid}-{language}-{condition}"
            text = (
                base["outputs"]["context"]["text"]
                if condition == "original"
                else render_context(selected)
            )
            contexts[identity] = {"text": text, "documents": selected}
            records.append(
                {
                    "inputs": {
                        **row["inputs"],
                        "condition": condition,
                        "case_id": identity,
                    },
                    "expectations": {
                        "insufficient_context_expected": condition != "original",
                        "clean_removal_comparison_eligible": eligible,
                        "reference": row["expectations"]["reference"],
                        "question_type": row["expectations"]["question_type"],
                    },
                }
            )
    preparation = {"records": records, "contexts": contexts, "audit": audit}
    (folder / "preparation.json").write_text(
        json.dumps(preparation, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if args.prepare_only:
        print(
            json.dumps(
                {
                    "cases": len(records),
                    "clean_pairs": sum(
                        row["clean_removal_comparison_eligible"] for row in audit
                    ),
                    "preparation": str(folder / "preparation.json"),
                }
            )
        )
        return

    load_dotenv(".env")
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise ValueError("Configure GEMINI_API_KEY in environment or .env")
    records = records[: args.limit]
    observations = {}
    mlflow.gemini.autolog()
    client = genai.Client(
        api_key=key,
        http_options=types.HttpOptions(
            timeout=60000, retry_options=types.HttpRetryOptions(attempts=1)
        ),
    )

    @mlflow.trace(name="controlled_context_generation", span_type="CHAIN")
    def predict(query, language, scenario_id, condition, case_id):
        if case_id in observations:
            return observations[case_id]
        context = contexts[case_id]
        if condition == "original":
            output = {**originals[scenario_id, language], "reused_g0": True}
        else:
            with mlflow.start_span(
                name="experiment_context", span_type="RETRIEVER"
            ) as span:
                span.set_inputs({"condition": condition, "case_id": case_id})
                span.set_outputs(context["documents"])
            output = generate_answer(client, query, language, context["text"])
            output.update({"documents": context["documents"], "reused_g0": False})
        observations[case_id] = output
        tracker.log_dict(run.info.run_id, output, f"answers/{case_id}.json")
        return output

    @scorer
    def declares_insufficient_context(outputs, expectations):
        if not expectations["insufficient_context_expected"]:
            return Feedback(
                value=None,
                rationale="Original context: no abstention expectation assigned",
            )
        return outputs["status"] == "insufficient_context"

    @scorer
    def citations_within_context(outputs):
        return citation_integrity(outputs)

    os.environ.setdefault("MLFLOW_GENAI_EVAL_MAX_WORKERS", "1")
    with (
        client,
        mlflow.start_run(
            run_name="G1-context-grounding" + ("-dry-run" if args.limit else "")
        ) as run,
    ):
        mlflow.set_tags(
            {
                "stage": "generation",
                "run_kind": "smoke" if args.limit else "pilot",
                "experiment_type": "context_intervention",
            }
        )
        mlflow.log_params(
            {
                "source_generation_run_id": G0,
                "model": MODEL,
                "prompt_sha256": source.data.params["prompt_sha256"],
                "cases": len(records),
                "temperature": 0,
                "split": "dev",
                "ragas_used": False,
                "control_mode": "reuse_saved_G0_answers",
                "corpus_sha256": hashlib.sha256(corpus_path.read_bytes()).hexdigest(),
            }
        )
        mlflow.log_dict(preparation, "preparation.json")
        for path in [
            __file__,
            "src/football_rules/context_controls.py",
            "src/football_rules/generation.py",
            "pyproject.toml",
            "uv.lock",
        ]:
            mlflow.log_artifact(path, artifact_path="code")
        fingerprint = hashlib.sha256(
            json.dumps(records, sort_keys=True).encode()
        ).hexdigest()[:16]
        name = "football-G1-dev-" + fingerprint
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
            predict(**records[0]["inputs"])
            identity = mlflow.get_last_active_trace_id()
            print("Starting trace readback", identity, flush=True)
            mlflow.flush_trace_async_logging()
            trace = mlflow.get_trace(identity)
            if trace is None or not any(
                span.span_type == "LLM" for span in trace.data.spans
            ):
                raise ValueError("Generation trace verification failed")
            print(
                "Verified spans:",
                [(span.name, span.span_type) for span in trace.data.spans],
                flush=True,
            )
        result = mlflow.genai.evaluate(
            data=dataset,
            predict_fn=predict,
            scorers=[declares_insufficient_context, citations_within_context],
        )
        if len(observations) != len(records):
            raise RuntimeError("Some generation calls failed; inspect trace errors")
        rows = [
            {**record, "outputs": observations[record["inputs"]["case_id"]]}
            for record in records
        ]
        mlflow.log_dict({"records": rows}, "per-question-results.json")
        summary = {
            "run_id": run.info.run_id,
            "cases": len(rows),
            "metrics": result.metrics,
            "by_condition": {},
        }
        for condition in ("original", "empty", "removed_evidence", "irrelevant"):
            for language in ("ru", "en"):
                group = [
                    row
                    for row in rows
                    if row["inputs"]["condition"] == condition
                    and row["inputs"]["language"] == language
                ]
                if group:
                    values = {
                        "cases": len(group),
                        **{
                            status: sum(
                                row["outputs"]["status"] == status for row in group
                            )
                            for status in (
                                "answered",
                                "insufficient_context",
                                "needs_clarification",
                            )
                        },
                        "citations_within_context": sum(
                            citation_integrity(row["outputs"]) for row in group
                        )
                        / len(group),
                    }
                    summary["by_condition"][f"{condition}_{language}"] = values
                    mlflow.log_metrics(
                        {
                            f"{condition}_{language}_{key}": value
                            for key, value in values.items()
                        }
                    )
        mlflow.log_dict(summary, "summary.json")
        print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
