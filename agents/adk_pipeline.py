import os
import re
import sys
import logging
from typing import Any, AsyncGenerator, Dict, Optional

from dotenv import load_dotenv
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.models.registry import LLMRegistry
from google.genai import types

from mcp_clients.firestore_client import FirestoreMCPClient
from mcp_clients.gmail_client import GmailMCPClient

load_dotenv()

logger = logging.getLogger("adk_pipeline")


def _firestore_client() -> FirestoreMCPClient:
    if "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ:
        return FirestoreMCPClient(mock_mode=True)
    return FirestoreMCPClient()


def _gmail_client() -> GmailMCPClient:
    use_mock_gmail = os.getenv("USE_MOCK_GMAIL", "true").lower() == "true"
    return GmailMCPClient(mock_mode=use_mock_gmail)


def get_lead(lead_id: str) -> dict:
    """Retrieve one lead from Firestore by its lead id."""
    lead = _firestore_client().get_lead(lead_id)
    if not lead:
        return {"error": f"Lead {lead_id} not found"}
    return lead


def update_lead(lead_id: str, updates: dict, event_name: str = "lead_updated") -> dict:
    """Merge updates into one Firestore lead document and append a history event."""
    lead = _firestore_client().update_lead(lead_id, updates, event_name)
    if not lead:
        return {"error": f"Lead {lead_id} not found"}
    return lead


def get_email_content(email_id: str) -> dict:
    """Fetch the original Gmail enquiry body for a Gmail message id."""
    email_data = _gmail_client().get_email_content(email_id)
    if not email_data:
        return {"error": f"Email {email_id} not found"}
    return email_data


def _source_text(lead_data: Dict[str, Any]) -> str:
    return str(lead_data.get("analysis", {}).get("source_text") or lead_data.get("raw_text", ""))


def _detect_course(text: str) -> str:
    if "data science" in text:
        return "Data Science"
    if "ai" in text or "artificial intelligence" in text:
        return "AI"
    if "python" in text:
        return "Python"
    if "marketing" in text:
        return "Digital Marketing"
    return "Unknown"


def _detect_timeline(text: str) -> str:
    if "asap" in text or "immediately" in text:
        return "ASAP"
    if "next month" in text:
        return "Next month"
    if "two weeks" in text or "2 weeks" in text:
        return "Within two weeks"
    if "tomorrow" in text:
        return "Immediate"
    return "Flexible"


def _detect_budget(text: str) -> str:
    match = re.search(r"(\$\s*\d+|\d+\s*dollars?|\d+\s*usd|\b\d{3,4}\b)", text, re.IGNORECASE)
    return match.group(1).upper() if match else "Unknown"


def _detect_contact_channel(text: str, source: str) -> str:
    if "whatsapp" in text or source == "whatsapp":
        return "WhatsApp"
    if "email" in text or source == "email":
        return "Email"
    return "Email"


def _detect_intent(text: str) -> str:
    if "scholarship" in text:
        return "scholarship_inquiry"
    if "price" in text or "fee" in text or "cost" in text:
        return "pricing_check"
    if "enroll" in text or "register" in text or "join" in text or "admission" in text:
        return "enrollment_request"
    return "course_inquiry"


def _score_lead(lead_data: Dict[str, Any]) -> Dict[str, Any]:
    extracted = lead_data.get("extracted_data", {})
    intent = lead_data.get("intent", "course_inquiry")
    score_points = 35
    reasons = ["incoming enquiry captured"]

    if extracted.get("course") and extracted.get("course") != "Unknown":
        score_points += 15
        reasons.append(f"course interest in {extracted['course']}")
    if extracted.get("timeline") and extracted.get("timeline") != "Flexible":
        score_points += 20
        reasons.append(f"clear timeline ({extracted['timeline']})")
    if extracted.get("budget") and extracted.get("budget") != "Unknown":
        score_points += 15
        reasons.append(f"budget mentioned ({extracted['budget']})")
    if intent in {"enrollment_request", "pricing_check", "scholarship_inquiry"}:
        score_points += 5
        reasons.append(f"intent is {intent}")

    score_points = min(score_points, 100)
    category = "HOT" if score_points >= 80 else "WARM" if score_points >= 55 else "COLD"
    return {
        "category": category,
        "points": score_points,
        "reasoning": f"{category} because {', '.join(reasons)}.",
    }


def complete_source_intake(lead_id: str) -> dict:
    """Complete source intake for one lead and save analysis.source_text."""
    lead = _firestore_client().get_lead(lead_id)
    if not lead:
        return {"error": f"Lead {lead_id} not found"}

    email_data = None
    if lead.get("source") == "email" and str(lead.get("raw_text", "")).startswith("msg-"):
        email_data = _gmail_client().get_email_content(str(lead.get("raw_text")))

    source_text = str((email_data or {}).get("body") or lead.get("raw_text", ""))
    updates: Dict[str, Any] = {
        "analysis": {
            "source_text": source_text,
            "normalized_text": source_text.lower(),
        }
    }
    if email_data:
        updates["lead_email"] = email_data.get("sender", lead.get("lead_email", "learner@example.com"))
        updates["email_subject"] = email_data.get("subject", lead.get("email_subject"))
    return update_lead(lead_id, updates, "source_intake_completed")


def complete_lead_analysis(
    lead_id: str,
    course: str,
    timeline: str,
    budget: str,
    contact_channel: str,
    intent: str
) -> dict:
    """Save extracted lead fields and intent to Firestore."""
    updates = {
        "extracted_data": {
            "course": course,
            "timeline": timeline,
            "budget": budget,
            "contact_channel": contact_channel,
        },
        "intent": intent,
    }
    return update_lead(lead_id, updates, "analysis_agent_completed")


def complete_lead_scoring(
    lead_id: str,
    category: str,
    points: int,
    reasoning: str
) -> dict:
    """Save lead classification and score reasoning to Firestore."""
    score_data = {
        "category": category,
        "points": points,
        "reasoning": reasoning,
    }
    return update_lead(lead_id, {"score": score_data}, "scoring_agent_completed")


def complete_recommendation(
    lead_id: str,
    action: str,
    details: str
) -> dict:
    """Save admissions next action and details to Firestore."""
    rec_data = {
        "action": action,
        "details": details,
        "calendar_event": None,
    }
    return update_lead(lead_id, {"recommendation": rec_data}, "recommendation_agent_completed")


def complete_communication_draft(
    lead_id: str,
    email_subject: str,
    email_body: str,
    whatsapp_body: str
) -> dict:
    """Save outreach drafts (Email and WhatsApp) to Firestore."""
    draft_data = {
        "email_subject": email_subject,
        "email_body": email_body,
        "whatsapp_body": whatsapp_body,
        "status": "pending_approval",
    }
    return update_lead(lead_id, {"draft": draft_data}, "communication_agent_completed")



class MockLeadManagementLLM(BaseLlm):
    """Offline ADK model that deterministically simulates the full agent team."""

    @classmethod
    def supported_models(cls) -> list[str]:
        return ["mock-adk-model"]

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        instruction = ""
        if llm_request.config and llm_request.config.system_instruction:
            instruction = str(llm_request.config.system_instruction)

        history = llm_request.contents or []
        lead_id = self._extract_lead_id(history)
        lead_data = self._latest_tool_payload(history, {"get_lead", "update_lead"})
        email_data = self._latest_tool_payload(history, {"get_email_content"})
        completed_calls: list[str] = []
        for content in history:
            for part in content.parts or []:
                if part.function_call:
                    completed_calls.append(part.function_call.name)
                if part.function_response:
                    completed_calls.append(part.function_response.name)

        if "SourceIntakeAgent" in instruction:
            if "complete_source_intake" in completed_calls:
                yield self._make_text_response("Source intake complete.")
                return
            yield self._make_tool_call("complete_source_intake", {"lead_id": lead_id})
            return
        if "LeadAnalysisAgent" in instruction:
            if "complete_lead_analysis" in completed_calls:
                yield self._make_text_response("Lead analysis complete.")
                return
            yield self._make_tool_call("complete_lead_analysis", {
                "lead_id": lead_id,
                "course": "AI",
                "timeline": "Next month",
                "budget": "$1500",
                "contact_channel": "Email",
                "intent": "enrollment_request"
            })
            return
        if "LeadScoringAgent" in instruction:
            if "complete_lead_scoring" in completed_calls:
                yield self._make_text_response("Lead scoring complete.")
                return
            yield self._make_tool_call("complete_lead_scoring", {
                "lead_id": lead_id,
                "category": "HOT",
                "points": 90,
                "reasoning": "HOT because high-demand course interest (+15), Urgent start timeline (+20), Budget details provided (+15), High buying intent (+10)."
            })
            return
        if "RecommendationAgent" in instruction:
            if "complete_recommendation" in completed_calls:
                yield self._make_text_response("Recommendation complete.")
                return
            yield self._make_tool_call("complete_recommendation", {
                "lead_id": lead_id,
                "action": "Call today",
                "details": "Follow up immediately to secure enrollment."
            })
            return
        if "CommunicationAgent" in instruction:
            if "complete_communication_draft" in completed_calls:
                yield self._make_text_response("Communication draft complete.")
                return
            yield self._make_tool_call("complete_communication_draft", {
                "lead_id": lead_id,
                "email_subject": "Welcome to our AI program!",
                "email_body": "Hi, Thanks for reaching out! We are thrilled to hear about your interest in our AI program. A course counselor will review your request and contact you soon.",
                "whatsapp_body": "Hi! Thanks for inquiring about the AI program. A counselor will get in touch with you shortly."
            })
            return

        yield self._make_text_response("Mock model run complete.")

    def _run_source_stage(self, lead_data: Dict[str, Any], email_data: Optional[Dict[str, Any]]) -> LlmResponse:
        if lead_data.get("analysis", {}).get("source_text"):
            return self._make_text_response("Source intake complete.")

        lead_id = lead_data.get("id", "test-lead-uuid")
        if self._should_fetch_email(lead_data, email_data):
            return self._make_tool_call("get_email_content", {"email_id": lead_data.get("raw_text", lead_id)})

        source_text = str((email_data or {}).get("body") or lead_data.get("raw_text", ""))
        updates: Dict[str, Any] = {
            "analysis": {
                "source_text": source_text,
                "normalized_text": source_text.lower(),
            }
        }
        if email_data:
            updates["lead_email"] = email_data.get("sender", lead_data.get("lead_email", "learner@example.com"))
            updates["email_subject"] = email_data.get("subject", lead_data.get("email_subject"))

        return self._make_tool_call(
            "update_lead",
            {"lead_id": lead_id, "updates": updates, "event_name": "source_intake_completed"},
        )

    def _run_analysis_stage(self, lead_data: Dict[str, Any]) -> LlmResponse:
        if lead_data.get("extracted_data") and lead_data.get("intent"):
            return self._make_text_response("Lead analysis complete.")

        text = self._source_text(lead_data)
        normalized_text = text.lower()
        updates = {
            "extracted_data": {
                "course": self._detect_course(normalized_text),
                "timeline": self._detect_timeline(normalized_text),
                "budget": self._detect_budget(text),
                "contact_channel": self._detect_contact_channel(normalized_text, lead_data.get("source", "")),
            },
            "intent": self._detect_intent(normalized_text),
        }
        return self._make_tool_call(
            "update_lead",
            {"lead_id": lead_data.get("id"), "updates": updates, "event_name": "analysis_agent_completed"},
        )

    def _run_scoring_stage(self, lead_data: Dict[str, Any]) -> LlmResponse:
        if lead_data.get("score"):
            return self._make_text_response("Lead scoring complete.")

        score = self._score_lead(lead_data)
        return self._make_tool_call(
            "update_lead",
            {"lead_id": lead_data.get("id"), "updates": {"score": score}, "event_name": "scoring_agent_completed"},
        )

    def _run_recommendation_stage(self, lead_data: Dict[str, Any]) -> LlmResponse:
        if lead_data.get("recommendation"):
            return self._make_text_response("Recommendation complete.")

        category = lead_data.get("score", {}).get("category", "COLD")
        if category == "HOT":
            recommendation = {
                "action": "Call today",
                "details": "High-intent lead. Contact immediately and offer a live consultation.",
                "calendar_event": None,
            }
        elif category == "WARM":
            recommendation = {
                "action": "Send tailored follow-up",
                "details": "Interest is real but not urgent. Follow up with course details and a low-friction CTA.",
                "calendar_event": None,
            }
        else:
            recommendation = {
                "action": "Send nurture email",
                "details": "Lead is early-stage. Send a helpful message and ask for the missing course, budget, or timeline details.",
                "calendar_event": None,
            }

        return self._make_tool_call(
            "update_lead",
            {
                "lead_id": lead_data.get("id"),
                "updates": {"recommendation": recommendation},
                "event_name": "recommendation_agent_completed",
            },
        )

    def _run_communication_stage(self, lead_data: Dict[str, Any]) -> LlmResponse:
        if lead_data.get("draft"):
            return self._make_text_response("Communication draft complete.")

        extracted = lead_data.get("extracted_data", {})
        course = extracted.get("course", "Unknown")
        course_label = course if course != "Unknown" else "our program"
        category = lead_data.get("score", {}).get("category", "COLD")
        reasoning = lead_data.get("score", {}).get("reasoning", "the enquiry needs more qualification")
        action = lead_data.get("recommendation", {}).get("action", "Send course details")

        draft = {
            "email_subject": f"Welcome to our {course_label} program!" if course != "Unknown" else "Welcome to our program",
            "email_body": (
                f"Hi,\n\n"
                f"Thanks for reaching out about {course_label}. We reviewed your enquiry and would be happy to help you take the next step.\n\n"
                f"Recommended next step: {action}.\n"
                f"Why we classified this lead as {category}: {reasoning}\n\n"
                f"Best regards,\nAdmissions Team"
            ),
            "whatsapp_body": (
                f"Hi! Thanks for your enquiry about {course_label}. Recommended next step: {action}. "
                f"We marked this as {category} because {reasoning}"
            ),
            "status": "pending_approval",
        }
        return self._make_tool_call(
            "update_lead",
            {"lead_id": lead_data.get("id"), "updates": {"draft": draft}, "event_name": "communication_agent_completed"},
        )

    def _score_lead(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        extracted = lead_data.get("extracted_data", {})
        intent = lead_data.get("intent", "course_inquiry")
        score_points = 35
        reasons = ["incoming enquiry captured"]

        if extracted.get("course") and extracted.get("course") != "Unknown":
            score_points += 15
            reasons.append(f"course interest in {extracted['course']}")
        if extracted.get("timeline") and extracted.get("timeline") != "Flexible":
            score_points += 20
            reasons.append(f"clear timeline ({extracted['timeline']})")
        if extracted.get("budget") and extracted.get("budget") != "Unknown":
            score_points += 15
            reasons.append(f"budget mentioned ({extracted['budget']})")
        if intent in {"enrollment_request", "pricing_check", "scholarship_inquiry"}:
            score_points += 5
            reasons.append(f"intent is {intent}")

        score_points = min(score_points, 100)
        category = "HOT" if score_points >= 80 else "WARM" if score_points >= 55 else "COLD"
        return {
            "category": category,
            "points": score_points,
            "reasoning": f"{category} because {', '.join(reasons)}.",
        }

    def _extract_lead_id(self, history: list[Any]) -> str:
        for content in history:
            for part in content.parts or []:
                if part.function_call and "lead_id" in part.function_call.args:
                    return str(part.function_call.args["lead_id"])

        if history and history[0].parts:
            text = history[0].parts[0].text or ""
            match = re.search(r"Process lead\s+([A-Za-z0-9-]+)", text)
            if match:
                return match.group(1)

        return "test-lead-uuid"

    @staticmethod
    def _latest_tool_payload(history: list[Any], names: set[str]) -> Optional[Dict[str, Any]]:
        payload = None
        for content in history:
            for part in content.parts or []:
                if part.function_response and part.function_response.name in names:
                    response = part.function_response.response
                    if isinstance(response, dict) and "error" not in response:
                        payload = response
        return payload

    @staticmethod
    def _should_fetch_email(lead_data: Dict[str, Any], email_data: Optional[Dict[str, Any]]) -> bool:
        if email_data or lead_data.get("source") != "email":
            return False
        return str(lead_data.get("raw_text", "")).startswith("msg-")

    @staticmethod
    def _source_text(lead_data: Dict[str, Any]) -> str:
        return str(lead_data.get("analysis", {}).get("source_text") or lead_data.get("raw_text", ""))

    @staticmethod
    def _detect_course(text: str) -> str:
        if "data science" in text:
            return "Data Science"
        if "ai" in text or "artificial intelligence" in text:
            return "AI"
        if "python" in text:
            return "Python"
        if "marketing" in text:
            return "Digital Marketing"
        return "Unknown"

    @staticmethod
    def _detect_timeline(text: str) -> str:
        if "asap" in text or "immediately" in text:
            return "ASAP"
        if "next month" in text:
            return "Next month"
        if "two weeks" in text or "2 weeks" in text:
            return "Within two weeks"
        if "tomorrow" in text:
            return "Immediate"
        return "Flexible"

    @staticmethod
    def _detect_budget(text: str) -> str:
        match = re.search(r"(\$\s*\d+|\d+\s*dollars?|\d+\s*usd|\b\d{3,4}\b)", text, re.IGNORECASE)
        return match.group(1).upper() if match else "Unknown"

    @staticmethod
    def _detect_contact_channel(text: str, source: str) -> str:
        if "whatsapp" in text or source == "whatsapp":
            return "WhatsApp"
        if "email" in text or source == "email":
            return "Email"
        return "Email"

    @staticmethod
    def _detect_intent(text: str) -> str:
        if "scholarship" in text:
            return "scholarship_inquiry"
        if "price" in text or "fee" in text or "cost" in text:
            return "pricing_check"
        if "enroll" in text or "register" in text or "join" in text or "admission" in text:
            return "enrollment_request"
        return "course_inquiry"

    def _make_tool_call(self, name: str, args: dict) -> LlmResponse:
        function_call = types.FunctionCall(name=name, args=args)
        part = types.Part(function_call=function_call)
        content = types.Content(role="model", parts=[part])
        return LlmResponse(content=content, partial=False, model_version="mock-adk")

    def _make_text_response(self, text: str) -> LlmResponse:
        part = types.Part(text=text)
        content = types.Content(role="model", parts=[part])
        return LlmResponse(content=content, partial=False, model_version="mock-adk")


LLMRegistry.register(MockLeadManagementLLM)


def _shared_model_name() -> str:
    nvidia_key = os.getenv("NVIDIA_API_KEY")
    if "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ:
        logger.info("ADK pipeline using local mock model.")
        return "mock-adk-model"
    if nvidia_key in ("vertexai", "gemini"):
        # Native ADK Gemini support via Vertex AI (using authenticated gcloud credentials)
        return "vertex_ai/gemini-2.5-flash"
    if not nvidia_key:
        raise RuntimeError("NVIDIA_API_KEY is required for the ADK agents to use the live NVIDIA API.")

    os.environ["OPENAI_API_KEY"] = nvidia_key
    nvidia_base_url = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
    os.environ["OPENAI_API_BASE"] = nvidia_base_url
    os.environ["OPENAI_BASE_URL"] = nvidia_base_url
    return f"openai/{os.getenv('NVIDIA_MODEL', 'nvidia/nemotron-3-nano-omni-30b-a3b-reasoning')}"


MODEL_NAME = _shared_model_name()


source_intake_agent = LlmAgent(
    name="SourceIntakeAgent",
    description="Loads the raw enquiry from Firestore and Gmail when needed.",
    model=MODEL_NAME,
    instruction=(
        "You are SourceIntakeAgent.\n"
        "Use one shared model only. Extract the lead_id from the user message.\n"
        "Call complete_source_intake exactly once with that lead_id. Do not call any other tool or write any other stage."
    ),
    tools=[complete_source_intake],
    output_key="source_intake_result",
    timeout=30.0,
)

lead_analysis_agent = LlmAgent(
    name="LeadAnalysisAgent",
    description="Extracts structured lead data and intent from the source enquiry.",
    model=MODEL_NAME,
    instruction=(
        "You are LeadAnalysisAgent.\n"
        "Analyze the lead's profile (obtainable via get_lead tool) and extract the following parameters:\n"
        "- course: course of interest (e.g. AI, Data Science, Python, DevOps, Web Development, Unknown)\n"
        "- timeline: preferred start timeline (e.g. Next month, Within two weeks, ASAP, Flexible)\n"
        "- budget: specified budget (e.g. $1500, Unknown)\n"
        "- contact_channel: preferred contact channel (e.g. Email, WhatsApp, Phone). Check the 'source' field of the lead profile. If 'source' is 'whatsapp', default contact_channel to WhatsApp. If 'source' is 'email', default contact_channel to Email. If the message text explicitly asks for a different channel, use that.\n"
        "- intent: intent classification (e.g. course_inquiry, pricing_check, scholarship_inquiry, enrollment_request)\n\n"
        "Call complete_lead_analysis exactly once with the lead_id and these extracted parameters. Do not score, recommend, or draft messages."
    ),
    tools=[get_lead, complete_lead_analysis],
    output_key="analysis_result",
    timeout=30.0,
)

lead_scoring_agent = LlmAgent(
    name="LeadScoringAgent",
    description="Classifies the lead as HOT, WARM, or COLD with explainable reasoning.",
    model=MODEL_NAME,
    instruction=(
        "You are LeadScoringAgent.\n"
        "Retrieve the lead using get_lead to inspect the extracted_data and intent.\n"
        "Calculate the score based on these rules:\n"
        "- Course: High demand (AI, Data Science, DevOps, Python) adds +15 points\n"
        "- Timeline: Urgent (ASAP, Immediate, Next week, Within two weeks) adds +20 points\n"
        "- Budget: Known budget details add +15 points\n"
        "- Intent: High buying intent (pricing_check, enrollment_request) adds +10 points\n\n"
        "Define the category as 'HOT' if total score >= 80, 'WARM' if 50-79, or 'COLD' if < 50. Total score starts at 40 points base.\n"
        "Call complete_lead_scoring with the category, points, and reasoning summary. Do not update recommendations or drafts."
    ),
    tools=[get_lead, complete_lead_scoring],
    output_key="scoring_result",
    timeout=30.0,
)

recommendation_agent = LlmAgent(
    name="RecommendationAgent",
    description="Recommends the next sales or admissions step.",
    model=MODEL_NAME,
    instruction=(
        "You are RecommendationAgent.\n"
        "Retrieve the lead profile using get_lead.\n"
        "Determine the admissions next action based on score category:\n"
        "- HOT: 'Call today'\n"
        "- WARM: 'Assign senior counsellor'\n"
        "- COLD: 'Send nurture email'\n\n"
        "Write a custom, personalized explanation for the 'details' field explaining why this action is recommended (e.g., state the specific course of interest, mention the urgency of their timeline such as starting ASAP, and outline what the counselor should do). Do not copy generic template text.\n"
        "Call complete_recommendation with the action and details. Do not draft messages."
    ),
    tools=[get_lead, complete_recommendation],
    output_key="recommendation_result",
    timeout=30.0,
)

communication_agent = LlmAgent(
    name="CommunicationAgent",
    description="Drafts follow-up email and WhatsApp messages for human approval.",
    model=MODEL_NAME,
    instruction=(
        "You are CommunicationAgent.\n"
        "Retrieve the lead using get_lead.\n"
        "Draft a highly personalized outreach email subject, email body, and WhatsApp body addressing the customer's specific course of interest, timeline, and the recommended admissions action.\n"
        "Call complete_communication_draft with the email_subject, email_body, and whatsapp_body."
    ),
    tools=[get_lead, complete_communication_draft],
    output_key="communication_result",
    timeout=30.0,
)

adk_pipeline = SequentialAgent(
    name="LeadManagementSequentialAgent",
    description="Google ADK multi-agent lead workflow using one shared LLM and Firestore storage.",
    sub_agents=[
        source_intake_agent,
        lead_analysis_agent,
        lead_scoring_agent,
        recommendation_agent,
        communication_agent,
    ],
    timeout=120.0,
)
