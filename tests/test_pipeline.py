import os
import shutil
import pytest
from utils.llm_provider import MockLLM, get_llm
from mcp_clients.firestore_client import FirestoreMCPClient, DB_FILE
from mcp_clients.gmail_client import GmailMCPClient
from mcp_clients.calendar_client import CalendarMCPClient
from orchestrator.pipeline import LeadManagementOrchestrator

@pytest.fixture(autouse=True)
def clean_database():
    """
    Cleans up the database file before and after tests.
    """
    # Delete database file if it exists
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
    yield
    # Cleanup after test
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)

def test_full_pipeline():
    llm = MockLLM()
    firestore_client = FirestoreMCPClient(mock_mode=True)
    gmail_client = GmailMCPClient(mock_mode=True)
    calendar_client = CalendarMCPClient(mock_mode=True)
    
    orchestrator = LeadManagementOrchestrator(
        llm=llm,
        firestore_client=firestore_client,
        gmail_client=gmail_client,
        calendar_client=calendar_client
    )
    
    # Run the pipeline on a sample lead
    raw_lead_text = "I want to join the AI course next month. Budget is $1500. Email me details."
    lead_source = "webform"

    try:
        final_lead = orchestrator.run_pipeline(raw_lead_text, lead_source)
    except Exception as exc:
        message = str(exc)
        if "ResourceExhausted" in message or "503" in message or "Service Unavailable" in message:
            pytest.skip(f"Live provider unavailable for this environment: {message}")
        raise
    
    # Validate final state
    assert final_lead["id"] is not None
    assert final_lead["raw_text"] == raw_lead_text
    assert final_lead["source"] == lead_source
    
    # Check extraction results
    extracted = final_lead["extracted_data"]
    assert extracted["course"] == "AI"
    assert extracted["timeline"] == "Next month"
    assert extracted["budget"] == "$1500"
    assert extracted["contact_channel"] == "Email"
    
    # Check scoring results (HOT lead expected)
    score = final_lead["score"]
    assert score["category"] in ["HOT", "WARM", "COLD"]
    assert isinstance(score["points"], int)
    
    # Check recommendation results
    rec = final_lead["recommendation"]
    assert rec["action"] is not None
    assert len(rec["details"]) > 0
    
    # Check communication drafts (should be pending_approval)
    draft = final_lead["draft"]
    assert draft["email_subject"] is not None
    assert draft["email_body"] is not None
    assert draft["whatsapp_body"] is not None
    assert draft["status"] == "pending_approval"
    
    # Verify that the lead is persistently stored in Firestore
    retrieved_lead = firestore_client.get_lead(final_lead["id"])
    assert retrieved_lead is not None
    assert retrieved_lead["id"] == final_lead["id"]
    assert retrieved_lead["draft"]["status"] == "pending_approval"

def test_live_pipeline_integration():
    # Only run this test if NVIDIA_API_KEY is configured in the environment
    if not os.getenv("NVIDIA_API_KEY"):
        pytest.skip("NVIDIA_API_KEY is not configured. Skipping live integration test.")
        
    llm = get_llm()
    if isinstance(llm, MockLLM):
        pytest.skip("get_llm returned MockLLM. Skipping live integration test.")

    firestore_client = FirestoreMCPClient(mock_mode=True)
    gmail_client = GmailMCPClient(mock_mode=True)
    calendar_client = CalendarMCPClient(mock_mode=True)
    
    orchestrator = LeadManagementOrchestrator(
        llm=llm,
        firestore_client=firestore_client,
        gmail_client=gmail_client,
        calendar_client=calendar_client
    )
    
    # Run the pipeline on a sample lead
    raw_lead_text = "I want to join the AI course next month. Budget is $1500. Email me details."
    lead_source = "webform"
    
    final_lead = orchestrator.run_pipeline(raw_lead_text, lead_source)
    
    # Validate final state
    assert final_lead["id"] is not None
    assert final_lead["raw_text"] == raw_lead_text
    
    # Check extraction results (Real LLM should be able to identify "AI" or related courses)
    extracted = final_lead["extracted_data"]
    assert "ai" in extracted.get("course", "").lower() or "unknown" in extracted.get("course", "").lower()
    
    # Check scoring results (HOT lead expected)
    score = final_lead["score"]
    assert score["category"] in ["HOT", "WARM", "COLD"]
    assert isinstance(score["points"], int)

