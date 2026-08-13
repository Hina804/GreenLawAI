"""
Meta-Cognition - Deterministic Edition.
Evaluates confidence WITHOUT calling the LLM.
Uses simple heuristics based on tool results.
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class MetaCognition:
    """
    Self-awareness layer for the Agentic AI system.
    Now fully deterministic — does NOT waste LLM calls.
    """
    
    def __init__(self, llm_engine=None):
        self.llm = llm_engine

    async def evaluate_confidence(self, task: str, plan: Any, steps: List[Dict]) -> float:
        """
        Estimates confidence using simple heuristics.
        No LLM call needed.
        """
        if not steps:
            return 0.5

        # Count successful vs failed steps
        total = len(steps)
        errors = sum(1 for s in steps if s.get('action') == 'error' or 
                     (isinstance(s.get('result'), dict) and 'error' in s.get('result', {})))
        successes = total - errors

        if total == 0:
            return 0.5
        
        # Base confidence from success rate
        confidence = successes / total
        
        # Bonus if we have specific data types
        has_patrol = any(s.get('action') == 'patrol_planner' for s in steps)
        has_search = any(s.get('action') == 'web_search' for s in steps)
        has_legal = any(s.get('action') in ['law_specialist', 'search_forest_laws'] for s in steps)
        
        if has_patrol:
            confidence += 0.1
        if has_search:
            confidence += 0.05
        if has_legal:
            confidence += 0.1
        
        return min(confidence, 1.0)

    async def get_fallback_strategy(self, task: str, failure_reason: str) -> str:
        """Returns a fallback strategy name."""
        return "Simplified Search"
