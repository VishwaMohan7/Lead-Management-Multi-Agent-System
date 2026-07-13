import os
import json
from mcp.server.fastmcp import FastMCP
from mcp_clients.firestore_client import FirestoreMCPClient
from mcp_clients.gmail_client import GmailMCPClient
from mcp_clients.whatsapp_client import WhatsAppMCPClient
from mcp_clients.calendar_client import CalendarMCPClient

# Initialize MCP Server
mcp = FastMCP("LeadManagementMCPServer")

# Initialize the mock clients
use_mock_gmail = os.getenv("USE_MOCK_GMAIL", "true").lower() == "true"
firestore_client = FirestoreMCPClient()
gmail_client = GmailMCPClient(mock_mode=use_mock_gmail)
whatsapp_client = WhatsAppMCPClient(mock_mode=True)
calendar_client = CalendarMCPClient(mock_mode=True)

# ----------------- FIRESTORE TOOLS -----------------

@mcp.tool()
def create_lead(raw_text: str, source: str) -> dict:
    """
    Creates a new lead document in the database with initial state.
    
    Args:
        raw_text (str): The raw inquiry message content.
        source (str): The ingestion source (e.g. 'email', 'whatsapp', 'webform').
    """
    return firestore_client.create_lead(raw_text, source)

@mcp.tool()
def get_lead(lead_id: str) -> dict:
    """
    Retrieves a lead document from the database by its ID.
    
    Args:
        lead_id (str): The UUID of the lead.
    """
    lead = firestore_client.get_lead(lead_id)
    if not lead:
        return {"error": f"Lead {lead_id} not found"}
    return lead

@mcp.tool()
def update_lead(lead_id: str, updates: dict, event_name: str = "lead_updated") -> dict:
    """
    Updates specific fields on a lead document in the database and appends to its history.
    
    Args:
        lead_id (str): The UUID of the lead.
        updates (dict): Key-value pairs to merge or write to the lead document.
        event_name (str): Description of the update event (e.g. 'analysis_completed').
    """
    lead = firestore_client.update_lead(lead_id, updates, event_name)
    if not lead:
        return {"error": f"Lead {lead_id} not found"}
    return lead

@mcp.tool()
def get_all_leads() -> list:
    """
    Retrieves all lead documents stored in the database.
    """
    return firestore_client.get_all_leads()


# ----------------- GMAIL TOOLS -----------------

@mcp.tool()
def get_email_content(email_id: str) -> dict:
    """
    Retrieves the sender, subject, and body of a raw email message.
    
    Args:
        email_id (str): The unique ID of the email message.
    """
    email_data = gmail_client.get_email_content(email_id)
    if not email_data:
        return {"error": f"Email {email_id} not found"}
    return email_data

@mcp.tool()
def send_email_draft(to_email: str, subject: str, body: str) -> dict:
    """
    Dispatches a real outbound email to a recipient.
    
    Args:
        to_email (str): The recipient's email address.
        subject (str): The subject line of the email.
        body (str): The body text of the email.
    """
    return gmail_client.send_email(to_email, subject, body)


# ----------------- WHATSAPP TOOLS -----------------

@mcp.tool()
def send_whatsapp_message(phone: str, body: str) -> dict:
    """
    Dispatches a WhatsApp outreach message to a recipient.
    
    Args:
        phone (str): The recipient's phone number.
        body (str): The message text.
    """
    return whatsapp_client.send_message(phone, body)


# ----------------- GOOGLE CALENDAR TOOLS -----------------

@mcp.tool()
def check_availability(date_str: str) -> list:
    """
    Checks calendar availability slots for a specific date.
    
    Args:
        date_str (str): Target date in YYYY-MM-DD format.
    """
    return calendar_client.check_availability(date_str)

@mcp.tool()
def schedule_meeting(attendee_email: str, title: str, start_time: str, duration_minutes: int = 30) -> dict:
    """
    Schedules an event on Google Calendar.
    
    Args:
        attendee_email (str): The email address of the attendee.
        title (str): The event title.
        start_time (str): The starting time slot.
        duration_minutes (int): Event duration in minutes.
    """
    return calendar_client.schedule_event(
        attendee_email=attendee_email,
        title=title,
        start_time=start_time,
        duration_minutes=duration_minutes
    )

if __name__ == "__main__":
    mcp.run()
