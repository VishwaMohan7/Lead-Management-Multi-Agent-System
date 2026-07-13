import json
from pydantic import BaseModel, Field
from typing import Any, Dict

class EmailDraft(BaseModel):
    subject: str = Field(description="Subject line for the outbound email")
    body: str = Field(description="Body text of the outbound email")

class EmailGenerationSkill:
    """
    Skill to generate personalized email drafts for the lead.
    """
    def __init__(self, llm: Any):
        self.llm = llm

    def execute(self, lead_email: str, score_category: str, recommendation: str, extracted_data: Dict[str, str]) -> EmailDraft:
        course = extracted_data.get("course", "our courses")
        timeline = extracted_data.get("timeline", "flexible timeline")

        prompt = (
            "You are a helpful admissions writer. Draft an outbound email from the 'Lead Management Admissions Team' to a prospective learner.\n\n"
            "Lead Info:\n"
            f"- Learner Email: {lead_email}\n"
            f"- Interested Course: {course}\n"
            f"- Starting Timeline: {timeline}\n"
            f"- Lead Rating: {score_category}\n"
            f"- Admissions Recommendation: {recommendation}\n\n"
            "Instructions:\n"
            "1. Address the email directly to the prospective learner (do not write it to the admissions team).\n"
            "2. Write in a friendly, professional tone.\n"
            "3. If the Lead Rating is HOT, convey excitement and mention the recommendation details.\n"
            "4. Provide a clear next step for the learner.\n"
            "5. Do NOT include instructions, rules, or JSON formatting instructions in your output subject or body.\n"
            "6. Sign off as 'Lead Management Admissions Team'.\n\n"
            "Format the output strictly as a JSON object with keys: \"subject\" and \"body\"."
        )

        try:
            if hasattr(self.llm, "with_structured_output"):
                structured_llm = self.llm.with_structured_output(EmailDraft)
                return structured_llm.invoke(prompt)

            response = self.llm.invoke(prompt)
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            data = json.loads(content)
            return EmailDraft(**data)
        except Exception as e:
            import openai
            if isinstance(e, (openai.APIError, openai.APITimeoutError, openai.RateLimitError, openai.APIConnectionError)):
                raise e
            # Fallback draft
            subject = f"Welcome to our {course} program!"
            body = (
                f"Hi,\n\n"
                f"Thank you for contacting us regarding our {course} program. We see that you are planning to start {timeline}.\n"
                f"Our advisor has recommended: '{recommendation}'. We will be in touch with you shortly to finalize details.\n\n"
                f"Best regards,\nAdmissions Team"
            )
            return EmailDraft(subject=subject, body=body)
