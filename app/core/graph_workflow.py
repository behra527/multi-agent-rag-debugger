from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.fix import FixAgent
from app.agents.issue_analyzer import IssueAnalyzer
from app.agents.root_cause import RootCauseAgent
from app.core.grounding import (
    DEFECT_TARGET_NOT_FOUND,
    DefectTargetNotFound,
    classify_issue_nature,
    retrieval_queries,
    filter_evidence_sources,
    locate_defect_targets,
    snippets_for_targets,
)
from app.core.models import (
    Evidence,
    IssueAnalysis,
    IssueRequest,
    ProposedFix,
    RootCauseAnalysis,
    StageTrace,
    ValidationResult,
    WorkflowError,
)
from app.core.workflow import DebuggingState
from app.rag.evidence import EvidenceRanker
from app.rag.hybrid_retriever import HybridRetriever
from app.rag.indexer import RepositoryIndexer
from app.tools.validation_service import ValidationService


class GraphWorkflowState(TypedDict, total=False):
    """Internal LangGraph state representation."""

    run_id: str
    issue: IssueRequest
    analysis: IssueAnalysis | None
    evidence: list[Evidence]
    root_cause: RootCauseAnalysis | None
    proposed_fix: ProposedFix | None
    validation: ValidationResult | None
    validation_attempts: int
    max_validation_attempts: int
    top_k: int
    validation_command: list[str] | None
    stage_traces: list[StageTrace]
    errors: list[WorkflowError]
    approval_status: str | None


class GraphDebuggingWorkflow:
    """LangGraph-powered stateful multi-agent debugging workflow."""

    def __init__(
        self,
        issue_analyzer: IssueAnalyzer,
        indexer: RepositoryIndexer,
        retriever: HybridRetriever,
        root_cause_agent: RootCauseAgent,
        fix_agent: FixAgent,
        validation_service: ValidationService,
        evidence_ranker: EvidenceRanker | None = None,
    ) -> None:
        self.issue_analyzer = issue_analyzer
        self.indexer = indexer
        self.retriever = retriever
        self.root_cause_agent = root_cause_agent
        self.fix_agent = fix_agent
        self.validation_service = validation_service
        self.evidence_ranker = evidence_ranker or EvidenceRanker()
        self._compiled_graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(GraphWorkflowState)

        graph.add_node("analyze", self._step_analyze)
        graph.add_node("retrieve", self._step_retrieve)
        graph.add_node("root_cause", self._step_root_cause)
        graph.add_node("generate_fix", self._step_generate_fix)
        graph.add_node("validate", self._step_validate)

        graph.add_edge(START, "analyze")
        graph.add_edge("analyze", "retrieve")
        graph.add_edge("retrieve", "root_cause")
        graph.add_edge("root_cause", "generate_fix")
        graph.add_edge("generate_fix", "validate")

        graph.add_conditional_edges(
            "validate",
            self._route_after_validation,
            {
                "retry": "generate_fix",
                "complete": END,
                "failed": END,
            },
        )

        return graph.compile()

    def _route_after_validation(self, state: GraphWorkflowState) -> str:
        validation = state.get("validation")
        if validation and validation.passed:
            return "complete"

        attempts = state.get("validation_attempts", 0)
        max_attempts = state.get("max_validation_attempts", 2)

        if attempts < max_attempts:
            return "retry"

        return "failed"

    def _record_trace(
        self,
        state: GraphWorkflowState,
        stage_name: str,
        start_time: float,
        status: str = "completed",
        error: Exception | None = None,
    ) -> None:
        duration_ms = (perf_counter() - start_time) * 1000
        traces = state.setdefault("stage_traces", [])
        trace = StageTrace(
            stage=stage_name,
            status="completed" if status == "completed" else "failed",
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            duration_ms=duration_ms,
            error_type=type(error).__name__ if error else None,
            error_message=str(error) if error else None,
        )
        traces.append(trace)

    def _step_analyze(self, state: GraphWorkflowState) -> dict[str, Any]:
        t0 = perf_counter()
        issue = state["issue"]
        try:
            analysis = self.issue_analyzer.analyze(issue)
            self._record_trace(state, "analyze", t0)
            return {"analysis": analysis}
        except Exception as exc:
            self._record_trace(state, "analyze", t0, status="failed", error=exc)
            raise

    def _step_retrieve(self, state: GraphWorkflowState) -> dict[str, Any]:
        t0 = perf_counter()
        issue = state["issue"]
        analysis = state["analysis"]
        top_k = state.get("top_k", 5)

        try:
            self.indexer.index(Path(issue.repository_path))
            chunks = self.indexer.get_chunks()
            evidence: list[Evidence] = []
            queries = retrieval_queries(
                issue.title,
                issue.description,
                analysis.search_queries if analysis else None,
            )
            nature = classify_issue_nature(issue.title, issue.description)
            targets = locate_defect_targets(
                issue.repository_path,
                title=issue.title,
                description=issue.description,
                extra_queries=queries,
            )
            if nature == "code" and not targets.found:
                raise DefectTargetNotFound(DEFECT_TARGET_NOT_FOUND)

            for query in queries or [issue.title]:
                results = self.retriever.retrieve(query, chunks, top_k=top_k)
                for chunk, score in results:
                    evidence.append(
                        Evidence(
                            source=chunk.source,
                            content=chunk.content,
                            score=max(0.0, float(score)),
                            start_line=chunk.start_line,
                            end_line=chunk.end_line,
                            language=chunk.language,
                        )
                    )

            ranked_evidence = self.evidence_ranker.rank(evidence, top_k=top_k)
            ranked_evidence = filter_evidence_sources(
                ranked_evidence,
                nature=nature,
                allowed_files=targets.files or None,
            )
            if not ranked_evidence and targets.files:
                for rel, content, start, end in snippets_for_targets(issue.repository_path, targets.files):
                    ranked_evidence.append(
                        Evidence(
                            source=rel,
                            content=content,
                            score=1.0,
                            start_line=start,
                            end_line=end,
                            language=Path(rel).suffix.lstrip(".") or "text",
                        )
                    )
            self._record_trace(state, "retrieve", t0)
            return {"evidence": ranked_evidence}
        except Exception as exc:
            self._record_trace(state, "retrieve", t0, status="failed", error=exc)
            raise

    def _step_root_cause(self, state: GraphWorkflowState) -> dict[str, Any]:
        t0 = perf_counter()
        issue = state["issue"]
        analysis = state["analysis"]
        evidence = state.get("evidence", [])

        try:
            rca = self.root_cause_agent.analyze(
                issue=issue,
                analysis=analysis,
                evidence=evidence,
            )
            self._record_trace(state, "root_cause", t0)
            return {"root_cause": rca}
        except Exception as exc:
            self._record_trace(state, "root_cause", t0, status="failed", error=exc)
            raise

    def _step_generate_fix(self, state: GraphWorkflowState) -> dict[str, Any]:
        t0 = perf_counter()
        issue = state["issue"]
        rca = state["root_cause"]
        evidence = state.get("evidence", [])

        try:
            fix = self.fix_agent.generate_fix(
                issue=issue,
                root_cause=rca,
                evidence=evidence,
            )
            self._record_trace(state, "generate_fix", t0)
            return {"proposed_fix": fix}
        except Exception as exc:
            self._record_trace(state, "generate_fix", t0, status="failed", error=exc)
            raise

    def _step_validate(self, state: GraphWorkflowState) -> dict[str, Any]:
        t0 = perf_counter()
        issue = state["issue"]
        fix = state.get("proposed_fix")
        command = state.get("validation_command")
        attempts = state.get("validation_attempts", 0) + 1

        try:
            val_result = self.validation_service.validate(
                repository_path=Path(issue.repository_path),
                proposed_fix=fix,
                command=command,
                issue=issue,
            )
            self._record_trace(state, "validate", t0)
            return {
                "validation": val_result,
                "validation_attempts": attempts,
            }
        except Exception as exc:
            self._record_trace(state, "validate", t0, status="failed", error=exc)
            raise

    def run(
        self,
        state: DebuggingState,
        *,
        top_k: int = 5,
        validation_command: list[str] | None = None,
        max_steps: int = 10,
    ) -> DebuggingState:
        """Execute the LangGraph workflow and map results back into DebuggingState."""
        initial_payload: GraphWorkflowState = {
            "run_id": state.run_id,
            "issue": state.issue,
            "analysis": state.analysis,
            "evidence": state.evidence,
            "root_cause": state.root_cause,
            "proposed_fix": state.proposed_fix,
            "validation": state.validation,
            "validation_attempts": state.validation_attempts,
            "max_validation_attempts": state.max_validation_attempts,
            "top_k": top_k,
            "validation_command": validation_command,
            "stage_traces": list(state.stage_traces),
            "errors": list(state.errors),
        }

        try:
            final_output = self._compiled_graph.invoke(initial_payload)

            state.analysis = final_output.get("analysis", state.analysis)
            state.evidence = final_output.get("evidence", state.evidence)
            state.root_cause = final_output.get("root_cause", state.root_cause)
            state.proposed_fix = final_output.get("proposed_fix", state.proposed_fix)
            state.validation = final_output.get("validation", state.validation)
            state.validation_attempts = final_output.get(
                "validation_attempts", state.validation_attempts
            )
            state.stage_traces = final_output.get(
                "stage_traces", state.stage_traces
            )
            state.errors = final_output.get("errors", state.errors)

        except Exception as exc:
            state.errors.append(
                WorkflowError(
                    stage="graph_execution",
                    error_type=type(exc).__name__,
                    message=str(exc),
                )
            )

        return state
