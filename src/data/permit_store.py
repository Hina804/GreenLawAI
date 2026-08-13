import json
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class PermitStore:
    """
    Persistent JSON-based store for forest permits.
    Provides CRUD operations and basic analytics.
    """
    def __init__(self, storage_path: str = "data/permits.json"):
        self.storage_path = os.path.join(os.getcwd(), storage_path)
        self._ensure_storage()
        self.permits = self._load()

    def _ensure_storage(self):
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        if not os.path.exists(self.storage_path):
            with open(self.storage_path, "w") as f:
                json.dump([], f)

    def _load(self) -> List[Dict]:
        try:
            with open(self.storage_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load permit store: {e}")
            return []

    def save(self):
        try:
            with open(self.storage_path, "w") as f:
                json.dump(self.permits, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save permit store: {e}")

    def add_permit(self, permit_data: Dict):
        # Ensure unique ID or generate one if missing
        if 'permit_id' not in permit_data:
            permit_data['permit_id'] = f"PRMT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        permit_data['created_at'] = datetime.now().isoformat()
        self.permits.append(permit_data)
        self.save()
        return permit_data['permit_id']

    def get_permit(self, permit_id: str) -> Optional[Dict]:
        for p in self.permits:
            if p.get('permit_id') == permit_id:
                return p
        return None

    def get_by_cnic(self, cnic: str) -> List[Dict]:
        return [p for p in self.permits if p.get('applicant', {}).get('cnic') == cnic]

    def get_recent_applications(self, cnic: str, days: int = 30) -> List[Dict]:
        cutoff = datetime.now() - timedelta(days=days)
        recent = []
        for p in self.permits:
            if p.get('applicant', {}).get('cnic') == cnic:
                try:
                    created_at = datetime.fromisoformat(p.get('created_at'))
                    if created_at > cutoff:
                        recent.append(p)
                except:
                    continue
        return recent

    def get_stats(self) -> Dict:
        total = len(self.permits)
        approved = len([p for p in self.permits if p.get('status') == 'Approved'])
        total_volume = sum([float(p.get('request', {}).get('volume_cubic_ft', 0)) for p in self.permits if p.get('status') == 'Approved'])
        
        return {
            "total_applications": total,
            "approved_count": approved,
            "rejection_rate": f"{(total - approved) / total * 100:.1f}%" if total > 0 else "0%",
            "total_volume_ft3": total_volume
        }

# Global singleton
permit_store = PermitStore()
