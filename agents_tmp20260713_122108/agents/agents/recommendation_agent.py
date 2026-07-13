from typing import Any
from mcp_clients.firestore_client import FirestoreMCPClient
from mcp_clients.calendar_client import CalendarMCPClient
from skills.recommendation_logic import RecommendationSkill
from mcp_clients.base_client import log_step

class RecommendationAgent:
    """
    Recommendation Agent.
    Decides next best actions for a lead, integrating with Calendar MCP if necessary.
    Uses: Firestore MCP (read/write state), Google Calendar MCP.
    Skills: RecommendationSkill.
    """
    def __init__(self, llm: Any, firestore_client: FirestoreMCPClient, calendar_client: CalendarMCPClient):
        self.llm = llm
        self.firestore_client = firestore_client
        self.calendar_client = calendar_client
        self.rec_skill = RecommendationSkill(llm, calendar_client)

    def execute(self, lead_id: str) -> dict:
        log_step("RecommendationAgent", f"ENTER execute for lead {lead_id}")

        # 1. Fetch current lead state
        log_step("RecommendationAgent", "Retrieving lead state from Firestore...")
        lead = self.firestore_client.get_lead(lead_id)
        if not lead:
            raise ValueError(f"Lead with id {lead_id} not found.")

        # 2. Extract input values
        score_data = lead.get("score", {})
        score_category = score_data.get("category", "COLD")
        score_points = score_data.get("points", 0)
        extracted_data = lead.get("extracted_data", {})
        lead_email = lead.get("lead_email", "learner@example.com")

        # 3. Run Recommendation skill
        log_step("RecommendationAgent", "Executing Recommendation Skill (with Calendar scheduling checks)...")
        rec_res = self.rec_skill.execute(
            lead_id=lead_id,
            lead_email=lead_email,
            score_category=score_category,
            score_points=score_points,
            extracted_data=extracted_data
        )
        log_step("RecommendationAgent", f"Recommendation Skill completed. Action={rec_res.action}, Calendar scheduled={rec_res.calendar_event is not None}")

        # 4. Save recommendation info to Firestore MCP
        log_step("RecommendationAgent", "Saving recommendation details back to Firestore...")
        updates = {
            "recommendation": {
                "action": rec_res.action,
                "details": rec_res.details,
                "calendar_event": rec_res.calendar_event
            }
        }

        updated_lead = self.firestore_client.update_lead(
            lead_id, 
            updates, 
            "recommendation_agent_completed"
        )
        log_step("RecommendationAgent", f"EXIT execute successfully for lead {lead_id}")
        return updated_lead
