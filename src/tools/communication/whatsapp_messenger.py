import logging
import os
import requests
import urllib.parse
from typing import Dict, Any
from tools.base_tool import BaseTool

logger = logging.getLogger(__name__)

class WhatsAppMessenger(BaseTool):
    """
    Sends real-world WhatsApp notifications using the CallMeBot API bridge.
    Zero-cost, stable, and easy to set up.
    """
    def __init__(self):
        super().__init__(
            name="whatsapp_messenger",
            description="Sends official WhatsApp alerts and reports for immediate action."
        )

    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        phone = parameters.get("phone") or os.getenv("DFO_PHONE_NUMBER")
        message = parameters.get("message", "GreenLawAI: Urgent Forest Alert!")
        api_key = os.getenv("WHATSAPP_API_KEY")

        if not phone:
            return {"status": "error", "message": "No phone number found in parameters or .env."}
        
        if not api_key:
            return {
                "status": "error", 
                "message": "WHATSAPP_API_KEY missing. Please follow WHATSAPP_SETUP_GUIDE.md to get your free key."
            }

        # Format phone for CallMeBot: international format without '+'
        clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "")
        
        try:
            # URL Encoding the message
            encoded_msg = urllib.parse.quote(message)
            url = f"https://api.callmebot.com/whatsapp.php?phone={clean_phone}&text={encoded_msg}&apikey={api_key}"
            
            logger.info(f"[WhatsAppMessenger] Dispatching to {clean_phone} via CallMeBot...")
            
            resp = requests.get(url, timeout=15)
            
            if resp.status_code == 200:
                return {
                    "status": "success",
                    "recipient": phone,
                    "message": "WhatsApp message dispatched successfully via CallMeBot bridge."
                }
            else:
                logger.error(f"[WhatsAppMessenger] Bridge failed: {resp.text}")
                return {"status": "error", "message": f"WhatsApp Bridge error: {resp.status_code}"}
                
        except Exception as e:
            logger.error(f"[WhatsAppMessenger] Exception: {e}")
            return {"status": "error", "message": str(e)}
