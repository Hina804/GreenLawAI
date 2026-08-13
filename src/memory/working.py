import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class WorkingMemory:
    """
    Volatile memory for the current conversation and task.
    In a distributed system, this would be Redis. Here, it's a thread-safe dict.
    """
    
    def __init__(self):
        self.context = {}
        self.active_task = None
        self.metadata = {}

    def update(self, key: str, value: Any):
        self.context[key] = value

    def bulk_update(self, data: Dict):
        self.context.update(data)

    def get(self, key: str, default: Any = None) -> Any:
        return self.context.get(key, default)

    def clear(self):
        self.context = {}
        self.active_task = None
        logger.info("WorkingMemory cleared.")

    def set_active_task(self, task_id: str, details: Dict):
        self.active_task = task_id
        self.metadata['task_details'] = details
        logger.debug(f"WorkingMemory: Active task set to {task_id}")

    def get_full_context(self) -> Dict:
        return {
            "context": self.context,
            "active_task": self.active_task,
            "metadata": self.metadata
        }
