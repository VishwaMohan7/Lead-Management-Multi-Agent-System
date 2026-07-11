import os
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from mcp_clients.base_client import BaseMCPClient, logger

DB_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "leads_db.json")

class FirestoreMCPClient(BaseMCPClient):
    """
    Firestore MCP Client wrapper.
    Manages lead status, logs, historical revisions, and metadata updates.
    """
    def __init__(self, mock_mode: bool = True):
        super().__init__("FirestoreMCP", mock_mode)
        if self.mock_mode:
            # Ensure data directory exists
            os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
            if not os.path.exists(DB_FILE):
                with open(DB_FILE, "w") as f:
                    json.dump({}, f)

    def _read_db(self) -> Dict[str, dict]:
        if not self.mock_mode:
            # Real Firestore connection logic here
            raise NotImplementedError("Real Firestore connection is not configured.")
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading database: {e}")
            return {}

    def _write_db(self, db: Dict[str, dict]):
        if not self.mock_mode:
            raise NotImplementedError("Real Firestore connection is not configured.")
        try:
            with open(DB_FILE, "w") as f:
                json.dump(db, f, indent=2)
        except Exception as e:
            logger.error(f"Error writing to database: {e}")

    def create_lead(self, raw_text: str, source: str) -> Dict:
        """
        Creates a new lead document with initial state.
        """
        self.log_call("create_document", {"collection": "leads", "data": {"raw_text": raw_text, "source": source}})
        lead_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        
        lead_data = {
            "id": lead_id,
            "raw_text": raw_text,
            "source": source,
            "extracted_data": {},
            "intent": None,
            "score": None,  # { "category": "HOT/WARM/COLD", "points": 0 }
            "recommendation": None,  # { "action": "...", "details": "..." }
            "draft": None,  # { "email_subject": "...", "email_body": "...", "whatsapp_body": "...", "status": "pending_approval" }
            "history": [
                {
                    "timestamp": now,
                    "event": "lead_created",
                    "details": f"Lead received via {source}"
                }
            ],
            "created_at": now,
            "updated_at": now
        }
        
        db = self._read_db()
        db[lead_id] = lead_data
        self._write_db(db)
        return lead_data

    def get_lead(self, lead_id: str) -> Optional[Dict]:
        """
        Retrieves a lead by its ID.
        """
        self.log_call("get_document", {"collection": "leads", "id": lead_id})
        db = self._read_db()
        return db.get(lead_id)

    def get_all_leads(self) -> List[Dict]:
        """
        Retrieves all leads from the database.
        """
        self.log_call("list_documents", {"collection": "leads"})
        db = self._read_db()
        # Sort by updated_at descending
        leads = list(db.values())
        leads.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return leads

    def update_lead(self, lead_id: str, updates: dict, event_name: str = "lead_updated") -> Optional[Dict]:
        """
        Updates specific fields on a lead and appends a history log.
        """
        self.log_call("update_document", {"collection": "leads", "id": lead_id, "updates": updates})
        db = self._read_db()
        if lead_id not in db:
            logger.warning(f"Lead {lead_id} not found for updates.")
            return None

        lead = db[lead_id]
        now = datetime.utcnow().isoformat()

        # Update nested dicts or overwrite fields
        for k, v in updates.items():
            if isinstance(v, dict) and k in lead and isinstance(lead[k], dict):
                lead[k].update(v)
            else:
                lead[k] = v

        # Append to history
        lead["history"].append({
            "timestamp": now,
            "event": event_name,
            "details": f"Updated fields: {list(updates.keys())}"
        })
        lead["updated_at"] = now
        db[lead_id] = lead
        self._write_db(db)
        return lead
