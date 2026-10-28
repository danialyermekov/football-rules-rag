"""E21: replay frozen Qwen reranking with one-hop neighbor context ordering."""

import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter

import mlflow
from evaluate_retrieval import evaluation_records, make_evidence_scorer, read_jsonl
from mlflow.genai.datasets import create_dataset, get_dataset
from transformers import AutoTokenizer

from football_rules.embeddings import MODEL_REVISION
from football_rules.evidence_evaluation import (
    chunk_successors,
    evidence_metrics,
    pack_context,
    prioritize_rule_neighbors,
)
from football_rules.tracking import configure_tracking

SOURCE = "b8b229800f4246d090eea03a4d5c9900"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    experiment = configure_tracking()
    client = mlflow.MlflowClient()
    source_run = client.get_run(SOURCE)
    if source_run.info.status != "FINISHED":
        raise ValueError("E15 must be FINISHED")
    folder = Path("tmp/e21").resolve()
    folder.mkdir(parents=True, exist_ok=True)
    paths = {
        "chunks_sha256": Path("data/processed/chunks.jsonl"),
        "scenarios_sha256": Path("data/evaluation/scenarios.jsonl"),
        "evidence_sha256": Path("data/evaluation/evidence.jsonl"),
        "cleaned_pages_sha256": Path("data/processed/cleaned-pages.jsonl"),
    }
    for key, path in paths.items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != source_run.data.params[key]:
            raise ValueError(f"Changed source: {key}")
    path = client.download_artifacts(SOURCE, "per-question-results.json", str(folder))
    previous = json.loads(Path(path).read_text(encoding="utf-8"))["records"]
    source = {(r["inputs"]["query"], r["inputs"]["language"]): r for r in previous}
    records = evaluation_records(paths["chunks_sha256"])
    assert len(records) == len(source) == 142
    chunks = read_jsonl(paths["chunks_sha256"])
    by_id = {r["chunk_id"]: r for r in chunks}
    links = chunk_successors(chunks)
    metadata = Path(
        "data/models/bge-m3/.cache/huggingface/download/tokenizer.json.metadata"
    )
    if metadata.read_text().splitlines()[0] != MODEL_REVISION:
        raise ValueError("Budget tokenizer revision changed")
    tokenizer = AutoTokenizer.from_pretrained(
        "data/models/bge-m3", local_files_only=True
    )

    def tokens(text):
        return len(tokenizer.encode(text, add_special_tokens=False))

    for record in records:
        row = source[record["inputs"]["query"], record["inputs"]["language"]]
        assert record["expectations"] == row["expectations"]
        docs = row["outputs"]["documents"]
        assert len(docs) == len({d["chunk_id"] for d in docs}) == 50
        for doc in docs:
            assert all(doc[k] == v for k, v in by_id[doc["chunk_id"]].items())
        assert pack_context(docs, 2048, tokens) == row["outputs"]["context"]
    if args.smoke:
        records = records[:3]
    name = (
        "football-e21-"
        + hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()[:16]
    )
    found = next(
        (
            d
            for d in client.search_datasets(experiment_ids=[experiment])
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
    pages = {
        (p["document_id"], p["pdf_page"]): p
        for p in read_jsonl(paths["cleaned_pages_sha256"])
    }
    metrics = [
        "complete_evidence",
        "strict_complete_evidence",
        "evidence_recall",
        "evidence_coverage",
        "source_redundancy",
    ]
    observations = {}

    @mlflow.trace(name="E21_neighbor_packing", span_type="CHAIN")
    def predict(query, language):
        docs = source[query, language]["outputs"]["documents"]
        started = perf_counter()
        ordered = prioritize_rule_neighbors(docs, links)
        assert {d["chunk_id"] for d in ordered} == {d["chunk_id"] for d in docs}
        context = pack_context(ordered, 2048, tokens)
        output = {
            "documents": docs,
            "context_candidates": ordered,
            "context": context,
            "ordering_and_packing_seconds": perf_counter() - started,
        }
        observations[query, language] = output
        return output

    with mlflow.start_run(
        run_name="E21-rule-neighbors" + ("-smoke" if args.smoke else "")
    ) as run:
        mlflow.set_tags(
            {"stage": "retrieval", "run_kind": "smoke" if args.smoke else "full"}
        )
        mlflow.log_params(
            {
                "source_run_id": SOURCE,
                "split": "dev",
                "questions": len(records),
                "context_budget": 2048,
                "policy": "one_predecessor_anchor_one_successor",
                "latency_scope": "cached_ordering_and_packing_only",
                **{k: source_run.data.params[k] for k in paths},
            }
        )
        for filename in [
            __file__,
            "src/football_rules/evidence_evaluation.py",
            "docs/retrieval-e21-protocol.md",
            "uv.lock",
        ]:
            mlflow.log_artifact(filename, artifact_path="reproduction")
        mlflow.log_dict(links, "neighbor-links.json")
        if args.smoke:
            predict(**records[0]["inputs"])
            identity = mlflow.get_last_active_trace_id()
            mlflow.flush_trace_async_logging()
            trace = mlflow.get_trace(identity)
            assert trace and trace.data.spans
            print("Verified trace", identity, flush=True)
        result = mlflow.genai.evaluate(
            data=dataset,
            predict_fn=predict,
            scorers=[make_evidence_scorer(m, pages) for m in metrics],
        )
        rows = []
        for record in records:
            inputs = record["inputs"]
            output = observations[inputs["query"], inputs["language"]]
            values = evidence_metrics(
                output["context"]["documents"],
                record["expectations"]["required_evidence"],
                pages,
            )
            rows.append({**record, "outputs": output, "metrics": values})
        assert len(rows) == len(records)
        summary = {
            f"{lang}_{m}": sum(
                r["metrics"][m] for r in rows if r["inputs"]["language"] == lang
            )
            / sum(r["inputs"]["language"] == lang for r in rows)
            for lang in {r["inputs"]["language"] for r in rows}
            for m in metrics
        }
        mlflow.log_metrics(summary)
        mlflow.log_dict({"records": rows}, "per-question-results.json")
        mlflow.log_dict(
            {"by_language": summary, "native_metrics": result.metrics}, "summary.json"
        )
        print("FINISHED", run.info.run_id, json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
