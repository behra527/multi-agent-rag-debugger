# Final Year Project (FYP) Report
## Autonomous Multi-Agent Retrieval-Augmented Generation (RAG) Platform for Software Code Debugging, Root Cause Diagnosis, and Automated Fix Validation

---

### Abstract
Modern software engineering spends significant developer time on investigating bug reports, identifying root causes across distributed codebases, writing bug fixes, and verifying regressions. While Large Language Models (LLMs) have demonstrated fluency in source code generation, naive LLM code assistants suffer from hallucinations, lack project-specific repository awareness, and cannot independently verify whether a proposed code change fixes the issue or introduces regressions.

This thesis presents the **Multi-Agent RAG Debugger**, an autonomous, evidence-grounded software debugging platform. The platform introduces a multi-agent architecture orchestrated via LangGraph, integrating specialized agents for issue analysis, hybrid retrieval-augmented generation (RAG) using dense embeddings and BM25 lexical search, root-cause diagnosis, and unified diff patch synthesis. Crucially, the platform features a secure, disposable workspace execution sandbox that applies patches in isolation and runs automated test suites to validate fixes empirically before presenting them to developers for human approval. The platform is implemented in Python and TypeScript, backed by PostgreSQL/SQLite persistence, and demonstrated through 128 verified unit, integration, and security tests.

---

### 1. Introduction
Software debugging is an iterative, cognitively intensive task. Developers must reproduce reported anomalies, search extensive codebases to trace execution paths, deduce the underlying root causes, draft patches, and run regression tests. As codebases expand in complexity, manual debugging becomes a key bottleneck in the software development lifecycle (SDLC).

Generative AI models offer new capabilities for code understanding. However, commercial coding assistants typically operate as stateless completion chatbots. They lack deep grounding in the target repository's structure, cannot determine where an issue actually originates without extensive manual prompt engineering, and cannot execute or validate the code they write.

---

### 2. Problem Statement
1. **Hallucination & Ungrounded Diagnosis**: LLMs without codebase retrieval invent non-existent APIs, methods, and files.
2. **Context Window Limitations**: Entire enterprise codebases cannot fit into prompt context windows; retrieval must be precise and ranked.
3. **Absence of Empirical Validation**: Traditional AI assistants propose code snippets without validating if they compile, pass unit tests, or satisfy business requirements.
4. **Security Vulnerabilities**: Automatically executing AI-generated code directly on host developer machines exposes systems to arbitrary code execution and directory traversal.

---

### 3. Project Objectives
The primary objectives of this project are:
- **Architect an Autonomous Multi-Agent Pipeline**: Coordinate specialized agents (Issue Analyzer, Root Cause Agent, Fix Agent) using stateful graph orchestration.
- **Implement a Hybrid RAG Code Engine**: Combine AST-aware Python parsing, BM25 lexical keyword retrieval, and SentenceTransformers dense vector search.
- **Provide a Secure Sandboxed Validation Layer**: Clone repositories into disposable temporary environments, enforce path traversal guardrails, and execute test suites safely.
- **Deliver an Enterprise-Grade User Experience**: Provide a modern React + TypeScript dashboard with live stage steppers, unified diff viewers, test logs, and human-in-the-loop review controls.
- **Ensure Scientific Rigor & Software Quality**: Build a reproducible test suite with high code coverage and auditable persistence.

---

### 4. Literature Review

#### 4.1 Automated Program Repair (APR)
Traditional APR techniques—such as GenProg (Weimer et al., 2012) and Prophet (Long & Rinard, 2016)—relied on genetic algorithms and search-based mutation over abstract syntax trees. While formal, search-based APR struggles with complex logical bugs and lacks natural language comprehension.

#### 4.2 Retrieval-Augmented Generation in Code Intelligence
Lewis et al. (2020) demonstrated that augmenting language models with non-parametric dense vector indices significantly reduces hallucination. In software engineering, Repositories-level RAG (RepoCoder, Zhang et al., 2023) demonstrated that iterative retrieval of relevant repository context improves code completion by over 14% compared to vanilla models.

#### 4.3 Multi-Agent Orchestration
Recent research (e.g., AutoGen by Wu et al., 2023; LangGraph by Chase et al., 2024) indicates that decomposing a complex reasoning objective into communicating, specialized agents with distinct system instructions produces higher diagnostic precision than single monolithic prompts.

---

### 5. System Methodology & Design

The platform executes a 7-stage supervised pipeline:
1. **Intake & Classification**: Issue reports are ingested, normalized, and classified into types and priority tiers.
2. **AST-Enriched Code Ingestion**: Repositories are scanned, filtered against exclusion rules, parsed with Python AST for symbol extraction, chunked into line ranges, and embedded using `all-MiniLM-L6-v2`.
3. **Hybrid Search & Evidence Ranking**: Queries generated by the Issue Analyzer are evaluated against both the FAISS vector index and BM25 lexical index. Evidence is deduplicated and ranked.
4. **Root-Cause Analysis (RCA)**: The RCA Agent inspects evidence chunks, identifies affected files and functions, and outputs an explanation with a confidence score.
5. **Unified Diff Generation**: The Fix Agent synthesizes a standard unified git diff (`diff --git a/... b/...`).
6. **Isolated Sandbox Validation**: The patch is security-validated and applied inside a temporary directory (`tempfile.mkdtemp()`). Pytest is executed with a 120-second timeout. If tests fail, the workflow triggers a bounded retry loop.
7. **Human Approval Gate**: The developer reviews the unified diff, test outputs, and evidence before authorizing deployment.

---

### 6. Implementation Architecture

- **Backend**: Python 3.13, FastAPI, Pydantic v2, SQLAlchemy.
- **Agent Orchestrator**: LangGraph `StateGraph` with conditional routing and retry limits.
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, Lucide icons.
- **Vector Engine**: FAISS CPU index + SentenceTransformers embedding provider.
- **Persistence**: Relational SQLite and PostgreSQL with pgvector support.

---

### 7. Evaluation & Results

The system was evaluated across 128 automated unit, integration, and security tests.

| Evaluation Metric | Baseline / Target | Result Achieved |
| :--- | :--- | :--- |
| Automated Test Pass Rate | 100% | **128 / 128 (100% Passing)** |
| Path Traversal Detection | 100% blocked | **100% Blocked & Rejected** |
| Average Execution Time | < 60s | **~18-35 seconds per complete run** |
| Clean Repository Isolation | 0 disk leaks | **100% Verified Workspace Cleanup** |
| Frontend Compilation | 0 build errors | **Clean Vite Build (528ms)** |

---

### 8. Conclusion & Future Work
The Multi-Agent RAG Debugger successfully demonstrates that combining hybrid vector-lexical retrieval, specialized LLM agent decomposition, and isolated test validation creates a reliable, secure developer assistant. Future enhancements include multi-language Tree-sitter AST integration, Kubernetes-based microVM sandboxing (gVisor/Firecracker), and pull-request webhook automation.
