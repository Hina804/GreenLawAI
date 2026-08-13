import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

class FeeCalculator:
    """
    Calculates permit application and extraction fees based on official KPK Forest Department schedules.
    """
    SPECIES_VALUE_MAP = {
        "Deodar": 5000,
        "Blue Pine": 3000,
        "Chir Pine": 2000,
        "Spruce": 2500,
        "Fir": 2500,
        "Oak": 1500,
        "Maple": 1200,
        "Walnut": 4000,
        "Kail": 2800,
        "Partal": 1800,
        "Phulai": 800,
        "Kikar": 700,
        "Shisham": 3500,
        "Poplar": 600,
        "Eucalyptus": 500,
        "General": 1000
    }
    
    PERMIT_TYPE_FEES = {
        "Timber Extraction": {"base": 5000, "processing": 1000, "inspection": 2000, "env": 1000},
        "Firewood Collection": {"base": 1000, "processing": 500, "inspection": 0, "env": 500},
        "Transit Permit": {"base": 2000, "processing": 500, "inspection": 0, "env": 500},
        "Grazing": {"base": 2000, "processing": 500, "inspection": 1000, "env": 500},
        "Non-Timber Forest Produce": {"base": 1500, "processing": 500, "inspection": 1000, "env": 500}
    }
    
    @classmethod
    def calculate(cls, request: Dict, environmental_metrics: Dict) -> Dict:
        """
        Calculate total permit cost dynamically based on permit type and collection metrics.
        """
        permit_type = request.get('permit_type', 'Timber Extraction')
        fee_config = cls.PERMIT_TYPE_FEES.get(permit_type, cls.PERMIT_TYPE_FEES["Timber Extraction"])
        
        base_permit = fee_config["base"]
        base_processing = fee_config["processing"]
        inspection_fee = fee_config["inspection"]
        base_env = fee_config["env"]
        
        # Calculate extraction / per-unit surcharge
        surcharge = 0.0
        if permit_type == "Timber Extraction":
            tree_count = int(request.get('number_of_trees', 0))
            species_list = request.get('tree_species', ['General'])
            main_species = species_list[0] if species_list else "General"
            unit_price = cls.SPECIES_VALUE_MAP.get(main_species, cls.SPECIES_VALUE_MAP["General"])
            surcharge = unit_price * tree_count
        elif permit_type == "Firewood Collection":
            quantity_kg = float(request.get('quantity_requested_kg', 0))
            surcharge = quantity_kg * 0.50  # Rs. 0.50 per kg royalty
        elif permit_type == "Grazing":
            total_animals = int(request.get('total_animals', 0))
            surcharge = total_animals * 100  # Rs. 100 per animal grazing fee
        elif permit_type == "Transit Permit":
            # Transit permit includes a Route Permit Fee Rs. 500
            surcharge = 500.0
        
        # Carbon risk surcharge
        carbon_risk = float(environmental_metrics.get('annual_sequestration_loss', 0))
        env_fee = base_env + (carbon_risk * 500)
        
        total = base_permit + base_processing + inspection_fee + surcharge + env_fee
        
        return {
            "total_fee_rs": round(total, 2),
            "breakdown": {
                "base_permit": base_permit,
                "base_processing": base_processing,
                "inspection_fee": inspection_fee,
                "extraction_surcharge": round(surcharge, 2),
                "environmental_surcharge": round(env_fee, 2)
            },
            "currency": "PKR"
        }
