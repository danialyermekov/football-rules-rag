import argparse
import json
from pathlib import Path


def main() -> None:
    from football_rules.ingestion import ingest

    parser = argparse.ArgumentParser(description="Football Rules document tools")
    commands = parser.add_subparsers(dest="command", required=True)
    ingestion = commands.add_parser(
        "ingest", help="Extract the registered PDFs page by page"
    )
    ingestion.add_argument(
        "--manifest", type=Path, default=Path("docs/source-manifest.json")
    )
    ingestion.add_argument(
        "--output", type=Path, default=Path("data/processed/pages.jsonl")
    )

    cleaning = commands.add_parser(
        "clean", help="Clean extracted pages while retaining source ranges"
    )
    cleaning.add_argument(
        "--input", type=Path, default=Path("data/processed/pages.jsonl")
    )
    cleaning.add_argument(
        "--output", type=Path, default=Path("data/processed/cleaned-pages.jsonl")
    )

    chunking = commands.add_parser(
        "chunk", help="Split cleaned pages with source provenance"
    )
    chunking.add_argument(
        "--input", type=Path, default=Path("data/processed/cleaned-pages.jsonl")
    )
    chunking.add_argument(
        "--output", type=Path, default=Path("data/processed/chunks.jsonl")
    )
    chunking.add_argument("--chunk-size", type=int, default=1000)
    chunking.add_argument("--chunk-overlap", type=int, default=150)

    indexing = commands.add_parser(
        "index", help="Embed chunks and build a local Qdrant collection"
    )
    indexing.add_argument(
        "--input", type=Path, default=Path("data/processed/chunks.jsonl")
    )
    indexing.add_argument("--database", type=Path, default=Path("data/qdrant"))
    indexing.add_argument(
        "--embedding",
        choices=["bge-m3", "qwen3-0.6b", "multilingual-e5-large"],
        default="bge-m3",
    )

    searching = commands.add_parser(
        "search", help="Retrieve chunks using local embeddings and Qdrant"
    )
    searching.add_argument("query")
    searching.add_argument("--language", choices=["ru", "en"], required=True)
    searching.add_argument("--collection", required=True)
    searching.add_argument("--database", type=Path, default=Path("data/qdrant"))
    searching.add_argument("--k", type=int, default=5)
    searching.add_argument(
        "--embedding",
        choices=["bge-m3", "qwen3-0.6b", "multilingual-e5-large"],
        default="bge-m3",
    )

    args = parser.parse_args()

    if args.command == "ingest":
        report = ingest(args.manifest, args.output, Path.cwd())
    elif args.command == "clean":
        from football_rules.cleaning import clean_corpus

        report = clean_corpus(args.input, args.output)
    elif args.command == "chunk":
        from football_rules.chunking import ChunkConfig, chunk_corpus

        config = ChunkConfig(args.chunk_size, args.chunk_overlap)
        report = chunk_corpus(args.input, args.output, config)
    elif args.command == "index":
        from football_rules.embeddings import load_embedder
        from football_rules.retrieval import index_chunks

        report = index_chunks(args.input, args.database, load_embedder(args.embedding))
    else:
        from football_rules.embeddings import load_embedder
        from football_rules.retrieval import DenseRetriever
        from football_rules.tracking import configure_tracking

        configure_tracking()
        retriever = DenseRetriever(
            args.database, args.collection, load_embedder(args.embedding)
        )

        try:
            report = {"documents": retriever.search(args.query, args.language, args.k)}
        finally:
            retriever.close()

    print(json.dumps(report, ensure_ascii=False, indent=2))
