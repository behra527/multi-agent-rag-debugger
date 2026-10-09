
from enum import Enum

from pydantic import BaseModel, Field


class IssuePriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IssueType(str, Enum):
    BUG = "bug"
    ERROR = "error"
    PERFORMANCE = "performance"
    SECURITY = "security"
    TEST_FAILURE = "test_failure"
    UNKNOWN = "unknown"


class IssueRequest(BaseModel):
    """Incoming software issue submitted by the user."""

    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    repository_path: str = Field(min_length=1)


class IssueAnalysis(BaseModel):
    """Structured output from the Issue Analyzer."""

    issue_type: IssueType
    priority: IssuePriority
    summary: str = Field(min_length=1)
    affected_components: list[str] = Field(default_factory=list)
    search_queries: list[str] = Field(default_factory=list)


class RetrievedDocument(BaseModel):
    """A single piece of evidence retrieved from the repository."""

    source: str = Field(min_length=1)
    content: str = Field(min_length=1)
    score: float = Field(ge=0.0)
    metadata: dict[str, str] = Field(default_factory=dict)


class Evidence(BaseModel):
    """Repository evidence used to support an agent's reasoning."""

    source: str = Field(min_length=1)
    content: str = Field(min_length=1)
    score: float = Field(ge=0.0)
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    language: str = Field(min_length=1)


class RetrievalResult(BaseModel):
    """Evidence returned by the RAG layer."""

    documents: list[RetrievedDocument] = Field(default_factory=list)
    query: str = Field(min_length=1)


class RootCauseAnalysis(BaseModel):
    """Root-cause conclusion supported by retrieved evidence."""

    root_cause: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    affected_files: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class ProposedFix(BaseModel):
    """Fix proposed by the Fix Agent."""

    summary: str = Field(min_length=1)
    affected_files: list[str] = Field(default_factory=list)
    patch: str = ""
    reasoning: str = Field(min_length=1)


class ValidationResult(BaseModel):
    """Result produced by the validation layer."""

    passed: bool
    tests_run: int = Field(ge=0)
    tests_passed: int = Field(ge=0)
    tests_failed: int = Field(ge=0)
    output: str = ""
    errors: list[str] = Field(default_factory=list)


class DebuggingReport(BaseModel):
    """Final result returned to the user."""

    issue: IssueRequest
    analysis: IssueAnalysis
    root_cause: RootCauseAnalysis
    proposed_fix: ProposedFix
    validation: ValidationResult

