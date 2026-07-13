import os
os.environ.pop("NVIDIA_API_KEY", None)
import pytest
from google.adk.runners import InMemoryRunner
from google.genai import types
from mcp_clients.firestore_client import FirestoreMCPClient, DB_FILE
from agents.adk_pipeline import adk_pipeline

@pytest.fixture(autouse=True)
def clean_database():
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
    yield
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)

def test_adk_pipeline_execution():
    # 1. Create a lead manually in Firestore to get its lead_id
    firestore_client = FirestoreMCPClient(mock_mode=True)
    raw_text = "I want to join the AI course next month. Budget is $1500."
    source = "webform"
    lead = firestore_client.create_lead(raw_text, source)
    lead_id = lead["id"]
    
    # 2. Set up InMemoryRunner with the ADK SequentialAgent pipeline
    runner = InMemoryRunner(agent=adk_pipeline)
    runner.auto_create_session = True
    
    # 3. Create the genai content message
    p = types.Part(text=f"Process lead {lead_id}")
    new_message = types.Content(role="user", parts=[p])
    
    # 4. Execute the runner synchronously (run returns a generator)
    # Pass the lead_id in state_delta to initialize the session state
    events = list(runner.run(
        user_id="test_user",
        session_id=lead_id,
        new_message=new_message,
        state_delta={"lead_id": lead_id}
    ))
    
    # Assert we received some events from the pipeline run
    assert len(events) > 0
    
    # 5. Fetch the updated lead state from the database
    updated_lead = firestore_client.get_lead(lead_id)
    assert updated_lead is not None
    
    # Assert Stage 1 completed (extracted course and intent)
    assert updated_lead.get("extracted_data", {}).get("course") == "AI"
    assert updated_lead.get("intent") == "enrollment_request"
    
    # Assert Stage 2 completed (score category and points)
    assert updated_lead.get("score", {}).get("category") == "HOT"
    assert updated_lead.get("score", {}).get("points") == 90
    
    # Assert Stage 3 completed (recommendation action)
    assert updated_lead.get("recommendation", {}).get("action") == "Call today"
    
    # Assert Stage 4 completed (draft templates and status)
    draft = updated_lead.get("draft", {})
    assert draft.get("status") == "pending_approval"
    assert "Welcome to our AI program!" in draft.get("email_subject")
