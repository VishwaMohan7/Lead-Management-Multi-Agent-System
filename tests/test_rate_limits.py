import os
import pytest
import threading
import time
import openai
from unittest.mock import patch, MagicMock
from utils.llm_provider import get_llm, MockLLM
from mcp_clients.firestore_client import FirestoreMCPClient, DB_FILE
from mcp_clients.gmail_client import GmailMCPClient
from mcp_clients.calendar_client import CalendarMCPClient
from orchestrator.pipeline import LeadManagementOrchestrator

@pytest.fixture(autouse=True)
def clean_database():
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
    yield
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)

def test_rate_limit_fail_fast_and_no_thread_leak():
    # 1. Capture starting thread count
    start_threads = threading.active_count()
    
    # 2. Setup mock response for 429 Rate Limit
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.headers = {"retry-after": "12"}
    
    rate_limit_error = openai.RateLimitError(
        message="Nvidia API rate limit exceeded.",
        response=mock_response,
        body=None
    )
    
    # Mock ChatOpenAI's underlying OpenAI client request to raise the rate limit error
    with patch("openai.OpenAI.request", side_effect=rate_limit_error):
        # Configure env variables to force get_llm to load real ChatOpenAI client
        with patch.dict(os.environ, {"NVIDIA_API_KEY": "fake_test_key_12345"}):
            llm = get_llm()
            assert not isinstance(llm, MockLLM), "Expected get_llm to load ChatOpenAI, not MockLLM"
            
            firestore_client = FirestoreMCPClient(mock_mode=True)
            gmail_client = GmailMCPClient(mock_mode=True)
            calendar_client = CalendarMCPClient(mock_mode=True)
            
            orchestrator = LeadManagementOrchestrator(
                llm=llm,
                firestore_client=firestore_client,
                gmail_client=gmail_client,
                calendar_client=calendar_client
            )
            
            # Start timer
            start_time = time.time()
            
            # 3. Assert pipeline raises RateLimitError
            with pytest.raises(openai.RateLimitError) as exc_info:
                orchestrator.run_pipeline("I want to join AI course next month. Budget $1500.", "webform")
                
            elapsed_time = time.time() - start_time
            
            # Assert failure happens quickly (should be near instant, well under 15-20s)
            assert elapsed_time < 5.0, f"Expected pipeline to fail fast, but took {elapsed_time}s"
            assert "rate limit exceeded" in str(exc_info.value).lower()
            
            # Check the DB record has saved the correct rate limit status
            leads = firestore_client.get_all_leads()
            assert len(leads) > 0
            latest_lead = leads[0]
            latest_history = latest_lead["history"][-1]
            assert "pipeline_failed_rate_limit" in latest_history["event"]
            assert "Retry-After: 12" in latest_history["event"]

    # 4. Wait brief moment to allow thread cleanup if any, then assert no thread leak
    time.sleep(0.5)
    end_threads = threading.active_count()
    assert end_threads <= start_threads, f"Thread leak detected! Started with {start_threads}, ended with {end_threads}"
