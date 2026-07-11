import json
from pydantic import BaseModel, Field
from typing import Any

class DetectedIntent(BaseModel):
    intent: str = Field(description="Detected primary intent (e.g. 'course_inquiry', 'pricing_check', 'scholarship_inquiry', 'enrollment_request', 'other')")
    confidence: float = Field(default=0.8, description="Confidence score from 0.0 to 1.0")

class IntentDetectionSkill:
    """
    Skill to detect the primary intent of the lead inquiry.
    """
    def __init__(self, llm: Any):
        self.llm = llm

    def execute(self, raw_text: str) -> DetectedIntent:
        prompt = (
            "You are an intake classifier for an education/course company.\n"
            "Classify the lead's enquiry into one of these intents:\n"
            "- course_inquiry: General questions about courses, curriculum, schedule, or teachers.\n"
            "- pricing_check: Specific questions about cost, pricing, fees, installment plans.\n"
            "- scholarship_inquiry: Questions about discounts, scholarships, financial aid.\n"
            "- enrollment_request: Expressing direct interest to register, sign up, or start immediately.\n"
            "- other: Spam, irrelevant, or general greetings.\n\n"
            f"Inquiry: \"{raw_text}\"\n\n"
            "Format the output strictly as a JSON object with keys: "
            "\"intent\", \"confidence\"."
        )
        
        try:
            if hasattr(self.llm, "with_structured_output"):
                structured_llm = self.llm.with_structured_output(DetectedIntent)
                return structured_llm.invoke(prompt)
            
            response = self.llm.invoke(prompt)
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            data = json.loads(content)
            return DetectedIntent(**data)
        except Exception as e:
            # Simple fallback
            intent = "course_inquiry"
            if "price" in raw_text.lower() or "fee" in raw_text.lower() or "cost" in raw_text.lower():
                intent = "pricing_check"
            elif "scholarship" in raw_text.lower() or "discount" in raw_text.lower():
                intent = "scholarship_inquiry"
            return DetectedIntent(intent=intent, confidence=0.7)
