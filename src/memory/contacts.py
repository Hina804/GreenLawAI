import logging
import json
import os
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class ContactMemory:
    """
    Manages identity and relationship data for stakeholders, officers, and users.
    Ensures the agent knows WHO it is talking to or about.
    """
    
    def __init__(self, data_dir: str = "e:/GL_AI/data/memory/contacts"):
        self.data_dir = data_dir
        self.contacts_file = os.path.join(data_dir, "directory.json")
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.contacts = self._load_json()

    def _load_json(self) -> Dict:
        if os.path.exists(self.contacts_file):
            with open(self.contacts_file, 'r') as f:
                return json.load(f)
        return {}

    def _save_json(self):
        with open(self.contacts_file, 'w') as f:
            json.dump(self.contacts, f, indent=2)

    async def get_contact(self, name_or_id: str) -> Optional[Dict]:
        """Retrieves contact details."""
        return self.contacts.get(name_or_id)

    async def update_contact(self, contact_id: str, data: Dict):
        """Updates or creates a contact."""
        if contact_id not in self.contacts:
            self.contacts[contact_id] = {"id": contact_id}
        
        self.contacts[contact_id].update(data)
        self._save_json()
        logger.info(f"ContactMemory: Updated contact {contact_id}")

    async def search_contacts(self, query: str) -> List[Dict]:
        """Simple keyword search across contact fields."""
        results = []
        q = query.lower()
        for c in self.contacts.values():
            if q in str(c).lower():
                results.append(c)
        return results
