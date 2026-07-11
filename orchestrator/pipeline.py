from typing import Any, Dict
from mcp_clients.firestore_client import FirestoreMCPClient
from mcp_clients.gmail_client import GmailMCPClient
from mcp_clients.calendar_client import CalendarMCPClient
from agents.analysis_agent import LeadAnalysisAgent
from agents.scoring_agent import LeadScoringAgent
from agents.recommendation_agent import RecommendationAgent
from agents.communication_agent import CommunicationAgent
from mcp_clients.base_client import logger

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
        logger.info("Starting Orchestration Pipeline for a new lead...")
        
        # Step 0: Create initial record in Firestore MCP
        lead = self.firestore_client.create_lead(raw_text, source)
        lead_id = lead["id"]
        logger.info(f"Lead created with ID: {lead_id}")

        try:
            # Step 1: Lead Analysis Agent
            logger.info("Executing Stage 1: Lead Analysis Agent...")
            lead = self.analysis_agent.execute(lead_id)

            # Step 2: Lead Scoring Agent
            logger.info("Executing Stage 2: Lead Scoring Agent...")
            lead = self.scoring_agent.execute(lead_id)

            # Step 3: Recommendation Agent
            logger.info("Executing Stage 3: Recommendation Agent...")
            lead = self.recommendation_agent.execute(lead_id)

            # Step 4: Communication Agent
            logger.info("Executing Stage 4: Communication Agent...")
            lead = self.communication_agent.execute(lead_id)

            logger.info(f"Pipeline completed successfully for lead: {lead_id}")
            return lead

        except Exception as e:
            logger.error(f"Pipeline failed mid-execution for lead {lead_id}: {e}")
            # Track failure in history
            self.firestore_client.update_lead(
                lead_id, 
                {}, 
                f"pipeline_failed: {str(e)}"
            )
            raise e
