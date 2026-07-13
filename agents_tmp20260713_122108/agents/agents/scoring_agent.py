from typing import Any
from mcp_clients.firestore_client import FirestoreMCPClient
from skills.scoring_rules import ScoringRulesSkill
from mcp_clients.base_client import log_step

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
        log_step("ScoringAgent", f"ENTER execute for lead {lead_id}")

        # 1. Fetch current lead state
        log_step("ScoringAgent", "Retrieving lead state from Firestore...")
        lead = self.firestore_client.get_lead(lead_id)
        if not lead:
            raise ValueError(f"Lead with id {lead_id} not found.")

        # 2. Run scoring skill
        extracted_data = lead.get("extracted_data", {})
        intent = lead.get("intent", "other")
        
        log_step("ScoringAgent", "Executing Scoring Rules Skill...")
        scoring_res = self.scoring_skill.execute(extracted_data, intent)
        log_step("ScoringAgent", f"Scoring Rules Skill finished. Category={scoring_res.category}, Points={scoring_res.score}")

        # 3. Update Firestore MCP
        log_step("ScoringAgent", "Saving lead score results back to Firestore...")
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
        log_step("ScoringAgent", f"EXIT execute successfully for lead {lead_id}")
        return updated_lead
