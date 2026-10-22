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
    args = parser.parse_args()
    report = ingest(args.manifest, args.output, Path.cwd())
    print(json.dumps(report, ensure_ascii=False, indent=2))
