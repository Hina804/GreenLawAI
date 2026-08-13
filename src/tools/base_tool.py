from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class BaseTool(ABC):
    """
    Abstract base class for all Agentic tools.
    """
    def __init__(self, name: str, description: str, metadata: Optional[Dict] = None):
        self.name = name
        self.description = description
        self.metadata = metadata or {}

    @abstractmethod
    async def execute(self, parameters: Dict[str, Any]) -> Any:
        """
        Main execution logic for the tool.
        """
        pass

    def get_info(self) -> Dict[str, str]:
        """Provides metadata and description for the LLM."""
        return {
            "name": self.name,
            "description": self.description
        }
