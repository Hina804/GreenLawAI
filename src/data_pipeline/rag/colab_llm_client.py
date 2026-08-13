"""
Colab LLM Client — Fixed Version
Connects to GPU-accelerated LLM server running on Google Colab.

FIXES vs previous version:
  - HTTP support (no SSL errors)
  - Auto URL reload from .env
  - Prompt-based API (not context/question split)
  - Better error messages
  - URL hot-swap without restart
"""

import requests
import urllib3
import time
import os
from typing import Optional, Iterator
from loguru import logger

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class ColabLLMClient:
    """
    Client for Colab-hosted LLM server.
    Supports both HTTP (ngrok free) and HTTPS (ngrok paid) tunnels.
    """

    def __init__(self, colab_url: str, timeout: int = 120):
        self.timeout  = timeout
        self.is_degraded = False

        # Normalise URL — strip trailing slash
        self.colab_url = colab_url.rstrip("/")

        # Single session — SSL verification disabled for ngrok self-signed certs
        self.session         = requests.Session()
        self.session.verify  = False
        self.session.headers.update({"ngrok-skip-browser-warning": "any"})

        logger.info(f"[ColabLLMClient] Target: {self.colab_url}")
        self._verify_connection()

    # ── URL management ────────────────────────────────────────────────────────

    def update_url(self, new_url: str) -> None:
        """Hot-swap the Colab URL without restarting the app."""
        self.colab_url   = new_url.rstrip("/")
        self.is_degraded = False
        logger.info(f"[ColabLLMClient] URL updated to: {self.colab_url}")
        self._verify_connection()

    def reload_url_from_env(self) -> bool:
        """Re-read COLAB_URL from .env file and update if changed."""
        try:
            from dotenv import dotenv_values
            env = dotenv_values("E:/GL_AI/.env")
            new_url = env.get("COLAB_URL", "").strip().strip('"').strip("'")
            if new_url and new_url != self.colab_url:
                logger.info(f"[ColabLLMClient] New URL from .env: {new_url}")
                self.update_url(new_url)
                return True
        except Exception as e:
            logger.warning(f"[ColabLLMClient] Could not reload .env: {e}")
        return False

    # ── Connection check ──────────────────────────────────────────────────────

    def _verify_connection(self) -> bool:
        try:
            r = self.session.get(
                f"{self.colab_url}/health",
                timeout=8
            )
            if r.status_code == 200:
                data = r.json()
                logger.info(
                    f"[ColabLLMClient] Connected — "
                    f"GPU={data.get('gpu', '?')} "
                    f"model={data.get('model', 'unknown')}"
                )
                self.is_degraded = False
                return True
            elif r.status_code == 404:
                # Server up but no /health endpoint — still usable
                logger.info("[ColabLLMClient] Server up (no /health endpoint)")
                self.is_degraded = False
                return True
            else:
                logger.warning(f"[ColabLLMClient] Health returned {r.status_code}")
                self.is_degraded = True
                return False
        except Exception as e:
            if "ERR_NGROK_3200" in str(e) or "3200" in str(e):
                logger.error("[ColabLLMClient] Colab session is OFFLINE (ERR_NGROK_3200). "
                             "Please restart the Colab notebook and update COLAB_URL in .env")
            else:
                logger.warning(f"[ColabLLMClient] Health check failed: {e}")
            self.is_degraded = True
            return False

    def health_check(self) -> bool:
        return self._verify_connection()

    # ── Main generation ───────────────────────────────────────────────────────

    def generate(
        self,
        context:     str  = "",
        question:    str  = "",
        prompt:      str  = "",          # ← new: accept full prompt directly
        max_tokens:  int  = 600,
        temperature: float = 0.1,
        **kwargs
    ) -> str:
        """
        Generate text from the Colab LLM.

        Accepts either:
          - prompt= (full prompt string)
          - context= + question= (legacy split format)
        """
        # Build the effective prompt
        if prompt:
            effective_prompt   = prompt
            effective_context  = ""
            effective_question = prompt
        else:
            effective_prompt   = f"Context: {context}\nQuestion: {question}\nAnswer:"
            effective_context  = context
            effective_question = question

        start = time.time()
        last_error = None

        for attempt in range(3):
            try:
                r = self.session.post(
                    f"{self.colab_url}/generate",
                    json={
                        # Send both formats so any server version works
                        "prompt":             effective_prompt,
                        "context":            effective_context,
                        "question":           effective_question,
                        "max_tokens":         max_tokens,
                        "max_new_tokens":     max_tokens,
                        "temperature":        temperature,
                        "do_sample":          temperature > 0,
                        "repetition_penalty": kwargs.get("repetition_penalty", 1.3),
                    },
                    timeout=self.timeout
                )

                if r.status_code == 200:
                    data   = r.json()
                    answer = (
                        data.get("answer") or
                        data.get("response") or
                        data.get("generated_text") or
                        data.get("text") or
                        ""
                    )
                    answer = self._clean_answer(answer, effective_question)
                    elapsed = time.time() - start
                    logger.info(f"[ColabLLMClient] Generated in {elapsed:.1f}s "
                                f"({len(answer)} chars)")
                    self.is_degraded = False
                    return answer

                elif r.status_code in (502, 503, 504):
                    # Gateway errors — tunnel alive but model loading
                    logger.warning(f"[ColabLLMClient] {r.status_code} — model may be loading")
                    time.sleep(3)
                    continue

                else:
                    raise Exception(f"HTTP {r.status_code}: {r.text[:200]}")

            except (requests.exceptions.SSLError,
                    requests.exceptions.ConnectionError) as e:
                last_error = e
                logger.warning(f"[ColabLLMClient] Attempt {attempt+1}/3 failed: "
                               f"{type(e).__name__}")
                if attempt < 2:
                    time.sleep(2)
                continue

            except Exception as e:
                last_error = e
                # Check for ngrok offline error
                if "ERR_NGROK_3200" in str(e) or "3200" in str(e):
                    logger.error(
                        "[ColabLLMClient] Colab is OFFLINE. "
                        "Restart Colab notebook and update COLAB_URL in .env"
                    )
                    self.is_degraded = True
                    raise Exception(
                        "LLM offline — Colab session ended. "
                        "Please restart the Colab notebook and update COLAB_URL."
                    )
                if attempt < 2:
                    time.sleep(1)
                continue

        self.is_degraded = True
        raise Exception(
            f"LLM connection failed after 3 attempts: {last_error}"
        )

    def generate_stream(
        self,
        context:  str = "",
        question: str = "",
        prompt:   str = "",
        **kwargs
    ) -> Iterator[str]:
        """Streaming wrapper — yields full answer at once."""
        answer = self.generate(
            context=context,
            question=question,
            prompt=prompt,
            **kwargs
        )
        yield answer

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _clean_answer(self, raw: str, question: str) -> str:
        """Remove repeated question prefix and repetition loops."""
        if not raw:
            return ""

        text = raw.strip()

        # Strip echoed question/prompt prefix
        for prefix in (
            f"Question: {question}",
            f"Context:",
            "Answer:",
        ):
            if text.startswith(prefix):
                text = text[len(prefix):].strip()

        # Cut at "Answer:" if model repeated the full prompt
        if "Answer:" in text:
            text = text.split("Answer:")[-1].strip()

        # Fragment loop killer (Phi-2 tends to repeat)
        if len(text) > 200:
            chunk = 40
            for i in range(0, len(text) - chunk, 20):
                fragment = text[i: i + chunk]
                if text.count(fragment) > 3:
                    second = text.find(fragment, text.find(fragment) + 1)
                    if second > 0:
                        text = text[:second].strip()
                    break

        return text or "No answer generated."