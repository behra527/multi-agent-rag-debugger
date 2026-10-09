
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from app.agents.fix import FixAgent
from app.agents.issue_analyzer import IssueAnalyzer
from app.agents.root_cause import RootCauseAgent
from app.core.models import (
    Evidence,
    StageTrace,
    WorkflowError,
)
from app.core.supervisor import Supervisor, WorkflowStage
from app.core.workflow import DebuggingState
from app.rag.chunker import DocumentChunk
from app.rag.evidence import EvidenceRanker
from app.rag.hybrid_retriever import HybridRetriever
from app.rag.indexer import RepositoryIndexer
from app.tools.validation_service import ValidationService


class DebuggingWorkflow:
    """Coordinate supervised debugging with execution tracing."""

    def __init__(
        self,
        issue_analyzer: IssueAnalyzer,
        indexer: RepositoryIndexer,
        retriever: HybridRetriever,
        root_cause_agent: RootCauseAgent,
        fix_agent: FixAgent,
        validation_service: ValidationService,
        supervisor: Supervisor,
        evidence_ranker: EvidenceRanker | None = None,
    ) -> None:
        self.issue_analyzer = issue_analyzer
        self.indexer = indexer
        self.retriever = retriever
        self.root_cause_agent = root_cause_agent
        self.fix_agent = fix_agent
        self.validation_service = validation_service
        self.supervisor = supervisor
        self.evidence_ranker = evidence_ranker or EvidenceRanker()

    def run(
        self,
        state: DebuggingState,
        *,
        top_k: int = 5,
        validation_command: list[str] | None = None,
        max_steps: int = 10,
    ) -> DebuggingState:
        """Run the workflow and record each executed stage."""

        if top_k <= 0:
            raise ValueError("top_k must be greater than 0.")

        if max_steps <= 0:
            raise ValueError("max_steps must be greater than 0.")

        for _ in range(max_steps):
            stage = self.supervisor.decide(state)

            if stage == WorkflowStage.COMPLETE:
                return state

            if stage == WorkflowStage.FAILED:
                return state

            trace = StageTrace(
                stage=stage.value,
                status="running",
            )
            state.stage_traces.append(trace)
            start_time = perf_counter()

            try:
                if stage == WorkflowStage.ANALYZE:
                    state.analysis = self.issue_analyzer.analyze(
                        state.issue
                    )

                elif stage == WorkflowStage.RETRIEVE:
                    chunks = self._index_repository(
                        state.issue.repository_path
                    )

                    evidence: list[Evidence] = []

                    for query in state.analysis.search_queries:
                        results = self.retriever.retrieve(
                            query,
                            chunks,
                            top_k=top_k,
                        )

                        for chunk, score in results:
                            evidence.append(
                                self._chunk_to_evidence(
                                    chunk,
                                    score,
                                )
                            )

                    state.evidence = self.evidence_ranker.rank(
                        evidence,
                        top_k=top_k,
                    )

                elif stage == WorkflowStage.ROOT_CAUSE:
                    state.root_cause = (
                        self.root_cause_agent.analyze(
                            issue=state.issue,
                            analysis=state.analysis,
                            evidence=state.evidence,
                        )
                    )

                elif stage == WorkflowStage.GENERATE_FIX:
                    state.proposed_fix = (
                        self.fix_agent.generate_fix(
                            issue=state.issue,
                            root_cause=state.root_cause,
                            evidence=state.evidence,
                        )
                    )

                elif stage == WorkflowStage.VALIDATE:
                    state.validation_attempts += 1

                    state.validation = (
                        self.validation_service.validate(
                            repository_path=Path(
                                state.issue.repository_path
                            ),
                            proposed_fix=state.proposed_fix,
                            command=validation_command,
                        )
                    )

                trace.status = "completed"

            except Exception as exc:
                trace.status = "failed"
                trace.error_type = type(exc).__name__
                trace.error_message = str(exc)

                state.errors.append(
                    WorkflowError(
                        stage=stage.value,
                        error_type=type(exc).__name__,
                        message=str(exc) or type(exc).__name__,
                    )
                )

                # Preserve the failure details in the state,
                # then let the caller handle the exception.
                raise

            finally:
                trace.finished_at = datetime.now(timezone.utc)
                trace.duration_ms = (
                    perf_counter() - start_time
                ) * 1000

        message = (
            "Debugging workflow exceeded the maximum number "
            "of allowed steps."
        )

        state.errors.append(
            WorkflowError(
                stage="workflow",
                error_type="MaxStepsExceeded",
                message=message,
            )
        )

        raise RuntimeError(message)

    def _index_repository(
        self,
        repository_path: str | Path,
    ) -> list[DocumentChunk]:
        """Index a repository and return its available chunks."""

        self.indexer.index(repository_path)
        return self.indexer.get_chunks()

    @staticmethod
    def _chunk_to_evidence(
        chunk: DocumentChunk,
        score: float,
    ) -> Evidence:
        """Convert a retrieved chunk into structured evidence."""

        return Evidence(
            source=chunk.source,
            content=chunk.content,
            score=score,
            start_line=chunk.start_line,
            end_line=chunk.end_line,
            language=chunk.language,
        )