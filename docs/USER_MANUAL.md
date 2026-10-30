# User Manual: Multi-Agent RAG Debugger

A step-by-step operational guide for developers using the Multi-Agent RAG Debugger platform.

---

## 1. Starting the Application

### 1. Start the Backend API
In terminal 1:
```powershell
cd "D:\AI TASK\multi-agent-rag-debugger"
.\.venv\Scripts\python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000 --reload
```
Verify the API is running by checking `http://localhost:8000/api/v1/health`.

### 2. Start the React Frontend Dashboard
In terminal 2:
```powershell
cd "D:\AI TASK\multi-agent-rag-debugger\frontend"
npm run dev
```
Open `http://localhost:5173` in Google Chrome or any modern browser.

---

## 2. Navigating the Dashboard

The dashboard provides four primary tabs in the top navigation bar:
- **Dashboard**: Displays high-level metrics, active debugging session, live multi-agent execution pipeline, grounded code evidence, proposed diff, and sandbox validation test console.
- **Run History**: A searchable, filterable history of all past debugging sessions with JSON export.
- **Repo Explorer**: Directory scanner to inspect repository source files and verify exclusion rules.
- **Settings**: System configurations for active LLM providers (OpenRouter, OpenAI, Ollama, Mock), model identifiers, temperature, and tokens.

---

## 3. Creating a Debugging Session

1. Click the **"New Debug Session"** button in the top-right corner.
2. In the modal:
   - **Issue Title**: Provide a concise summary of the bug (e.g. `Calculation returns incorrect result`).
   - **Issue Description**: Enter the observed behavior, stack traces, and expected behavior.
   - **Target Repository Directory**: Enter the absolute path to the local repository (e.g. `D:\AI TASK\multi-agent-rag-debugger\data\sample_project`).
   - *(Optional)* Click **"Load Reproducible Sample Demo"** to pre-fill an instant test case.
   - **LLM Provider**: Select `Deterministic Mock (Instant / Offline Demo)` for zero-cost immediate testing, or choose `OpenRouter` / `OpenAI` if API keys are configured.
   - **Enable LangGraph**: Keep checked for stateful multi-agent execution.
3. Click **"Run Multi-Agent Pipeline"**.

---

## 4. Reviewing the Diagnosis & Patch

Once the pipeline completes:
1. **Pipeline Stepper**: Review the execution duration and status of each stage (`Issue Analysis`, `Hybrid RAG Retrieval`, `Root Cause Diagnosis`, `Patch Generation`, and `Sandbox Validation`).
2. **Issue Analysis**: View categorized type, priority, and automatically generated search queries.
3. **Root Cause Analysis**: Read the causal explanation and confidence percentage.
4. **Ranked Evidence**: Inspect the exact lines of code retrieved from the repository with similarity scores.
5. **Proposed Diff Viewer**: Examine the syntax-highlighted unified git diff patch. Click **"Copy Diff"** to copy the patch to your clipboard.
6. **Sandbox Validation Console**: Review the automated test suite results. Green indicates all tests passed inside the isolated workspace.

---

## 5. Human Approval & Merge Gate

At the top of the session view, an interactive banner displays the approval status:
- Click **"Approve Patch"** to mark the fix as accepted and ready to merge into your codebase.
- Click **"Reject"** to decline the suggested patch.
- Click the message icon to add review feedback or request a revision.
