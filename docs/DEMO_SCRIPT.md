# Reproducible Demonstration Script: Multi-Agent RAG Debugger

This demonstration script allows university evaluators, reviewers, and engineering teams to reproduce an end-to-end debugging workflow using the included sample repository.

---

## 1. Demo Scenario Overview

- **Target Workspace**: `data/sample_project`
- **Component**: `login.py` (authentication module)
- **Defect**: The login function incorrectly handles authentication status and returns false on valid inputs.
- **Expected Outcome**:
  1. System scans and indexes `sample_project`.
  2. Issue analyzer identifies `bug` category and generates search query `login validation`.
  3. Hybrid RAG retrieves `login.py`.
  4. Root cause agent diagnoses the invalid return logic.
  5. Fix agent generates a unified git diff patch.
  6. Sandbox executes tests and confirms tests pass.
  7. Human reviewer approves the patch on the React dashboard.

---

## 2. Step-by-Step Live Demo Execution

### Step 1: Start Services
Ensure FastAPI and the React frontend are running:
```powershell
# In terminal 1:
.\.venv\Scripts\python -m uvicorn app.api.main:app --port 8000

# In terminal 2:
cd frontend
npm run dev
```

### Step 2: Open Dashboard
Navigate to `http://localhost:5173`.
- Notice the green **"API Ready"** badge and database connection status.
- Notice the operational metrics cards displaying real historical test statistics.

### Step 3: Launch New Session
1. Click **"New Debug Session"**.
2. Click **"Load Reproducible Sample Demo"**.
   - Title: `Login authentication fails for valid users`
   - Description: `Users report that valid credentials fail authentication due to an unexpected null check exception in login.py. Expected return value should be True.`
   - Repository: `D:\AI TASK\multi-agent-rag-debugger\data\sample_project`
   - Provider: `Deterministic Mock (Instant / Offline Demo)`
3. Click **"Run Multi-Agent Pipeline"**.

### Step 4: Verify Multi-Agent Progression
Watch the pipeline execute across all stages:
- **Intake**: Validated inputs.
- **Issue Analysis**: Categorized as `BUG`, priority `HIGH`.
- **RAG Retrieval**: Retrieved code chunks with line ranges and similarity scores.
- **Root Cause**: Confidence 95% with causal explanation.
- **Patch Generation**: Unified diff displayed in green and red.
- **Sandbox Validation**: Tests executed in isolated temporary workspace; zero mutations to original repository.

### Step 5: Complete Human Approval
1. Click **"Approve Patch"** on the top approval banner.
2. Notice the status badge dynamically transitions to **"APPROVED"**.
3. View the record added to the **"Run History"** table with downloadable JSON reports.
