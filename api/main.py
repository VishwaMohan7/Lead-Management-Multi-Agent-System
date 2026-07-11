from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from mcp_clients.firestore_client import FirestoreMCPClient
from mcp_clients.gmail_client import GmailMCPClient
from mcp_clients.whatsapp_client import WhatsAppMCPClient
from mcp_clients.calendar_client import CalendarMCPClient
from utils.llm_provider import get_llm
from orchestrator.pipeline import LeadManagementOrchestrator

app = FastAPI(title="Lead Management Multi-Agent System API")

# Enable CORS for frontend connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For local development, allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize MCP clients and Orchestrator
# Shared Firestore MCP client is used throughout
firestore_client = FirestoreMCPClient(mock_mode=True)
gmail_client = GmailMCPClient(mock_mode=True)
whatsapp_client = WhatsAppMCPClient(mock_mode=True)
calendar_client = CalendarMCPClient(mock_mode=True)

# LLM provider
llm = get_llm()

# Orchestrator
orchestrator = LeadManagementOrchestrator(
    llm=llm,
    firestore_client=firestore_client,
    gmail_client=gmail_client,
    calendar_client=calendar_client
)

# Input Request Models
class CreateLeadRequest(BaseModel):
    raw_text: str = Field(description="Raw text of the incoming lead (e.g. inquiry email or form message)")
    source: str = Field(default="webform", description="Source of the lead (webform, email, whatsapp)")

class UpdateLeadRequest(BaseModel):
    extracted_data: Optional[Dict[str, str]] = None
    score: Optional[Dict[str, Any]] = None
    recommendation: Optional[Dict[str, Any]] = None
    draft: Optional[Dict[str, str]] = None

# Background pipeline task runner
def run_orchestrator_task(raw_text: str, source: str):
    try:
        orchestrator.run_pipeline(raw_text, source)
    except Exception as e:
        # Errors are caught and logged inside the orchestrator history
        pass

@app.post("/api/leads", status_code=201)
def create_lead(request: CreateLeadRequest, background_tasks: BackgroundTasks):
    """
    Ingest a new lead.
    This creates the lead record and runs the multi-agent pipeline in the background.
    """
    # Create the initial lead record first to return immediately to the client
    lead = firestore_client.create_lead(request.raw_text, request.source)
    # Start the agent pipeline in the background
    background_tasks.add_task(run_orchestrator_task, request.raw_text, request.source)
    return {
        "message": "Lead ingested. Agent pipeline started in background.",
        "lead_id": lead["id"]
    }

@app.get("/api/leads", response_model=List[Dict])
def get_leads():
    """
    Returns all leads, sorted by last update time.
    """
    return firestore_client.get_all_leads()

@app.get("/api/leads/{lead_id}")
def get_lead(lead_id: str):
    """
    Returns the details of a single lead including its state history.
    """
    lead = firestore_client.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")
    return lead

@app.put("/api/leads/{lead_id}")
def update_lead(lead_id: str, request: UpdateLeadRequest):
    """
    Updates lead fields manually (e.g., editing the drafted response before approval).
    """
    updates = {}
    if request.extracted_data is not None:
        updates["extracted_data"] = request.extracted_data
    if request.score is not None:
        updates["score"] = request.score
    if request.recommendation is not None:
        updates["recommendation"] = request.recommendation
    if request.draft is not None:
        updates["draft"] = request.draft

    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided for update.")

    lead = firestore_client.update_lead(lead_id, updates, "lead_edited_by_human")
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")
    return lead

@app.post("/api/leads/{lead_id}/approve")
def approve_lead_draft(lead_id: str):
    """
    Approve drafts and send outgoing messages via Gmail and WhatsApp MCP clients.
    """
    lead = firestore_client.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")

    draft = lead.get("draft")
    if not draft:
        raise HTTPException(status_code=400, detail="No communication drafts found for this lead.")

    if draft.get("status") == "approved":
        return {"message": "Draft already approved and sent."}

    recipient_email = lead.get("lead_email", "learner@example.com")
    email_sent = False
    whatsapp_sent = False

    # Send Email if draft content is present
    if draft.get("email_body"):
        email_sent = gmail_client.send_email(
            recipient=recipient_email,
            subject=draft.get("email_subject", "Admissions Consultation"),
            body=draft.get("email_body")
        )

    # Send WhatsApp if draft content is present
    if draft.get("whatsapp_body"):
        whatsapp_sent = whatsapp_client.send_whatsapp(
            recipient=recipient_email, # For mock, email acts as identifier or standard mock number
            body=draft.get("whatsapp_body")
        )

    # Update draft status to approved and log the send event
    firestore_client.update_lead(
        lead_id,
        {"draft": {"status": "approved"}},
        "draft_approved_and_sent"
    )

    return {
        "message": "Draft approved and communications dispatched successfully.",
        "details": {
            "email_sent": email_sent,
            "whatsapp_sent": whatsapp_sent
        }
    }

@app.post("/api/leads/{lead_id}/reject")
def reject_lead_draft(lead_id: str):
    """
    Reject draft content and set draft status to rejected.
    """
    lead = firestore_client.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")

    draft = lead.get("draft")
    if not draft:
        raise HTTPException(status_code=400, detail="No communication drafts found for this lead.")

    # Update draft status to rejected
    firestore_client.update_lead(
        lead_id,
        {"draft": {"status": "rejected"}},
        "draft_rejected_by_human"
    )

    return {"message": "Draft rejected."}
