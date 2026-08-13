# E:\GL_AI\src\agents\permit\permit_application_generator.py
"""
Permit Application Generator
==============================
Creates OFFICIAL APPLICATION FORMS and dispatches them to the DFO via:
  - Email (Gmail SMTP port 465)  -- DFO replies "APPROVED <APP-ID>" or "REJECTED <APP-ID>"
  - WhatsApp (Twilio)   -- same reply protocol
  - SMS fallback        -- same reply protocol
  - Slack               -- mirrors your existing monitoring agent pattern

The DFO NEVER needs to log into the portal.
They receive the application, review the PDF, and reply from wherever they are.
The system polls/listens for those replies and auto-updates permit_store status.
"""

import os
import re
import ssl
import smtplib
import logging
import imaplib
import email as email_lib
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from enum import Enum
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

import requests
from fpdf import FPDF

# Internal Utilities
from utils.pdf_generator import GreenLawPDF, sanitize_text

logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURATION  (override via .env)
# ============================================================
SMTP_SERVER     = os.getenv("SMTP_SERVER",   "smtp.gmail.com")
SMTP_PORT       = int(os.getenv("SMTP_PORT", "465"))
SMTP_SENDER     = os.getenv("SMTP_SENDER",   "")          # alihinaali2022@gmail.com
SMTP_PASSWORD   = os.getenv("SMTP_PASSWORD", "").replace(" ", "")  # vynyrajtgrrgmqgi
EMAIL_RELAY_URL = os.getenv("EMAIL_RELAY_URL", "")       # Google Apps Script fallback

IMAP_SERVER     = "imap.gmail.com"
IMAP_PORT       = 993

DFO_EMAIL       = os.getenv("DFO_EMAIL",     "")          # recipient
DFO_PHONE       = os.getenv("DFO_PHONE_NUMBER", "")       # +923495994503

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_CHANNEL   = os.getenv("SLACK_CHANNEL_ID", "")
SLACK_WEBHOOK   = os.getenv("SLACK_WEBHOOK_URL", "")

TWILIO_SID      = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_TOKEN    = os.getenv("TWILIO_AUTH_TOKEN",  "")
TWILIO_WA_FROM  = os.getenv("TWILIO_WA_FROM",     "whatsapp:+14155238886")
TWILIO_SMS_FROM = os.getenv("TWILIO_SMS_FROM",    "")

APPROVE_KEYWORDS = ["approved", "approve", "منظور", "منظوری"]
REJECT_KEYWORDS  = ["rejected", "reject", "denied", "deny", "مسترد"]


# ============================================================
# Startup credential check
# ============================================================

def check_credentials():
    """Call once at app boot to catch missing config early."""
    issues = []

    if not SMTP_SENDER:
        issues.append("SMTP_SENDER is not set in .env")
    if not SMTP_PASSWORD:
        issues.append(
            "SMTP_PASSWORD is not set in .env  "
            "(should be your 16-char Gmail App Password)"
        )
    if not DFO_EMAIL:
        issues.append("DFO_EMAIL is not set in .env  (DFO recipient address)")
    if not DFO_PHONE:
        issues.append("DFO_PHONE_NUMBER is not set in .env")
    if not TWILIO_SID or not TWILIO_TOKEN:
        issues.append("Twilio credentials missing -- WhatsApp/SMS will run in demo mode")
    if not TWILIO_SMS_FROM:
        issues.append("TWILIO_SMS_FROM not set -- SMS fallback disabled")

    for issue in issues:
        logger.warning(f"[CONFIG] {issue}")

    if not issues:
        logger.info("[CONFIG] All credentials OK.")

    return issues


# ============================================================
# PDF-SAFE TEXT HELPER
# ============================================================

def pdf_safe(text: str) -> str:
    """Replace characters outside Latin-1 with safe ASCII equivalents."""
    if not text:
        return ""
    replacements = {
        "\u2014": "--",
        "\u2013": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201C": '"',
        "\u201D": '"',
        "\u2022": "*",
        "\u2026": "...",
        "\u00A0": " ",
        "\u2122": "(TM)",
        "\u00AE": "(R)",
        "\u00A9": "(C)",
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    return text.encode("latin-1", errors="replace").decode("latin-1")


# ============================================================
# FORM PDF CLASS
# ============================================================

class FormPDF(FPDF):
    """
    Clean government application form PDF.
    No system branding -- only department header and form fields.
    Uses Times (serif) for the formal look of a real printed form.
    """

    # ----------------------------------------------------------
    # Shared drawing helpers
    # ----------------------------------------------------------

    def set_times(self, style: str = "", size: int = 10):
        self.set_font("Times", style, size)

    def set_helvetica(self, style: str = "", size: int = 10):
        self.set_font("Helvetica", style, size)

    def draw_line(self, extra_y: float = 0):
        """Draw a full-width horizontal rule at current Y."""
        y = self.get_y() + extra_y
        self.line(self.l_margin, y, self.w - self.r_margin, y)

    # ----------------------------------------------------------
    # Section title bar  (black background, white text)
    # ----------------------------------------------------------

    def section_bar(self, title: str):
        self.ln(3)
        self.set_fill_color(0, 0, 0)
        self.set_text_color(255, 255, 255)
        self.set_times("B", 9)
        self.cell(0, 6, "  " + pdf_safe(title.upper()), ln=True, fill=True)
        self.set_text_color(0, 0, 0)
        self.set_times("", 10)
        self.ln(2)

    # ----------------------------------------------------------
    # Labelled field helpers
    # ----------------------------------------------------------

    def labelled_field(self, label: str, value: str = "", w: float = 0, ln: bool = False):
        """
        One field: bold label + underlined value area.
        w=0 means full remaining width.
        """
        if w == 0:
            w = self.w - self.l_margin - self.r_margin - self.get_x() + self.l_margin
        self.set_times("B", 8)
        label_w = self.get_string_width(label + ": ") + 1
        self.cell(label_w, 6, pdf_safe(label + ":"), ln=False)
        self.set_times("", 10)
        val_w = w - label_w
        if val_w < 10:
            val_w = 10
        # underline via border-bottom only (cell with "B" border)
        self.cell(val_w, 6, "  " + pdf_safe(value), border="B", ln=True if ln else False)

    def blank_field(self, label: str, w: float = 0, ln: bool = True):
        """Field with no pre-filled value -- shows blank underline."""
        self.labelled_field(label, "", w, ln)

    def two_fields(self, label1: str, val1: str, label2: str, val2: str):
        half = (self.w - self.l_margin - self.r_margin) / 2
        x_start = self.l_margin
        self.set_x(x_start)
        self.labelled_field(label1, val1, half, ln=False)
        self.set_x(x_start + half)
        self.labelled_field(label2, val2, half, ln=True)
        self.ln(1)

    def three_fields(self, items: list):
        """items = [(label, value), ...]  -- 3 per row."""
        third = (self.w - self.l_margin - self.r_margin) / 3
        x_start = self.l_margin
        for i, (lbl, val) in enumerate(items):
            self.set_x(x_start + i * third)
            self.labelled_field(lbl, val, third, ln=(i == 2))
        self.ln(1)

    def multi_line_field(self, label: str, value: str = "", lines: int = 2):
        self.set_times("B", 8)
        self.cell(0, 5, pdf_safe(label + ":"), ln=True)
        self.set_times("", 10)
        for _ in range(lines):
            self.cell(0, 6, "  " + (pdf_safe(value) if _ == 0 else ""), border="B", ln=True)
        self.ln(1)

    def checkbox_row(self, items: list):
        """items = list of label strings."""
        self.set_times("", 9)
        for item in items:
            box_x = self.get_x()
            box_y = self.get_y()
            self.rect(box_x, box_y + 1, 3.5, 3.5)
            self.set_x(box_x + 4.5)
            item_w = self.get_string_width(pdf_safe(item)) + 8
            self.cell(item_w, 6, "  " + pdf_safe(item), ln=False)
        self.ln(7)


# ============================================================
# PERMIT TYPE ENUM
# ============================================================

class PermitType(Enum):
    TIMBER_EXTRACTION   = "timber_extraction"
    FIREWOOD_COLLECTION = "firewood_collection"
    GRAZING             = "grazing"
    NTFP                = "ntfp"
    TRANSIT             = "transit"
    NWFDMA              = "nwfdma"


# ============================================================
# MAIN CLASS
# ============================================================

class PermitApplicationGenerator:
    """
    Generates professional permit APPLICATION FORM PDFs and dispatches
    them to the DFO via Email / WhatsApp / SMS / Slack.
    """

    def __init__(self):
        self.permit_configs: Dict[PermitType, Dict] = {
            PermitType.TIMBER_EXTRACTION: {
                'name':                 'Timber Extraction Permit',
                'section':              'Section 33, KP Forest Ordinance 2002',
                'validity_days':        30,
                'requires_species':     True,
                'requires_quantity':    True,
                'requires_justification': True,
                'requires_girth':       True,
            },
            PermitType.FIREWOOD_COLLECTION: {
                'name':                 'Firewood Collection Permit',
                'section':              'Section 26, KP Forest Ordinance 2002',
                'validity_days':        90,
                'requires_species':     False,
                'requires_quantity':    True,
                'requires_justification': True,
                'requires_girth':       False,
            },
            PermitType.GRAZING: {
                'name':                 'Grazing Permit',
                'section':              'Section 26, Forest Act 1927',
                'validity_days':        365,
                'requires_species':     False,
                'requires_quantity':    True,
                'requires_justification': False,
                'requires_girth':       False,
            },
            PermitType.NTFP: {
                'name':                 'Non-Timber Forest Produce Permit',
                'section':              'Section 33, KP Forest Ordinance 2002',
                'validity_days':        180,
                'requires_species':     False,
                'requires_quantity':    True,
                'requires_justification': True,
                'requires_girth':       False,
            },
            PermitType.TRANSIT: {
                'name':                 'Timber Transit Permit',
                'section':              'Section 41-42, Forest Act 1927',
                'validity_days':        14,
                'requires_species':     True,
                'requires_quantity':    True,
                'requires_justification': False,
                'requires_girth':       False,
            },
            PermitType.NWFDMA: {
                'name':                 'NWFDMA Special Permit',
                'section':              'NWFDMA Regulations',
                'validity_days':        30,
                'requires_species':     False,
                'requires_quantity':    False,
                'requires_justification': True,
                'requires_girth':       False,
            },
        }

    # ============================================================
    # PUBLIC API
    # ============================================================

    async def generate_application(
        self,
        permit_type:      PermitType,
        application_data: Dict,
        application_id:   str,
        supporting_docs:  List[str] = None,
    ) -> bytes:
        """Generate a government-style APPLICATION FORM PDF. Returns PDF bytes."""

        config    = self.permit_configs[permit_type]
        applicant = application_data.get('applicant', {})
        location  = application_data.get('location',  {})
        request   = application_data.get('request',   {})

        application_date  = datetime.now()
        expected_duration = request.get('duration_days', config['validity_days'])
        expected_expiry   = application_date + timedelta(days=expected_duration)

        pdf = FormPDF(orientation='P', unit='mm', format='A4')
        pdf.set_margins(left=18, top=18, right=18)
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.add_page()

        self._build_dept_header(pdf, config, application_id, application_date)
        self._build_receipt_strip(pdf, application_id, application_date)
        self._build_applicant_section(pdf, applicant)
        self._build_location_section(pdf, location)
        self._build_permit_details_section(pdf, permit_type, config, request)
        self._build_resource_section(pdf, permit_type, config, request)

        if config['requires_justification']:
            self._build_justification_section(pdf, request.get('justification', ''))

        self._build_documents_section(pdf, supporting_docs)
        self._build_declaration_section(pdf, application_date, expected_expiry, applicant)
        self._build_official_use_section(pdf, application_id)

        return bytes(pdf.output())

    async def send_application_to_dfo(
        self,
        pdf_bytes:         bytes,
        application_id:    str,
        applicant_name:    str,
        permit_type:       str,
        applicant_contact: str = "",
        dfo_email:         str = DFO_EMAIL,
        dfo_phone:         str = DFO_PHONE,
    ) -> Dict:
        """Dispatch the application PDF to DFO via Email + WhatsApp + SMS + Slack."""
        results = {}
        divider = "-" * 50

        reply_hint = (
            f"To APPROVE reply: APPROVED {application_id}\n"
            f"To REJECT  reply: REJECTED {application_id} <reason>\n"
            f"Urdu: Manzoor {application_id}  /  Mastrad {application_id}"
        )

        email_body = (
            f"Assalam o Alaikum DFO Sahib,\n\n"
            f"A new forest permit application has been submitted.\n\n"
            f"{divider}\n"
            f"Application ID  : {application_id}\n"
            f"Applicant Name  : {applicant_name}\n"
            f"Permit Type     : {permit_type}\n"
            f"Submitted At    : {datetime.now().strftime('%d %b %Y, %I:%M %p')}\n"
            f"Citizen Contact : {applicant_contact or 'Not provided'}\n"
            f"{divider}\n\n"
            f"PDF application form is attached.\n\n"
            f"HOW TO RESPOND (no portal login needed):\n{reply_hint}\n\n"
            f"The system will automatically notify the citizen after your reply.\n\n"
            f"JazakAllah Khair,\nKP Forest Department"
        )

        wa_body = (
            f"*[KP Forest Dept] New Permit Application*\n\n"
            f"*ID:* `{application_id}`\n"
            f"*Applicant:* {applicant_name}\n"
            f"*Type:* {permit_type}\n"
            f"*Date:* {datetime.now().strftime('%d %b %Y %I:%M %p')}\n\n"
            f"PDF sent to your email ({dfo_email}).\n\n"
            f"*Reply to approve:*\nAPPROVED {application_id}\n"
            f"*Reply to reject:*\nREJECTED {application_id} <reason>"
        )

        results['email'] = await self._send_email(
            to_email=dfo_email,
            subject=f"[Permit Application] {permit_type} -- {application_id}",
            body=email_body,
            attachment=pdf_bytes,
            attachment_name=f"application_{application_id}.pdf",
        )
        results['whatsapp'] = await self._send_whatsapp(dfo_phone, wa_body)

        if results['whatsapp'].get('status') not in ('sent', 'demo'):
            results['sms'] = await self._send_sms(
                dfo_phone,
                f"KP Forest Dept: New permit {application_id} from {applicant_name}. "
                f"Check email. Reply: APPROVED/REJECTED {application_id}",
            )
        else:
            results['sms'] = {'status': 'skipped', 'reason': 'WhatsApp delivered'}

        results['slack'] = await self._send_slack(
            f":scroll: *New Permit Application*\n"
            f">*ID:* `{application_id}`\n"
            f">*Applicant:* {applicant_name}\n"
            f">*Type:* {permit_type}\n"
            f">*Time:* {datetime.now().strftime('%d %b %Y %I:%M %p')}\n"
            f">Reply: `APPROVED {application_id}` or `REJECTED {application_id} <reason>`"
        )

        logger.info(f"Dispatch complete for {application_id}: "
                    f"{ {ch: v.get('status') for ch, v in results.items()} }")
        return results

    # ============================================================
    # DFO REPLY HANDLER
    # ============================================================

    def check_dfo_replies(self) -> List[Dict]:
        processed = []
        try:
            mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
            mail.login(SMTP_SENDER, SMTP_PASSWORD)
            mail.select("inbox")
            _, msg_ids = mail.search(None, f'(UNSEEN FROM "{DFO_EMAIL}")')

            for msg_id in msg_ids[0].split():
                _, msg_data = mail.fetch(msg_id, '(RFC822)')
                msg      = email_lib.message_from_bytes(msg_data[0][1])
                body     = self._extract_email_body(msg)
                decision = self._parse_dfo_reply(body)

                if decision:
                    self._apply_decision(decision)
                    processed.append(decision)
                    mail.store(msg_id, '+FLAGS', '\\Seen')
                    logger.info(f"DFO reply processed: {decision}")

            mail.logout()
        except imaplib.IMAP4.error as e:
            logger.warning(f"IMAP polling failed (check credentials): {e}")
        except Exception as e:
            logger.error(f"Reply check error: {e}")
        return processed

    def parse_whatsapp_webhook(self, webhook_payload: Dict) -> Optional[Dict]:
        try:
            sender = webhook_payload.get('From', '')
            body   = webhook_payload.get('Body', '')
            if DFO_PHONE.replace('+', '') not in sender.replace('+', ''):
                logger.info(f"WhatsApp from unknown sender {sender} -- ignored")
                return None
            decision = self._parse_dfo_reply(body)
            if decision:
                self._apply_decision(decision)
                logger.info(f"WhatsApp decision processed: {decision}")
            return decision
        except Exception as e:
            logger.error(f"WhatsApp webhook error: {e}")
            return None

    # ============================================================
    # PRIVATE -- REPLY PARSING
    # ============================================================

    def _parse_dfo_reply(self, text: str) -> Optional[Dict]:
        if not text:
            return None
        pattern = re.compile(
            r'(approved?|rejected?|denied?|منظور|منظوری|مسترد)'
            r'\s+(APP-\d{14,})'
            r'(.*)?',
            re.IGNORECASE | re.DOTALL,
        )
        match = pattern.search(text.strip())
        if not match:
            return None
        keyword = match.group(1).lower()
        app_id  = match.group(2).strip()
        reason  = (match.group(3) or '').strip()
        status  = 'approved' if any(k in keyword for k in ['approv', 'منظور']) else 'rejected'
        return {
            'application_id': app_id,
            'status':         status,
            'reason':         reason or ('Approved by DFO' if status == 'approved' else 'Rejected by DFO'),
            'decided_at':     datetime.now().isoformat(),
        }

    def _apply_decision(self, decision: Dict):
        app_id = decision['application_id']
        status = decision['status']
        reason = decision['reason']

        try:
            from data.permit_store import permit_store
            permit_store.update_status(app_id, status, reason)
            logger.info(f"permit_store: {app_id} -> {status}")
        except Exception as e:
            logger.error(f"permit_store update failed for {app_id}: {e}")

        try:
            from data.permit_store import permit_store
            app_data = permit_store.get_application(app_id)
            if not app_data:
                return

            name        = app_data.get('applicant_name', 'Applicant')
            phone       = app_data.get('applicant_contact', '')
            permit_type = app_data.get('permit_type', 'Permit')

            if status == 'approved':
                citizen_msg = (
                    f"Assalam o Alaikum {name},\n\n"
                    f"Your {permit_type} application has been APPROVED by the DFO.\n\n"
                    f"Application ID: {app_id}\n"
                    f"Approved on: {datetime.now().strftime('%d %b %Y')}\n\n"
                    f"Please visit the DFO office with your original CNIC to collect your permit.\n\n"
                    f"KP Forest Department"
                )
            else:
                citizen_msg = (
                    f"Assalam o Alaikum {name},\n\n"
                    f"Your {permit_type} application ({app_id}) has been REJECTED.\n\n"
                    f"Reason: {reason}\n\n"
                    f"Please address the above and reapply, or contact the DFO office.\n\n"
                    f"KP Forest Department"
                )

            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import nest_asyncio
                    nest_asyncio.apply()
                    loop.run_until_complete(self._send_whatsapp(phone, citizen_msg))
                else:
                    asyncio.run(self._send_whatsapp(phone, citizen_msg))
            except Exception:
                asyncio.run(self._send_whatsapp(phone, citizen_msg))

            emoji = 'white_check_mark' if status == 'approved' else 'x'
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.run_until_complete(self._send_slack(
                        f":{emoji}: *DFO Decision* | `{app_id}` -> *{status.upper()}*\n"
                        f">Applicant: {name} | Reason: {reason}"
                    ))
                else:
                    asyncio.run(self._send_slack(
                        f":{emoji}: *DFO Decision* | `{app_id}` -> *{status.upper()}*\n"
                        f">Applicant: {name} | Reason: {reason}"
                    ))
            except Exception as slack_e:
                logger.warning(f"Slack ops alert failed: {slack_e}")

        except Exception as e:
            logger.error(f"Citizen notification failed for {app_id}: {e}")

    # ============================================================
    # PRIVATE -- PDF FORM BUILDERS
    # ============================================================

    def _build_dept_header(self, pdf: FormPDF, config: Dict, app_id: str, app_date: datetime):
        """
        Formal department header -- no system/AI branding.
        Looks like a standard govt. printed form.
        """
        # Outer border around the header block
        pdf.set_draw_color(0, 0, 0)
        pdf.set_line_width(0.8)

        # Department name
        pdf.set_times("B", 14)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 8, "KHYBER PAKHTUNKHWA FOREST DEPARTMENT", ln=True, align="C")

        # Thin rule
        pdf.set_line_width(0.3)
        pdf.draw_line()
        pdf.ln(1)

        # Form title
        pdf.set_times("B", 12)
        pdf.cell(0, 7, pdf_safe(config['name'].upper() + " -- APPLICATION FORM"), ln=True, align="C")

        # Ordinance reference
        pdf.set_times("I", 9)
        pdf.set_text_color(60, 60, 60)
        pdf.cell(0, 5,
                 pdf_safe(f"(Under {config['section']})   |   Divisional Forest Office, Hazara Division"),
                 ln=True, align="C")
        pdf.set_text_color(0, 0, 0)

        # Double rule under header
        pdf.set_line_width(0.8)
        pdf.draw_line(1)
        pdf.set_line_width(0.3)
        pdf.draw_line(2.5)
        pdf.ln(5)

    def _build_receipt_strip(self, pdf: FormPDF, app_id: str, app_date: datetime):
        """Three-column strip: Application No | Date | Received By."""
        pdf.set_times("B", 8)
        third = (pdf.w - pdf.l_margin - pdf.r_margin) / 3
        x0 = pdf.l_margin

        labels = [
            ("Application No.", app_id),
            ("Date of Submission", app_date.strftime("%d / %m / %Y")),
            ("Received By (Office Use)", ""),
        ]
        for i, (lbl, val) in enumerate(labels):
            pdf.set_x(x0 + i * third)
            pdf.set_times("B", 8)
            pdf.cell(pdf.get_string_width(lbl + ": ") + 1, 6, lbl + ": ", ln=False)
            pdf.set_times("", 10)
            pdf.cell(
                third - pdf.get_string_width(lbl + ": ") - 1,
                6, "  " + pdf_safe(val),
                border="B", ln=(i == 2)
            )

        pdf.set_line_width(0.5)
        pdf.draw_line(1)
        pdf.set_line_width(0.3)
        pdf.ln(3)

    def _build_applicant_section(self, pdf: FormPDF, applicant: Dict):
        pdf.section_bar("Part A -- Applicant Information")

        pdf.two_fields(
            "Full Name (Block Letters)", applicant.get('name', ''),
            "Father / Husband Name",    applicant.get('father_name', '')
        )
        pdf.three_fields([
            ("CNIC Number",    applicant.get('cnic', '')),
            ("Mobile Number",  applicant.get('contact', '')),
            ("Email Address",  applicant.get('email', '')),
        ])
        pdf.multi_line_field("Postal Address", applicant.get('address', ''), lines=2)

    def _build_location_section(self, pdf: FormPDF, location: Dict):
        pdf.section_bar("Part B -- Location of Forest Area")

        pdf.three_fields([
            ("District",       location.get('district', '')),
            ("Tehsil",         location.get('tehsil', '')),
            ("Village / Mouza", location.get('village', '')),
        ])
        pdf.three_fields([
            ("Khasra No.",     location.get('khasra_number', '')),
            ("Forest Type",    location.get('forest_type', '')),
            ("Area (Acres)",   str(location.get('land_area_acres', ''))),
        ])
        pdf.multi_line_field(
            "GPS Coordinates / Landmark Description",
            location.get('coordinates', ''),
            lines=1
        )

    def _build_permit_details_section(
        self, pdf: FormPDF, permit_type: PermitType, config: Dict, request: Dict
    ):
        pdf.section_bar("Part B2 -- Permit Details")

        pdf.two_fields(
            "Permit Type", config['name'],
            "Duration Requested (Days)", str(request.get('duration_days', config['validity_days']))
        )

        if permit_type == PermitType.TRANSIT:
            pdf.two_fields(
                "Origin (Loading Point)", request.get('origin_district', ''),
                "Destination",           request.get('dest_district', '')
            )
            pdf.multi_line_field("Proposed Route", request.get('proposed_route', ''), lines=1)

        elif permit_type == PermitType.GRAZING:
            pdf.two_fields(
                "Preferred Season", request.get('preferred_season', ''),
                "Water Source",     request.get('water_sources', '')
            )

    def _build_resource_section(
        self, pdf: FormPDF, permit_type: PermitType, config: Dict, request: Dict
    ):
        pdf.section_bar("Part C -- Resource Specifications")

        if permit_type == PermitType.TIMBER_EXTRACTION:
            species = request.get('tree_species', [])
            pdf.two_fields(
                "Tree Species",    ', '.join(species) if species else '',
                "Number of Trees", str(request.get('number_of_trees', ''))
            )
            girth = request.get('girth_sizes_cm', [])
            pdf.two_fields(
                "Girth Size (cm)",     ', '.join(map(str, girth)) if girth else '',
                "Volume (Cubic Ft)",   str(request.get('volume_cubic_ft', ''))
            )
            pdf.multi_line_field("Purpose of Extraction", request.get('purpose', ''), lines=1)

        elif permit_type == PermitType.FIREWOOD_COLLECTION:
            pdf.three_fields([
                ("Quantity (kg)",        str(request.get('quantity_kg', ''))),
                ("Family Members",       str(request.get('family_members', ''))),
                ("Current Fuel Source",  request.get('fuel_source', '')),
            ])
            pdf.multi_line_field("Purpose", request.get('purpose', 'Domestic use only'), lines=1)

        elif permit_type == PermitType.GRAZING:
            lv = request.get('livestock', {})
            pdf.two_fields(
                "Total Animals",       str(request.get('total_animals', '')),
                "Grazing Area (Acres)", str(request.get('grazing_area_acres', ''))
            )
            pdf.three_fields([
                ("Goats",   str(lv.get('goats', ''))),
                ("Sheep",   str(lv.get('sheep', ''))),
                ("Cows",    str(lv.get('cows', ''))),
            ])
            pdf.two_fields(
                "Buffalo",          str(lv.get('buffalo', '')),
                "Animals per Day",  str(request.get('animals_per_day', ''))
            )

        elif permit_type == PermitType.NTFP:
            ntfp = request.get('ntfp_types', [])
            pdf.two_fields(
                "NTFP Types",          ', '.join(ntfp) if ntfp else '',
                "Quantity (kg/ltr)",   str(request.get('quantity_kg', ''))
            )
            pdf.two_fields(
                "Collection Method",   request.get('collection_method', ''),
                "End Use",             request.get('end_use', '')
            )

        elif permit_type == PermitType.TRANSIT:
            pdf.two_fields(
                "Vehicle Type",       request.get('vehicle_type', ''),
                "Registration No.",   request.get('vehicle_reg', '')
            )
            pdf.two_fields(
                "Driver Name",        request.get('driver_name', ''),
                "Driver CNIC",        request.get('driver_cnic', '')
            )
            species = request.get('tree_species', [])
            pdf.two_fields(
                "Timber Volume (cft)", str(request.get('volume_cubic_ft', '')),
                "Species",             ', '.join(species) if species else ''
            )

        elif permit_type == PermitType.NWFDMA:
            pdf.multi_line_field("Project Type",       request.get('project_type', ''), lines=1)
            pdf.multi_line_field("Impact Assessment",  request.get('impact_assessment', ''), lines=1)
            pdf.multi_line_field("Mitigation Plan",    request.get('mitigation_plan', ''), lines=1)

    def _build_justification_section(self, pdf: FormPDF, justification: str):
        pdf.section_bar("Part D -- Justification / Reason for Request")
        pdf.multi_line_field(
            "Detailed Explanation",
            pdf_safe(sanitize_text(justification)) if justification else '',
            lines=3
        )

    def _build_documents_section(self, pdf: FormPDF, supporting_docs: Optional[List[str]]):
        pdf.section_bar("Part E -- Supporting Documents Enclosed (tick all that apply)")
        docs = [
            "Copy of CNIC",
            "Land Ownership / Tenancy Proof",
            "Site Map / Sketch",
            "Previous Permit (if any)",
        ]
        if supporting_docs:
            docs += [f"Attached: {d}" for d in supporting_docs]
        else:
            docs.append("Other: ___________________________")
        pdf.checkbox_row(docs[:4])
        if len(docs) > 4:
            pdf.checkbox_row(docs[4:])

    def _build_declaration_section(
        self, pdf: FormPDF, app_date: datetime, expiry_date: datetime, applicant: Dict
    ):
        pdf.section_bar("Part F -- Declaration by Applicant")

        declaration = (
            "I hereby solemnly declare that all information provided above is true and correct "
            "to the best of my knowledge. I understand that providing false or misleading "
            "information is an offence under Section 33 of the KP Forest Ordinance 2002 and may "
            "result in rejection of this application and/or legal proceedings against me. "
            "I agree to: (1) comply with all conditions attached to the permit if granted; "
            "(2) allow site inspection by authorised Forest Department officers at any time; "
            "(3) use the permit solely for the stated purpose; and (4) not transfer this "
            "application to any other person. I further understand that this application confers "
            "no rights until a formal permit is officially issued and signed by the competent authority."
        )

        # Declaration text box
        x0   = pdf.l_margin
        page_w = pdf.w - pdf.l_margin - pdf.r_margin
        y0   = pdf.get_y()
        pdf.set_times("", 9)
        pdf.set_fill_color(250, 250, 250)
        pdf.multi_cell(page_w, 5, pdf_safe(declaration), border=1, fill=True)
        pdf.ln(3)

        # Signature boxes side by side
        half = page_w / 2 - 3
        x_left  = pdf.l_margin
        x_right = pdf.l_margin + half + 6

        sig_h = 18

        pdf.set_draw_color(0, 0, 0)
        pdf.set_line_width(0.3)

        # Left box: signature
        pdf.rect(x_left, pdf.get_y(), half, sig_h)
        pdf.set_x(x_left + 1)
        pdf.set_times("B", 8)
        pdf.cell(half - 2, 5, "Applicant Signature / Thumb Impression", ln=True)
        pdf.set_x(x_left + 1)
        pdf.set_times("", 8)
        pdf.cell(half - 2, 5, "", ln=True)
        pdf.set_x(x_left + 1)
        pdf.cell(half - 2, 5,
                 pdf_safe(f"Name: {applicant.get('name', '______________________________')}"),
                 ln=True)

        # Right box: date & place
        y_sig = pdf.get_y() - sig_h
        pdf.rect(x_right, y_sig, half, sig_h)
        pdf.set_xy(x_right + 1, y_sig)
        pdf.set_times("B", 8)
        pdf.cell(half - 2, 5, pdf_safe(f"Date: {app_date.strftime('%d / %m / %Y')}"), ln=True)
        pdf.set_x(x_right + 1)
        pdf.cell(half - 2, 5, "", ln=True)
        pdf.set_x(x_right + 1)
        pdf.set_times("", 8)
        pdf.cell(half - 2, 5,
                 pdf_safe(f"Expected Validity: {expiry_date.strftime('%d/%m/%Y')}"),
                 ln=True)

        pdf.ln(3)

    def _build_official_use_section(self, pdf: FormPDF, app_id: str):
        """
        Official use box at bottom -- for DFO/Range Officer decision.
        Has stamp box, signature lines and decision area.
        """
        # Check if we need a new page
        if pdf.get_y() > 240:
            pdf.add_page()

        pdf.section_bar("For Official Use Only -- DFO / Range Officer")

        page_w = pdf.w - pdf.l_margin - pdf.r_margin
        half   = page_w / 2 - 3
        x_left  = pdf.l_margin
        x_right = pdf.l_margin + half + 6

        # Row 1: receipt date | file no.
        pdf.two_fields("Date of Receipt", "", "File / Register No.", "")

        # Row 2: site inspection remarks
        pdf.multi_line_field("Site Inspection Remarks", "", lines=2)

        # Decision row
        pdf.set_times("B", 8)
        pdf.cell(pdf.get_string_width("Decision: ") + 1, 6, "Decision: ", ln=False)
        pdf.set_times("", 9)
        for decision_opt in ["APPROVED", "REJECTED", "DEFERRED"]:
            box_x = pdf.get_x()
            box_y = pdf.get_y() + 1.5
            pdf.rect(box_x, box_y, 3.5, 3.5)
            pdf.set_x(box_x + 4.5)
            pdf.cell(pdf.get_string_width(decision_opt) + 5, 6, " " + decision_opt, ln=False)
        pdf.ln(7)

        # Reason if rejected
        pdf.multi_line_field("Reason (if Rejected / Deferred)", "", lines=2)

        # Signature row
        sig_h  = 20
        y_sig  = pdf.get_y()
        third3 = page_w / 3

        for i, (title, sub) in enumerate([
            ("Range Officer Signature", "Name & Designation:"),
            ("DFO Signature", "Name & Designation:"),
            ("Official Stamp", ""),
        ]):
            bx = pdf.l_margin + i * third3
            pdf.rect(bx, y_sig, third3 - 2, sig_h)
            pdf.set_xy(bx + 1, y_sig + 1)
            pdf.set_times("B", 8)
            pdf.cell(third3 - 4, 5, title, ln=True)
            if sub:
                pdf.set_x(bx + 1)
                pdf.set_times("", 7)
                pdf.cell(third3 - 4, 4, sub, ln=True)
                pdf.set_x(bx + 1)
                pdf.cell(third3 - 4, 5, "Date: ___ / ___ / ______", ln=True)

        pdf.ln(sig_h + 2)

        # Footer rule and note
        pdf.set_line_width(0.8)
        pdf.draw_line()
        pdf.set_line_width(0.3)
        pdf.ln(2)
        pdf.set_times("I", 8)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(
            0, 5,
            "Submit this form to the Divisional Forest Officer of your district.  |  "
            "Keep a copy for your records.  |  This form is free of cost.",
            ln=True, align="C"
        )
        pdf.set_text_color(0, 0, 0)

    # ============================================================
    # PRIVATE -- COMMUNICATION HELPERS (FIXED)
    # ============================================================

    async def _send_email(self, to_email, subject, body,
                          attachment=None, attachment_name=None) -> Dict:
        """
        Sends via Gmail on port 465 (SMTP_SSL).
        Falls back to EMAIL_RELAY_URL (Google Apps Script) if SMTP fails.

        .env keys used:
            SMTP_SERVER   = smtp.gmail.com
            SMTP_PORT     = 465
            SMTP_SENDER   = alihinaali2022@gmail.com
            SMTP_PASSWORD = vynyrajtgrrgmqgi          (Gmail App Password)
            EMAIL_RELAY_URL = https://script.google.com/...  (fallback)
        """
        from email.mime.text      import MIMEText
        from email.mime.multipart import MIMEMultipart
        from email.mime.base      import MIMEBase
        from email                import encoders as enc

        # ── guard: missing / placeholder password ──────────────
        if not SMTP_PASSWORD or len(SMTP_PASSWORD) != 16:
            err = (
                f"SMTP_PASSWORD looks wrong ({len(SMTP_PASSWORD)} chars, need 16). "
                "Trying EMAIL_RELAY_URL fallback."
            )
            logger.warning(err)
            return await self._send_via_relay(to_email, subject, body)

        # ── build message ──────────────────────────────────────
        msg = MIMEMultipart()
        msg['From']    = SMTP_SENDER
        msg['To']      = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        if attachment and attachment_name:
            part = MIMEBase('application', 'pdf')
            part.set_payload(attachment)
            enc.encode_base64(part)
            part.add_header('Content-Disposition',
                            f'attachment; filename="{attachment_name}"')
            msg.attach(part)

        # ── send via SMTP_SSL (port 465) ───────────────────────
        try:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT,
                                   context=context, timeout=30) as server:
                server.login(SMTP_SENDER, SMTP_PASSWORD)
                server.send_message(msg)

            logger.info(f"Email sent to {to_email} via SMTP_SSL:{SMTP_PORT}")
            return {'status': 'sent', 'to': to_email, 'method': 'smtp_ssl'}

        except smtplib.SMTPAuthenticationError:
            err = (
                "Gmail authentication failed. "
                "Make sure SMTP_PASSWORD is a Gmail App Password "
                "(not your regular password). "
                "Generate one at: https://myaccount.google.com/apppasswords"
            )
            logger.error(err)

        except smtplib.SMTPRecipientsRefused as e:
            err = f"Recipient refused: {to_email} -- {e}"
            logger.error(err)
            return {'status': 'failed', 'error': err}

        except (smtplib.SMTPException, TimeoutError, OSError) as e:
            err = f"SMTP error: {type(e).__name__}: {e}"
            logger.error(err)

        # ── fallback: Google Apps Script relay ─────────────────
        logger.info("Attempting EMAIL_RELAY_URL fallback...")
        return await self._send_via_relay(to_email, subject, body)

    async def _send_via_relay(self, to_email: str, subject: str, body: str) -> Dict:
        """
        POST to EMAIL_RELAY_URL (Google Apps Script).
        Note: does not support PDF attachments -- text-only fallback.
        """
        if not EMAIL_RELAY_URL:
            return {
                'status': 'failed',
                'error': 'SMTP failed and EMAIL_RELAY_URL is not set -- no fallback available.',
            }
        try:
            resp = requests.post(
                EMAIL_RELAY_URL,
                json={'to': to_email, 'subject': subject, 'body': body},
                timeout=20,
            )
            if resp.status_code == 200:
                logger.info(f"Email sent via relay to {to_email}")
                return {'status': 'sent', 'to': to_email, 'method': 'relay'}
            else:
                err = f"Relay returned HTTP {resp.status_code}: {resp.text[:200]}"
                logger.error(err)
                return {'status': 'failed', 'error': err}
        except Exception as e:
            err = f"Relay failed: {type(e).__name__}: {e}"
            logger.error(err)
            return {'status': 'failed', 'error': err}

    async def _send_whatsapp(self, to_phone: str, message: str) -> Dict:
        """
        .env keys used:
            TWILIO_ACCOUNT_SID
            TWILIO_AUTH_TOKEN
            TWILIO_WA_FROM     (default: whatsapp:+14155238886)
            DFO_PHONE_NUMBER
        """
        if not TWILIO_SID or not TWILIO_TOKEN:
            logger.info(
                f"[DEMO WhatsApp] Twilio not configured. "
                f"Would send to {to_phone}: {message[:80]}..."
            )
            return {
                'status': 'demo',
                'to': to_phone,
                'reason': 'TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN not set',
            }

        if not to_phone:
            logger.warning("WhatsApp skipped: DFO_PHONE_NUMBER not set in .env")
            return {'status': 'skipped', 'reason': 'DFO_PHONE_NUMBER not set'}

        try:
            from twilio.rest import Client
            client = Client(TWILIO_SID, TWILIO_TOKEN)
            wa_to  = (f"whatsapp:{to_phone}"
                      if not to_phone.startswith('whatsapp:') else to_phone)
            result = client.messages.create(
                body=message, from_=TWILIO_WA_FROM, to=wa_to
            )
            logger.info(f"WhatsApp sent to {to_phone} (SID: {result.sid})")
            return {'status': 'sent', 'to': to_phone, 'sid': result.sid}

        except Exception as e:
            logger.warning(f"WhatsApp failed ({to_phone}): {type(e).__name__}: {e}")
            return {'status': 'failed', 'error': str(e)}

    async def _send_sms(self, to_phone: str, message: str) -> Dict:
        """
        .env keys used:
            TWILIO_ACCOUNT_SID
            TWILIO_AUTH_TOKEN
            TWILIO_SMS_FROM    (a purchased Twilio number, e.g. +1XXXXXXXXXX)
            DFO_PHONE_NUMBER
        """
        missing = [v for v, k in [
            ("TWILIO_ACCOUNT_SID", TWILIO_SID),
            ("TWILIO_AUTH_TOKEN",  TWILIO_TOKEN),
            ("TWILIO_SMS_FROM",    TWILIO_SMS_FROM),
        ] if not k]

        if missing:
            logger.info(
                f"[DEMO SMS] Missing: {', '.join(missing)}. "
                f"Would send to {to_phone}: {message[:80]}..."
            )
            return {
                'status': 'demo',
                'to': to_phone,
                'reason': f"Missing env vars: {', '.join(missing)}",
            }

        if not to_phone:
            logger.warning("SMS skipped: DFO_PHONE_NUMBER not set in .env")
            return {'status': 'skipped', 'reason': 'DFO_PHONE_NUMBER not set'}

        try:
            from twilio.rest import Client
            client = Client(TWILIO_SID, TWILIO_TOKEN)
            result = client.messages.create(
                body=message, from_=TWILIO_SMS_FROM, to=to_phone
            )
            logger.info(f"SMS sent to {to_phone} (SID: {result.sid})")
            return {'status': 'sent', 'to': to_phone, 'sid': result.sid}

        except Exception as e:
            logger.warning(f"SMS failed ({to_phone}): {type(e).__name__}: {e}")
            return {'status': 'failed', 'error': str(e)}

    async def _send_slack(self, message: str) -> Dict:
        """
        Uses SLACK_BOT_TOKEN + SLACK_CHANNEL_ID from .env directly.
        Falls back to SLACK_WEBHOOK_URL or internal SlackNotifier if token missing.
        """
        if SLACK_BOT_TOKEN and SLACK_CHANNEL:
            try:
                resp = requests.post(
                    "https://slack.com/api/chat.postMessage",
                    headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
                    json={"channel": SLACK_CHANNEL, "text": message},
                    timeout=10,
                )
                data = resp.json()
                if data.get("ok"):
                    logger.info(f"Slack message sent to {SLACK_CHANNEL}")
                    return {'status': 'sent', 'channel': SLACK_CHANNEL}
                else:
                    err = data.get("error", "unknown slack error")
                    logger.warning(f"Slack API error: {err}")
                    return {'status': 'failed', 'error': err}
            except Exception as e:
                logger.warning(f"Slack failed: {type(e).__name__}: {e}")
                return {'status': 'failed', 'error': str(e)}

        # fallback to webhook or internal notifier
        if SLACK_WEBHOOK:
            try:
                resp = requests.post(SLACK_WEBHOOK,
                                     json={"text": message}, timeout=10)
                resp.raise_for_status()
                return {'status': 'sent', 'method': 'webhook'}
            except Exception as e:
                logger.warning(f"Slack webhook failed: {e}")
                return {'status': 'failed', 'error': str(e)}

        try:
            from tools.communication.slack_notifier import SlackNotifier
            res = await SlackNotifier().execute({"message": message})
            return {'status': res.get('status', 'unknown'), 'method': 'notifier'}
        except Exception:
            logger.info(f"[DEMO SLACK] {message[:80]}...")
            return {'status': 'demo'}

    @staticmethod
    def _extract_email_body(msg) -> str:
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    try:
                        body += part.get_payload(decode=True).decode('utf-8', errors='replace')
                    except Exception:
                        pass
        else:
            try:
                body = msg.get_payload(decode=True).decode('utf-8', errors='replace')
            except Exception:
                pass
        return body


# ============================================================
# MODULE-LEVEL CONVENIENCE WRAPPERS
# ============================================================

async def generate_timber_application(application_data: Dict, app_id: str) -> bytes:
    return await PermitApplicationGenerator().generate_application(
        PermitType.TIMBER_EXTRACTION, application_data, app_id)

async def generate_firewood_application(application_data: Dict, app_id: str) -> bytes:
    return await PermitApplicationGenerator().generate_application(
        PermitType.FIREWOOD_COLLECTION, application_data, app_id)

async def generate_grazing_application(application_data: Dict, app_id: str) -> bytes:
    return await PermitApplicationGenerator().generate_application(
        PermitType.GRAZING, application_data, app_id)

async def generate_ntfp_application(application_data: Dict, app_id: str) -> bytes:
    return await PermitApplicationGenerator().generate_application(
        PermitType.NTFP, application_data, app_id)

async def generate_transit_application(application_data: Dict, app_id: str) -> bytes:
    return await PermitApplicationGenerator().generate_application(
        PermitType.TRANSIT, application_data, app_id)

async def generate_nwfdma_application(application_data: Dict, app_id: str) -> bytes:
    return await PermitApplicationGenerator().generate_application(
        PermitType.NWFDMA, application_data, app_id)