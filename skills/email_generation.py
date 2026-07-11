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
            "You are a helpful admissions writer. Draft an outbound email to a prospective learner with the following info:\n"
            f"Email: {lead_email}\n"
            f"Course: {course}\n"
            f"Timeline: {timeline}\n"
            f"Lead Rating: {score_category}\n"
            f"Admissions Recommendation: {recommendation}\n\n"
            "Rules for Draft:\n"
            "- Friendly, professional tone.\n"
            "- If Lead Rating is HOT, convey excitement and refer to the specific action (like scheduling a demo or calling).\n"
            "- Provide a clear next step (e.g. 'A counsellor will call you shortly').\n"
            "- Sign off as the 'Lead Management Admissions Team'.\n\n"
            "Format the output strictly as a JSON object with keys: "
            "\"subject\", \"body\"."
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
            # Fallback draft
            subject = f"Welcome to our {course} program!"
            body = (
                f"Hi,\n\n"
                f"Thank you for contacting us regarding our {course} program. We see that you are planning to start {timeline}.\n"
                f"Our advisor has recommended: '{recommendation}'. We will be in touch with you shortly to finalize details.\n\n"
                f"Best regards,\nAdmissions Team"
            )
            return EmailDraft(subject=subject, body=body)
