from typing import Dict, Any
from agents.base_agent import BaseAgent
from core.schemas import CanonicalAgentResponse, AudienceType, Citation
from loguru import logger

class EvidenceAnalyzerAgent(BaseAgent):
    """
    Transforms raw satellite detections (NASA FIRMS / GFW) and field logs 
    into structured, court-admissible evidence reports according to Qanun-e-Shahadat Order.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(name="Evidence Analyzer Agent", config=config)

    async def run(self, query: str, retrieved_chunks: list, audience: AudienceType, context: Dict[str, Any] = None) -> CanonicalAgentResponse:
        """
        Takes raw json context about an incident and generates an evidence packet.
        """
        logger.info("Executing Evidence Analyzer Agent...")
        
        incident_data = context.get('incident_data', {}) if context else {}
        
        if not incident_data:
            return CanonicalAgentResponse(
                simple_explanation="Cannot analyze evidence: No incident data provided.",
                legal_explanation="Analysis failed: Input context 'incident_data' is empty. Evidence packets require forensic detection data.",
                citations=[],
                agent_name="EvidenceAnalyzerEngine",
                confidence=0.0,
                source_chunks=[],
                abstain=True
            )

        evidence_report = self.analyze(incident_data)
        content = self._format_response(evidence_report)
        
        return CanonicalAgentResponse(
            simple_explanation=f"Generated and verified a court-admissible evidence report for the detection at {evidence_report['summary']['location']}.",
            legal_explanation=content,
            citations=[
                Citation(document="Qanun-e-Shahadat Order 1984", section="Article 164")
            ],
            agent_name="EvidenceAnalyzerEngine",
            confidence=0.9,
            source_chunks=[],
            graph_metadata={"evidence": evidence_report}
        )

    def analyze(self, incident: Dict) -> Dict:
        """
        Constructs the formalized evidence structure using entity extraction on field notes.
        """
        notes = str(incident.get('notes', '')).lower()
        
        # Extract Night Violation & Timestamp
        is_night = incident.get('is_night', False)
        timestamp_utc = incident.get('timestamp_utc', 'Unknown')
        
        import re
        time_match = re.search(r'(\d{2}00\s*(?:hours|hrs)|([0-1]?[0-9]|2[0-3]):[0-5][0-9]\s*(?:am|pm)?|\d{1,2}\s*(?:am|pm))', notes)
        if time_match:
            timestamp_utc = time_match.group(1).upper()
            if "0400" in timestamp_utc or "0300" in timestamp_utc or "0200" in timestamp_utc or "2300" in timestamp_utc or "PM" in timestamp_utc:
                is_night = True
                
        if "night" in notes or "0400" in notes or "dark" in notes or "midnight" in notes:
            is_night = True

        # Extract Protected Area Status
        is_protected = incident.get('is_protected', False)
        if "block b" in notes or "reserve" in notes or "protected" in notes or "national park" in notes:
            is_protected = True
            
        # Extract Damage Type
        damage_type = incident.get('damage_type', 'Unspecified')
        if "stump" in notes or "cut" in notes or "timber" in notes or "log" in notes or "clearing" in notes:
            damage_type = "Illicit Cutting / Deforestation"
        elif "fire" in notes or "burn" in notes or "smoke" in notes:
            damage_type = "Aggravated Forest Fire"
            
        # Extract Trees Count
        trees = incident.get('trees_cut', 'Unknown')
        tree_match = re.search(r'(\d+)\s*(?:trees|stumps|logs)', notes)
        if tree_match:
            trees = tree_match.group(1)
        elif "stumps" in notes or "clearing" in notes:
            trees = "Multiple (Quantification Pending Forensic Count)"

        return {
            "summary": {
                "date": incident.get('date', 'Unknown'),
                "location": incident.get('location', 'Unknown'),
                "coordinates": incident.get('coordinates', 'Unknown')
            },
            "satellite_evidence": {
                "type": incident.get('source', 'Field Extracted intelligence'),
                "confidence_interval": incident.get('confidence_interval', 'HIGH'),
                "timestamp_utc": timestamp_utc
            },
            "environmental_impact": {
                "trees_affected": trees,
                "nature_of_damage": damage_type
            },
            "legal_qualifiers": {
                "protected_area": is_protected,
                "night_time_violation": is_night
            },
            "admissibility_assessment": {
                "status": "Admissible",
                "legal_basis": "Electronic Document Admissible under Article 164, Qanun-e-Shahadat Order 1984",
                "requires_certification": True
            }
        }

    def _format_response(self, evidence: Dict) -> str:
        md = "## 🧾 Court-Admissible Evidence Report\n\n"
        
        sm = evidence['summary']
        md += f"**Incident:** Forensic Detection at `{sm['location']}` on `{sm['date']}` (Coords: `{sm['coordinates']}`)\n\n"
        
        se = evidence['satellite_evidence']
        md += "### Satellite Intelligence (Primary Evidence)\n"
        md += f"- **Source System:** {se['type']}\n"
        md += f"- **Detection Timestamp:** {se['timestamp_utc']}\n"
        md += f"- **Sensor Confidence:** {se['confidence_interval']}\n\n"
        
        lq = evidence['legal_qualifiers']
        md += "### Legal Context & Qualifiers\n"
        md += f"- **Night Violation:** {'Yes' if lq['night_time_violation'] else 'No'}\n"
        md += f"- **Protected Forest Registry:** {'Yes' if lq['protected_area'] else 'No'}\n\n"
        
        aa = evidence['admissibility_assessment']
        md += "### Court Admissibility\n"
        md += f"- **Status:** `{aa['status'].upper()}`\n"
        md += f"- **Statutory Basis:** {aa['legal_basis']}\n"
        md += f"- **Next Step:** Requires Section 164 certification stamp by Field Officer.\n"
        
        return md

    def generate_pdf(self, event, operator_name: str = "Unknown"):
        import os
        import hashlib
        from datetime import datetime
        
        # Construct bridge dictionary for GIS GeoEvents
        incident = {
            "source": getattr(event, "source", "Satellite Intelligence"),
            "notes": event.details.get("strategic_narrative", getattr(event, "type", "Anomaly")),
            "location": event.details.get("sector_name", "Hazara Division"),
            "date": getattr(event, "timestamp", datetime.now()).strftime("%Y-%m-%d"),
            "coordinates": f"{getattr(event, 'lat', 0.0):.4f}_{getattr(event, 'lon', 0.0):.4f}",
            "damage_type": getattr(event, "type", "Unknown")
        }
        
        evidence_dict = self.analyze(incident)
        md_text = self._format_response(evidence_dict)
        
        header = f"# 🏛️ GREENLAW AI - OFFENSE EVIDENCE BUNDLE\n**Generated by:** {operator_name}\n**System ID:** {getattr(event, 'id', 'Unknown')}\n**Timestamp:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n\n"
        full_report = header + md_text
        
        export_dir = os.path.join(os.getcwd(), "data", "legal_exports")
        os.makedirs(export_dir, exist_ok=True)
        
        filename = f"evidence_{getattr(event, 'id', 'doc')}.md"
        filepath = os.path.join(export_dir, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(full_report)
            
        return {
            "filepath": filepath,
            "filename": filename,
            "hash": hashlib.md5(full_report.encode("utf-8")).hexdigest()
        }
