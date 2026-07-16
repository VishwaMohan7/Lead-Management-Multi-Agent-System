import os
from datetime import datetime, timezone, timedelta
from mcp_clients.gmail_client import GmailMCPClient

def test_gmail_filtering_default():
    # Clear env threshold to ensure it uses default (2026-07-13T13:33:44+05:30)
    os.environ.pop("GMAIL_MIN_TIMESTAMP", None)
    client = GmailMCPClient(mock_mode=True)
    
    # Under the default threshold:
    # mock-unread-101 (2026-07-13 14:00:00 +0530) should be included
    # mock-unread-102 (2026-07-13 12:00:00 +0530) should be excluded
    emails = client.get_unread_emails()
    ids = [e["id"] for e in emails]
    assert "mock-unread-101" in ids
    assert "mock-unread-102" not in ids
    assert len(emails) == 1

def test_gmail_filtering_custom_env():
    # Set threshold to a later time (2026-07-13 15:00:00 +0530)
    # Both mock emails should be excluded now
    os.environ["GMAIL_MIN_TIMESTAMP"] = "2026-07-13T15:00:00+05:30"
    try:
        client = GmailMCPClient(mock_mode=True)
        emails = client.get_unread_emails()
        assert len(emails) == 0
    finally:
        os.environ.pop("GMAIL_MIN_TIMESTAMP", None)

def test_gmail_filtering_custom_env_earlier():
    # Set threshold to an earlier time (2026-07-13 10:00:00 +0530)
    # Both mock emails should be included now
    os.environ["GMAIL_MIN_TIMESTAMP"] = "2026-07-13T10:00:00+05:30"
    try:
        client = GmailMCPClient(mock_mode=True)
        emails = client.get_unread_emails()
        ids = [e["id"] for e in emails]
        assert "mock-unread-101" in ids
        assert "mock-unread-102" in ids
        assert len(emails) == 2
    finally:
        os.environ.pop("GMAIL_MIN_TIMESTAMP", None)
