import json
import os
from datetime import datetime
from typing import List, Dict, Any
from loguru import logger

class KnowledgeEvolutionEngine:
    """
    Scans the knowledge base for stale or outdated content based on 
    temporal thresholds and status markers.
    """
    def __init__(self, stale_threshold_days: int = 180):
        self.stale_threshold_days = stale_threshold_days

    def check_staleness(self, metadata_dict: Dict[str, Any]) -> str:
        """
        Determines the status of a knowledge entry based on its verification date.
        Returns: 'CURRENT', 'STALE', or 'NEEDS_REVIEW'
        """
        last_verified_str = metadata_dict.get("last_verified")
        if not last_verified_str:
            return "NEEDS_REVIEW"
        
        try:
            last_verified = datetime.strptime(last_verified_str, "%Y-%m-%d")
            age_days = (datetime.now() - last_verified).days
            
            if age_days > self.stale_threshold_days:
                return "STALE"
            elif age_days > (self.stale_threshold_days // 2):
                return "NEEDS_REVIEW"
            
            return "CURRENT"
        except Exception as e:
            logger.error(f"Failed to parse verification date {last_verified_str}: {e}")
            return "NEEDS_REVIEW"

    def scan_knowledge_base(self, json_file_path: str) -> List[Dict[str, Any]]:
        """
        Scans a JSON file of knowledge entries and identifies those needing review.
        """
        if not os.path.exists(json_file_path):
            return []
            
        stale_entries = []
        try:
            with open(json_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            for item in data:
                metadata = item.get("metadata", {})
                new_status = self.check_staleness(metadata)
                
                if new_status != "CURRENT":
                    stale_entries.append({
                        "id": item.get("case_id"),
                        "title": item.get("title"),
                        "status": new_status,
                        "age": (datetime.now() - datetime.strptime(metadata.get("last_verified", "1970-01-01"), "%Y-%m-%d")).days
                    })
            
            return stale_entries
        except Exception as e:
            logger.error(f"Scan failed for {json_file_path}: {e}")
            return []

evolution_engine = KnowledgeEvolutionEngine()
