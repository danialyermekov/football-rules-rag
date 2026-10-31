"""Q3: native deterministic replay of frozen dev contexts, never new retrieval.

Run from the repository root with --smoke, then --full (caller-enforced hard
process deadlines: 120s / 300s). Supply all original review files using repeated
--review-file arguments; approved in the manifest is the adjudicated decision,
not a decision inferred by this runner from an unspecified review schema.
"""

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
from collections import Counter
from copy import deepcopy
from itertools import combinations
from pathlib import Path
from time import perf_counter

# Set before importing MLflow, including in the bounded readback child.
SAFE_ENV = {
    "MLFLOW_DISABLE_TELEMETRY": "true",
    "MLFLOW_GENAI_EVAL_MAX_WORKERS": "1",
    "MLFLOW_GENAI_EVAL_MAX_SCORER_WORKERS": "1",
    "MLFLOW_ENABLE_ASYNC_TRACE_LOGGING": "false",
}
os.environ.update(SAFE_ENV)

import mlflow
from mlflow.genai.datasets import create_dataset, get_dataset
from mlflow.genai.scorers import scorer

from football_rules.evidence_alternatives import alternative_evidence_metrics
from football_rules.evidence_evaluation import evidence_metrics
from football_rules.tracking import configure_tracking

SOURCES = {
    "E21": "174a45eee3c243e2a7bf21be9ddd7bae",
    "E23": "005cc004be224106af364013e5dd3c64",
    "E24": "ca86f33245c343869dcd0eacfe879895",
    "E25": "a5cd577ec6184069ae7060f95bbebe08",
}
METRICS = (
    "canonical_complete_evidence",
    "alternative_complete_evidence",
    "canonical_strict_complete_evidence",
    "alternative_strict_complete_evidence",
)
SMOKE_IDS = ("E21-FR005-ru", "E21-FR050-en", "E21-FR001-ru")
SCOPE = {("FR005", "ru"), ("FR050", "en")}
MANIFEST = "data/evaluation/evidence-alternatives-q3.json"
SOURCE_PATHS = {
    "chunks_sha256": "data/processed/chunks.jsonl",
    "scenarios_sha256": "data/evaluation/scenarios.jsonl",
    "evidence_sha256": "data/evaluation/evidence.jsonl",
    "cleaned_pages_sha256": "data/processed/cleaned-pages.jsonl",
}
REPRODUCTION = (
    "scripts/evaluate_q3_alternatives.py",
    "src/football_rules/__init__.py",
    "src/football_rules/evidence_alternatives.py",
    "src/football_rules/evidence_evaluation.py",
    "src/football_rules/tracking.py",
    "docs/evaluation-q3-protocol.md",
    "data/evaluation/manifest.json",
    "pyproject.toml",
    "uv.lock",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(encoded(value).encode("utf-8")).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_jsonl(path):
    return [
        json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()
    ]


def git(*args):
    return subprocess.run(
        ["git", "--no-pager", *args], check=True, capture_output=True, timeout=15
    ).stdout


def check_versioned(paths, committed):
    """Smoke permits staged work; full requires these exact files in HEAD."""
    for path in paths:
        git("ls-files", "--error-unmatch", "--", path)
    if committed:
        git("diff", "--exit-code", "HEAD", "--", *paths)
    return git("rev-parse", "HEAD").decode().strip()


def trace_readback(trace_id, output, folder):
    """Synchronous parent writes; child readback/retries die within one 60s budget."""
    require(trace_id, "Smoke did not capture a trace ID")
    expected = folder / "trace-expected.json"
    expected.write_text(encoded(output), encoding="utf-8")
    print("Starting trace readback", trace_id, flush=True)
    code = (
        "import json,sys,mlflow; "
        "mlflow.set_tracking_uri(sys.argv[1]); "
        "mlflow.flush_trace_async_logging(); "
        "t=mlflow.get_trace(sys.argv[2]); "
        "assert t and t.data.spans, 'Missing smoke spans'; "
        "s=next(s for s in t.data.spans if s.name=='Q3_snapshot_replay'); "
        "assert s.inputs=={'snapshot_id':'E21-FR005-ru'}; "
        "assert s.outputs==json.load(open(sys.argv[3],encoding='utf-8')); "
        "print(json.dumps({'trace_id':sys.argv[2],'spans':len(t.data.spans)}))"
    )
    started = perf_counter()
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
            mlflow.get_tracking_uri(),
            trace_id,
            str(expected),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=True,
    )
    receipt = json.loads(result.stdout.strip().splitlines()[-1])
    receipt["readback_seconds"] = perf_counter() - started
    require(receipt["readback_seconds"] <= 60, "Trace readback exceeded 60s")
    return receipt


def make_scorer(metric, pages):
    @scorer(name=metric)
    def score(outputs, expectations):
        return alternative_evidence_metrics(
            outputs["context"]["documents"],
            expectations["required_evidence"],
            expectations["alternatives"],
            pages,
        )[metric]

    return score


def native_rows(result, records, snapshots, pages):
    frame = result.result_df
    require(frame is not None and len(frame) == len(records), "Missing native rows")
    expected = {r["inputs"]["snapshot_id"]: r for r in records}
    seen, rows = set(), []
    for native in frame.to_dict("records"):
        request, response = native["request"], native["response"]
        require(isinstance(request, dict), "Native request must be a dictionary")
        identity = request["snapshot_id"]
        require(
            identity in expected and identity not in seen, "Native snapshot mismatch"
        )
        seen.add(identity)
        record = expected[identity]
        snapshot = snapshots[identity]
        require(request == record["inputs"], "Native inputs changed")
        require(
            response == snapshot["outputs"], "Native response changed frozen context"
        )
        gold = record["expectations"]
        values = alternative_evidence_metrics(
            response["context"]["documents"],
            gold["required_evidence"],
            gold["alternatives"],
            pages,
        )
        scores = {}
        for metric in METRICS:
            value = float(native[f"{metric}/value"])
            require(
                math.isfinite(value) and value in (0, 1),
                f"Invalid {identity}: {metric}",
            )
            require(
                value == values[metric], f"Native/helper mismatch: {identity}/{metric}"
            )
            scores[metric] = value
        for suffix in ("complete_evidence", "strict_complete_evidence"):
            canonical, alternative = (
                scores[f"canonical_{suffix}"],
                scores[f"alternative_{suffix}"],
            )
            require(
                canonical == snapshot["old_metrics"][suffix],
                f"Historical mismatch: {identity}/{suffix}",
            )
            require(alternative >= canonical, f"Non-monotone alternative: {identity}")
            if not gold["alternatives"]:
                require(alternative == canonical, f"Uncovered case changed: {identity}")
        witnesses = []
        for index, option in enumerate(gold["alternatives"]):
            complete = evidence_metrics(response["context"]["documents"], option, pages)
            if complete["complete_evidence"] or complete["strict_complete_evidence"]:
                witnesses.append(
                    {
                        "candidate_index": gold["candidate_indices"][index],
                        "required_evidence": option,
                        "complete_evidence": complete["complete_evidence"],
                        "strict_complete_evidence": complete[
                            "strict_complete_evidence"
                        ],
                    }
                )
        for suffix in ("complete_evidence", "strict_complete_evidence"):
            expected_complete = bool(scores[f"canonical_{suffix}"]) or any(
                witness[suffix] for witness in witnesses
            )
            require(
                scores[f"alternative_{suffix}"] == float(expected_complete),
                f"Complete witness OR mismatch: {identity}/{suffix}",
            )
        rows.append(
            {
                **snapshot,
                "snapshot_id": identity,
                "metrics": scores,
                "accepted_complete_witnesses": witnesses,
            }
        )
    for metric in METRICS:
        for suffix in ("error_code", "error_message"):
            column = f"{metric}/{suffix}"
            if column in frame:
                require(
                    frame[column].dropna().eq("").all(),
                    f"Native scorer error: {column}",
                )
        mean = float(result.metrics[f"{metric}/mean"])
        require(
            math.isfinite(mean)
            and math.isclose(
                mean, sum(r["metrics"][metric] for r in rows) / len(rows), abs_tol=1e-12
            ),
            f"Native mean mismatch: {metric}",
        )
    return sorted(rows, key=lambda r: r["snapshot_id"])


def summarize(rows):
    groups = {}
    for method in SOURCES:
        for language in ("ru", "en"):
            group = [
                r for r in rows if r["method"] == method and r["language"] == language
            ]
            if group:
                counts = {m: sum(r["metrics"][m] for r in group) for m in METRICS}
                groups[f"{method}_{language}"] = {
                    "n": len(group),
                    "counts": counts,
                    "means": {m: v / len(group) for m, v in counts.items()},
                }
    differences = []
    for left, right in combinations(SOURCES, 2):
        for language in ("ru", "en"):
            a, b = groups.get(f"{left}_{language}"), groups.get(f"{right}_{language}")
            if a and b:
                differences.append(
                    {
                        "left": left,
                        "right": right,
                        "language": language,
                        "mean_differences": {
                            m: a["means"][m] - b["means"][m] for m in METRICS
                        },
                    }
                )
    changed = [
        r
        for r in rows
        if any(
            r["metrics"][f"alternative_{s}"] != r["metrics"][f"canonical_{s}"]
            for s in ("complete_evidence", "strict_complete_evidence")
        )
    ]
    return {
        "by_method_language": groups,
        "pairwise_differences": differences,
        "changed": [
            {k: r[k] for k in ("snapshot_id", "metrics", "accepted_complete_witnesses")}
            for r in changed
        ],
        "provider_calls": 0,
        "provider_cost": 0,
        "expert_calibration": "pending",
        "interpretation": "Targeted dev measurement sensitivity, not system improvement or equivalence; no winner/default change",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--smoke", action="store_true")
    modes.add_argument("--full", action="store_true")
    parser.add_argument(
        "--review-file",
        type=Path,
        action="append",
        required=True,
        help="Original reviewer/provenance file; repeat to include all reviews",
    )
    args = parser.parse_args()
    kind = "smoke" if args.smoke else "full"
    folder = Path("tmp/q3").resolve()
    folder.mkdir(parents=True, exist_ok=True)
    root = Path.cwd().resolve()
    reviews = sorted(
        {p.resolve().relative_to(root).as_posix() for p in args.review_file}
    )
    require(
        all(Path(p).is_file() and Path(p).stat().st_size for p in reviews),
        "Missing/empty review file",
    )
    versioned = sorted(set((*REPRODUCTION, MANIFEST, *reviews)))
    commit = check_versioned(versioned, committed=args.full)
    paths = {p: Path(p) for p in (*versioned, *SOURCE_PATHS.values())}
    hashes = {name: sha(path) for name, path in paths.items()}
    manifest = read_json(MANIFEST)
    require(
        set(manifest["review_files"]) == set(reviews), "All original reviews required"
    )
    review_data = [read_json(path) for path in reviews]
    require(
        len(review_data) == 2 and len({r["reviewer"] for r in review_data}) == 2,
        "Two distinct assistant reviews required",
    )
    for path, expected_hash in manifest["source_hashes"].items():
        require(sha(path) == expected_hash, f"Candidate source changed: {path}")
    candidates = manifest["candidates"]
    require(isinstance(candidates, list), "Manifest candidates must be a list")
    options = {}
    for index, candidate in enumerate(candidates):
        pair = candidate["scenario_id"], candidate["language"]
        require(
            pair in SCOPE and type(candidate["approved"]) is bool,
            "Candidate outside frozen scope or nonboolean approval",
        )
        require(
            isinstance(candidate["required_evidence"], list)
            and candidate["required_evidence"],
            "Empty candidate witness set",
        )
        agreement = all(
            any(
                (r["scenario_id"], r["language"]) == pair
                and r["verdict"] == "candidate_sufficient"
                for r in review["reviews"]
            )
            for review in review_data
        )
        require(
            candidate["approved"] == agreement, "Approval differs from original reviews"
        )
        if candidate["approved"]:
            options.setdefault(pair, []).append((index, candidate["required_evidence"]))

    # Build v2 annotations without importing retrieval/model/GPU dependencies.
    evidence = {e["id"]: e for e in read_jsonl(SOURCE_PATHS["evidence_sha256"])}
    canonical = {}
    for scenario in read_jsonl(SOURCE_PATHS["scenarios_sha256"]):
        if scenario["split"] == "dev" and scenario["required_evidence"]:
            for language in ("ru", "en"):
                canonical[scenario["id"], language] = {
                    "query": scenario["questions"][language],
                    "required_evidence": [
                        {"id": eid, "locators": evidence[eid]["locators"][language]}
                        for eid in scenario["required_evidence"]
                    ],
                }
    require(len(canonical) == 142, "Expected dev142")
    experiment = configure_tracking()
    client = mlflow.MlflowClient()
    snapshots, records = {}, []
    for method, source_id in SOURCES.items():
        source = client.get_run(source_id)
        require(source.info.status == "FINISHED", f"{method} source not FINISHED")
        for param, path in SOURCE_PATHS.items():
            require(
                source.data.params[param] == hashes[path],
                f"{method} source hash changed: {path}",
            )
        destination = folder / source_id
        destination.mkdir(exist_ok=True)
        artifact = Path(
            client.download_artifacts(
                source_id, "per-question-results.json", str(destination)
            )
        )
        paths[f"{source_id}/per-question-results.json"] = artifact
        hashes[f"{source_id}/per-question-results.json"] = sha(artifact)
        historical = read_json(artifact)["records"]
        require(len(historical) == 142, f"{method} not dev142")
        pairs = set()
        for row in historical:
            pair = row["expectations"]["scenario_id"], row["inputs"]["language"]
            require(
                pair in canonical and pair not in pairs,
                f"{method} unexpected/duplicate case",
            )
            pairs.add(pair)
            gold = canonical[pair]
            require(
                row["inputs"]["query"] == gold["query"]
                and row["expectations"]["required_evidence"]
                == gold["required_evidence"],
                "Historical annotations changed",
            )
            identity = f"{method}-{pair[0]}-{pair[1]}"
            context = deepcopy(row["outputs"]["context"])
            require(
                isinstance(context["documents"], list),
                "Missing historical context documents",
            )
            snapshots[identity] = {
                "method": method,
                "source_run_id": source_id,
                "scenario_id": pair[0],
                "language": pair[1],
                "outputs": {"context": context},
                "old_metrics": row["metrics"],
                "snapshot_sha256": digest(context),
            }
            approved = options.get(pair, [])
            records.append(
                {
                    "inputs": {"snapshot_id": identity},
                    "expectations": {
                        "required_evidence": deepcopy(gold["required_evidence"]),
                        "alternatives": deepcopy([option for _, option in approved]),
                        "candidate_indices": [index for index, _ in approved],
                    },
                }
            )
        require(
            pairs == set(canonical)
            and Counter(p[1] for p in pairs) == {"ru": 71, "en": 71},
            "Source population changed",
        )
    fingerprint = digest({"hashes": hashes, "snapshots": snapshots, "records": records})
    smoke = None
    if args.full:
        smoke = read_json(folder / "smoke.json")
        require(
            smoke["status"] == "FINISHED"
            and smoke["fingerprint"] == fingerprint
            and smoke["snapshot_ids"] == list(SMOKE_IDS)
            and smoke["assessments"] == 12
            and smoke["trace"]["spans"] > 0
            and smoke["trace"]["readback_seconds"] <= 60,
            "Matching successful smoke3 required",
        )
        prior = client.get_run(smoke["run_id"])
        require(
            prior.info.status == "FINISHED"
            and str(prior.info.experiment_id) == str(experiment)
            and prior.data.tags.get("q3_fingerprint") == fingerprint
            and prior.data.tags.get("run_kind") == "smoke",
            "Smoke backend status/identity mismatch",
        )
        backend_receipt = read_json(
            client.download_artifacts(smoke["run_id"], "run-receipt.json", str(folder))
        )
        require(backend_receipt == smoke, "Smoke receipt differs from logged artifact")
    if args.smoke:
        by_id = {r["inputs"]["snapshot_id"]: r for r in records}
        records = [by_id[identity] for identity in SMOKE_IDS]
    name = f"football-q3-{kind}-{fingerprint[:24]}"
    found = [
        d for d in client.search_datasets(experiment_ids=[experiment]) if d.name == name
    ]
    require(len(found) <= 1, "Ambiguous native dataset name")
    if found:
        dataset = get_dataset(dataset_id=found[0].dataset_id)
    else:
        dataset = create_dataset(
            name=name,
            experiment_id=[experiment],
            tags={"split": "dev", "q3_fingerprint": fingerprint},
        )
        dataset.merge_records(deepcopy(records))
    persisted = [
        {k: r[k] for k in ("inputs", "expectations")}
        for r in dataset.to_df().to_dict("records")
    ]
    require(
        sorted(map(encoded, persisted)) == sorted(map(encoded, records)),
        "Native dataset content mismatch",
    )
    pages = {
        (p["document_id"], p["pdf_page"]): p
        for p in read_jsonl(SOURCE_PATHS["cleaned_pages_sha256"])
    }
    for candidate in candidates:
        for unit in candidate["required_evidence"]:
            for locator in unit["locators"]:
                text = pages[locator["document_id"], locator["pdf_page"]]["text"]
                start, end = locator["char_start"], locator["char_end"]
                require(0 <= start < end <= len(text), "Invalid candidate range")
                require(
                    hashlib.sha256(text[start:end].encode("utf-8")).hexdigest()
                    == locator["span_sha256"],
                    "Candidate source span changed",
                )
        evidence_metrics([], candidate["required_evidence"], pages)
    allowed = {r["inputs"]["snapshot_id"] for r in records}

    @mlflow.trace(name="Q3_snapshot_replay", span_type="CHAIN")
    def predict(snapshot_id):
        require(snapshot_id in allowed, "Unknown replay snapshot")
        return deepcopy(snapshots[snapshot_id]["outputs"])

    with mlflow.start_run(run_name=f"Q3-alternative-evidence-{kind}") as run:
        mlflow.set_tags(
            {
                "stage": "analysis",
                "run_kind": kind,
                "q3_fingerprint": fingerprint,
                "scorer_execution": "direct_source_controlled",
                "default_changed": "false",
            }
        )
        mlflow.log_params(
            {
                "split": "dev",
                "questions": len(records),
                "git_commit": commit,
                "provider_calls": 0,
                "provider_cost": 0,
                **SAFE_ENV,
            }
        )
        work = folder / run.info.run_id
        work.mkdir(exist_ok=True)

        def save(name, value):
            path = work / name
            path.write_text(encoded(value) + "\n", encoding="utf-8")
            mlflow.log_artifact(str(path))

        # Freeze sources, annotations, reviews and helper code before any scoring.
        save("input-hashes.json", hashes)
        save("snapshots.json", snapshots)
        for path in versioned:
            mlflow.log_artifact(
                path,
                artifact_path="reproduction/"
                + str(Path(path).parent).replace("\\", "/"),
            )
        require(
            {name: sha(path) for name, path in paths.items()} == hashes,
            "Inputs changed before scoring",
        )
        trace = None
        if args.smoke:
            output = predict(snapshot_id=SMOKE_IDS[0])
            trace_id = mlflow.get_last_active_trace_id()
            save("smoke-trace-id.json", {"trace_id": trace_id})
            trace = trace_readback(trace_id, output, work)
            save("trace-readback.json", trace)
        result = mlflow.genai.evaluate(
            data=dataset,
            predict_fn=predict,
            scorers=[make_scorer(m, pages) for m in METRICS],
        )
        rows = native_rows(result, records, snapshots, pages)
        summary = {
            **summarize(rows),
            "native_metrics": result.metrics,
            "fingerprint": fingerprint,
            "assessments": len(rows) * 4,
        }
        save("per-question-results.json", {"records": rows})
        result.result_df.to_json(
            work / "native-results.json", orient="records", force_ascii=False
        )
        mlflow.log_artifact(str(work / "native-results.json"))
        save("summary.json", summary)
        require(
            {name: sha(path) for name, path in paths.items()} == hashes,
            "Inputs/code/reviews changed during scoring",
        )
        check_versioned(versioned, committed=args.full)
        receipt = {
            "status": "FINISHED",
            "run_id": run.info.run_id,
            "run_kind": kind,
            "fingerprint": fingerprint,
            "snapshot_ids": [r["inputs"]["snapshot_id"] for r in records],
            "assessments": len(rows) * 4,
            "trace": trace,
            "hashes": hashes,
            "summary_path": str(work / "summary.json"),
            "matching_smoke_run_id": smoke["run_id"] if smoke else None,
        }
        save("run-receipt.json", receipt)
    require(
        client.get_run(run.info.run_id).info.status == "FINISHED", "Run did not finish"
    )
    (folder / f"{kind}.json").write_text(encoded(receipt) + "\n", encoding="utf-8")
    print("FINISHED", run.info.run_id, str(work / "summary.json"), flush=True)


if __name__ == "__main__":
    main()
