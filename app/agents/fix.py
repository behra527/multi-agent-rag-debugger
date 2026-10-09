
from app.core.models import (
    Evidence,
    IssueRequest,
    ProposedFix,
    RootCauseAnalysis,
)
from app.llm.interface import LLMClient
from app.llm.structured import parse_json_response


FIX_AGENT_SYSTEM_PROMPT = """
You are a software fix generation agent.

Your job is to propose a minimal and technically justified code fix
for the identified root cause.

Use only the provided issue, root-cause analysis, and repository
evidence.

Return ONLY valid JSON.

The JSON must contain exactly these fields:

{
  "summary": "short description of the proposed fix",
  "affected_files": ["file1.py"],
  "patch": "unified diff patch",
  "reasoning": "technical explanation of why this fix addresses the root cause"
}

Rules:
- Do not invent files or code that are not supported by the evidence.
- Make the smallest reasonable change.
- Preserve existing behavior unless the root cause requires a change.
- The patch must be a unified diff.
- Do not execute or apply the patch.
- Do not claim that the fix has been validated.
- Do not include markdown outside the JSON.
"""


class FixAgent:
    """Generates a proposed code fix from root-cause evidence."""

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def generate_fix(
        self,
        issue: IssueRequest,
        root_cause: RootCauseAnalysis,
        evidence: list[Evidence],
    ) -> ProposedFix:
        evidence_text = self._format_evidence(evidence)

        prompt = f"""
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

        response = self.llm.generate(
            prompt,
            system_prompt=FIX_AGENT_SYSTEM_PROMPT,
        )

        return parse_json_response(
            response,
            ProposedFix,
        )

    @staticmethod
    def _format_evidence(
        evidence: list[Evidence],
    ) -> str:
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

