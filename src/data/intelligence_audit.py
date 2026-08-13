import json
import os
from datetime import datetime
from pathlib import Path
from loguru import logger

class IntelligenceAudit:
    """
    Persistent audit log for operator decisions (Command & Control).
    Ensures that manual verifications and dismissals are saved and can be ingested 
    back into the Reasoning Engine.
    """
    def __init__(self, log_path=None):
        if log_path is None:
            # Default to project root / data / audit_trail.json
            base_dir = Path(__file__).resolve().parent.parent.parent
            self.log_path = base_dir / "data" / "intelligence_audit.json"
        else:
            self.log_path = Path(log_path)
            
        # Ensure directory exists
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize file if not exists
        if not self.log_path.exists():
            with open(self.log_path, 'w', encoding='utf-8') as f:
                json.dump({"decisions": [], "version": "1.0"}, f, indent=4)

    def log_decision(self, cluster_id, action, cluster_details=None, reasoning="", evidence_meta=None):
        """
        Append a new decision to the audit trail.
        action: 'VERIFIED', 'DISMISSED', 'DISPATCHED', 'EVIDENCE_GENERATED'
        evidence_meta: {'pdf_path': str, 'hash': str}
        """
        try:
            with open(self.log_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            entry = {
                "timestamp": datetime.now().isoformat(),
                "cluster_id": cluster_id,
                "action": action,
                "reasoning": reasoning,
                "meta": cluster_details or {},
                "evidence": evidence_meta or {}
            }
            
            data["decisions"].append(entry)
            
            with open(self.log_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
                
            logger.info(f"Audit Logged: {action} on {cluster_id}")
            return True
        except Exception as e:
            logger.error(f"Audit log failed: {e}")
            return False

    def update_feedback(self, cluster_id, rating, notes=""):
        """
        Updates an existing audit entry with Ranger feedback.
        rating: 'CORRECT', 'FALSE_POSITIVE'
        """
        try:
            with open(self.log_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Find the most recent entry for this cluster_id
            found = False
            for entry in reversed(data.get("decisions", [])):
                if entry["cluster_id"] == cluster_id:
                    entry["field_reality"] = {
                        "rating": rating,
                        "notes": notes,
                        "updated_at": datetime.now().isoformat()
                    }
                    found = True
                    break
            
            if not found:
                logger.warning(f"Could not find cluster_id {cluster_id} to update feedback.")
                return False

            with open(self.log_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            
            logger.info(f"Feedback updated for {cluster_id}: {rating}")
            return True
        except Exception as e:
            logger.error(f"Feedback update failed: {e}")
            return False

    def get_decisions(self):
        """Retrieve all historical decisions."""
        try:
            if not self.log_path.exists():
                return {}
            with open(self.log_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Return as a mapping for quick lookup: cluster_id -> status
                return {d['cluster_id']: d['action'] for d in data.get('decisions', [])}
        except Exception as e:
            logger.error(f"Failed to read audit decisions: {e}")
            return {}

audit_trail = IntelligenceAudit()
