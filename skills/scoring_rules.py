import json
from pydantic import BaseModel, Field
from typing import Any, Dict

class LeadScoreResult(BaseModel):
    category: str = Field(description="Scoring category (HOT, WARM, COLD)")
    score: int = Field(description="Numerical score from 0 to 100")
    reasoning: str = Field(description="Detailed explanation of how the score was calculated")

class ScoringRulesSkill:
    """
    Skill to score leads based on business rules and LLM evaluation.
    Business Rules:
    - High priority courses (AI, Data Science) +15 points
    - Urgent timelines (ASAP, Immediate, Next week) +20 points
    - Known budget (not 'Unknown') +15 points
    - High intent (pricing_check, enrollment_request) +10 points
    """
    def __init__(self, llm: Any):
        self.llm = llm

    def execute(self, extracted_data: Dict[str, str], intent: str) -> LeadScoreResult:
        # 1. Base Score calculation using deterministic business rules
        base_score = 40
        rules_log = []

        course = extracted_data.get("course", "Unknown").lower()
        if course in ["ai", "data science", "python", "machine learning"]:
            base_score += 15
            rules_log.append("High-demand course interest (+15)")
        
        timeline = extracted_data.get("timeline", "Flexible").lower()
        if any(kw in timeline for kw in ["asap", "immediate", "next week", "within two weeks"]):
            base_score += 20
            rules_log.append("Urgent start timeline (+20)")
        elif "flexible" not in timeline:
            base_score += 10
            rules_log.append("Moderate start timeline (+10)")

        budget = extracted_data.get("budget", "Unknown").lower()
        if budget != "unknown" and len(budget) > 0:
            base_score += 15
            rules_log.append("Budget details provided (+15)")

        if intent in ["pricing_check", "enrollment_request"]:
            base_score += 10
            rules_log.append("High buying intent category (+10)")

        base_score = min(base_score, 100)

        # 2. Ask the LLM to refine the score or validate the reasoning
        prompt = (
            "You are a lead scoring specialist. Review the following lead profile and rule-based score:\n"
            f"Extracted Profile: {json.dumps(extracted_data)}\n"
            f"Intent: {intent}\n"
            f"Calculated Base Score: {base_score}/100\n"
            f"Rule Log: {', '.join(rules_log)}\n\n"
            "Assess if the score is fair. Keep it closely aligned with the rules but refine it up or down by +/- 5 points based on your qualitative evaluation.\n"
            "Provide the final score, the corresponding category (HOT for >=80, WARM for 50-79, COLD for <50), and a concise summary of the reasoning.\n\n"
            "Format the output strictly as a JSON object with keys: "
            "\"category\", \"score\", \"reasoning\"."
        )

        try:
            if hasattr(self.llm, "with_structured_output"):
                structured_llm = self.llm.with_structured_output(LeadScoreResult)
                return structured_llm.invoke(prompt)

            response = self.llm.invoke(prompt)
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            data = json.loads(content)
            # Ensure the score is within 0-100 bounds
            data["score"] = max(0, min(100, int(data["score"])))
            return LeadScoreResult(**data)
        except Exception as e:
            # Fallback based on deterministic rules
            category = "COLD"
            if base_score >= 80:
                category = "HOT"
            elif base_score >= 50:
                category = "WARM"
            return LeadScoreResult(
                category=category,
                score=base_score,
                reasoning=f"Calculated automatically using business rules: {', '.join(rules_log)}."
            )
