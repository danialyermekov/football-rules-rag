"""Offline E22 bounded gold-aware feasibility experiment, not a retriever."""

import argparse
import hashlib
import itertools
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
    render_context,
    retained_positions,
)
from football_rules.tracking import configure_tracking

E21 = "174a45eee3c243e2a7bf21be9ddd7bae"
E15 = "b8b229800f4246d090eea03a4d5c9900"
BUDGET = 2048


def search_oracle(docs, baseline, required, pages, tokens, *, seconds=2, limit=20000):
    """Return a verified witness, a pool impossibility proof, or UNKNOWN."""

    def complete(selected):
        return evidence_metrics(selected, required, pages)["complete_evidence"] == 1

    if not complete(docs):
        return {"status": "IMPOSSIBLE_POOL", "reason": "pool_incomplete", "checked": 0}
    if complete(baseline):
        text = render_context(baseline)
        n = tokens(text)
        if n > BUDGET:
            raise ValueError("Baseline exceeds budget")
        return {
            "status": "FOUND",
            "reason": "baseline",
            "checked": 0,
            "documents": baseline,
            "text": text,
            "token_count": n,
        }

    gold = []
    for unit in required:
        for loc in unit["locators"]:
            key = (loc["document_id"], loc["pdf_page"])
            gold.append(
                (
                    key,
                    retained_positions(pages[key], loc["char_start"], loc["char_end"]),
                )
            )
    candidates = []
    for doc in docs:
        key = (doc["document_id"], doc["pdf_page"])
        positions = set()
        for span in doc["source_spans"]:
            positions.update(retained_positions(pages[key], span["start"], span["end"]))
        masks = []
        for gkey, g in gold:
            masks.append(positions & g if key == gkey else set())
        if any(masks):
            candidates.append((doc, masks))
    start = perf_counter()
    checked = 0
    for size in range(1, min(4, len(candidates)) + 1):
        for combination in itertools.combinations(candidates, size):
            if perf_counter() - start >= seconds:
                return {"status": "UNKNOWN", "reason": "timeout", "checked": checked}
            if checked >= limit:
                return {
                    "status": "UNKNOWN",
                    "reason": "combination_limit",
                    "checked": checked,
                }
            checked += 1
            if not all(
                len(set().union(*(c[1][i] for c in combination))) / len(g) >= 0.8
                for i, (_, g) in enumerate(gold)
            ):
                continue
            selected = [c[0] for c in combination]
            text = render_context(selected)
            n = tokens(text)
            if n <= BUDGET:
                assert complete(selected)
                return {
                    "status": "FOUND",
                    "reason": "search",
                    "checked": checked,
                    "documents": selected,
                    "text": text,
                    "token_count": n,
                }
    return {
        "status": "UNKNOWN",
        "reason": "bounded_search_exhausted",
        "checked": checked,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    experiment = configure_tracking()
    client = mlflow.MlflowClient()
    runs = [client.get_run(x) for x in (E21, E15)]
    assert all(r.info.status == "FINISHED" for r in runs)
    paths = {
        "chunks_sha256": Path("data/processed/chunks.jsonl"),
        "scenarios_sha256": Path("data/evaluation/scenarios.jsonl"),
        "evidence_sha256": Path("data/evaluation/evidence.jsonl"),
        "cleaned_pages_sha256": Path("data/processed/cleaned-pages.jsonl"),
    }

    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    hashes = {str(p): sha(p) for p in paths.values()}
    for key, path in paths.items():
        assert all(r.data.params[key] == hashes[str(path)] for r in runs), key
    folder = Path("tmp/e22")
    folder.mkdir(parents=True, exist_ok=True)

    sources = []
    for run_id in (E21, E15):
        dest = folder / run_id
        dest.mkdir(exist_ok=True)
        path = Path(
            client.download_artifacts(
                run_id, "per-question-results.json", str(dest.resolve())
            )
        )
        hashes[f"{run_id}/per-question-results.json"] = sha(path)
        sources.append(json.loads(path.read_text(encoding="utf-8"))["records"])
    records = evaluation_records(paths["chunks_sha256"])
    assert len(records) == len(sources[0]) == len(sources[1]) == 142
    lookup = [
        {(r["inputs"]["query"], r["inputs"]["language"]): r for r in rows}
        for rows in sources
    ]
    assert all(len(x) == 142 for x in lookup)
    chunks = read_jsonl(paths["chunks_sha256"])
    by_id = {x["chunk_id"]: x for x in chunks}
    links = chunk_successors(chunks)
    pages = {
        (p["document_id"], p["pdf_page"]): p
        for p in read_jsonl(paths["cleaned_pages_sha256"])
    }
    model = Path("data/models/bge-m3")
    metadata = model / ".cache/huggingface/download/tokenizer.json.metadata"
    assert metadata.read_text().splitlines()[0] == MODEL_REVISION
    for p in [
        metadata,
        model / "tokenizer.json",
        model / "tokenizer_config.json",
        model / "special_tokens_map.json",
    ]:
        if p.exists():
            hashes[str(p)] = sha(p)
    tokenizer = AutoTokenizer.from_pretrained(str(model), local_files_only=True)

    def tokens(text):
        return len(tokenizer.encode(text, add_special_tokens=False))

    for record in records:
        key = record["inputs"]["query"], record["inputs"]["language"]
        a, b = (x[key] for x in lookup)
        assert record["expectations"] == a["expectations"] == b["expectations"]
        da, db = a["outputs"]["documents"], b["outputs"]["documents"]
        assert len(da) == len(db) == 50
        assert {x["chunk_id"] for x in da} == {x["chunk_id"] for x in db}
        assert {x["chunk_id"]: x for x in da} == {x["chunk_id"]: x for x in db}
        assert all(all(d[k] == v for k, v in by_id[d["chunk_id"]].items()) for d in db)
        ordered = prioritize_rule_neighbors(db, links)
        assert ordered == a["outputs"]["context_candidates"]
        context = pack_context(ordered, BUDGET, tokens)
        assert context == a["outputs"]["context"]
        assert (
            evidence_metrics(
                context["documents"], record["expectations"]["required_evidence"], pages
            )
            == a["metrics"]
        )
    print("Verified 142 E21 replays and input hashes", flush=True)
    if args.smoke:
        records = records[:3]
    name = (
        "football-e22-"
        + hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()[:16]
    )
    existing = next(
        (
            d
            for d in client.search_datasets(experiment_ids=[experiment])
            if d.name == name
        ),
        None,
    )
    dataset = (
        get_dataset(dataset_id=existing.dataset_id)
        if existing
        else create_dataset(
            name=name, experiment_id=[experiment], tags={"split": "dev"}
        )
    )
    if not existing:
        dataset.merge_records(records)
    observations = {}

    @mlflow.trace(name="E22_budget_oracle", span_type="CHAIN")
    def predict(query, language):
        key = query, language
        a, b = (x[key] for x in lookup)
        result = search_oracle(
            b["outputs"]["documents"],
            a["outputs"]["context"]["documents"],
            a["expectations"]["required_evidence"],
            pages,
            tokens,
        )
        context = {
            "documents": result.get("documents", []),
            "text": result.get("text", ""),
            "token_count": result.get("token_count", 0),
        }
        output = {
            "context": context,
            "oracle": {
                k: v for k, v in result.items() if k not in ("documents", "text")
            },
        }
        observations[key] = output
        return output

    with mlflow.start_run(
        run_name="E22-budget-oracle" + ("-smoke" if args.smoke else "")
    ) as run:
        mlflow.set_tags(
            {"stage": "retrieval", "run_kind": "smoke" if args.smoke else "full"}
        )
        mlflow.log_params(
            {
                "e21_run": E21,
                "e15_run": E15,
                "questions": len(records),
                "split": "dev",
                "budget": BUDGET,
                "seconds_per_question": 2,
                "combination_limit": 20000,
                "max_chunks": 4,
                "tokenizer_revision": MODEL_REVISION,
            }
        )
        for p in [
            __file__,
            "src/football_rules/evidence_evaluation.py",
            "scripts/evaluate_retrieval.py",
            "docs/retrieval-e22-protocol.md",
            "uv.lock",
        ]:
            mlflow.log_artifact(p, artifact_path="reproduction")
        mlflow.log_dict(hashes, "input-hashes.json")
        if args.smoke:
            predict(**records[0]["inputs"])
            trace_id = mlflow.get_last_active_trace_id()
            mlflow.flush_trace_async_logging()
            assert mlflow.get_trace(trace_id).data.spans
            print("Verified trace", trace_id, flush=True)
        result = mlflow.genai.evaluate(
            data=dataset,
            predict_fn=predict,
            scorers=[make_evidence_scorer("complete_evidence", pages)],
        )
        rows = []
        for record in records:
            inputs = record["inputs"]
            key = inputs["query"], inputs["language"]
            output = observations[key]
            metric = evidence_metrics(
                output["context"]["documents"],
                record["expectations"]["required_evidence"],
                pages,
            )
            if output["oracle"]["status"] == "FOUND":
                assert (
                    metric["complete_evidence"] == 1
                    and tokens(output["context"]["text"]) <= BUDGET
                )
            rows.append(
                {
                    **record,
                    "outputs": output,
                    "metrics": metric,
                    "baseline_metrics": lookup[0][key]["metrics"],
                }
            )
        summary = {}
        for lang in ("ru", "en"):
            subset = [r for r in rows if r["inputs"]["language"] == lang]
            summary[lang] = {
                "n": len(subset),
                "baseline": sum(
                    int(r["baseline_metrics"]["complete_evidence"]) for r in subset
                ),
                **{
                    status: sum(
                        r["outputs"]["oracle"]["status"] == status for r in subset
                    )
                    for status in ("FOUND", "IMPOSSIBLE_POOL", "UNKNOWN")
                },
            }
        mlflow.log_dict({"records": rows}, "per-question-results.json")
        mlflow.log_dict(
            {"by_language": summary, "native_metrics": result.metrics}, "summary.json"
        )
        (folder / ("smoke.json" if args.smoke else "full.json")).write_text(
            json.dumps(
                {"run_id": run.info.run_id, "summary": summary},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print("FINISHED", run.info.run_id, json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
