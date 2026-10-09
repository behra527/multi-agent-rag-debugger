
from app.core.models import (
    Evidence,
    IssueAnalysis,
    IssueRequest,
    RootCauseAnalysis,
)
from app.llm.interface import LLMClient
from app.llm.structured import parse_json_response


ROOT_CAUSE_SYSTEM_PROMPT = """
You are a software root-cause analysis agent.

Your job is to identify the most likely root cause of a reported
software issue using the issue description, issue analysis, and
repository evidence.

Return ONLY valid JSON.

The JSON must contain exactly these fields:

{
  "root_cause": "short description of the root cause",
  "explanation": "clear technical explanation",
  "affected_files": ["file1.py", "file2.py"],
  "evidence": ["specific evidence supporting the conclusion"],
  "confidence": 0.0
}

Rules:
- Base the conclusion only on the provided information.
- Do not invent files, functions, errors, or behavior.
- Evidence must directly support the root-cause conclusion.
- Confidence must be between 0.0 and 1.0.
- If evidence is insufficient, say so clearly and use a lower confidence.
- Do not propose a fix.
- Do not include markdown.
- Do not include explanations outside the JSON.
"""


class RootCauseAgent:
    """Identifies the likely root cause of a software issue."""

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def analyze(
        self,
        issue: IssueRequest,
        analysis: IssueAnalysis,
        evidence: list[Evidence],
    ) -> RootCauseAnalysis:
        evidence_text = self._format_evidence(evidence)

        prompt = f"""
Issue title:
{issue.title}

Issue description:
{issue.description}

Issue type:
{analysis.issue_type.value}

Priority:
{analysis.priority.value}

Issue summary:
{analysis.summary}

Affected components:
{", ".join(analysis.affected_components) or "None provided"}

Repository evidence:
{evidence_text}
"""

        response = self.llm.generate(
            prompt,
            system_prompt=ROOT_CAUSE_SYSTEM_PROMPT,
        )

        return parse_json_response(
            response,
            RootCauseAnalysis,
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

