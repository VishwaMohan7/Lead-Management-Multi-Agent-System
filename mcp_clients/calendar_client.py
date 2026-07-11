from typing import List, Dict
from mcp_clients.base_client import BaseMCPClient, logger

class CalendarMCPClient(BaseMCPClient):
    """
    Google Calendar MCP Client wrapper.
    Checks availability and schedules meetings/calls.
    """
    def __init__(self, mock_mode: bool = True):
        super().__init__("GoogleCalendarMCP", mock_mode)

    def check_availability(self, date_str: str) -> List[str]:
        """
        Retrieves open time slots for a given date.
        """
        self.log_call("list_free_slots", {"date": date_str})
        if self.mock_mode:
            # Return some mock slots
            return ["10:00 AM", "11:30 AM", "2:00 PM", "4:30 PM"]
        return []

    def schedule_meeting(self, attendee_email: str, title: str, start_time: str, duration_minutes: int = 30) -> Dict:
        """
        Schedules a calendar event.
        """
        self.log_call("create_event", {
            "attendee": attendee_email,
            "title": title,
            "start": start_time,
            "duration": duration_minutes
        })
        if self.mock_mode:
            logger.info(f"--- SIMULATING CALENDAR SCHEDULE ---")
            logger.info(f"Event: {title}")
            logger.info(f"Attendee: {attendee_email}")
            logger.info(f"Time: {start_time} ({duration_minutes} mins)")
            logger.info(f"------------------------------------")
            return {
                "event_id": "evt_mock_12345",
                "status": "confirmed",
                "start_time": start_time,
                "meet_link": "https://meet.google.com/mock-meet-abc"
            }
        return {}
