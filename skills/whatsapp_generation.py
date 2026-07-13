import json
from pydantic import BaseModel, Field
from typing import Any, Dict

class WhatsAppDraft(BaseModel):
    body: str = Field(description="Body of the WhatsApp message")

class WhatsAppGenerationSkill:
    """
    Skill to generate personalized WhatsApp message drafts.
    """
    def __init__(self, llm: Any):
        self.llm = llm

    def execute(self, score_category: str, recommendation: str, extracted_data: Dict[str, str]) -> WhatsAppDraft:
        course = extracted_data.get("course", "our courses")
        timeline = extracted_data.get("timeline", "flexible timeline")

        prompt = (
            "You are a modern customer relations assistant. Draft a WhatsApp message to a prospective learner with the following info:\n"
            f"Course: {course}\n"
            f"Timeline: {timeline}\n"
            f"Lead Rating: {score_category}\n"
            f"Admissions Recommendation: {recommendation}\n\n"
            "Rules for Draft:\n"
            "- Short, casual, and polite (max 3 sentences).\n"
            "- Use relevant emojis (like 🚀, 📚, 👋).\n"
            "- Include a direct call to action.\n\n"
            "Format the output strictly as a JSON object with keys: "
            "\"body\"."
        )

        try:
            if hasattr(self.llm, "with_structured_output"):
                structured_llm = self.llm.with_structured_output(WhatsAppDraft)
                return structured_llm.invoke(prompt)

            response = self.llm.invoke(prompt)
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            data = json.loads(content)
            return WhatsAppDraft(**data)
        except Exception as e:
            import openai
            if isinstance(e, (openai.APIError, openai.APITimeoutError, openai.RateLimitError, openai.APIConnectionError)):
                raise e
            # Fallback draft
            body = f"Hi! 👋 Thanks for inquiring about our {course} program. Let's schedule a brief call to talk about starting {timeline}! 🚀"
            return WhatsAppDraft(body=body)
