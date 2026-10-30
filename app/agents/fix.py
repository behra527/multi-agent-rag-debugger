
from app.core.grounding import (
    DEFECT_TARGET_NOT_FOUND,
    DefectTargetNotFound,
    PatchTypeMismatch,
    assert_patch_matches_nature,
    classify_issue_nature,
    is_source_file,
)
from app.core.models import (
    Evidence,
    IssueRequest,
    ProposedFix,
    RootCauseAnalysis,
)
from app.core.prompts import load_prompt
from app.llm.interface import LLMClient
from app.llm.structured import parse_json_response


FIX_AGENT_SYSTEM_PROMPT = load_prompt(
    "repair_engineer.md",
    """
You are a software fix generation agent.

Propose a minimal, technically justified code fix using only the
provided issue, root-cause analysis, and repository evidence.

Return ONLY one valid JSON object with exactly these fields:

{
  "summary": "Short description of the proposed fix",
  "affected_files": ["file1.py"],
  "patch": "Unified diff patch as a JSON string",
  "reasoning": "Technical explanation of why this fix addresses the root cause"
}

Requirements:
- Every field is required.
- Do not invent files, code, or facts unsupported by the evidence.
- For application-logic bugs, patch only executable source files.
- Never modify README.md, .md, .txt, or .json to fix application behavior.
- Do not include Markdown fences or explanatory text outside the JSON.
""",
)


class FixAgent:
    """Generate and validate a proposed code fix."""

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def generate_fix(
        self,
        issue: IssueRequest,
        root_cause: RootCauseAnalysis,
        evidence: list[Evidence],
    ) -> ProposedFix:
        """Generate a proposed fix, retrying once if its response is invalid."""
        prompt = self._build_prompt(
            issue=issue,
            root_cause=root_cause,
            evidence=evidence,
        )

        response = self.llm.generate(
            prompt,
            system_prompt=FIX_AGENT_SYSTEM_PROMPT,
        )

        try:
            proposed = parse_json_response(
                response,
                ProposedFix,
            )
            return self._enforce_grounding(issue, proposed)
        except DefectTargetNotFound:
            raise
        except (ValueError, PatchTypeMismatch) as first_error:
            # Retry once with explicit feedback; never bypass validation.
            retry_prompt = f"""
{prompt}

IMPORTANT: Your previous response did not pass validation.
Validation error: {first_error}

Generate the complete response again as one valid JSON object.
Include every required field:
- summary
- affected_files
- patch
- reasoning

The reasoning field must be a non-empty string.
Patch only executable source files for application-logic bugs.
Never modify README.md, .md, .txt, or .json for those bugs.
Return JSON only. Do not use Markdown fences.
"""

            retry_response = self.llm.generate(
                retry_prompt,
                system_prompt=FIX_AGENT_SYSTEM_PROMPT,
            )

            # If the retry is invalid, let the error propagate.
            proposed = parse_json_response(
                retry_response,
                ProposedFix,
            )
            return self._enforce_grounding(issue, proposed)

    @staticmethod
    def _enforce_grounding(issue: IssueRequest, proposed: ProposedFix) -> ProposedFix:
        nature = classify_issue_nature(issue.title, issue.description)
        source_evidence_files = [
            path for path in (proposed.affected_files or []) if is_source_file(path)
        ]
        if nature == "code" and not (proposed.patch or "").strip() and not source_evidence_files:
            raise DefectTargetNotFound(DEFECT_TARGET_NOT_FOUND)
        assert_patch_matches_nature(
            proposed.patch,
            proposed.affected_files,
            nature=nature,
        )
        return proposed

    @staticmethod
    def _build_prompt(
        issue: IssueRequest,
        root_cause: RootCauseAnalysis,
        evidence: list[Evidence],
    ) -> str:
        """Build the evidence-grounded prompt for fix generation."""
        evidence_text = FixAgent._format_evidence(evidence)

        return f"""
Issue title:
{issue.title}

Issue description:
{issue.description}

Root cause:
{root_cause.root_cause}

Root cause explanation:
{root_cause.explanation}

Affected files:
{", ".join(root_cause.affected_files) or "None provided"}

Root cause evidence:
{chr(10).join(root_cause.evidence) or "None provided"}

Repository evidence:
{evidence_text}
"""

    @staticmethod
    def _format_evidence(
        evidence: list[Evidence],
    ) -> str:
        """Format retrieved repository evidence for the LLM."""
        if not evidence:
            return "No repository evidence was retrieved."

        sections = []

        for index, item in enumerate(evidence, start=1):
            sections.append(
                f"""
Evidence {index}:
Source: {item.source}
Language: {item.language}
Lines: {item.start_line}-{item.end_line}
Similarity score: {item.score:.4f}

Content:
{item.content}
""".strip()
            )

        return "\n\n".join(sections)
