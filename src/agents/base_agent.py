from abc import ABC, abstractmethod
from typing import List, Any, Dict
from loguru import logger
import os

from core.contracts import BasePipelineComponent, AgentResponseProtocol
from core.schemas import CanonicalAgentResponse, AudienceType
from core.tool_executor import ToolExecutor, ToolOutput

# Logging
log_dir = "e:/GL_AI/logs"
os.makedirs(log_dir, exist_ok=True)
logger.add(os.path.join(log_dir, "agents.log"), rotation="10 MB", level="INFO")


class BaseAgent(BasePipelineComponent, ABC):
    """
    STRICT PRODUCER INTERFACE
    Registry-Compatible (Phase 3)
    """

    def __init__(self, name: str, component_id: str = None, tools: List[Any] = None, config: Dict = None):
        # component_id defaults to name if not provided
        super().__init__(component_id or name)
        self.name = name
        self.tools = {tool.name: tool for tool in tools} if tools else {}
        self.config = config or {}

    async def load(self, config: Dict[str, Any]) -> bool:
        """Lifecycle: Load configuration."""
        self.config.update(config)
        self._is_loaded = True
        logger.info(f"[BaseAgent] {self.component_id} ({self.name}) loaded.")
        return True

    async def unload(self) -> bool:
        """Lifecycle: Shutdown."""
        self._is_loaded = False
        return True

    @abstractmethod
    async def run(
        self,
        query: str,
        retrieved_chunks: list,
        audience: AudienceType,
        context: Dict[str, Any] = None
    ) -> CanonicalAgentResponse:
        """
        SINGLE ENTRY POINT FOR ALL AGENTS
        """
        pass

    # ------------------ TOOL EXECUTION ------------------
    async def use_tool(self, tool_name: str, **kwargs) -> ToolOutput:
        if tool_name not in self.tools:
            logger.error(f"[{self.name}] Tool '{tool_name}' not registered")
            raise ValueError(f"Tool '{tool_name}' not registered in agent '{self.name}'")

        tool = self.tools[tool_name]
        return await ToolExecutor.execute(tool, **kwargs)

    def __repr__(self):
        return f"<BaseAgent id={self.component_id} name={self.name} loaded={self._is_loaded}>"