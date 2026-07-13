import os
from dotenv import load_dotenv
# Load environment
load_dotenv()

from utils.llm_provider import get_llm
from mcp_clients.firestore_client import FirestoreMCPClient
from mcp_clients.gmail_client import GmailMCPClient
from mcp_clients.calendar_client import CalendarMCPClient
from orchestrator.pipeline import LeadManagementOrchestrator
from mcp_clients.base_client import log_step

def run_diagnostic():
    log_step("Diagnostic", "--- STARTING STUCK PIPELINE DIAGNOSIS ---")
    
    # 1. Initialize dependencies
    llm = get_llm()
    log_step("Diagnostic", f"LLM client loaded: {type(llm).__name__}")
    
    firestore_client = FirestoreMCPClient(mock_mode=True)
    gmail_client = GmailMCPClient(mock_mode=True)
    calendar_client = CalendarMCPClient(mock_mode=True)
    
    orchestrator = LeadManagementOrchestrator(
        llm=llm,
        firestore_client=firestore_client,
        gmail_client=gmail_client,
        calendar_client=calendar_client
    )
    
    # 2. Run test lead
    raw_lead_text = "I want to join AI course next month. Budget is $1500. Email me details."
    source = "webform"
    
    try:
        log_step("Diagnostic", f"Ingesting lead: '{raw_lead_text}'")
        final_state = orchestrator.run_pipeline(raw_lead_text, source)
        log_step("Diagnostic", "SUCCESS: Pipeline completed end-to-end!")
        log_step("Diagnostic", f"Final Score: {final_state.get('score')}")
        log_step("Diagnostic", f"Final Rec: {final_state.get('recommendation')}")
        log_step("Diagnostic", f"Final Draft Status: {final_state.get('draft', {}).get('status')}")
    except Exception as e:
        log_step("Diagnostic", f"FAILED: Pipeline crashed with error: {e}")

if __name__ == "__main__":
    run_diagnostic()
