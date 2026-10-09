from app.core.models import Evidence
from app.rag.evidence import EvidenceRanker


def make_evidence(
    source: str,
    content: str,
    score: float,
    start_line: int = 1,
    end_line: int = 10,
) -> Evidence:
    return Evidence(
        source=source,
        content=content,
        score=score,
        start_line=start_line,
        end_line=end_line,
        language="python",
    )


def test_evidence_ranker_deduplicates_evidence():
    evidence = [
        make_evidence(
            source="auth.py",
            content="login authentication error",
            score=0.8,
        ),
        make_evidence(
            source="auth.py",
            content="login authentication error",
            score=0.6,
        ),
        make_evidence(
            source="database.py",
            content="database connection",
            score=0.7,
        ),
    ]

    ranker = EvidenceRanker()

    results = ranker.rank(evidence)

    assert len(results) == 2


def test_evidence_ranker_keeps_highest_duplicate_score():
    evidence = [
        make_evidence(
            source="auth.py",
            content="login authentication error",
            score=0.6,
        ),
        make_evidence(
            source="auth.py",
            content="login authentication error",
            score=0.9,
        ),
    ]

    ranker = EvidenceRanker()

    results = ranker.rank(evidence)

    assert len(results) == 1
    assert results[0].score == 0.9


def test_evidence_ranker_sorts_by_score():
    evidence = [
        make_evidence(
            source="database.py",
            content="database connection",
            score=0.5,
        ),
        make_evidence(
            source="auth.py",
            content="authentication failure",
            score=0.9,
        ),
        make_evidence(
            source="service.py",
            content="service error",
            score=0.7,
        ),
    ]

    ranker = EvidenceRanker()

    results = ranker.rank(evidence)

    assert [item.score for item in results] == [
        0.9,
        0.7,
        0.5,
    ]


def test_evidence_ranker_respects_top_k():
    evidence = [
        make_evidence(
            source="auth.py",
            content="authentication",
            score=0.9,
        ),
        make_evidence(
            source="service.py",
            content="service",
            score=0.8,
        ),
        make_evidence(
            source="database.py",
            content="database",
            score=0.7,
        ),
    ]

    ranker = EvidenceRanker()

    results = ranker.rank(
        evidence,
        top_k=2,
    )

    assert len(results) == 2
    assert results[0].score == 0.9
    assert results[1].score == 0.8


def test_evidence_ranker_returns_empty_for_empty_input():
    ranker = EvidenceRanker()

    results = ranker.rank([])

    assert results == []


def test_evidence_ranker_rejects_invalid_top_k():
    ranker = EvidenceRanker()

    try:
        ranker.rank(
            [],
            top_k=0,
        )
    except ValueError as exc:
        assert "top_k must be greater than 0" in str(exc)
    else:
        raise AssertionError(
            "Expected ValueError."
        )