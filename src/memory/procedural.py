import logging
import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class ProceduralMemory:
    """
    Stores 'skills' and 'workflows' - how the agent should handle specific scenarios.
    Backs up success patterns for future reuse.
    """
    
    def __init__(self, data_dir: str = "e:/GL_AI/data/memory/procedural"):
        self.data_dir = data_dir
        self.skills_file = os.path.join(data_dir, "skills.json")
        self.patterns_file = os.path.join(data_dir, "patterns.json")
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.skills = self._load_json(self.skills_file)
        self.patterns = self._load_json(self.patterns_file)

    def _load_json(self, path: str) -> Dict:
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
        return {}

    def _save_json(self, path: str, data: Any):
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

    async def retrieve_skill(self, task_name: str) -> Optional[Dict]:
        """Finds a pre-defined skill for a task."""
        return self.skills.get(task_name)

    async def learn_pattern(self, pattern_name: str, steps: List[Dict]):
        """Saves a successful sequence of steps as a reusable pattern."""
        self.patterns[pattern_name] = {
            "steps": steps,
            "learned_at": datetime.now().isoformat(),
            "use_count": 0
        }
        self._save_json(self.patterns_file, self.patterns)
        logger.info(f"ProceduralMemory: Learned new pattern '{pattern_name}'")

    async def get_best_pattern(self, context_query: str) -> Optional[Dict]:
        """Simple retrieval logic for patterns (will be enhanced with semantic search later)."""
        # For now, keyword matching
        for name, data in self.patterns.items():
            if context_query.lower() in name.lower():
                data["use_count"] += 1
                return data
        return None
