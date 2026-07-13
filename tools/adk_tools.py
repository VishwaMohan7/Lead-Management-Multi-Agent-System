from utils.llm_provider import get_llm
from skills.lead_extraction import LeadExtractionSkill
from skills.intent_detection import IntentDetectionSkill
from skills.scoring_rules import ScoringRulesSkill
from skills.recommendation_logic import RecommendationSkill
from skills.email_generation import EmailGenerationSkill
from skills.whatsapp_generation import WhatsAppGenerationSkill

def extract_lead_info(raw_text: str) -> dict:
    """
    Extracts structured fields (course, timeline, budget, contact_channel) from raw inquiry text.
    
    Args:
        raw_text (str): The raw inquiry text or message from the lead.
    """
    llm = get_llm()
    skill = LeadExtractionSkill(llm)
    res = skill.execute(raw_text)
    return {
        "course": res.course,
        "custom_course": res.course, # Support both old and new keys if frontend uses it
        "timeline": res.timeline,
        "budget": res.budget,
        "contact_channel": res.contact_channel
    }

def detect_lead_intent(raw_text: str) -> dict:
    """
    Classifies the primary intent of the lead's enquiry.
    
    Args:
        raw_text (str): The raw inquiry text.
    """
    llm = get_llm()
    skill = IntentDetectionSkill(llm)
    res = skill.execute(raw_text)
    return {
        "intent": res.intent,
        "confidence": res.confidence
    }

def calculate_lead_score(extracted_data: dict, intent: str) -> dict:
    """
    Calculates the category (HOT/WARM/COLD) and point score for a lead based on structured data and intent.
    
    Args:
        extracted_data (dict): The extracted lead dictionary with keys: course, timeline, budget, contact_channel.
        intent (str): The detected intent of the lead.
    """
    llm = get_llm()
    skill = ScoringRulesSkill(llm)
    res = skill.execute(extracted_data, intent)
    return {
        "category": res.category,
        "points": res.score,
        "reasoning": res.reasoning
    }

def generate_recommendations(lead_id: str, lead_email: str, score_category: str, score_points: int, extracted_data: dict) -> dict:
    """
    Generates next-best-action recommendations for the admissions team, integrating calendar scheduling if needed.
    
    Args:
        lead_id (str): The UUID of the lead.
        lead_email (str): The email address of the lead.
        score_category (str): The lead score category (HOT, WARM, COLD).
        score_points (int): The total score points of the lead.
        extracted_data (dict): The extracted lead dictionary with keys: course, timeline, budget, contact_channel.
    """
    llm = get_llm()
    # Use mock calendar client in the skill execution (the agent can also query the calendar MCP tool directly if desired)
    from mcp_clients.calendar_client import CalendarMCPClient
    calendar_client = CalendarMCPClient(mock_mode=True)
    skill = RecommendationSkill(llm, calendar_client)
    
    res = skill.execute(
        lead_id=lead_id,
        lead_email=lead_email,
        score_category=score_category,
        score_points=score_points,
        extracted_data=extracted_data
    )
    return {
        "action": res.action,
        "details": res.details,
        "calendar_event": res.calendar_event
    }

def generate_outbound_drafts(lead_email: str, score_category: str, recommendation: str, extracted_data: dict) -> dict:
    """
    Drafts tailored outbound messages (Email and WhatsApp) for a lead.
    
    Args:
        lead_email (str): The email address of the lead.
        score_category (str): The lead score category (HOT, WARM, COLD).
        recommendation (str): The next best action recommended for the lead.
        extracted_data (dict): The extracted lead dictionary with keys: course, timeline, budget, contact_channel.
    """
    llm = get_llm()
    email_skill = EmailGenerationSkill(llm)
    whatsapp_skill = WhatsAppGenerationSkill(llm)
    
    email_draft = email_skill.execute(
        lead_email=lead_email,
        score_category=score_category,
        recommendation=recommendation,
        extracted_data=extracted_data
    )
    
    whatsapp_draft = whatsapp_skill.execute(
        score_category=score_category,
        recommendation=recommendation,
        extracted_data=extracted_data
    )
    
    return {
        "email_subject": email_draft.subject,
        "email_body": email_draft.body,
        "whatsapp_body": whatsapp_draft.body,
        "status": "pending_approval"
    }
