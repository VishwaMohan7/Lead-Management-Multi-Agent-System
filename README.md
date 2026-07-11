# LeadFlow AI: Lead Management Multi-Agent System

An AI-powered lead management system built for education and course businesses. The application takes incoming course inquiries (via web forms, simulated WhatsApp, or Gmail), runs them through a sequential pipeline of specialized reasoning agents (Analysis, Scoring, Recommendation, and Communication), drafts outbound messaging, and drops them into a human-approval dashboard queue before dispatching.

---

## Architecture Overview

The project adheres to a strict three-layer separation:
1. **Agents**: Orchestrated sequentially by the pipeline router. Each agent owns a specific domain of reasoning (e.g., scoring lead value). All agents communicate with the database via the shared Firestore MCP client.
2. **Skills**: Reusable, stateless functions imported by agents (e.g. Lead Extraction, Email Drafting).
3. **MCP Clients**: The sole interface between agents/skills and external platforms (Firestore, Google Calendar, Gmail, WhatsApp). 

```
   Raw Lead (Form/WhatsApp/Email)
                │
                ▼
        [ FastAPI Backend ] ◄──────────► [ React Dashboard ]
                │
                ▼
      [ Orchestrator Pipeline ]
                │
  ┌─────────────┼──────────────┬──────────────┐
  ▼             ▼              ▼              ▼
[Analysis]  [Scoring]   [Recommendation] [Communication]
  │             │              │              │
  └─────────────┼──────────────┴──────────────┤
                ▼                             ▼
       [ Firestore MCP ]               [ Other MCPs ]
      (data/leads_db.json)         (Gmail, WhatsApp, Calendar)
```

---

## Directory Structure

```text
├── agents/             # Stateful reasoning agents (Analysis, Scoring, etc.)
├── skills/             # Stateless business skills (Extraction, Drafting, etc.)
├── mcp_clients/        # Simulation clients for Firestore, Gmail, WhatsApp, Calendar
├── orchestrator/       # Thin router sequentially invoking agents and persisting state
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
4. Create a `.env` file in the root directory and configure your Nvidia Nemotron API key (retrieved from [build.nvidia.com](https://build.nvidia.com)):
   ```env
   NVIDIA_API_KEY="your-nvapi-key-here"
   NVIDIA_MODEL="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
   NVIDIA_BASE_URL="https://integrate.api.nvidia.com/v1"
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
- Leads DB File (Simulated Firestore): `data/leads_db.json`

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