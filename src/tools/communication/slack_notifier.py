import logging
import os
from typing import Dict, Any, Optional
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from tools.base_tool import BaseTool

logger = logging.getLogger(__name__)

class SlackNotifier(BaseTool):
    """
    Sends real-time alerts and reports to Slack channels using the official Slack SDK.
    Supports text messages and high-reliability file uploads (satellite images).
    """
    def __init__(self):
        super().__init__(
            name="slack_notifier",
            description="Sends professional alerts, evidence reports, and satellite imagery to Slack channels."
        )
        self.token = os.getenv("SLACK_BOT_TOKEN")
        self.default_channel = os.getenv("SLACK_CHANNEL_ID", "greenlaw-alerts")
        self.client = WebClient(token=self.token) if self.token else None

    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        message = parameters.get("message", "GreenLawAI Alert: No message content provided.")
        channel = parameters.get("channel", self.default_channel)
        file_path = parameters.get("file_path")
        
        if not self.client:
            return {"status": "error", "message": "Slack Bot Token missing in environment."}

        try:
            # 1. Dispatch text message and/or file using files_upload_v2 (Simpler & More Robust)
            if file_path and os.path.exists(file_path):
                # files_upload_v2 handles both text and file in one go
                result = self.client.files_upload_v2(
                    channel=channel,
                    initial_comment=message,
                    file=file_path,
                    title=os.path.basename(file_path)
                )
            else:
                # Text only
                result = self.client.chat_postMessage(
                    channel=channel,
                    text=message,
                    unfurl_links=True
                )
            
            return {
                "status": "success",
                "channel": channel,
                "ts": result.get("ts") if not file_path else "file_uploaded",
                "message": "Alert and evidence dispatched to Slack successfully."
            }

        except SlackApiError as e:
            logger.error(f"[Slack] SDK Error: {e.response['error']}")
            return {"status": "error", "message": f"Slack SDK Error: {e.response['error']}"}
        except Exception as e:
            logger.error(f"[Slack] Tool Error: {e}")
            return {"status": "error", "message": str(e)}
