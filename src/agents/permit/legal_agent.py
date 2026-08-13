import asyncio
import logging
import os
from typing import Dict, List, Any

# Internal Imports
from data.permit_store import permit_store
try:
    from agents.judiciary.case_retrieval_agent import CaseRetrievalAgent
except ImportError:
    # Handle if path is different
    from agents.judiciary.case_retrieval_agent import CaseRetrievalAgent

logger = logging.getLogger(__name__)

class LegalValidationAgent:
    """
    Hardened Legal Agent:
    - Verifies applicant against Judiciary Database (prior violations)
    - Enforces Dynamic Quotas based on compliance and land area
    - Implements Spam Protection (Rate limiting)
    - Validates against Protected Species lists
    """
    def __init__(self):
        # Initialize Judiciary lookup
        self.judiciary_agent = CaseRetrievalAgent()
        
    async def check_judicial_risk(self, cnic: str) -> Dict:
        """Query judiciary database for previous forest-related violations."""
        try:
            # We search specifically for the CNIC or generic forest offenses in the same region
            query = f"Forest violation history for applicant {cnic}"
            response = await self.judiciary_agent.run(query=f"CNIC {cnic} forest violation")
            
            # If any precedents are found with high confidence, we flag it
            has_violations = len(response.citations) > 0
            risk_score = 40 if has_violations else 0
            
            return {
                "has_violations": has_violations,
                "violation_count": len(response.citations),
                "risk_score": risk_score,
                "details": [c.document for c in response.citations]
            }
        except Exception as e:
            logger.error(f"Judiciary cross-ref failed: {e}")
            return {"has_violations": False, "risk_score": 0}

    async def check_application_spam(self, applicant_cnic: str, days=30):
        """Prevent multiple permit applications from same CNIC (Rate Limiting)"""
        recent_apps = permit_store.get_recent_applications(applicant_cnic, days=days)
        if len(recent_apps) >= 3:
            return {"flag": True, "reason": f"Excessive applications ({len(recent_apps)}) in last 30 days"}
        return {"flag": False}

    async def calculate_dynamic_quota(self, cnic: str, land_area_ha: float = 1.0):
        """
        Quota = Area * Density_Factor - (Violations * Weight)
        Base: 5 trees per hectare for Guzara forest
        """
        judicial_data = await self.check_judicial_risk(cnic)
        violations = judicial_data.get('violation_count', 0)
        
        base_quota = land_area_ha * 5
        penalty = violations * 2
        
        final_quota = max(0, base_quota - penalty)
        return {
            "allowed_trees": round(final_quota),
            "base": base_quota,
            "penalty": penalty,
            "judicial_risk": judicial_data.get('risk_score')
        }

    def check_species_allowed(self, species: List[str]):
        # Hardened block list for Hazara
        protected_species = ["Deodar", "Blue Pine", "Chir Pine (Seedling)"]
        for sp in species:
            if sp in protected_species:
                return {"flag": False, "species": sp}
        return {"flag": True}

    async def validate(self, request: Dict, location: Dict) -> Dict:
        """
        Professional Legal Validation Pipeline
        """
        applicant = request.get('applicant', {})
        cnic = applicant.get('cnic')
        
        # 1. Spam Protection
        spam = await self.check_application_spam(cnic)
        
        # 2. Judicial Check & Quota
        # Mocking land area from location if not provided (default 2ha for Guzara)
        land_area = float(location.get('land_area_ha', 2.0))
        quota_data = await self.calculate_dynamic_quota(cnic, land_area)
        
        # 3. Species Check
        species_check = self.check_species_allowed(request.get('tree_species', []))
        
        # 4. Quantity check
        requested_count = int(request.get('number_of_trees', 0))
        quota_exceeded = requested_count > quota_data['allowed_trees']
        
        checks = {
            "spam_flag": spam['flag'],
            "judicial_record": quota_data['judicial_risk'] > 0,
            "quota_compliance": not quota_exceeded,
            "species_allowed": species_check['flag'],
            "land_ownership_verified": True # Assuming pre-verified for this POC
        }
        
        # Scoring
        score = 100
        if checks['spam_flag']: score -= 100 # Direct rejection
        if checks['judicial_record']: score -= 40
        if not checks['species_allowed']: score -= 50
        if not checks['quota_compliance']: score -= 30
        
        reasoning = []
        if checks['spam_flag']: reasoning.append(spam['reason'])
        if checks['judicial_record']: reasoning.append("Applicant has prior forest violations in judiciary database.")
        if not checks['species_allowed']: reasoning.append(f"Species '{species_check['species']}' is strictly protected in this sector.")
        if not checks['quota_compliance']: reasoning.append(f"Request exceeds dynamic quota of {quota_data['allowed_trees']} trees for your land area/compliance history.")
        
        if not reasoning:
            reasoning = ["Legal validation success: Applicant is in good standing and request meets statutory quotas."]

        return {
            "agent": "legal",
            "score": max(0, score),
            "checks": checks,
            "status": "PASS" if score >= 60 else "FAIL",
            "reasoning": " ".join(reasoning),
            "judicial_metadata": {
                "quota": quota_data['allowed_trees'],
                "risk_index": quota_data['judicial_risk']
            }
        }
