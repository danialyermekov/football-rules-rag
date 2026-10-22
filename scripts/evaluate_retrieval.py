"""Native MLflow dataset + deterministic scorers + one run per retrieval experiment."""

import argparse
import hashlib
import json
import os
from pathlib import Path
from time import perf_counter

import mlflow
from mlflow.entities import Feedback
from mlflow.genai.datasets import create_dataset, get_dataset
from mlflow.genai.scorers import scorer

from football_rules.embeddings import BGEEmbedder
from football_rules.retrieval import DenseRetriever, read_chunks
from football_rules.retrieval_metrics import ranking_metrics, relevant_chunks
from football_rules.tracking import configure_tracking


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def evaluation_records(chunks_path):
    chunks = read_chunks(chunks_path)
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
            gold = relevant_chunks(chunks, locators, pages)
            records.append(
                {
                    "inputs": {
                        "query": row["questions"][language],
                        "language": language,
                    },
                    "expectations": {
                        "scenario_id": row["id"],
                        "relevant_chunk_ids": gold,
                    },
                }
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", required=True)
    parser.add_argument("--database", type=Path, default=Path("data/qdrant"))
    parser.add_argument(
        "--chunks", type=Path, default=Path("data/processed/chunks.jsonl")
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--verify-trace", action="store_true")
    args = parser.parse_args()

    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be positive")

    os.environ["MLFLOW_GENAI_EVAL_MAX_WORKERS"] = "1"
    experiment_id = configure_tracking()
    records = evaluation_records(args.chunks)

    if args.limit:
        records = records[: args.limit]

    fingerprint = hashlib.sha256(
        json.dumps(records, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    dataset_name = "football-dev-retrieval-" + fingerprint[:16]
    client = mlflow.MlflowClient()
    existing = client.search_datasets(experiment_ids=[experiment_id])
    matches = [item for item in existing if item.name == dataset_name]

    if matches:
        dataset = get_dataset(dataset_id=matches[0].dataset_id)
    else:
        dataset = create_dataset(
            name=dataset_name,
            experiment_id=[experiment_id],
            tags={"split": "dev", "qrels": "locator_coverage_0.8_v1"},
        )
        dataset.merge_records(records)

    retriever = DenseRetriever(args.database, args.collection, BGEEmbedder())

    if (
        retriever.manifest["chunks_sha256"]
        != hashlib.sha256(args.chunks.read_bytes()).hexdigest()
    ):
        retriever.close()
        raise ValueError("Evaluation chunks differ from the indexed corpus")

    scorers = [make_scorer(metric) for metric in ("recall", "precision", "mrr", "ndcg")]
    observations = {}
    trace_ids = []

    @mlflow.trace(name="dense_retrieval", span_type="CHAIN")
    def predict(query, language):
        started = perf_counter()
        documents = retriever.search(query, language, 10)
        output = {"documents": documents, "latency_seconds": perf_counter() - started}
        observations[query, language] = output

        active_span = mlflow.get_current_active_span()

        if active_span is not None:
            trace_ids.append(active_span.trace_id)

        return output

    try:
        with mlflow.start_run(
            run_name="dense-baseline-dry-run" if args.limit else "dense-baseline"
        ) as run:
            mlflow.log_dict(retriever.manifest, "index-manifest.json")
            mlflow.log_params(
                {
                    "strategy": "dense",
                    "language_filter": "same_language",
                    "split": "dev",
                    "questions": len(records),
                    "qrel_coverage": 0.8,
                    "dataset_sha256": fingerprint,
                }
            )
            mlflow.log_params(
                {
                    f"embedding_{key}": value
                    for key, value in retriever.manifest["embedding"].items()
                }
            )
            chunking = read_chunks(args.chunks)[0]["chunking"]
            mlflow.log_params(
                {f"chunking_{key}": value for key, value in chunking.items()}
            )

            for name in ("scenarios", "evidence"):
                path = Path(f"data/evaluation/{name}.jsonl")
                mlflow.log_param(
                    f"{name}_sha256", hashlib.sha256(path.read_bytes()).hexdigest()
                )

            mlflow.log_param("chunks_sha256", retriever.manifest["chunks_sha256"])
            mlflow.log_metric(
                "questions_without_relevant_chunks",
                sum(
                    not record["expectations"]["relevant_chunk_ids"]
                    for record in records
                ),
            )
            mlflow.log_artifact(str(args.chunks), artifact_path="corpus")
            mlflow.log_artifact("uv.lock")
            mlflow.log_artifact(__file__, artifact_path="code")

            for name in ("embeddings", "retrieval", "retrieval_metrics"):
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
                metrics = {
                    f"{metric}_at_{k}": value
                    for k in (1, 3, 5, 10)
                    for metric, value in ranking_metrics(
                        retrieved, record["expectations"]["relevant_chunk_ids"], k
                    ).items()
                }
                rows.append({**record, "outputs": output, "metrics": metrics})

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
                        "metrics": summary,
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
        retriever.close()


if __name__ == "__main__":
    main()
