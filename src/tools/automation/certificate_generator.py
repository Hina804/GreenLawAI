import logging
import qrcode
import os
from datetime import datetime
from typing import Dict, Any, Optional
from tools.base_tool import BaseTool

logger = logging.getLogger(__name__)

class CertificateGenerator(BaseTool):
    """
    Generates compliance certificates with embedded QR codes for verification.
    """
    def __init__(self):
        super().__init__(
            name="certificate_generator",
            description="Generates a compliance certificate in text/markdown format with a QR code link."
        )
        self.output_dir = "e:/GL_AI/data/certificates"
        os.makedirs(self.output_dir, exist_ok=True)

    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parameters:
        - stakeholder: Name of the individual/org
        - compliance_type: e.g., 'Reforestation Verify', 'Legal clearance'
        - evidence_hash: Hash of the evidence from blockchain
        """
        stakeholder = parameters.get("stakeholder", "Unknown")
        c_type = parameters.get("compliance_type", "General Compliance")
        e_hash = parameters.get("evidence_hash", "N/A")
        cert_id = f"CERT-{datetime.now().strftime('%Y%m%d')}-{os.getpid()}"
        
        # Generate a dummy verification URL
        verify_url = f"https://greenlaw.ai/verify/{cert_id}"
        
        # Generate QR Code
        qr_path = os.path.join(self.output_dir, f"{cert_id}_qr.png")
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(verify_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(qr_path)

        # Generate Certificate Content
        cert_content = f"""
# GREENLAW AI COMPLIANCE CERTIFICATE
**Certificate ID:** {cert_id}
**Stakeholder:** {stakeholder}
**Compliance Category:** {c_type}
**Verification Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Blockchain Evidence Hash:** {e_hash}

---
Verified via GreenLawAI Autonomous Agentic System.
        """
        
        cert_path = os.path.join(self.output_dir, f"{cert_id}.md")
        with open(cert_path, 'w') as f:
            f.write(cert_content)

        return {
            "status": "success",
            "certificate_id": cert_id,
            "certificate_path": cert_path,
            "qr_code_path": qr_path,
            "verification_url": verify_url
        }
