from __future__ import annotations

import re
import uuid

from app.domain.schemas import TextChunk


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def estimate_tokens(text: str) -> int:
    return max(1, len(text.split()))


def chunk_text(
    text: str,
    *,
    knowledge_base_id: str,
    document_id: str,
    source: str,
    chunk_size: int = 800,
    chunk_overlap: int = 120,
    metadata: dict | None = None,
) -> list[TextChunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0.")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap must not be negative.")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size.")

    normalized = text.strip()
    if not normalized:
        return []

    windows = _split_with_overlap(normalized, chunk_size, chunk_overlap)
    chunks: list[TextChunk] = []
    meta = metadata or {}

    for index, (start, end, content) in enumerate(windows):
        chunks.append(
            TextChunk(
                chunk_id=str(uuid.uuid4()),
                document_id=document_id,
                knowledge_base_id=knowledge_base_id,
                content=content,
                source=source,
                chunk_index=index,
                start_char=start,
                end_char=end,
                token_estimate=estimate_tokens(content),
                metadata=dict(meta),
            )
        )
    return chunks


def _split_with_overlap(text: str, chunk_size: int, overlap: int) -> list[tuple[int, int, str]]:
    sentences = _SENTENCE_SPLIT.split(text)
    if len(sentences) == 1 and len(text) <= chunk_size:
        return [(0, len(text), text)]

    pieces: list[tuple[int, int, str]] = []
    cursor = 0
    buffer = ""
    buffer_start = 0

    def flush(end_pos: int) -> None:
        content = buffer.strip()
        if content:
            pieces.append((buffer_start, end_pos, content))

    for sentence in sentences:
        if not sentence:
            continue
        # Locate sentence in remaining text for character offsets.
        found = text.find(sentence, cursor)
        if found < 0:
            found = cursor
        candidate = sentence if not buffer else f"{buffer} {sentence}"
        if len(candidate) <= chunk_size:
            if not buffer:
                buffer_start = found
            buffer = candidate
            cursor = found + len(sentence)
            continue

        if buffer:
            flush(found)
            overlap_start = max(buffer_start, found - overlap)
            buffer = text[overlap_start:found + len(sentence)].strip()
            buffer_start = overlap_start
            cursor = found + len(sentence)
        else:
            # Hard-split oversized sentence.
            start = found
            while start < found + len(sentence):
                end = min(start + chunk_size, found + len(sentence))
                pieces.append((start, end, text[start:end].strip()))
                if end >= found + len(sentence):
                    break
                start = max(start + 1, end - overlap)
            buffer = ""
            cursor = found + len(sentence)

    if buffer:
        flush(len(text))

    if not pieces:
        step = max(1, chunk_size - overlap)
        for start in range(0, len(text), step):
            end = min(len(text), start + chunk_size)
            content = text[start:end].strip()
            if content:
                pieces.append((start, end, content))
            if end >= len(text):
                break
    return pieces


def chunking_stats(chunks: list[TextChunk]) -> dict:
    if not chunks:
        return {
            "chunk_count": 0,
            "avg_chars": 0.0,
            "min_chars": 0,
            "max_chars": 0,
            "duplicate_ratio": 0.0,
            "avg_tokens": 0.0,
        }
    lengths = [len(c.content) for c in chunks]
    tokens = [c.token_estimate for c in chunks]
    unique = len({c.content for c in chunks})
    return {
        "chunk_count": len(chunks),
        "avg_chars": round(sum(lengths) / len(lengths), 2),
        "min_chars": min(lengths),
        "max_chars": max(lengths),
        "duplicate_ratio": round(1 - (unique / len(chunks)), 4),
        "avg_tokens": round(sum(tokens) / len(tokens), 2),
    }
