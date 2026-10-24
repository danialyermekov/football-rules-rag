"""Native MLflow dataset + deterministic scorers + one run per retrieval experiment."""

import argparse
import hashlib
import json
import os
from pathlib import Path
from statistics import quantiles
from time import perf_counter

import mlflow
from mlflow.entities import Feedback
from mlflow.genai.datasets import create_dataset, get_dataset
from mlflow.genai.scorers import scorer

from football_rules.bm25 import BM25Retriever
from football_rules.embeddings import MODEL_ID, MODEL_REVISION, load_embedder
from football_rules.evidence_evaluation import (
    chunk_successors,
    evidence_metrics,
    pack_context,
    prioritize_successors,
)
from football_rules.hybrid import HybridRetriever
from football_rules.retrieval import DenseRetriever, read_chunks
from football_rules.retrieval_metrics import ranking_metrics, relevant_chunks
from football_rules.tracking import configure_tracking


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def evaluation_records(chunks_path, protocol="v2"):
    chunks = read_chunks(chunks_path) if protocol == "v1" else []
    pages = {
        (page["document_id"], page["pdf_page"]): page
        for page in read_jsonl(Path("data/processed/cleaned-pages.jsonl"))
    }
    evidence = {
        item["id"]: item for item in read_jsonl(Path("data/evaluation/evidence.jsonl"))
    }
    records = []

    for row in read_jsonl(Path("data/evaluation/scenarios.jsonl")):
        if row["split"] != "dev" or not row["required_evidence"]:
            continue

        for language in ("ru", "en"):
            locators = [
                span
                for key in row["required_evidence"]
                for span in evidence[key]["locators"][language]
            ]
            records.append(
                {
                    "inputs": {
                        "query": row["questions"][language],
                        "language": language,
                    },
                    "expectations": {
                        "scenario_id": row["id"],
                    },
                }
            )

            if protocol == "v2":
                records[-1]["expectations"]["required_evidence"] = [
                    {"id": key, "locators": evidence[key]["locators"][language]}
                    for key in row["required_evidence"]
                ]
            else:
                records[-1]["expectations"]["relevant_chunk_ids"] = relevant_chunks(
                    chunks, locators, pages
                )

    return records


def make_scorer(metric):
    @scorer(name=metric)
    def score(outputs, expectations):
        retrieved = [item["chunk_id"] for item in outputs["documents"]]
        gold = expectations["relevant_chunk_ids"]
        return [
            Feedback(
                name=f"{metric}_at_{k}",
                value=ranking_metrics(retrieved, gold, k)[metric],
            )
            for k in (1, 3, 5, 10)
        ]

    return score


def make_evidence_scorer(metric, pages):
    @scorer(name=metric)
    def score(outputs, expectations):
        values = evidence_metrics(
            outputs["context"]["documents"], expectations["required_evidence"], pages
        )
        return values[metric]

    return score


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection")
    parser.add_argument(
        "--embedding",
        choices=["bge-m3", "qwen3-0.6b", "multilingual-e5-large"],
        default="bge-m3",
    )
    parser.add_argument(
        "--strategy", choices=["dense", "bm25", "hybrid"], default="dense"
    )
    parser.add_argument("--database", type=Path, default=Path("data/qdrant"))
    parser.add_argument(
        "--chunks", type=Path, default=Path("data/processed/chunks.jsonl")
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--run-name", help="MLflow run label for a controlled experiment"
    )
    parser.add_argument("--verify-trace", action="store_true")
    parser.add_argument("--protocol", choices=["v1", "v2"], default="v2")
    parser.add_argument("--context-budget", type=int, default=2048)
    parser.add_argument(
        "--context-policy",
        choices=["rank_order", "successor_first", "page_continuation"],
        default="rank_order",
    )
    args = parser.parse_args()

    if args.strategy in {"dense", "hybrid"} and not args.collection:
        parser.error("--collection is required for dense/hybrid retrieval")

    if args.strategy != "dense" and args.protocol != "v2":
        parser.error("BM25/hybrid experiments require protocol v2")

    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be positive")

    if args.context_budget <= 0:
        parser.error("--context-budget must be positive")

    if args.context_policy != "rank_order" and args.protocol != "v2":
        parser.error("Context ordering experiments require protocol v2")

    os.environ["MLFLOW_GENAI_EVAL_MAX_WORKERS"] = "1"
    experiment_id = configure_tracking()
    records = evaluation_records(args.chunks, args.protocol)
    pages = {
        (page["document_id"], page["pdf_page"]): page
        for page in read_jsonl(Path("data/processed/cleaned-pages.jsonl"))
    }

    if args.limit:
        records = records[: args.limit]

    legacy_records = (
        records if args.protocol == "v1" else evaluation_records(args.chunks, "v1")
    )
    gold_by_question = {
        (record["inputs"]["query"], record["inputs"]["language"]): record[
            "expectations"
        ]["relevant_chunk_ids"]
        for record in legacy_records
    }

    fingerprint = hashlib.sha256(
        json.dumps(records, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    dataset_name = f"football-dev-{args.protocol}-" + fingerprint[:16]
    client = mlflow.MlflowClient()
    existing = client.search_datasets(experiment_ids=[experiment_id])
    matches = [item for item in existing if item.name == dataset_name]

    if matches:
        dataset = get_dataset(dataset_id=matches[0].dataset_id)
    else:
        dataset = create_dataset(
            name=dataset_name,
            experiment_id=[experiment_id],
            tags={"split": "dev", "protocol": args.protocol},
        )
        dataset.merge_records(records)

    if args.strategy in {"dense", "hybrid"}:
        embedder = load_embedder(args.embedding)
        retriever = DenseRetriever(args.database, args.collection, embedder)
        if args.strategy == "hybrid":
            retriever = HybridRetriever(retriever, BM25Retriever(args.chunks))
    else:
        retriever = BM25Retriever(args.chunks)

    from transformers import AutoTokenizer

    tokenizer_metadata = Path(
        "data/models/bge-m3/.cache/huggingface/download/tokenizer.json.metadata"
    )

    if tokenizer_metadata.read_text(encoding="utf-8").splitlines()[:1] != [
        MODEL_REVISION
    ]:
        raise ValueError("Budget tokenizer differs from the pinned BGE revision")

    tokenizer = AutoTokenizer.from_pretrained(
        "data/models/bge-m3", local_files_only=True
    )

    if (
        retriever.manifest["chunks_sha256"]
        != hashlib.sha256(args.chunks.read_bytes()).hexdigest()
    ):
        if isinstance(retriever, (DenseRetriever, HybridRetriever)):
            retriever.close()
        raise ValueError("Evaluation chunks differ from the indexed corpus")

    metrics = (
        "evidence_coverage",
        "evidence_recall",
        "complete_evidence",
        "strict_complete_evidence",
    )
    scorers = (
        [make_evidence_scorer(metric, pages) for metric in metrics]
        if args.protocol == "v2"
        else [make_scorer(metric) for metric in ("recall", "precision", "mrr", "ndcg")]
    )
    observations = {}
    trace_ids = []
    successors = (
        chunk_successors(
            read_chunks(args.chunks),
            cross_page_only=args.context_policy == "page_continuation",
        )
        if args.context_policy != "rank_order"
        else {}
    )

    def count_tokens(text):
        return len(tokenizer.encode(text, add_special_tokens=False))

    @mlflow.trace(name=f"{args.strategy}_retrieval", span_type="CHAIN")
    def predict(query, language):
        started = perf_counter()
        documents = retriever.search(
            query, language, 50 if args.protocol == "v2" else 10
        )
        retrieval_seconds = perf_counter() - started
        output = {"documents": documents, "retrieval_seconds": retrieval_seconds}

        if args.strategy == "hybrid":
            output["fusion_candidates"] = documents
            documents = documents[:50]
            output["documents"] = documents

        if args.protocol == "v2":
            packing_started = perf_counter()
            context_candidates = (
                prioritize_successors(documents, successors)
                if args.context_policy != "rank_order"
                else documents
            )
            if args.context_policy != "rank_order":
                output["context_candidates"] = context_candidates

            with mlflow.start_span(name="context_packing", span_type="CHAIN") as span:
                span.set_inputs(
                    {
                        "candidate_ids": [
                            item["chunk_id"] for item in context_candidates
                        ],
                        "budget": args.context_budget,
                        "context_policy": args.context_policy,
                    }
                )
                output["context"] = pack_context(
                    context_candidates, args.context_budget, count_tokens
                )
                span.set_outputs(output["context"])

            output["packing_seconds"] = perf_counter() - packing_started

        output["latency_seconds"] = retrieval_seconds + output.get("packing_seconds", 0)
        observations[query, language] = output

        active_span = mlflow.get_current_active_span()

        if active_span is not None:
            trace_ids.append(active_span.trace_id)

        return output

    try:
        with mlflow.start_run(
            run_name=(
                args.run_name
                or (
                    {
                        "dense": "E0-dense-baseline-v2",
                        "bm25": "E1-bm25-v2",
                        "hybrid": "E2-hybrid-rrf-v2",
                    }[args.strategy]
                    if args.protocol == "v2"
                    else "dense-baseline-v1"
                )
            )
            + ("-dry-run" if args.limit else "")
        ) as run:
            mlflow.set_tag("run_kind", "smoke" if args.limit else "full")
            mlflow.log_dict(retriever.manifest, "index-manifest.json")
            if args.context_policy != "rank_order":
                mlflow.log_dict(
                    {
                        "version": args.context_policy + "_v1",
                        "boundary": (
                            "consecutive_page_bullet"
                            if args.context_policy == "page_continuation"
                            else "same_page_or_consecutive_page_bullet"
                        ),
                        "candidate_expansion": False,
                        "max_successors_per_anchor": 1,
                        "recursive": False,
                        "successors": successors,
                    },
                    "context-ordering.json",
                )
            mlflow.log_params(
                {
                    "strategy": args.strategy,
                    "language_filter": "same_language",
                    "split": "dev",
                    "questions": len(records),
                    "qrel_coverage": 0.8,
                    "dataset_sha256": fingerprint,
                    "evaluation_protocol": args.protocol,
                    "candidate_pool_size": 50 if args.protocol == "v2" else 10,
                    "context_budget": (
                        args.context_budget
                        if args.protocol == "v2"
                        else "not_applicable"
                    ),
                    "budget_tokenizer": (
                        "BAAI/bge-m3" if args.protocol == "v2" else "not_applicable"
                    ),
                    "packing_policy": "whole_chunks_skip_oversized_exact_id_dedup_v1",
                    "context_policy": args.context_policy,
                    "historical_run_id": "bcf4cea80728477ba9ebd41093b56df5",
                    "control_run_id": "7c739293e3284f39833421cc9b8f400a",
                }
            )
            if args.strategy in {"dense", "hybrid"}:
                mlflow.log_params(
                    {
                        f"embedding_{key}": value
                        for key, value in retriever.manifest["embedding"].items()
                    }
                )
            if args.strategy in {"bm25", "hybrid"}:
                bm25_parameters = (
                    retriever.manifest["bm25"]
                    if args.strategy == "hybrid"
                    else retriever.manifest
                )
                mlflow.log_params(
                    {f"bm25_{key}": value for key, value in bm25_parameters.items()}
                )
            if args.strategy == "hybrid":
                mlflow.log_params(
                    {
                        f"fusion_{key}": value
                        for key, value in retriever.manifest["fusion"].items()
                    }
                )
                mlflow.log_param("branch_depth", 50)
            chunking = read_chunks(args.chunks)[0]["chunking"]
            mlflow.log_params(
                {f"chunking_{key}": value for key, value in chunking.items()}
            )

            for name, path in [
                ("scenarios", Path("data/evaluation/scenarios.jsonl")),
                ("evidence", Path("data/evaluation/evidence.jsonl")),
                ("cleaned_pages", Path("data/processed/cleaned-pages.jsonl")),
            ]:
                mlflow.log_param(
                    f"{name}_sha256", hashlib.sha256(path.read_bytes()).hexdigest()
                )

            mlflow.log_param("chunks_sha256", retriever.manifest["chunks_sha256"])
            mlflow.log_metric(
                "questions_without_relevant_chunks_v1",
                sum(
                    not gold_by_question[
                        record["inputs"]["query"], record["inputs"]["language"]
                    ]
                    for record in records
                ),
            )
            if args.protocol == "v2":
                mlflow.log_dict(
                    {
                        "version": "evidence_union_v2.0.0",
                        "coverage_unit": "retained_nonwhitespace_source_characters",
                        "required_units": "AND",
                        "locators_per_unit": "AND",
                        "threshold": 0.8,
                        "strict_threshold": 1.0,
                        "coverage_aggregation": "mean_locators_then_units_then_questions",
                        "alternatives": "not_annotated_not_implemented",
                        "tokenizer": MODEL_ID,
                        "tokenizer_revision": MODEL_REVISION,
                        "add_special_tokens": False,
                        "context_budget": args.context_budget,
                        "packing": "rank_order_whole_chunks_skip_nonfitting",
                        "partial_overlap": "counts_in_budget_once_in_coverage",
                        "exact_id_duplicates": "removed",
                    },
                    "evaluation-protocol.json",
                )
                mlflow.log_artifact("docs/evidence-audit-e0.md")

            mlflow.log_artifact("docs/source-manifest.json")
            mlflow.log_artifact(str(args.chunks), artifact_path="corpus")
            mlflow.log_artifact("uv.lock")
            mlflow.log_artifact("pyproject.toml")
            mlflow.log_artifact(__file__, artifact_path="code")

            for name in (
                "embeddings",
                "chunking",
                "cleaning",
                "bm25",
                "hybrid",
                "retrieval",
                "retrieval_metrics",
                "evidence_evaluation",
            ):
                mlflow.log_artifact(
                    f"src/football_rules/{name}.py", artifact_path="code"
                )
            result = mlflow.genai.evaluate(
                data=dataset, predict_fn=predict, scorers=scorers
            )
            trace_id = trace_ids[-1] if trace_ids else None
            rows = []

            for record in records:
                inputs = record["inputs"]
                output = observations[inputs["query"], inputs["language"]]
                retrieved = [item["chunk_id"] for item in output["documents"]]
                values = {
                    f"{metric}_at_{k}": value
                    for k in (1, 3, 5, 10)
                    for metric, value in ranking_metrics(
                        retrieved,
                        gold_by_question[inputs["query"], inputs["language"]],
                        k,
                    ).items()
                }

                if args.protocol == "v2":
                    required = record["expectations"]["required_evidence"]
                    values = {f"chunk_v1_{key}": value for key, value in values.items()}
                    values.update(
                        evidence_metrics(
                            output["context"]["documents"], required, pages
                        )
                    )
                    values["context_tokens"] = output["context"]["token_count"]

                    if args.strategy == "hybrid":
                        union = output["fusion_candidates"]
                        values["fusion_union_size"] = len(union)
                        values.update(
                            {
                                f"candidate_union_{key}": value
                                for key, value in evidence_metrics(
                                    union, required, pages
                                ).items()
                            }
                        )

                    for depth in (10, 20, 50):
                        candidate_values = evidence_metrics(
                            output["documents"][:depth], required, pages
                        )
                        values.update(
                            {
                                f"candidate_{depth}_{key}": value
                                for key, value in candidate_values.items()
                            }
                        )

                    for budget in sorted({1024, 2048, 4096, args.context_budget}):
                        packed = (
                            output["context"]
                            if budget == args.context_budget
                            else pack_context(
                                output.get("context_candidates", output["documents"]),
                                budget,
                                count_tokens,
                            )
                        )
                        packed_values = evidence_metrics(
                            packed["documents"], required, pages
                        )
                        values.update(
                            {
                                f"budget_{budget}_{key}": value
                                for key, value in packed_values.items()
                            }
                        )

                        output.setdefault("budget_selections", {})[str(budget)] = {
                            "chunk_ids": [
                                item["chunk_id"] for item in packed["documents"]
                            ],
                            "token_count": packed["token_count"],
                            "skipped": packed["skipped"],
                        }

                rows.append({**record, "outputs": output, "metrics": values})

            summary = {}

            for language in ("ru", "en"):
                selected = [
                    row for row in rows if row["inputs"]["language"] == language
                ]

                if not selected:
                    continue

                values = {
                    f"{language}_{key}": sum(row["metrics"][key] for row in selected)
                    / len(selected)
                    for key in selected[0]["metrics"]
                }
                values[f"{language}_latency_seconds_mean"] = sum(
                    row["outputs"]["latency_seconds"] for row in selected
                ) / len(selected)

                for stage in (
                    "retrieval_seconds",
                    "packing_seconds",
                    "latency_seconds",
                ):
                    durations = [
                        row["outputs"][stage]
                        for row in selected
                        if stage in row["outputs"]
                    ]

                    if durations:
                        percentiles = (
                            quantiles(durations, n=100, method="inclusive")
                            if len(durations) > 1
                            else durations * 99
                        )
                        values[f"{language}_{stage}_p50"] = percentiles[49]
                        values[f"{language}_{stage}_p95"] = percentiles[94]

                summary.update(values)

            mlflow.log_metrics(summary)
            mlflow.log_dict({"records": rows}, "per-question-results.json")
            mlflow.log_dict(
                {"metrics": result.metrics, "by_language": summary}, "summary.json"
            )
            print(
                json.dumps(
                    {
                        "run_id": run.info.run_id,
                        "questions": len(records),
                        "trace_id": trace_id,
                        "metrics": {
                            key: value
                            for key, value in summary.items()
                            if "chunk_v1" not in key
                            and "budget_" not in key
                            and "source_redundancy" not in key
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                flush=True,
            )

        if args.verify_trace:
            print("Starting trace readback", flush=True)
            mlflow.flush_trace_async_logging()
            trace = mlflow.get_trace(trace_id) if trace_id else None

            if trace is None or not trace.data.spans:
                raise RuntimeError("Trace readback failed")

            print(
                "Verified spans:",
                [(span.name, span.span_type) for span in trace.data.spans],
                flush=True,
            )
    finally:
        if isinstance(retriever, (DenseRetriever, HybridRetriever)):
            retriever.close()


if __name__ == "__main__":
    main()
