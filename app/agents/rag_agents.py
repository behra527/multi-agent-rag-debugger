from __future__ import annotations

import re
from statistics import mean, pstdev

from app.domain.enums import JudgmentKind
from app.domain.schemas import (
    AgentFinding,
    PipelineConfig,
    QueryResult,
    RootCauseFinding,
    TextChunk,
)
from app.rag.bm25 import tokenize
from app.rag.text_chunker import chunk_text, chunking_stats


def _overlap(query: str, text: str) -> float:
    q = set(tokenize(query))
    t = set(tokenize(text))
    if not q:
        return 0.0
    return len(q & t) / len(q)


def analyze_retrieval(query: str, result: QueryResult) -> list[AgentFinding]:
    findings: list[AgentFinding] = []
    scores = [item.score for item in result.retrieved]
    overlaps = [_overlap(query, item.chunk.content) for item in result.retrieved]
    if not result.retrieved:
        findings.append(
            AgentFinding(
                agent="retrieval_analyst",
                title="No documents retrieved",
                description="The retriever returned zero chunks for the query.",
                severity="high",
                confidence=0.95,
                kind=JudgmentKind.MEASURED,
                stage="retrieval",
                evidence=["retrieved_count=0"],
                recommendation="Verify the knowledge base is indexed and that the query terms exist in the corpus.",
                validation_procedure="Re-run the same query after confirming chunk_count > 0.",
                metrics={"retrieved_count": 0},
            )
        )
        return findings

    avg_overlap = mean(overlaps) if overlaps else 0.0
    if avg_overlap < 0.15:
        findings.append(
            AgentFinding(
                agent="retrieval_analyst",
                title="Low query-document term overlap",
                description=(
                    "Retrieved chunks share few lexical terms with the query. "
                    "This is a measured overlap statistic, not labeled recall."
                ),
                severity="medium",
                confidence=0.7,
                kind=JudgmentKind.MEASURED,
                stage="retrieval",
                evidence=[f"mean_term_overlap={avg_overlap:.3f}"],
                recommendation="Try hybrid retrieval, query expansion, or re-chunking long documents.",
                validation_procedure="Compare lexical vs hybrid retrieval on this query and inspect overlap.",
                metrics={
                    "mean_term_overlap": round(avg_overlap, 4),
                    "retrieved_count": len(result.retrieved),
                    "score_mean": round(mean(scores), 4) if scores else 0,
                    "score_std": round(pstdev(scores), 4) if len(scores) > 1 else 0,
                },
            )
        )
    else:
        findings.append(
            AgentFinding(
                agent="retrieval_analyst",
                title="Retrieval produced ranked evidence",
                description="Chunks were retrieved and scored. Precision/recall are not reported because no ground-truth labels were supplied.",
                severity="info",
                confidence=0.9,
                kind=JudgmentKind.MEASURED,
                stage="retrieval",
                evidence=[f"retrieved_count={len(result.retrieved)}", f"mean_term_overlap={avg_overlap:.3f}"],
                metrics={
                    "mean_term_overlap": round(avg_overlap, 4),
                    "retrieved_count": len(result.retrieved),
                    "score_mean": round(mean(scores), 4),
                    "score_std": round(pstdev(scores), 4) if len(scores) > 1 else 0.0,
                    "top_k": len(result.retrieved),
                    "mode": result.retrieval_mode.value,
                },
            )
        )
    return findings


def analyze_chunking(chunks: list[TextChunk], config: PipelineConfig, query: str) -> list[AgentFinding]:
    stats = chunking_stats(chunks)
    findings: list[AgentFinding] = []
    findings.append(
        AgentFinding(
            agent="chunking_analyst",
            title="Chunk configuration profile",
            description="Statistics computed from the live index, not from a static template.",
            severity="info",
            confidence=1.0,
            kind=JudgmentKind.MEASURED,
            stage="chunking",
            evidence=[f"chunk_count={stats['chunk_count']}", f"avg_chars={stats['avg_chars']}"],
            metrics={**stats, "configured_chunk_size": config.chunk_size, "configured_overlap": config.chunk_overlap},
        )
    )
    if stats["duplicate_ratio"] > 0.25:
        findings.append(
            AgentFinding(
                agent="chunking_analyst",
                title="High duplicate chunk ratio",
                description="Many chunks have identical text, which can waste retrieval slots.",
                severity="medium",
                confidence=0.85,
                kind=JudgmentKind.MEASURED,
                stage="chunking",
                evidence=[f"duplicate_ratio={stats['duplicate_ratio']}"],
                recommendation="Reduce overlap or deduplicate near-identical windows before indexing.",
                validation_procedure="Reindex with lower overlap and compare duplicate_ratio.",
                metrics={"duplicate_ratio": stats["duplicate_ratio"]},
            )
        )
    if stats["max_chars"] > config.chunk_size * 2:
        findings.append(
            AgentFinding(
                agent="chunking_analyst",
                title="Oversized chunks present",
                description="At least one chunk is substantially larger than the configured size.",
                severity="low",
                confidence=0.8,
                kind=JudgmentKind.MEASURED,
                stage="chunking",
                evidence=[f"max_chars={stats['max_chars']}", f"chunk_size={config.chunk_size}"],
                recommendation="Inspect the splitter for documents without sentence boundaries.",
                validation_procedure="Re-run chunking on the largest source file.",
            )
        )

    # Optional alternative configuration comparison on the same query terms.
    if chunks:
        sample_source = chunks[0]
        alt_size = max(200, config.chunk_size // 2)
        alt_overlap = min(config.chunk_overlap, alt_size // 4)
        joined = " ".join(chunk.content for chunk in chunks[:40])
        alt = chunk_text(
            joined,
            knowledge_base_id=sample_source.knowledge_base_id,
            document_id="alt",
            source="alternative",
            chunk_size=alt_size,
            chunk_overlap=alt_overlap,
        )
        current_overlap = mean([_overlap(query, c.content) for c in chunks[: config.top_k]]) if chunks else 0
        alt_overlap_score = mean([_overlap(query, c.content) for c in alt[: config.top_k]]) if alt else 0
        findings.append(
            AgentFinding(
                agent="chunking_analyst",
                title="Alternative chunk size comparison",
                description=(
                    f"Compared configured size {config.chunk_size} against {alt_size} using query-term overlap "
                    "on a reconstructed sample. This is a heuristic comparison, not a full reindex benchmark."
                ),
                severity="info",
                confidence=0.45,
                kind=JudgmentKind.HEURISTIC,
                stage="chunking",
                evidence=[
                    f"current_overlap={current_overlap:.3f}",
                    f"alt_overlap={alt_overlap_score:.3f}",
                ],
                recommendation=(
                    "If the alternative overlap is higher, run a full reindex experiment before adopting it."
                ),
                validation_procedure="Create an experiment with the alternative chunk size and compare retrieval metrics.",
                metrics={
                    "current_overlap": round(current_overlap, 4),
                    "alternative_chunk_size": alt_size,
                    "alternative_overlap": round(alt_overlap_score, 4),
                },
            )
        )
    return findings


def analyze_embeddings(
    *,
    provider_name: str,
    model_name: str,
    dimension: int,
    index_dimension: int,
    result: QueryResult,
) -> list[AgentFinding]:
    findings: list[AgentFinding] = []
    if dimension != index_dimension:
        findings.append(
            AgentFinding(
                agent="embedding_analyst",
                title="Embedding dimension mismatch",
                description="The embedding model dimension does not match the FAISS index dimension.",
                severity="critical",
                confidence=1.0,
                kind=JudgmentKind.MEASURED,
                stage="embedding",
                evidence=[f"model_dim={dimension}", f"index_dim={index_dimension}"],
                recommendation="Reindex the knowledge base with the current embedding model.",
                validation_procedure="Confirm index.d equals embedder.dimension after reindex.",
            )
        )
    semantic_scores = [item.semantic_score for item in result.retrieved if item.semantic_score is not None]
    findings.append(
        AgentFinding(
            agent="embedding_analyst",
            title="Embedding configuration",
            description="Recorded the live embedding provider, model, and observed semantic scores.",
            severity="info",
            confidence=1.0,
            kind=JudgmentKind.MEASURED,
            stage="embedding",
            evidence=[f"provider={provider_name}", f"model={model_name}", f"dimension={dimension}"],
            metrics={
                "provider": provider_name,
                "model": model_name,
                "dimension": dimension,
                "index_dimension": index_dimension,
                "semantic_score_mean": round(mean(semantic_scores), 4) if semantic_scores else None,
            },
        )
    )
    if provider_name == "hash":
        findings.append(
            AgentFinding(
                agent="embedding_analyst",
                title="Hash embeddings are not semantic",
                description="The hash embedding provider is for tests/offline CI and cannot measure true semantic similarity.",
                severity="high",
                confidence=1.0,
                kind=JudgmentKind.MEASURED,
                stage="embedding",
                evidence=["embedding_provider=hash"],
                recommendation="Switch embedding_provider to local or openai for production debugging.",
                validation_procedure="Reindex with sentence-transformers and compare retrieval for the same query.",
            )
        )
    return findings


def analyze_generation(result: QueryResult) -> list[AgentFinding]:
    findings: list[AgentFinding] = []
    if result.context_truncated:
        findings.append(
            AgentFinding(
                agent="generation_analyst",
                title="Context truncated",
                description="Relevant passages may have been dropped because the assembled context exceeded the configured character budget.",
                severity="medium",
                confidence=0.9,
                kind=JudgmentKind.MEASURED,
                stage="generation",
                evidence=["context_truncated=true"],
                recommendation="Increase max context size, reduce top_k, or use smaller chunks.",
                validation_procedure="Re-run with a higher context budget and compare citations.",
            )
        )
    answer = result.answer or ""
    citation_markers = set(re.findall(r"\[(\d+)\]", answer))
    if answer and result.retrieved and not citation_markers:
        findings.append(
            AgentFinding(
                agent="generation_analyst",
                title="Answer lacks citation markers",
                description="The generated answer does not reference retrieved context with [n] markers.",
                severity="low",
                confidence=0.6,
                kind=JudgmentKind.HEURISTIC,
                stage="generation",
                evidence=["no [n] markers in answer"],
                recommendation="Tighten the system prompt or post-process citations from retrieved chunks.",
            )
        )
    if result.retrieved and answer:
        overlap = _overlap(answer, " ".join(item.chunk.content for item in result.retrieved))
        findings.append(
            AgentFinding(
                agent="generation_analyst",
                title="Context utilization",
                description="Lexical overlap between the answer and retrieved context. This does not prove correctness.",
                severity="info" if overlap >= 0.08 else "medium",
                confidence=0.55,
                kind=JudgmentKind.HEURISTIC,
                stage="generation",
                evidence=[f"answer_context_overlap={overlap:.3f}"],
                metrics={"answer_context_overlap": round(overlap, 4), "citation_markers": sorted(citation_markers)},
                recommendation="If overlap is very low, inspect whether generation ignored retrieved evidence.",
                validation_procedure="Compare the answer sentences against cited chunks.",
            )
        )
    if not result.retrieved:
        findings.append(
            AgentFinding(
                agent="generation_analyst",
                title="Generation without evidence",
                description="An answer was requested but retrieval returned no context.",
                severity="high",
                confidence=0.9,
                kind=JudgmentKind.MEASURED,
                stage="generation",
                evidence=["retrieved_count=0"],
            )
        )
    return findings


def evaluate_faithfulness(result: QueryResult, llm=None) -> list[AgentFinding]:
    findings: list[AgentFinding] = []
    answer = (result.answer or "").strip()
    if not answer:
        return findings
    context = " ".join(item.chunk.content for item in result.retrieved)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", answer) if s.strip()]
    unsupported = []
    supported = []
    for sentence in sentences:
        if _overlap(sentence, context) >= 0.2 or not tokenize(sentence):
            supported.append(sentence)
        else:
            unsupported.append(sentence)
    ratio = len(supported) / len(sentences) if sentences else 0.0
    findings.append(
        AgentFinding(
            agent="faithfulness_evaluator",
            title="Lexical claim support",
            description=(
                "Sentence-level lexical overlap against retrieved evidence. "
                "This is a heuristic, not a guarantee of factual faithfulness."
            ),
            severity="high" if ratio < 0.5 else "info",
            confidence=0.5,
            kind=JudgmentKind.HEURISTIC,
            stage="faithfulness",
            evidence=[
                f"supported_sentences={len(supported)}",
                f"unsupported_sentences={len(unsupported)}",
            ],
            metrics={
                "lexical_support_ratio": round(ratio, 4),
                "unsupported_claims": unsupported[:8],
            },
            recommendation="Inspect unsupported sentences and add missing source documents or reduce generative freedom.",
            validation_procedure="Manually verify each unsupported sentence against the cited chunks.",
        )
    )
    if llm is not None and hasattr(llm, "generate"):
        prompt = (
            "Evaluate unsupported claims in the answer given the context. "
            "Return JSON with overall_faithfulness between 0 and 1.\n\n"
            f"Answer:\n{answer}\n\nContext:\n{context[:6000]}"
        )
        try:
            text = llm.generate(prompt, system_prompt="You are a faithfulness evaluator. Do not invent evidence.")
            findings.append(
                AgentFinding(
                    agent="faithfulness_evaluator",
                    title="Model-based faithfulness judgment",
                    description="LLM judgment of answer support. This is an evaluation, not a verified fact.",
                    severity="info",
                    confidence=0.4,
                    kind=JudgmentKind.MODEL_BASED,
                    stage="faithfulness",
                    evidence=[text[:500]],
                    metrics={"raw_model_output": text[:1000]},
                )
            )
        except Exception as exc:
            findings.append(
                AgentFinding(
                    agent="faithfulness_evaluator",
                    title="Model-based faithfulness unavailable",
                    description=str(exc),
                    severity="low",
                    confidence=1.0,
                    kind=JudgmentKind.MEASURED,
                    stage="faithfulness",
                    evidence=[type(exc).__name__],
                )
            )
    return findings


def correlate_root_causes(findings: list[AgentFinding]) -> list[RootCauseFinding]:
    causes: list[RootCauseFinding] = []
    by_agent = {f.agent: f for f in findings}
    retrieval_empty = any(f.title == "No documents retrieved" for f in findings)
    low_overlap = any(f.title == "Low query-document term overlap" for f in findings)
    truncated = any(f.title == "Context truncated" for f in findings)
    hash_embeddings = any(f.title.startswith("Hash embeddings") for f in findings)
    low_util = any(
        f.agent == "generation_analyst" and (f.metrics or {}).get("answer_context_overlap", 1) < 0.08
        for f in findings
    )

    if retrieval_empty:
        causes.append(
            RootCauseFinding(
                description="The pipeline could not ground the answer because retrieval returned no chunks.",
                supporting_evidence=["retrieved_count=0"],
                confidence=0.9,
                severity="high",
                affected_stage="retrieval",
                recommended_action="Index documents and confirm the query is in-domain before diagnosing generation.",
                validation_procedure="Upload a document containing the query terms, ingest, and re-query.",
                causation="demonstrated",
            )
        )
    elif low_overlap and "chunking_analyst" in by_agent:
        causes.append(
            RootCauseFinding(
                description="Weak retrieval overlap may be related to chunk fragmentation or embedding configuration.",
                supporting_evidence=[f.title for f in findings if f.severity in {"medium", "high"}],
                confidence=0.55,
                severity="medium",
                affected_stage="retrieval",
                recommended_action="Run an experiment with alternate chunk sizes and hybrid weights.",
                validation_procedure="Compare mean term overlap before and after reindexing.",
                causation="correlation",
            )
        )
    if truncated:
        causes.append(
            RootCauseFinding(
                description="Context assembly truncated retrieved passages, which can drop supporting evidence after successful retrieval.",
                supporting_evidence=["context_truncated=true"],
                confidence=0.8,
                severity="medium",
                affected_stage="generation",
                recommended_action="Increase the context budget or retrieve fewer, more relevant chunks.",
                validation_procedure="Re-run with a higher max_context_chars and compare citations.",
                causation="demonstrated",
            )
        )
    if hash_embeddings:
        causes.append(
            RootCauseFinding(
                description="Semantic retrieval quality cannot be trusted while hash embeddings are configured.",
                supporting_evidence=["embedding_provider=hash"],
                confidence=1.0,
                severity="high",
                affected_stage="embedding",
                recommended_action="Use a real embedding model and reindex.",
                validation_procedure="Switch provider to local and reindex.",
                causation="demonstrated",
            )
        )
    if low_util and not retrieval_empty:
        causes.append(
            RootCauseFinding(
                description="Retrieval returned context, but the generated answer shares little lexical overlap with that context.",
                supporting_evidence=["low answer_context_overlap"],
                confidence=0.5,
                severity="medium",
                affected_stage="generation",
                recommended_action="Inspect the prompt and consider extracting claims against citations.",
                validation_procedure="Compare answer sentences to cited chunks.",
                causation="correlation",
            )
        )
    if not causes:
        causes.append(
            RootCauseFinding(
                description="No high-confidence failure mode was demonstrated. Remaining issues should be treated as hypotheses.",
                supporting_evidence=[f.title for f in findings[:5]],
                confidence=0.4,
                severity="info",
                affected_stage="pipeline",
                recommended_action="Add labeled evaluation queries if you need precision/recall rather than overlap heuristics.",
                validation_procedure="Run an experiment against a labeled dataset.",
                causation="hypothesis",
            )
        )
    return causes
