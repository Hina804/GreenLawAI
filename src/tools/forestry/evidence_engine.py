from datetime import datetime
from typing import Dict, Any, List
import json
import os

from core.penalty_calculator import PenaltyCalculator

class EvidenceEngine:
    """
    Generates professional, "Police-Ready" evidence packages for forest crimes.
    Packages detections into a structured format for official dispatch.
    """
    
    @staticmethod
    def create_package(
        location: str,
        coordinates: Dict[str, float],
        detection_type: str,
        source: str,
        image_path: str = None,
        loss_estimate: float = 0.0
    ) -> Dict[str, Any]:
        """Creates a structured evidence package."""
        
        # Calculate legal estimates
        species = "Deodar" if "swat" in location.lower() or "kaghan" in location.lower() else "Mixed Coniferous"
        penalty_info = PenaltyCalculator.analyze_query(f"illegal logging of {species} in {location}")
        
        # Estimate trees based on loss area (Avg 100 trees per hectare)
        estimated_trees = int(loss_estimate * 100) if loss_estimate > 0 else 1
        total_fine = penalty_info['base_penalty'] * estimated_trees
        
        package = {
            "incident_id": f"GL-EV-{datetime.now().strftime('%Y%m%d-%H%M')}",
            "timestamp": datetime.now().isoformat(),
            "location": {
                "name": location,
                "lat": coordinates.get("lat"),
                "lon": coordinates.get("lon")
            },
            "forensics": {
                "detection_type": detection_type,
                "source": source,
                "loss_area_ha": loss_estimate,
                "estimated_trees": estimated_trees,
                "evidence_image": image_path
            },
            "legal_assessment": {
                "primary_species": species,
                "base_penalty_per_tree": penalty_info['base_penalty'],
                "estimated_total_fine": total_fine,
                "legal_statute": "KPK Forest Ordinance / Forest Act 1927"
            },
            "dispatch_status": "READY_FOR_OFFICIAL_REVIEW"
        }
        
        return package

    @staticmethod
    def format_for_officer(package: Dict[str, Any]) -> str:
        """Formats the evidence package into a professional brief for Rangers/Police."""
        
        brief = (
            f"🚨 **OFFICIAL EVIDENCE REPORT: {package['incident_id']}**\n\n"
            f"**1. LOCATION SUMMARY**\n"
            f"• Target Area: {package['location']['name']}\n"
            f"• GPS: {package['location']['lat']}, {package['location']['lon']}\n\n"
            f"**2. DETECTION DATA**\n"
            f"• Method: {package['forensics']['detection_type']}\n"
            f"• Source: {package['forensics']['source']}\n"
            f"• Scale: {package['forensics']['loss_area_ha']} hectares affected\n\n"
            f"**3. LEGAL IMPACT**\n"
            f"• Est. Damage: {package['forensics']['estimated_trees']} trees ({package['legal_assessment']['primary_species']})\n"
            f"• Est. Fines: Rs. {package['legal_assessment']['estimated_total_fine']:,}\n\n"
            f"**ACTION REQUIRED**: Immediate ground verification and arrest of trespassers at the provided coordinates."
        )
        return brief
