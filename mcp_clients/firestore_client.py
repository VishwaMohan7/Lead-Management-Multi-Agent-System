import os
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from mcp_clients.base_client import BaseMCPClient, logger

load_dotenv()

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
except ImportError:  # pragma: no cover - optional runtime dependency
    firebase_admin = None
    credentials = None
    firestore = None

DB_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "leads_db.json")

class FirestoreMCPClient(BaseMCPClient):
    """
    Firestore-first lead repository.

    When Firebase credentials are available, this client stores data in a real
    Firestore collection. For local development and tests, it falls back to the
    existing JSON file so the rest of the application can still run offline.
    """
    def __init__(self, mock_mode: Optional[bool] = None, collection_name: str = "leads"):
        self.collection_name = collection_name
        self._firestore_db = None
        self._use_firestore = self._should_use_firestore(mock_mode)
        super().__init__("FirestoreMCP", mock_mode=not self._use_firestore)

        if not self._use_firestore:
            self._ensure_mock_db()

    def _should_use_firestore(self, mock_mode: Optional[bool]) -> bool:
        if mock_mode is True or os.getenv("USE_LOCAL_DATABASE") == "true":
            return False
        if firestore is None or firebase_admin is None:
            raise RuntimeError("firebase-admin is required for Firestore storage.")

        try:
            if not firebase_admin._apps:
                options: Dict[str, Any] = {}
                project_id = os.getenv("FIRESTORE_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
                if project_id:
                    options["projectId"] = project_id
                credential_path = os.getenv("FIRESTORE_APPLICATION_CREDENTIALS") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
                if credential_path:
                    credential_path = os.path.expanduser(credential_path.strip().strip('"'))
                    if not os.path.exists(credential_path):
                        raise FileNotFoundError(
                            f"Firestore credentials file does not exist: {credential_path}"
                        )
                    firebase_admin.initialize_app(
                        credentials.Certificate(credential_path),
                        options=options or None,
                    )
                else:
                    firebase_admin.initialize_app(options=options or None)
            self._firestore_db = firestore.client()
            logger.info("FirestoreMCP configured to use live Firestore storage.")
            return True
        except Exception as exc:  # pragma: no cover - depends on runtime credentials
            self._firestore_db = None
            if os.getenv("FIRESTORE_PROJECT_ID") or os.getenv("FIRESTORE_APPLICATION_CREDENTIALS") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
                raise RuntimeError(f"Firestore storage is configured but unavailable: {exc}") from exc
            logger.warning(f"Falling back to JSON lead storage because Firestore is unavailable: {exc}")
            return False

    def _ensure_mock_db(self) -> None:
        os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
        if not os.path.exists(DB_FILE):
            with open(DB_FILE, "w") as f:
                json.dump({}, f)

    def _read_db(self) -> Dict[str, dict]:
        if self._use_firestore:
            docs = self._firestore_db.collection(self.collection_name).stream()
            return {doc.id: doc.to_dict() for doc in docs}
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading database: {e}")
            return {}

    def _write_db(self, db: Dict[str, dict]):
        if self._use_firestore:
            collection = self._firestore_db.collection(self.collection_name)
            for lead_id, lead_data in db.items():
                collection.document(lead_id).set(lead_data, merge=True)
            return
        try:
            with open(DB_FILE, "w") as f:
                json.dump(db, f, indent=2)
        except Exception as e:
            logger.error(f"Error writing to database: {e}")

    def _persist_lead(self, lead_id: str, lead_data: Dict[str, Any]) -> None:
        if self._use_firestore:
            self._firestore_db.collection(self.collection_name).document(lead_id).set(lead_data, merge=True)
            return

        db = self._read_db()
        db[lead_id] = lead_data
        self._write_db(db)

    @staticmethod
    def _merge_dicts(existing: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(existing)
        for key, value in updates.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = FirestoreMCPClient._merge_dicts(merged[key], value)
            else:
                merged[key] = value
        return merged

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

        self._persist_lead(lead_id, lead_data)
        return lead_data

    def get_lead(self, lead_id: str) -> Optional[Dict]:
        """
        Retrieves a lead by its ID.
        """
        self.log_call("get_document", {"collection": "leads", "id": lead_id})
        if self._use_firestore:
            document = self._firestore_db.collection(self.collection_name).document(lead_id).get()
            return document.to_dict() if document.exists else None

        db = self._read_db()
        return db.get(lead_id)

    def get_all_leads(self) -> List[Dict]:
        """
        Retrieves all leads from the database.
        """
        self.log_call("list_documents", {"collection": "leads"})
        if self._use_firestore:
            documents = self._firestore_db.collection(self.collection_name).stream()
            leads = [doc.to_dict() for doc in documents]
            leads.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
            return leads

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
        lead = self.get_lead(lead_id)
        if not lead:
            logger.warning(f"Lead {lead_id} not found for updates.")
            return None

        now = datetime.utcnow().isoformat()

        lead = self._merge_dicts(lead, updates)

        # Append to history
        history = list(lead.get("history", []))
        history.append({
            "timestamp": now,
            "event": event_name,
            "details": f"Updated fields: {list(updates.keys())}"
        })
        lead["history"] = history
        lead["updated_at"] = now

        self._persist_lead(lead_id, lead)
        return lead
