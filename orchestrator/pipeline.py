import threading
import openai
from typing import Any, Dict
from mcp_clients.firestore_client import FirestoreMCPClient
from mcp_clients.gmail_client import GmailMCPClient
from mcp_clients.calendar_client import CalendarMCPClient
from agents.analysis_agent import LeadAnalysisAgent
from agents.scoring_agent import LeadScoringAgent
from agents.recommendation_agent import RecommendationAgent
from agents.communication_agent import CommunicationAgent
from mcp_clients.base_client import log_step, logger

def run_step_with_timeout(func, args, step_name: str, timeout_sec: float = 45.0) -> Any:
    """
    Executes a step function in a daemon thread, joining with a timeout.
    This guarantees that synchronous or network hangs will be interrupted
    by raising a TimeoutError.
    """
    result = [None]
    exception = [None]

    def target():
        try:
            result[0] = func(*args)
        except Exception as e:
            exception[0] = e

    thread = threading.Thread(target=target)
    thread.daemon = True
    log_step("OrchestratorTimeoutWrapper", f"Starting step '{step_name}' thread with a {timeout_sec}s timeout.")
    thread.start()
    thread.join(timeout=timeout_sec)

    if thread.is_alive():
        log_step("OrchestratorTimeoutWrapper", f"TIMEOUT ERROR: Step '{step_name}' exceeded limit of {timeout_sec}s.")
        raise TimeoutError(f"Step '{step_name}' timed out after {timeout_sec} seconds.")
    if exception[0]:
        raise exception[0]
    return result[0]

class LeadManagementOrchestrator:
    """
    Lead Management Orchestrator.
    Sequentially runs the lead analysis, scoring, recommendation, 
    and communication drafting stages, persisting state at each checkpoint.
    """
    def __init__(
        self, 
        llm: Any,
        firestore_client: FirestoreMCPClient,
        gmail_client: GmailMCPClient,
        calendar_client: CalendarMCPClient
    ):
        self.firestore_client = firestore_client
        
        # Initialize the agents
        self.analysis_agent = LeadAnalysisAgent(llm, firestore_client, gmail_client)
        self.scoring_agent = LeadScoringAgent(llm, firestore_client)
        self.recommendation_agent = RecommendationAgent(llm, firestore_client, calendar_client)
        self.communication_agent = CommunicationAgent(llm, firestore_client)

    def run_pipeline(self, raw_text: str, source: str) -> Dict:
        """
        Executes the full pipeline for a new incoming lead.
        """
        log_step("Orchestrator", f"ENTER run_pipeline. Source={source}, Raw text preview='{raw_text[:40]}...'")
        
        # Step 0: Create initial record in Firestore MCP
        log_step("Orchestrator", "Creating initial lead record in Firestore...")
        lead = self.firestore_client.create_lead(raw_text, source)
        lead_id = lead["id"]
        log_step("Orchestrator", f"Created lead document in database with ID: {lead_id}")

        try:
            # Step 1: Lead Analysis Agent
            log_step("Orchestrator", "Stage 1: Launching Lead Analysis Agent...")
            lead = run_step_with_timeout(self.analysis_agent.execute, (lead_id,), "LeadAnalysisAgent", 45.0)
            log_step("Orchestrator", "Stage 1 Completed: Lead Analysis Agent finished.")

            # Step 2: Lead Scoring Agent
            log_step("Orchestrator", "Stage 2: Launching Lead Scoring Agent...")
            lead = run_step_with_timeout(self.scoring_agent.execute, (lead_id,), "LeadScoringAgent", 45.0)
            log_step("Orchestrator", "Stage 2 Completed: Lead Scoring Agent finished.")

            # Step 3: Recommendation Agent
            log_step("Orchestrator", "Stage 3: Launching Recommendation Agent...")
            lead = run_step_with_timeout(self.recommendation_agent.execute, (lead_id,), "RecommendationAgent", 45.0)
            log_step("Orchestrator", "Stage 3 Completed: Recommendation Agent finished.")

            # Step 4: Communication Agent
            log_step("Orchestrator", "Stage 4: Launching Communication Agent...")
            lead = run_step_with_timeout(self.communication_agent.execute, (lead_id,), "CommunicationAgent", 45.0)
            log_step("Orchestrator", "Stage 4 Completed: Communication Agent finished.")

            log_step("Orchestrator", f"EXIT run_pipeline successfully for lead: {lead_id}")
            return lead

        except openai.RateLimitError as rle:
            retry_after = "unknown"
            if hasattr(rle, "response") and rle.response is not None:
                retry_after = rle.response.headers.get("retry-after", "unknown")
            log_step("Orchestrator", f"RATE LIMIT ERROR: Provider rate-limited lead {lead_id}. Retry-After: {retry_after}")
            try:
                self.firestore_client.update_lead(
                    lead_id,
                    {},
                    f"pipeline_failed_rate_limit: {str(rle)} (Retry-After: {retry_after})"
                )
            except Exception as update_err:
                log_step("Orchestrator", f"CRITICAL: Failed to write error status back to Firestore: {update_err}")
            raise rle
        except Exception as e:
            log_step("Orchestrator", f"ERROR: Pipeline execution failed mid-run for lead {lead_id}: {e}")
            # Track failure in history
            try:
                self.firestore_client.update_lead(
                    lead_id, 
                    {}, 
                    f"pipeline_failed: {str(e)}"
                )
            except Exception as update_err:
                log_step("Orchestrator", f"CRITICAL: Failed to write error status back to Firestore: {update_err}")
            raise e
