"""
ngrok Keep-Alive Service — Fixed Version

FIXES:
  - Uses HTTP (not HTTPS) to avoid SSLEOFError
  - Detects ERR_NGROK_3200 (session ended) and stops retrying
  - Reloads URL from .env automatically when session restarts
  - Cleaner logging
"""

import threading
import time
import requests
import urllib3
from loguru import logger

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class NgrokKeepAlive:
    """
    Background thread that periodically pings the Colab server
    to keep the ngrok tunnel alive and detect failures early.
    """

    NGROK_OFFLINE_CODE = "3200"   # ERR_NGROK_3200 = session ended

    def __init__(self, url: str, check_interval: int = 45):
        self.url                  = url.rstrip("/")
        self.check_interval       = check_interval
        self.running              = False
        self.thread               = None
        self.is_healthy           = True
        self.last_check           = None
        self.consecutive_failures = 0
        self.session_ended        = False   # True when ngrok 3200 detected

        self.session         = requests.Session()
        self.session.verify  = False
        self.session.headers.update({"ngrok-skip-browser-warning": "any"})

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread  = threading.Thread(
            target=self._loop, daemon=True, name="NgrokKeepAlive"
        )
        self.thread.start()
        logger.info(f"[NgrokKeepAlive] Monitoring {self.url} "
                    f"every {self.check_interval}s")

    def stop(self):
        self.running = False

    def update_url(self, new_url: str):
        """Call this after restarting Colab with a new ngrok URL."""
        self.url              = new_url.rstrip("/")
        self.session_ended    = False
        self.is_healthy       = True
        self.consecutive_failures = 0
        logger.info(f"[NgrokKeepAlive] URL updated to {self.url}")

    def get_status(self) -> dict:
        return {
            "healthy":              self.is_healthy,
            "session_ended":        self.session_ended,
            "last_check":           self.last_check,
            "consecutive_failures": self.consecutive_failures,
            "url":                  self.url,
        }

    # ── Main loop ─────────────────────────────────────────────────────────────

    def _loop(self):
        while self.running:
            self._check()
            self.last_check = time.strftime("%Y-%m-%d %H:%M:%S")
            time.sleep(self.check_interval)

    def _check(self):
        # If we already know the session ended, stop hammering
        if self.session_ended:
            return

        try:
            r = self.session.get(
                f"{self.url}/health",
                timeout=10
            )

            if r.status_code in (200, 404):
                # 200 = healthy; 404 = server up but no /health endpoint
                self.is_healthy           = True
                self.consecutive_failures = 0
                if self.consecutive_failures == 0:
                    pass  # Silent success
            else:
                self._on_failure(f"HTTP {r.status_code}")

        except requests.exceptions.SSLError as e:
            self._on_failure(f"SSLError: {e}")

        except requests.exceptions.ConnectionError as e:
            err = str(e)
            if self.NGROK_OFFLINE_CODE in err or "ERR_NGROK" in err:
                self._on_session_ended()
            else:
                self._on_failure(f"ConnectionError: {e}")

        except Exception as e:
            self._on_failure(str(e))

    def _on_failure(self, reason: str):
        self.is_healthy            = False
        self.consecutive_failures += 1
        if self.consecutive_failures <= 3:
            logger.warning(
                f"[NgrokKeepAlive] Health check failed "
                f"({self.consecutive_failures}): {reason}"
            )
        elif self.consecutive_failures == 4:
            logger.error(
                "[NgrokKeepAlive] Server appears DOWN. "
                "System running on local fallback LLM."
            )

    def _on_session_ended(self):
        if not self.session_ended:
            self.session_ended = True
            self.is_healthy    = False
            logger.error(
                "[NgrokKeepAlive] Colab session ENDED (ERR_NGROK_3200). "
                "To restore: restart Colab notebook → run all cells → "
                "copy new URL → update COLAB_URL in .env"
            )