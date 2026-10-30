from app.agents.rag_agents import analyze_retrieval, correlate_root_causes, evaluate_faithfulness
from app.domain.enums import RetrievalMode
from app.domain.schemas import QueryResult, RetrievedChunk, TextChunk


def _chunk(text: str) -> TextChunk:
    return TextChunk(
        chunk_id="c1",
        document_id="d1",
        knowledge_base_id="k1",
        content=text,
        source="doc.txt",
        chunk_index=0,
        start_char=0,
        end_char=len(text),
    )


def test_retrieval_analyst_flags_empty_results():
    result = QueryResult(
        query="refunds",
        answer=None,
        citations=[],
        retrieved=[],
        retrieval_mode=RetrievalMode.HYBRID,
    )
    findings = analyze_retrieval("refunds", result)
    assert findings[0].title == "No documents retrieved"
    assert findings[0].kind.value == "measured"


def test_faithfulness_marks_heuristic_not_fact():
    chunk = _chunk("Refunds are issued within 14 days of purchase.")
    result = QueryResult(
        query="refunds",
        answer="The moon is made of cheese.",
        citations=[],
        retrieved=[RetrievedChunk(chunk=chunk, score=0.9)],
        retrieval_mode=RetrievalMode.HYBRID,
    )
    findings = evaluate_faithfulness(result)
    assert findings
    assert findings[0].kind.value == "heuristic"


def test_root_cause_distinguishes_empty_retrieval():
    result = QueryResult(
        query="x",
        answer=None,
        citations=[],
        retrieved=[],
        retrieval_mode=RetrievalMode.LEXICAL,
    )
    causes = correlate_root_causes(analyze_retrieval("x", result))
    assert causes[0].causation == "demonstrated"
