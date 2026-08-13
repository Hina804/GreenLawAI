import asyncio
import uuid
import logging
from typing import Dict, List
from datetime import datetime

# Internal Agents
from .geo_agent import GeoValidationAgent
from .climate_agent import ClimateValidationAgent
from .legal_agent import LegalValidationAgent
from .permit_generator import PermitGeneratorAgent
from .fee_calculator import FeeCalculator

# Data & Persistence
from data.permit_store import permit_store
from data.blockchain_ledger import blockchain_ledger

logger = logging.getLogger(__name__)

class PermitDecisionEngine:
    """
    Autonomous Permit Decision Engine.
    Fuses Geo, Climate, and Legal intelligence into a final binding decision.
    Handles persistence and blockchain auditing.
    """
    def __init__(self):
        self.geo_agent = GeoValidationAgent()
        self.climate_agent = ClimateValidationAgent()
        self.legal_agent = LegalValidationAgent()
        self.permit_generator = PermitGeneratorAgent()
        
    def parse_coordinates(self, coords_input):
        if not coords_input:
            return {}
        if isinstance(coords_input, dict):
            return coords_input
        try:
            # Handle "34.12, 73.45" string format
            parts = coords_input.replace(" ", "").split(",")
            if len(parts) == 2:
                return {"lat": float(parts[0]), "lon": float(parts[1])}
        except:
            pass
        return {}

    async def evaluate(self, request: Dict) -> Dict:
        """
        Full Autonomous Pipeline:
        1. Multi-Agent Validation
        2. Weighted Scoring & Decision
        3. Fee Calculation
        4. Permit Storage & Blockchain Auditing
        5. Document Generation
        """
        # Step 1: Pre-process
        coordinates = self.parse_coordinates(request.get('location', {}).get('coordinates'))
        location_data = request.get('location', {})
        req_details = request.get('request', {})
        
        # Step 2: Parallel Multi-Agent Intelligence
        logger.info(f"Initiating autonomous evaluation for: {request.get('applicant', {}).get('cnic')}")
        
        geo_task = self.geo_agent.validate(coordinates, location_data)
        climate_task = self.climate_agent.validate(coordinates, req_details)
        legal_task = self.legal_agent.validate(request, location_data)
        
        geo_res, climate_res, legal_res = await asyncio.gather(geo_task, climate_task, legal_task)
        
        # Step 3: Weighted Decision Fusion
        weights = {"geo": 0.30, "climate": 0.35, "legal": 0.35}
        total_score = (
            geo_res['score'] * weights['geo'] +
            climate_res['score'] * weights['climate'] +
            legal_res['score'] * weights['legal']
        )
        
        # Final Status Determination
        status = "rejected"
        if total_score >= 80 and geo_res['status'] == 'PASS' and legal_res['status'] == 'PASS':
            status = "approved"
        elif total_score >= 60 and legal_res['status'] == 'PASS':
            status = "conditional"
        
        # Step 4: Financial & Technical Metrics
        fees = FeeCalculator.calculate(req_details, climate_res.get('environmental_metrics', {}))
        
        # Step 5: Persistence & Trust
        permit_id = None
        permit_pdf = None
        ledger_hash = "N/A"
        
        # Prepare decision packet
        decision_packet = {
            "status": status,
            "confidence": round(total_score, 1),
            "fees": fees,
            "reasoning": {
                "geo": geo_res['reasoning'],
                "climate": climate_res['reasoning'],
                "legal": legal_res['reasoning']
            },
            "validation_details": {
                "geo": geo_res,
                "climate": climate_res,
                "legal": legal_res
            }
        }
        
        if status in ["approved", "conditional"]:
            permit_id = f"PRMT-{uuid.uuid4().hex[:8].upper()}"
            
            # Record to Blockchain first (Audit requirement)
            ledger_hash = blockchain_ledger.record_permit(
                permit_id=permit_id,
                applicant_cnic=request.get('applicant', {}).get('cnic'),
                decision_score=total_score
            )
            
            # Generate Document
            permit_pdf = await self.permit_generator.generate_permit(
                request=request,
                permit_id=permit_id,
                status=status,
                conditions=self._extract_conditions(geo_res, climate_res, legal_res),
                ledger_hash=ledger_hash,
                fees=fees
            )
            
            # Final data to store
            full_record = {
                **request,
                **decision_packet,
                "permit_id": permit_id,
                "ledger_hash": ledger_hash,
                "verified": True
            }
            permit_store.add_permit(full_record)
        
        return {
            **decision_packet,
            "permit_id": permit_id,
            "permit_pdf": permit_pdf,
            "ledger_hash": ledger_hash
        }

    def _extract_conditions(self, geo, climate, legal) -> List[str]:
        conditions = []
        if climate['score'] < 90:
            conditions.append("Operations halted if NASA FIRMS detects fires within 10km.")
        if geo['checks'].get('forest_classification') == 'Reserved':
            conditions.append("Died back trees only; green felling strictly prohibited.")
        if legal['judicial_metadata'].get('risk_index', 0) > 0:
            conditions.append("Weekly field inspection by local forest guard mandatory.")
        return conditions
