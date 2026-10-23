"""E3/E4: rerank a fixed Dense20 or RRF20 replay against its original order."""

import argparse
import hashlib
import json
import os
from pathlib import Path
from statistics import quantiles
from time import perf_counter

import mlflow
from evaluate_retrieval import evaluation_records, make_evidence_scorer, read_jsonl
from mlflow.genai.datasets import create_dataset, get_dataset
from transformers import AutoTokenizer

from football_rules.embeddings import MODEL_REVISION as BUDGET_REVISION
from football_rules.evidence_evaluation import evidence_metrics, pack_context
from football_rules.reranking import CrossEncoderReranker
from football_rules.retrieval import read_chunks
from football_rules.tracking import configure_tracking

SOURCE_RUN = "7c739293e3284f39833421cc9b8f400a"


def replay_configuration(parameters: dict[str, str]) -> tuple[str, str]:
    if (
        parameters.get("strategy") not in {"dense", "hybrid"}
        or parameters.get("evaluation_protocol") != "v2"
        or parameters.get("context_budget") != "2048"
    ):
        raise ValueError(
            "Source must be a Dense or RRF v2 run with context budget 2048"
        )

    if parameters["strategy"] == "hybrid":
        expected = {
            "fusion_method": "RRF",
            "fusion_rank_constant": "60",
            "fusion_rank_origin": "1",
            "fusion_weights": "equal",
            "branch_depth": "50",
        }
        if any(parameters.get(key) != value for key, value in expected.items()):
            raise ValueError("RRF source must match the E2 fusion configuration")
        return "E4-rrf20-reranker-v2", "rrf"

    return "E3-dense20-reranker-v2", "dense"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--source-run", default=SOURCE_RUN)
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cuda")
    parser.add_argument("--verify-trace", action="store_true")
    args = parser.parse_args()
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be positive")

    os.environ["MLFLOW_GENAI_EVAL_MAX_WORKERS"] = "1"
    experiment_id = configure_tracking()
    client = mlflow.MlflowClient()
    source_run = client.get_run(args.source_run)
    if source_run.info.status != "FINISHED":
        raise ValueError("Source run is incomplete")
    run_name, source_strategy = replay_configuration(source_run.data.params)

    destination = Path(f"tmp/{source_strategy}-reranker-source")
    destination.mkdir(parents=True, exist_ok=True)
    source_path = client.download_artifacts(
        args.source_run, "per-question-results.json", str(destination)
    )
    protocol_path = client.download_artifacts(
        args.source_run, "evaluation-protocol.json", str(destination)
    )
    source_rows = json.loads(Path(source_path).read_text(encoding="utf-8"))["records"]
    source = {
        (row["inputs"]["query"], row["inputs"]["language"]): row for row in source_rows
    }
    chunks_path = Path("data/processed/chunks.jsonl")
    chunks = {chunk["chunk_id"]: chunk for chunk in read_chunks(chunks_path)}

    for parameter, path in (
        ("chunks_sha256", chunks_path),
        ("scenarios_sha256", Path("data/evaluation/scenarios.jsonl")),
        ("evidence_sha256", Path("data/evaluation/evidence.jsonl")),
        ("cleaned_pages_sha256", Path("data/processed/cleaned-pages.jsonl")),
    ):
        if (
            hashlib.sha256(path.read_bytes()).hexdigest()
            != source_run.data.params[parameter]
        ):
            raise ValueError(f"Source run differs from current {parameter}")

    records = evaluation_records(chunks_path)
    for record in records:
        row = source[record["inputs"]["query"], record["inputs"]["language"]]
        if row["expectations"] != record["expectations"]:
            raise ValueError("Source gold differs from the current dataset")
        candidates = row["outputs"]["documents"][:20]
        if len(candidates) != 20 or len({hit["chunk_id"] for hit in candidates}) != 20:
            raise ValueError("Replay must supply 20 unique candidates")
        for hit in candidates:
            if any(hit[key] != value for key, value in chunks[hit["chunk_id"]].items()):
                raise ValueError("Source candidate differs from the current corpus")

    if args.limit:
        records = records[: args.limit]
    fingerprint = hashlib.sha256(
        json.dumps(records, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    name = "football-dev-v2-" + fingerprint[:16]
    matches = [
        item
        for item in client.search_datasets(experiment_ids=[experiment_id])
        if item.name == name
    ]
    if matches:
        dataset = get_dataset(dataset_id=matches[0].dataset_id)
    else:
        dataset = create_dataset(
            name=name,
            experiment_id=[experiment_id],
            tags={"split": "dev", "protocol": "v2"},
        )
        dataset.merge_records(records)

    metadata = Path(
        "data/models/bge-m3/.cache/huggingface/download/tokenizer.json.metadata"
    )
    if metadata.read_text(encoding="utf-8").splitlines()[:1] != [BUDGET_REVISION]:
        raise ValueError("Budget tokenizer differs from E0")
    tokenizer = AutoTokenizer.from_pretrained(
        "data/models/bge-m3", local_files_only=True
    )
    reranker = CrossEncoderReranker(args.device)
    pages = {
        (page["document_id"], page["pdf_page"]): page
        for page in read_jsonl(Path("data/processed/cleaned-pages.jsonl"))
    }
    metrics = (
        "evidence_coverage",
        "evidence_recall",
        "complete_evidence",
        "strict_complete_evidence",
    )
    observations = {}
    trace_ids = []

    def count_tokens(text):
        return len(tokenizer.encode(text, add_special_tokens=False))

    @mlflow.trace(name=f"{source_strategy}20_reranker_replay", span_type="CHAIN")
    def predict(query, language):
        candidates = source[query, language]["outputs"]["documents"][:20]
        control_context = pack_context(candidates, 2048, count_tokens)
        started = perf_counter()
        documents = reranker.rerank(query, candidates)
        reranking_seconds = perf_counter() - started
        with mlflow.start_span(name="context_packing", span_type="CHAIN") as span:
            span.set_inputs(
                {
                    "candidate_ids": [hit["chunk_id"] for hit in documents],
                    "budget": 2048,
                }
            )
            packing_started = perf_counter()
            context = pack_context(documents, 2048, count_tokens)
            packing_seconds = perf_counter() - packing_started
            span.set_outputs(context)
        output = {
            "documents": documents,
            "source_candidates": candidates,
            "context": context,
            "control_context": control_context,
            "reranking_seconds": reranking_seconds,
            "packing_seconds": packing_seconds,
            "rerank_and_pack_seconds": reranking_seconds + packing_seconds,
        }
        observations[query, language] = output
        active = mlflow.get_current_active_span()
        if active is not None:
            trace_ids.append(active.trace_id)
        return output

    with mlflow.start_run(
        run_name=run_name + ("-dry-run" if args.limit else "")
    ) as run:
        mlflow.log_params(
            {
                "strategy": f"{source_strategy}_replay_reranker",
                "source_run_id": args.source_run,
                "candidate_pool_size": 20,
                "context_budget": 2048,
                "split": "dev",
                "questions": len(records),
                "dataset_sha256": fingerprint,
                "retrieval_execution": "replay_no_query_embedding_or_search",
                "latency_scope": "reranking_and_packing_only",
            }
        )
        mlflow.log_params(
            {f"reranker_{key}": value for key, value in reranker.parameters().items()}
        )
        if source_strategy == "rrf":
            mlflow.log_params(
                {
                    key: value
                    for key, value in source_run.data.params.items()
                    if key.startswith("fusion_") or key == "branch_depth"
                }
            )
        for key in (
            "chunks_sha256",
            "scenarios_sha256",
            "evidence_sha256",
            "cleaned_pages_sha256",
        ):
            mlflow.log_param(key, source_run.data.params[key])
        mlflow.log_artifact(protocol_path)
        mlflow.log_artifact(source_path, artifact_path="source")
        mlflow.log_artifact("uv.lock")
        mlflow.log_artifact("pyproject.toml")
        for path in (
            __file__,
            "scripts/evaluate_retrieval.py",
            "src/football_rules/reranking.py",
            "src/football_rules/evidence_evaluation.py",
        ):
            mlflow.log_artifact(path, artifact_path="code")
        pilot = Path("tmp/reranker-pilot.json")
        if pilot.exists():
            mlflow.log_artifact(str(pilot))

        import torch

        if args.device == "cuda":
            torch.cuda.reset_peak_memory_stats()
        result = mlflow.genai.evaluate(
            data=dataset,
            predict_fn=predict,
            scorers=[make_evidence_scorer(metric, pages) for metric in metrics],
        )
        rows = []
        for record in records:
            output = observations[
                record["inputs"]["query"], record["inputs"]["language"]
            ]
            required = record["expectations"]["required_evidence"]
            values = evidence_metrics(output["context"]["documents"], required, pages)
            values.update(
                {
                    f"control_{key}": value
                    for key, value in evidence_metrics(
                        output["control_context"]["documents"], required, pages
                    ).items()
                }
            )
            values.update(
                {
                    f"candidate_20_{key}": value
                    for key, value in evidence_metrics(
                        output["source_candidates"], required, pages
                    ).items()
                }
            )
            values["context_tokens"] = output["context"]["token_count"]
            rows.append({**record, "outputs": output, "metrics": values})
        summary = {}
        for language in ("ru", "en"):
            selected = [row for row in rows if row["inputs"]["language"] == language]
            if not selected:
                continue
            summary.update(
                {
                    f"{language}_{key}": sum(row["metrics"][key] for row in selected)
                    / len(selected)
                    for key in selected[0]["metrics"]
                }
            )
            for stage in (
                "reranking_seconds",
                "packing_seconds",
                "rerank_and_pack_seconds",
            ):
                durations = [row["outputs"][stage] for row in selected]
                percentiles = (
                    quantiles(durations, n=100, method="inclusive")
                    if len(durations) > 1
                    else durations * 99
                )
                summary[f"{language}_{stage}_p50"] = percentiles[49]
                summary[f"{language}_{stage}_p95"] = percentiles[94]
        if args.device == "cuda":
            summary["gpu_peak_allocated_mib"] = (
                torch.cuda.max_memory_allocated() / 2**20
            )
            summary["gpu_peak_reserved_mib"] = torch.cuda.max_memory_reserved() / 2**20
        mlflow.log_metrics(summary)
        mlflow.log_dict({"records": rows}, "per-question-results.json")
        mlflow.log_dict(
            {"metrics": result.metrics, "by_language": summary}, "summary.json"
        )
        trace_id = trace_ids[-1] if trace_ids else None
        print(
            json.dumps(
                {
                    "run_id": run.info.run_id,
                    "questions": len(rows),
                    "trace_id": trace_id,
                    "summary": summary,
                },
                indent=2,
            ),
            flush=True,
        )

    if args.verify_trace:
        print("Starting trace readback", flush=True)
        mlflow.flush_trace_async_logging()
        trace = mlflow.get_trace(trace_id) if trace_id else None
        if trace is None or not trace.data.spans:
            raise RuntimeError("Reranker trace readback failed")
        print(
            "Verified spans:",
            [(span.name, span.span_type) for span in trace.data.spans],
            flush=True,
        )


if __name__ == "__main__":
    main()
