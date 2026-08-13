import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any
from tools.base_tool import BaseTool

logger = logging.getLogger(__name__)

class EmailSender(BaseTool):
    """
    Sends official email notifications using real SMTP.
    100% stable fail-safe for any restricted environment.
    """
    def __init__(self):
        super().__init__(
            name="email_sender",
            description="Sends official environmental reports and alerts via secure SMTP email."
        )
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.sender_email = os.getenv("SMTP_SENDER")
        self.sender_password = os.getenv("SMTP_PASSWORD")

    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        recipient = parameters.get("recipient") or os.getenv("DFO_EMAIL", "alihinaali2022@gmail.com")
        subject = parameters.get("subject", "GreenLawAI: Urgent Notification")
        message_body = parameters.get("message", "No message provided")
        
        # --- PHASE 8: HTTPS RELAY BYPASS ---
        # If your network blocks SMTP ports, this will use the Web Relay URL from .env
        relay_url = os.getenv("EMAIL_RELAY_URL")
        if relay_url and relay_url.startswith("http"):
            import requests
            import json
            try:
                logger.info(f"[EmailSender] Attempting HTTPS Relay (Form-POST): {relay_url}")
                # Form-encoded POST is the most stable interaction for Google Apps Script redirects
                payload = {
                    "recipient": recipient,
                    "subject": subject,
                    "message": message_body
                }
                
                # data=payload triggers application/x-www-form-urlencoded
                resp = requests.post(relay_url, data=payload, timeout=25)
                
                if resp.status_code == 200:
                    try:
                        relay_resp = resp.json()
                        if relay_resp.get("status") == "success":
                            return {
                                "status": "success",
                                "recipient": recipient,
                                "message": "Email dispatched successfully via HTTPS Web Relay (Universal Mode)."
                            }
                        else:
                            error_msg = relay_resp.get("message", "Unknown relay error")
                            logger.error(f"[EmailSender] Relay logic failed: {error_msg}")
                            return {"status": "error", "message": f"Web Relay error: {error_msg}"}
                    except json.JSONDecodeError:
                        snippet = resp.text[:200].replace('\n', ' ')
                        logger.error(f"[EmailSender] Relay returned non-JSON: {snippet}")
                        return {"status": "error", "message": f"Web Relay invalid response. Ensure you deployed as 'Anyone'."}
                else:
                    logger.error(f"[EmailSender] Relay failed with HTTP {resp.status_code}")
                    return {"status": "error", "message": f"Web Relay HTTP error {resp.status_code}"}
            except Exception as re:
                logger.error(f"[EmailSender] Relay exception: {re}")

        # --- Standard SMTP Logic (Fallback) ---
        if not self.sender_email or not self.sender_password:
            return {"status": "error", "message": "Email credentials (SMTP_SENDER/SMTP_PASSWORD) missing in .env."}

        try:
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = recipient
            msg['Subject'] = subject
            msg.attach(MIMEText(message_body, 'plain'))

            if self.smtp_port == 465:
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port)
            else:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                server.starttls()
            
            server.login(self.sender_email, self.sender_password)
            server.send_message(msg)
            server.quit()

            logger.info(f"EmailSender: Email sent to {recipient}")
            return {
                "status": "success",
                "recipient": recipient,
                "message": "Email dispatched successfully via secure SMTP."
            }
        except Exception as e:
            logger.error(f"[EmailSender] Error: {e}")
            return {"status": "error", "message": str(e)}
