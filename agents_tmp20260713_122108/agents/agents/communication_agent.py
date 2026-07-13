from typing import Any
from mcp_clients.firestore_client import FirestoreMCPClient
from skills.email_generation import EmailGenerationSkill
from skills.whatsapp_generation import WhatsAppGenerationSkill
from mcp_clients.base_client import log_step

class CommunicationAgent:
    """
    Communication Agent.
    Drafts outbound communication (Email and/or WhatsApp) tailored to the lead.
    Uses: Firestore MCP (read/write state).
    Skills: EmailGenerationSkill, WhatsAppGenerationSkill.
    """
    def __init__(self, llm: Any, firestore_client: FirestoreMCPClient):
        self.llm = llm
        self.firestore_client = firestore_client
        self.email_skill = EmailGenerationSkill(llm)
        self.whatsapp_skill = WhatsAppGenerationSkill(llm)

    def execute(self, lead_id: str) -> dict:
        log_step("CommunicationAgent", f"ENTER execute for lead {lead_id}")

        # 1. Fetch current lead state
        log_step("CommunicationAgent", "Retrieving lead state from Firestore...")
        lead = self.firestore_client.get_lead(lead_id)
        if not lead:
            raise ValueError(f"Lead with id {lead_id} not found.")

        # 2. Extract inputs
        score_data = lead.get("score", {})
        score_category = score_data.get("category", "COLD")
        rec_data = lead.get("recommendation", {})
        recommendation_action = rec_data.get("action", "Send info email")
        extracted_data = lead.get("extracted_data", {})
        lead_email = lead.get("lead_email", "learner@example.com")

        # 3. Execute drafting skills
        log_step("CommunicationAgent", "Executing Email Generation Skill...")
        email_draft = self.email_skill.execute(
            lead_email=lead_email,
            score_category=score_category,
            recommendation=recommendation_action,
            extracted_data=extracted_data
        )
        log_step("CommunicationAgent", f"Email Generation Skill completed. Subject: '{email_draft.subject}'")

        log_step("CommunicationAgent", "Executing WhatsApp Generation Skill...")
        whatsapp_draft = self.whatsapp_skill.execute(
            score_category=score_category,
            recommendation=recommendation_action,
            extracted_data=extracted_data
        )
        log_step("CommunicationAgent", "WhatsApp Generation Skill completed.")

        # 4. Save drafts to Firestore with pending_approval status
        log_step("CommunicationAgent", "Saving draft messaging to Firestore with status 'pending_approval'...")
        updates = {
            "draft": {
                "email_subject": email_draft.subject,
                "email_body": email_draft.body,
                "whatsapp_body": whatsapp_draft.body,
                "status": "pending_approval"
            }
        }

        updated_lead = self.firestore_client.update_lead(
            lead_id, 
            updates, 
            "communication_agent_completed"
        )
        log_step("CommunicationAgent", f"EXIT execute successfully for lead {lead_id}")
        return updated_lead
