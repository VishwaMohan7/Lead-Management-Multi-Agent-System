from mcp_clients.base_client import BaseMCPClient, logger

class WhatsAppMCPClient(BaseMCPClient):
    """
    WhatsApp MCP Client wrapper.
    Responsible for drafting/sending WhatsApp messages.
    """
    def __init__(self, mock_mode: bool = True):
        super().__init__("WhatsAppMCP", mock_mode)

    def send_whatsapp(self, recipient: str, body: str) -> bool:
        """
        Sends a WhatsApp message.
        In mock mode, simulates delivery and logs details.
        """
        self.log_call("send_whatsapp_message", {"to": recipient, "body_preview": body[:60] + "..."})
        if self.mock_mode:
            logger.info(f"--- SIMULATING WHATSAPP SEND ---")
            logger.info(f"To: {recipient}")
            logger.info(f"Message:\n{body}")
            logger.info(f"--------------------------------")
            return True
        return False
