import os
import json
import shutil
from datetime import datetime
from typing import Dict, Any, List, Optional
from loguru import logger

class KnowledgeVersionControl:
    """
    Manages the versioning and archival of legal knowledge assets.
    """
    def __init__(self, base_dir: str = "e:/GL_AI/data/knowledge"):
        self.base_dir = base_dir
        self.archive_dir = os.path.join(base_dir, "archive")
        self._ensure_dirs()

    def _ensure_dirs(self):
        os.makedirs(self.archive_dir, exist_ok=True)

    def create_snapshot(self, case_id: str, content: Dict[str, Any]) -> str:
        """
        Saves a point-in-time snapshot of a knowledge entry.
        Returns the path to the snapshot.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        version = content.get("metadata", {}).get("version", "1.0")
        snapshot_filename = f"{case_id}_v{version}_{timestamp}.json"
        snapshot_path = os.path.join(self.archive_dir, snapshot_filename)
        
        try:
            with open(snapshot_path, "w", encoding="utf-8") as f:
                json.dump(content, f, indent=4)
            logger.info(f"Snapshot created: {snapshot_path}")
            return snapshot_path
        except Exception as e:
            logger.error(f"Failed to create snapshot for {case_id}: {e}")
            return ""

    def increment_version(self, current_version: str) -> str:
        """Simple version increment logic (e.g., 1.0 -> 1.1)."""
        try:
            major, minor = map(int, current_version.split("."))
            return f"{major}.{minor + 1}"
        except:
            return "1.1"

    def get_version_history(self, case_id: str) -> List[str]:
        """Lists all archived versions for a specific case ID."""
        files = [f for f in os.listdir(self.archive_dir) if f.startswith(f"{case_id}_v")]
        return sorted(files, reverse=True)

version_manager = KnowledgeVersionControl()
