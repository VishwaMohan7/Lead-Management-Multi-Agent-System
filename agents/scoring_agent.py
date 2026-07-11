from typing import Any
from mcp_clients.firestore_client import FirestoreMCPClient
from skills.scoring_rules import ScoringRulesSkill
from mcp_clients.base_client import logger

class LeadScoringAgent:
    """
    Lead Scoring Agent.
    Responsible for scoring leads based on extracted characteristics and intent.
    Uses: Firestore MCP (read/write state).
    Skills: ScoringRulesSkill.
    """
    def __init__(self, llm: Any, firestore_client: FirestoreMCPClient):
        self.llm = llm
        self.firestore_client = firestore_client
        self.scoring_skill = ScoringRulesSkill(llm)

    def execute(self, lead_id: str) -> dict:
        logger.info(f"[ScoringAgent] Executing for lead: {lead_id}")

        # 1. Fetch current lead state
        lead = self.firestore_client.get_lead(lead_id)
        if not lead:
            raise ValueError(f"Lead with id {lead_id} not found.")

        # 2. Run scoring skill
        extracted_data = lead.get("extracted_data", {})
        intent = lead.get("intent", "other")
        
        scoring_res = self.scoring_skill.execute(extracted_data, intent)

        # 3. Update Firestore MCP
        updates = {
            "score": {
                "category": scoring_res.category,
                "points": scoring_res.score,
                "reasoning": scoring_res.reasoning
            }
        }
        
        updated_lead = self.firestore_client.update_lead(
            lead_id, 
            updates, 
            "scoring_agent_completed"
        )
        logger.info(f"[ScoringAgent] Completed scoring for lead {lead_id}: {scoring_res.category} ({scoring_res.score} pts)")
        return updated_lead
