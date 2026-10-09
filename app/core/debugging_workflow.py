
from pathlib import Path

from app.agents.fix import FixAgent
from app.agents.issue_analyzer import IssueAnalyzer
from app.agents.root_cause import RootCauseAgent
from app.core.models import Evidence
from app.core.supervisor import Supervisor, WorkflowStage
from app.core.workflow import DebuggingState
from app.rag.evidence import EvidenceRanker
from app.rag.hybrid_retriever import HybridRetriever
from app.rag.indexer import RepositoryIndexer
from app.tools.validation_service import ValidationService


class DebuggingWorkflow:
    """Coordinates the debugging workflow using a supervisor."""

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
        self.evidence_ranker = (
            evidence_ranker or EvidenceRanker()
        )

    def run(
        self,
        state: DebuggingState,
        *,
        top_k: int = 5,
        validation_command: list[str] | None = None,
        max_steps: int = 10,
    ) -> DebuggingState:
        """Run the supervised debugging workflow."""

        if max_steps <= 0:
            raise ValueError(
                "max_steps must be greater than 0."
            )

        for _ in range(max_steps):
            stage = self.supervisor.decide(state)

            if stage == WorkflowStage.ANALYZE:
                state.analysis = (
                    self.issue_analyzer.analyze(
                        state.issue
                    )
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

                state.evidence = (
                    self.evidence_ranker.rank(
                        evidence,
                        top_k=top_k,
                    )
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

            elif stage == WorkflowStage.COMPLETE:
                return state

            elif stage == WorkflowStage.FAILED:
                return state

        raise RuntimeError(
            "Debugging workflow exceeded the maximum number "
            "of allowed steps."
        )

    def _index_repository(
        self,
        repository_path: str | Path,
    ):
        """Index a repository and return its available chunks."""

        self.indexer.index(repository_path)
        return self.indexer.get_chunks()

    @staticmethod
    def _chunk_to_evidence(
        chunk,
        score: float,
    ) -> Evidence:
        return Evidence(
            source=chunk.source,
            content=chunk.content,
            score=score,
            start_line=chunk.start_line,
            end_line=chunk.end_line,
            language=chunk.language,
        )

