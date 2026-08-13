"""
Local Fallback LLM.
Ultra-lightweight rule-based responder when the Colab LLM is unavailable.
Provides deterministic, structured responses that keep the ReAct loop moving.
"""

import json
import logging
from typing import Dict, Any, Generator

logger = logging.getLogger(__name__)


class LocalFallbackLLM:
    """
    Rule-based fallback that generates valid JSON actions
    when the remote LLM (Colab/Phi-2) is unreachable or returning garbage.
    """

    def __init__(self):
        logger.info("[LocalFallbackLLM] Initialized as emergency backup.")

    def generate(self, prompt: str, stream: bool = False) -> Generator[str, None, None]:
        """
        Analyze the prompt and return a deterministic, valid JSON action.
        Compatible with the LLMManager.generate() interface.
        """
        action = self._decide_action(prompt)
        yield json.dumps(action, indent=2)

    def generate_json(self, prompt: str) -> Dict[str, Any]:
        """Direct JSON generation for the LLMBridge interface."""
        return self._decide_action(prompt)

    def count_tokens(self, text: str) -> int:
        return len(text) // 4

    def _decide_action(self, prompt: str) -> Dict[str, Any]:
        """
        Keyword-based action selection.
        Returns a valid ReAct-compatible JSON structure.
        """
        prompt_lower = prompt.lower()

        # --- PLANNING PROMPTS ---
        if "break this task" in prompt_lower or "sub_tasks" in prompt_lower:
            return self._plan_response(prompt)

        # --- THINKING PROMPTS (ReAct action selection) ---
        if "available tools" in prompt_lower or "next action" in prompt_lower:
            return self._think_response(prompt)

        # --- SYNTHESIS PROMPTS ---
        if "synthesize" in prompt_lower or "evidence gathered" in prompt_lower:
            return self._synthesize_response(prompt)

        # --- CONFIDENCE EVALUATION ---
        if "confidence" in prompt_lower or "evaluate" in prompt_lower:
            return {"confidence": 0.7, "reasoning": "Fallback estimate."}

        # --- REPLANNING ---
        if "revise" in prompt_lower or "remaining_sub_tasks" in prompt_lower:
            return {"revised": False, "reasoning": "Plan is still valid."}

        # --- DEFAULT: Try web_search ---
        return {
            "thought": "Fallback: defaulting to web_search.",
            "action": "web_search",
            "parameters": {"query": self._extract_task(prompt)}
        }

    def _plan_response(self, prompt: str) -> Dict[str, Any]:
        """Generate a simple 2-step plan."""
        task = self._extract_task(prompt)
        task_lower = task.lower()

        steps = []

        # Decide steps based on task content
        if any(kw in task_lower for kw in ['fire', 'wildfire', 'risk', 'weather']):
            steps = [
                {"id": 1, "name": "Gather Risk Data", "description": f"Search for current risk data related to: {task[:80]}"},
                {"id": 2, "name": "Generate Patrol Schedule", "description": "Use patrol_planner to create response schedule."},
                {"id": 3, "name": "Synthesize Report", "description": "Compile findings into a professional report."}
            ]
        elif any(kw in task_lower for kw in ['law', 'legal', 'penalty', 'section', 'act']):
            steps = [
                {"id": 1, "name": "Legal Research", "description": f"Search forest laws for: {task[:80]}"},
                {"id": 2, "name": "Synthesize Legal Analysis", "description": "Compile findings into IRAC format."}
            ]
        else:
            steps = [
                {"id": 1, "name": "Research", "description": f"Search for information on: {task[:80]}"},
                {"id": 2, "name": "Synthesize", "description": "Compile findings into a report."}
            ]

        return {
            "plan_name": "task_plan",
            "sub_tasks": steps
        }

    def _think_response(self, prompt: str) -> Dict[str, Any]:
        """Decide the next action based on prompt keywords and progress."""
        prompt_lower = prompt.lower()

        # Check progress
        progress_match = None
        if "progress:" in prompt_lower:
            try:
                parts = prompt_lower.split("progress:")[1].strip().split("\n")[0]
                current, total = parts.split("/")
                progress_match = (int(current.strip()), int(total.strip()))
            except Exception:
                pass

        # If near the end of plan, complete
        if progress_match and progress_match[0] >= progress_match[1] - 1:
            return {
                "thought": "All plan steps completed. Synthesizing final answer.",
                "action": "complete",
                "parameters": {}
            }

        # Check past actions to avoid repeating
        past_actions = []
        if "past actions" in prompt_lower or "past_actions" in prompt_lower:
            if "web_search" in prompt_lower and prompt_lower.count("web_search") > 2:
                # Already searched multiple times, try a different tool
                if "patrol" in prompt_lower or "schedule" in prompt_lower:
                    return {
                        "thought": "Already searched. Now generating patrol schedule.",
                        "action": "patrol_planner",
                        "parameters": {}
                    }
                elif "law" in prompt_lower or "legal" in prompt_lower:
                    return {
                        "thought": "Already searched. Now consulting legal specialist.",
                        "action": "law_specialist",
                        "parameters": {"query": self._extract_task(prompt)}
                    }
                else:
                    return {
                        "thought": "Sufficient data gathered. Completing task.",
                        "action": "complete",
                        "parameters": {}
                    }

        # Default: search first
        task = self._extract_task(prompt)
        task_lower_extracted = task.lower()

        if any(kw in task_lower_extracted for kw in ['patrol', 'schedule', 'deploy']):
            return {
                "thought": "Task requires patrol scheduling.",
                "action": "patrol_planner",
                "parameters": {}
            }
        elif any(kw in task_lower_extracted for kw in ['law', 'legal', 'penalty', 'fine']):
            return {
                "thought": "Task requires legal consultation.",
                "action": "law_specialist",
                "parameters": {"query": task[:150]}
            }
        else:
            return {
                "thought": "Gathering initial information via web search.",
                "action": "web_search",
                "parameters": {"query": task[:150]}
            }

    def _synthesize_response(self, prompt: str) -> str:
        """Return empty string to force ReActAgent's detailed template fallback."""
        return ""

    def _extract_task(self, prompt: str) -> str:
        """Extract the core task from a prompt string."""
        # Look for "TASK:" marker
        if "TASK:" in prompt:
            task_part = prompt.split("TASK:")[1]
            # Take until next known marker
            for marker in ["PROGRESS:", "PAST ACTIONS:", "AVAILABLE TOOLS:", "CONTEXT:", "EVIDENCE", "INSTRUCTION:"]:
                if marker in task_part:
                    task_part = task_part.split(marker)[0]
                    break
            return task_part.strip()[:200]

        # Fallback: first meaningful line
        lines = [l.strip() for l in prompt.split('\n') if l.strip() and len(l.strip()) > 10]
        return lines[0][:200] if lines else prompt[:200]
