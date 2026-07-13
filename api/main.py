from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from mcp_clients.firestore_client import FirestoreMCPClient
from mcp_clients.gmail_client import GmailMCPClient
from mcp_clients.whatsapp_client import WhatsAppMCPClient
from mcp_clients.calendar_client import CalendarMCPClient
from google.adk.runners import InMemoryRunner
from google.genai import types
from agents.adk_pipeline import MODEL_NAME, adk_pipeline
import logging
import traceback

app = FastAPI(title="Lead Management Multi-Agent System API")

# Enable CORS for frontend connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For local development, allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize MCP clients
import os
use_mock_gmail = os.getenv("USE_MOCK_GMAIL", "true").lower() == "true"
firestore_client = FirestoreMCPClient()
gmail_client = GmailMCPClient(mock_mode=use_mock_gmail)
whatsapp_client = WhatsAppMCPClient(mock_mode=True)
calendar_client = CalendarMCPClient(mock_mode=True)

# Input Request Models
class CreateLeadRequest(BaseModel):
    raw_text: str = Field(description="Raw text of the incoming lead (e.g. inquiry email or form message)")
    source: str = Field(default="webform", description="Source of the lead (webform, email, whatsapp)")

class UpdateLeadRequest(BaseModel):
    extracted_data: Optional[Dict[str, str]] = None
    score: Optional[Dict[str, Any]] = None
    recommendation: Optional[Dict[str, Any]] = None
    draft: Optional[Dict[str, str]] = None

# Background ADK pipeline task runner
def run_adk_pipeline_task(lead_id: str):
    try:
        firestore_client.update_lead(
            lead_id,
            {"pipeline_status": "running"},
            "pipeline_started",
        )
        runner = InMemoryRunner(agent=adk_pipeline)
        runner.auto_create_session = True
        
        # Construct message content
        p = types.Part(text=f"Process lead {lead_id}")
        new_message = types.Content(role="user", parts=[p])
        
        # Execute the ADK SequentialAgent pipeline synchronously in this background worker
        list(runner.run(
            user_id="api_service",
            session_id=lead_id,
            new_message=new_message,
            state_delta={"lead_id": lead_id}
        ))

        lead = firestore_client.get_lead(lead_id)
        missing = []
        if not lead:
            missing.append("lead")
        else:
            if not lead.get("analysis", {}).get("source_text"):
                missing.append("analysis.source_text")
            if not lead.get("extracted_data"):
                missing.append("extracted_data")
            if not lead.get("intent"):
                missing.append("intent")
            if not lead.get("score"):
                missing.append("score")
            if not lead.get("recommendation"):
                missing.append("recommendation")
            if not lead.get("draft"):
                missing.append("draft")
        if missing:
            raise RuntimeError(f"ADK pipeline finished without required fields: {', '.join(missing)}")

        firestore_client.update_lead(
            lead_id,
            {"pipeline_status": "completed"},
            "pipeline_completed",
        )
    except Exception as e:
        logging.getLogger("api").error("Error executing ADK pipeline for %s: %s", lead_id, traceback.format_exc())
        try:
            firestore_client.update_lead(
                lead_id,
                {
                    "pipeline_status": "failed",
                    "pipeline_error": str(e),
                },
                "pipeline_failed",
            )
        except Exception:
            logging.getLogger("api").error("Failed to persist pipeline failure for %s", lead_id, exc_info=True)

@app.post("/api/leads", status_code=201)
def create_lead(request: CreateLeadRequest, background_tasks: BackgroundTasks):
    """
    Ingest a new lead.
    This creates the lead record and runs the multi-agent pipeline in the background.
    """
    # Create the initial lead record first to return immediately to the client
    lead = firestore_client.create_lead(request.raw_text, request.source)
    # Start the agent pipeline in the background
    background_tasks.add_task(run_adk_pipeline_task, lead["id"])
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

@app.get("/api/config")
def get_config():
    """
    Returns the current execution configuration mode of the ADK pipeline.
    """
    if MODEL_NAME != "mock-adk-model":
        return {
            "mode": "Live NVIDIA API ADK Mode",
            "model": MODEL_NAME,
            "is_mock": False
        }
    return {
        "mode": "Local Mock ADK Mode",
        "model": "mock-adk-model",
        "is_mock": True
    }
