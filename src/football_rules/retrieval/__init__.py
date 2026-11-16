"""Retrieval, fusion, reranking, and context assembly subpackage."""

from football_rules.retrieval.bm25 import BM25Retriever, tokenize
from football_rules.retrieval.context import pack_context, render_context
from football_rules.retrieval.embeddings import (
    BGEEmbedder,
    E5Embedder,
    Embedder,
    QwenEmbedder,
    load_embedder,
)
from football_rules.retrieval.hybrid import HybridRetriever, reciprocal_rank_fusion
from football_rules.retrieval.reranking import (
    CrossEncoderReranker,
    fuse_retrieval_reranker,
    rank_documents,
)
from football_rules.retrieval.store import DenseRetriever, index_chunks, read_chunks

__all__ = [
    "BGEEmbedder",
    "BM25Retriever",
    "CrossEncoderReranker",
    "DenseRetriever",
    "E5Embedder",
    "Embedder",
    "HybridRetriever",
    "QwenEmbedder",
    "fuse_retrieval_reranker",
    "index_chunks",
    "load_embedder",
    "pack_context",
    "rank_documents",
    "read_chunks",
    "reciprocal_rank_fusion",
    "render_context",
    "tokenize",
]
