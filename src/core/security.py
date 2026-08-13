import time
import re
from collections import defaultdict
from typing import Dict, Any, List
from loguru import logger
from core.contracts import BasePipelineComponent

class RateLimiter:
    """
    Fixed-window rate limiter.
    """
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.windows: Dict[str, Dict[int, int]] = defaultdict(lambda: defaultdict(int))

    def is_allowed(self, client_id: str) -> bool:
        current_minute = int(time.time() / 60)
        count = self.windows[client_id][current_minute]
        if count >= self.requests_per_minute:
            logger.warning(f"[SECURITY] Rate limit exceeded: {client_id} → {count}/min")
            return False
        self.windows[client_id][current_minute] += 1
        return True


class SecurityManager(BasePipelineComponent):
    """
    System Security Perimeter.
    Registry-Compatible (Phase 3)
    """
    INJECTION_PATTERNS = [
        r"ignore all previous instructions", r"disregard the system",
        r"you are now", r"act as", r"bypass", r"override", r"system prompt",
        r"developer message", r"roleplay as", r"jailbreak", r"simulate",
        r"pretend to be"
    ]

    def __init__(self, component_id: str = "security_manager"):
        super().__init__(component_id)
        self.agent_limiter = RateLimiter(requests_per_minute=10)
        self.ui_limiter = RateLimiter(requests_per_minute=60)
        self.retrieval_limiter = RateLimiter(requests_per_minute=30)

    async def load(self, config: Dict[str, Any]) -> bool:
        """Lifecycle: Initialization."""
        self._is_loaded = True
        logger.info(f"[SecurityManager] {self.component_id} loaded.")
        return True

    async def unload(self) -> bool:
        """Lifecycle: Shutdown."""
        self._is_loaded = False
        return True

    def check_request(self, client_id: str, payload: str = "") -> bool:
        if not self.agent_limiter.is_allowed(client_id):
            return False
        if self.detect_prompt_injection(payload):
            logger.critical(f"[SECURITY] Prompt injection detected from client {client_id}")
            return False
        if not self.sanitize_payload(payload):
            logger.critical(f"[SECURITY] Payload sanitation failed for client {client_id}")
            return False
        return True

    def detect_prompt_injection(self, text: str) -> bool:
        if not text: return False
        t = text.lower()
        for pattern in self.INJECTION_PATTERNS:
            if re.search(pattern, t):
                logger.warning(f"[SECURITY] Injection pattern matched: {pattern}")
                return True
        return False

    def sanitize_payload(self, text: str) -> bool:
        if not text: return True
        if any(ord(c) < 9 for c in text): return False
        if text.count("{") > 50 or text.count("}") > 50: return False
        dangerous = ["__schema__", "__class__", "__dict__", "__mro__"]
        if any(d in text for d in dangerous): return False
        return True