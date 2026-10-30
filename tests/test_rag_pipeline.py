from app.domain.enums import RetrievalMode
from app.domain.schemas import PipelineConfig, TextChunk
from app.rag.document_index import PersistentDocumentIndex
from app.rag.embeddings import HashEmbeddingProvider
from app.rag.pipeline import RagPipeline


def test_hybrid_pipeline_retrieves_lexical_match(tmp_path, monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "index_dir", tmp_path)
    chunks = [
        TextChunk(
            chunk_id="1",
            document_id="d1",
            knowledge_base_id="kb",
            content="Refunds are issued within 14 days of purchase.",
            source="policy.txt",
            chunk_index=0,
            start_char=0,
            end_char=40,
        ),
        TextChunk(
            chunk_id="2",
            document_id="d2",
            knowledge_base_id="kb",
            content="The cafeteria serves vegetarian meals on Friday.",
            source="menu.txt",
            chunk_index=0,
            start_char=0,
            end_char=40,
        ),
    ]
    embedder = HashEmbeddingProvider(dimension=32)
    index = PersistentDocumentIndex("kb", 32, "ws")
    index.add(embedder.embed([c.content for c in chunks]), chunks)
    pipeline = RagPipeline(
        index=index,
        embedder=embedder,
        config=PipelineConfig(retrieval_mode=RetrievalMode.LEXICAL, generate_answer=False, top_k=1),
    )
    result = pipeline.query("refunds 14 days")
    assert result.retrieved
    assert "Refunds" in result.retrieved[0].chunk.content
    assert result.answer is None
