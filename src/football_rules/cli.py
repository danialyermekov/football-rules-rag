"""Command-line interface for the Football Rules RAG pipeline."""

import argparse
import json
from pathlib import Path

from football_rules.config import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_CLEANED_PAGES_PATH,
    DEFAULT_CHUNKS_PATH,
    DEFAULT_GENERATION_MODEL,
    DEFAULT_INDEX_EMBEDDING,
    DEFAULT_LANGUAGE,
    DEFAULT_MANIFEST_PATH,
    DEFAULT_PAGES_PATH,
    DEFAULT_QDRANT_PATH,
    DEFAULT_SAVE_PATH,
    SUPPORTED_LANGUAGES,
    SUPPORTED_MODELS,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Football Rules RAG tools")
    commands = parser.add_subparsers(dest="command", required=True)

    ingestion = commands.add_parser(
        "ingest", help="Extract the registered PDFs page by page"
    )
    ingestion.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    ingestion.add_argument("--output", type=Path, default=DEFAULT_PAGES_PATH)

    cleaning = commands.add_parser(
        "clean", help="Clean extracted pages while retaining source ranges"
    )
    cleaning.add_argument("--input", type=Path, default=DEFAULT_PAGES_PATH)
    cleaning.add_argument("--output", type=Path, default=DEFAULT_CLEANED_PAGES_PATH)

    chunking = commands.add_parser(
        "chunk", help="Split cleaned pages with source provenance"
    )
    chunking.add_argument("--input", type=Path, default=DEFAULT_CLEANED_PAGES_PATH)
    chunking.add_argument("--output", type=Path, default=DEFAULT_CHUNKS_PATH)
    chunking.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    chunking.add_argument("--chunk-overlap", type=int, default=DEFAULT_CHUNK_OVERLAP)

    indexing = commands.add_parser(
        "index", help="Embed chunks and build a local Qdrant collection"
    )
    indexing.add_argument("--input", type=Path, default=DEFAULT_CHUNKS_PATH)
    indexing.add_argument("--database", type=Path, default=DEFAULT_QDRANT_PATH)
    indexing.add_argument(
        "--embedding",
        choices=["bge-m3", "qwen3-0.6b", "multilingual-e5-large"],
        default=DEFAULT_INDEX_EMBEDDING,
    )

    searching = commands.add_parser(
        "search", help="Retrieve chunks using local embeddings and Qdrant"
    )
    searching.add_argument("query")
    searching.add_argument("--language", choices=list(SUPPORTED_LANGUAGES), required=True)
    searching.add_argument("--collection", required=True)
    searching.add_argument("--database", type=Path, default=DEFAULT_QDRANT_PATH)
    searching.add_argument("--k", type=int, default=5)
    searching.add_argument(
        "--embedding",
        choices=["bge-m3", "qwen3-0.6b", "multilingual-e5-large"],
        default=DEFAULT_INDEX_EMBEDDING,
    )

    asking = commands.add_parser(
        "ask", help="Answer a question using Hybrid retrieval and Gemini"
    )
    asking.add_argument("query")
    asking.add_argument(
        "--language", choices=list(SUPPORTED_LANGUAGES), default=DEFAULT_LANGUAGE
    )
    asking.add_argument(
        "--model", choices=list(SUPPORTED_MODELS), default=DEFAULT_GENERATION_MODEL
    )
    asking.add_argument("--database", type=Path, default=DEFAULT_QDRANT_PATH)
    asking.add_argument("--collection", default=None)
    asking.add_argument(
        "--rerank",
        action="store_true",
        help="Apply Qwen3 cross-encoder reranking before packing context",
    )
    asking.add_argument(
        "--json", action="store_true", help="Include sources and token usage"
    )
    asking.add_argument(
        "--sources", action="store_true", help="Show the retrieved context excerpts"
    )
    asking.add_argument(
        "--save",
        type=Path,
        default=None,
        help="Append question, sources, answer, and settings to a JSONL file",
    )

    chatting = commands.add_parser(
        "chat",
        help="Interactive question-answering loop that loads the index once",
    )
    chatting.add_argument(
        "--language", choices=list(SUPPORTED_LANGUAGES), default=DEFAULT_LANGUAGE
    )
    chatting.add_argument(
        "--model", choices=list(SUPPORTED_MODELS), default=DEFAULT_GENERATION_MODEL
    )
    chatting.add_argument("--database", type=Path, default=DEFAULT_QDRANT_PATH)
    chatting.add_argument("--collection", default=None)
    chatting.add_argument(
        "--rerank",
        action="store_true",
        help="Apply Qwen3 cross-encoder reranking before packing context",
    )
    chatting.add_argument(
        "--save-path",
        type=Path,
        default=DEFAULT_SAVE_PATH,
        help="JSONL file used by the /save command",
    )

    args = parser.parse_args()

    if args.command == "ask":
        from football_rules.app import (
            ask_question,
            format_answer,
            format_sources,
            save_report,
        )

        if not args.query.strip():
            parser.error("Question must not be empty")
        report = ask_question(
            args.query,
            args.language,
            args.model,
            args.database,
            args.collection,
            rerank=args.rerank,
        )
        if args.save is not None:
            save_report(report, args.save)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(format_answer(report, args.model))
            if args.sources:
                print("\n" + format_sources(report))
        return

    if args.command == "chat":
        from football_rules.app import AskSession, chat_loop

        with AskSession(
            args.database, args.collection, rerank=args.rerank
        ) as session:
            chat_loop(
                session,
                language=args.language,
                model=args.model,
                save_path=args.save_path,
            )
        return

    if args.command == "ingest":
        from football_rules.ingestion import ingest

        report = ingest(args.manifest, args.output, Path.cwd())
    elif args.command == "clean":
        from football_rules.ingestion import clean_corpus

        report = clean_corpus(args.input, args.output)
    elif args.command == "chunk":
        from football_rules.ingestion import ChunkConfig, chunk_corpus

        config = ChunkConfig(args.chunk_size, args.chunk_overlap)
        report = chunk_corpus(args.input, args.output, config)
    elif args.command == "index":
        from football_rules.retrieval import index_chunks, load_embedder

        report = index_chunks(args.input, args.database, load_embedder(args.embedding))
    else:
        from football_rules.evaluation import configure_tracking
        from football_rules.retrieval import DenseRetriever, load_embedder

        configure_tracking()
        retriever = DenseRetriever(
            args.database, args.collection, load_embedder(args.embedding)
        )

        try:
            report = {"documents": retriever.search(args.query, args.language, args.k)}
        finally:
            retriever.close()

    print(json.dumps(report, ensure_ascii=False, indent=2))
