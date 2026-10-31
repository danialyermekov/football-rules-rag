"""E24: one frozen gold-blind overlap-compaction experiment (offline dev only).

Run only after main approves core tests; smoke/full need external 180s/300s
process deadlines. This script does not run models or change application defaults.
"""

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path
from time import perf_counter, time

os.environ.setdefault("MLFLOW_DISABLE_TELEMETRY", "true")
os.environ.setdefault("MLFLOW_GENAI_EVAL_MAX_WORKERS", "1")
os.environ.setdefault("MLFLOW_GENAI_EVAL_MAX_SCORER_WORKERS", "1")

import mlflow
import mlflow.genai
from evaluate_anchor_first import (
    BUDGET,
    E15,
    E21,
    FROZEN_HASHES,
    METRICS,
    SOURCE_PATHS,
    canonical,
    key,
    require,
    sha,
)
from evaluate_retrieval import evaluation_records, make_evidence_scorer, read_jsonl
from football_rules.context_compaction import pack_overlap_context
from mlflow.genai.datasets import create_dataset, get_dataset
from transformers import AutoTokenizer

from football_rules.chunking import source_positions, source_ranges
from football_rules.embeddings import MODEL_REVISION
from football_rules.evidence_evaluation import (
    chunk_successors,
    evidence_metrics,
    pack_context,
    prioritize_rule_neighbors,
    render_context,
)
from football_rules.tracking import configure_tracking

POLICY = "e21_order_strict_page_overlap_union_greedy_no_eviction_v1"
TRACE_NAME = "E24_overlap_packing"
# The imported E23 runner supplies frozen constants/helpers, NOT its policy.
REPRODUCTION = (
    "scripts/evaluate_overlap_packing.py",
    "scripts/evaluate_anchor_first.py",
    "src/football_rules/context_compaction.py",
    "src/football_rules/chunking.py",
    "src/football_rules/cleaning.py",
    "src/football_rules/evidence_evaluation.py",
    "scripts/evaluate_retrieval.py",
    "src/football_rules/embeddings.py",
    "src/football_rules/tracking.py",
    "docs/retrieval-e24-protocol.md",
    "pyproject.toml",
    "uv.lock",
)
PAGE_METADATA = (
    "document_id",
    "pdf_page",
    "printed_page",
    "edition",
    "language",
    "publisher",
    "source_url",
    "source_sha256",
    "cleaning_version",
    "cleaning_flags",
)
# A smoke authorizes only the same code/inputs in the next 24 hours.
SMOKE_MAX_AGE_SECONDS = 24 * 60 * 60


def trace_readback(trace_id):
    """One flush/readback child, killed after at most 60 seconds; no fallback."""
    require(trace_id is not None, "No smoke trace ID; stop before evaluation")
    print("Starting trace readback", trace_id, flush=True)
    code = (
        "import json,sys,mlflow; "
        "mlflow.set_tracking_uri(sys.argv[1]); "
        "mlflow.flush_trace_async_logging(); "
        "t=mlflow.get_trace(sys.argv[2]); "
        "assert t and t.data.spans, 'Missing smoke spans'; "
        "assert any(s.name == sys.argv[3] and s.inputs and s.outputs "
        "for s in t.data.spans), 'Missing E24 span I/O'; "
        "print(json.dumps({'trace_id':sys.argv[2], 'spans':len(t.data.spans)}))"
    )
    started = perf_counter()
    result = subprocess.run(
        [sys.executable, "-c", code, mlflow.get_tracking_uri(), trace_id, TRACE_NAME],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    receipt = json.loads(result.stdout.strip().splitlines()[-1])
    receipt["readback_seconds"] = perf_counter() - started
    require(receipt["readback_seconds"] <= 60, "Trace readback exceeded 60 seconds")
    print("Verified trace", json.dumps(receipt), flush=True)
    return receipt


def validate_source(document, pages, maps):
    """Validate either a raw chunk or a synthetic block, never assume pool identity."""
    page_key = document["document_id"], document["pdf_page"]
    page = pages[page_key]
    start, end = document["cleaned_start"], document["cleaned_end"]
    require(
        type(start) is int
        and type(end) is int
        and 0 <= start < end <= len(page["cleaned_text"]),
        "Invalid cleaned interval",
    )
    require(document["text"] == page["cleaned_text"][start:end], "Source text mismatch")
    require(
        all(document[field] == page[field] for field in PAGE_METADATA),
        "Page/source metadata mismatch",
    )
    require(
        document["source_spans"]
        == source_ranges(maps[page_key][start:end], page["text"]),
        "Source spans differ from original cleaned-to-source map",
    )


def coordinate_union(documents):
    """Exact per-page interval union (touching is OK for set equality, not merging)."""
    by_page = {}
    for document in documents:
        intervals = [(document["cleaned_start"], document["cleaned_end"])]
        by_page.setdefault((document["document_id"], document["pdf_page"]), []).extend(
            intervals
        )
    result = {}
    for page_key, intervals in by_page.items():
        union = []
        for start, end in sorted(intervals):
            if union and start <= union[-1][1]:
                union[-1] = union[-1][0], max(end, union[-1][1])
            else:
                union.append((start, end))
        result[page_key] = union
    return result


def overlap_components(selected):
    """Independent validation of strict, transitive same-page components."""
    by_page = {}
    for rank, document in enumerate(selected):
        by_page.setdefault((document["document_id"], document["pdf_page"]), []).append(
            (document["cleaned_start"], document["cleaned_end"], rank, document)
        )
    groups = []
    for intervals in by_page.values():
        current = []
        right = -1
        for start, end, rank, document in sorted(intervals, key=lambda row: row[:3]):
            if current and start >= right:
                groups.append(current)
                current = []
            current.append((rank, document))
            right = max(right, end) if len(current) > 1 else end
        if current:
            groups.append(current)
    return sorted(groups, key=lambda group: min(rank for rank, _ in group))


def validate_context(context, ordered, pages, maps, tokens, original_ids):
    selected = context["selected_documents"]
    blocks = context["documents"]
    pool = {document["chunk_id"]: document for document in ordered}
    selected_ids = [document["chunk_id"] for document in selected]
    require(len(selected_ids) == len(set(selected_ids)), "Duplicate selected originals")
    require(
        all(document == pool.get(document["chunk_id"]) for document in selected),
        "Selected original outside frozen top50 or changed",
    )
    selected_set = set(selected_ids)
    require(
        selected
        == [document for document in ordered if document["chunk_id"] in selected_set],
        "Raw admission order differs from E21 candidate order",
    )
    skipped = context["skipped"]
    require(
        skipped
        == [
            {"chunk_id": document["chunk_id"], "reason": "token_budget"}
            for document in ordered
            if document["chunk_id"] not in selected_set
        ],
        "Skipped candidates must be the ordered, once-only complement",
    )
    groups = overlap_components(selected)
    require(len(groups) == len(blocks), "Wrong number of strict overlap components")
    require(
        len({block["chunk_id"] for block in blocks}) == len(blocks),
        "Duplicate packed block IDs",
    )
    membership = []
    for block, group in zip(blocks, groups, strict=True):
        constituents = [
            document for _, document in sorted(group, key=lambda row: row[0])
        ]
        ids = [document["chunk_id"] for document in constituents]
        validate_source(block, pages, maps)
        require(
            all(block[field] == constituents[0][field] for field in PAGE_METADATA),
            "Block source identity differs from its constituents",
        )
        if len(constituents) == 1:
            require(
                block == constituents[0], "Singleton must remain the original record"
            )
            membership.extend(ids)
        else:
            block_ids = block["constituent_chunk_ids"]
            require(
                len(block_ids) == len(ids) and set(block_ids) == set(ids),
                "Merged membership differs from strict overlap component",
            )
            require(
                isinstance(block["chunk_id"], str)
                and bool(block["chunk_id"])
                and block["chunk_id"] not in original_ids,
                "Synthetic merged ID masquerades as an original",
            )
            require(
                block["cleaned_start"] == min(d["cleaned_start"] for d in constituents)
                and block["cleaned_end"] == max(d["cleaned_end"] for d in constituents),
                "Merged interval is not the exact component union",
            )
            membership.extend(block_ids)
    require(
        Counter(membership) == Counter(selected_ids),
        "Incomplete/duplicate constituents",
    )
    require(
        coordinate_union(selected) == coordinate_union(blocks),
        "Compaction added or removed cleaned coordinates (including whitespace)",
    )

    # Source spans may compact whitespace, so compare mapped source characters as
    # well as exact per-block map-derived spans, rather than raw span boundaries.
    def source_characters(documents):
        result = {}
        for document in documents:
            page_key = document["document_id"], document["pdf_page"]
            positions = maps[page_key][
                document["cleaned_start"] : document["cleaned_end"]
            ]
            result.setdefault(page_key, set()).update(
                p for p in positions if p is not None
            )
        return result

    require(
        source_characters(selected) == source_characters(blocks), "Source union changed"
    )
    require(context["text"] == render_context(blocks), "Merged rendering mismatch")
    require(
        type(context["token_count"]) is int
        and tokens(context["text"]) == context["token_count"] <= BUDGET,
        "Exact whole-render token budget failed",
    )


def make_predict(candidates, pages, maps, tokens, original_ids):
    """The closure receives only frozen retrieval inputs and source maps, no gold."""
    observations = {}

    @mlflow.trace(name=TRACE_NAME, span_type="CHAIN")
    def predict(query, language):
        ordered = candidates[query, language]
        before = json.dumps(ordered, sort_keys=True)
        packing_started = perf_counter()
        context = pack_overlap_context(ordered, pages, BUDGET, tokens)
        packing_seconds = perf_counter() - packing_started
        require(
            json.dumps(ordered, sort_keys=True) == before,
            "Core mutated candidate records",
        )
        validate_context(context, ordered, pages, maps, tokens, original_ids)
        output = {
            "documents": ordered,
            "context": context,
            "packing_seconds": packing_seconds,
        }
        observations[query, language] = output
        return output

    return predict, observations


def validate_native(result, rows):
    frame = result.result_df
    if frame is None:
        raise ValueError("Missing native result frame")
    require(len(frame) == len(rows), "Missing native rows")
    expected = {key(row): row for row in rows}
    observed = set()
    for native in frame.to_dict("records"):
        # MLflow 3.17.2 constructs result_df from traces: request/response are
        # deserialized root I/O, not invented flattened inputs.query columns.
        request = native["request"]
        require(isinstance(request, dict), "Native trace request is not an input dict")
        identity = request["query"], request["language"]
        require(
            identity in expected and identity not in observed, "Native input mismatch"
        )
        observed.add(identity)
        response = native["response"]
        require(
            isinstance(response, dict)
            and response["context"] == expected[identity]["outputs"]["context"],
            "Native trace did not retain the actual merged context",
        )
        for metric in METRICS:
            value = float(native[f"{metric}/value"])
            require(math.isfinite(value), f"Nonfinite native assessment: {metric}")
            require(
                math.isclose(
                    value, expected[identity]["metrics"][metric], abs_tol=1e-12
                ),
                f"Native per-question mismatch: {metric}",
            )
    for metric in METRICS:
        for suffix in ("error_code", "error_message"):
            column = f"{metric}/{suffix}"
            if column in frame:
                require(frame[column].dropna().eq("").all(), f"Native error: {column}")
        mean = float(result.metrics[f"{metric}/mean"])
        target = sum(row["metrics"][metric] for row in rows) / len(rows)
        require(
            math.isfinite(mean) and math.isclose(mean, target, abs_tol=1e-12),
            f"Native mean mismatch: {metric}",
        )


def validate_smoke(smoke, hashes, code_hashes, client, experiment):
    require(
        smoke["status"] == "FINISHED"
        and smoke["run_kind"] == "smoke"
        and smoke["questions"] == 3
        and smoke["policy"] == POLICY
        and smoke["input_hashes"] == hashes
        and smoke["code_hashes"] == code_hashes
        and smoke["trace"]["spans"] > 0
        and smoke["trace"]["readback_seconds"] <= 60
        and 0 <= time() - smoke["completed_at_epoch"] <= SMOKE_MAX_AGE_SECONDS,
        "Fresh successful smoke3 with identical input/code hashes required",
    )
    run = client.get_run(smoke["run_id"])
    require(
        run.info.status == "FINISHED"
        and str(run.info.experiment_id) == str(experiment)
        and run.data.params["policy"] == POLICY
        and run.data.params["questions"] == "3"
        and run.data.tags["run_kind"] == "smoke",
        "Smoke run metadata mismatch",
    )


def main():
    started = perf_counter()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    kind = "smoke" if args.smoke else "full"
    require(
        os.environ["MLFLOW_DISABLE_TELEMETRY"].lower() == "true"
        and os.environ["MLFLOW_GENAI_EVAL_MAX_WORKERS"] == "1"
        and os.environ["MLFLOW_GENAI_EVAL_MAX_SCORER_WORKERS"] == "1",
        "E24 requires telemetry disabled and eval/scorer workers 1/1",
    )
    experiment = configure_tracking()
    client = mlflow.MlflowClient()
    runs = [client.get_run(run_id) for run_id in (E21, E15)]
    require(all(run.info.status == "FINISHED" for run in runs), "Sources not FINISHED")
    folder = Path("tmp/e24")
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
    require(len(hashes) == 10 and hashes == FROZEN_HASHES, "Frozen10 hash mismatch")
    for name, path in SOURCE_PATHS.items():
        require(all(run.data.params[name] == hashes[path] for run in runs), name)
    code_hashes = {path: sha(path) for path in REPRODUCTION}
    # Full authorization happens before replay/dataset creation, not after scoring.
    if not args.smoke:
        smoke = json.loads((folder / "smoke.json").read_text(encoding="utf-8"))
        validate_smoke(smoke, hashes, code_hashes, client, experiment)
    records = evaluation_records(Path(SOURCE_PATHS["chunks_sha256"]))
    require(len(records) == len(sources[0]) == len(sources[1]) == 142, "Not dev142")
    lookup = [{key(row): row for row in rows} for rows in sources]
    require(len({key(row) for row in records}) == 142, "Duplicate dev inputs")
    require(
        all(
            len(source) == 142 and set(source) == {key(row) for row in records}
            for source in lookup
        ),
        "Source keys differ",
    )
    for language in ("ru", "en"):
        require(
            sum(row["inputs"]["language"] == language for row in records) == 71,
            "Not 71+71",
        )
    chunks = read_jsonl(Path(SOURCE_PATHS["chunks_sha256"]))
    by_id = {document["chunk_id"]: document for document in chunks}
    require(len(by_id) == len(chunks), "Duplicate source IDs")
    links = chunk_successors(chunks)
    page_rows = read_jsonl(Path(SOURCE_PATHS["cleaned_pages_sha256"]))
    pages = {(page["document_id"], page["pdf_page"]): page for page in page_rows}
    require(len(pages) == len(page_rows), "Duplicate source pages")
    maps = {}
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
    candidates = {}
    for record in records:
        baseline, ranked = (source[key(record)] for source in lookup)
        require(
            record["inputs"] == baseline["inputs"] == ranked["inputs"], "Input mismatch"
        )
        require(
            record["expectations"]
            == baseline["expectations"]
            == ranked["expectations"],
            "Gold changed",
        )
        da, db = baseline["outputs"]["documents"], ranked["outputs"]["documents"]
        require(
            len(da) == len(db) == len({d["chunk_id"] for d in db}) == 50,
            "Not unique top50",
        )
        require(
            {d["chunk_id"]: d for d in da} == {d["chunk_id"]: d for d in db},
            "Pool/scores changed",
        )
        for document in db:
            require(
                all(
                    document[field] == value
                    for field, value in by_id[document["chunk_id"]].items()
                ),
                "Source chunk metadata changed",
            )
            page_key = document["document_id"], document["pdf_page"]
            if page_key not in maps:
                maps[page_key] = source_positions(pages[page_key])
            validate_source(document, pages, maps)
        ordered = prioritize_rule_neighbors(db, links)
        context = pack_context(ordered, BUDGET, tokens)
        require(
            ordered == baseline["outputs"]["context_candidates"],
            "E21 ordering replay failed",
        )
        require(context == baseline["outputs"]["context"], "E21 context replay failed")
        require(
            evidence_metrics(
                context["documents"], record["expectations"]["required_evidence"], pages
            )
            == baseline["metrics"],
            "E21 metric replay failed",
        )
        require(
            pack_context(db, BUDGET, tokens) == ranked["outputs"]["context"],
            "E15 context replay failed",
        )
        # Copy retrieval-only records; predict never captures source artifacts/gold.
        candidates[key(record)] = json.loads(json.dumps(ordered))
    replay_seconds = perf_counter() - replay_started
    print("Verified 142 E21/E15 replays, source maps and 10 frozen hashes", flush=True)
    if args.smoke:
        records = records[:3]
    digest = hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()[
        :16
    ]
    name = "football-e24-" + digest
    matches = [
        d for d in client.search_datasets(experiment_ids=[experiment]) if d.name == name
    ]
    require(len(matches) <= 1, "Ambiguous native dataset name")
    if matches:
        dataset = get_dataset(dataset_id=matches[0].dataset_id)
    else:
        dataset = create_dataset(
            name=name, experiment_id=[experiment], tags={"split": "dev"}
        )
        dataset.merge_records(records)
    dataset_records = [
        {"inputs": row["inputs"], "expectations": row["expectations"]}
        for row in dataset.to_df().to_dict("records")
    ]
    require(canonical(dataset_records) == canonical(records), "Native dataset changed")
    predict, observations = make_predict(candidates, pages, maps, tokens, set(by_id))
    trace_receipt = None
    receipt = None
    with mlflow.start_run(run_name="E24-overlap-packing-" + kind) as run:
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
                "policy": POLICY,
                "tokenizer_revision": MODEL_REVISION,
                "tokenizer": "data/models/bge-m3",
                "latency_scope": "cached_packing_only",
                "mlflow_disable_telemetry": os.environ["MLFLOW_DISABLE_TELEMETRY"],
                "eval_max_workers": os.environ["MLFLOW_GENAI_EVAL_MAX_WORKERS"],
                "eval_max_scorer_workers": os.environ[
                    "MLFLOW_GENAI_EVAL_MAX_SCORER_WORKERS"
                ],
                **{name: hashes[path] for name, path in SOURCE_PATHS.items()},
            }
        )
        for path in REPRODUCTION:
            mlflow.log_artifact(path, artifact_path="reproduction")
        mlflow.log_dict(hashes, "input-hashes.json")
        mlflow.log_dict(code_hashes, "code-hashes.json")
        mlflow.log_dict(links, "neighbor-links.json")
        if args.smoke:
            os.environ["MLFLOW_ENABLE_ASYNC_TRACE_LOGGING"] = "false"
            mlflow.log_param("smoke_async_trace_logging", "false")
            predict(**records[0]["inputs"])
            trace_id = mlflow.get_last_active_trace_id()
            print("TRACE", trace_id, flush=True)
            mlflow.log_dict({"trace_id": trace_id}, "smoke-trace-id.json")
            trace_receipt = trace_readback(trace_id)
            mlflow.log_dict(trace_receipt, "trace-readback.json")
        # Persistent registration is security-blocked locally; no unsafe opt-in.
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
            validate_context(
                context, candidates[key(record)], pages, maps, tokens, set(by_id)
            )
            required = record["expectations"]["required_evidence"]
            values = evidence_metrics(context["documents"], required, pages)
            raw_values = evidence_metrics(
                context["selected_documents"], required, pages
            )
            require(
                all(
                    values[metric] == raw_values[metric]
                    for metric in METRICS
                    if metric != "source_redundancy"
                ),
                "Compaction changed selected-original evidence coverage",
            )
            rows.append(
                {
                    **record,
                    "outputs": output,
                    "metrics": values,
                    "selected_raw_metrics": raw_values,
                    "baseline_metrics": lookup[0][key(record)]["metrics"],
                }
            )
        validate_native(result, rows)
        by_language = {}
        for language in ("ru", "en"):
            subset = [row for row in rows if row["inputs"]["language"] == language]
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
                "selected_raw_metrics": {
                    m: sum(r["selected_raw_metrics"][m] for r in subset) / len(subset)
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
        mean_cer = sum(row["metrics"]["complete_evidence"] for row in rows) / len(rows)
        baseline_cer = sum(
            row["baseline_metrics"]["complete_evidence"] for row in rows
        ) / len(rows)
        gate = (
            None
            if args.smoke
            else (
                mean_cer > baseline_cer
                and all(
                    value["complete_count"] >= value["baseline_complete_count"] - 1
                    for value in by_language.values()
                )
            )
        )
        require(
            {name: sha(path) for name, path in local_paths.items()} == hashes,
            "Inputs changed during run",
        )
        require(
            {path: sha(path) for path in REPRODUCTION} == code_hashes,
            "Code changed during run",
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
                "packing_seconds": sum(
                    row["outputs"]["packing_seconds"] for row in rows
                ),
                "elapsed_before_artifact_export_seconds": perf_counter() - started,
            },
        }
        mlflow.log_dict({"records": rows}, "per-question-results.json")
        mlflow.log_dict(summary, "summary.json")
        mlflow.log_metrics(
            {
                f"{lang}_{m}": value["metrics"][m]
                for lang, value in by_language.items()
                for m in METRICS
            }
        )
        receipt = {
            "run_id": run_id,
            "run_kind": kind,
            "status": "FINISHED",
            "questions": len(rows),
            "policy": POLICY,
            "input_hashes": hashes,
            "code_hashes": code_hashes,
            "trace": trace_receipt,
            "summary": summary,
        }
        mlflow.log_dict(receipt, "run-receipt.json")
    require(client.get_run(run_id).info.status == "FINISHED", "Run did not finish")
    if receipt is None:
        raise ValueError("No successful run receipt")
    receipt["completed_at_epoch"] = time()
    receipt["end_to_end_seconds"] = perf_counter() - started
    text = json.dumps(receipt, ensure_ascii=False, indent=2, allow_nan=False)
    (folder / (run_id + ".json")).write_text(text, encoding="utf-8")
    (folder / (kind + ".json")).write_text(text, encoding="utf-8")
    print("FINISHED", text, flush=True)


if __name__ == "__main__":
    main()
