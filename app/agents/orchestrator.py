from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from app.agents.rag_agents import (
    analyze_chunking,
    analyze_embeddings,
    analyze_generation,
    analyze_retrieval,
    correlate_root_causes,
    evaluate_faithfulness,
)
from app.core.config import settings
from app.core.exceptions import BudgetExceeded
from app.core.telemetry import UsageStats
from app.domain.schemas import DebugReport, PipelineConfig, QueryResult
from app.rag.document_index import PersistentDocumentIndex
from app.rag.pipeline import RagPipeline


class DebugOrchestrator:
    def __init__(self, llm=None, embedder=None) -> None:
        self.llm = llm
        self.embedder = embedder

    def run(
        self,
        *,
        knowledge_base_id: str,
        workspace_id: str,
        query: str,
        config: PipelineConfig,
        index: PersistentDocumentIndex,
        embedding_provider_name: str,
        embedding_model: str,
        session_id: str | None = None,
    ) -> DebugReport:
        started = perf_counter()
        usage = UsageStats()
        if usage.llm_calls > settings.max_llm_calls_per_workflow:
            raise BudgetExceeded("LLM call budget exceeded before start.")

        pipeline = RagPipeline(
            index=index,
            embedder=self.embedder,
            config=config,
            llm=self.llm,
            usage=usage,
        )
        result: QueryResult = pipeline.query(query)
        traces: list[dict] = []
        deadline = started + settings.max_workflow_seconds

        def run_agent(name: str, fn):
            if perf_counter() > deadline:
                raise BudgetExceeded("Workflow deadline exceeded.")
            t0 = perf_counter()
            try:
                output = fn()
                traces.append(
                    {
                        "agent": name,
                        "status": "completed",
                        "duration_ms": round((perf_counter() - t0) * 1000, 3),
                    }
                )
                return output
            except BudgetExceeded:
                raise
            except Exception as exc:
                traces.append(
                    {
                        "agent": name,
                        "status": "failed",
                        "duration_ms": round((perf_counter() - t0) * 1000, 3),
                        "error": str(exc),
                    }
                )
                return []

        findings = []
        findings.extend(run_agent("retrieval_analyst", lambda: analyze_retrieval(query, result)))
        findings.extend(run_agent("chunking_analyst", lambda: analyze_chunking(index.chunks, config, query)))
        findings.extend(
            run_agent(
                "embedding_analyst",
                lambda: analyze_embeddings(
                    provider_name=embedding_provider_name,
                    model_name=embedding_model,
                    dimension=self.embedder.dimension if self.embedder else index.dimension,
                    index_dimension=index.dimension,
                    result=result,
                ),
            )
        )
        findings.extend(run_agent("generation_analyst", lambda: analyze_generation(result)))
        findings.extend(
            run_agent("faithfulness_evaluator", lambda: evaluate_faithfulness(result, llm=self.llm))
        )
        if usage.llm_calls > settings.max_llm_calls_per_workflow:
            raise BudgetExceeded("LLM call budget exceeded.")

        root_causes = correlate_root_causes(findings)
        duration_ms = round((perf_counter() - started) * 1000, 3)
        high = [f for f in findings if f.severity in {"high", "critical"}]
        summary = (
            f"Debugged query against {len(index.chunks)} chunks. "
            f"Retrieved {len(result.retrieved)} passages. "
            f"{len(high)} high-severity findings."
        )
        recommendations = []
        for cause in root_causes:
            recommendations.append(cause.recommended_action)
        for finding in findings:
            if finding.recommendation:
                recommendations.append(finding.recommendation)
        unique_recs = list(dict.fromkeys(recommendations))
        uncertainties = [
            "Precision/recall were not computed because no labeled relevant documents were provided.",
            "LLM faithfulness judgments, when present, are evaluations rather than guarantees.",
        ]
        if embedding_provider_name == "hash":
            uncertainties.append("Hash embeddings were used, so semantic scores are not meaningful.")

        return DebugReport(
            session_id=session_id or str(uuid4()),
            knowledge_base_id=knowledge_base_id,
            query=query,
            created_at=datetime.now(timezone.utc),
            duration_ms=duration_ms,
            executive_summary=summary,
            pipeline_config=config,
            methodology=(
                "Deterministic retrieval/chunk/embedding statistics plus optional model-based "
                "faithfulness. Ground-truth ranking metrics are omitted unless labels exist."
            ),
            measured_metrics={
                "retrieved_count": len(result.retrieved),
                "chunk_count": len(index.chunks),
                "context_truncated": result.context_truncated,
                "latencies_ms": result.latencies_ms,
            },
            findings=findings,
            root_causes=root_causes,
            recommendations=unique_recs,
            remaining_uncertainties=uncertainties,
            usage=usage.as_dict(),
            query_result=result,
            agent_traces=traces,
        )
