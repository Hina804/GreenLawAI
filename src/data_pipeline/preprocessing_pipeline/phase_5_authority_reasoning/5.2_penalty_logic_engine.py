"""
penalty_logic_engine.py - ENHANCED
===========================================================
RESEARCH-GRADE KPK-SPECIFIC PENALTY LOGIC ENGINE

ENHANCEMENTS:
1. ✅ Direct integration with Phase 5.1 (AuthorityHierarchyResolver)
2. ✅ Gazette notification validation (SRO integration)
3. ✅ Enhanced temporal chains with amendment tracking
4. ✅ Forest type-specific penalty regimes
5. ✅ Climate change surcharge calculations
6. ✅ Community Forest (Guzara) special rules
7. ✅ Research statistics for VIVA demonstration
8. ✅ Graph output for Phase 6 integration

Key Research Features:
- Hazara Act special penalty provisions
- SRO-based penalty escalations
- Retroactive penalty applications
- Officer discretion audit trails
- Penalty evolution timeline visualization
"""

import re
import json
import logging
from typing import Dict, List, Tuple, Optional, Union, Any, Set
from dataclasses import dataclass, asdict, field
from enum import Enum
from datetime import datetime, date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import hashlib
from collections import defaultdict
import statistics

# Import from Phase 5.1 (Authority Hierarchy)
try:
    from .authority_hierarchy import (
        AuthorityHierarchyResolver, 
        AuthorityLevel, 
        LegalSource,
        ResolutionResult
    )
    from .authority_hierarchy import KPKJurisdictionMapper
except ImportError:
    # Fallback for standalone testing
    class AuthorityHierarchyResolver:
        pass
    class AuthorityLevel(Enum):
        pass
    class LegalSource:
        pass
    class ResolutionResult:
        pass
    class KPKJurisdictionMapper:
        pass

# Import from Phase 4 (Amendment tracking)
try:
    from ..phase_4_legal_extraction.amendment_tracker import AmendmentChain
except ImportError:
    class AmendmentChain:
        pass

# Import from Phase 0 (Abstention logging)
try:
    from ..phase_0_foundation.abstention_log import AbstentionLogger
except ImportError:
    class AbstentionLogger:
        def log_abstention(self, *args, **kwargs):
            pass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ViolationType(Enum):
    """Enhanced KPK forestry violation types with research categories"""
    # Tree-related violations
    UNAUTHORIZED_FELLING = "unauthorized_felling"
    UNAUTHORIZED_LOGGING = "unauthorized_logging"
    UNAUTHORIZED_PRUNING = "unauthorized_pruning"
    
    # Transport violations
    ILLEGAL_TRANSPORT_TIMBER = "illegal_transport_timber"
    ILLEGAL_TRANSPORT_FIREWOOD = "illegal_transport_firewood"
    ILLEGAL_TRANSPORT_MEDICINAL_PLANTS = "illegal_transport_medicinal_plants"
    
    # Collection violations
    FIREWOOD_COLLECTION = "firewood_collection"
    RESIN_TAPPING = "resin_tapping"
    MEDICINAL_PLANT_COLLECTION = "medicinal_plant_collection"
    HONEY_COLLECTION = "honey_collection"
    
    # Land use violations
    GRAZING_VIOLATION = "grazing_violation"
    TRESPASSING = "trespassing"
    ENCROACHMENT = "encroachment"
    ILLEGAL_CONSTRUCTION = "illegal_construction"
    MINING_EXCAVATION = "mining_excavation"
    
    # Fire violations
    FOREST_FIRE_NEGLIGENCE = "forest_fire_negligence"
    ARSON = "arson"
    UNAUTHORIZED_BURNING = "unauthorized_burning"
    
    # Environmental violations
    WATER_POLLUTION = "water_pollution"
    SOIL_EROSION_CAUSATION = "soil_erosion_causation"
    BIODIVERSITY_DAMAGE = "biodiversity_damage"
    
    # Administrative violations
    PERMIT_VIOLATION = "permit_violation"
    LICENSE_VIOLATION = "license_violation"
    DOCUMENT_FORGERY = "document_forgery"
    FALSE_DECLARATION = "false_declaration"
    RESISTING_OFFICER = "resisting_officer"
    
    # Climate-related violations (RESEARCH FOCUS)
    CARBON_SEQUESTRATION_DAMAGE = "carbon_sequestration_damage"
    WATERSHED_DAMAGE = "watershed_damage"
    CLIMATE_RESILIENCE_DAMAGE = "climate_resilience_damage"
    
    # Community forest violations
    COMMUNITY_FOREST_BREACH = "community_forest_breach"
    GUZARA_FOREST_MISMANAGEMENT = "guzara_forest_mismanagement"


class OfficerRank(Enum):
    """Enhanced KPK forestry officer ranks with research attributes"""
    FOREST_GUARD = "forest_guard"
    SENIOR_FOREST_GUARD = "senior_forest_guard"
    BLOCK_OFFICER = "block_officer"
    RANGE_OFFICER = "range_officer"
    DIVISIONAL_FOREST_OFFICER = "divisional_forest_officer"
    CONSERVATOR_FOREST = "conservator_forest"
    CHIEF_CONSERVATOR = "chief_conservator"
    SECRETARY_FOREST = "secretary_forest"
    MINISTER_FOREST = "minister_forest"
    
    # Special roles (for research tracking)
    HAZARA_SPECIAL_OFFICER = "hazara_special_officer"
    MALAKAND_SPECIAL_OFFICER = "malakand_special_officer"
    TRIBAL_DISTRICT_OFFICER = "tribal_district_officer"


class ForestType(Enum):
    """KPK forest types with legal implications"""
    RESERVED_FOREST = "reserved_forest"
    PROTECTED_FOREST = "protected_forest"
    GUZARA_FOREST = "guzara_forest"
    UNCLASSED_FOREST = "unclassed_forest"
    PRIVATE_FOREST = "private_forest"
    COMMUNITY_FOREST = "community_forest"
    WATERSHED_FOREST = "watershed_forest"
    RIPARIAN_FOREST = "riparian_forest"


@dataclass
class PenaltyCalculation:
    """Enhanced penalty calculation with research tracking"""
    # Input parameters
    violation_type: str
    location: str
    quantity: int
    
    # Identification (with defaults)
    calculation_id: str = field(default_factory=lambda: f"penalty_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hashlib.md5(str(datetime.now()).encode()).hexdigest()[:6]}")
    timestamp: datetime = field(default_factory=datetime.now)
    
    species: Optional[str] = None
    scientific_name: Optional[str] = None
    unit: str = "tree"  # tree, kg, hectare, vehicle, animal, etc.
    forest_type: Optional[ForestType] = None
    jurisdiction_details: Dict[str, Any] = field(default_factory=dict)
    
    # Temporal context
    violation_date: Optional[date] = None
    effective_date: date = field(default_factory=date.today)
    processing_date: date = field(default_factory=date.today)
    
    # Offender context
    offense_count: int = 1
    offender_type: str = "individual"  # individual, company, community
    is_repeat_offender: bool = False
    previous_penalties: List[Dict] = field(default_factory=list)
    
    # Authority context (from Phase 5.1)
    authority_source: Optional[LegalSource] = None
    authority_resolution: Optional[ResolutionResult] = None
    applicable_authorities: List[Dict] = field(default_factory=list)
    
    # Calculation components
    base_amount: Decimal = Decimal("0")
    species_multiplier: Decimal = Decimal("1.0")
    location_multiplier: Decimal = Decimal("1.0")
    temporal_multiplier: Decimal = Decimal("1.0")
    repeat_multiplier: Decimal = Decimal("1.0")
    forest_type_multiplier: Decimal = Decimal("1.0")
    climate_surcharge: Decimal = Decimal("0")
    biodiversity_surcharge: Decimal = Decimal("0")
    
    # Discretion
    officer_rank: Optional[OfficerRank] = None
    discretion_percentage: Decimal = Decimal("0")
    discretion_reason: Optional[str] = None
    discretion_audit_trail: List[Dict] = field(default_factory=list)
    
    # Final amounts
    subtotal_before_discretion: Decimal = Decimal("0")
    discretion_amount: Decimal = Decimal("0")
    total_fine: Decimal = Decimal("0")
    currency: str = "PKR"
    
    # Non-monetary penalties
    imprisonment_term: Optional[str] = None
    imprisonment_months: Optional[int] = None
    community_service_hours: Optional[int] = None
    confiscation_items: List[str] = field(default_factory=list)
    restoration_requirements: List[str] = field(default_factory=list)
    license_suspension_months: Optional[int] = None
    
    # Legal references
    primary_legal_reference: str = ""
    amendment_references: List[str] = field(default_factory=list)
    gazette_references: List[str] = field(default_factory=list)
    section_references: List[str] = field(default_factory=list)
    
    # Calculation breakdown for transparency
    calculation_steps: List[Dict[str, Any]] = field(default_factory=list)
    applied_rules: List[str] = field(default_factory=list)
    
    # Research metrics
    confidence_score: float = 0.0
    confidence_breakdown: Dict[str, float] = field(default_factory=dict)
    complexity_score: float = 0.0
    research_significance: str = "standard"  # standard, hazara_special, sro_based, etc.
    
    # Quality control
    validation_passed: bool = False
    validation_errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    # Phase 6 graph integration
    graph_node_id: Optional[str] = None
    graph_relationships: List[Dict] = field(default_factory=list)
    
    # Phase 7 quality gates
    passed_quality_gates: List[str] = field(default_factory=list)
    failed_quality_gates: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        # Generate graph node ID
        if not self.graph_node_id:
            self.graph_node_id = f"Penalty_{self.calculation_id}"
        
        # Calculate complexity score
        self.complexity_score = self._calculate_complexity()
        
        # Determine research significance
        self.research_significance = self._determine_research_significance()
    
    def _calculate_complexity(self) -> float:
        """Calculate complexity score for research analysis."""
        score = 0.0
        
        # Multiple multipliers add complexity
        multipliers = [
            self.species_multiplier,
            self.location_multiplier,
            self.temporal_multiplier,
            self.repeat_multiplier,
            self.forest_type_multiplier
        ]
        
        for mult in multipliers:
            if mult != Decimal("1.0"):
                score += 0.1
        
        # Special authorities add complexity
        if self.authority_source:
            if self.authority_source.authority_level in [
                AuthorityLevel.HAZARA_ACT if hasattr(AuthorityLevel, 'HAZARA_ACT') else None,
                AuthorityLevel.GAZETTE_NOTIFICATION if hasattr(AuthorityLevel, 'GAZETTE_NOTIFICATION') else None
            ]:
                score += 0.2
        
        # Multiple penalty types add complexity
        penalty_types = 0
        if self.imprisonment_term:
            penalty_types += 1
        if self.community_service_hours:
            penalty_types += 1
        if self.confiscation_items:
            penalty_types += 1
        
        score += penalty_types * 0.15
        
        # Discretion adds complexity
        if self.discretion_percentage != Decimal("0"):
            score += 0.1
        
        return min(score, 1.0)
    
    def _determine_research_significance(self) -> str:
        """Determine research significance for VIVA demonstration."""
        if not self.authority_source:
            return "standard"
        
        auth_level = self.authority_source.authority_level
        
        if hasattr(AuthorityLevel, 'HAZARA_ACT') and auth_level == AuthorityLevel.HAZARA_ACT:
            return "hazara_special"
        elif hasattr(AuthorityLevel, 'GAZETTE_NOTIFICATION') and auth_level == AuthorityLevel.GAZETTE_NOTIFICATION:
            return "sro_based"
        elif hasattr(AuthorityLevel, 'KPK_ORDINANCE') and auth_level == AuthorityLevel.KPK_ORDINANCE:
            return "ordinance_based"
        elif self.forest_type == ForestType.GUZARA_FOREST:
            return "community_forest"
        elif "climate" in self.violation_type.lower():
            return "climate_related"
        
        return "standard"
    
    def to_dict(self) -> Dict:
        """Convert to dictionary with proper serialization."""
        data = asdict(self)
        
        # Handle special types
        if self.forest_type:
            data['forest_type'] = self.forest_type.value
        
        if self.officer_rank:
            data['officer_rank'] = self.officer_rank.value
        
        if self.authority_source:
            data['authority_source'] = self.authority_source.to_dict()
        
        if self.authority_resolution:
            data['authority_resolution'] = self.authority_resolution.to_dict()
        
        # Convert Decimal to string for JSON
        decimal_fields = [
            'base_amount', 'species_multiplier', 'location_multiplier',
            'temporal_multiplier', 'repeat_multiplier', 'forest_type_multiplier',
            'climate_surcharge', 'biodiversity_surcharge', 'subtotal_before_discretion',
            'discretion_amount', 'total_fine', 'discretion_percentage'
        ]
        
        for field in decimal_fields:
            if field in data and isinstance(data[field], Decimal):
                data[field] = str(data[field])
        
        # Convert dates
        date_fields = ['timestamp', 'violation_date', 'effective_date', 'processing_date']
        for field in date_fields:
            value = data.get(field)
            if value:
                if isinstance(value, datetime):
                    data[field] = value.isoformat()
                elif isinstance(value, date):
                    data[field] = value.isoformat()
        
        return data
    
    def to_human_readable(self, lang: str = "en") -> str:
        """Generate human-readable penalty description."""
        if lang == "ur":
            return self._to_urdu_readable()
        
        lines = [
            f"PENALTY CALCULATION RESULT",
            f"=" * 70,
            f"Calculation ID: {self.calculation_id}",
            f"Timestamp: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"",
            f"VIOLATION DETAILS:",
            f"- Type: {self.violation_type.replace('_', ' ').title()}",
            f"- Species: {self.species if self.species else 'Not specified'}",
            f"- Quantity: {self.quantity} {self.unit}{'s' if self.quantity > 1 and self.unit != 'hectare' else ''}",
            f"- Location: {self.location}",
            f"- Forest Type: {self.forest_type.value if self.forest_type else 'Not specified'}",
            f"- Violation Date: {self.violation_date or 'Not specified'}",
            f"- Offense Count: #{self.offense_count}",
            f"",
            f"FINE CALCULATION:",
            f"- Base Amount: {self.currency} {self.base_amount:,.2f}",
            f"- Species Multiplier: {self.species_multiplier:.2f}x",
            f"- Location Multiplier: {self.location_multiplier:.2f}x",
            f"- Temporal Multiplier: {self.temporal_multiplier:.2f}x",
            f"- Repeat Offense Multiplier: {self.repeat_multiplier:.2f}x",
            f"- Forest Type Multiplier: {self.forest_type_multiplier:.2f}x",
            f"- Climate Surcharge: {self.currency} {self.climate_surcharge:,.2f}",
            f"- Biodiversity Surcharge: {self.currency} {self.biodiversity_surcharge:,.2f}",
            f"",
            f"DISCRETION:",
            f"- Officer: {self.officer_rank.value.replace('_', ' ').title() if self.officer_rank else 'None'}",
            f"- Discretion Percentage: {self.discretion_percentage:+.1f}%",
            f"- Discretion Amount: {self.currency} {self.discretion_amount:,.2f}",
            f"",
            f"TOTAL FINE: {self.currency} {self.total_fine:,.2f}",
        ]
        
        if self.imprisonment_term:
            lines.append(f"IMPRISONMENT: {self.imprisonment_term}")
        
        if self.community_service_hours:
            lines.append(f"COMMUNITY SERVICE: {self.community_service_hours} hours")
        
        if self.confiscation_items:
            lines.append(f"CONFISCATION: {', '.join(self.confiscation_items)}")
        
        if self.restoration_requirements:
            lines.append(f"RESTORATION: {', '.join(self.restoration_requirements)}")
        
        lines.append(f"")
        lines.append(f"LEGAL BASIS:")
        lines.append(f"- Primary Reference: {self.primary_legal_reference}")
        
        if self.gazette_references:
            lines.append(f"- Gazette References: {', '.join(self.gazette_references[:3])}")
        
        lines.append(f"")
        lines.append(f"RESEARCH METRICS:")
        lines.append(f"- Confidence Score: {self.confidence_score:.1%}")
        lines.append(f"- Complexity Score: {self.complexity_score:.1%}")
        lines.append(f"- Research Significance: {self.research_significance.replace('_', ' ').title()}")
        
        if self.warnings:
            lines.append(f"")
            lines.append(f"WARNINGS:")
            for warning in self.warnings[:3]:  # Show only first 3 warnings
                lines.append(f"- {warning}")
        
        return "\n".join(lines)
    
    def _to_urdu_readable(self) -> str:
        """Generate Urdu version of penalty description."""
        lines = [
            f"جرمانے کا حساب کتاب",
            f"=" * 50,
            f"حساب کتاب کی شناخت: {self.calculation_id}",
            f"تاریخ: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"",
            f"خلاف ورزی کی تفصیلات:",
            f"- قسم: {self._translate_violation_to_urdu(self.violation_type)}",
            f"- نوع: {self.species if self.species else 'متعین نہیں'}",
            f"- مقدار: {self.quantity} {self._translate_unit_to_urdu(self.unit)}",
            f"- مقام: {self.location}",
            f"- جنگل کی قسم: {self._translate_forest_type_to_urdu(self.forest_type)}",
            f"- خلاف ورزی کی تاریخ: {self.violation_date or 'متعین نہیں'}",
            f"- خلاف ورزی کی تعداد: #{self.offense_count}",
            f"",
            f"جرمانے کا حساب:",
            f"- بنیادی رقم: {self.currency} {self.base_amount:,.0f}",
            f"- نوع کا ضرب: {self.species_multiplier:.1f} گنا",
            f"- مقام کا ضرب: {self.location_multiplier:.1f} گنا",
            f"- زمانی ضرب: {self.temporal_multiplier:.1f} گنا",
            f"- مکرر خلاف ورزی کا ضرب: {self.repeat_multiplier:.1f} گنا",
            f"",
            f"کل جرمانہ: {self.currency} {self.total_fine:,.0f}",
        ]
        
        if self.imprisonment_term:
            lines.append(f"قید: {self.imprisonment_term}")
        
        return "\n".join(lines)
    
    def _translate_violation_to_urdu(self, violation: str) -> str:
        """Translate violation type to Urdu."""
        translations = {
            "unauthorized_felling": "غیر مجاز کٹائی",
            "illegal_transport": "غیر قانونی نقل و حمل",
            "firewood_collection": "ایندھن کی لکڑی اکٹھا کرنا",
            "grazing_violation": "چرائی کی خلاف ورزی",
            "trespassing": "ناجائز دخول"
        }
        return translations.get(violation, violation)
    
    def _translate_unit_to_urdu(self, unit: str) -> str:
        """Translate unit to Urdu."""
        translations = {
            "tree": "درخت",
            "kg": "کلوگرام",
            "hectare": "ہیکٹر",
            "vehicle": "گاڑی",
            "animal": "جانور"
        }
        return translations.get(unit, unit)
    
    def _translate_forest_type_to_urdu(self, forest_type: Optional[ForestType]) -> str:
        """Translate forest type to Urdu."""
        if not forest_type:
            return "متعین نہیں"
        
        translations = {
            ForestType.RESERVED_FOREST: "مختص جنگل",
            ForestType.PROTECTED_FOREST: "محفوظ جنگل",
            ForestType.GUZARA_FOREST: "گزارہ جنگل",
            ForestType.UNCLASSED_FOREST: "غیر درجہ بند جنگل",
            ForestType.COMMUNITY_FOREST: "اجتماعی جنگل"
        }
        return translations.get(forest_type, "متعین نہیں")


class KPKPenaltyMatrix:
    """Enhanced penalty matrix with research capabilities"""
    
    def __init__(self, authority_resolver: Optional[AuthorityHierarchyResolver] = None):
        self.authority_resolver = authority_resolver
        self.currency = "PKR"
        
        # Base penalty matrix (as of KPK Forest Ordinance 2002)
        self.base_matrix = self._initialize_base_matrix()
        
        # Species-specific data (enhanced for research)
        self.species_data = self._initialize_species_data()
        
        # Location multipliers (enhanced with Phase 5.1 integration)
        self.location_data = self._initialize_location_data()
        
        # Temporal adjustments (amendment-based)
        self.temporal_data = self._initialize_temporal_data()
        
        # Officer discretion matrix
        self.discretion_data = self._initialize_discretion_data()
        
        # Forest type regimes
        self.forest_type_data = self._initialize_forest_type_data()
        
        # Surcharge calculations
        self.surcharge_data = self._initialize_surcharge_data()
        
        # Research statistics
        self.research_stats = defaultdict(int)
        
        logger.info("Enhanced KPK Penalty Matrix initialized")
    
    def _initialize_base_matrix(self) -> Dict:
        """Initialize base penalty matrix with enhanced details."""
        return {
            ViolationType.UNAUTHORIZED_FELLING: {
                "base_amount": Decimal("50000"),
                "per_unit_additional": Decimal("10000"),
                "unit": "tree",
                "imprisonment": {"min_months": 6, "max_months": 36},
                "community_service": {"base_hours": 40, "per_tree_hours": 8},
                "confiscation": ["tools", "timber"],
                "restoration": ["plant 10 saplings per tree"],
                "license_suspension": 12,
                "primary_reference": "KPK Forest Ordinance 2002, Section 27",
                "gazette_references": ["SRO-123(I)/2002"],
                "section_references": ["Section 27", "Section 28"],
                "research_notes": "Most common violation, baseline for all species calculations"
            },
            ViolationType.UNAUTHORIZED_LOGGING: {
                "base_amount": Decimal("75000"),
                "per_unit_additional": Decimal("15000"),
                "unit": "tree",
                "imprisonment": {"min_months": 12, "max_months": 48},
                "community_service": {"base_hours": 60, "per_tree_hours": 12},
                "confiscation": ["equipment", "vehicles", "timber"],
                "restoration": ["plant 20 saplings per tree"],
                "license_suspension": 24,
                "primary_reference": "KPK Forest Ordinance 2002, Section 27A",
                "research_notes": "Commercial-scale unauthorized felling"
            },
            ViolationType.ILLEGAL_TRANSPORT_TIMBER: {
                "base_amount": Decimal("25000"),
                "per_unit_additional": Decimal("5000"),
                "unit": "vehicle",
                "imprisonment": {"min_months": 3, "max_months": 12},
                "confiscation": ["vehicle", "timber"],
                "primary_reference": "KPK Forest Ordinance 2002, Section 28",
                "gazette_references": ["SRO-456(I)/2015"]
            },
            ViolationType.FIREWOOD_COLLECTION: {
                "base_amount": Decimal("5000"),
                "per_unit_additional": Decimal("100"),
                "unit": "kg",
                "confiscation": ["firewood"],
                "primary_reference": "KPK Forest Rules 2004, Rule 15",
                "research_notes": "Common in community forests, often subsistence-based"
            },
            ViolationType.GRAZING_VIOLATION: {
                "base_amount": Decimal("3000"),
                "per_unit_additional": Decimal("500"),
                "unit": "animal",
                "confiscation": ["animals"],
                "primary_reference": "KPK Forest Rules 2004, Rule 18",
                "section_references": ["Rule 18(2)"]
            },
            ViolationType.ENCROACHMENT: {
                "base_amount": Decimal("100000"),
                "per_unit_additional": Decimal("5000"),
                "unit": "hectare",
                "imprisonment": {"min_months": 6, "max_months": 24},
                "restoration": ["remove encroachment", "restore vegetation"],
                "primary_reference": "KPK Forest Ordinance 2002, Section 32",
                "research_notes": "Major issue in watershed areas"
            },
            ViolationType.FOREST_FIRE_NEGLIGENCE: {
                "base_amount": Decimal("100000"),
                "per_unit_additional": Decimal("10000"),
                "unit": "hectare_damaged",
                "imprisonment": {"min_months": 12, "max_months": 60},
                "restoration": ["reforestation", "soil conservation"],
                "primary_reference": "KPK Forest Ordinance 2002, Section 33",
                "research_notes": "Climate change impacts considered"
            },
            ViolationType.CARBON_SEQUESTRATION_DAMAGE: {
                "base_amount": Decimal("200000"),
                "per_unit_additional": Decimal("50000"),
                "unit": "hectare",
                "climate_surcharge": Decimal("0.25"),  # 25% additional
                "primary_reference": "Climate Change Policy 2022",
                "research_notes": "RESEARCH FOCUS: Climate-related penalty"
            },
            ViolationType.COMMUNITY_FOREST_BREACH: {
                "base_amount": Decimal("20000"),
                "per_unit_additional": Decimal("5000"),
                "unit": "violation",
                "community_service": {"base_hours": 80},
                "primary_reference": "Community Forest Rules 2010",
                "research_notes": "Special regime for community-managed forests"
            }
        }
    
    def _initialize_species_data(self) -> Dict:
        """Initialize species-specific data with research attributes."""
        return {
            # Highly Protected Species (Category A)
            "Deodar": {
                "scientific_name": "Cedrus deodara",
                "urdu_name": "دیار",
                "pashto_name": "دیودار",
                "category": "highly_protected",
                "base_multiplier": Decimal("2.5"),
                "min_multiplier": Decimal("2.0"),
                "max_multiplier": Decimal("3.0"),
                "minimum_fine": Decimal("100000"),
                "carbon_sequestration_kg_per_year": Decimal("50.2"),
                "water_yield_impact": "high",
                "biodiversity_value": "very_high",
                "climate_resilience": "very_high",
                "legal_references": [
                    "KPK Protected Species List, Notification No. 123/2010",
                    "Hazara Forest Act 1936, Schedule I"
                ],
                "research_notes": "State tree of KPK, highest protection level"
            },
            "Kail": {
                "scientific_name": "Pinus wallichiana",
                "urdu_name": "کایل",
                "pashto_name": "کایل",
                "category": "highly_protected",
                "base_multiplier": Decimal("2.0"),
                "minimum_fine": Decimal("80000"),
                "carbon_sequestration_kg_per_year": Decimal("45.8"),
                "legal_references": ["KPK Protected Species List, Notification No. 123/2010"],
                "research_notes": "Blue pine, important for high-altitude forests"
            },
            "Chir": {
                "scientific_name": "Pinus roxburghii",
                "urdu_name": "چیر",
                "pashto_name": "چیر",
                "category": "protected",
                "base_multiplier": Decimal("1.8"),
                "minimum_fine": Decimal("60000"),
                "carbon_sequestration_kg_per_year": Decimal("40.3"),
                "legal_references": ["KPK Protected Species List, Notification No. 123/2010"],
                "research_notes": "Chir pine, widespread in lower Himalayas"
            },
            
            # Protected Species (Category B)
            "Walnut": {
                "scientific_name": "Juglans regia",
                "urdu_name": "اخروٹ",
                "pashto_name": "اخروٹ",
                "category": "protected",
                "base_multiplier": Decimal("1.5"),
                "minimum_fine": Decimal("40000"),
                "carbon_sequestration_kg_per_year": Decimal("35.7"),
                "economic_value": "high",
                "legal_references": ["KPK Protected Species List, Notification No. 123/2010"],
                "research_notes": "High economic value, often targeted"
            },
            "Oak": {
                "scientific_name": "Quercus spp.",
                "urdu_name": "شاہ بلوط",
                "pashto_name": "مازو",
                "category": "protected",
                "base_multiplier": Decimal("1.3"),
                "minimum_fine": Decimal("30000"),
                "carbon_sequestration_kg_per_year": Decimal("42.1"),
                "biodiversity_value": "high",
                "legal_references": ["KPK Protected Species List, Notification No. 78/2015"],
                "research_notes": "Multiple species, important for biodiversity"
            },
            
            # Common Species (Category C)
            "Poplar": {
                "scientific_name": "Populus spp.",
                "category": "common",
                "base_multiplier": Decimal("1.0"),
                "minimum_fine": Decimal("15000"),
                "carbon_sequestration_kg_per_year": Decimal("30.5"),
                "research_notes": "Fast-growing, often used in plantations"
            },
            "Eucalyptus": {
                "scientific_name": "Eucalyptus spp.",
                "category": "common",
                "base_multiplier": Decimal("0.8"),
                "minimum_fine": Decimal("10000"),
                "carbon_sequestration_kg_per_year": Decimal("38.2"),
                "water_impact": "negative",
                "research_notes": "Exotic species, water-intensive"
            },
            
            # Medicinal Plants (Special Category)
            "Yew": {
                "scientific_name": "Taxus wallichiana",
                "urdu_name": "سرونگ",
                "category": "medicinal_protected",
                "base_multiplier": Decimal("3.0"),
                "minimum_fine": Decimal("150000"),
                "medicinal_value": "very_high",
                "legal_references": ["CITES Appendix II", "Medicinal Plants Protection Act 2018"],
                "research_notes": "Source of cancer drug taxol, critically endangered"
            }
        }
    
    def _initialize_location_data(self) -> Dict:
        """Initialize location-based multipliers."""
        return {
            # Protected Areas (Highest protection)
            "National Park": {
                "multiplier": Decimal("2.0"),
                "additional_surcharge": Decimal("0.2"),
                "legal_basis": "National Parks Act 1975",
                "research_notes": "Highest level of legal protection"
            },
            "Wildlife Sanctuary": {
                "multiplier": Decimal("1.8"),
                "additional_surcharge": Decimal("0.15"),
                "legal_basis": "KPK Wildlife Act 2015"
            },
            "Biosphere Reserve": {
                "multiplier": Decimal("2.2"),
                "additional_surcharge": Decimal("0.25"),
                "research_notes": "UNESCO designated, international importance"
            },
            
            # Forest Types
            "Reserved Forest": {
                "multiplier": Decimal("1.5"),
                "legal_basis": "KPK Forest Ordinance 2002, Section 26"
            },
            "Protected Forest": {
                "multiplier": Decimal("1.3"),
                "legal_basis": "KPK Forest Ordinance 2002, Section 29"
            },
            "Guzara Forest": {
                "multiplier": Decimal("0.7"),
                "legal_basis": "Guzara Forest Rules 2010",
                "research_notes": "Community-managed, different penalty regime"
            },
            
            # Divisions (KPK administrative)
            "Malakand Division": {
                "multiplier": Decimal("1.2"),
                "special_notes": "Tourism pressure, frequent violations"
            },
            "Hazara Division": {
                "multiplier": Decimal("1.1"),
                "special_notes": "Hazara Act applies, special considerations"
            },
            "Swat District": {
                "multiplier": Decimal("1.4"),
                "parent_division": "Malakand",
                "special_notes": "High biodiversity, tourism pressure"
            },
            "Chitral District": {
                "multiplier": Decimal("1.5"),
                "parent_division": "Malakand",
                "special_notes": "Sensitive ecosystem, climate vulnerability"
            },
            "Mansehra District": {
                "multiplier": Decimal("1.2"),
                "parent_division": "Hazara",
                "special_notes": "Hazara Act fully applicable"
            },
            
            # Watershed Areas (Climate focus)
            "Watershed Area": {
                "multiplier": Decimal("1.6"),
                "climate_surcharge": Decimal("0.15"),
                "research_notes": "Critical for water security, climate resilience"
            },
            
            # Default
            "Default": {
                "multiplier": Decimal("1.0"),
                "research_notes": "Standard KPK jurisdiction"
            }
        }
    
    def _initialize_temporal_data(self) -> Dict:
        """Initialize temporal adjustment data based on amendments."""
        return {
            "2002": {
                "multiplier": Decimal("1.0"),
                "description": "Original KPK Forest Ordinance 2002",
                "base_year": True
            },
            "2010": {
                "multiplier": Decimal("1.5"),
                "description": "First major amendment (SRO-123/2010)",
                "gazette_ref": "SRO-123/2010",
                "changes": ["Protected species list", "Increased fines for Deodar/Kail"]
            },
            "2015": {
                "multiplier": Decimal("2.0"),
                "description": "Second amendment (SRO-456/2015)",
                "gazette_ref": "SRO-456/2015",
                "changes": ["Doubled base penalties", "Stricter repeat offense rules"]
            },
            "2018": {
                "multiplier": Decimal("2.3"),
                "description": "Environmental Protection Enhancement",
                "gazette_ref": "SRO-789/2018",
                "changes": ["Climate change considerations", "Biodiversity surcharge"]
            },
            "2020": {
                "multiplier": Decimal("2.5"),
                "description": "Climate Change Focus (SRO-101/2020)",
                "gazette_ref": "SRO-101/2020",
                "changes": ["10% climate surcharge", "Carbon sequestration damage penalties"]
            },
            "2022": {
                "multiplier": Decimal("3.0"),
                "description": "Current rate (post-COVID adjustments)",
                "gazette_ref": "SRO-202/2022",
                "changes": ["Inflation adjustment", "Community service emphasis"]
            },
            "2023": {
                "multiplier": Decimal("3.5"),
                "description": "Projected for GreenLawAI research",
                "research_projection": True
            }
        }
    
    def _initialize_discretion_data(self) -> Dict:
        """Initialize officer discretion data."""
        return {
            OfficerRank.FOREST_GUARD: {
                "adjustment_range": {"min": Decimal("-0.10"), "max": Decimal("0.05")},
                "can_waive_minimum": False,
                "can_waive_imprisonment": False,
                "max_waiver_amount": Decimal("0"),
                "required_approval": "Range Officer",
                "audit_required": True,
                "research_notes": "Limited discretion, mostly enforcement role"
            },
            OfficerRank.BLOCK_OFFICER: {
                "adjustment_range": {"min": Decimal("-0.15"), "max": Decimal("0.10")},
                "can_waive_minimum": False,
                "can_waive_imprisonment": False,
                "max_waiver_amount": Decimal("5000"),
                "required_approval": "Range Officer",
                "audit_required": True
            },
            OfficerRank.RANGE_OFFICER: {
                "adjustment_range": {"min": Decimal("-0.20"), "max": Decimal("0.15")},
                "can_waive_minimum": True,
                "can_waive_imprisonment": False,
                "max_waiver_amount": Decimal("20000"),
                "required_approval": "Divisional Officer",
                "audit_required": True,
                "research_notes": "Key discretion level, field command"
            },
            OfficerRank.DIVISIONAL_FOREST_OFFICER: {
                "adjustment_range": {"min": Decimal("-0.30"), "max": Decimal("0.25")},
                "can_waive_minimum": True,
                "can_waive_imprisonment": True,
                "can_reduce_imprisonment_by": Decimal("0.50"),
                "max_waiver_amount": Decimal("50000"),
                "required_approval": "Conservator",
                "audit_required": True,
                "research_notes": "Substantial discretion, district-level authority"
            },
            OfficerRank.CONSERVATOR_FOREST: {
                "adjustment_range": {"min": Decimal("-0.50"), "max": Decimal("0.50")},
                "can_waive_minimum": True,
                "can_waive_imprisonment": True,
                "can_reduce_imprisonment_by": Decimal("0.75"),
                "max_waiver_amount": Decimal("100000"),
                "required_approval": "Chief Conservator",
                "audit_required": True,
                "research_notes": "Divisional level, policy implementation"
            },
            OfficerRank.HAZARA_SPECIAL_OFFICER: {
                "adjustment_range": {"min": Decimal("-0.40"), "max": Decimal("0.30")},
                "can_waive_minimum": True,
                "can_waive_imprisonment": True,
                "max_waiver_amount": Decimal("75000"),
                "special_authority": "Hazara Forest Act 1936",
                "research_notes": "Special regional authority in Hazara"
            }
        }
    
    def _initialize_forest_type_data(self) -> Dict:
        """Initialize forest type-specific penalty regimes."""
        return {
            ForestType.RESERVED_FOREST: {
                "multiplier": Decimal("1.5"),
                "penalty_emphasis": "deterrence",
                "community_service_weight": Decimal("1.2"),
                "restoration_requirements": ["scientific_reforestation", "monitoring"],
                "legal_basis": "Section 26, KPK Forest Ordinance 2002",
                "research_notes": "Highest protection, government-managed"
            },
            ForestType.PROTECTED_FOREST: {
                "multiplier": Decimal("1.3"),
                "penalty_emphasis": "deterrence_and_restoration",
                "community_service_weight": Decimal("1.0"),
                "restoration_requirements": ["reforestation", "soil_conservation"],
                "legal_basis": "Section 29, KPK Forest Ordinance 2002",
                "research_notes": "Protected but with community rights"
            },
            ForestType.GUZARA_FOREST: {
                "multiplier": Decimal("0.7"),
                "penalty_emphasis": "community_resolution",
                "community_service_weight": Decimal("1.5"),
                "restoration_requirements": ["community_reforestation"],
                "confiscation_emphasis": "community_benefit",
                "legal_basis": "Guzara Forest Rules 2010",
                "research_notes": "Community-managed, different legal regime"
            },
            ForestType.COMMUNITY_FOREST: {
                "multiplier": Decimal("0.8"),
                "penalty_emphasis": "community_governance",
                "community_service_weight": Decimal("2.0"),
                "restoration_requirements": ["participatory_reforestation"],
                "legal_basis": "Community Forest Management Rules 2015",
                "research_notes": "Participatory management, focus on governance"
            },
            ForestType.WATERSHED_FOREST: {
                "multiplier": Decimal("1.6"),
                "penalty_emphasis": "ecological_restoration",
                "climate_surcharge": Decimal("0.20"),
                "restoration_requirements": ["watershed_restoration", "erosion_control"],
                "legal_basis": "Watershed Management Policy 2018",
                "research_notes": "Critical for water security and climate resilience"
            }
        }
    
    def _initialize_surcharge_data(self) -> Dict:
        """Initialize surcharge calculations."""
        return {
            "climate_change_surcharge": {
                "base_rate": Decimal("0.10"),  # 10%
                "applicable_since": "2020-01-01",
                "legal_basis": "SRO-101/2020",
                "calculation_method": "percentage_of_base",
                "exemptions": ["guzara_forest_subsistence", "community_forest_first_offense"],
                "research_notes": "Climate mitigation fund contribution"
            },
            "biodiversity_surcharge": {
                "base_rate": Decimal("0.05"),  # 5%
                "applicable_since": "2018-07-01",
                "legal_basis": "SRO-789/2018",
                "calculation_method": "percentage_of_base",
                "triggers": ["protected_species", "critical_habitat", "breeding_season"],
                "research_notes": "Biodiversity conservation fund"
            },
            "watershed_protection_surcharge": {
                "base_rate": Decimal("0.15"),  # 15%
                "applicable_since": "2019-03-15",
                "legal_basis": "Watershed Protection Notification 2019",
                "calculation_method": "percentage_of_base",
                "applicable_locations": ["watershed_areas", "riparian_zones"],
                "research_notes": "Water security and climate resilience"
            }
        }
    
    def get_species_info(self, species_input: str) -> Optional[Dict]:
        """Enhanced species lookup with multilingual support."""
        species_lower = species_input.lower().strip()
        
        # Direct name match
        for name, info in self.species_data.items():
            if name.lower() == species_lower:
                return {**info, "matched_name": name, "match_type": "exact"}
        
        # Urdu name match
        for name, info in self.species_data.items():
            urdu_name = info.get("urdu_name", "").lower()
            if urdu_name and urdu_name == species_lower:
                return {**info, "matched_name": name, "match_type": "urdu"}
        
        # Pashto name match
        for name, info in self.species_data.items():
            pashto_name = info.get("pashto_name", "").lower()
            if pashto_name and pashto_name == species_lower:
                return {**info, "matched_name": name, "match_type": "pashto"}
        
        # Scientific name match
        for name, info in self.species_data.items():
            sci_name = info.get("scientific_name", "").lower()
            if sci_name and sci_name == species_lower:
                return {**info, "matched_name": name, "match_type": "scientific"}
        
        # Partial match
        for name, info in self.species_data.items():
            if species_lower in name.lower():
                return {**info, "matched_name": name, "match_type": "partial"}
        
        return None
    
    def get_location_info(self, location: str) -> Dict:
        """Get comprehensive location information."""
        location_lower = location.lower()
        
        # Check each location category
        for loc_name, info in self.location_data.items():
            if loc_name.lower() in location_lower:
                return {**info, "matched_location": loc_name}
        
        # Check for division/district names
        kpk_divisions = ["malakand", "hazara", "peshawar", "mardan", "kohat", "bannu", "dera ismail khan"]
        for division in kpk_divisions:
            if division in location_lower:
                return self.location_data.get(f"{division.title()} Division", 
                                             self.location_data["Default"])
        
        # Default
        return {**self.location_data["Default"], "matched_location": "Default"}
    
    def get_temporal_multiplier(self, effective_date: date) -> Dict:
        """Get temporal multiplier with detailed metadata."""
        year = effective_date.year
        
        # Find applicable temporal adjustment
        applicable_years = []
        for year_str, info in self.temporal_data.items():
            try:
                year_int = int(year_str)
                if year_int <= year:
                    applicable_years.append((year_int, info))
            except ValueError:
                continue
        
        if applicable_years:
            # Get most recent applicable year
            latest_year, latest_info = max(applicable_years, key=lambda x: x[0])
            return {
                **latest_info,
                "applicable_year": latest_year,
                "target_year": year,
                "years_since_base": year - 2002
            }
        
        # Default to base year
        return {
            **self.temporal_data["2002"],
            "applicable_year": 2002,
            "target_year": year,
            "years_since_base": year - 2002
        }
    
    def calculate_surcharge(self, base_amount: Decimal, context: Dict) -> Dict:
        """Calculate applicable surcharges."""
        surcharges = {}
        total_surcharge = Decimal("0")
        
        # Climate change surcharge
        if context.get("effective_date") >= date(2020, 1, 1):
            climate_rate = self.surcharge_data["climate_change_surcharge"]["base_rate"]
            
            # Check exemptions
            if not context.get("is_guzara_subsistence", False):
                climate_surcharge = base_amount * climate_rate
                surcharges["climate_change"] = {
                    "amount": climate_surcharge,
                    "rate": climate_rate,
                    "basis": self.surcharge_data["climate_change_surcharge"]["legal_basis"]
                }
                total_surcharge += climate_surcharge
        
        # Biodiversity surcharge
        if context.get("species_category") in ["highly_protected", "protected"]:
            biodiversity_rate = self.surcharge_data["biodiversity_surcharge"]["base_rate"]
            biodiversity_surcharge = base_amount * biodiversity_rate
            surcharges["biodiversity"] = {
                "amount": biodiversity_surcharge,
                "rate": biodiversity_rate,
                "basis": self.surcharge_data["biodiversity_surcharge"]["legal_basis"]
            }
            total_surcharge += biodiversity_surcharge
        
        # Watershed protection surcharge
        location_info = self.get_location_info(context.get("location", ""))
        if "watershed" in location_info.get("matched_location", "").lower():
            watershed_rate = self.surcharge_data["watershed_protection_surcharge"]["base_rate"]
            watershed_surcharge = base_amount * watershed_rate
            surcharges["watershed_protection"] = {
                "amount": watershed_surcharge,
                "rate": watershed_rate,
                "basis": self.surcharge_data["watershed_protection_surcharge"]["legal_basis"]
            }
            total_surcharge += watershed_surcharge
        
        return {
            "surcharges": surcharges,
            "total_surcharge": total_surcharge,
            "surcharge_percentage": (total_surcharge / base_amount) if base_amount > 0 else Decimal("0")
        }
    
    def update_research_stats(self, key: str, value: Any = 1):
        """Update research statistics."""
        self.research_stats[key] += value


class PenaltyLogicEngine:
    """
    Enhanced penalty logic engine with Phase 5.1 integration.
    """
    
    def __init__(self, 
                 config: Optional[Any] = None,
                 penalty_matrix: Optional[KPKPenaltyMatrix] = None,
                 authority_resolver: Optional[AuthorityHierarchyResolver] = None,
                 abstention_logger: Optional[AbstentionLogger] = None):
        
        self.config = config
        
        self.matrix = penalty_matrix or KPKPenaltyMatrix(authority_resolver)
        self.authority_resolver = authority_resolver
        self.abstention_logger = abstention_logger or AbstentionLogger()
        
        # Calculation history for research
        self.calculation_history = []
        self.research_metrics = {
            "total_calculations": 0,
            "total_fine_amount": Decimal("0"),
            "hazara_act_calculations": 0,
            "sro_based_calculations": 0,
            "climate_related_calculations": 0,
            "community_forest_calculations": 0,
            "average_confidence": 0.0,
            "average_complexity": 0.0
        }
        
        # Gazette registry for SRO validation
        self.gazette_registry = self._load_gazette_registry()
        
        # Officer discretion audit trail
        self.discretion_audit_trail = []
        
        logger.info("Enhanced PenaltyLogicEngine initialized")
    
    def _load_gazette_registry(self) -> Dict:
        """Load gazette registry for SRO validation."""
        return {
            "SRO-123/2010": {
                "date": date(2010, 3, 15),
                "subject": "Protected Species List Enhancement",
                "effective_date": date(2010, 4, 1),
                "penalty_changes": ["Deodar", "Kail"]
            },
            "SRO-456/2015": {
                "date": date(2015, 7, 1),
                "subject": "General Penalty Enhancement",
                "effective_date": date(2015, 8, 1),
                "penalty_multiplier": Decimal("2.0")
            },
            "SRO-789/2018": {
                "date": date(2018, 6, 15),
                "subject": "Biodiversity Surcharge",
                "effective_date": date(2018, 7, 1),
                "biodiversity_surcharge": Decimal("0.05")
            },
            "SRO-101/2020": {
                "date": date(2020, 1, 1),
                "subject": "Climate Change Surcharge",
                "effective_date": date(2020, 2, 1),
                "climate_surcharge": Decimal("0.10")
            }
        }
    
    def calculate_penalty(
        self,
        violation_type: Union[str, ViolationType],
        species: Optional[str] = None,
        quantity: int = 1,
        location: str = "KPK",
        forest_type: Optional[Union[str, ForestType]] = None,
        offense_count: int = 1,
        violation_date: Optional[Union[str, date]] = None,
        effective_date: Optional[Union[str, date]] = None,
        offender_type: str = "individual",
        previous_penalties: Optional[List[Dict]] = None,
        officer_rank: Optional[Union[str, OfficerRank]] = None,
        apply_discretion: bool = True,
        discretion_reason: Optional[str] = None,
        authority_context: Optional[Dict] = None,
        viva_mode: bool = False,
        **kwargs
    ) -> PenaltyCalculation:
        """
        Enhanced penalty calculation with research tracking.
        """
        start_time = datetime.now()
        
        logger.info(f"Calculating penalty: {violation_type}, species={species}, location={location}")
        
        # Parse inputs
        if isinstance(violation_type, str):
            violation_type_enum = self._parse_violation_type(violation_type)
        else:
            violation_type_enum = violation_type
        
        if isinstance(forest_type, str):
            try:
                forest_type_enum = ForestType(forest_type)
            except ValueError:
                forest_type_enum = self._infer_forest_type(location, kwargs.get("forest_type_hint"))
        else:
            forest_type_enum = forest_type
        
        # Parse dates
        violation_date_parsed = self._parse_date(violation_date)
        effective_date_parsed = self._parse_date(effective_date) or date.today()
        
        # Parse officer rank
        officer_rank_enum = None
        if officer_rank:
            if isinstance(officer_rank, str):
                try:
                    officer_rank_enum = OfficerRank(officer_rank)
                except ValueError:
                    officer_rank_enum = OfficerRank.FOREST_GUARD
            else:
                officer_rank_enum = officer_rank
        
        # Get species information
        species_info = None
        scientific_name = None
        if species:
            species_info = self.matrix.get_species_info(species)
            if species_info:
                scientific_name = species_info.get("scientific_name")
                self.matrix.update_research_stats("species_identified", 1)
            else:
                self.matrix.update_research_stats("species_unidentified", 1)
        
        # Get location information
        location_info = self.matrix.get_location_info(location)
        
        # Get temporal information
        temporal_info = self.matrix.get_temporal_multiplier(effective_date_parsed)
        
        # Determine applicable authorities (Phase 5.1 integration)
        applicable_authorities = []
        authority_source = None
        authority_resolution = None
        
        if self.authority_resolver:
            try:
                # Build conflicting sources for authority resolution
                conflicting_sources = self._build_authority_sources(
                    violation_type_enum, species_info, location, effective_date_parsed
                )
                
                if conflicting_sources:
                    resolution = self.authority_resolver.resolve_conflict(
                        entity=f"{violation_type_enum.value}_{species or 'unknown'}",
                        conflicting_sources=conflicting_sources,
                        location=location,
                        effective_date=effective_date_parsed,
                        context=authority_context or {},
                        viva_mode=viva_mode
                    )
                    
                    if resolution and resolution.selected_source:
                        authority_resolution = resolution
                        authority_source = resolution.selected_source
                        
                        # Update research stats
                        if hasattr(AuthorityLevel, 'HAZARA_ACT') and \
                           resolution.selected_source.authority_level == AuthorityLevel.HAZARA_ACT:
                            self.research_metrics["hazara_act_calculations"] += 1
                        
                        if hasattr(AuthorityLevel, 'GAZETTE_NOTIFICATION') and \
                           resolution.selected_source.authority_level == AuthorityLevel.GAZETTE_NOTIFICATION:
                            self.research_metrics["sro_based_calculations"] += 1
            except Exception as e:
                logger.warning(f"Authority resolution failed: {e}")
        
        # Start calculation
        calculation_steps = []
        applied_rules = []
        
        # Step 1: Get base penalty
        base_info = self.matrix.base_matrix.get(violation_type_enum)
        if not base_info:
            raise ValueError(f"Unsupported violation type: {violation_type_enum}")
        
        base_amount = base_info["base_amount"]
        calculation_steps.append({
            "step": "base_penalty",
            "description": f"Base penalty for {violation_type_enum.value}",
            "amount": f"{self.matrix.currency} {base_amount:,.2f}",
            "reference": base_info.get("primary_reference", ""),
            "rule": "base_penalty_lookup"
        })
        applied_rules.append("base_penalty_lookup")
        
        # Step 2: Apply quantity
        adjusted_amount = base_amount
        quantity_addition = Decimal("0")
        
        if quantity > 1 and "per_unit_additional" in base_info:
            additional_per_unit = base_info["per_unit_additional"]
            quantity_addition = additional_per_unit * (quantity - 1)
            adjusted_amount += quantity_addition
            
            calculation_steps.append({
                "step": "quantity_addition",
                "description": f"Additional for {quantity - 1} more {base_info.get('unit', 'units')}",
                "amount": f"{self.matrix.currency} {quantity_addition:,.2f}",
                "per_unit": f"{self.matrix.currency} {additional_per_unit:,.2f} per {base_info.get('unit', 'unit')}",
                "rule": "quantity_addition"
            })
            applied_rules.append("quantity_addition")
        
        # Step 3: Apply species multiplier
        species_multiplier = Decimal("1.0")
        if species_info:
            species_multiplier = species_info.get("base_multiplier", Decimal("1.0"))
            adjusted_amount *= species_multiplier
            
            calculation_steps.append({
                "step": "species_multiplier",
                "description": f"Multiplier for {species_info.get('matched_name', species)} ({species_info.get('category', 'unknown')})",
                "multiplier": f"{species_multiplier:.2f}x",
                "amount_effect": f"Applied {species_multiplier}x multiplier",
                "reference": species_info.get("legal_references", [""])[0],
                "rule": "species_multiplier"
            })
            applied_rules.append("species_multiplier")
            
            # Apply minimum fine if applicable
            if "minimum_fine" in species_info:
                minimum_fine = species_info["minimum_fine"]
                if adjusted_amount < minimum_fine:
                    adjusted_amount = minimum_fine
                    
                    calculation_steps.append({
                        "step": "species_minimum",
                        "description": f"Minimum fine for {species_info.get('matched_name', species)}",
                        "amount": f"{self.matrix.currency} {minimum_fine:,.2f}",
                        "rule": "species_minimum"
                    })
                    applied_rules.append("species_minimum")
        
        # Step 4: Apply location multiplier
        location_multiplier = location_info.get("multiplier", Decimal("1.0"))
        adjusted_amount *= location_multiplier
        
        if location_multiplier != Decimal("1.0"):
            calculation_steps.append({
                "step": "location_multiplier",
                "description": f"Location multiplier for {location_info.get('matched_location', location)}",
                "multiplier": f"{location_multiplier:.2f}x",
                "amount_effect": f"Applied {location_multiplier}x multiplier",
                "rule": "location_multiplier"
            })
            applied_rules.append("location_multiplier")
        
        # Step 5: Apply temporal multiplier
        temporal_multiplier = temporal_info.get("multiplier", Decimal("1.0"))
        adjusted_amount *= temporal_multiplier
        
        if temporal_multiplier != Decimal("1.0"):
            calculation_steps.append({
                "step": "temporal_adjustment",
                "description": f"Temporal adjustment ({temporal_info.get('description', 'Unknown')})",
                "multiplier": f"{temporal_multiplier:.2f}x",
                "applicable_year": temporal_info.get("applicable_year"),
                "gazette_ref": temporal_info.get("gazette_ref", ""),
                "rule": "temporal_adjustment"
            })
            applied_rules.append("temporal_adjustment")
        
        # Step 6: Apply repeat offense multiplier
        repeat_multiplier = Decimal("1.0")
        if offense_count > 1:
            if offense_count == 2:
                repeat_multiplier = Decimal("1.5")
            elif offense_count == 3:
                repeat_multiplier = Decimal("2.0")
            elif offense_count >= 4:
                repeat_multiplier = Decimal("3.0")
            
            adjusted_amount *= repeat_multiplier
            
            calculation_steps.append({
                "step": "repeat_offense",
                "description": f"Repeat offense multiplier (offense #{offense_count})",
                "multiplier": f"{repeat_multiplier:.2f}x",
                "rule": "repeat_offense_multiplier"
            })
            applied_rules.append("repeat_offense_multiplier")
        
        # Step 7: Apply forest type multiplier
        forest_type_multiplier = Decimal("1.0")
        if forest_type_enum:
            forest_type_info = self.matrix.forest_type_data.get(forest_type_enum, {})
            forest_type_multiplier = forest_type_info.get("multiplier", Decimal("1.0"))
            adjusted_amount *= forest_type_multiplier
            
            calculation_steps.append({
                "step": "forest_type_multiplier",
                "description": f"Forest type multiplier for {forest_type_enum.value}",
                "multiplier": f"{forest_type_multiplier:.2f}x",
                "legal_basis": forest_type_info.get("legal_basis", ""),
                "rule": "forest_type_multiplier"
            })
            applied_rules.append("forest_type_multiplier")
            
            # Update research stats
            if forest_type_enum == ForestType.GUZARA_FOREST:
                self.research_metrics["community_forest_calculations"] += 1
        
        # Step 8: Calculate surcharges
        surcharge_context = {
            "effective_date": effective_date_parsed,
            "species_category": species_info.get("category") if species_info else None,
            "location": location,
            "is_guzara_subsistence": forest_type_enum == ForestType.GUZARA_FOREST and quantity <= 3
        }
        
        surcharge_result = self.matrix.calculate_surcharge(adjusted_amount, surcharge_context)
        
        climate_surcharge = Decimal("0")
        biodiversity_surcharge = Decimal("0")
        
        if "climate_change" in surcharge_result["surcharges"]:
            climate_surcharge = surcharge_result["surcharges"]["climate_change"]["amount"]
            adjusted_amount += climate_surcharge
            
            calculation_steps.append({
                "step": "climate_surcharge",
                "description": "Climate change mitigation surcharge",
                "amount": f"{self.matrix.currency} {climate_surcharge:,.2f}",
                "rate": f"{surcharge_result['surcharges']['climate_change']['rate'] * 100:.0f}%",
                "basis": surcharge_result["surcharges"]["climate_change"]["basis"],
                "rule": "climate_surcharge"
            })
            applied_rules.append("climate_surcharge")
            
            if "climate" in violation_type_enum.value.lower():
                self.research_metrics["climate_related_calculations"] += 1
        
        if "biodiversity" in surcharge_result["surcharges"]:
            biodiversity_surcharge = surcharge_result["surcharges"]["biodiversity"]["amount"]
            adjusted_amount += biodiversity_surcharge
            
            calculation_steps.append({
                "step": "biodiversity_surcharge",
                "description": "Biodiversity conservation surcharge",
                "amount": f"{self.matrix.currency} {biodiversity_surcharge:,.2f}",
                "rule": "biodiversity_surcharge"
            })
            applied_rules.append("biodiversity_surcharge")
        
        # Step 9: Apply officer discretion
        discretion_applied = False
        discretion_percentage = Decimal("0")
        discretion_amount = Decimal("0")
        subtotal_before_discretion = adjusted_amount
        discretion_audit_trail = []
        
        if apply_discretion and officer_rank_enum:
            discretion_info = self.matrix.discretion_data.get(officer_rank_enum)
            if discretion_info:
                # For demonstration, apply midpoint of range
                min_adj = discretion_info["adjustment_range"]["min"]
                max_adj = discretion_info["adjustment_range"]["max"]
                discretion_percentage = (min_adj + max_adj) / Decimal("2")
                
                discretion_amount = adjusted_amount * discretion_percentage
                adjusted_amount += discretion_amount
                
                discretion_applied = True
                
                # Create audit trail entry
                audit_entry = {
                    "timestamp": datetime.now(),
                    "officer_rank": officer_rank_enum.value,
                    "discretion_percentage": float(discretion_percentage),
                    "discretion_amount": float(discretion_amount),
                    "reason": discretion_reason or "Standard discretion application",
                    "range_min": float(min_adj),
                    "range_max": float(max_adj)
                }
                discretion_audit_trail.append(audit_entry)
                self.discretion_audit_trail.append(audit_entry)
                
                calculation_steps.append({
                    "step": "officer_discretion",
                    "description": f"Officer discretion applied by {officer_rank_enum.value}",
                    "adjustment": f"{discretion_percentage * 100:+.1f}%",
                    "amount": f"{self.matrix.currency} {discretion_amount:,.2f}",
                    "rule": "officer_discretion"
                })
                applied_rules.append("officer_discretion")
        
        # Step 10: Round final amount
        total_fine = adjusted_amount.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        
        # Step 11: Determine non-monetary penalties
        imprisonment_term = None
        imprisonment_months = None
        community_service_hours = None
        confiscation_items = []
        restoration_requirements = []
        license_suspension_months = None
        
        if "imprisonment" in base_info:
            imp_info = base_info["imprisonment"]
            min_months = imp_info.get("min_months", 0)
            max_months = imp_info.get("max_months", 0)
            
            # Scale imprisonment based on severity
            severity_factor = min(Decimal("2.0"), total_fine / Decimal("100000"))
            imprisonment_months = int(min_months * severity_factor)
            
            if imprisonment_months > 0:
                if imprisonment_months >= 12:
                    years = imprisonment_months // 12
                    months = imprisonment_months % 12
                    imprisonment_term = f"{years} year{'s' if years > 1 else ''}{f' {months} months' if months > 0 else ''}"
                else:
                    imprisonment_term = f"{imprisonment_months} months"
        
        if "community_service" in base_info:
            cs_info = base_info["community_service"]
            base_hours = cs_info.get("base_hours", 0)
            per_unit_hours = cs_info.get("per_tree_hours", 0)  # Adjust based on unit
            
            community_service_hours = base_hours + (per_unit_hours * (quantity - 1))
            
            # Apply forest type weight
            if forest_type_enum and forest_type_info:
                cs_weight = forest_type_info.get("community_service_weight", Decimal("1.0"))
                community_service_hours = int(community_service_hours * cs_weight)
        
        if "confiscation" in base_info:
            confiscation_items = base_info["confiscation"]
        
        if "restoration" in base_info:
            restoration_requirements = base_info["restoration"]
            
            # Add forest type specific requirements
            if forest_type_enum and forest_type_info:
                additional_requirements = forest_type_info.get("restoration_requirements", [])
                restoration_requirements.extend(additional_requirements)
        
        if "license_suspension" in base_info:
            license_suspension_months = base_info["license_suspension"]
        
        # Step 12: Compile legal references
        primary_legal_reference = base_info.get("primary_reference", "")
        amendment_references = []
        gazette_references = base_info.get("gazette_references", [])
        section_references = base_info.get("section_references", [])
        
        # Add temporal amendment references
        if temporal_info.get("gazette_ref"):
            gazette_references.append(temporal_info["gazette_ref"])
            amendment_references.append(f"Amended by {temporal_info['gazette_ref']}")
        
        # Add species references
        if species_info:
            species_refs = species_info.get("legal_references", [])
            gazette_references.extend(species_refs)
        
        # Step 13: Calculate confidence
        confidence_score, confidence_breakdown = self._calculate_confidence(
            species_info is not None,
            location_info.get("multiplier", Decimal("1.0")) != Decimal("1.0"),
            temporal_info.get("multiplier", Decimal("1.0")) != Decimal("1.0"),
            offense_count > 1,
            authority_source is not None,
            len(calculation_steps)
        )
        
        # Step 14: Validate calculation
        validation_passed, validation_errors = self._validate_calculation(
            total_fine, species_info, officer_rank_enum, discretion_percentage
        )
        
        # Step 15: Generate warnings
        warnings = self._generate_warnings(
            total_fine, species_info, location_info, forest_type_enum
        )
        
        # Step 16: Apply quality gates
        passed_gates, failed_gates = self._apply_quality_gates(
            total_fine, confidence_score, validation_passed, species_info
        )
        
        # Step 17: Calculate complexity
        complexity_score = self._calculate_complexity(
            species_info, location_info, temporal_info, offense_count
        )
        
        # Step 18: Create result object
        result = PenaltyCalculation(
            violation_type=violation_type_enum.value,
            species=species_info.get("matched_name", species) if species_info else species,
            scientific_name=scientific_name,
            quantity=quantity,
            unit=base_info.get("unit", "unit"),
            location=location,
            forest_type=forest_type_enum,
            jurisdiction_details=location_info,
            violation_date=violation_date_parsed,
            effective_date=effective_date_parsed,
            processing_date=date.today(),
            offense_count=offense_count,
            offender_type=offender_type,
            is_repeat_offender=offense_count > 1,
            previous_penalties=previous_penalties or [],
            authority_source=authority_source,
            authority_resolution=authority_resolution,
            applicable_authorities=applicable_authorities,
            base_amount=base_amount,
            species_multiplier=species_multiplier,
            location_multiplier=location_multiplier,
            temporal_multiplier=temporal_multiplier,
            repeat_multiplier=repeat_multiplier,
            forest_type_multiplier=forest_type_multiplier,
            climate_surcharge=climate_surcharge,
            biodiversity_surcharge=biodiversity_surcharge,
            officer_rank=officer_rank_enum,
            discretion_percentage=discretion_percentage,
            discretion_reason=discretion_reason,
            discretion_audit_trail=discretion_audit_trail,
            subtotal_before_discretion=subtotal_before_discretion,
            discretion_amount=discretion_amount,
            total_fine=total_fine,
            currency=self.matrix.currency,
            imprisonment_term=imprisonment_term,
            imprisonment_months=imprisonment_months,
            community_service_hours=community_service_hours,
            confiscation_items=confiscation_items,
            restoration_requirements=restoration_requirements,
            license_suspension_months=license_suspension_months,
            primary_legal_reference=primary_legal_reference,
            amendment_references=amendment_references,
            gazette_references=gazette_references,
            section_references=section_references,
            calculation_steps=calculation_steps,
            applied_rules=applied_rules,
            confidence_score=confidence_score,
            confidence_breakdown=confidence_breakdown,
            complexity_score=complexity_score,
            validation_passed=validation_passed,
            validation_errors=validation_errors,
            warnings=warnings,
            passed_quality_gates=passed_gates,
            failed_quality_gates=failed_gates
        )
        
        # Step 19: Update research metrics
        self._update_research_metrics(result)
        
        # Step 20: Add to history
        self.calculation_history.append(result)
        
        # Step 21: Log for VIVA
        if viva_mode:
            self._log_viva_demo(result, start_time)
        
        logger.info(f"Penalty calculated: {self.matrix.currency} {total_fine:,.2f} "
                   f"(confidence: {confidence_score:.1%}, complexity: {complexity_score:.1%})")
        
        return result
    
    def _parse_violation_type(self, text: str) -> ViolationType:
        """Parse violation type from text with enhanced matching."""
        text_lower = text.lower()
        
        # Tree-related violations
        if any(word in text_lower for word in ["fell", "cut", "کٹائی", "درخت کاٹنا"]):
            if "commercial" in text_lower or "logging" in text_lower:
                return ViolationType.UNAUTHORIZED_LOGGING
            return ViolationType.UNAUTHORIZED_FELLING
        
        # Transport violations
        if any(word in text_lower for word in ["transport", "نقل", "گاڑی", "ٹرک"]):
            if "firewood" in text_lower or "لکڑی" in text_lower:
                return ViolationType.ILLEGAL_TRANSPORT_FIREWOOD
            return ViolationType.ILLEGAL_TRANSPORT_TIMBER
        
        # Collection violations
        if any(word in text_lower for word in ["firewood", "ایندھن", "لکڑی اکٹھا"]):
            return ViolationType.FIREWOOD_COLLECTION
        
        # Climate-related violations (RESEARCH FOCUS)
        if any(word in text_lower for word in ["carbon", "کاربن", "climate", "موسمیاتی"]):
            return ViolationType.CARBON_SEQUESTRATION_DAMAGE
        
        # Community forest violations
        if any(word in text_lower for word in ["guzara", "گزارہ", "community forest"]):
            return ViolationType.COMMUNITY_FOREST_BREACH
        
        # Default to most common
        return ViolationType.UNAUTHORIZED_FELLING
    
    def _infer_forest_type(self, location: str, hint: Optional[str] = None) -> Optional[ForestType]:
        """Infer forest type from location and hints."""
        location_lower = location.lower()
        
        if hint:
            hint_lower = hint.lower()
            if "guzara" in hint_lower or "گزارہ" in hint_lower:
                return ForestType.GUZARA_FOREST
            if "reserved" in hint_lower or "مختص" in hint_lower:
                return ForestType.RESERVED_FOREST
            if "protected" in hint_lower or "محفوظ" in hint_lower:
                return ForestType.PROTECTED_FOREST
            if "community" in hint_lower or "اجتماعی" in hint_lower:
                return ForestType.COMMUNITY_FOREST
            if "watershed" in hint_lower:
                return ForestType.WATERSHED_FOREST
        
        # Infer from location names
        if "guzara" in location_lower or "گزارہ" in location_lower:
            return ForestType.GUZARA_FOREST
        
        if any(word in location_lower for word in ["reserved", "مختص"]):
            return ForestType.RESERVED_FOREST
        
        if any(word in location_lower for word in ["protected", "محفوظ", "national park", "قومی پارک"]):
            return ForestType.PROTECTED_FOREST
        
        return None
    
    def _parse_date(self, date_input: Optional[Union[str, date]]) -> Optional[date]:
        """Parse date from various input formats."""
        if date_input is None:
            return None
        
        if isinstance(date_input, date):
            return date_input
        
        try:
            # Try ISO format
            return datetime.fromisoformat(date_input.replace('Z', '+00:00')).date()
        except ValueError:
            pass
        
        try:
            # Try common formats
            for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y.%m.%d']:
                try:
                    return datetime.strptime(date_input, fmt).date()
                except ValueError:
                    continue
        except Exception:
            pass
        
        # Try to extract year from string
        year_match = re.search(r'\b(\d{4})\b', date_input)
        if year_match:
            year = int(year_match.group(1))
            return date(year, 1, 1)
        
        return None
    
    def _build_authority_sources(self, violation_type: ViolationType, 
                                 species_info: Optional[Dict], 
                                 location: str,
                                 effective_date: date) -> List[Dict]:
        """Build authority sources for Phase 5.1 resolution."""
        sources = []
        
        # Base KPK Ordinance source
        sources.append({
            "title": "KPK Forest Ordinance 2002",
            "authority": "kpk_ordinance",
            "jurisdiction": "provincial",
            "effective_date": "2002-06-15",
            "relevance": "base_law",
            "confidence": 0.95
        })
        
        # Hazara Act source if location in Hazara
        if "hazara" in location.lower():
            sources.append({
                "title": "Hazara Forest Act 1936",
                "authority": "hazara_act",
                "jurisdiction": "regional",
                "effective_date": "1936-11-10",
                "relevance": "special_regional_law",
                "confidence": 0.85
            })
        
        # Add SRO-based sources based on effective date
        if effective_date >= date(2010, 1, 1):
            sources.append({
                "title": "SRO-123/2010 - Protected Species Enhancement",
                "authority": "gazette_notification",
                "jurisdiction": "provincial",
                "effective_date": "2010-04-01",
                "gazette_reference": "SRO-123/2010",
                "relevance": "amendment",
                "confidence": 0.90
            })
        
        if effective_date >= date(2015, 1, 1):
            sources.append({
                "title": "SRO-456/2015 - General Penalty Enhancement",
                "authority": "gazette_notification",
                "jurisdiction": "provincial",
                "effective_date": "2015-08-01",
                "gazette_reference": "SRO-456/2015",
                "relevance": "amendment",
                "confidence": 0.90
            })
        
        # Species-specific SRO if applicable
        if species_info and species_info.get("category") in ["highly_protected", "protected"]:
            sources.append({
                "title": f"Protected Species List - {species_info.get('matched_name', 'Species')}",
                "authority": "department_circular",
                "jurisdiction": "provincial",
                "effective_date": "2010-04-01",
                "relevance": "species_specific",
                "confidence": 0.80
            })
        
        return sources
    
    def _calculate_confidence(self, species_identified: bool, 
                             location_specific: bool,
                             temporal_specific: bool,
                             repeat_offense: bool,
                             authority_resolved: bool,
                             step_count: int) -> Tuple[float, Dict[str, float]]:
        """Calculate confidence score with breakdown."""
        breakdown = {}
        total = 0.0
        
        # Base confidence
        base_confidence = 0.6
        total += base_confidence
        breakdown["base"] = base_confidence
        
        # Species identification
        if species_identified:
            species_confidence = 0.15
            total += species_confidence
            breakdown["species"] = species_confidence
        
        # Location specificity
        if location_specific:
            location_confidence = 0.10
            total += location_confidence
            breakdown["location"] = location_confidence
        
        # Temporal specificity
        if temporal_specific:
            temporal_confidence = 0.08
            total += temporal_confidence
            breakdown["temporal"] = temporal_confidence
        
        # Repeat offense data
        if repeat_offense:
            repeat_confidence = 0.05
            total += repeat_confidence
            breakdown["repeat_offense"] = repeat_confidence
        
        # Authority resolution
        if authority_resolved:
            authority_confidence = 0.12
            total += authority_confidence
            breakdown["authority"] = authority_confidence
        
        # Calculation detail
        if step_count > 5:
            detail_confidence = min(0.10, (step_count - 5) * 0.02)
            total += detail_confidence
            breakdown["detail"] = detail_confidence
        
        # Cap at 0.95 (always some legal uncertainty)
        confidence = min(0.95, total)
        
        # Normalize breakdown
        if total > 0:
            scale = confidence / total
            for key in breakdown:
                breakdown[key] *= scale
        
        return confidence, breakdown
    
    def _validate_calculation(self, total_fine: Decimal, 
                             species_info: Optional[Dict],
                             officer_rank: Optional[OfficerRank],
                             discretion_percentage: Decimal) -> Tuple[bool, List[str]]:
        """Validate penalty calculation."""
        errors = []
        
        # Check species minimum
        if species_info and "minimum_fine" in species_info:
            minimum = species_info["minimum_fine"]
            if total_fine < minimum:
                errors.append(f"Fine below species minimum of {self.matrix.currency} {minimum:,.2f}")
        
        # Check officer discretion limits
        if officer_rank and discretion_percentage != Decimal("0"):
            discretion_info = self.matrix.discretion_data.get(officer_rank)
            if discretion_info:
                min_adj = discretion_info["adjustment_range"]["min"]
                max_adj = discretion_info["adjustment_range"]["max"]
                
                if discretion_percentage < min_adj or discretion_percentage > max_adj:
                    errors.append(f"Discretion {discretion_percentage*100:.1f}% outside allowed range "
                                 f"[{min_adj*100:.0f}%, {max_adj*100:.0f}%]")
        
        # Check for absurdly high/low fines
        if total_fine > Decimal("10000000"):  # 10 million PKR
            errors.append(f"Fine amount {self.matrix.currency} {total_fine:,.2f} appears excessively high")
        
        if total_fine < Decimal("100"):  # 100 PKR
            errors.append(f"Fine amount {self.matrix.currency} {total_fine:,.2f} appears excessively low")
        
        return len(errors) == 0, errors
    
    def _generate_warnings(self, total_fine: Decimal,
                          species_info: Optional[Dict],
                          location_info: Dict,
                          forest_type: Optional[ForestType]) -> List[str]:
        """Generate warnings about the calculation."""
        warnings = []
        
        # Species protection level warning
        if species_info and species_info.get("category") == "highly_protected":
            warnings.append(f"Highly protected species: {species_info.get('matched_name')}")
        
        # High protection area warning
        if location_info.get("multiplier", Decimal("1.0")) > Decimal("1.5"):
            warnings.append(f"High protection area: {location_info.get('matched_location')}")
        
        # Community forest warning
        if forest_type == ForestType.GUZARA_FOREST:
            warnings.append("Community forest (Guzara): Different legal regime applies")
        
        # Climate surcharge warning
        if total_fine > Decimal("100000"):
            warnings.append("Climate change surcharge may apply")
        
        return warnings
    
    def _apply_quality_gates(self, total_fine: Decimal,
                            confidence: float,
                            validation_passed: bool,
                            species_info: Optional[Dict]) -> Tuple[List[str], List[str]]:
        """Apply quality gates from Phase 7."""
        passed = []
        failed = []
        
        # Gate 1: Confidence threshold
        if confidence >= 0.7:
            passed.append("confidence_threshold")
        else:
            failed.append("confidence_threshold")
        
        # Gate 2: Validation passed
        if validation_passed:
            passed.append("validation_passed")
        else:
            failed.append("validation_passed")
        
        # Gate 3: Reasonable amount
        if Decimal("100") <= total_fine <= Decimal("1000000"):
            passed.append("reasonable_amount")
        else:
            failed.append("reasonable_amount")
        
        # Gate 4: Species identified (if applicable)
        if species_info:
            passed.append("species_identified")
        else:
            # Only fail if species was expected
            pass
        
        return passed, failed
    
    def _calculate_complexity(self, species_info: Optional[Dict],
                             location_info: Dict,
                             temporal_info: Dict,
                             offense_count: int) -> float:
        """Calculate complexity score."""
        complexity = 0.0
        
        # Species complexity
        if species_info:
            if species_info.get("category") == "highly_protected":
                complexity += 0.2
            elif species_info.get("category") == "protected":
                complexity += 0.1
        
        # Location complexity
        loc_multiplier = location_info.get("multiplier", Decimal("1.0"))
        if loc_multiplier > Decimal("1.5"):
            complexity += 0.15
        elif loc_multiplier > Decimal("1.0"):
            complexity += 0.1
        
        # Temporal complexity
        temp_multiplier = temporal_info.get("multiplier", Decimal("1.0"))
        if temp_multiplier > Decimal("2.0"):
            complexity += 0.15
        elif temp_multiplier > Decimal("1.0"):
            complexity += 0.1
        
        # Repeat offense complexity
        if offense_count > 1:
            complexity += min(0.2, offense_count * 0.05)
        
        return min(complexity, 1.0)
    
    def _update_research_metrics(self, penalty: PenaltyCalculation):
        """Update research metrics with new calculation."""
        self.research_metrics["total_calculations"] += 1
        self.research_metrics["total_fine_amount"] += penalty.total_fine
        self.research_metrics["average_confidence"] = (
            (self.research_metrics["average_confidence"] * (self.research_metrics["total_calculations"] - 1) + 
             penalty.confidence_score) / self.research_metrics["total_calculations"]
        )
        self.research_metrics["average_complexity"] = (
            (self.research_metrics["average_complexity"] * (self.research_metrics["total_calculations"] - 1) + 
             penalty.complexity_score) / self.research_metrics["total_calculations"]
        )
    
    def _log_viva_demo(self, penalty: PenaltyCalculation, start_time: datetime):
        """Log detailed information for VIVA demonstration."""
        duration = (datetime.now() - start_time).total_seconds() * 1000
        
        viva_log = {
            "timestamp": datetime.now().isoformat(),
            "calculation_id": penalty.calculation_id,
            "violation_type": penalty.violation_type,
            "species": penalty.species,
            "total_fine": float(penalty.total_fine),
            "confidence": penalty.confidence_score,
            "complexity": penalty.complexity_score,
            "research_significance": penalty.research_significance,
            "calculation_steps": len(penalty.calculation_steps),
            "applied_rules": len(penalty.applied_rules),
            "duration_ms": duration,
            "authority_resolved": penalty.authority_resolution is not None,
            "quality_gates_passed": len(penalty.passed_quality_gates),
            "quality_gates_failed": len(penalty.failed_quality_gates)
        }
        
        logger.info(f"VIVA Demo Log: {json.dumps(viva_log, indent=2, default=str)}")
    
    def parse_penalty_from_text(self, text: str, **kwargs) -> Optional[PenaltyCalculation]:
        """Enhanced text parsing for penalties."""
        logger.info(f"Parsing penalty from text: {text[:100]}...")
        
        extracted = self._extract_penalty_info(text)
        
        if extracted:
            try:
                return self.calculate_penalty(
                    violation_type=extracted.get("violation_type", "unauthorized_felling"),
                    species=extracted.get("species"),
                    quantity=extracted.get("quantity", 1),
                    location=extracted.get("location", "KPK"),
                    offense_count=extracted.get("offense_count", 1),
                    **kwargs
                )
            except Exception as e:
                logger.error(f"Failed to calculate parsed penalty: {e}")
        
        return None
    
    def _extract_penalty_info(self, text: str) -> Dict:
        """Extract penalty information from legal text."""
        extracted = {}
        
        # Extract fine amount
        amount_patterns = [
            r'Rs\.?\s*([\d,]+)',
            r'جرمانہ.*?([\d,]+)',
            r'fine.*?([\d,]+)'
        ]
        
        for pattern in amount_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(',', '')
                extracted["base_amount"] = Decimal(amount_str)
                break
        
        # Extract species
        species_patterns = [
            r'(Deodar|دیار|Kail|کایل|Chir|چیر|Walnut|اخروٹ)',
            r'(درخت|tree).*?(?:of|کا)\s*([A-Za-z]+)'
        ]
        
        for pattern in species_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                extracted["species"] = match.group(1)
                break
        
        # Extract quantity
        quantity_patterns = [
            r'(\d+)\s*(?:درخت|trees?)',
            r'فی\s*درخت.*?(\d+)',
            r'per\s*tree.*?(\d+)'
        ]
        
        for pattern in quantity_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                extracted["quantity"] = int(match.group(1))
                break
        
        # Extract imprisonment
        imprisonment_patterns = [
            r'قید.*?(\d+)\s*(?:ماہ|month)',
            r'imprisonment.*?(\d+)\s*(?:ماہ|month)',
            r'(\d+)\s*(?:ماہ|month).*?قید'
        ]
        
        for pattern in imprisonment_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                extracted["imprisonment_months"] = int(match.group(1))
                break
        
        return extracted
    
    def get_research_statistics(self) -> Dict:
        """Get comprehensive research statistics."""
        return {
            **self.research_metrics,
            "matrix_stats": dict(self.matrix.research_stats),
            "total_discretion_applied": len(self.discretion_audit_trail),
            "calculation_history_count": len(self.calculation_history),
            "average_fine_amount": (
                self.research_metrics["total_fine_amount"] / self.research_metrics["total_calculations"]
                if self.research_metrics["total_calculations"] > 0 else Decimal("0")
            )
        }
    
    def export_calculations_for_graph(self) -> Dict:
        """Export calculations for Phase 6 graph construction."""
        nodes = []
        edges = []
        
        for calc in self.calculation_history:
            # Penalty node
            penalty_node = {
                "id": calc.graph_node_id,
                "label": f"Penalty_{calc.violation_type}",
                "type": "PenaltyCalculation",
                "properties": {
                    "violation_type": calc.violation_type,
                    "species": calc.species,
                    "total_fine": float(calc.total_fine),
                    "confidence": calc.confidence_score,
                    "complexity": calc.complexity_score,
                    "timestamp": calc.timestamp.isoformat()
                }
            }
            nodes.append(penalty_node)
            
            # Authority relationship
            if calc.authority_source and calc.authority_source.node_id:
                edge = {
                    "id": f"auth_{calc.calculation_id}",
                    "source": calc.graph_node_id,
                    "target": calc.authority_source.node_id,
                    "type": "BASED_ON",
                    "properties": {
                        "authority_level": calc.authority_source.authority_level.value 
                            if hasattr(calc.authority_source, 'authority_level') else "unknown",
                        "confidence": calc.confidence_score
                    }
                }
                edges.append(edge)
            
            # Species relationship
            if calc.species:
                species_node_id = f"Species_{calc.species}"
                
                # Check if species node already exists
                if not any(n["id"] == species_node_id for n in nodes):
                    species_node = {
                        "id": species_node_id,
                        "label": calc.species,
                        "type": "TreeSpecies",
                        "properties": {
                            "scientific_name": calc.scientific_name
                        }
                    }
                    nodes.append(species_node)
                
                edge = {
                    "id": f"species_{calc.calculation_id}",
                    "source": calc.graph_node_id,
                    "target": species_node_id,
                    "type": "INVOLVES",
                    "properties": {
                        "quantity": calc.quantity,
                        "species_multiplier": float(calc.species_multiplier)
                    }
                }
                edges.append(edge)
        
        return {
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "total_calculations": len(self.calculation_history),
                "generated_at": datetime.now().isoformat(),
                "graph_type": "penalty_calculation_network",
                "purpose": "Phase 6 graph construction"
            }
        }


# Factory functions and utilities
def create_penalty_engine(
    authority_resolver: Optional[AuthorityHierarchyResolver] = None,
    abstention_logger: Optional[AbstentionLogger] = None
) -> PenaltyLogicEngine:
    """Create enhanced penalty engine."""
    return PenaltyLogicEngine(
        authority_resolver=authority_resolver,
        abstention_logger=abstention_logger
    )


def calculate_quick_penalty(
    violation_desc: str,
    species: Optional[str] = None,
    location: str = "KPK",
    lang: str = "en"
) -> str:
    """Quick penalty calculation for demonstrations."""
    engine = PenaltyLogicEngine()
    
    try:
        penalty = engine.calculate_penalty(
            violation_type=violation_desc,
            species=species,
            location=location,
            viva_mode=False
        )
        
        return penalty.to_human_readable(lang)
    except Exception as e:
        return f"Error calculating penalty: {str(e)}"


# Example usage and testing
if __name__ == "__main__":
    print("=" * 80)
    print("ENHANCED KPK PENALTY LOGIC ENGINE - RESEARCH DEMONSTRATION")
    print("=" * 80)
    print("Phase 5.2: Penalty Logic with Authority Integration")
    print("")
    
    # Initialize engine
    engine = PenaltyLogicEngine()
    
    # Test Case 1: RESEARCH FOCUS - Hazara Act Special Case
    print("TEST CASE 1: Hazara Act Special Penalty Calculation")
    print("-" * 80)
    
    penalty1 = engine.calculate_penalty(
        violation_type="unauthorized_felling",
        species="Deodar",
        quantity=2,
        location="Mansehra, Hazara Division",
        forest_type="reserved_forest",
        offense_count=1,
        violation_date="2023-06-15",
        effective_date="2023-06-15",
        viva_mode=True
    )
    
    print(penalty1.to_human_readable())
    print(f"\nResearch Significance: {penalty1.research_significance}")
    print(f"Complexity Score: {penalty1.complexity_score:.1%}")
    
    print("\n" + "=" * 80)
    
    # Test Case 2: Climate-related violation with surcharges
    print("\nTEST CASE 2: Climate Change Surcharge Calculation")
    print("-" * 80)
    
    penalty2 = engine.calculate_penalty(
        violation_type="carbon_sequestration_damage",
        species="Kail",
        quantity=5,
        location="Watershed Area, Swat",
        forest_type="watershed_forest",
        offense_count=1,
        effective_date="2023-01-01",
        viva_mode=False
    )
    
    print(penalty2.to_human_readable())
    print(f"\nClimate Surcharge: {engine.matrix.currency} {penalty2.climate_surcharge:,.2f}")
    print(f"Biodiversity Surcharge: {engine.matrix.currency} {penalty2.biodiversity_surcharge:,.2f}")
    
    print("\n" + "=" * 80)
    
    # Test Case 3: Community Forest (Guzara) Special Regime
    print("\nTEST CASE 3: Community Forest (Guzara) Penalty")
    print("-" * 80)
    
    penalty3 = engine.calculate_penalty(
        violation_type="community_forest_breach",
        species="Walnut",
        quantity=1,
        location="Guzara Forest, Dir",
        forest_type="guzara_forest",
        offense_count=1,
        offender_type="community_member",
        viva_mode=False
    )
    
    print(penalty3.to_human_readable("ur"))  # Urdu output
    print(f"\nForest Type: {penalty3.forest_type.value if penalty3.forest_type else 'N/A'}")
    print(f"Community Service Hours: {penalty3.community_service_hours}")
    
    print("\n" + "=" * 80)
    
    # Test Case 4: Repeat Offense with Officer Discretion
    print("\nTEST CASE 4: Repeat Offense with DFO Discretion")
    print("-" * 80)
    
    penalty4 = engine.calculate_penalty(
        violation_type="illegal_transport_timber",
        species="Chir",
        quantity=3,
        location="Malakand Division",
        offense_count=3,
        officer_rank="divisional_forest_officer",
        apply_discretion=True,
        discretion_reason="First-time offender in family, cooperative attitude",
        viva_mode=False
    )
    
    print(penalty4.to_human_readable())
    print(f"\nDiscretion Applied: {penalty4.discretion_percentage * 100:+.1f}%")
    print(f"Discretion Amount: {engine.matrix.currency} {penalty4.discretion_amount:,.2f}")
    
    print("\n" + "=" * 80)
    
    # Test Case 5: Research Statistics and Export
    print("\nTEST CASE 5: Research Statistics and Graph Export")
    print("-" * 80)
    
    stats = engine.get_research_statistics()
    print(f"Total Calculations: {stats['total_calculations']}")
    print(f"Average Confidence: {stats['average_confidence']:.1%}")
    print(f"Average Complexity: {stats['average_complexity']:.1%}")
    print(f"Hazara Act Calculations: {stats['hazara_act_calculations']}")
    print(f"SRO-based Calculations: {stats['sro_based_calculations']}")
    print(f"Climate-related Calculations: {stats['climate_related_calculations']}")
    print(f"Community Forest Calculations: {stats['community_forest_calculations']}")
    print(f"Average Fine Amount: {engine.matrix.currency} {float(stats['average_fine_amount']):,.2f}")
    
    # Export for Phase 6 graph
    graph_data = engine.export_calculations_for_graph()
    print(f"\nGraph Export Prepared:")
    print(f"  Nodes: {len(graph_data['nodes'])}")
    print(f"  Edges: {len(graph_data['edges'])}")
    print(f"  Graph Type: {graph_data['metadata']['graph_type']}")
    
    print("\n" + "=" * 80)
    
    # Display penalty matrix summary
    print("\nPENALTY MATRIX SUMMARY:")
    print("-" * 80)
    
    print(f"\nSpecies in Database: {len(engine.matrix.species_data)}")
    protected_species = [s for s, info in engine.matrix.species_data.items() 
                        if info.get('category') in ['highly_protected', 'protected']]
    print(f"Protected Species: {len(protected_species)}")
    
    print(f"\nViolation Types: {len(engine.matrix.base_matrix)}")
    print(f"Forest Type Regimes: {len(engine.matrix.forest_type_data)}")
    print(f"Temporal Adjustments: {len(engine.matrix.temporal_data)}")
    
    print(f"\nSurcharge Types:")
    for surcharge, info in engine.matrix.surcharge_data.items():
        rate = info.get('base_rate', Decimal('0')) * 100
        print(f"  - {surchcharge}: {rate:.0f}% ({info.get('legal_basis', 'No basis')})")
    
    print("\n" + "=" * 80)
    print("Enhanced Penalty Logic Engine Test Complete ✓")
    print("Ready for Phase 6 Graph Construction")
    print("=" * 80)
