"""
Task Planner - Deterministic Edition.
Since Phi-2 cannot reliably output JSON, this planner uses
keyword analysis to create structured plans WITHOUT the LLM.
The LLM is only used for synthesis (plain text), never for planning.
"""

import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class TaskPlan:
    """Represents a structured plan consisting of multiple sub-tasks."""
    
    def __init__(self, original_task: str, sub_tasks: List[Dict[str, Any]], location_data: Optional[Dict[str, Any]] = None):
        self.original_task = original_task
        self.sub_tasks = sub_tasks
        self.location_data = location_data
        self.created_at = datetime.now()
        self.current_step_index = 0
        self.status = "in_progress"
        self.results = {}

    def get_next_sub_task(self) -> Optional[Dict[str, Any]]:
        if self.current_step_index < len(self.sub_tasks):
            return self.sub_tasks[self.current_step_index]
        return None

    def complete_step(self, result: Any):
        if self.current_step_index < len(self.sub_tasks):
            task_name = self.sub_tasks[self.current_step_index].get("name", f"step_{self.current_step_index}")
            self.results[task_name] = result
            self.current_step_index += 1
            if self.current_step_index >= len(self.sub_tasks):
                self.status = "completed"

    def is_finished(self) -> bool:
        return self.status == "completed" or self.current_step_index >= len(self.sub_tasks)


class TaskPlanner:
    """
    DETERMINISTIC task planner.
    Analyzes task keywords to create optimal tool execution plans.
    Does NOT rely on the LLM for planning — only for final synthesis.
    """
    
    # Centralized Location Intelligence
    LOCATION_MAPPING = {
        'hazara': {'lat': 34.15, 'lon': 73.22, 'districts': ['Abbottabad', 'Mansehra', 'Haripur', 'Batagram']},
        'abbottabad': {'lat': 34.15, 'lon': 73.22},
        'mansehra': {'lat': 34.33, 'lon': 73.20},
        'haripur': {'lat': 33.99, 'lon': 72.93},
        'swat': {'lat': 35.22, 'lon': 72.48, 'region_full': 'Swat District'},
        'kalam': {'lat': 35.48, 'lon': 72.58, 'region_full': 'Kalam Region of Swat District'}
    }
    
    def __init__(self, llm_engine=None):
        self.llm = llm_engine

    async def create_plan(self, task: str, context: Optional[Dict] = None) -> TaskPlan:
        """Create a deterministic plan based on task keywords."""
        logger.info(f"[Planner] Creating deterministic plan for: {task[:80]}...")
        
        task_lower = task.lower()
        sub_tasks = []
        
        # Determine specific location for tool injection
        location_data = None
        for loc, data in self.LOCATION_MAPPING.items():
            if loc in task_lower:
                location_data = data.copy()
                location_data['name'] = loc
                break
        
        # If no specific district, check if "Hazara" is mentioned
        if not location_data and 'hazara' in task_lower:
             location_data = self.LOCATION_MAPPING['hazara'].copy()
             location_data['name'] = 'Hazara (Abbottabad/Mansehra)'
        
        # === TOP-LEVEL NEWS/SEARCH OVERRIDE (Phase 15.6) ===
        # If user explicitly asks to "search" or wants "news", web_search MUST be first tool
        is_news_query = any(kw in task_lower for kw in [
            'search for', 'news report', 'latest news', 'find news', 'search news', 
            'what happened', 'latest updates', 'current status', 'incidents in', 'any news'
        ])
        
        if is_news_query:
            sub_tasks = [
                {"id": 1, "name": "Live News Discovery", "tool": "web_search",
                 "description": f"Searching for: {task[:100]}"}
            ]
            # ONLY add climate_oracle if it's SPECIFICALLY about risk/weather, not just "news"
            if any(kw in task_lower for kw in ['risk', 'forecast', 'weather', 'conditions']):
                sub_tasks.append({"id": 2, "name": "Climate Context", "tool": "climate_oracle",
                                 "description": "Risk index and weather forecast"})
            
            sub_tasks.append({"id": len(sub_tasks)+1, "name": "Compile Intelligence", "tool": "complete",
                             "description": "Synthesize search findings into report"})
        
        # === ACTIVE EMERGENCY / FIRE SPOTTED PROTOCOL ===
        elif any(kw in task_lower for kw in ['fire spotted', 'active fire', 'emergency', 'burning now', 'spotted near']):
            sub_tasks = [
                {"id": 1, "name": "Alert Emergency Services", "tool": "fire_department_api",
                 "description": "Notify local 1122 and fire department"},
                {"id": 2, "name": "Plan Evacuation", "tool": "evacuation_planner",
                 "description": "Check if evacuation is needed and plan routes"},
                {"id": 3, "name": "Deploy Patrol", "tool": "patrol_planner",
                 "description": "Deploy rapid response team to location"},
                {"id": 4, "name": "Notify DFO", "tool": "sms_messenger",
                 "description": "Send urgent SMS alert to the DFO"},
                {"id": 5, "name": "Compile Emergency Report", "tool": "complete",
                 "description": "Synthesize emergency response actions into a report"}
            ]
            
        # === INVESTIGATE & NOTIFY PROTOCOL ===
        elif any(kw in task_lower for kw in ['investigate', 'recent', 'incident', 'happened', 'illegal', 'status', 'satellite', 'imagery']):
            # Milestone 15.7: Include web_search for "what happened" investigations
            sub_tasks.append({"id": len(sub_tasks) + 1, "name": "News Search", "tool": "web_search",
                              "description": "Search for live news/reports on the event"})
            
            # Proactively include satellite imagery if mentioned or investigating status
            sub_tasks.append({"id": len(sub_tasks) + 1, "name": "Satellite Intelligence", "tool": "satellite_analyzer",
                              "description": "Analyze satellite imagery for environmental changes"})
            
            sub_tasks.append({"id": len(sub_tasks) + 1, "name": "Gather Evidence", "tool": "incident_agent",
                              "description": "Investigate the incident data"})
            
            sub_tasks.append({"id": len(sub_tasks) + 1, "name": "Legal Review", "tool": "law_specialist",
                              "description": "Check relevant laws for the incident"})
                              
            if any(kw in task_lower for kw in ['notify', 'notification', 'alert', 'inform', 'contact', 'tell', 'dfo', 'slack', 'teams', 'email', 'send', 'sms', 'whatsapp', 'link']):
                # Determine best notifier
                tool = "slack_notifier"
                if "teams" in task_lower: tool = "teams_notifier"
                elif "email" in task_lower: tool = "email_sender"
                elif "whatsapp" in task_lower: tool = "whatsapp_messenger"
                elif "sms" in task_lower: tool = "sms_messenger"
                
                sub_tasks.append({"id": len(sub_tasks) + 1, "name": f"Dispatch {tool.split('_')[0].capitalize()} Alert", "tool": tool,
                                  "description": f"Send detailed report to {tool.split('_')[0].capitalize()}"})
                                  
            sub_tasks.append({"id": len(sub_tasks) + 1, "name": "Compile Report", "tool": "complete",
                              "description": "Synthesize findings into an investigation report"})
        
        # === WILDFIRE / FIRE RISK TASKS ===
        elif any(kw in task_lower for kw in ['fire', 'wildfire', 'burn', 'blaze', 'risk']):
            # Milestone: Check for "news" or "reports" to inject web search
            is_news = any(kw in task_lower for kw in ['news', 'report', 'search', 'happening', 'latest'])
            
            sub_tasks = [
                {"id": 1, "name": "Identify Location", "tool": "complete", "description": f"Targeting {location_data['name'] if location_data else 'Hazara Region'}"}
            ]
            
            if is_news:
                sub_tasks.append({"id": 2, "name": "News Intel", "tool": "web_search", 
                                 "description": "Search for live news reports on fire activity (Pakistan Scope)"})
            
            sub_tasks.extend([
                {"id": len(sub_tasks) + 1, "name": "Climate Risk Oracle", "tool": "climate_oracle", 
                 "description": "Consult the Hazara Climate Oracle for live 7-day fire risk forecasts"},
                {"id": len(sub_tasks) + 1, "name": "Legal Consequences", "tool": "law_specialist",
                 "description": "Determine legal penalties for causing forest fires (Section 33)"},
                {"id": len(sub_tasks) + 1, "name": "Generate Patrol Schedule", "tool": "patrol_planner",
                 "description": "Create patrol assignments based on risk analysis"},
                {"id": len(sub_tasks) + 1, "name": "Compile Report", "tool": "complete",
                 "description": "Synthesize findings into professional report"}
            ])
        
        # === WEATHER / CLIMATE TASKS ===
        elif any(kw in task_lower for kw in ['weather', 'climate', 'temperature', 'rain', 'forecast', 'storm', 'condition']):
            sub_tasks = [
                {"id": 1, "name": "Climate Intelligence", "tool": "climate_oracle",
                 "description": "Consult the Hazara Climate Oracle for live weather and 7-day forecasts"},
                {"id": 2, "name": "Compile Report", "tool": "complete",
                 "description": "Synthesize climate findings"}
            ]
        
        # === AWARENESS / CITIZEN ACTION TASKS ===
        elif any(kw in task_lower for kw in ['help', 'awareness', 'educate', 'citizen', 'guide', 'action', 'can i do', 'wrong', 'right', 'message']):
            sub_tasks = [
                {"id": 1, "name": "Public Awareness", "tool": "citizen_awareness",
                 "description": "Consult Public Awareness Officer for citizen guidance"},
                {"id": 2, "name": "Compile Report", "tool": "complete",
                 "description": "Synthesize awareness message"}
            ]

        # === JUDICIAL / COURT SPECIALIST TASKS ===
        elif any(kw in task_lower for kw in ['verdict', 'bail', 'prediction', 'outcome', 'precedent', 'court case', 'judgment', 'judicial']):
            sub_tasks = [
                {"id": 1, "name": "Judicial Precedents", "tool": "judiciary_specialist", "action": "retrieve",
                 "description": "Search for specific court precedents and citations"},
                {"id": 2, "name": "Outcome Prediction", "tool": "judiciary_specialist", "action": "predict",
                 "description": "Predict likely court verdict and fine based on specific facts"},
                {"id": 3, "name": "Bail Analysis", "tool": "judiciary_specialist", "action": "bail",
                 "description": "Analyze bail eligibility for the specific offense"},
                {"id": 4, "name": "Statutory Context", "tool": "law_specialist",
                 "description": "Cross-reference with statutory Law (KP Forest Ordinance)"},
                {"id": 5, "name": "Final Decision Analysis", "tool": "complete",
                 "description": "Synthesize judicial predictions and precedents into a final report"}
            ]

        # === PATROL / SCHEDULE TASKS ===
        
        # === LEGAL / LAW TASKS ===
        elif any(kw in task_lower for kw in ['law', 'legal', 'penalty', 'section', 'act ', 'fine ', 'punishment', 'fire', 'offence', 'arrest', 'warrant', 'magistrate', 'police', 'confiscate', 'seizure']):
            is_news = any(kw in task_lower for kw in ['news', 'report', 'search', 'happening', 'latest'])
            
            # Always check climate for fire risk context in legal queries if fire mentioned
            if 'fire' in task_lower:
                sub_tasks.append({"id": 1, "name": "Climate Context", "tool": "climate_oracle",
                                 "description": "Check current environmental risk context for fire offence"})
            
            if is_news:
                sub_tasks.append({"id": len(sub_tasks) + 1, "name": "Latest Legal Updates", "tool": "web_search", 
                                 "description": "Search for recent legal news/amendments (Pakistan Scope)"})
            
            sub_tasks.append({"id": len(sub_tasks) + 1, "name": "Legal Research", "tool": "law_specialist",
                             "description": "Search for relevant legal provisions and penalties (Grounded IRAC)"})
            
            # Check for notification in legal queries
            if any(kw in task_lower for kw in ['notify', 'alert', 'inform', 'contact', 'tell', 'dfo', 'slack', 'teams', 'email', 'send']):
                tool = "slack_notifier"
                if "teams" in task_lower: tool = "teams_notifier"
                elif "email" in task_lower: tool = "email_sender"
                sub_tasks.append({"id": len(sub_tasks) + 1, "name": f"Dispatch {tool.split('_')[0].capitalize()} Alert", "tool": tool,
                                  "description": f"Send legal analysis to {tool.split('_')[0].capitalize()}"})

            sub_tasks.append({"id": len(sub_tasks) + 1, "name": "Compile Analysis", "tool": "complete",
                             "description": "Synthesize legal findings into IRAC format"})
        
        # === DEFORESTATION / FOREST TASKS ===
        elif any(kw in task_lower for kw in ['deforest', 'logging', 'timber', 'tree', 'forest']):
            sub_tasks = [
                {"id": 1, "name": "Legal Framework", "tool": "search_forest_laws",
                 "description": "Search for relevant forest laws and definitions"},
                {"id": 2, "name": "Forest Data Search", "tool": "web_search",
                 "description": "Search for news and environmental context (Pakistan Scope)"},
                {"id": 3, "name": "Public Impact", "tool": "citizen_awareness",
                 "description": "Get awareness message for forest conservation"},
                {"id": 4, "name": "Compile Report", "tool": "complete",
                 "description": "Synthesize findings into report"}
            ]
        
        # === GENERAL / UNKNOWN TASKS ===
        else:
            sub_tasks = [
                {"id": 1, "name": "Climate Intel", "tool": "climate_oracle",
                 "description": "Check regional environmental status"},
                {"id": 2, "name": "Research", "tool": "web_search",
                 "description": f"Search for information on: {task[:80]}"},
                {"id": 3, "name": "Compile Report", "tool": "complete",
                 "description": "Synthesize findings"}
            ]
        
        logger.info(f"[Planner] Created plan with {len(sub_tasks)} steps: {[s['name'] for s in sub_tasks]}")
        return TaskPlan(task, sub_tasks, location_data=location_data)

    async def revise_plan(self, plan: TaskPlan, observation: str) -> TaskPlan:
        """Revise plan on error — simply skip failed step and continue."""
        logger.info("[Planner] Revising plan: skipping failed step and continuing.")
        # Don't try to use LLM for replanning — just continue with the remaining steps
        return plan
