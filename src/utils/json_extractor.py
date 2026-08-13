"""
Robust JSON Extraction Utility.
Handles all failure modes from small LLMs (Phi-2):
- Prompt echoing
- Malformed JSON
- Plain text responses
- Extra data after valid JSON
"""

import re
import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class JSONExtractor:
    """
    Extract JSON from LLM responses even when they include extra text,
    prompt echoes, or malformed structures.
    """

    # Known tool names for keyword-based recovery
    TOOL_KEYWORDS = {
        'web_search': ['search', 'find', 'look up', 'google', 'internet', 'query'],
        'patrol_planner': ['patrol', 'schedule', 'deploy', 'guards', 'ranger'],
        'law_specialist': ['law', 'legal', 'section', 'act', 'penalty', 'fine'],
        'search_forest_laws': ['forest', 'timber', 'deodar', 'wildlife'],
        'complete': ['complete', 'done', 'finish', 'final', 'answer', 'synthesize', 'conclude'],
    }

    @staticmethod
    def extract(text: str) -> Optional[Dict[str, Any]]:
        """
        Multi-strategy JSON extraction from any LLM output.
        Returns parsed dict or None.
        """
        if not text or not text.strip():
            return None

        cleaned = text.strip()

        # Strategy 1: Try direct parse (best case)
        result = JSONExtractor._try_direct(cleaned)
        if result:
            return result

        # Strategy 2: Extract from code blocks
        result = JSONExtractor._try_code_blocks(cleaned)
        if result:
            return result

        # Strategy 3: Balanced brace extraction (handles prompt echoing)
        result = JSONExtractor._try_balanced_braces(cleaned)
        if result:
            return result

        # Strategy 4: Regex cleanup and retry
        result = JSONExtractor._try_regex_cleanup(cleaned)
        if result:
            return result

        logger.debug(f"[JSONExtractor] All strategies failed for: {text[:200]}...")
        return None

    @staticmethod
    def force_action(task: str, llm_response: str) -> Dict[str, Any]:
        """
        When all JSON extraction fails, infer an action from keywords
        in the LLM's plain-text response against known tools.
        """
        response_lower = (llm_response or "").lower()
        task_lower = (task or "").lower()

        # Check LLM response for tool keywords
        for tool_name, keywords in JSONExtractor.TOOL_KEYWORDS.items():
            if any(kw in response_lower for kw in keywords):
                if tool_name == 'complete':
                    return {
                        "thought": "Inferred completion from LLM response.",
                        "action": "complete",
                        "parameters": {}
                    }
                return {
                    "thought": f"Inferred '{tool_name}' from LLM response keywords.",
                    "action": tool_name,
                    "parameters": {"query": task[:150]}
                }

        # Check the original TASK for tool keywords
        for tool_name, keywords in JSONExtractor.TOOL_KEYWORDS.items():
            if tool_name == 'complete':
                continue
            if any(kw in task_lower for kw in keywords):
                return {
                    "thought": f"Inferred '{tool_name}' from task keywords.",
                    "action": tool_name,
                    "parameters": {"query": task[:150]}
                }

        # Ultimate fallback: web_search with the task itself
        return {
            "thought": "All extraction failed. Using web_search as default.",
            "action": "web_search",
            "parameters": {"query": task[:150]}
        }

    # --- Private Strategies ---

    @staticmethod
    def _try_direct(text: str) -> Optional[Dict]:
        try:
            return json.loads(text)
        except Exception:
            return None

    @staticmethod
    def _try_code_blocks(text: str) -> Optional[Dict]:
        patterns = [
            r'```json\s*([\s\S]*?)\s*```',
            r'```\s*([\s\S]*?)\s*```',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in reversed(matches):  # Try LAST match first
                try:
                    return json.loads(match.strip())
                except Exception:
                    continue
        return None

    @staticmethod
    def _try_balanced_braces(text: str) -> Optional[Dict]:
        """
        Find the LAST balanced {} block in the text.
        This is the most reliable strategy for prompt-echoing models.
        """
        # Find all '{' positions
        brace_starts = [i for i, c in enumerate(text) if c == '{']

        # Try from the LAST one backwards
        for start in reversed(brace_starts):
            depth = 0
            in_str = False
            escape_next = False
            end = -1

            for i in range(start, len(text)):
                ch = text[i]
                if escape_next:
                    escape_next = False
                    continue
                if ch == '\\':
                    escape_next = True
                    continue
                if ch == '"' and not escape_next:
                    in_str = not in_str
                    continue
                if in_str:
                    continue
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        end = i
                        break

            if end > start:
                candidate = text[start:end + 1]
                try:
                    return json.loads(candidate)
                except Exception:
                    # Try with regex cleanup
                    fixed = JSONExtractor._fix_common_errors(candidate)
                    try:
                        return json.loads(fixed)
                    except Exception:
                        continue
        return None

    @staticmethod
    def _try_regex_cleanup(text: str) -> Optional[Dict]:
        """Last resort: find any {} and aggressively fix it."""
        start = text.rfind('{')
        end = text.rfind('}')
        if start == -1 or end == -1 or start >= end:
            return None

        candidate = text[start:end + 1]
        fixed = JSONExtractor._fix_common_errors(candidate)
        try:
            return json.loads(fixed)
        except Exception:
            return None

    @staticmethod
    def _fix_common_errors(text: str) -> str:
        """Fix common Phi-2 JSON formatting errors."""
        # Add quotes to unquoted keys
        text = re.sub(r'(?<=[{,])\s*(\w+)\s*:', r' "\1":', text)
        # Remove trailing commas
        text = re.sub(r',\s*([}\]])', r'\1', text)
        # Fix single quotes to double quotes
        text = text.replace("'", '"')
        return text
