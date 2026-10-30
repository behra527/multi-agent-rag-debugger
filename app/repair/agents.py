from __future__ import annotations

import hashlib
from pathlib import Path

from app.agents.fix import FixAgent
from app.agents.issue_analyzer import IssueAnalyzer
from app.agents.root_cause import RootCauseAgent
from app.core.grounding import (
    DEFECT_TARGET_NOT_FOUND,
    MISSING_CODE_GUIDANCE,
    DefectTargetNotFound,
    PatchTypeMismatch,
    assert_patch_matches_nature,
    classify_issue_nature,
    retrieval_queries,
    filter_evidence_sources,
    is_source_file,
    locate_defect_targets,
    snippets_for_targets,
)
from app.core.models import Evidence, IssueRequest, ProposedFix
from app.llm.interface import LLMClient
from app.rag.evidence import EvidenceRanker
from app.rag.hybrid_retriever import HybridRetriever
from app.rag.indexer import RepositoryIndexer
from app.repair.schemas import EvidenceItem, FixProposal, InvestigationReport, VerificationReport
from app.tools.patcher import PatchApplier
from app.tools.sandbox import PatchSecurityValidator, SecurityViolationError
from app.tools.validation_service import ValidationService


def revision_for(patch: str) -> str:
    return hashlib.sha256((patch or "").encode("utf-8")).hexdigest()[:16]


def _to_items(ranked: list[Evidence]) -> list[EvidenceItem]:
    return [
        EvidenceItem(
            source=item.source,
            content=item.content,
            start_line=item.start_line,
            end_line=item.end_line,
            score=item.score,
        )
        for item in ranked
    ]


class RepositoryInvestigator:
    def __init__(
        self,
        llm: LLMClient,
        indexer: RepositoryIndexer,
        retriever: HybridRetriever,
        ranker: EvidenceRanker | None = None,
    ) -> None:
        self.analyzer = IssueAnalyzer(llm)
        self.root_cause = RootCauseAgent(llm)
        self.indexer = indexer
        self.retriever = retriever
        self.ranker = ranker or EvidenceRanker()

    def investigate(self, issue: IssueRequest, *, top_k: int = 5) -> InvestigationReport:
        analysis = self.analyzer.analyze(issue)
        nature = classify_issue_nature(issue.title, issue.description)
        queries = retrieval_queries(issue.title, issue.description, analysis.search_queries)

        targets = locate_defect_targets(
            issue.repository_path,
            title=issue.title,
            description=issue.description,
            extra_queries=queries,
        )

        self.indexer.index(issue.repository_path)
        chunks = self.indexer.get_chunks()
        evidence: list[Evidence] = []
        for query in queries or [issue.title]:
            for chunk, score in self.retriever.retrieve(query, chunks, top_k=top_k):
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
        ranked = self.ranker.rank(evidence, top_k=max(top_k, 8))
        ranked = filter_evidence_sources(
            ranked,
            nature=nature,
            allowed_files=targets.files or None,
        )

        if nature == "code" and not targets.found:
            return InvestigationReport(
                diagnosis=DEFECT_TARGET_NOT_FOUND,
                root_cause=DEFECT_TARGET_NOT_FOUND,
                explanation=MISSING_CODE_GUIDANCE,
                evidence=_to_items(ranked),
                affected_files=[],
                confidence=0.0,
                facts=[f"searched_terms={', '.join(targets.terms[:12])}"],
                hypotheses=[],
                recommended_tests=[],
                risks=[MISSING_CODE_GUIDANCE],
                target_found=False,
                issue_nature=nature,
                halt_reason=DEFECT_TARGET_NOT_FOUND,
            )

        if not ranked and targets.files:
            for rel, content, start, end in snippets_for_targets(issue.repository_path, targets.files):
                ranked.append(
                    Evidence(
                        source=rel,
                        content=content,
                        score=1.0,
                        start_line=start,
                        end_line=end,
                        language=Path(rel).suffix.lstrip(".") or "text",
                    )
                )

        rca = self.root_cause.analyze(issue=issue, analysis=analysis, evidence=ranked)
        real_files = sorted({item.source for item in ranked if is_source_file(item.source) or nature != "code"})
        claimed = [path for path in rca.affected_files if path in real_files or Path(path).name in {Path(item).name for item in real_files}]
        grounded_files = targets.files or claimed or real_files
        grounded_files = [
            path
            for path in grounded_files
            if nature != "code" or is_source_file(path)
        ]
        return InvestigationReport(
            diagnosis=analysis.summary,
            root_cause=rca.root_cause,
            explanation=rca.explanation,
            evidence=_to_items(ranked),
            affected_files=grounded_files,
            confidence=rca.confidence,
            facts=[f"{item.source}:{item.start_line}" for item in ranked]
            + [f"{symbol.path}:{symbol.name}" for symbol in targets.symbols],
            hypotheses=[],
            recommended_tests=["Run the project's existing test command in an isolated candidate."],
            risks=["LLM judgments are not proof. Verify against the retrieved files."],
            target_found=True,
            issue_nature=nature,
            halt_reason=None,
        )


class CodeRepairEngineer:
    def __init__(self, llm: LLMClient) -> None:
        self.fix_agent = FixAgent(llm)

    def propose(self, issue: IssueRequest, investigation: InvestigationReport) -> FixProposal:
        from app.core.models import RootCauseAnalysis

        nature = investigation.issue_nature or classify_issue_nature(issue.title, issue.description)
        if not investigation.target_found:
            raise DefectTargetNotFound(investigation.halt_reason or DEFECT_TARGET_NOT_FOUND)

        evidence = [
            Evidence(
                source=item.source,
                content=item.content,
                score=item.score,
                start_line=item.start_line,
                end_line=item.end_line,
                language=Path(item.source).suffix.lstrip(".") or "text",
            )
            for item in investigation.evidence
            if nature != "code" or is_source_file(item.source)
        ]
        if nature == "code" and not evidence:
            raise DefectTargetNotFound(DEFECT_TARGET_NOT_FOUND)

        rca = RootCauseAnalysis(
            root_cause=investigation.root_cause,
            explanation=investigation.explanation,
            affected_files=[path for path in investigation.affected_files if nature != "code" or is_source_file(path)],
            evidence=[item.content[:200] for item in evidence],
            confidence=investigation.confidence,
        )
        proposed: ProposedFix = self.fix_agent.generate_fix(issue=issue, root_cause=rca, evidence=evidence)
        patch = proposed.patch or ""
        assert_patch_matches_nature(patch, proposed.affected_files, nature=nature)
        source_files = [path for path in proposed.affected_files if nature != "code" or is_source_file(path)]
        return FixProposal(
            summary=proposed.summary,
            patch=patch,
            patch_revision=revision_for(patch),
            affected_files=source_files,
            reasoning=proposed.reasoning,
            regressions=["Focused tests may miss broader regressions."],
            verification_plan=investigation.recommended_tests,
            deletions=[],
        )


class QAEngineer:
    def __init__(self, validation: ValidationService, patcher: PatchApplier) -> None:
        self.validation = validation
        self.patcher = patcher

    def preflight(
        self,
        repository_path: str,
        proposal: FixProposal,
        *,
        issue_nature: str = "code",
        issue_title: str = "",
        issue_description: str = "",
    ) -> None:
        nature = issue_nature or classify_issue_nature(issue_title, issue_description)
        PatchSecurityValidator.validate_patch(proposal.patch, Path(repository_path))
        try:
            assert_patch_matches_nature(proposal.patch, proposal.affected_files, nature=nature)
        except (PatchTypeMismatch, DefectTargetNotFound) as exc:
            raise PatchTypeMismatch(str(exc)) from exc

    def verify(
        self,
        repository_path: str,
        proposal: FixProposal,
        *,
        command: list[str] | None,
        iteration: int,
        issue_nature: str = "code",
    ) -> tuple[VerificationReport, Path]:
        try:
            assert_patch_matches_nature(proposal.patch, proposal.affected_files, nature=issue_nature)
        except (PatchTypeMismatch, DefectTargetNotFound) as exc:
            report = VerificationReport(
                passed=False,
                command=command or [],
                exit_ok=False,
                output="",
                errors=[str(exc)],
                remaining_blockers=[str(exc)],
                iteration=iteration,
            )
            return report, Path(repository_path)

        workspace = self.patcher.create_workspace(repository_path)
        try:
            PatchSecurityValidator.validate_patch(proposal.patch, workspace)
            self.patcher.apply(workspace, proposal.patch)
            result = self.validation.test_runner.run(workspace, command=command)
        except (FileNotFoundError, NotADirectoryError, ValueError, RuntimeError, SecurityViolationError) as exc:
            report = VerificationReport(
                passed=False,
                command=command or [],
                exit_ok=False,
                output="",
                errors=[str(exc)],
                remaining_blockers=[str(exc)],
                iteration=iteration,
            )
            return report, workspace
        blockers = list(result.errors)
        if not result.passed:
            blockers.append("Verification did not pass. A revised patch needs renewed approval.")
        report = VerificationReport(
            passed=result.passed,
            command=command or [],
            exit_ok=result.passed,
            tests_run=result.tests_run,
            tests_passed=result.tests_passed,
            tests_failed=result.tests_failed,
            output=result.output[:20000],
            errors=result.errors,
            original_error_reproduced=None,
            remaining_blockers=blockers,
            iteration=iteration,
        )
        return report, workspace
