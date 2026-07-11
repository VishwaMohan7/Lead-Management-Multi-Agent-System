import logging
from abc import ABC

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp_clients")

class BaseMCPClient(ABC):
    """
    Base class for MCP Clients.
    In a real system, this would establish connection via JSON-RPC/SSE 
    to the respective MCP server. For this project, it provides logging, 
    instrumentation, and mock/simulated fallback capabilities.
    """
    def __init__(self, name: str, mock_mode: bool = True):
        self.name = name
        self.mock_mode = mock_mode
        logger.info(f"Initialized MCP Client: {self.name} (mock_mode={self.mock_mode})")

    def log_call(self, tool_name: str, args: dict):
        logger.info(f"[{self.name}] Call tool '{tool_name}' with arguments: {args}")
