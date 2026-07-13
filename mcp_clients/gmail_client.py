import os
import smtplib
import imaplib
import email
from email.header import decode_header
from email.mime.text import MIMEText
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
        In real mode, connects via IMAP to fetch the email content.
        """
        self.log_call("get_email", {"email_id": email_id})
        if not self.mock_mode:
            gmail_user = os.getenv("GMAIL_USER")
            gmail_password = os.getenv("GMAIL_APP_PASSWORD")
            if not gmail_user or not gmail_password:
                raise ValueError("GMAIL_USER and GMAIL_APP_PASSWORD must be configured in .env for real Gmail mode.")
            
            try:
                # Connect to Gmail IMAP
                mail = imaplib.IMAP4_SSL("imap.gmail.com")
                mail.login(gmail_user, gmail_password)
                mail.select("inbox")

                status, messages = mail.search(None, "ALL")
                if status != "OK":
                    raise RuntimeError("Failed to search IMAP messages.")

                mail_ids = messages[0].split()
                if not mail_ids:
                    return None

                # Default to the latest message
                target_id = mail_ids[-1]

                # If email_id matches a UID or is in a specific subject/header, find it
                if email_id.isdigit():
                    target_id = email_id
                else:
                    # Search last 10 messages for match
                    for m_id in reversed(mail_ids[-10:]):
                        _, msg_data = mail.fetch(m_id, "(RFC822)")
                        for response_part in msg_data:
                            if isinstance(response_part, tuple):
                                msg = email.message_from_bytes(response_part[1])
                                msg_id_header = msg.get("Message-ID", "")
                                if email_id in msg_id_header or email_id in msg.get("Subject", ""):
                                    target_id = m_id
                                    break

                # Fetch the selected email content
                status, data = mail.fetch(target_id, "(RFC822)")
                if status != "OK":
                    return None

                for response_part in data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        
                        subject = msg.get("Subject", "")
                        if subject:
                            decoded = decode_header(subject)[0]
                            if isinstance(decoded[0], bytes):
                                subject = decoded[0].decode(decoded[1] or "utf-8", errors="ignore")
                            else:
                                subject = decoded[0]

                        sender = msg.get("From", "")
                        if sender:
                            decoded = decode_header(sender)[0]
                            if isinstance(decoded[0], bytes):
                                sender = decoded[0].decode(decoded[1] or "utf-8", errors="ignore")
                            else:
                                sender = decoded[0]

                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                content_type = part.get_content_type()
                                content_disposition = str(part.get("Content-Disposition"))
                                if content_type == "text/plain" and "attachment" not in content_disposition:
                                    payload = part.get_payload(decode=True)
                                    if payload:
                                        body = payload.decode(errors="ignore")
                                    break
                        else:
                            payload = msg.get_payload(decode=True)
                            if payload:
                                body = payload.decode(errors="ignore")

                        mail.close()
                        mail.logout()
                        return {
                            "id": str(target_id.decode() if isinstance(target_id, bytes) else target_id),
                            "sender": sender,
                            "subject": subject,
                            "body": body.strip()
                        }
            except Exception as e:
                logger.error(f"Failed to fetch email from Gmail IMAP: {e}")
                raise e

        # Simulated inbox fallback (mock mode)
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
        In real mode, uses smtplib SMTP_SSL to send the email.
        """
        self.log_call("send_message", {"to": recipient, "subject": subject, "body_preview": body[:60] + "..."})
        if self.mock_mode:
            logger.info(f"--- SIMULATING GMAIL SEND ---")
            logger.info(f"To: {recipient}")
            logger.info(f"Subject: {subject}")
            logger.info(f"Body:\n{body}")
            logger.info(f"-----------------------------")
            return True
        
        gmail_user = os.getenv("GMAIL_USER")
        gmail_password = os.getenv("GMAIL_APP_PASSWORD")
        if not gmail_user or not gmail_password:
            raise ValueError("GMAIL_USER and GMAIL_APP_PASSWORD must be configured in .env for real Gmail mode.")

        try:
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = gmail_user
            msg["To"] = recipient

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(gmail_user, gmail_password)
                server.sendmail(gmail_user, recipient, msg.as_string())
            logger.info(f"Successfully sent email to {recipient} via SMTP.")
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {recipient} via SMTP: {e}")
            return False

