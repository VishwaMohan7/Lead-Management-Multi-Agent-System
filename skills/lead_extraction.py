import json
from pydantic import BaseModel, Field
from typing import Any

class ExtractedLeadFields(BaseModel):
    course: str = Field(default="Unknown", description="The course of interest (e.g. 'AI', 'Data Science', 'Python', 'Unknown')")
    timeline: str = Field(default="Flexible", description="Desired start timeline (e.g. 'Next month', 'Within two weeks', 'ASAP', 'Flexible')")
    budget: str = Field(default="Unknown", description="Specified budget if any, e.g. '$1500', otherwise 'Unknown'")
    contact_channel: str = Field(default="Email", description="Preferred contact channel (e.g. 'Email', 'WhatsApp', 'Phone')")

class LeadExtractionSkill:
    """
    Skill to extract structured data from raw lead text.
    """
    def __init__(self, llm: Any):
        self.llm = llm

    def execute(self, raw_text: str) -> ExtractedLeadFields:
        prompt = (
            "You are an expert lead intake assistant for an education company.\n"
            "Extract the following structured fields from the raw inquiry text:\n"
            "- course: course of interest (e.g., AI, Data Science, Python, Web Development, Unknown)\n"
            "- timeline: target starting date or timeframe (e.g., Next month, Within two weeks, ASAP, Flexible)\n"
            "- budget: specified budget (e.g., $1500, Unknown)\n"
            "- contact_channel: preferred contact channel (e.g., Email, WhatsApp, Phone)\n\n"
            f"Inquiry: \"{raw_text}\"\n\n"
            "Format the output strictly as a JSON object with keys: "
            "\"course\", \"timeline\", \"budget\", \"contact_channel\"."
        )
        
        try:
            # Check if LLM supports structured outputs (LangChain native helper)
            if hasattr(self.llm, "with_structured_output"):
                structured_llm = self.llm.with_structured_output(ExtractedLeadFields)
                return structured_llm.invoke(prompt)
            
            # Fallback to standard invoke + json parse
            response = self.llm.invoke(prompt)
            content = response.content.strip()
            
            # Clean up potential markdown formatting block if present
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            data = json.loads(content)
            return ExtractedLeadFields(**data)
        except Exception as e:
            # Safe parsing fallback using regex/defaults
            return ExtractedLeadFields(
                course="AI" if "ai" in raw_text.lower() else "Unknown",
                timeline="Next month" if "next month" in raw_text.lower() else "Flexible",
                budget="Unknown",
                contact_channel="Email"
            )
