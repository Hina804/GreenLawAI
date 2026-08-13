"""
LLM Bridge - Hardened Edition.
Bridges the legacy LLMManager to the async interface expected by ReActAgent.
Now includes:
- JSONExtractor integration (4-strategy parsing)
- LocalFallbackLLM activation on repeated failures
- Echo stripping for small models
"""

import logging
import json
import asyncio
from typing import Dict, Any, Optional, Generator
from data_pipeline.rag.llm_manager import LLMManager
from utils.json_extractor import JSONExtractor
from llm.local_fallback import LocalFallbackLLM

logger = logging.getLogger(__name__)


class LLMBridge:
    """
    Bridges the legacy LLMManager (sync/streaming) to the
    async JSON/Text interface expected by the ReActAgent.
    Includes automatic fallback to LocalFallbackLLM on repeated failures.
    """

    def __init__(self, manager: LLMManager):
        self.manager = manager
        self.fallback = LocalFallbackLLM()
        self._consecutive_failures = 0
        self._failure_threshold = 3  # Switch to fallback after 3 consecutive failures

    @property
    def is_degraded(self) -> bool:
        """True if the bridge has switched to fallback mode."""
        return self._consecutive_failures >= self._failure_threshold

    async def generate_text(self, prompt: str, retries: int = 3) -> str:
        """
        Asynchronously generates plain text from the LLM.
        Falls back to LocalFallbackLLM if remote is consistently failing.
        """
        # If degraded, use fallback immediately
        if self.is_degraded:
            logger.warning("[LLMBridge] DEGRADED MODE: Using LocalFallbackLLM for text.")
            result = self.fallback._synthesize_response(prompt)
            if isinstance(result, str):
                return result
            return json.dumps(result)

        for i in range(retries):
            try:
                logger.debug(f"[LLMBridge] Generating text (Attempt {i+1}/{retries})...")

                def _sync_gen():
                    full_text = ""
                    for token in self.manager.generate(prompt, stream=False):
                        full_text += token
                    return full_text

                raw_text = await asyncio.to_thread(_sync_gen)

                # ECHO STRIPPING
                prompt_tail = prompt.strip()[-50:]
                if prompt_tail in raw_text:
                    content_start = raw_text.rfind(prompt_tail) + len(prompt_tail)
                    stripped = raw_text[content_start:].strip()
                    if stripped:
                        self._consecutive_failures = 0  # Reset on success
                        return stripped

                if raw_text.strip():
                    self._consecutive_failures = 0
                    return raw_text.strip()

                # Empty response
                logger.warning("[LLMBridge] Received empty text from LLM.")
                self._consecutive_failures += 1

            except Exception as e:
                self._consecutive_failures += 1
                if i == retries - 1:
                    logger.error(f"[LLMBridge] Final text attempt failed: {e}")
                    # Don't raise - return fallback text
                    return self.fallback._synthesize_response(prompt) if isinstance(
                        self.fallback._synthesize_response(prompt), str
                    ) else "Unable to generate response at this time."
                logger.warning(f"[LLMBridge] Attempt {i+1} failed ({e}). Retrying in 1s...")
                await asyncio.sleep(1)

        return "Unable to generate response at this time."

    async def generate_json(self, prompt: str, task_context: str = "") -> Dict[str, Any]:
        """
        Generates and parses JSON from the LLM using JSONExtractor.
        Falls back to keyword-based action inference if all parsing fails.
        Falls back to LocalFallbackLLM if remote is consistently failing.
        """
        # If degraded, use fallback immediately
        if self.is_degraded:
            logger.warning("[LLMBridge] DEGRADED MODE: Using LocalFallbackLLM for JSON.")
            return self.fallback.generate_json(prompt)

        try:
            text = await self.generate_text(prompt)
        except Exception as e:
            logger.error(f"[LLMBridge] Text generation failed completely: {e}")
            self._consecutive_failures += 1
            return self.fallback.generate_json(prompt)

        if not text or not text.strip():
            logger.warning("[LLMBridge] Empty text from LLM. Using fallback.")
            self._consecutive_failures += 1
            return self.fallback.generate_json(prompt)

        # === STAGE 1: Use JSONExtractor (4 strategies) ===
        result = JSONExtractor.extract(text)
        if result:
            self._consecutive_failures = 0
            return result

        # === STAGE 2: Keyword-based action inference ===
        logger.warning(f"[LLMBridge] JSONExtractor failed. Trying keyword inference...")
        result = JSONExtractor.force_action(task_context or prompt, text)
        if result:
            self._consecutive_failures += 1  # Still a partial failure
            return result

        # === STAGE 3: LocalFallbackLLM ===
        logger.error(f"[LLMBridge] All extraction failed. Using LocalFallbackLLM. Raw: {text[:200]}...")
        self._consecutive_failures += 1
        return self.fallback.generate_json(prompt)
