from __future__ import annotations

import math
import re

from app.domain.schemas import TextChunk

_TOKEN = re.compile(r"[a-z0-9_]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


class BM25Index:
    """In-memory BM25Okapi over text chunks."""

    def __init__(self, chunks: list[TextChunk], k1: float = 1.5, b: float = 0.75) -> None:
        self.chunks = chunks
        self.k1 = k1
        self.b = b
        self._docs = [tokenize(chunk.content) for chunk in chunks]
        self._avgdl = sum(len(doc) for doc in self._docs) / len(self._docs) if self._docs else 0.0
        self._df: dict[str, int] = {}
        for doc in self._docs:
            for term in set(doc):
                self._df[term] = self._df.get(term, 0) + 1

    def search(self, query: str, top_k: int = 5) -> list[tuple[TextChunk, float]]:
        if not query.strip() or not self.chunks:
            return []
        q_terms = tokenize(query)
        if not q_terms:
            return []
        n = len(self.chunks)
        scored: list[tuple[TextChunk, float]] = []
        for chunk, doc in zip(self.chunks, self._docs):
            if not doc:
                continue
            score = 0.0
            tf_map: dict[str, int] = {}
            for term in doc:
                tf_map[term] = tf_map.get(term, 0) + 1
            dl = len(doc)
            for term in q_terms:
                tf = tf_map.get(term, 0)
                if tf == 0:
                    continue
                df = self._df.get(term, 0)
                idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
                denom = tf + self.k1 * (1 - self.b + self.b * dl / (self._avgdl or 1))
                score += idf * (tf * (self.k1 + 1) / denom)
            if score > 0:
                scored.append((chunk, float(score)))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:top_k]
