# E:\GL_AI\src\tools\communication\email_dfo.py

import logging
import os
import smtplib
import ssl
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


class DFONotifier:

    def __init__(self):
        self.name = "dfo_notifier"

        # DFO contacts
        self.contacts = {
            "default": {
                "name": "DFO Hazara Circle",
                "email": "alihinaali2022@gmail.com",
                "phone": "+923495994503"
            },
            "Swat": {
                "name": "DFO Swat",
                "email": "alihinaali2022@gmail.com",
                "phone": "+923495994503"
            },
            "Abbottabad": {
                "name": "DFO Abbottabad",
                "email": "alihinaali2022@gmail.com",
                "phone": "+923495994503"
            },
            "Mansehra": {
                "name": "DFO Mansehra",
                "email": "alihinaali2022@gmail.com",
                "phone": "+923495994503"
            }
        }

        # Email configuration (UNCHANGED)
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "465"))
        self.sender_email = os.getenv("SMTP_SENDER", "alihinaali2022@gmail.com")
        self.sender_password = os.getenv("SMTP_PASSWORD", "")
        self.can_send_email = bool(self.sender_email and self.sender_password)
        self.is_development = os.getenv('ENVIRONMENT') == 'development'

        # Twilio configuration (NEW)
        self.twilio_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
        self.twilio_token = os.getenv("TWILIO_AUTH_TOKEN", "")
        self.twilio_from = os.getenv("TWILIO_FROM_NUMBER", "")
        self.can_send_sms = bool(self.twilio_sid and self.twilio_token and self.twilio_from)

        logger.info(
            f"[DFO] Init: can_send_email={self.can_send_email}, "
            f"can_send_sms={self.can_send_sms}, is_development={self.is_development}"
        )

    async def get_dfo_contact(self, region: str) -> Dict[str, str]:
        """Get DFO contact for a region"""
        region_lower = region.lower()
        for key in self.contacts.keys():
            if key.lower() in region_lower:
                return self.contacts[key]
        return self.contacts["default"]

    # ============================================================
    # EMAIL (UNCHANGED)
    # ============================================================

    async def notify(self, region: str, message: str) -> Dict[str, Any]:
        """
        Send REAL notification to DFO via email
        """
        logger.info(f"[DFO] Notifying DFO for {region}")

        dfo = await self.get_dfo_contact(region)

        if self.is_development:
            logger.info(f"[DFO] DEV MODE: Would send email to {dfo['email']}")
            return {
                'notification_sent': False,
                'mode': 'development',
                'message': f"[DEV] Would notify {dfo['name']}: {message[:100]}..."
            }

        if self.can_send_email:
            try:
                email_sent = await self._send_email(dfo, message, region)
                if email_sent:
                    return {
                        'notification_sent': True,
                        'method': 'email',
                        'dfo': dfo['name'],
                        'email': dfo['email'],
                        'timestamp': datetime.now().isoformat()
                    }
                else:
                    return {
                        'notification_sent': False,
                        'error': 'Email sending failed'
                    }
            except Exception as e:
                logger.error(f"[DFO] Email error: {e}")
                return {
                    'notification_sent': False,
                    'error': str(e)
                }
        else:
            logger.warning(f"[DFO] No email credentials. Would notify: {message[:100]}")
            return {
                'notification_sent': False,
                'mode': 'no_credentials',
                'message': f"Would notify {dfo['name']}: {message[:100]}..."
            }

    async def _send_email(self, dfo: Dict, message: str, region: str) -> bool:
        """Actually send email via SMTP"""
        try:
            subject = f"🚨 EMERGENCY ALERT: Forest Fire in {region} 🚨"

            full_message = f"""
            🚨 FOREST FIRE EMERGENCY NOTIFICATION 🚨

            DFO: {dfo['name']}
            Region: {region}
            Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

            Message:
            {message}

            ---------------------------------------------------
            This is an automated alert from GreenLawAI System.
            Immediate action is required.
            """

            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = dfo['email']
            msg['Subject'] = subject
            msg.attach(MIMEText(full_message, 'plain'))

            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, context=context, timeout=30) as server:
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)

            logger.info(f"[DFO] Email sent to {dfo['email']}")
            return True

        except Exception as e:
            logger.error(f"[DFO] Email send failed: {e}")
            return False

    # ============================================================
    # SMS (REPLACED - now uses Twilio instead of email-to-SMS gateways)
    # ============================================================

    async def send_sms(self, phone_number: str, message: str) -> bool:
        """
        Send REAL SMS via Twilio.
        """
        logger.info(f"[SMS] send_sms() called for {phone_number}")

        if self.is_development:
            logger.info(f"[SMS] DEV MODE: Would send SMS to {phone_number}: {message[:80]}...")
            return False

        if not self.can_send_sms:
            logger.warning(
                "[SMS] No Twilio credentials configured "
                "(check TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_FROM_NUMBER in .env)."
            )
            return False

        if not phone_number:
            logger.warning("[SMS] No phone number provided.")
            return False

        # Normalize to E.164 format
        clean_number = phone_number.replace(' ', '').replace('-', '')
        if not clean_number.startswith('+'):
            clean_number = clean_number.lstrip('0')
            if clean_number.startswith('92'):
                clean_number = '+' + clean_number
            else:
                clean_number = '+92' + clean_number

        sms_text = message[:1600]  # Twilio allows longer than 160, but keep it reasonable

        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.twilio_sid}/Messages.json"
        payload = {
            "From": self.twilio_from,
            "To": clean_number,
            "Body": sms_text,
        }

        try:
            response = requests.post(
                url,
                data=payload,
                auth=(self.twilio_sid, self.twilio_token),
                timeout=15
            )

            if response.status_code in (200, 201):
                resp_json = response.json()
                logger.info(
                    f"[SMS] SMS sent to {clean_number} via Twilio "
                    f"(sid={resp_json.get('sid')}, status={resp_json.get('status')})"
                )
                return True
            else:
                logger.error(
                    f"[SMS] Twilio error {response.status_code} for {clean_number}: {response.text}"
                )
                return False

        except Exception as e:
            logger.error(f"[SMS] Twilio send failed for {clean_number}: {e}")
            return False

    async def send_bulk_sms(self, phone_numbers: List[str], message: str) -> Dict[str, bool]:
        """Send SMS to multiple phone numbers."""
        results = {}
        for number in phone_numbers:
            results[number] = await self.send_sms(number, message)
        return results

    async def send_emergency_alerts(self, region: str, message: str, phone_numbers: List[str] = None) -> Dict[str, Any]:
        """Send both email and SMS alerts."""
        email_result = await self.notify(region, message)

        if phone_numbers is None:
            dfo = await self.get_dfo_contact(region)
            phone_numbers = [dfo.get('phone')] if dfo.get('phone') else []

        sms_results = {}
        for number in phone_numbers:
            if number:
                sms_results[number] = await self.send_sms(number, message)

        return {
            'email': email_result,
            'sms': sms_results,
            'notification_sent': email_result.get('notification_sent', False) or any(sms_results.values())
        }