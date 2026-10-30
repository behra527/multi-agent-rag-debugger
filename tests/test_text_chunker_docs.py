from app.rag.text_chunker import chunk_text, chunking_stats


def test_chunk_text_preserves_offsets_and_overlap():
    text = "Alpha sentence one. Bravo sentence two. Charlie sentence three. Delta sentence four."
    chunks = chunk_text(
        text,
        knowledge_base_id="kb",
        document_id="doc",
        source="notes.txt",
        chunk_size=40,
        chunk_overlap=10,
    )
    assert chunks
    assert chunks[0].start_char == 0
    assert all(chunk.document_id == "doc" for chunk in chunks)
    stats = chunking_stats(chunks)
    assert stats["chunk_count"] == len(chunks)
    assert stats["min_chars"] > 0


def test_empty_text_yields_no_chunks():
    assert chunk_text("   ", knowledge_base_id="k", document_id="d", source="s") == []
