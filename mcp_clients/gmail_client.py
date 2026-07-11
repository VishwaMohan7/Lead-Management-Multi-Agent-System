from typing import Optional
from mcp_clients.base_client import BaseMCPClient, logger

class GmailMCPClient(BaseMCPClient):
    """
    Gmail MCP Client wrapper.
    Reads original email enquiries and sends draft messages.
    """
    def __init__(self, mock_mode: bool = True):
        super().__init__("GmailMCP", mock_mode)

    def get_email_content(self, email_id: str) -> Optional[dict]:
        """
        Reads email details (sender, subject, body).
        In mock mode, retrieves mock email data based on the email_id.
        """
        self.log_call("get_email", {"email_id": email_id})
        if not self.mock_mode:
            raise NotImplementedError("Real Gmail connection not configured.")
        
        # Simulated inbox
        mock_emails = {
            "msg-001": {
                "id": "msg-001",
                "sender": "student.john@gmail.com",
                "subject": "Inquiry about AI Course",
                "body": "Hello, I am interested in joining the advanced AI course starting next month. Can you share the fee details and whether there is any scholarship available for students with coding experience? Thanks, John."
            },
            "msg-002": {
                "id": "msg-002",
                "sender": "sarah.smith@yahoo.com",
                "subject": "Data Science Boot Camp",
                "body": "Hi there, I want to know if the Data Science Boot Camp is online or in-person. I need to start within two weeks because of my current job transition. My budget is around $1500. Let me know the schedule."
            }
        }
        return mock_emails.get(email_id, {
            "id": email_id,
            "sender": "unknown@example.com",
            "subject": "Lead Enquiry",
            "body": "Please provide more details on available courses."
        })

    def send_email(self, recipient: str, subject: str, body: str) -> bool:
        """
        Sends an email via Gmail.
        In mock mode, simulates delivery and logs details.
        """
        self.log_call("send_message", {"to": recipient, "subject": subject, "body_preview": body[:60] + "..."})
        if self.mock_mode:
            logger.info(f"--- SIMULATING GMAIL SEND ---")
            logger.info(f"To: {recipient}")
            logger.info(f"Subject: {subject}")
            logger.info(f"Body:\n{body}")
            logger.info(f"-----------------------------")
            return True
        return False
