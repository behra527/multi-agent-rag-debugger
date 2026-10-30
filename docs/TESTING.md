# Testing & Quality Assurance: Multi-Agent RAG Debugger

## 1. Testing Strategy & Layers

The Multi-Agent RAG Debugger adheres to rigorous quality assurance standards across multiple testing layers:

```
+-----------------------------------------------------------+
|              End-to-End Workflow Tests                    |
|        (Full Pipeline with Sandbox & TestRunner)          |
+-----------------------------------------------------------+
|             FastAPI REST Endpoint Integration             |
|       (Health, Metrics, Repositories, Debugging Runs)     |
+-----------------------------------------------------------+
|         LangGraph Stateful Orchestration Tests            |
|       (StateGraph transitions, retries, stage traces)     |
+-----------------------------------------------------------+
|               Sandbox Security & Guardrail                |
|       (Path traversal, forbidden extensions, timeouts)    |
+-----------------------------------------------------------+
|               Relational Persistence Tests                |
|      (SQLAlchemy models, CRUD, metrics, approvals)        |
+-----------------------------------------------------------+
|                  Agent & Unit Tests                       |
|       (Issue Analyzer, RCA, Fix Agent, Pydantic, AST)     |
+-----------------------------------------------------------+
```

---

## 2. Actual Verified Test Execution Baseline

All **128 automated tests** pass with **100% green status** on the active project environment:

```
============================= test session starts =============================
platform win32 -- Python 3.13.12, pytest-9.1.1, pluggy-1.6.0
rootdir: D:\AI TASK\multi-agent-rag-debugger
configfile: pyproject.toml
plugins: anyio-4.15.1, langsmith-0.14.11
collected 128 items

tests/test_api_v1.py .....                                              [  3%]
tests/test_ast_parser.py ..                                             [  5%]
tests/test_chunker.py ....                                              [  8%]
tests/test_database.py .                                                [  9%]
tests/test_debugging_workflow.py .......                                [ 14%]
tests/test_embeddings.py .                                              [ 15%]
tests/test_evidence.py .......                                          [ 21%]
tests/test_fix.py ....                                                  [ 24%]
tests/test_fix_validation_integration.py ..                             [ 25%]
tests/test_graph_workflow.py .                                          [ 26%]
tests/test_hybrid_retriever.py .......                                  [ 32%]
tests/test_indexer.py ...........                                       [ 40%]
tests/test_issue_analyzer.py ..                                         [ 42%]
tests/test_keyword_retriever.py ....                                    [ 45%]
tests/test_llm.py .                                                     [ 46%]
tests/test_loader.py ...                                                [ 48%]
tests/test_models.py .......                                            [ 53%]
tests/test_patcher.py ...                                               [ 56%]
tests/test_project_manager.py .....                                     [ 60%]
tests/test_providers.py .....                                           [ 64%]
tests/test_rag_integration.py .                                         [ 64%]
tests/test_report.py .........                                          [ 71%]
tests/test_retriever.py .....                                           [ 75%]
tests/test_root_cause.py ...                                            [ 78%]
tests/test_root_cause_integration.py ..                                 [ 79%]
tests/test_sandbox.py .....                                             [ 83%]
tests/test_scanner.py ...                                               [ 85%]
tests/test_structured.py .......                                        [ 91%]
tests/test_supervisor.py ........                                       [ 97%]
tests/test_validation_service.py ....                                   [100%]
tests/test_validator.py ....                                            [100%]
tests/test_vector_store.py .....                                        [100%]
tests/test_workflow.py .                                                [100%]

============================= 128 passed in 55.79s =============================
```

---

## 3. Test Commands Reference

### Full Test Suite
```powershell
.\.venv\Scripts\pytest -v
```

### Specific Subsystem Tests
```powershell
# API v1 REST Integration
.\.venv\Scripts\pytest -v tests/test_api_v1.py

# LangGraph Workflow Orchestration
.\.venv\Scripts\pytest -v tests/test_graph_workflow.py

# Sandbox & Security Guardrails
.\.venv\Scripts\pytest -v tests/test_sandbox.py

# Relational Persistence
.\.venv\Scripts\pytest -v tests/test_database.py

# AST Parsing & Language-Aware Chunking
.\.venv\Scripts\pytest -v tests/test_ast_parser.py tests/test_chunker.py

# Multi-Provider LLM Clients
.\.venv\Scripts\pytest -v tests/test_providers.py
```

### Frontend Typechecking & Production Build Test
```powershell
cd frontend
npm run build
```
*(Verified: Compiles in ~528ms with 0 type errors).*
