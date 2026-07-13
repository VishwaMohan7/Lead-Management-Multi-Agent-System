from typing import Any
from mcp_clients.firestore_client import FirestoreMCPClient
from mcp_clients.gmail_client import GmailMCPClient
from skills.lead_extraction import LeadExtractionSkill
from skills.intent_detection import IntentDetectionSkill
from mcp_clients.base_client import log_step

class LeadAnalysisAgent:
    """
    Lead Analysis Agent.
    Responsible for extracting structured lead data and detecting lead intent.
    Uses: Gmail MCP (to read email body if needed), Firestore MCP (to read/write lead).
    Skills: LeadExtractionSkill, IntentDetectionSkill.
    """
    def __init__(self, llm: Any, firestore_client: FirestoreMCPClient, gmail_client: GmailMCPClient):
        self.llm = llm
        self.firestore_client = firestore_client
        self.gmail_client = gmail_client
        self.extraction_skill = LeadExtractionSkill(llm)
        self.intent_skill = IntentDetectionSkill(llm)

    def execute(self, lead_id: str) -> dict:
        log_step("AnalysisAgent", f"ENTER execute for lead {lead_id}")
        
        # 1. Fetch current lead state
        log_step("AnalysisAgent", "Retrieving lead state from Firestore...")
        lead = self.firestore_client.get_lead(lead_id)
        if not lead:
            raise ValueError(f"Lead with id {lead_id} not found.")
        log_step("AnalysisAgent", "Successfully fetched lead state.")

        # 2. Retrieve enquiry text. If it came via email, use Gmail MCP to pull the content
        raw_text = lead.get("raw_text", "")
        email_source = lead.get("source") == "email"
        
        if email_source and raw_text.startswith("msg-"):
            log_step("AnalysisAgent", f"Lead source is email. Fetching email contents via Gmail MCP for email ID: {raw_text}")
            email_data = self.gmail_client.get_email_content(raw_text)
            if email_data:
                raw_text = email_data.get("body", raw_text)
                # Store email metadata on lead
                log_step("AnalysisAgent", f"Updating email sender metadata: {email_data.get('sender')}")
                self.firestore_client.update_lead(lead_id, {
                    "lead_email": email_data.get("sender"),
                    "email_subject": email_data.get("subject")
                }, "fetched_email_metadata")
            log_step("AnalysisAgent", "Completed email details retrieval.")

        # 3. Execute skills
        log_step("AnalysisAgent", f"Executing Extraction Skill on raw inquiry text: '{raw_text[:50]}...'")
        extracted = self.extraction_skill.execute(raw_text)
        log_step("AnalysisAgent", f"Extraction Skill completed. Course={extracted.course}, Timeline={extracted.timeline}")

        log_step("AnalysisAgent", "Executing Intent Detection Skill...")
        intent = self.intent_skill.execute(raw_text)
        log_step("AnalysisAgent", f"Intent Detection completed. Intent={intent.intent}, Confidence={intent.confidence}")

        # 4. Save updates to Firestore MCP
        log_step("AnalysisAgent", "Saving structured results back to Firestore...")
        updates = {
            "extracted_data": {
                "course": extracted.course,
                "timeline": extracted.timeline,
                "budget": extracted.budget,
                "contact_channel": extracted.contact_channel
            },
            "intent": intent.intent
        }
        
        updated_lead = self.firestore_client.update_lead(
            lead_id, 
            updates, 
            "analysis_agent_completed"
        )
        log_step("AnalysisAgent", f"EXIT execute successfully for lead {lead_id}")
        return updated_lead
