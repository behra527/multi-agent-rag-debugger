from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.domain.enums import JudgmentKind, RetrievalMode


class PipelineConfig(BaseModel):
    chunk_size: int = Field(default=800, ge=64, le=8000)
    chunk_overlap: int = Field(default=120, ge=0, le=2000)
    top_k: int = Field(default=5, ge=1, le=50)
    retrieval_mode: RetrievalMode = RetrievalMode.HYBRID
    keyword_weight: float = Field(default=0.4, ge=0.0, le=1.0)
    vector_weight: float = Field(default=0.6, ge=0.0, le=1.0)
    rerank: bool = False
    embedding_provider: str | None = None
    embedding_model: str | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    generate_answer: bool = True


class TextChunk(BaseModel):
    chunk_id: str
    document_id: str
    knowledge_base_id: str
    content: str
    source: str
    chunk_index: int = Field(ge=0)
    start_char: int = Field(ge=0)
    end_char: int = Field(ge=0)
    token_estimate: int = Field(ge=0, default=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievedChunk(BaseModel):
    chunk: TextChunk
    score: float
    lexical_score: float | None = None
    semantic_score: float | None = None
    rerank_score: float | None = None


class Citation(BaseModel):
    chunk_id: str
    source: str
    document_id: str
    quote: str
    score: float


class QueryResult(BaseModel):
    query: str
    answer: str | None
    citations: list[Citation]
    retrieved: list[RetrievedChunk]
    context_truncated: bool = False
    retrieval_mode: RetrievalMode
    latencies_ms: dict[str, float] = Field(default_factory=dict)
    usage: dict[str, Any] = Field(default_factory=dict)


class AgentFinding(BaseModel):
    agent: str
    title: str
    description: str
    severity: str = Field(pattern="^(info|low|medium|high|critical)$")
    confidence: float = Field(ge=0.0, le=1.0)
    kind: JudgmentKind
    stage: str
    evidence: list[str] = Field(default_factory=list)
    recommendation: str | None = None
    validation_procedure: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)


class RootCauseFinding(BaseModel):
    description: str
    supporting_evidence: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    severity: str
    affected_stage: str
    recommended_action: str
    validation_procedure: str
    causation: str = Field(default="correlation")


class DebugReport(BaseModel):
    session_id: str
    knowledge_base_id: str
    query: str
    created_at: datetime
    duration_ms: float
    executive_summary: str
    pipeline_config: PipelineConfig
    methodology: str
    measured_metrics: dict[str, Any]
    findings: list[AgentFinding]
    root_causes: list[RootCauseFinding]
    recommendations: list[str]
    remaining_uncertainties: list[str]
    usage: dict[str, Any]
    query_result: QueryResult | None = None
    agent_traces: list[dict[str, Any]] = Field(default_factory=list)
