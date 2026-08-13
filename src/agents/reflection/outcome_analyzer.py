import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from core.schemas import CanonicalAgentResponse

logger = logging.getLogger(__name__)

class OutcomeAnalyzer:
    """
    Evaluates the success of agent executions and identifies 
    patterns that lead to failures or suboptimal results.
    """
    def __init__(self):
        self.success_threshold = 0.7

    def analyze_step(self, step_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyzes a single tool execution step.
        """
        tool = step_data.get("tool")
        status = step_data.get("status", "unknown")
        observation = step_data.get("observation", "")
        
        is_failure = status == "error" or "error" in str(observation).lower()
        
        analysis = {
            "is_failure": is_failure,
            "severity": "high" if is_failure else "low",
            "suggestion": None
        }
        
        if is_failure:
            analysis["suggestion"] = f"Tool {tool} failed. Consider verifying parameters or trying an alternative tool."
            
        return analysis

    def evaluate_final_outcome(self, response: CanonicalAgentResponse, trace: List[Dict[str, Any]]) -> float:
        """
        Assigns a success score (0.0 - 1.0) to the final response.
        """
        score = 1.0
        
        # 2. Penalty for fallback/negative keywords in string response
        resp_str = str(response).lower()
        negative_keywords = [
            "could not find", "couldn't find", "don't know", "not found", 
            "no information", "abstain", "no recent news", "historical record",
            "sensors are online", "no active forest fire"
        ]
        if any(word in resp_str for word in negative_keywords):
            # Significant penalty for fallback-only reports
            score -= 0.6
        
        # 3. Penalty for technical failures or throttling in trace
        failures = []
        for s in trace:
            obs = str(s.get("observation", "")).lower()
            res = str(s.get("result", "")).lower()
            if "error" in obs or "not found" in obs or "throttled" in res:
                failures.append(s)
        
        score -= (len(failures) * 0.4)
        
        # 4. Penalty for very short answers
        if len(resp_str) < 150:
            score -= 0.3
            
        # Floor score at 0.1 (to avoid absolute zero for working fallbacks)
        return max(0.1, score)

    def identify_learning_opportunity(self, query: str, score: float, trace: List[Dict[str, Any]]) -> Optional[str]:
        """
        Decides if this specific run contains a lesson worth saving.
        """
        if score < self.success_threshold:
            # Analyze trace for common errors
            for step in trace:
                obs = str(step.get("observation", "")).lower()
                if "not found" in obs or "missing" in obs:
                    return f"Query '{query}' failed because information was missing in {step.get('tool')}. Try broadening the search."
                    
            return f"Query '{query}' received a low success score. Review reasoning path."
            
        return None
