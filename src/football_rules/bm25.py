"""In-memory BM25 baseline with independent Russian and English statistics."""

import hashlib
import math
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

import mlflow

from football_rules.retrieval import read_chunks


def tokenize(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text).casefold().replace("ё", "е")
    return re.findall(r"[^\W_]+", normalized)


class BM25Retriever:
    def __init__(self, chunks_path: Path) -> None:
        chunks = read_chunks(chunks_path)

        if any(chunk["language"] not in {"ru", "en"} for chunk in chunks):
            raise ValueError("BM25 corpus languages must be en/ru")

        self.k1 = 1.2
        self.b = 0.75
        self.documents = {
            language: [chunk for chunk in chunks if chunk["language"] == language]
            for language in ("ru", "en")
        }
        self.terms = {
            language: [Counter(tokenize(chunk["text"])) for chunk in documents]
            for language, documents in self.documents.items()
        }
        self.lengths = {
            language: [sum(terms.values()) for terms in rows]
            for language, rows in self.terms.items()
        }
        self.frequencies: dict[str, Counter[str]] = {}

        for language, rows in self.terms.items():
            frequencies: Counter[str] = Counter()

            for terms in rows:
                frequencies.update(terms.keys())

            self.frequencies[language] = frequencies

        self.manifest: dict[str, Any] = {
            "strategy": "bm25",
            "version": "bm25_okapi_v1",
            "chunks_sha256": hashlib.sha256(chunks_path.read_bytes()).hexdigest(),
            "points": len(chunks),
            "k1": self.k1,
            "b": self.b,
            "tokenization": "NFKC_casefold_yo_to_e_unicode_alphanumeric_v1",
            "unicode_version": unicodedata.unidata_version,
            "query_terms": "unique",
            "idf": "log(1+(N-df+0.5)/(df+0.5))",
            "language_statistics": "separate",
            "stopwords": False,
            "stemming": False,
            "zero_score_hits": "excluded",
            "tie_break": "chunk_id_ascending",
        }

    @mlflow.trace(name="bm25_search", span_type="RETRIEVER")
    def search(self, query: str, language: str, k: int = 5) -> list[dict[str, Any]]:
        if not query.strip() or language not in {"ru", "en"} or k <= 0:
            raise ValueError("Provide a nonempty query, language en/ru and positive k")

        documents = self.documents[language]
        lengths = self.lengths[language]
        total_length = sum(lengths)

        if not documents or total_length == 0:
            return []

        average_length = total_length / len(documents)
        query_terms = sorted(set(tokenize(query)))
        scores = []

        for document, terms, length in zip(
            documents, self.terms[language], lengths, strict=True
        ):
            score = 0.0
            normalization = self.k1 * (1 - self.b + self.b * length / average_length)

            for term in query_terms:
                frequency = terms[term]

                if frequency:
                    df = self.frequencies[language][term]
                    idf = math.log1p((len(documents) - df + 0.5) / (df + 0.5))
                    score += (
                        idf * frequency * (self.k1 + 1) / (frequency + normalization)
                    )

            if score > 0:
                scores.append({**document, "score": score})

        return sorted(scores, key=lambda hit: (-hit["score"], hit["chunk_id"]))[:k]
