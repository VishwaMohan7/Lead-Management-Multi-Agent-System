import json
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional
from mcp_clients.base_client import logger

class RecommendationResult(BaseModel):
    action: str = Field(description="Recommended action (e.g., 'Call today', 'Assign senior counsellor', 'Schedule demo', 'Send info email')")
    details: str = Field(description="Detailed plan or justification for the recommended action")
    calendar_event: Optional[Dict] = Field(default=None, description="Calendar event details if a slot was scheduled")

class RecommendationSkill:
    """
    Skill to determine the next best action for a lead.
    If a demo needs scheduling (HOT leads with urgent timeline), uses Google Calendar MCP to find slots and schedule.
    """
    def __init__(self, llm: Any, calendar_client: Any):
        self.llm = llm
        self.calendar_client = calendar_client

    def execute(self, lead_id: str, lead_email: str, score_category: str, score_points: int, extracted_data: Dict[str, str]) -> RecommendationResult:
        # Determine base recommended action
        course = extracted_data.get("course", "Unknown")
        timeline = extracted_data.get("timeline", "Flexible")
        
        # Determine if we need to schedule a calendar demo call
        schedule_demo_needed = False
        base_action = "Send info email"
        
        if score_category == "HOT":
            if any(kw in timeline.lower() for kw in ["asap", "immediate", "next week", "two weeks"]):
                schedule_demo_needed = True
                base_action = "Schedule demo"
            else:
                base_action = "Call today"
        elif score_category == "WARM":
            base_action = "Assign senior counsellor"
        else:
            base_action = "Send info email"

        calendar_event = None
        if schedule_demo_needed:
            # Query availability from Calendar MCP
            try:
                available_slots = self.calendar_client.check_availability("tomorrow")
                if available_slots:
                    # Select the first slot for demonstration
                    chosen_slot = available_slots[0]
                    # Schedule the meeting
                    calendar_event = self.calendar_client.schedule_meeting(
                        attendee_email=lead_email or "learner@example.com",
                        title=f"Course Consultation: {course} Program",
                        start_time=f"Tomorrow at {chosen_slot}",
                        duration_minutes=30
                    )
            except Exception as e:
                logger.error(f"Error calling Calendar MCP: {e}")

        prompt = (
            "You are an admissions strategist. Review the current lead recommendation plan:\n"
            f"Course Interest: {course}\n"
            f"Timeline: {timeline}\n"
            f"Score Category: {score_category} ({score_points} pts)\n"
            f"Base Action Recommended: {base_action}\n"
            f"Calendar Event: {json.dumps(calendar_event) if calendar_event else 'None'}\n\n"
            "Formulate a concise admissions next best action plan. Explain exactly what the next steps are and why.\n"
            "Format the output strictly as a JSON object with keys: "
            "\"action\", \"details\"."
        )

        try:
            if hasattr(self.llm, "with_structured_output"):
                structured_llm = self.llm.with_structured_output(RecommendationResult)
                res = structured_llm.invoke(prompt)
                if calendar_event:
                    res.calendar_event = calendar_event
                return res

            response = self.llm.invoke(prompt)
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            data = json.loads(content)
            return RecommendationResult(
                action=data.get("action", base_action),
                details=data.get("details", f"Follow up with lead on course {course}."),
                calendar_event=calendar_event
            )
        except Exception as e:
            details = f"Follow up on course {course}. Lead is {score_category}."
            if calendar_event:
                details += f" A Zoom consult has been pre-scheduled for {calendar_event.get('start_time')}."
            return RecommendationResult(
                action=base_action,
                details=details,
                calendar_event=calendar_event
            )
