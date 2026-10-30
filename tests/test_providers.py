import pytest

from app.core.config import settings
from app.llm.factory import get_llm_client
from app.llm.mock_provider import MockLLMClient
from app.llm.ollama_provider import OllamaClient
from app.llm.openai_provider import OpenAIClient


def test_mock_llm_client_returns_valid_agent_structures():
    client = MockLLMClient()

    # Issue analysis detection
    issue_resp = client.generate("Analyze this issue and return search_queries and affected_components")
    assert "issue_type" in issue_resp
    assert "search_queries" in issue_resp

    # Root cause detection
    rca_resp = client.generate("Identify the root cause and causal chain from evidence")
    assert "root_cause" in rca_resp
    assert "confidence" in rca_resp

    # Fix generation without repository evidence must not invent a patch
    fix_resp = client.generate("Generate a unified diff patch to fix the defect")
    assert "patch" in fix_resp
    assert "--- a/README.md" not in fix_resp
    assert "No code modifications possible" in fix_resp or '"patch": ""' in fix_resp


def test_mock_fix_rewrites_missing_greeter_import():
    client = MockLLMClient()
    prompt = """
Issue title:
ModuleNotFoundError: No module named greeter

Issue description:
app.py imports greeter but greeting.py defines greet.

Evidence 1:
Source: app.py
Lines: 1-8
Content:
from greeter import greet
"""
    response = client.generate(prompt, system_prompt="You are a software fix generation agent.")
    assert "from greeting import greet" in response
    assert "from greeter import greet" in response
    assert "# Fixed:" not in response


def test_mock_llm_client_canned_responses():
    client = MockLLMClient(canned_responses=['{"custom": "value"}'])
    resp = client.generate("any prompt")
    assert resp == '{"custom": "value"}'


def test_openai_client_requires_api_key(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "")
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        OpenAIClient(api_key="")


def test_ollama_client_initialization():
    client = OllamaClient(base_url="http://localhost:11434/v1", model="test-model")
    assert client.model == "test-model"
    assert client.base_url == "http://localhost:11434/v1"


def test_get_llm_client_factory(monkeypatch):
    mock = get_llm_client("mock")
    assert isinstance(mock, MockLLMClient)

    monkeypatch.setattr(settings, "openai_api_key", "sk-fake-test-key")
    openai_client = get_llm_client("openai")
    assert isinstance(openai_client, OpenAIClient)
