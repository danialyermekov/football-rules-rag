"""E25: rerank the frozen E10 union, select 50, then apply E21 packing.

Preparation is not authorization to run. Main must approve tests before smoke.
The supervisor bounds smoke/full to 240/720 seconds, including trace readback.
"""

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from time import perf_counter, time
from urllib.parse import urlparse
from urllib.request import url2pathname

PROCESS_STARTED = perf_counter()
REQUIRED_ENV = {
    "MLFLOW_DISABLE_TELEMETRY": "true",
    "MLFLOW_GENAI_EVAL_MAX_WORKERS": "1",
    "MLFLOW_GENAI_EVAL_MAX_SCORER_WORKERS": "1",
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "MLFLOW_ENABLE_ASYNC_TRACE_LOGGING": "false",
}
for _name, _value in REQUIRED_ENV.items():
    os.environ.setdefault(_name, _value)

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
    validate_native,
)
from evaluate_retrieval import evaluation_records, make_evidence_scorer, read_jsonl
from mlflow.genai.datasets import create_dataset, get_dataset
from transformers import AutoTokenizer

from football_rules.candidate_expansion import (
    merge_reranked_candidates,
    tail_candidates,
)
from football_rules.embeddings import MODEL_REVISION
from football_rules.evidence_evaluation import (
    chunk_successors,
    evidence_metrics,
    pack_context,
    prioritize_rule_neighbors,
    render_context,
)
from football_rules.reranking import (
    QWEN_INSTRUCTION,
    QWEN_MODEL_ID,
    QWEN_REVISION,
    CrossEncoderReranker,
    rank_documents,
)
from football_rules.tracking import configure_tracking

E10 = "b50e71e2d39d4145ae2f7e08fd49416e"
PREFIX_N = 50
POLICY = "full_e10_union_qwen_rerank_top50_e21_neighbors_b2048_v1"
TRACE_NAME = "E25_full_union_reranker"
FOLDER = Path("tmp/e25")
MODEL = Path("data/models/qwen3-reranker-0.6b")
INPUT_HASHES = {
    **FROZEN_HASHES,
    E10
    + "/per-question-results.json": "762ccd9194ed44b5826ac434a3176c7688e361a03ab196cf9b81586b034c7c8d",
}
# Locally present files of e61197..., pinned before any E25 inference.
MODEL_HASHES = {
    "config.json": "d479c427a9ca5295218063d4f9aca4f297ab4ac27487cca7af42c84643d51ef0",
    "model.safetensors": "27cd75a405b9c1b46b59abfd88aaa209e6fed2a1972cde9b70e7659537c5e65b",
    "tokenizer.json": "aeb13307a71acd8fe81861d94ad54ab689df773318809eed3cbe794b4492dae4",
    "tokenizer_config.json": "253153d0738ceb4c668d2eff957714dd2bea0b56de772a9fdccd96cbf517e6a0",
    "config_sentence_transformers.json": "6a153d6696f78fd588c1c728967f0b773ea869d3c6028f151ce71ebe49140762",
    "modules.json": "6f13b6b4a89e577b591b2077bca40c67c26541a6740a8809267cb474f90806a9",
    "sentence_bert_config.json": "3234ebd224d492cbe8d55d5ec80a3f408451c4db3005bafb64fe1c51c763e01e",
    "chat_template.jinja": "6f682162495ec5b39fd9005c01b6aa2a74669379fe967039f1e2cbbe8752369d",
    "1_LogitScore/config.json": "73e3156450564d8a98b7e47bcf5aace0f29600828b51937da545571e84db3ff3",
    "generation_config.json": "81051cd3f6e77013827148d0b8a6ead93f8ac390d5ab805f849199f0af6a08db",
    "merges.txt": "8831e4f1a044471340f7c0a83d7bd71306a5b867e95fd870f74d0c5308a904d5",
    "vocab.json": "ca10d7e9fb3ed18575dd1e277a2579c16d108e32f27439684afa0e10b1440910",
}
REPRODUCTION = (
    "scripts/evaluate_full_union_reranker.py",
    "scripts/evaluate_anchor_first.py",
    "scripts/evaluate_retrieval.py",
    "src/football_rules/candidate_expansion.py",
    "src/football_rules/reranking.py",
    "src/football_rules/evidence_evaluation.py",
    "src/football_rules/embeddings.py",
    "src/football_rules/tracking.py",
    "docs/retrieval-e25-protocol.md",
    "pyproject.toml",
    "uv.lock",
)


def clone(value):
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
    ).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def checkpoint(path, value):
    """Atomic durable response/receipt; never destroy a prior completed cache."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def model_manifest():
    """Hash weights once per process; stat guards detect changes at run end."""
    hashes, stamps = {}, {}
    for name, expected in MODEL_HASHES.items():
        path = MODEL / name
        metadata = MODEL / ".cache/huggingface/download" / (name + ".metadata")
        require(path.is_file() and metadata.is_file(), f"Missing local model: {name}")
        require(
            metadata.read_text(encoding="utf-8").splitlines()[:1] == [QWEN_REVISION],
            f"Unpinned model metadata: {name}",
        )
        before = path.stat()
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        require(actual == expected, f"Model hash mismatch: {name}")
        require(
            (before.st_size, before.st_mtime_ns)
            == (path.stat().st_size, path.stat().st_mtime_ns),
            f"Model changed while hashing: {name}",
        )
        hashes[str(path)] = actual
        hashes[str(metadata)] = sha(metadata)
        for item in (path, metadata):
            stat = item.stat()
            stamps[str(item)] = (stat.st_size, stat.st_mtime_ns)
    return hashes, stamps


def local_artifact(run, name):
    uri = run.info.artifact_uri
    require(uri.startswith("file:"), "Only local artifacts are allowed")
    parsed = urlparse(uri)
    require(not parsed.netloc, "Remote file authority is forbidden")
    return Path(url2pathname(parsed.path)) / name


def load_sources(client):
    runs, sources = {}, {}
    local = {p: Path(p) for p in INPUT_HASHES if "/per-question-results.json" not in p}
    for run_id in (E10, E15, E21):
        run = client.get_run(run_id)
        require(run.info.status == "FINISHED", f"Unfinished source: {run_id}")
        # No download/network fallback, including for the smoke receipt.
        path = local_artifact(run, "per-question-results.json")
        local[run_id + "/per-question-results.json"] = path
        rows = read_json(path)["records"]
        source = {key(r): r for r in rows}
        require(len(source) == len(rows) == 142, "Source is not unique dev142")
        sources[run_id], runs[run_id] = source, run
    hashes = {name: sha(path) for name, path in local.items()}
    require(hashes == INPUT_HASHES, "Frozen 11 input hashes differ")
    for parameter, path in SOURCE_PATHS.items():
        require(
            all(r.data.params[parameter] == hashes[path] for r in runs.values()),
            f"Source JSONL hash mismatch: {parameter}",
        )
    require(runs[E15].data.params["source_run_id"] == E10, "E15 lineage changed")
    require(runs[E21].data.params["source_run_id"] == E15, "E21 lineage changed")
    require(runs[E15].data.params["candidate_pool_size"] == "50", "Not E15 top50")
    return runs, sources, local, hashes


def replay(records, sources, chunks, pages, links, tokens):
    """Validate all frozen records before inference; gold never enters model inputs."""
    require(PREFIX_N == 50 and len(records) == 142, "E25 requires dev142/prefix50")
    identities = {key(r) for r in records}
    require(len(identities) == 142, "Duplicate dev inputs")
    require(all(set(s) == identities for s in sources.values()), "Source keys differ")
    by_id = {d["chunk_id"]: d for d in chunks}
    require(len(by_id) == len(chunks), "Duplicate corpus IDs")
    candidates, cached, total_tail = {}, {}, 0
    for language in ("ru", "en"):
        require(
            sum(r["inputs"]["language"] == language for r in records) == 71, "Not 71+71"
        )
    for record in records:
        identity = key(record)
        a, b, c = (sources[r][identity] for r in (E10, E15, E21))
        require(
            all(r["inputs"] == record["inputs"] for r in (a, b, c)), "Inputs changed"
        )
        require(
            all(r["expectations"] == record["expectations"] for r in (a, b, c)),
            "Gold changed",
        )
        fused = a["outputs"]["fusion_candidates"]
        prefix = b["outputs"]["documents"]
        require(
            64 <= len(fused) <= 92 and len(prefix) == PREFIX_N, "Unexpected pool size"
        )
        require(
            fused == sorted(fused, key=lambda d: (-d["score"], d["chunk_id"])),
            "E10 rank changed",
        )
        require(a["outputs"]["documents"] == fused[:PREFIX_N], "E10 top50 changed")
        require(
            b["outputs"]["source_candidates"] == fused[:PREFIX_N], "E15 source changed"
        )
        tail = tail_candidates(fused, prefix)
        total_tail += len(tail)
        require(
            all(all(d[k] == v for k, v in by_id[d["chunk_id"]].items()) for d in fused),
            "Corpus/source provenance changed",
        )
        require(
            {d["chunk_id"]: d for d in c["outputs"]["documents"]}
            == {d["chunk_id"]: d for d in prefix},
            "E21 scores or pool changed",
        )
        contexts = [
            pack_context(fused[:PREFIX_N], BUDGET, tokens),
            pack_context(prefix, BUDGET, tokens),
        ]
        ordered = prioritize_rule_neighbors(prefix, links)
        require(
            ordered == c["outputs"]["context_candidates"], "E21 order replay failed"
        )
        contexts.append(pack_context(ordered, BUDGET, tokens))
        for row, context in zip((a, b, c), contexts, strict=True):
            require(
                context == row["outputs"]["context"], "Frozen context replay failed"
            )
            values = evidence_metrics(
                context["documents"], record["expectations"]["required_evidence"], pages
            )
            require(
                all(values[m] == row["metrics"][m] for m in METRICS),
                "Frozen metrics replay failed",
            )
        candidates[identity], cached[identity] = fused, prefix
    require(total_tail == 3960, "Expected exactly 3960 new tail pairs")
    require(
        sum(len(d) for d in cached.values()) == 7100, "Expected 7100 original scores"
    )
    return candidates, cached


def validate_recipe(reranker, source_run):
    parameters = reranker.parameters()
    expected = {
        "model": QWEN_MODEL_ID,
        "revision": QWEN_REVISION,
        "device": "cuda",
        "dtype": "float32",
        "batch_size": 2,
        "max_pair_tokens": 1024,
        "truncation": "reject_overflow",
        "scores": "yes_minus_no_logits",
        "instruction": QWEN_INSTRUCTION,
    }
    require(
        all(parameters[k] == v for k, v in expected.items()),
        "Frozen Qwen recipe changed",
    )
    saved = {
        k.removeprefix("reranker_"): v
        for k, v in source_run.data.params.items()
        if k.startswith("reranker_")
    }
    require(
        {k: str(v) for k, v in parameters.items()} == saved,
        "Runtime differs from E15 recipe",
    )
    return parameters


def preflight_templates(reranker, candidates):
    """No predict/forward: check every actual Qwen chat template, not plain text."""
    maximum, pairs = 0, 0
    for (query, _), documents in candidates.items():
        require(
            query.strip() and all(d["text"].strip() for d in documents),
            "Empty model input",
        )
        features = reranker.model.preprocess(
            [(query, d["text"]) for d in documents],
            prompt=QWEN_INSTRUCTION,
            processing_kwargs={"text": {"truncation": False}},
        )
        lengths = features["attention_mask"].sum(dim=1).tolist()
        require(
            len(lengths) == len(documents) and max(lengths) <= 1024,
            "Template overflow; no truncation allowed",
        )
        maximum, pairs = max(maximum, max(lengths)), pairs + len(lengths)
    require(pairs == 11060, "Missing source template preflight")
    return {"queries": 142, "pairs": pairs, "max_template_tokens": maximum}


class ResponseCache:
    """Exact-input model responses only; no gold, evidence, or cached metrics."""

    def __init__(self, reranker, parameters, model_hashes, run_id):
        self.reranker, self.parameters = reranker, parameters
        self.model_hashes, self.run_id = model_hashes, run_id
        self.events = []

    def identity(self, query, documents):
        return {
            "query": query,
            "documents": documents,
            "parameters": self.parameters,
            "model_hashes": self.model_hashes,
        }

    def response(self, query, documents, purpose, *, cache_only=False):
        identity = self.identity(query, documents)
        cache_key = digest(identity)
        path = FOLDER / "responses" / purpose / (cache_key + ".json")
        pending = path.with_suffix(".pending.json")
        started = perf_counter()
        if path.exists():
            saved = read_json(path)
            require(saved["identity"] == identity, "Cache input mismatch")
            require(saved["cache_key"] == cache_key, "Cache key mismatch")
            status = "hit"
        else:
            require(not cache_only, f"Required smoke cache missing: {path}")
            require(
                not pending.exists(),
                f"Unresolved model call; no automatic retry: {pending}",
            )
            checkpoint(
                pending,
                {"run_id": self.run_id, "cache_key": cache_key, "started_at": time()},
            )
            response_started = perf_counter()
            documents_scored = self.reranker.rerank(query, documents)
            saved = {
                "identity": identity,
                "cache_key": cache_key,
                "documents": documents_scored,
                "response_seconds": perf_counter() - response_started,
                "producer_run_id": self.run_id,
            }
            # Checkpoint immediately on response, before metrics or further SDK calls.
            checkpoint(path, saved)
            status = "miss"
        scored = saved["documents"]
        lookup = {d["chunk_id"]: d for d in scored}
        require(
            len(lookup) == len(scored) == len(documents), "Cache duplicate/missing IDs"
        )
        require(
            set(lookup) == {d["chunk_id"] for d in documents},
            "Cache membership mismatch",
        )
        checked = rank_documents(
            documents, [lookup[d["chunk_id"]]["score"] for d in documents]
        )
        require(checked == scored, "Cache scores/rank/provenance invalid")
        require(
            math.isfinite(saved["response_seconds"]) and saved["response_seconds"] >= 0,
            "Invalid cache latency",
        )
        if pending.exists():
            pending.unlink()
        event = {
            "purpose": purpose,
            "cache_key": cache_key,
            "cache_status": status,
            "pairs": len(documents),
            "local_calls": int(status == "miss"),
            "local_pairs": len(documents) if status == "miss" else 0,
            "local_inference_seconds": saved["response_seconds"]
            if status == "miss"
            else 0,
            "cache_access_seconds": perf_counter() - started,
        }
        self.events.append(event)
        checkpoint(FOLDER / (self.run_id + "-calls.json"), self.events)
        print("CACHE", json.dumps(event), flush=True)
        return clone(scored), cache_key


def head_controls(records, candidates, cached, cache, *, cache_only=False):
    checks = []
    for record in records[:3]:
        identity = key(record)
        scored, cache_key = cache.response(
            identity[0],
            candidates[identity][:PREFIX_N],
            "head-control",
            cache_only=cache_only,
        )
        expected = cached[identity]
        scores = {d["chunk_id"]: d["score"] for d in expected}
        maximum = max(abs(d["score"] - scores[d["chunk_id"]]) for d in scored)
        exact_ids = [d["chunk_id"] for d in scored] == [d["chunk_id"] for d in expected]
        require(
            maximum <= 1e-4 and exact_ids,
            "Smoke head control mismatch; do not relax tolerance/rank",
        )
        checks.append(
            {
                "inputs": record["inputs"],
                "cache_key": cache_key,
                "scores_compared": 50,
                "max_abs_error": maximum,
                "exact_sorted_ids": exact_ids,
            }
        )
    require(
        sum(c["scores_compared"] for c in checks) == 150, "Not all 150 controls checked"
    )
    return checks


def trace_readback(trace_id, deadline):
    require(trace_id is not None, "No E25 trace ID")
    print("Starting trace readback", trace_id, flush=True)
    code = (
        "import json,sys,mlflow; mlflow.set_tracking_uri(sys.argv[1]); "
        "mlflow.flush_trace_async_logging(); t=mlflow.get_trace(sys.argv[2]); "
        "assert t and t.data.spans; spans=t.data.spans; "
        "assert any(s.name==sys.argv[3] and s.span_type=='CHAIN' and s.inputs and s.outputs for s in spans); "
        "assert any(s.name=='E25_union_reranking' and s.span_type=='RERANKER' and s.inputs and s.outputs for s in spans); "
        "print(json.dumps({'trace_id':sys.argv[2], 'spans':len(spans), 'chain':True, 'reranker':True}))"
    )
    started = perf_counter()
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            code,
            mlflow.get_tracking_uri(),
            trace_id,
            TRACE_NAME,
        ],
        capture_output=True,
        text=True,
        timeout=min(60, max(0.001, deadline - perf_counter())),
        check=True,
    )
    receipt = json.loads(result.stdout.strip().splitlines()[-1])
    receipt["readback_seconds"] = perf_counter() - started
    require(receipt["readback_seconds"] <= 60, "Trace readback exceeded deadline")
    return receipt


def native_dataset(client, experiment, records):
    name = "football-e25-" + digest(records)[:16]
    matches = [
        d for d in client.search_datasets(experiment_ids=[experiment]) if d.name == name
    ]
    require(len(matches) <= 1, "Ambiguous native dataset")
    if matches:
        dataset = get_dataset(dataset_id=matches[0].dataset_id)
    else:
        dataset = create_dataset(
            name=name,
            experiment_id=[experiment],
            tags={"split": "dev", "protocol": "v2"},
        )
        # MLflow mutates nested dictionaries while merging; isolate the frozen gold.
        dataset.merge_records(clone(records))
    actual = [
        clone({"inputs": r["inputs"], "expectations": r["expectations"]})
        for r in dataset.to_df().to_dict("records")
    ]
    require(canonical(actual) == canonical(records), "Native dataset mismatch")
    return dataset


def validate_smoke(smoke, binding, client, experiment):
    require(
        smoke["status"] == "FINISHED"
        and smoke["run_kind"] == "smoke"
        and smoke["questions"] == 3
        and smoke["binding"] == binding
        and smoke["trace"]["chain"]
        and smoke["trace"]["reranker"]
        and smoke["trace"]["spans"] >= 2
        and smoke["trace"]["readback_seconds"] <= 60
        and smoke["finite_assessments"] == 15
        and smoke["elapsed_seconds"] <= 240,
        "Successful matching smoke3 required",
    )
    run = client.get_run(smoke["run_id"])
    require(
        run.info.status == "FINISHED"
        and str(run.info.experiment_id) == str(experiment),
        "Smoke run not FINISHED in this experiment",
    )
    require(
        run.data.params["policy"] == POLICY and run.data.params["questions"] == "3",
        "Smoke metadata mismatch",
    )
    require(
        read_json(FOLDER / (smoke["run_id"] + ".json")) == smoke,
        "Run-specific smoke receipt differs",
    )
    backend = read_json(local_artifact(run, "run-receipt.json"))
    require(
        {k: v for k, v in backend.items() if k != "elapsed_seconds"}
        == {k: v for k, v in smoke.items() if k != "elapsed_seconds"},
        "Backend smoke receipt differs",
    )


def make_predict(candidates, cached, cache, links, tokens):
    observations = {}

    @mlflow.trace(name="E25_union_reranking", span_type="RERANKER")
    def rerank_union(query, fused, prefix):
        tail = tail_candidates(fused, prefix)
        fresh, cache_key = cache.response(query, tail, "tail")
        ranked = merge_reranked_candidates(fused, prefix, fresh)
        require(len(ranked) == len(fused), "Incomplete common ranking")
        return {"ranked_union": ranked, "tail_cache_key": cache_key}

    @mlflow.trace(name=TRACE_NAME, span_type="CHAIN")
    def predict(query, language):
        identity = query, language
        result = rerank_union(query, candidates[identity], cached[identity])
        documents = result["ranked_union"][:PREFIX_N]
        require(
            len(documents) == len({d["chunk_id"] for d in documents}) == 50,
            "Not unique selected50",
        )
        ordered = prioritize_rule_neighbors(documents, links)
        started = perf_counter()
        context = pack_context(ordered, BUDGET, tokens)
        require(
            context["text"] == render_context(context["documents"]),
            "Context render mismatch",
        )
        require(
            tokens(context["text"]) == context["token_count"] <= BUDGET,
            "Budget violation",
        )
        pool = {d["chunk_id"]: d for d in documents}
        require(
            all(d == pool[d["chunk_id"]] for d in context["documents"]),
            "Context outside selected50",
        )
        require(
            len({d["chunk_id"] for d in context["documents"]})
            == len(context["documents"]),
            "Duplicate context IDs",
        )
        output = {
            **result,
            "documents": documents,
            "context_candidates": ordered,
            "context": context,
            "packing_seconds": perf_counter() - started,
        }
        observations[identity] = output
        return output

    return predict, observations


def report(rows):
    by_language = {}
    for language in ("ru", "en"):
        subset = [r for r in rows if r["inputs"]["language"] == language]
        by_language[language] = {
            "n": len(subset),
            "metrics": {
                m: sum(r["metrics"][m] for r in subset) / len(subset) for m in METRICS
            },
            "baseline_metrics": {
                m: sum(r["baseline_metrics"][m] for r in subset) / len(subset)
                for m in METRICS
            },
            "complete_count": sum(r["metrics"]["complete_evidence"] for r in subset),
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
            "pool_metrics": {
                pool: {
                    m: sum(r["pool_metrics"][pool][m] for r in subset) / len(subset)
                    for m in METRICS
                }
                for pool in rows[0]["pool_metrics"]
            },
        }
    mean = sum(r["metrics"]["complete_evidence"] for r in rows) / len(rows)
    baseline = sum(r["baseline_metrics"]["complete_evidence"] for r in rows) / len(rows)
    return {
        "by_language": by_language,
        "mean_cer": mean,
        "baseline_mean_cer": baseline,
        "future_generation_gate": (
            mean > baseline
            and all(
                v["complete_count"] >= v["baseline_complete_count"] - 1
                for v in by_language.values()
            )
        )
        if len(rows) == 142
        else None,
        "default_changed": False,
        "test_evaluated": False,
        "gemini_calls": 0,
    }


def execute(smoke_mode, deadline):
    started = PROCESS_STARTED
    kind = "smoke" if smoke_mode else "full"
    for name, expected in REQUIRED_ENV.items():
        require(os.environ[name] == expected, f"E25 requires {name}={expected}")
    # Reject a remote tracking destination before configure_tracking can contact it.
    require(
        not os.environ.get("MLFLOW_TRACKING_URI")
        or os.environ["MLFLOW_TRACKING_URI"].startswith(("sqlite:", "file:")),
        "E25 requires local tracking",
    )
    experiment = configure_tracking()
    client = mlflow.MlflowClient()
    run_id, receipt = None, None
    with mlflow.start_run(run_name="E25-full-union-" + kind) as run:
        run_id = run.info.run_id
        print("STARTED", run_id, kind, flush=True)
        checkpoint(
            FOLDER / (kind + "-started.json"),
            {"run_id": run_id, "status": "RUNNING", "started_at": time()},
        )
        mlflow.set_tags(
            {"stage": "retrieval", "run_kind": kind, "default_changed": "false"}
        )
        runs, sources, local, hashes = load_sources(client)
        code_hashes = {p: sha(p) for p in REPRODUCTION}
        model_hashes, model_stamps = model_manifest()
        records = evaluation_records(Path(SOURCE_PATHS["chunks_sha256"]))
        records_hash = digest(records)
        chunks = read_jsonl(Path(SOURCE_PATHS["chunks_sha256"]))
        pages = {
            (p["document_id"], p["pdf_page"]): p
            for p in read_jsonl(Path(SOURCE_PATHS["cleaned_pages_sha256"]))
        }
        links = chunk_successors(chunks)
        metadata = Path(
            "data/models/bge-m3/.cache/huggingface/download/tokenizer.json.metadata"
        )
        require(
            metadata.read_text(encoding="utf-8").splitlines()[:1] == [MODEL_REVISION],
            "Budget tokenizer revision changed",
        )
        tokenizer = AutoTokenizer.from_pretrained(
            "data/models/bge-m3", local_files_only=True
        )

        def tokens(text):
            return len(tokenizer.encode(text, add_special_tokens=False))

        replay_started = perf_counter()
        candidates, cached = replay(records, sources, chunks, pages, links, tokens)
        replay_seconds = perf_counter() - replay_started
        reranker = CrossEncoderReranker(model_name="qwen3-0.6b", device="cuda")
        parameters = validate_recipe(reranker, runs[E15])
        binding = {
            "policy": POLICY,
            "input_hashes": hashes,
            "code_hashes": code_hashes,
            "model_hashes": model_hashes,
            "reranker_parameters": parameters,
        }
        smoke = None
        if not smoke_mode:
            smoke = read_json(FOLDER / "smoke.json")
            validate_smoke(smoke, binding, client, experiment)
        template_started = perf_counter()
        templates = preflight_templates(reranker, candidates)
        template_seconds = perf_counter() - template_started
        cache = ResponseCache(reranker, parameters, model_hashes, run_id)
        controls = head_controls(
            records, candidates, cached, cache, cache_only=not smoke_mode
        )
        if smoke is not None:
            require(
                controls == smoke["head_controls"], "Smoke head receipt checks differ"
            )
            # Full must reuse each smoke tail response, never silently reconstruct it.
            for record in records[:3]:
                identity = key(record)
                _, cache_key = cache.response(
                    identity[0],
                    tail_candidates(candidates[identity], cached[identity]),
                    "tail",
                    cache_only=True,
                )
                require(
                    cache_key == smoke["tail_cache_keys"][digest(record["inputs"])],
                    "Smoke tail receipt mismatch",
                )
        selected = records[:3] if smoke_mode else records
        dataset = native_dataset(client, experiment, selected)
        predict, observations = make_predict(candidates, cached, cache, links, tokens)
        mlflow.log_params(
            {
                "policy": POLICY,
                "e10_run": E10,
                "e15_run": E15,
                "e21_run": E21,
                "split": "dev",
                "questions": len(selected),
                "prefix_n": PREFIX_N,
                "context_budget": BUDGET,
                "tokenizer_revision": MODEL_REVISION,
                "latency_scope": "offline_local_tail_inference_cache_and_packing_not_online_sla",
                **{name: hashes[p] for name, p in SOURCE_PATHS.items()},
                **{"reranker_" + k: v for k, v in parameters.items()},
            }
        )
        mlflow.log_dict(binding, "binding.json")
        mlflow.log_dict(REQUIRED_ENV, "environment.json")
        mlflow.log_dict(templates, "template-preflight.json")
        mlflow.log_dict({"checks": controls}, "head-controls.json")
        mlflow.log_dict(links, "neighbor-links.json")
        for path in REPRODUCTION:
            mlflow.log_artifact(path, artifact_path="reproduction")
        trace_receipt = None
        if smoke_mode:
            predict(**selected[0]["inputs"])
            trace_id = mlflow.get_last_active_trace_id()
            print("TRACE", trace_id, flush=True)
            checkpoint(FOLDER / (run_id + "-trace.json"), {"trace_id": trace_id})
            trace_receipt = trace_readback(trace_id, deadline)
            mlflow.log_dict(trace_receipt, "trace-readback.json")
        mlflow.set_tag("scorer_execution", "imported_repository_code_no_registration")
        evaluation_started = perf_counter()
        result = mlflow.genai.evaluate(
            data=dataset,
            predict_fn=predict,
            scorers=[make_evidence_scorer(m, pages) for m in METRICS],
        )
        evaluation_seconds = perf_counter() - evaluation_started
        rows = []
        for record in selected:
            identity = key(record)
            output = observations[identity]
            required = record["expectations"]["required_evidence"]
            pools = {
                "original50": cached[identity],
                "full_union": candidates[identity],
                "reranked_union": output["ranked_union"],
                "selected50": output["documents"],
            }
            rows.append(
                {
                    **record,
                    "outputs": output,
                    "metrics": evidence_metrics(
                        output["context"]["documents"], required, pages
                    ),
                    "baseline_metrics": {
                        m: sources[E21][identity]["metrics"][m] for m in METRICS
                    },
                    "pool_metrics": {
                        name: evidence_metrics(docs, required, pages)
                        for name, docs in pools.items()
                    },
                }
            )
            require(
                rows[-1]["pool_metrics"]["full_union"]
                == rows[-1]["pool_metrics"]["reranked_union"],
                "Reranking lost pool coverage",
            )
        validate_native(result, rows)
        # Means alone cannot detect swapped assessments: verify each native row.
        native_seen = set()
        by_key = {key(r): r for r in rows}
        frame = result.result_df
        if frame is None:
            raise ValueError("Missing native result frame")
        for native in frame.to_dict("records"):
            identity = native["request"]["query"], native["request"]["language"]
            require(
                identity in by_key and identity not in native_seen,
                "Native row identity mismatch",
            )
            native_seen.add(identity)
            require(
                native["response"]["context"] == by_key[identity]["outputs"]["context"],
                "Native context mismatch",
            )
            require(
                all(
                    math.isclose(
                        float(native[m + "/value"]),
                        by_key[identity]["metrics"][m],
                        rel_tol=0,
                        abs_tol=1e-12,
                    )
                    for m in METRICS
                ),
                "Native per-row metric mismatch",
            )
        require(len(native_seen) == len(selected), "Missing completed questions")
        require(digest(records) == records_hash, "SDK mutated frozen records")
        require(
            {name: sha(path) for name, path in local.items()} == hashes,
            "Input changed during run",
        )
        require(
            {p: sha(p) for p in REPRODUCTION} == code_hashes, "Code changed during run"
        )
        require(
            all(
                (Path(p).stat().st_size, Path(p).stat().st_mtime_ns) == stamp
                for p, stamp in model_stamps.items()
            ),
            "Model changed during run",
        )
        summary = report(rows)
        summary["native_metrics"] = result.metrics
        summary["calls"] = cache.events
        summary["timing"] = {
            "replay_seconds": replay_seconds,
            "template_preflight_seconds": template_seconds,
            "native_evaluation_seconds": evaluation_seconds,
        }
        summary["local_calls"] = {
            purpose: {
                field: sum(e[field] for e in cache.events if e["purpose"] == purpose)
                for field in ("local_calls", "local_pairs", "local_inference_seconds")
            }
            for purpose in ("head-control", "tail")
        }
        summary["original_cached_scores"] = 7100
        summary["new_tail_pairs_total"] = 3960
        if not smoke_mode:
            require(
                len(rows) == 142 and len(rows) * len(METRICS) == 710,
                "Incomplete full142/710 assessments",
            )
            require(
                all(
                    summary["by_language"][lang]["pool_metrics"]["original50"][
                        "complete_evidence"
                    ]
                    == count / 71
                    for lang, count in (("ru", 61), ("en", 67))
                ),
                "Original pool diagnostic changed",
            )
            require(
                all(
                    summary["by_language"][lang]["pool_metrics"]["full_union"][
                        "complete_evidence"
                    ]
                    == count / 71
                    for lang, count in (("ru", 64), ("en", 68))
                ),
                "Union pool diagnostic changed",
            )
        checkpoint(FOLDER / (run_id + "-results.json"), {"records": rows})
        mlflow.log_dict({"records": rows}, "per-question-results.json")
        mlflow.log_dict(summary, "summary.json")
        mlflow.log_metrics(
            {
                **{
                    f"{lang}_{m}": v["metrics"][m]
                    for lang, v in summary["by_language"].items()
                    for m in METRICS
                },
                **{
                    f"{purpose}_{field}": value
                    for purpose, counters in summary["local_calls"].items()
                    for field, value in counters.items()
                },
                **summary["timing"],
            }
        )
        receipt = {
            "run_id": run_id,
            "run_kind": kind,
            "status": "FINISHED",
            "questions": len(rows),
            "binding": binding,
            "authorizing_smoke_run_id": smoke["run_id"] if smoke is not None else None,
            "head_controls": controls,
            "trace": trace_receipt,
            "finite_assessments": len(rows) * len(METRICS),
            "summary": summary,
            "tail_cache_keys": {
                digest(r["inputs"]): r["outputs"]["tail_cache_key"] for r in rows
            },
            "elapsed_seconds": perf_counter() - started,
        }
        require(
            receipt["elapsed_seconds"] <= (240 if smoke_mode else 720),
            "Run exceeded deadline",
        )
        mlflow.log_dict(receipt, "run-receipt.json")
    if run_id is None or receipt is None:
        raise ValueError("Run exited without a completed receipt")
    require(client.get_run(run_id).info.status == "FINISHED", "Run did not finish")
    receipt["elapsed_seconds"] = perf_counter() - started
    require(
        receipt["elapsed_seconds"] <= (240 if smoke_mode else 720),
        "Run finalization exceeded deadline",
    )
    checkpoint(FOLDER / (run_id + ".json"), receipt)
    checkpoint(FOLDER / (kind + ".json"), receipt)
    print(
        "FINISHED", json.dumps(receipt, ensure_ascii=False, allow_nan=False), flush=True
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--deadline", type=float, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        require(args.deadline is not None, "Worker requires supervisor deadline")
        execute(args.smoke, args.deadline)
        return
    deadline = PROCESS_STARTED + (240 if args.smoke else 720)
    command = [
        sys.executable,
        "-B",
        str(Path(__file__).resolve()),
        "--worker",
        "--deadline",
        str(deadline),
    ]
    if args.smoke:
        command.append("--smoke")
    try:
        result = subprocess.run(
            command, timeout=max(0.001, deadline - perf_counter()), check=False
        )
    except subprocess.TimeoutExpired:
        raise SystemExit(
            "E25 deadline exceeded; preserve caches, inspect started run; no automatic rerun"
        ) from None
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
