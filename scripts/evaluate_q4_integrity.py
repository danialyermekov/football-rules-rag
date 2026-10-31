"""Q4 frozen-answer integrity only; never calls Ragas or a provider.

Run --prepare-only, obtain two independent reviews, then --smoke and --full.
Caller must enforce external process deadlines of 120s / 180s respectively.
Each --review-file is JSON: {"reviewer": "unique name", "reviews": [
{"packet_id": "P001", "meaning_changed": false, "rationale": "...",
 "examples": ["exact text ..."]}, ...]}. Null meaning_changed is permitted.
Semantic reviews are descriptive, never structural scores or an approval vote.
"""

import argparse
import hashlib
import json
import math
import os
import random
import subprocess
from collections import Counter
from copy import deepcopy
from pathlib import Path
from time import perf_counter, time

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

from football_rules.answer_envelope import (
    build_answer_envelope,
    validate_answer_envelope,
)
from football_rules.tracking import configure_tracking

SOURCE = "0efab3b7199845e9b4ba2942399f106c"
SMOKE = ("Q015", "Q026", "Q033")
PROBES = (*SMOKE, "Q003", "Q010", "Q025")
FOLDER = Path("tmp/q4")
PACKET = "docs/evaluation-q4-review-packet.json"
Q1_REVIEW = "docs/evaluation-q1-review.json"
VERSIONED = (
    "scripts/evaluate_q4_integrity.py",
    "src/football_rules/answer_envelope.py",
    "tests/test_answer_envelope.py",
    "src/football_rules/tracking.py",
    "docs/evaluation-q4-protocol.md",
    PACKET,
    Q1_REVIEW,
    "pyproject.toml",
    "uv.lock",
)
METRICS = ("envelope_integrity", "corruption_rejected")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(encoded(value).encode("utf-8")).hexdigest()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    Path(path).write_text(encoded(value) + "\n", encoding="utf-8")


def source_path(path):
    # Q1 recorded Windows separators, sometimes with an absolute workspace prefix.
    normalized = path.replace("\\", "/")
    parts = normalized.split("/")
    if "mlruns" in parts:
        normalized = "/".join(parts[parts.index("mlruns") :])
    resolved = Path(normalized).resolve()
    resolved.relative_to(Path.cwd().resolve())
    return resolved


def git(*args):
    return subprocess.run(
        ["git", "--no-pager", "--no-optional-locks", *args],
        check=True,
        capture_output=True,
        timeout=15,
    ).stdout


def provenance(paths, committed):
    for path in paths:
        git("ls-files", "--error-unmatch", "--", path)
    if committed:
        git("diff", "--exit-code", "HEAD", "--", *paths)
    return {
        "commit": git("rev-parse", "HEAD").decode().strip(),
        "status": git("status", "--porcelain", "--", *paths).decode(),
        "diff_sha256": hashlib.sha256(git("diff", "HEAD", "--", *paths)).hexdigest(),
    }


def frozen_source(client):
    require(client.get_run(SOURCE).info.status == "FINISHED", "Q1 source not FINISHED")
    paths = {Q1_REVIEW: Path(Q1_REVIEW)}
    selection = read(Q1_REVIEW)["selection"]
    for original, expected in selection["source_hashes"].items():
        path = source_path(original)
        require(sha(path) == expected, f"Q1 source hash mismatch: {original}")
        paths[path.relative_to(Path.cwd()).as_posix()] = path
    artifacts = {}
    for name in ("selection", "blinded", "judgments"):
        local = Path(f"mlruns/1/{SOURCE}/artifacts/audit/{name}.json")
        if not local.is_file():
            destination = FOLDER / "source"
            destination.mkdir(exist_ok=True)
            local = Path(
                client.download_artifacts(
                    SOURCE, f"audit/{name}.json", str(destination)
                )
            )
        paths[f"q1/audit/{name}.json"] = local
        artifacts[name] = read(local)
    require(artifacts["selection"] == selection, "Q1 artifact/docs selection differs")
    selected = selection["records"]
    require(len(selected) == 48, "Expected frozen Q1 selection48")
    require(
        Counter(r["language"] for r in selected) == {"ru": 24, "en": 24},
        "Q1 languages changed",
    )
    require(
        Counter(r["stratum"] for r in selected) == {"random": 24, "targeted": 24},
        "Q1 strata changed",
    )
    answers = {r["audit_id"]: r["answer"] for r in artifacts["blinded"]}
    judgments = {r["audit_id"]: r["judgments"] for r in artifacts["judgments"]}
    ids = {r["audit_id"] for r in selected}
    require(
        len(ids) == 48 and set(answers) == set(judgments) == ids,
        "Q1 audit identities differ",
    )
    historical = {}
    for run_id in selection["source_runs"]:
        result_path = Path(f"mlruns/1/{run_id}/artifacts/per-question-results.json")
        historical[run_id] = {
            r["inputs"]["snapshot_id"]: r for r in read(result_path)["records"]
        }
    snapshots, records = {}, []
    for row in selected:
        identity, answer = row["audit_id"], answers[row["audit_id"]]
        for occurrence in row["occurrences"]:
            source = historical[occurrence["run_id"]][occurrence["snapshot_id"]]
            item = {
                "question": source["inputs"]["query"],
                "language": source["inputs"]["language"],
                "status": source["outputs"]["status"],
                "answer": source["outputs"]["answer"],
                "citations": source["outputs"]["citations"],
                "contexts": [
                    {k: d[k] for k in ("document_id", "pdf_page", "text")}
                    for d in source["outputs"]["documents"]
                ],
                "expectations": source["expectations"],
            }
            original_fingerprint = hashlib.sha256(
                json.dumps(
                    item, sort_keys=True, ensure_ascii=False, separators=(",", ":")
                ).encode("utf-8")
            ).hexdigest()
            require(
                original_fingerprint == row["fingerprint"] and answer == item["answer"],
                "Frozen answer/source fingerprint differs",
            )
        # Q1's immutable content fingerprint is the replay snapshot identity.
        snapshot_id = row["fingerprint"]
        build_answer_envelope(
            answer, snapshot_id
        )  # Reject malformed/empty sources now.
        require(snapshot_id not in snapshots, "Duplicate Q1 fingerprint")
        snapshots[snapshot_id] = {
            "audit_id": identity,
            "scenario_id": row["scenario_id"],
            "answer": answer,
        }
        records.append(
            {
                "inputs": {"snapshot_id": snapshot_id},
                "expectations": {"answer": answer, "snapshot_id": snapshot_id},
            }
        )
    return paths, snapshots, records, judgments


def review_packet(snapshots, judgments):
    by_id = {r["audit_id"]: (sid, r) for sid, r in snapshots.items()}
    items = []
    for identity in PROBES:
        sid, row = by_id[identity]
        statements = judgments[identity]["faithfulness"]["parsed_responses"][0][
            "statements"
        ]
        require(
            isinstance(statements, list)
            and all(isinstance(s, str) for s in statements),
            "Expected first parsed faithfulness statements",
        )
        for method, units in (
            ("baseline", statements),
            (
                "whole_answer",
                [build_answer_envelope(row["answer"], sid)["units"][0]["quote"]],
            ),
        ):
            items.append(
                (
                    {"answer": row["answer"], "units": units},
                    {"audit_id": identity, "snapshot_id": sid, "method": method},
                )
            )
    random.Random(20261101).shuffle(items)
    packet, mapping = [], {}
    for index, (item, hidden) in enumerate(items, 1):
        identity = f"P{index:03d}"
        packet.append({"packet_id": identity, **item})
        mapping[identity] = hidden
    return packet, mapping


def semantic_reviews(files, packet):
    require(len(files) == 2, "Supply exactly two distinct --review-file paths")
    ids = {r["packet_id"] for r in packet}
    reviews = [read(path) for path in files]
    require(
        all(isinstance(r["reviewer"], str) and r["reviewer"].strip() for r in reviews),
        "Missing reviewer identity",
    )
    require(
        len({r["reviewer"] for r in reviews}) == 2, "Two distinct reviewers required"
    )
    indexed, counts = [], []
    for review in reviews:
        rows = review["reviews"]
        require(
            len(rows) == 12 and {r["packet_id"] for r in rows} == ids,
            "Each reviewer must cover all12 packet IDs once",
        )
        for row in rows:
            require(
                row["meaning_changed"] is None or type(row["meaning_changed"]) is bool,
                "Invalid meaning_changed",
            )
            require(
                isinstance(row["rationale"], str) and row["rationale"].strip(),
                "Missing review rationale",
            )
            require(
                isinstance(row["examples"], list)
                and row["examples"]
                and all(isinstance(e, str) and e for e in row["examples"]),
                "Missing exact review examples",
            )
        indexed.append({r["packet_id"]: r for r in rows})
        counts.append(
            {
                "reviewer": review["reviewer"],
                "counts": {
                    str(v): sum(r["meaning_changed"] is v for r in rows)
                    for v in (True, False, None)
                },
            }
        )
    return {
        "descriptive_only": True,
        "reviews": reviews,
        "counts": counts,
        "disagreements": [
            i
            for i in sorted(ids)
            if indexed[0][i]["meaning_changed"] != indexed[1][i]["meaning_changed"]
        ],
    }


@scorer
def envelope_integrity(outputs, expectations):
    validate_answer_envelope(
        expectations["answer"], expectations["snapshot_id"], outputs
    )
    return 1


@scorer
def corruption_rejected(outputs, expectations):
    answer, sid = expectations["answer"], expectations["snapshot_id"]
    validate_answer_envelope(answer, sid, outputs)
    mutants = [deepcopy(outputs) for _ in range(8)]
    mutants[0]["units"][0]["quote"] = answer + "!"
    mutants[1]["answer_sha256"] = "invalid-sha256"
    mutants[2]["snapshot_id"] = sid + "-corrupted"
    mutants[3]["units"][0]["end"] = len(answer) - 1
    mutants[4]["units"] = []
    mutants[5]["units"].append(deepcopy(outputs["units"][0]))
    mutants[6]["units"][0]["start"] = False
    mutants[7]["units"][0]["claim"] = answer
    rejected = 0
    for mutant in mutants:
        try:
            validate_answer_envelope(answer, sid, mutant)
        except ValueError:
            rejected += 1
    return int(rejected == 8)


def trace_readback(trace_id, started_ms, inputs, output, work):
    require(trace_id, "Fresh smoke trace ID missing")
    expected = work / "trace-expected.json"
    write(expected, {"inputs": inputs, "output": output})
    print("Starting trace readback", trace_id, flush=True)
    code = (
        "import json,sys,mlflow; mlflow.set_tracking_uri(sys.argv[1]); "
        "mlflow.flush_trace_async_logging(); t=mlflow.get_trace(sys.argv[2]); "
        "assert t and t.data.spans and t.info.request_time>=int(sys.argv[3]); "
        "s=next(s for s in t.data.spans if s.name=='Q4_answer_envelope'); "
        "e=json.load(open(sys.argv[4],encoding='utf-8')); "
        "assert s.inputs==e['inputs'] and s.outputs==e['output']; "
        "print(json.dumps({'trace_id':sys.argv[2],'spans':len(t.data.spans)}))"
    )
    started = perf_counter()
    result = subprocess.run(
        [
            "uv",
            "run",
            "--no-sync",
            "python",
            "-c",
            code,
            mlflow.get_tracking_uri(),
            trace_id,
            str(started_ms),
            str(expected),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=60,
    )
    receipt = json.loads(result.stdout.strip().splitlines()[-1])
    receipt["readback_seconds"] = perf_counter() - started
    require(receipt["readback_seconds"] <= 60, "Trace readback exceeded60s")
    return receipt


def native_rows(result, records):
    frame = result.result_df
    require(frame is not None and len(frame) == len(records), "Missing native rows")
    expected = {r["inputs"]["snapshot_id"]: r for r in records}
    rows, seen = [], set()
    for row in frame.to_dict("records"):
        request, response = row["request"], row["response"]
        require(isinstance(request, dict), "Native request is not a dictionary")
        sid = request["snapshot_id"]
        require(
            sid in expected and sid not in seen, "Native identity mismatch/duplicate"
        )
        seen.add(sid)
        record = expected[sid]
        require(request == record["inputs"], "Native inputs changed")
        validate_answer_envelope(record["expectations"]["answer"], sid, response)
        scores = {}
        for metric in METRICS:
            value = row[f"{metric}/value"]
            require(
                not isinstance(value, bool)
                and isinstance(value, (int, float))
                and math.isfinite(value)
                and value == 1,
                f"Invalid native assessment: {sid}/{metric}",
            )
            scores[metric] = value
        rows.append({**record, "outputs": response, "scores": scores})
    for metric in METRICS:
        mean = result.metrics[f"{metric}/mean"]
        require(math.isfinite(mean) and mean == 1, f"Invalid native mean: {metric}")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    for mode in ("prepare-only", "smoke", "full"):
        modes.add_argument(f"--{mode}", action="store_true")
    parser.add_argument("--review-file", type=Path, action="append", default=[])
    args = parser.parse_args()
    FOLDER.mkdir(parents=True, exist_ok=True)
    experiment = configure_tracking()
    client = mlflow.MlflowClient()
    paths, snapshots, records, judgments = frozen_source(client)
    packet, mapping = review_packet(snapshots, judgments)
    if args.prepare_only:
        write(PACKET, packet)
        write(FOLDER / "review-mapping.json", mapping)
        print(PACKET, FOLDER / "review-mapping.json")
        return
    require(
        read(PACKET) == packet and read(FOLDER / "review-mapping.json") == mapping,
        "Prepared packet/mapping differs; run --prepare-only",
    )
    reviews = sorted(
        {
            p.resolve().relative_to(Path.cwd().resolve()).as_posix()
            for p in args.review_file
        }
    )
    semantics = semantic_reviews(reviews, packet)
    versioned = sorted(set((*VERSIONED, *reviews)))
    before_git = provenance(versioned, args.full)
    paths.update({p: Path(p) for p in versioned})
    paths["review-mapping.json"] = FOLDER / "review-mapping.json"
    hashes = {p: sha(path) for p, path in paths.items()}
    fingerprint = digest({"hashes": hashes, "records": records, "source": SOURCE})
    kind = "smoke" if args.smoke else "full"
    smoke_ids = [
        sid
        for audit_id in SMOKE
        for sid, row in snapshots.items()
        if row["audit_id"] == audit_id
    ]
    require(len(smoke_ids) == 3, "Smoke identities missing")
    smoke = None
    if args.full:
        smoke = read(FOLDER / "smoke.json")
        require(
            smoke["status"] == "FINISHED"
            and smoke["fingerprint"] == fingerprint
            and smoke["snapshot_ids"] == smoke_ids
            and smoke["assessments"] == 6
            and smoke["trace"]["spans"] > 0
            and smoke["trace"]["readback_seconds"] <= 60,
            "Matching successful smoke3 required",
        )
        prior = client.get_run(smoke["run_id"])
        require(
            prior.info.status == "FINISHED"
            and str(prior.info.experiment_id) == str(experiment)
            and prior.data.tags.get("q4_fingerprint") == fingerprint
            and prior.data.tags.get("run_kind") == "smoke",
            "Smoke backend mismatch",
        )
        receipt_path = client.download_artifacts(
            smoke["run_id"], "run-receipt.json", str(FOLDER)
        )
        require(read(receipt_path) == smoke, "Smoke local/backend receipt differs")
    if args.smoke:
        by_id = {r["inputs"]["snapshot_id"]: r for r in records}
        records = [by_id[sid] for sid in smoke_ids]
    name = f"football-q4-{kind}-{fingerprint[:24]}"
    found, token = [], None
    while True:
        page = client.search_datasets(experiment_ids=[experiment], page_token=token)
        found.extend(d for d in page if d.name == name)
        token = page.token
        if not token:
            break
    require(len(found) <= 1, "Ambiguous native dataset")
    if found:
        dataset = get_dataset(dataset_id=found[0].dataset_id)
    else:
        dataset = create_dataset(
            name=name, experiment_id=[experiment], tags={"q4_fingerprint": fingerprint}
        )
        dataset.merge_records(deepcopy(records))
    persisted = [
        {k: r[k] for k in ("inputs", "expectations")}
        for r in dataset.to_df().to_dict("records")
    ]
    require(
        sorted(map(encoded, persisted)) == sorted(map(encoded, records)),
        "Native dataset differs",
    )
    allowed = {r["inputs"]["snapshot_id"] for r in records}

    @mlflow.trace(name="Q4_answer_envelope", span_type="CHAIN")
    def predict(snapshot_id):
        require(snapshot_id in allowed, "Unknown frozen snapshot")
        return build_answer_envelope(snapshots[snapshot_id]["answer"], snapshot_id)

    with mlflow.start_run(run_name=f"Q4-answer-integrity-{kind}") as run:
        mlflow.set_tags(
            {
                "q4_fingerprint": fingerprint,
                "run_kind": kind,
                "scorer_execution": "direct_source_controlled",
                "default_changed": "false",
            }
        )
        mlflow.log_params(
            {
                "questions": len(records),
                "provider_calls": 0,
                "git_commit": before_git["commit"],
                **SAFE_ENV,
            }
        )
        work = FOLDER / run.info.run_id
        work.mkdir()

        def save(name, value):
            write(work / name, value)
            mlflow.log_artifact(str(work / name))

        save("input-hashes.json", {"hashes": hashes, "git": before_git})
        save("semantic-reviews.json", semantics)
        save("snapshots.json", snapshots)
        for path in versioned:
            mlflow.log_artifact(
                path,
                artifact_path=(Path("reproduction") / Path(path).parent).as_posix(),
            )
        require(
            {p: sha(path) for p, path in paths.items()} == hashes,
            "Inputs changed before scoring",
        )
        trace = None
        if args.smoke:
            started_ms = int(time() * 1000)
            output = predict(snapshot_id=smoke_ids[0])
            trace_id = mlflow.get_last_active_trace_id()
            save(
                "smoke-trace-id.json", {"trace_id": trace_id, "started_ms": started_ms}
            )
            trace = trace_readback(
                trace_id, started_ms, {"snapshot_id": smoke_ids[0]}, output, work
            )
            save("trace-readback.json", trace)
        result = mlflow.genai.evaluate(
            data=dataset,
            predict_fn=predict,
            scorers=[envelope_integrity, corruption_rejected],
        )
        rows = native_rows(result, records)
        save("per-row-results.json", rows)
        result.result_df.to_json(
            work / "native-results.json", orient="records", force_ascii=False
        )
        mlflow.log_artifact(str(work / "native-results.json"))
        save(
            "summary.json",
            {
                "cases": len(rows),
                "assessments": 2 * len(rows),
                "native_metrics": result.metrics,
                "provider_calls": 0,
                "interpretation": "Structural integrity only; not faithfulness/accuracy improvement. Original answer errors remain; defaults unchanged.",
            },
        )
        after_hashes = {p: sha(path) for p, path in paths.items()}
        after_git = provenance(versioned, args.full)
        save("output-hashes.json", {"hashes": after_hashes, "git": after_git})
        require(
            after_hashes == hashes and after_git == before_git,
            "Source/code/protocol/reviews/Git changed during evaluation",
        )
        require(
            client.get_run(SOURCE).info.status == "FINISHED", "Q1 source status changed"
        )
        receipt = {
            "status": "FINISHED",
            "run_id": run.info.run_id,
            "run_kind": kind,
            "fingerprint": fingerprint,
            "snapshot_ids": [r["inputs"]["snapshot_id"] for r in records],
            "assessments": 2 * len(rows),
            "trace": trace,
            "hashes": hashes,
            "git_before": before_git,
            "git_after": after_git,
            "matching_smoke_run_id": smoke["run_id"] if smoke else None,
        }
        save("run-receipt.json", receipt)
    require(
        client.get_run(run.info.run_id).info.status == "FINISHED",
        "Evaluation run not FINISHED",
    )
    write(FOLDER / f"{kind}.json", receipt)
    print("FINISHED", run.info.run_id, work / "summary.json", flush=True)


if __name__ == "__main__":
    main()
