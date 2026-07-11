import pytest
from utils.llm_provider import MockLLM
from mcp_clients.calendar_client import CalendarMCPClient
from skills.lead_extraction import LeadExtractionSkill
from skills.intent_detection import IntentDetectionSkill
from skills.scoring_rules import ScoringRulesSkill
from skills.recommendation_logic import RecommendationSkill
from skills.email_generation import EmailGenerationSkill
from skills.whatsapp_generation import WhatsAppGenerationSkill

@pytest.fixture
def mock_llm():
    return MockLLM()

@pytest.fixture
def mock_calendar():
    return CalendarMCPClient(mock_mode=True)

def test_lead_extraction(mock_llm):
    skill = LeadExtractionSkill(mock_llm)
    # Lead with AI course, next month timeline, and budget
    raw_lead = "Hi, I'd like to enroll in the AI course starting next month. My budget is $2000. Contact me via Email."
    result = skill.execute(raw_lead)
    
    assert result.course == "AI"
    assert result.timeline == "Next month"
    assert result.budget == "$2000"
    assert result.contact_channel == "Email"

def test_intent_detection(mock_llm):
    skill = IntentDetectionSkill(mock_llm)
    # Lead asking about fees
    pricing_lead = "How much does the data science bootcamp cost?"
    result = skill.execute(pricing_lead)
    
    assert result.intent == "pricing_check"
    assert result.confidence >= 0.5

def test_scoring_rules(mock_llm):
    skill = ScoringRulesSkill(mock_llm)
    
    # Hot Lead profile: AI course, urgent timeline, known budget, high intent
    extracted_data = {
        "course": "AI",
        "timeline": "ASAP",
        "budget": "$1500",
        "contact_channel": "Email"
    }
    intent = "enrollment_request"
    result = skill.execute(extracted_data, intent)
    
    # 40 (base) + 15 (course) + 20 (timeline) + 15 (budget) + 10 (intent) = 100
    assert result.category == "HOT"
    assert result.score >= 80

def test_recommendation_logic(mock_llm, mock_calendar):
    skill = RecommendationSkill(mock_llm, mock_calendar)
    
    # Test for HOT lead with ASAP timeline -> should trigger "Schedule demo" and schedule a meeting
    extracted_data = {
        "course": "AI",
        "timeline": "ASAP",
        "budget": "Unknown",
        "contact_channel": "Email"
    }
    result = skill.execute(
        lead_id="test-lead-123",
        lead_email="john@example.com",
        score_category="HOT",
        score_points=90,
        extracted_data=extracted_data
    )
    
    assert result.action == "Schedule demo"
    assert result.calendar_event is not None
    assert result.calendar_event["event_id"] == "evt_mock_12345"

def test_communication_drafts(mock_llm):
    email_skill = EmailGenerationSkill(mock_llm)
    whatsapp_skill = WhatsAppGenerationSkill(mock_llm)
    
    extracted_data = {
        "course": "AI",
        "timeline": "ASAP"
    }
    
    email_draft = email_skill.execute(
        lead_email="john@example.com",
        score_category="HOT",
        recommendation="Schedule demo",
        extracted_data=extracted_data
    )
    
    whatsapp_draft = whatsapp_skill.execute(
        score_category="HOT",
        recommendation="Schedule demo",
        extracted_data=extracted_data
    )
    
    assert "AI" in email_draft.subject or "AI" in email_draft.body or "course" in email_draft.body.lower()
    assert len(email_draft.body) > 0
    assert len(whatsapp_draft.body) > 0
