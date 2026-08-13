import logging
import asyncio
from typing import Dict, List, Any, Optional
from tools.base_tool import BaseTool

logger = logging.getLogger(__name__)

INTENT_MAPPING = {
    'investigate': {
        'keywords': ['investigate', 'recent', 'incident', 'happened', 'illegal', 'satellite'],
        'primary_tools': ['incident_agent', 'satellite_analyzer'],
        'fallback_tools': ['web_search', 'law_specialist'],
        'required_actions': ['get_incidents', 'analyze_timeline']
    },
    'notify': {
        'primary_tools': ['slack_notifier', 'email_sender', 'sms_messenger', 'whatsapp_messenger'],
        'fallback_tools': ['teams_notifier'],
        'required_actions': ['send_to_dfo', 'log_notification']
    }
}

class ToolRegistry:
    """
    Advanced Registry for Agentic tools.
    Supports categories, dynamic loading, and BaseTool instances.
    """
    
    def __init__(self, llm_manager=None):
        self._tools: Dict[str, BaseTool] = {}
        self.categories: Dict[str, List[str]] = {
            "core": [],
            "search": [],
            "automation": [],
            "certification": [],
            "agent_wrappers": []
        }
        self._register_builtins(llm_manager)
        
    def _register_builtins(self, llm_manager=None):
        from tools.automation.certificate_generator import CertificateGenerator
        from tools.automation.blockchain_recorder import BlockchainRecorder
        from tools.automation.audit_logger import AuditLogger
        from tools.phase2_wrappers.legal_wrapper import LegalAgentWrapper
        from tools.phase2_wrappers.patrol_wrapper import PatrolAgentWrapper
        from tools.phase2_wrappers.incident_wrapper import IncidentAgent
        from tools.phase2_wrappers.climate_tool import ClimateAgentWrapper
        from tools.phase2_wrappers.awareness_tool import AwarenessAgentWrapper
        from tools.phase2_wrappers.judiciary_wrapper import JudiciarySpecialist
        from tools.search.forest_law_search import ForestLawSearch
        from tools.search.web_search import WebSearch
        from tools.communication.email_sender import EmailSender
        from tools.communication.sms_messenger import SMSMessenger
        from tools.communication.whatsapp_messenger import WhatsAppMessenger
        from tools.communication.slack_notifier import SlackNotifier
        from tools.communication.teams_notifier import TeamsNotifier
        from tools.emergency.fire_department import FireDepartmentNotifier
        from tools.emergency.evacuation_planner import EvacuationPlanner
        from tools.forestry.satellite_analyzer import SatelliteAnalyzer
        
        self.register(CertificateGenerator(), category="certification")
        self.register(BlockchainRecorder(), category="certification")
        self.register(AuditLogger(), category="automation")
        self.register(LegalAgentWrapper(llm_manager=llm_manager), category="agent_wrappers")
        self.register(PatrolAgentWrapper(), category="agent_wrappers")
        self.register(IncidentAgent(), category="agent_wrappers")
        self.register(ClimateAgentWrapper(), category="agent_wrappers")
        self.register(AwarenessAgentWrapper(), category="agent_wrappers")
        self.register(JudiciarySpecialist(llm_manager=llm_manager), category="agent_wrappers")
        self.register(ForestLawSearch(), category="search")
        self.register(WebSearch(), category="search")
        self.register(EmailSender(), category="communication")
        self.register(SMSMessenger(), category="communication")
        self.register(SlackNotifier(), category="communication")
        self.register(TeamsNotifier(), category="communication")
        self.register(FireDepartmentNotifier(), category="emergency")
        self.register(EvacuationPlanner(), category="emergency")
        self.register(SatelliteAnalyzer(), category="forestry")

    def register(self, tool: BaseTool, category: str = "core"):
        """Register a tool instance."""
        if not isinstance(tool, BaseTool):
            raise ValueError("Only instances of BaseTool can be registered.")
        
        self._tools[tool.name] = tool
        if category in self.categories:
            if tool.name not in self.categories[category]:
                self.categories[category].append(tool.name)
        
        logger.debug(f"Tool '{tool.name}' registered in category '{category}'.")

    def list_tools(self, category: Optional[str] = None) -> List[Dict[str, str]]:
        """List available tools, optionally filtered by category."""
        target_names = []
        if category and category in self.categories:
            target_names = self.categories[category]
        else:
            target_names = list(self._tools.keys())
            
        return [self._tools[name].get_info() for name in target_names]

    async def execute(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        """Execute a tool by name with parameters."""
        if tool_name not in self._tools:
            return {"error": f"Tool '{tool_name}' not found in registry."}
        
        tool = self._tools[tool_name]
        try:
            return await tool.execute(parameters)
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return {"error": str(e)}
