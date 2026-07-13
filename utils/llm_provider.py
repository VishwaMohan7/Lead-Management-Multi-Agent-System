import os
import re
import json
from typing import Any, List, Optional, Union
from pydantic import BaseModel, Field

# Try importing LangChain libraries. If they are still installing, we will catch it.
try:
    from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI
except ImportError:
    class BaseMessage: pass
    class AIMessage:
        def __init__(self, content: str):
            self.content = content
    class HumanMessage: pass
    class SystemMessage: pass
    class ChatOpenAI: pass

# Environment configuration
from dotenv import load_dotenv
load_dotenv()

_LLM_CACHE: dict[tuple[Optional[str], Optional[str], Optional[str], float], Any] = {}

class MockAIMessage:
    def __init__(self, content: str):
        self.content = content

class MockLLM:
    """
    Mock LLM that parses the prompt or messages and returns 
    realistic responses based on keywords. Perfect for offline testing.
    """
    def __init__(self):
        pass

    def invoke(self, messages: Any) -> MockAIMessage:
        # Convert messages to text to analyze
        prompt_text = ""
        if isinstance(messages, str):
            prompt_text = messages
        elif isinstance(messages, list):
            for m in messages:
                if hasattr(m, 'content'):
                    prompt_text += f"\n{m.content}"
                elif isinstance(m, dict):
                    prompt_text += f"\n{m.get('content', '')}"
                else:
                    prompt_text += f"\n{str(m)}"
        else:
            prompt_text = str(messages)

        prompt_text_lower = prompt_text.lower()
        response_content = ""

        # Check if the prompt is asking for Lead Extraction / Structured analysis
        if "extract" in prompt_text_lower or "structured" in prompt_text_lower or "course" in prompt_text_lower:
            # Extract Inquiry block to avoid matching instructions
            inquiry_text = prompt_text_lower
            inquiry_match = re.search(r'inquiry:\s*"(.*?)"', prompt_text_lower)
            if not inquiry_match:
                inquiry_match = re.search(r'inquiry:\s*(.*)', prompt_text_lower)
            if inquiry_match:
                inquiry_text = inquiry_match.group(1).strip()

            # Simple rule-based extraction
            course = "Unknown"
            if "ai" in inquiry_text:
                course = "AI"
            elif "data science" in inquiry_text:
                course = "Data Science"
            elif "python" in inquiry_text:
                course = "Python"
            elif "marketing" in inquiry_text:
                course = "Digital Marketing"

            timeline = "Flexible"
            if "next month" in inquiry_text:
                timeline = "Next month"
            elif "two weeks" in inquiry_text or "2 weeks" in inquiry_text:
                timeline = "Within two weeks"
            elif "asap" in inquiry_text or "immediately" in inquiry_text:
                timeline = "ASAP"
            elif "tomorrow" in inquiry_text:
                timeline = "Immediate"

            budget = "Unknown"
            price_match = re.search(r"(\$\s*\d+|\d+\s*dollars?|\d+\s*usd|\b\d{3,4}\b)", inquiry_text)
            if price_match:
                budget = price_match.group(1).upper()

            contact_channel = "Email"
            if "whatsapp" in inquiry_text or "phone" in inquiry_text:
                contact_channel = "WhatsApp"
            elif "email" in inquiry_text:
                contact_channel = "Email"

            intent = "course_inquiry"
            if "price" in inquiry_text or "fee" in inquiry_text or "cost" in inquiry_text:
                intent = "pricing_check"
            elif "scholarship" in inquiry_text:
                intent = "scholarship_inquiry"
            elif "enroll" in inquiry_text or "register" in inquiry_text or "join" in inquiry_text:
                intent = "enrollment_request"

            structured_output = {
                "course": course,
                "timeline": timeline,
                "budget": budget,
                "contact_channel": contact_channel,
                "intent": intent
            }
            # Return json string
            response_content = json.dumps(structured_output)

        # Check if the prompt is asking for Lead Scoring
        elif "score" in prompt_text_lower or "points" in prompt_text_lower:
            # Rule-based scoring
            score_points = 50
            if "next month" in prompt_text_lower or "two weeks" in prompt_text_lower or "asap" in prompt_text_lower:
                score_points += 20
            if "ai" in prompt_text_lower or "data science" in prompt_text_lower:
                score_points += 15
            if "budget" in prompt_text_lower or "$" in prompt_text_lower or "1500" in prompt_text_lower:
                score_points += 10
            
            category = "COLD"
            if score_points >= 80:
                category = "HOT"
            elif score_points >= 50:
                category = "WARM"

            scoring_output = {
                "category": category,
                "score": min(score_points, 100),
                "reason": f"Lead shows high interest in target courses with specified details. Base score calculation: {score_points}."
            }
            response_content = json.dumps(scoring_output)

        # Check if the prompt is for Outbound Communication drafting
        elif "draft" in prompt_text_lower or "email" in prompt_text_lower or "whatsapp" in prompt_text_lower:
            # Detect what details we have
            course = "our program"
            if "ai" in prompt_text_lower:
                course = "AI"
            elif "data science" in prompt_text_lower:
                course = "Data Science"

            email_subject = f"Welcome to our {course} program!" if course != "our program" else "Welcome to our program"
            email_body = (
                f"Hi,\n\n"
                f"Thanks for reaching out! We are thrilled to hear about your interest in our {course} program.\n"
                f"A course counselor will review your request and contact you soon regarding scheduling and enrollment.\n\n"
                f"Best regards,\nAdmissions Team"
            )
            whatsapp_body = f"Hi! Thanks for inquiring about the {course} program. A counselor will get in touch with you shortly on WhatsApp to answer your questions. Let us know if you have a preferred time to connect!"

            comm_output = {
                "email_subject": email_subject,
                "email_body": email_body,
                "whatsapp_body": whatsapp_body
            }
            response_content = json.dumps(comm_output)
            
        else:
            # Fallback response
            response_content = "This is a mock LLM response. Let us know how we can assist you."

        return MockAIMessage(content=response_content)

def get_llm(temperature: float = 0.0) -> Any:
    """
    Returns the Nvidia Nemotron LLM client using OpenAI compatibility interface.
    Falls back to MockLLM if NVIDIA_API_KEY is not configured or in tests.
    """
    import sys
    if "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ:
        if os.getenv("NVIDIA_API_KEY") != "fake_test_key_12345":
            return MockLLM()

    api_key = os.getenv("NVIDIA_API_KEY")
    model_name = os.getenv("NVIDIA_MODEL", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning")
    base_url = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
    cache_key = (api_key, model_name if api_key else None, base_url if api_key else None, temperature)

    if cache_key in _LLM_CACHE:
        return _LLM_CACHE[cache_key]

    if api_key:
        llm = ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_retries=1,
            timeout=15.0
        )
    else:
        llm = MockLLM()

    _LLM_CACHE[cache_key] = llm
    return llm
