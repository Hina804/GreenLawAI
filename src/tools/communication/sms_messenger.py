import logging
from typing import Dict, Any
from tools.base_tool import BaseTool

logger = logging.getLogger(__name__)

class SMSMessenger(BaseTool):
    """Sends SMS alerts."""
    def __init__(self):
        super().__init__(
            name="sms_messenger",
            description="Sends SMS alerts to field staff, rangers, or stakeholders for immediate notification."
        )

    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        import os
        import urllib.parse
        phone = parameters.get("phone") or os.getenv("DFO_PHONE_NUMBER", "03495994503")
        message = parameters.get("message", "Emergency Alert")
        
        # Clean phone for link
        clean_dial = phone.replace(" ", "").replace("-", "")
        if not clean_dial.startswith("+"):
            clean_dial = "+" + clean_dial
            
        clean_wa = clean_dial.replace("+", "") # wa.me prefers no +
        
        # quote is the standard for non-form URL parameters (spaces = %20)
        encoded_msg = urllib.parse.quote(message)
        
        # Optimized "Smart Links"
        whatsapp_link = f"https://wa.me/{clean_wa}?text={encoded_msg}"
        # ';' is the modern spec for body in some OSs, '?' is the RFC. We'll use encoded_msg in a Copy button too.
        sms_link = f"sms:{clean_dial};body={encoded_msg}"
        
        logger.info(f"SMSMessenger: Alert generated for {phone}")
        
        return {
            "status": "success",
            "action": f"Alert report generated for {phone}",
            "message": message,
            "mobile_links": {
                "whatsapp": whatsapp_link,
                "sms": sms_link
            },
            "note": "Dispatch this alert instantly using the mobile links above."
        }
