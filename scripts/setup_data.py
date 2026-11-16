"""Download and verify IFAB/RFS PDFs and pinned local Hugging Face models."""

import argparse
import hashlib
from pathlib import Path
from urllib.request import Request, urlopen

from football_rules.ingestion.pdf import load_sources, source_path
from football_rules.retrieval.embeddings import QWEN_MODEL_ID, QWEN_MODEL_REVISION
from football_rules.retrieval.reranking import QWEN_MODEL_ID as QWEN_RERANK_ID
from football_rules.retrieval.reranking import QWEN_REVISION as QWEN_RERANK_REVISION

USER_AGENT = "football-rules-rag/0.1 (+https://github.com)"

EMBEDDING_FILES = (
    "model.safetensors",
    "config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "config_sentence_transformers.json",
    "modules.json",
    "1_Pooling/config.json",
)

RERANKER_FILES = (
    "config.json",
    "model.safetensors",
    "tokenizer.json",
    "tokenizer_config.json",
    "config_sentence_transformers.json",
    "modules.json",
    "sentence_bert_config.json",
    "chat_template.jinja",
    "1_LogitScore/config.json",
)


def _file_matches(path: Path, expected_bytes: int, expected_sha256: str) -> bool:
    if not path.is_file() or path.stat().st_size != expected_bytes:
        return False
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest == expected_sha256


def download_pdfs(manifest_path: Path, root: Path) -> list[Path]:
    """Download registered PDFs if missing and verify exact byte size and SHA-256."""
    sources = load_sources(manifest_path)
    downloaded: list[Path] = []
    for source in sources:
        target = source_path(source, root)
        if _file_matches(target, source.bytes, source.sha256):
            print(f"[ok] {source.id}: already verified at {target}")
            downloaded.append(target)
            continue

        print(f"[download] {source.id}: {source.source_url}")
        request = Request(source.source_url, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=60) as response:
            payload = response.read()

        actual_sha = hashlib.sha256(payload).hexdigest()
        if len(payload) != source.bytes or actual_sha != source.sha256:
            raise ValueError(
                f"{source.id}: downloaded PDF failed verification "
                f"(bytes={len(payload)}/{source.bytes}, sha256={actual_sha})"
            )

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        print(f"[saved] {source.id}: {target}")
        downloaded.append(target)
    return downloaded


def download_hf_model(
    repo_id: str,
    revision: str,
    filenames: tuple[str, ...],
    local_dir: Path,
) -> Path:
    """Download pinned Hugging Face files with .cache metadata intact."""
    from huggingface_hub import hf_hub_download

    local_dir.mkdir(parents=True, exist_ok=True)
    for filename in filenames:
        print(f"[hf] {repo_id}@{revision[:8]} -> {filename}")
        hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            revision=revision,
            local_dir=str(local_dir),
        )
    return local_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path, default=Path("docs/source-manifest.json")
    )
    parser.add_argument("--pdfs", action="store_true", help="Download source PDFs")
    parser.add_argument(
        "--models", action="store_true", help="Download Qwen3-Embedding-0.6B"
    )
    parser.add_argument(
        "--reranker",
        action="store_true",
        help="Also download optional Qwen3-Reranker-0.6B",
    )
    args = parser.parse_args()

    if not (args.pdfs or args.models or args.reranker):
        args.pdfs = True
        args.models = True

    if args.pdfs:
        download_pdfs(args.manifest, Path.cwd())
    if args.models:
        download_hf_model(
            QWEN_MODEL_ID,
            QWEN_MODEL_REVISION,
            EMBEDDING_FILES,
            Path("data/models/qwen3-embedding-0.6b"),
        )
    if args.reranker:
        download_hf_model(
            QWEN_RERANK_ID,
            QWEN_RERANK_REVISION,
            RERANKER_FILES,
            Path("data/models/qwen3-reranker-0.6b"),
        )


if __name__ == "__main__":
    main()
