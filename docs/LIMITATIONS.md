# Known Limitations & Engineering Boundaries

This document provides a factual accounting of the platform's current design limitations, environment requirements, and deliberate architectural boundaries.

---

## 1. Sandbox Isolation Level
- **Current Mode**: Host process execution in disposable cloned directory workspaces (`tempfile.mkdtemp`).
- **Filesystem Safety**: Original repository code is protected from mutation. Patches are validated and tested strictly inside disposable clones.
- **Limitation**: Without Docker / containerd running on the host, CPU time and memory are bounded by subprocess timeouts (`sandbox_timeout_seconds`), but kernel namespaces and seccomp syscall filtering are not active. Untrusted code should not be executed without containerized isolation in multi-tenant cloud environments.

## 2. Multi-Language AST Symbol Extraction
- **Python**: Deep AST analysis is supported via the standard Python `ast` parser, extracting function, class, and method symbols with line number ranges.
- **JavaScript, TypeScript, Go, Rust, Java, C++**: Chunked using line-based windowing with configurable overlap. AST-based symbol awareness for non-Python languages requires integrating Tree-sitter grammars in future releases.

## 3. Remote Git Provider Integration
- **Local Git**: Fully functional. Can inspect branches, query HEAD commit history, create isolated fix branches, stage patch-modified files, and create commits with author provenance.
- **Remote Push & Pull Requests**: Requires user-configured SSH keys or OAuth personal access tokens. In the absence of credentials, the platform completes all local Git operations and produces the branch and diff ready for manual push or PR creation.

## 4. Test Suite Dependency
- The validation engine executes test suites detected in the target repository (e.g., `pytest`, `python -m unittest`, `npm test`, `cargo test`, `go test`).
- If a target repository has no test suite configured, the system executes patch syntax checks and reports `tests_run=0, passed=True` with a clear explanation that automated test execution was not configured. The system does not synthesize unit tests from scratch when none exist.

## 5. Offline and LLM Provider Modes
- **Mock Provider**: Fast, deterministic, and fully offline. Dynamically derives root causes and unified diffs based on retrieved repository evidence. Useful for CI/CD, demonstration, and automated test suites.
- **Production Providers (OpenRouter, OpenAI, Ollama)**: Require active API keys or local daemon execution (`ollama serve`). Rate limits, model latency, and token quotas depend on the external provider.
