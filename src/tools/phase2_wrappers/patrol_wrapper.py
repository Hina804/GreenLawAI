import logging
from typing import Dict, Any
from tools.base_tool import BaseTool
from agents.patrol_recommender import PatrolRecommenderAgent

logger = logging.getLogger(__name__)

class PatrolAgentWrapper(BaseTool):
    """
    Wraps the Phase 3 PatrolRecommenderAgent as a tool.
    Now returns RICH, STRUCTURED data that the agent can directly use.
    """
    def __init__(self):
        super().__init__(
            name="patrol_planner",
            description="Generates daily patrol schedules and resource allocation based on current risk data. Returns specific patrol assignments with zones, team counts, and shift times."
        )
        self.agent = PatrolRecommenderAgent()

    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Returns detailed, structured patrol schedule data.
        """
        logger.info("PatrolAgentWrapper: Generating daily patrol schedule...")
        
        try:
            result = self.agent.generate_daily_schedule()
            
            # Enrich the result with actionable summary text
            recs = result.get("recommendations", [])
            critical_count = result.get("total_critical_zones", 0)
            high_count = result.get("total_high_zones", 0)
            
            # Build human-readable summary
            summary_lines = [f"📋 Patrol Schedule for {result.get('date', 'Today')}"]
            summary_lines.append(f"🔴 Critical Zones: {critical_count} | 🟠 High-Risk Zones: {high_count}")
            summary_lines.append("")
            
            for rec in recs:
                summary_lines.append(
                    f"  {rec.get('priority', '⚪')} {rec.get('division', 'Unknown')}: "
                    f"{rec.get('action', 'Standard patrol')} "
                    f"(Reason: {rec.get('reason', 'N/A')})"
                )
            
            result["summary"] = "\n".join(summary_lines)
            result["structured_assignments"] = recs
            return result
            
        except Exception as e:
            logger.error(f"Error in PatrolAgentWrapper: {e}")
            return {"error": str(e)}
