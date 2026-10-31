"""E23: one frozen gold-blind anchor-first packing experiment (offline dev only)."""

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from time import perf_counter

# Apply the E22 local-store safety defaults before MLflow import/evaluation.
os.environ.setdefault("MLFLOW_DISABLE_TELEMETRY", "true")
os.environ.setdefault("MLFLOW_GENAI_EVAL_MAX_WORKERS", "1")
os.environ.setdefault("MLFLOW_GENAI_EVAL_MAX_SCORER_WORKERS", "1")

import mlflow
from evaluate_retrieval import evaluation_records, make_evidence_scorer, read_jsonl
from mlflow.genai.datasets import create_dataset, get_dataset
from transformers import AutoTokenizer

from football_rules.embeddings import MODEL_REVISION
from football_rules.evidence_evaluation import (
    chunk_successors,
    evidence_metrics,
    pack_anchor_first_context,
    pack_context,
    prioritize_rule_neighbors,
    render_context,
)
from football_rules.tracking import configure_tracking

E21 = "174a45eee3c243e2a7bf21be9ddd7bae"
E15 = "b8b229800f4246d090eea03a4d5c9900"
BUDGET = 2048
METRICS = (
    "complete_evidence",
    "strict_complete_evidence",
    "evidence_recall",
    "evidence_coverage",
    "source_redundancy",
)
SOURCE_PATHS = {
    "chunks_sha256": "data/processed/chunks.jsonl",
    "scenarios_sha256": "data/evaluation/scenarios.jsonl",
    "evidence_sha256": "data/evaluation/evidence.jsonl",
    "cleaned_pages_sha256": "data/processed/cleaned-pages.jsonl",
}
# Frozen against FINISHED E22 d54f4c7f1fc046e58b12caa275033d17/input-hashes.json.
FROZEN_HASHES = {
    "data/processed/chunks.jsonl": "160affca3f09408aae7b147d44d9e388cc7419c6c89994b324ca8885c832d105",
    "data/evaluation/scenarios.jsonl": "12588edf4c1149a06e4d8adf11cd087758536d9d7df92ab07ac36fcb181fce04",
    "data/evaluation/evidence.jsonl": "7ebb4f4031895d7a36a992aec3c75c9eec6b759fce273522db4034f0b72c7b71",
    "data/processed/cleaned-pages.jsonl": "7cea405ef76c0939833b41566180690503d23ef71d89155b7c405893a7baa261",
    E21
    + "/per-question-results.json": "676bb6bab1476872f03572ca5515fa9e070fb3dc24ba84820e8380fee617593f",
    E15
    + "/per-question-results.json": "bdb3f37a8248874d6dfb52ba79035c3de8c7d67e2b14071117b7d057f8725e15",
    "data/models/bge-m3/.cache/huggingface/download/tokenizer.json.metadata": "7665f744571464b33d39eb28784090789287bcea451551e8950e0b64ba845856",
    "data/models/bge-m3/tokenizer.json": "21106b6d7dab2952c1d496fb21d5dc9db75c28ed361a05f5020bbba27810dd08",
    "data/models/bge-m3/tokenizer_config.json": "a62b2b6784f990259fddef5f16388693a8043be4f69179e6a5257eeb3f9abac4",
    "data/models/bge-m3/special_tokens_map.json": "8c785abebea9ae3257b61681b4e6fd8365ceafde980c21970d001e834cf10835",
}
REPRODUCTION = (
    "scripts/evaluate_anchor_first.py",
    "src/football_rules/evidence_evaluation.py",
    "scripts/evaluate_retrieval.py",
    "src/football_rules/embeddings.py",
    "src/football_rules/tracking.py",
    "docs/retrieval-e23-protocol.md",
    "pyproject.toml",
    "uv.lock",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def key(record):
    return record["inputs"]["query"], record["inputs"]["language"]


def canonical(records):
    return sorted(json.dumps(r, sort_keys=True, ensure_ascii=False) for r in records)


def trace_readback(trace_id):
    """Bound flush + backend readback together; kill the child on timeout."""
    require(trace_id is not None, "No smoke trace ID; stop before evaluation")
    print("Starting trace readback", trace_id, flush=True)
    code = (
        "import json,sys,mlflow; "
        "mlflow.set_tracking_uri(sys.argv[1]); "
        "mlflow.flush_trace_async_logging(); "
        "t=mlflow.get_trace(sys.argv[2]); "
        "assert t and t.data.spans, 'Missing smoke spans'; "
        "assert any(s.name == 'E23_anchor_first' for s in t.data.spans); "
        "print(json.dumps({'trace_id':sys.argv[2], 'spans':len(t.data.spans)}))"
    )
    started = perf_counter()
    result = subprocess.run(
        [sys.executable, "-c", code, mlflow.get_tracking_uri(), trace_id],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    receipt = json.loads(result.stdout.strip().splitlines()[-1])
    receipt["readback_seconds"] = perf_counter() - started
    print("Verified trace", json.dumps(receipt), flush=True)
    return receipt


def validate_native(result, rows):
    frame = result.result_df
    require(frame is not None and len(frame) == len(rows), "Missing native rows")
    for metric in METRICS:
        values = frame[f"{metric}/value"]
        require(all(math.isfinite(float(v)) for v in values), f"Nonfinite {metric}")
        for suffix in ("error_code", "error_message"):
            column = f"{metric}/{suffix}"
            if column in frame:
                require(frame[column].dropna().eq("").all(), f"Native error: {column}")
        mean = result.metrics[f"{metric}/mean"]
        require(math.isfinite(float(mean)), f"Missing native mean: {metric}")
        expected = sum(r["metrics"][metric] for r in rows) / len(rows)
        require(math.isclose(mean, expected, abs_tol=1e-12), f"Mean mismatch: {metric}")
        require(
            math.isclose(float(values.mean()), expected, abs_tol=1e-12),
            f"Assessment mean mismatch: {metric}",
        )


def main():
    started = perf_counter()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    kind = "smoke" if args.smoke else "full"
    require(
        os.environ["MLFLOW_DISABLE_TELEMETRY"].lower() == "true",
        "E23 requires MLFLOW_DISABLE_TELEMETRY=true",
    )
    experiment = configure_tracking()
    client = mlflow.MlflowClient()
    runs = [client.get_run(run_id) for run_id in (E21, E15)]
    require(all(r.info.status == "FINISHED" for r in runs), "Sources not FINISHED")
    folder = Path("tmp/e23")
    folder.mkdir(parents=True, exist_ok=True)
    local_paths = {p: Path(p) for p in FROZEN_HASHES if not p.startswith((E21, E15))}
    sources = []
    for run_id in (E21, E15):
        destination = folder / run_id
        destination.mkdir(exist_ok=True)
        path = Path(
            client.download_artifacts(
                run_id, "per-question-results.json", str(destination.resolve())
            )
        )
        local_paths[run_id + "/per-question-results.json"] = path
        sources.append(json.loads(path.read_text(encoding="utf-8"))["records"])
    hashes = {name: sha(path) for name, path in local_paths.items()}
    require(hashes == FROZEN_HASHES, "Frozen source/tokenizer/artifact hash mismatch")
    for name, path in SOURCE_PATHS.items():
        require(all(r.data.params[name] == hashes[path] for r in runs), name)
    code_hashes = {p: sha(p) for p in REPRODUCTION}
    records = evaluation_records(Path(SOURCE_PATHS["chunks_sha256"]))
    require(len(records) == len(sources[0]) == len(sources[1]) == 142, "Not dev142")
    lookup = [{key(r): r for r in rows} for rows in sources]
    require(len({key(r) for r in records}) == 142, "Duplicate dev inputs")
    require(
        all(len(x) == 142 and set(x) == {key(r) for r in records} for x in lookup),
        "Source keys differ",
    )
    for language in ("ru", "en"):
        require(
            sum(r["inputs"]["language"] == language for r in records) == 71, "Not 71+71"
        )
    chunks = read_jsonl(Path(SOURCE_PATHS["chunks_sha256"]))
    by_id = {d["chunk_id"]: d for d in chunks}
    require(len(by_id) == len(chunks), "Duplicate source IDs")
    links = chunk_successors(chunks)
    pages = {
        (p["document_id"], p["pdf_page"]): p
        for p in read_jsonl(Path(SOURCE_PATHS["cleaned_pages_sha256"]))
    }
    metadata = Path(
        "data/models/bge-m3/.cache/huggingface/download/tokenizer.json.metadata"
    )
    require(
        metadata.read_text().splitlines()[0] == MODEL_REVISION,
        "Tokenizer revision changed",
    )
    tokenizer = AutoTokenizer.from_pretrained(
        "data/models/bge-m3", local_files_only=True
    )

    def tokens(text):
        return len(tokenizer.encode(text, add_special_tokens=False))

    replay_started = perf_counter()
    for record in records:
        a, b = (source[key(record)] for source in lookup)
        require(record["inputs"] == a["inputs"] == b["inputs"], "Input mismatch")
        require(
            record["expectations"] == a["expectations"] == b["expectations"],
            "Gold changed",
        )
        da, db = a["outputs"]["documents"], b["outputs"]["documents"]
        require(
            len(da) == len(db) == len({d["chunk_id"] for d in db}) == 50,
            "Not unique top50",
        )
        require(
            {d["chunk_id"]: d for d in da} == {d["chunk_id"]: d for d in db},
            "Pool/scores changed",
        )
        require(
            all(all(d[k] == v for k, v in by_id[d["chunk_id"]].items()) for d in db),
            "Source chunks changed",
        )
        ordered = prioritize_rule_neighbors(db, links)
        context = pack_context(ordered, BUDGET, tokens)
        require(
            ordered == a["outputs"]["context_candidates"], "E21 ordering replay failed"
        )
        require(context == a["outputs"]["context"], "E21 context replay failed")
        require(
            evidence_metrics(
                context["documents"], record["expectations"]["required_evidence"], pages
            )
            == a["metrics"],
            "E21 metric replay failed",
        )
        require(
            pack_context(db, BUDGET, tokens) == b["outputs"]["context"],
            "E15 context replay failed",
        )
    replay_seconds = perf_counter() - replay_started
    print("Verified 142 E21 replays, E15 contexts and 10 frozen hashes", flush=True)
    if args.smoke:
        records = records[:3]
    else:
        smoke = json.loads((folder / "smoke.json").read_text(encoding="utf-8"))
        require(
            smoke["status"] == "FINISHED"
            and smoke["input_hashes"] == hashes
            and smoke["code_hashes"] == code_hashes
            and smoke["trace"]["spans"] > 0,
            "Fresh successful smoke required",
        )
        require(
            client.get_run(smoke["run_id"]).info.status == "FINISHED",
            "Smoke run not FINISHED",
        )
    digest = hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()[
        :16
    ]
    name = "football-e23-" + digest
    existing = next(
        (
            d
            for d in client.search_datasets(experiment_ids=[experiment])
            if d.name == name
        ),
        None,
    )
    if existing:
        dataset = get_dataset(dataset_id=existing.dataset_id)
        dataset_records = [
            {"inputs": r["inputs"], "expectations": r["expectations"]}
            for r in dataset.df.to_dict("records")
        ]
        require(
            canonical(dataset_records) == canonical(records),
            "Existing native dataset changed",
        )
    else:
        dataset = create_dataset(
            name=name, experiment_id=[experiment], tags={"split": "dev"}
        )
        dataset.merge_records(records)
    observations = {}

    @mlflow.trace(name="E23_anchor_first", span_type="CHAIN")
    def predict(query, language):
        documents = lookup[1][query, language]["outputs"]["documents"]
        packing_started = perf_counter()
        context = pack_anchor_first_context(documents, links, BUDGET, tokens)
        output = {
            "documents": documents,
            "context": context,
            "packing_seconds": perf_counter() - packing_started,
        }
        observations[query, language] = output
        return output

    trace_receipt = None
    with mlflow.start_run(run_name="E23-anchor-first-" + kind) as run:
        run_id = run.info.run_id
        print("STARTED", run_id, kind, flush=True)
        mlflow.set_tags(
            {"stage": "retrieval", "run_kind": kind, "default_changed": "false"}
        )
        mlflow.log_params(
            {
                "e21_run": E21,
                "e15_run": E15,
                "split": "dev",
                "questions": len(records),
                "context_budget": BUDGET,
                "policy": "anchor_first_one_predecessor_one_successor_no_eviction",
                "tokenizer_revision": MODEL_REVISION,
                "tokenizer": "data/models/bge-m3",
                "latency_scope": "cached_packing_only",
                "mlflow_disable_telemetry": os.environ["MLFLOW_DISABLE_TELEMETRY"],
                "eval_max_workers": os.environ["MLFLOW_GENAI_EVAL_MAX_WORKERS"],
                "eval_max_scorer_workers": os.environ[
                    "MLFLOW_GENAI_EVAL_MAX_SCORER_WORKERS"
                ],
                **{name: hashes[p] for name, p in SOURCE_PATHS.items()},
            }
        )
        for path in REPRODUCTION:
            mlflow.log_artifact(path, artifact_path="reproduction")
        mlflow.log_dict(hashes, "input-hashes.json")
        mlflow.log_dict(code_hashes, "code-hashes.json")
        mlflow.log_dict(links, "neighbor-links.json")
        if args.smoke:
            # Synchronous trace persistence avoids an unbounded parent flush.
            os.environ["MLFLOW_ENABLE_ASYNC_TRACE_LOGGING"] = "false"
            mlflow.log_param("smoke_async_trace_logging", "false")
            predict(**records[0]["inputs"])
            trace_id = mlflow.get_last_active_trace_id()
            print("TRACE", trace_id, flush=True)
            mlflow.log_dict({"trace_id": trace_id}, "smoke-trace-id.json")
            trace_receipt = trace_readback(trace_id)
            mlflow.log_dict(trace_receipt, "trace-readback.json")
        # Local MLflow blocks persisted custom scorers for security; use the
        # same source-controlled scorer imports as E21/E22, not unsafe opt-in.
        scorers = [make_evidence_scorer(metric, pages) for metric in METRICS]
        mlflow.set_tag("scorer_execution", "imported_repository_code")
        evaluation_started = perf_counter()
        result = mlflow.genai.evaluate(
            data=dataset, predict_fn=predict, scorers=scorers
        )
        evaluation_seconds = perf_counter() - evaluation_started
        rows = []
        for record in records:
            output = observations[key(record)]
            context = output["context"]
            selected = context["documents"]
            pool = {d["chunk_id"]: d for d in output["documents"]}
            require(
                len(selected) == len({d["chunk_id"] for d in selected}),
                "Duplicate packed IDs",
            )
            require(
                all(d == pool[d["chunk_id"]] for d in selected),
                "Packed chunk outside frozen pool",
            )
            require(
                context["text"] == render_context(selected), "Context rendering changed"
            )
            require(
                tokens(context["text"]) == context["token_count"] <= BUDGET,
                "Exact token budget failed",
            )
            values = evidence_metrics(
                selected, record["expectations"]["required_evidence"], pages
            )
            rows.append(
                {
                    **record,
                    "outputs": output,
                    "metrics": values,
                    "baseline_metrics": lookup[0][key(record)]["metrics"],
                }
            )
        validate_native(result, rows)
        by_language = {}
        for language in ("ru", "en"):
            subset = [r for r in rows if r["inputs"]["language"] == language]
            by_language[language] = {
                "n": len(subset),
                "metrics": {
                    m: sum(r["metrics"][m] for r in subset) / len(subset)
                    for m in METRICS
                },
                "baseline_metrics": {
                    m: sum(r["baseline_metrics"][m] for r in subset) / len(subset)
                    for m in METRICS
                },
                "complete_count": sum(
                    r["metrics"]["complete_evidence"] for r in subset
                ),
                "baseline_complete_count": sum(
                    r["baseline_metrics"]["complete_evidence"] for r in subset
                ),
                "improved_ids": [
                    r["expectations"]["scenario_id"]
                    for r in subset
                    if r["metrics"]["complete_evidence"]
                    > r["baseline_metrics"]["complete_evidence"]
                ],
                "regressed_ids": [
                    r["expectations"]["scenario_id"]
                    for r in subset
                    if r["metrics"]["complete_evidence"]
                    < r["baseline_metrics"]["complete_evidence"]
                ],
            }
        mean_cer = sum(r["metrics"]["complete_evidence"] for r in rows) / len(rows)
        baseline_cer = sum(
            r["baseline_metrics"]["complete_evidence"] for r in rows
        ) / len(rows)
        gate = (
            None
            if args.smoke
            else mean_cer > baseline_cer
            and all(
                v["complete_count"] >= v["baseline_complete_count"] - 1
                for v in by_language.values()
            )
        )
        require(
            {name: sha(path) for name, path in local_paths.items()} == hashes,
            "Inputs changed during run",
        )
        require(
            {p: sha(p) for p in REPRODUCTION} == code_hashes, "Code changed during run"
        )
        summary = {
            "by_language": by_language,
            "native_metrics": result.metrics,
            "mean_cer": mean_cer,
            "baseline_mean_cer": baseline_cer,
            "future_generation_gate": gate,
            "default_changed": False,
            "timing": {
                "replay_seconds": replay_seconds,
                "native_evaluation_seconds": evaluation_seconds,
                "packing_seconds": sum(r["outputs"]["packing_seconds"] for r in rows),
                "elapsed_before_artifact_export_seconds": perf_counter() - started,
            },
        }
        mlflow.log_dict({"records": rows}, "per-question-results.json")
        mlflow.log_dict(summary, "summary.json")
        mlflow.log_metrics(
            {
                f"{lang}_{m}": v["metrics"][m]
                for lang, v in by_language.items()
                for m in METRICS
            }
        )
        receipt = {
            "run_id": run_id,
            "run_kind": kind,
            "status": "FINISHED",
            "questions": len(rows),
            "input_hashes": hashes,
            "code_hashes": code_hashes,
            "trace": trace_receipt,
            "summary": summary,
        }
        mlflow.log_dict(receipt, "run-receipt.json")
    # Write a successful receipt only after the native run context finishes.
    receipt["end_to_end_seconds"] = perf_counter() - started
    text = json.dumps(receipt, ensure_ascii=False, indent=2, allow_nan=False)
    (folder / (run_id + ".json")).write_text(text, encoding="utf-8")
    (folder / (kind + ".json")).write_text(text, encoding="utf-8")
    print("FINISHED", text, flush=True)


if __name__ == "__main__":
    main()
