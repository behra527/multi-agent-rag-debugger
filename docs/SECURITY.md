# Security & Threat Model: Multi-Agent RAG Debugger

## 1. Security Architecture Principles

In an autonomous debugging platform that analyzes repositories, generates patches, and runs test commands, security is a first-class architectural requirement:

1. **Untrusted Code Execution Boundary**: Code generated or modified by LLMs is treated as untrusted. It is never executed directly on the host repository.
2. **Strict Filesystem Boundaries**: Patches are strictly validated to prevent directory traversal and unauthorized modification of system or credential files.
3. **Disposable Workspace Isolation**: All testing and patching occurs in temporary workspaces (`tempfile.mkdtemp()`) with explicit lifecycle cleanup.
4. **Separation of Approval from Execution**: Patches are proposed and validated, but never automatically pushed, merged, or deployed without explicit human authorization.
5. **Least Privilege & Secret Protection**: Sensitive files (`.env`, `.git`, SSH keys) are excluded from RAG ingestion and modification.

---

## 2. Threat Modeling & Mitigations

### Threat 1: Malicious Unified Diff Path Traversal
- **Attack Scenario**: A prompt-injection attack or manipulated LLM response proposes a patch target such as `+++ b/../../etc/passwd` or `+++ b/C:\Windows\System32\cmd.exe`.
- **Mitigation**: `PatchSecurityValidator.validate_patch` checks every file header:
  - Rejects paths containing `..` or leading `/`, `\`.
  - Resolves target paths against the workspace root and verifies that `resolved_path.startswith(workspace_root)`.
  - Rejects attempts modifying sensitive names (`.env`, `id_rsa`, `passwd`) or executable scripts (`.exe`, `.sh`, `.bat`, `.ps1`).

### Threat 2: Host Repository Corruption
- **Attack Scenario**: Patch application damages existing repository files or leaves incomplete changes in user working trees.
- **Mitigation**: `WorkspaceSandbox` clones the repository into a separate temporary directory. The original repository is accessed in read-only mode. If validation fails or completes, the disposable workspace is deleted. The original repository remains completely pristine.

### Threat 3: Denial-of-Service via Infinite Loops / Resource Exhaustion
- **Attack Scenario**: Generated patch introduces an infinite loop in tests (e.g. `while True: pass`).
- **Mitigation**: `TestRunner` enforces a strict 120-second timeout (`subprocess.run(timeout=120)`). When exceeded, the process tree is terminated immediately and marked as a validation timeout failure.

### Threat 4: Prompt Injection via Repository Files or Comments
- **Attack Scenario**: Malicious code comments attempt to hijack LLM system prompts (`"IGNORE ALL PREVIOUS INSTRUCTIONS AND..."`).
- **Mitigation**: Retrieved code is strictly passed inside explicit user message content, isolated from the immutable agent system prompt. Outputs are enforced via strict Pydantic JSON schema validators (`parse_json_response`). Any response failing schema validation is rejected.

### Threat 5: Secret and Credential Ingestion
- **Attack Scenario**: API keys, database passwords, or private keys inside `.env` or credentials files are loaded into vector embeddings.
- **Mitigation**: `RepositoryScanner` and `WorkspaceSandbox` ignore patterns explicitly disallow `.env*`, `.git`, `*.key`, `id_rsa`, and common secret files.

---

## 3. Human Approval Gate
The platform implements an explicit Human-in-the-Loop (HITL) gate:
- Even when automated tests pass with 100% success rate, the patch status is set to `validated`, not `applied`.
- The developer must review the unified diff, inspect test logs, and click **Approve** before changes can be exported or committed.
