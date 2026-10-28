"""G8: one evidence-check recipe versus baseline, with frozen stress controls."""

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

from football_rules.evidence_evaluation import render_context
from football_rules.generation import (
    EVIDENCE_CHECK_PROMPT,
    MODEL,
    SYSTEM_PROMPT,
    EvidenceCheckedAnswer,
    generate_answer,
    valid_citations,
    valid_evidence_quotes,
)
from football_rules.tracking import configure_tracking

G7 = "200753af02644870a17e0cee46c6f7fd"
G1 = "13bca0d6da334de58f200846cac3fbbf"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(tracker, folder):
    def read(rid, name):
        target = folder / rid
        target.mkdir(exist_ok=True)
        path = tracker.download_artifacts(rid, name, str(target))
        return json.loads(Path(path).read_text(encoding="utf-8"))

    source = tracker.get_run(G7)
    if (
        source.info.status != "FINISHED"
        or tracker.get_run(G1).info.status != "FINISHED"
    ):
        raise ValueError("Frozen generation/control sources must be FINISHED")
    if (
        source.data.params["prompt_sha256"]
        != hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()
    ):
        raise ValueError("Baseline prompt changed since G7")
    if source.data.params["scenarios_sha256"] != digest(
        "data/evaluation/scenarios.jsonl"
    ):
        raise ValueError("Scenario dataset changed since G7")
    selection = json.loads(
        Path("docs/generation-g7-context-selection.json").read_text(encoding="utf-8")
    )
    if selection["source_pages_sha256"] != digest("data/processed/pages.jsonl"):
        raise ValueError("Source pages changed since manual control review")
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
    frozen = read(G7, "preparation.json")
    original = [
        r
        for r in read(G7, "per-question-results.json")["records"]
        if r["inputs"]["condition"] == "e10"
    ]
    negative = read(G1, "preparation.json")
    contexts, records, baseline = {}, [], {}

    def add(row, kind, context, saved=None):
        sid, language = row["inputs"]["scenario_id"], row["inputs"]["language"]
        if (
            scenarios[sid]["split"] != "dev"
            or scenarios[sid]["questions"][language] != row["inputs"]["query"]
        ):
            raise ValueError("G8 requires unchanged dev questions")
        context_key = f"{sid}-{language}-{kind}"
        contexts[context_key] = context
        for policy in ("checked", "baseline"):
            case = f"{context_key}-{policy}"
            records.append(
                {
                    "inputs": {
                        "query": row["inputs"]["query"],
                        "language": language,
                        "scenario_id": sid,
                        "condition": (
                            policy if kind == "original" else f"{policy}_{kind}"
                        ),
                        "case_id": case,
                    },
                    "expectations": (
                        row["expectations"]
                        if kind == "original"
                        else {
                            "insufficient_context_expected": True,
                            "question_type": kind,
                        }
                    ),
                }
            )
            if policy == "baseline" and saved is not None:
                baseline[case] = saved

    for row in original:
        sid, lang = row["inputs"]["scenario_id"], row["inputs"]["language"]
        context = frozen["contexts"][f"{sid}-{lang}-e10"]
        if row["outputs"]["documents"] != context["documents"]:
            raise ValueError("G7 outputs differ from frozen E10 context")
        add(row, "original", context, row["outputs"])
        if sid in {"FR001", "FR005", "FR009", "FR055"}:
            key = f"{sid}-{lang}-irrelevant"
            saved = next(
                r for r in negative["records"] if r["inputs"]["case_id"] == key
            )
            if saved["inputs"]["query"] != row["inputs"]["query"]:
                raise ValueError("Frozen irrelevant question mismatch")
            add(row, "irrelevant", {**negative["contexts"][key], "token_count": None})
        if sid in {"FR005", "FR009", "FR055"}:
            spans = {
                ("FR005", "ru"): [(122, 4, 145)],
                ("FR005", "en"): [(119, 1160, 1326)],
                ("FR009", "ru"): [(120, 1617, 1767), (121, 4, 136)],
                ("FR009", "en"): [(118, 1082, 1350)],
                ("FR055", "ru"): [(151, 242, 333)],
                ("FR055", "en"): [(145, 270, 352)],
            }[sid, lang]
            documents = []
            for page_number, start, end in spans:
                page = pages[lang, page_number]
                if not 0 <= start < end <= len(page["text"]):
                    raise ValueError("Control source span outside page")
                documents.append(
                    {
                        "document_id": page["document_id"],
                        "pdf_page": page_number,
                        "printed_page": page["printed_page"],
                        "language": lang,
                        "edition": page["edition"],
                        "text": page["text"][start:end],
                        "source_spans": [{"start": start, "end": end}],
                    }
                )
            add(
                row,
                "partial",
                {
                    "documents": documents,
                    "text": render_context(documents),
                    "token_count": None,
                },
            )
    assert len(original) == 32 and len(records) == 92 and len(baseline) == 32
    assert len({r["inputs"]["case_id"] for r in records}) == 92
    return records, contexts, baseline


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--limit", type=int, help="Number of normal paired questions")
    parser.add_argument("--verify-trace", action="store_true")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    experiment = configure_tracking()
    tracker = mlflow.MlflowClient()
    folder = Path("tmp/g8").resolve()
    folder.mkdir(exist_ok=True, parents=True)
    records, contexts, baselines = prepare(tracker, folder)
    preparation = {"records": records, "contexts": contexts}
    (folder / "preparation.json").write_text(
        json.dumps(preparation, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if args.prepare_only:
        print("Validated", len(records), "snapshots", flush=True)
        return
    if args.limit:
        records = [
            r for r in records if r["inputs"]["condition"] in {"checked", "baseline"}
        ][: args.limit * 2]
    load_dotenv(".env")
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise ValueError("Configure GEMINI_API_KEY locally; do not put secrets in logs")
    client = genai.Client(
        api_key=key,
        http_options=types.HttpOptions(
            timeout=60000, retry_options=types.HttpRetryOptions(attempts=1)
        ),
    )
    mlflow.gemini.autolog()
    observations = {}
    cache_folder = folder / "answer-cache"
    cache_folder.mkdir(exist_ok=True)

    @mlflow.trace(name="G8_evidence_check", span_type="CHAIN")
    def predict(query, language, scenario_id, condition, case_id):
        if case_id in observations:
            return observations[case_id]
        context = contexts[case_id.rsplit("-", 1)[0]]
        checked = condition.startswith("checked")
        if case_id in baselines:
            output = {
                **baselines[case_id],
                "reused_generation": True,
                "source_generation_run": G7,
            }
        else:
            payload = {
                "query": query,
                "language": language,
                "context": context["text"],
                "checked": checked,
                "prompt": EVIDENCE_CHECK_PROMPT if checked else SYSTEM_PROMPT,
                "model": MODEL,
                "generation_sha256": digest("src/football_rules/generation.py"),
                "temperature": 0,
                "max_output_tokens": 1024,
            }
            fingerprint = hashlib.sha256(
                json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest()
            cache = cache_folder / f"{fingerprint}.json"
            with mlflow.start_span(
                name="G8_frozen_context", span_type="RETRIEVER"
            ) as span:
                span.set_inputs({"case_id": case_id})
                span.set_outputs(context["documents"])
            if cache.exists():
                saved = json.loads(cache.read_text(encoding="utf-8"))
                if saved["payload"] != payload:
                    raise ValueError("Cached request differs")
                output = {**saved["output"], "reused_generation": True}
            else:
                output = generate_answer(
                    client, query, language, context["text"], check_evidence=checked
                )
                output.update(
                    {"reused_generation": False, "computed_in_run_id": run.info.run_id}
                )
                cache.write_text(
                    json.dumps(
                        {"payload": payload, "output": output}, ensure_ascii=False
                    ),
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
        print("Saved", case_id, flush=True)
        return output

    @scorer
    def citation_validity(outputs):
        return valid_citations(outputs)

    @scorer
    def quote_provenance(outputs):
        return (
            valid_evidence_quotes(outputs)
            if "checks" in outputs
            else Feedback(value=None, rationale="Baseline has no checks")
        )

    @scorer
    def declares_insufficient_context(outputs, expectations):
        if not expectations.get("insufficient_context_expected"):
            return Feedback(
                value=None,
                rationale="Normal question, no forced abstention expectation",
            )
        return outputs["status"] == "insufficient_context"

    with (
        client,
        mlflow.start_run(
            run_name="G8-evidence-check" + ("-smoke" if args.limit else "")
        ) as run,
    ):
        print("RUN_ID", run.info.run_id, flush=True)
        mlflow.set_tags(
            {"stage": "generation", "run_kind": "smoke" if args.limit else "pilot"}
        )
        mlflow.log_params(
            {
                "source_generation_run": G7,
                "retrieval_run_id": "b50e71e2d39d4145ae2f7e08fd49416e",
                "model": MODEL,
                "temperature": 0,
                "max_output_tokens": 1024,
                "split": "dev",
                "snapshots": len(records),
                "checked_prompt_sha256": hashlib.sha256(
                    EVIDENCE_CHECK_PROMPT.encode()
                ).hexdigest(),
                "baseline_prompt_sha256": hashlib.sha256(
                    SYSTEM_PROMPT.encode()
                ).hexdigest(),
            }
        )
        for filename in [
            __file__,
            "src/football_rules/generation.py",
            "docs/generation-g8-protocol.md",
            "uv.lock",
            "pyproject.toml",
        ]:
            mlflow.log_artifact(filename, artifact_path="reproduction")
        mlflow.log_dict(preparation, "preparation.json")
        mlflow.log_dict(
            {
                "baseline": SYSTEM_PROMPT,
                "checked": EVIDENCE_CHECK_PROMPT,
                "checked_schema": EvidenceCheckedAnswer.model_json_schema(),
            },
            "prompts-and-schema.json",
        )
        name = (
            "football-G8-"
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
            row = next(r for r in records if r["inputs"]["condition"] == "checked")
            predict(**row["inputs"])
            identity = mlflow.get_last_active_trace_id()
            print("Starting trace readback", identity, flush=True)
            mlflow.flush_trace_async_logging()
            trace = mlflow.get_trace(identity)
            kinds = {s.span_type for s in trace.data.spans} if trace else set()
            if not {"CHAIN", "RETRIEVER", "LLM"} <= kinds:
                raise ValueError(f"Trace spans missing: {kinds}")
            print("Verified", sorted(kinds), flush=True)
        result = mlflow.genai.evaluate(
            data=dataset,
            predict_fn=predict,
            scorers=[
                citation_validity,
                quote_provenance,
                declares_insufficient_context,
            ],
        )
        rows = [{**r, "outputs": observations[r["inputs"]["case_id"]]} for r in records]
        normal = [
            r for r in rows if r["inputs"]["condition"] in {"checked", "baseline"}
        ]
        controls = [r for r in rows if r not in normal]
        mlflow.log_dict({"records": normal}, "per-question-results.json")
        mlflow.log_dict({"records": controls}, "control-results.json")
        mlflow.log_dict(
            {
                "run_id": run.info.run_id,
                "normal": len(normal),
                "controls": len(controls),
                "metrics": result.metrics,
            },
            "summary.json",
        )
        print("FINISHED", run.info.run_id, len(normal), len(controls), flush=True)


if __name__ == "__main__":
    main()
