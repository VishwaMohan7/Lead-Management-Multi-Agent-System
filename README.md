# LeadFlow AI: Lead Management Multi-Agent System

An AI-powered lead management system built for education and course businesses. The application takes incoming course inquiries from WhatsApp, Gmail, or a form, processes them through a Google ADK multi-agent workflow powered by one shared LLM, stores the result in Firestore, classifies the lead as HOT/WARM/COLD, explains the reason, recommends the next step, and drafts the follow-up email and WhatsApp reply for human approval.

---

## Architecture Overview

The project now uses an ADK-first design:
1. **One ADK SequentialAgent workflow** coordinates specialized sub-agents for source intake, analysis, scoring, recommendation, and communication drafting.
2. **One shared LLM** powers every ADK sub-agent through the same model setting.
3. **Firestore** is the primary storage layer, with a local JSON fallback for offline development and tests.
4. **FastAPI** keeps the dashboard endpoints stable while the ADK workflow updates each lead record.

```
   Raw Lead (Form/WhatsApp/Email)
                │
                ▼
        [ FastAPI Backend ] ◄──────────► [ React Dashboard ]
                │
                ▼
     [ Google ADK Sequential Workflow ]
                │
  ┌─────────────┼──────────────┬──────────────┬──────────────┐
  ▼             ▼              ▼              ▼              ▼
[Source]   [Analysis]      [Scoring]   [Recommendation] [Drafting]
  │             │              │              │              │
  └─────────────┴──────────────┴──────────────┴──────────────┘
                        │
                        ▼
                 [ Firestore ]
                        │
                        ├──────────► [ Gmail ]
                        └──────────► [ WhatsApp ]
```

---

## Directory Structure

```text
├── agents/             # ADK workflow and specialized sub-agent definitions
├── skills/             # Reusable business logic helpers
├── mcp_clients/        # Firestore/Gmail/WhatsApp/Calendar client wrappers
├── orchestrator/       # Legacy sequential pipeline kept for compatibility/tests
├── api/                # FastAPI backend endpoints serving lead intake and dashboard UI
├── frontend/           # Vite + React dark-themed glassmorphism dashboard portal
├── tests/              # Pytest unit and integration test scripts
└── utils/              # Swappable LLM configuration helpers (Nvidia Nemotron)
```

---

## Prerequisites

- **Python**: 3.10.11 or higher
- **Node.js**: v24 or higher
- **npm**: 11 or higher

---

## Installation & Setup

### 1. Backend Setup
1. Clone the repository and navigate to the project directory.
2. Create and activate a Python virtual environment:
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```
3. Install backend packages:
   ```powershell
   pip install -r requirements.txt
   ```
4. Create a `.env` file in the root directory and configure your model and Firestore credentials:
   ```env
   NVIDIA_API_KEY="your-nvapi-key-here"
   NVIDIA_MODEL="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
   NVIDIA_BASE_URL="https://integrate.api.nvidia.com/v1"
   FIRESTORE_PROJECT_ID="your-gcp-project-id"
   GOOGLE_APPLICATION_CREDENTIALS="C:\\path\\to\\service-account.json"
   ```

### 2. Frontend Setup
1. Navigate to the `frontend/` directory.
2. Install npm modules:
   ```powershell
   cd frontend
   npm install
   ```

---

## Running the Application

Ensure your virtual environment is active, then launch both services:

### 1. Launch FastAPI Backend
From the root workspace directory, run:
```powershell
.venv\Scripts\uvicorn api.main:app --reload
```
- API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Firestore storage: real Firestore when credentials are present, otherwise `data/leads_db.json`

### 2. Launch React Frontend
Open a new terminal shell, navigate to `frontend/`, and run:
```powershell
cd frontend
npm run dev
```
- React Dashboard URL: [http://localhost:5173](http://localhost:5173)

---

## Running Tests

We use `pytest` for unit and integration testing. Run tests locally from the root folder:
```powershell
# Run the test suite
.venv\Scripts\pytest -v tests/
```

---

## Step-by-Step Dashboard Walkthrough

1. Open **[http://localhost:5173](http://localhost:5173)** in your browser.
2. Click **Add Incoming Lead** at the top right of the dashboard.
3. Choose your simulation channel:
   - **Website Form Inquiry** or **WhatsApp Message**: Paste a raw inquiry in the text box (e.g. *"I want to enroll in the AI course next month, budget is $1500"*).
   - **Email Message**: Choose one of the preset mock emails in the dropdown (which invokes the Gmail MCP simulation to pull the content).
4. Click **Run Agents Pipeline**.
5. Once the pipeline completes in the background (usually a few seconds), select the lead from the queue list to inspect the AI extraction properties, scoring reasoning (HOT/WARM/COLD), Google Calendar scheduling actions, and outbound message draft editors.
6. Edit any draft templates or recommended details, then click **Approve & Dispatch Outreach** to trigger the final Gmail and WhatsApp client mock deliveries (you can watch the delivery payloads log out in the backend terminal process).
