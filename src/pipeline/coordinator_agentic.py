# E:\GL_AI\src\pipeline\coordinator_agentic.py
import logging
import asyncio
import yaml
from typing import Dict, Any, Optional
from pathlib import Path
from agents.orchestrator.react_core import ReActAgent
from agents.orchestrator.llm_bridge import LLMBridge
from data_pipeline.rag.llm_manager import LLMManager
from core.schemas import CanonicalAgentResponse
from utils.ngrok_keepalive import NgrokKeepAlive

logger = logging.getLogger(__name__)

class AgenticCoordinator:
    """
    Unified entry point for the GreenLawAI Agentic AI system.
    Orchestrates the ReAct reasoning loop, memory fabric, tool registry, and reflection.
    """
    
    def __init__(self, llm_engine=None):
        self._llm_engine = llm_engine
        self.agent = ReActAgent(llm_engine=llm_engine)
        self._keepalive = None
        logger.info("[AgenticCoordinator] Initialized. LLM will be verified on first run.")

    @property
    def health_status(self) -> dict:
        """Get system health status for UI display."""
        llm_connected = self.agent.llm is not None
        llm_degraded = False
        if llm_connected and hasattr(self.agent.llm, 'is_degraded'):
            llm_degraded = self.agent.llm.is_degraded
        
        tunnel_healthy = True
        if self._keepalive:
            tunnel_healthy = self._keepalive.is_healthy
        
        return {
            "llm_connected": llm_connected,
            "llm_degraded": llm_degraded,
            "tunnel_healthy": tunnel_healthy,
            "keepalive_status": self._keepalive.get_status() if self._keepalive else None
        }

    async def _ensure_llm(self):
        """Lazy async initialization of the LLM provider."""
        if self.agent.llm is not None:
            return

        logger.info("[AgenticCoordinator] Attempting lazy LLM initialization...")
        try:
            config_path = Path("e:/GL_AI/config/rag_config.yaml")
            if not config_path.exists():
                logger.error(f"[AgenticCoordinator] Config MISSING at {config_path}")
                return
                
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)
            
            common_llm_config = config.get("llm", {})
            provider = common_llm_config.get("provider", "unknown")
            logger.info(f"[AgenticCoordinator] Config found. Provider: {provider}")

            manager = LLMManager()
            success = await manager.load(common_llm_config)
            
            if success:
                logger.info("[AgenticCoordinator] LLMManager loaded successfully.")
                self.agent.llm = LLMBridge(manager)
                self.agent.planner.llm = self.agent.llm
                self.agent.meta.llm = self.agent.llm
                
                # Start ngrok Keep-Alive if using Colab
                if provider == "colab":
                    colab_url = common_llm_config.get("colab_url", "")
                    if colab_url:
                        self._keepalive = NgrokKeepAlive(colab_url, check_interval=45)
                        self._keepalive.start()
                        logger.info(f"[AgenticCoordinator] NgrokKeepAlive started for {colab_url}")
            else:
                logger.error("[AgenticCoordinator] LLMManager.load() returned False")
        except Exception as e:
            logger.error(f"[AgenticCoordinator] Critical failure in _ensure_llm: {e}", exc_info=True)

    async def run(self, query: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Executes a query through the full agentic stack.
        """
        # Ensure LLM is ready before processing
        await self._ensure_llm()
        
        logger.info(f"[AgenticCoordinator] Processing query: {query}")
        
        try:
            # Execute ReAct loop
            result = await self.agent.process(query, context)
            
            # log summary for monitoring
            if result.get("status") == "success":
                logger.info(f"[AgenticCoordinator] Task completed successfully in {result.get('total_steps')} steps.")
            else:
                logger.warning(f"[AgenticCoordinator] Task finished with status: {result.get('status')}")
                
            return result
        except Exception as e:
            logger.error(f"[AgenticCoordinator] Critical error during execution: {e}")
            return {
                "status": "error",
                "error": str(e),
                "query": query
            }

# Singleton instance for global access if needed
_coordinator = None

def get_coordinator(llm_engine=None):
    global _coordinator
    if _coordinator is None:
        _coordinator = AgenticCoordinator(llm_engine=llm_engine)
    return _coordinator
