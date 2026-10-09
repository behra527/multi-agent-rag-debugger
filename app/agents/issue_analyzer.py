from app.core.models import IssueAnalysis, IssueRequest
from app.llm.interface import LLMClient
from app.llm.structured import parse_json_response


ISSUE_ANALYZER_SYSTEM_PROMPT = """
You are a software issue analysis agent.

Analyze the developer's reported issue and return ONLY valid JSON.

The JSON must contain exactly these fields:

{
  "issue_type": "bug | error | performance | security | test_failure | unknown",
  "priority": "low | medium | high | critical",
  "summary": "short summary of the issue",
  "affected_components": ["component1", "component2"],
  "search_queries": ["query1", "query2"]
}

Do not include markdown.
Do not include explanations outside the JSON.
"""


class IssueAnalyzer:
    """Analyzes a software issue and produces structured output."""

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def analyze(self, issue: IssueRequest) -> IssueAnalysis:
        prompt = f"""
Issue title:
{issue.title}

Issue description:
{issue.description}

Repository:
{issue.repository_path}
"""

        response = self.llm.generate(
            prompt,
            system_prompt=ISSUE_ANALYZER_SYSTEM_PROMPT,
        )

        return parse_json_response(response, IssueAnalysis)