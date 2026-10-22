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

    args = parser.parse_args()

    if args.command == "ingest":
        report = ingest(args.manifest, args.output, Path.cwd())
    elif args.command == "clean":
        from football_rules.cleaning import clean_corpus

        report = clean_corpus(args.input, args.output)
    else:
        from football_rules.chunking import ChunkConfig, chunk_corpus

        config = ChunkConfig(args.chunk_size, args.chunk_overlap)
        report = chunk_corpus(args.input, args.output, config)

    print(json.dumps(report, ensure_ascii=False, indent=2))
