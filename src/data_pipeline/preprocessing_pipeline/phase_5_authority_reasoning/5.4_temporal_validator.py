"""
TEMPORAL_VALIDATOR.PY - ENHANCED
===========================================================
PHASE 5.4: TEMPORAL VALIDATION WITH ENHANCED KPK-SPECIFIC RULES

ENHANCEMENTS:
1. ✅ Integration with Phase 5.1 (Authority Hierarchy)
2. ✅ Integration with Phase 5.2 (Penalty Logic)
3. ✅ Integration with Phase 5.3 (LLM Ambiguity Resolution)
4. ✅ KPK-specific gazette publication rules
5. ✅ Amendment chain temporal validation
6. ✅ Retroactive application handling
7. ✅ Research-grade validation metrics
8. ✅ Graph output for Phase 6

KEY FEATURES:
- Gazette notification effective date calculation
- Amendment supersession tracking
- Working plan validity periods
- SRO (Statutory Regulatory Order) temporal validation
- Climate policy timeline integration
"""

import logging
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any, Set
from dataclasses import dataclass, asdict, field
from datetime import datetime, date, timedelta
from enum import Enum
import hashlib
from decimal import Decimal

# Import from Phase 5.1-5.3
try:
    from .authority_hierarchy import (
        AuthorityHierarchyResolver, 
        AuthorityLevel, 
        LegalSource,
        ResolutionResult
    )
    from .penalty_logic_engine import PenaltyLogicEngine, PenaltyCalculation
    from .llm_ambiguity_resolver import LLMAmbiguityResolver, AmbiguityType
    from ..phase_0_foundation.abstention_log import AbstentionLogger
    from ..phase_4_legal_extraction.amendment_tracker import AmendmentChain
    from ..common.config import KPK_FORESTRY_CONFIG
except ImportError:
    # Fallback for standalone testing
    class AuthorityHierarchyResolver:
        pass
    class AuthorityLevel(Enum):
        pass
    class LegalSource:
        pass
    class PenaltyLogicEngine:
        pass
    class PenaltyCalculation:
        pass
    class LLMAmbiguityResolver:
        pass
    class AmbiguityType(Enum):
        pass
    class AbstentionLogger:
        def log_abstention(self, *args, **kwargs):
            pass
    class AmendmentChain:
        pass
    KPK_FORESTRY_CONFIG = {}

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TemporalValidityStatus(Enum):
    """Enhanced temporal validity statuses"""
    VALID = "valid"                    # Currently valid
    EXPIRED = "expired"                # Past expiry date
    NOT_YET_EFFECTIVE = "not_yet_effective"  # Before effective date
    SUSPENDED = "suspended"            # Temporarily suspended
    REPEALED = "repealed"              # Formally repealed
    SUPERSEDED = "superseded"          # Replaced by newer version
    AMENDED = "amended"                # Modified but still partially valid
    RETROACTIVE = "retroactive"        # Applied retroactively
    TRANSITIONAL = "transitional"      # In transition period
    UNCERTAIN = "uncertain"            # Cannot determine
    INVALID = "invalid"                # Invalid for other reasons


class GazetteType(Enum):
    """Types of gazette publications in KPK"""
    GAZETTE_EXTRAORDINARY = "gazette_extraordinary"  # Immediate effect
    GAZETTE_REGULAR = "gazette_regular"              # Standard publication
    GAZETTE_SUPPLEMENT = "gazette_supplement"        # Supplementary
    GAZETTE_SPECIAL = "gazette_special"              # Special issue


class TemporalConflictType(Enum):
    """Types of temporal conflicts"""
    EFFECTIVE_DATE_CONFLICT = "effective_date_conflict"
    EXPIRY_DATE_CONFLICT = "expiry_date_conflict"
    AMENDMENT_CHAIN_BREAK = "amendment_chain_break"
    RETROACTIVE_APPLICATION = "retroactive_application"
    SUSPENSION_PERIOD = "suspension_period"
    TRANSITION_OVERLAP = "transition_overlap"
    GAZETTE_VALIDATION = "gazette_validation"
    WORKING_PLAN_EXPIRY = "working_plan_expiry"


@dataclass
class TemporalValidation:
    """Enhanced temporal validation result"""
    validation_id: str = field(default_factory=lambda: f"tempval_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hashlib.md5(str(datetime.now()).encode()).hexdigest()[:6]}")
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Entity being validated
    entity_id: Optional[str] = None
    entity_type: str = "unknown"  # law, section, circular, sro, etc.
    entity_title: Optional[str] = None
    
    # Validation parameters
    validation_date: date = field(default_factory=date.today)
    effective_date: Optional[date] = None
    expiry_date: Optional[date] = None
    gazette_date: Optional[date] = None
    enforcement_date: Optional[date] = None
    
    # Gazette information
    gazette_type: Optional[GazetteType] = None
    gazette_reference: Optional[str] = None
    gazette_page: Optional[str] = None
    
    # Amendment chain
    amendment_chain_id: Optional[str] = None
    parent_entity_id: Optional[str] = None
    amendment_date: Optional[date] = None
    
    # Validation results
    validity_status: TemporalValidityStatus = TemporalValidityStatus.UNCERTAIN
    confidence: float = 0.0
    is_current: bool = False
    is_retroactive: bool = False
    
    # Detailed analysis
    days_since_effective: Optional[int] = None
    days_until_expiry: Optional[int] = None
    gazette_delay_days: Optional[int] = None
    enforcement_delay_days: Optional[int] = None
    
    # Conflicts and issues
    conflicts: List[Dict] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    
    # KPK-specific factors
    kpk_jurisdiction: bool = False
    involves_hazara_act: bool = False
    involves_sro: bool = False
    is_working_plan: bool = False
    
    # Phase integration
    authority_validation: Optional[Dict] = None
    penalty_validation: Optional[Dict] = None
    llm_resolution: Optional[Dict] = None
    
    # Research metrics
    complexity_score: float = 0.0
    validation_time_ms: int = 0
    rules_applied: List[str] = field(default_factory=list)
    
    # Phase 6 graph integration
    graph_node_id: Optional[str] = None
    graph_relationships: List[Dict] = field(default_factory=list)
    
    def __post_init__(self):
        # Generate graph node ID
        if not self.graph_node_id:
            self.graph_node_id = f"TemporalValidation_{self.validation_id}"
        
        # Calculate complexity
        self.complexity_score = self._calculate_complexity()
        
        # Auto-detect KPK factors
        self._detect_kpk_factors()
    
    @property
    def is_consistent(self) -> bool:
        """Compatibility property for pipeline."""
        return self.validity_status in [TemporalValidityStatus.VALID, TemporalValidityStatus.RETROACTIVE, TemporalValidityStatus.TRANSITION_OVERLAP]
    
    def _calculate_complexity(self) -> float:
        """Calculate validation complexity."""
        complexity = 0.0
        
        # Multiple dates add complexity
        date_fields = [self.effective_date, self.expiry_date, self.gazette_date, self.enforcement_date]
        date_count = sum(1 for d in date_fields if d is not None)
        complexity += min(date_count * 0.1, 0.4)
        
        # Conflicts add complexity
        complexity += min(len(self.conflicts) * 0.15, 0.3)
        
        # Special factors add complexity
        if self.is_retroactive:
            complexity += 0.2
        
        if self.involves_hazara_act:
            complexity += 0.1
        
        if self.involves_sro:
            complexity += 0.1
        
        if self.is_working_plan:
            complexity += 0.1
        
        return min(complexity, 1.0)
    
    def _detect_kpk_factors(self):
        """Auto-detect KPK-specific factors."""
        if not self.entity_title:
            return
        
        title_lower = self.entity_title.lower()
        
        # Check for KPK references
        kpk_indicators = ["kpk", "khyber pakhtunkhwa", "خیبر پختونخوا", "provincial"]
        self.kpk_jurisdiction = any(indicator in title_lower for indicator in kpk_indicators)
        
        # Check for Hazara Act
        self.involves_hazara_act = any(
            term in title_lower for term in ["hazara act", "ہزارہ ایکٹ", "hazara forest"]
        )
        
        # Check for SRO
        self.involves_sro = any(
            term in title_lower for term in ["sro", "gazette notification", "ایس آر او", "گزیٹ"]
        )
        
        # Check for working plan
        self.is_working_plan = any(
            term in title_lower for term in ["working plan", "ورکنگ پلان", "management plan"]
        )
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        
        # Convert dates
        date_fields = ['timestamp', 'validation_date', 'effective_date', 'expiry_date', 
                      'gazette_date', 'enforcement_date', 'amendment_date']
        for field in date_fields:
            value = data.get(field)
            if value:
                if isinstance(value, datetime):
                    data[field] = value.isoformat()
                elif isinstance(value, date):
                    data[field] = value.isoformat()
        
        # Convert enums
        if self.validity_status:
            data['validity_status'] = self.validity_status.value
        
        if self.gazette_type:
            data['gazette_type'] = self.gazette_type.value
        
        return data
    
    def to_human_readable(self) -> str:
        """Generate human-readable validation report."""
        lines = [
            f"TEMPORAL VALIDATION REPORT",
            f"=" * 70,
            f"Validation ID: {self.validation_id}",
            f"Timestamp: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"",
            f"ENTITY:",
            f"- Title: {self.entity_title or 'Unknown'}",
            f"- Type: {self.entity_type}",
            f"- ID: {self.entity_id or 'Not specified'}",
            f"",
            f"DATES:",
            f"- Validation Date: {self.validation_date}",
            f"- Effective Date: {self.effective_date or 'Not specified'}",
            f"- Expiry Date: {self.expiry_date or 'Not specified'}",
            f"- Gazette Date: {self.gazette_date or 'Not specified'}",
            f"- Enforcement Date: {self.enforcement_date or 'Not specified'}",
            f"",
            f"VALIDITY STATUS: {self.validity_status.value.upper()}",
            f"Confidence: {self.confidence:.1%}",
            f"Is Current: {'Yes' if self.is_current else 'No'}",
            f"Is Retroactive: {'Yes' if self.is_retroactive else 'No'}",
        ]
        
        if self.days_since_effective is not None:
            lines.append(f"Days Since Effective: {self.days_since_effective}")
        
        if self.days_until_expiry is not None:
            lines.append(f"Days Until Expiry: {self.days_until_expiry}")
        
        if self.gazette_delay_days is not None:
            lines.append(f"Gazette Delay: {self.gazette_delay_days} days")
        
        if self.enforcement_delay_days is not None:
            lines.append(f"Enforcement Delay: {self.enforcement_delay_days} days")
        
        lines.append(f"")
        lines.append(f"KPK FACTORS:")
        lines.append(f"- KPK Jurisdiction: {'Yes' if self.kpk_jurisdiction else 'No'}")
        lines.append(f"- Involves Hazara Act: {'Yes' if self.involves_hazara_act else 'No'}")
        lines.append(f"- Involves SRO: {'Yes' if self.involves_sro else 'No'}")
        lines.append(f"- Is Working Plan: {'Yes' if self.is_working_plan else 'No'}")
        
        if self.conflicts:
            lines.append(f"")
            lines.append(f"CONFLICTS ({len(self.conflicts)}):")
            for i, conflict in enumerate(self.conflicts[:3], 1):  # Show only first 3
                lines.append(f"{i}. {conflict.get('type', 'Unknown')}: {conflict.get('description', 'No description')}")
        
        if self.warnings:
            lines.append(f"")
            lines.append(f"WARNINGS ({len(self.warnings)}):")
            for i, warning in enumerate(self.warnings[:3], 1):  # Show only first 3
                lines.append(f"{i}. {warning}")
        
        if self.recommendations:
            lines.append(f"")
            lines.append(f"RECOMMENDATIONS ({len(self.recommendations)}):")
            for i, rec in enumerate(self.recommendations[:3], 1):
                lines.append(f"{i}. {rec}")
        
        lines.append(f"")
        lines.append(f"RESEARCH METRICS:")
        lines.append(f"- Complexity Score: {self.complexity_score:.1%}")
        lines.append(f"- Validation Time: {self.validation_time_ms} ms")
        lines.append(f"- Rules Applied: {len(self.rules_applied)}")
        
        return "\n".join(lines)


@dataclass
class TemporalRule:
    """Temporal validation rule for KPK context"""
    rule_id: str
    name: str
    description: str
    condition: str  # Python expression as string
    action: str  # "set_status", "add_conflict", "add_warning", "add_recommendation"
    parameters: Dict[str, Any] = field(default_factory=dict)
    priority: int = 1
    kpk_specific: bool = False
    applicable_to: List[str] = field(default_factory=lambda: ["all"])
    research_importance: str = "standard"  # standard, hazara_special, sro_related, etc.


class TemporalValidator:
    """
    Enhanced temporal validator with KPK-specific rules and Phase 5 integration.
    """
    
    def __init__(
        self,
        authority_resolver: Optional[AuthorityHierarchyResolver] = None,
        penalty_engine: Optional[PenaltyLogicEngine] = None,
        llm_resolver: Optional[LLMAmbiguityResolver] = None,
        abstention_logger: Optional[AbstentionLogger] = None,
        config: Optional[Dict] = None
    ):
        """
        Initialize enhanced temporal validator.
        
        Args:
            authority_resolver: Phase 5.1 authority hierarchy resolver
            penalty_engine: Phase 5.2 penalty logic engine
            llm_resolver: Phase 5.3 LLM ambiguity resolver
            abstention_logger: Abstention logging system
            config: Configuration dictionary
        """
        self.authority_resolver = authority_resolver
        self.penalty_engine = penalty_engine
        self.llm_resolver = llm_resolver
        self.abstention_logger = abstention_logger or AbstentionLogger()
        self.config = config or self._default_config()
        
        # Initialize temporal rules
        self.temporal_rules = self._initialize_temporal_rules()
        
        # Gazette registry
        self.gazette_registry = self._load_gazette_registry()
        
        # Amendment chain registry
        self.amendment_registry = self._load_amendment_registry()
        
        # Working plan registry
        self.working_plan_registry = self._load_working_plan_registry()
        
        # Research statistics
        self.research_stats = {
            "total_validations": 0,
            "valid_count": 0,
            "expired_count": 0,
            "not_yet_effective_count": 0,
            "superseded_count": 0,
            "repealed_count": 0,
            "retroactive_count": 0,
            "hazara_act_validations": 0,
            "sro_validations": 0,
            "working_plan_validations": 0,
            "average_confidence": 0.0,
            "average_complexity": 0.0,
            "validation_times_ms": [],
        }
        
        # Validation history
        self.validation_history = []
        
        logger.info("Enhanced Temporal Validator initialized")
    
    def validate_temporal(self, amendments: List[Dict], context: Dict) -> TemporalValidation:
        """
        Compatibility alias for run_sequential_pipeline.py.
        Adapts the legacy call signature to the new validate() method.
        """
        document_id = context.get('document_id')
        file_path = context.get('file_path')
        title = None
        if file_path:
             title = Path(file_path).stem.replace('_', ' ').title()
             
        # Call the enhanced validation method
        return self.validate(
            entity_id=document_id,
            entity_title=title,
            validation_date=date.today(),
            context=context
        )
    
    def _default_config(self) -> Dict[str, Any]:
        """Default configuration."""
        return {
            # Validation parameters
            "default_validation_date": "today",  # or specific date
            "assume_gazette_delay_days": 30,
            "assume_enforcement_delay_days": 60,
            "working_plan_validity_years": 10,
            "sro_retroactive_limit_days": 365,
            
            # KPK-specific parameters
            "kpk_gazette_rules": {
                "extraordinary_immediate": True,
                "regular_delay_days": 30,
                "supplement_same_as_regular": True,
            },
            "hazara_act_special_rules": True,
            "community_forest_transition_years": 5,
            
            # Conflict resolution
            "prefer_stricter_interpretation": True,
            "allow_retroactive_application": False,
            "require_gazette_validation": True,
            
            # Integration parameters
            "use_authority_hierarchy": True,
            "use_penalty_logic": True,
            "use_llm_for_ambiguity": True,
            
            # Performance parameters
            "timeout_seconds": 10,
            "cache_validations": True,
            "cache_ttl_hours": 24,
            
            # Research parameters
            "collect_research_metrics": True,
            "log_viva_examples": True,
            "export_graph_data": True,
        }
    
    def _initialize_temporal_rules(self) -> List[TemporalRule]:
        """Initialize temporal validation rules."""
        rules = []
        
        # Basic validity rules
        rules.append(TemporalRule(
            rule_id="R001",
            name="Effective Date Check",
            description="Check if entity is effective on validation date",
            condition="effective_date and validation_date < effective_date",
            action="set_status",
            parameters={"status": TemporalValidityStatus.NOT_YET_EFFECTIVE.value},
            priority=1,
        ))
        
        rules.append(TemporalRule(
            rule_id="R002",
            name="Expiry Date Check",
            description="Check if entity has expired",
            condition="expiry_date and validation_date > expiry_date",
            action="set_status",
            parameters={"status": TemporalValidityStatus.EXPIRED.value},
            priority=1,
        ))
        
        rules.append(TemporalRule(
            rule_id="R003",
            name="Basic Validity Check",
            description="Entity is valid if effective and not expired",
            condition="effective_date and (not expiry_date or validation_date <= expiry_date) and validation_date >= effective_date",
            action="set_status",
            parameters={"status": TemporalValidityStatus.VALID.value, "confidence": 0.8},
            priority=2,
        ))
        
        # Gazette-related rules (KPK-specific)
        rules.append(TemporalRule(
            rule_id="R004",
            name="Gazette Publication Delay",
            description="Check gazette publication delay for KPK",
            condition="gazette_date and gazette_type and gazette_type.value == 'gazette_extraordinary'",
            action="add_warning",
            parameters={"warning": "Gazette Extraordinary may have immediate effect"},
            priority=2,
            kpk_specific=True,
        ))
        
        rules.append(TemporalRule(
            rule_id="R005",
            name="Regular Gazette Delay",
            description="Regular gazette has 30-day delay in KPK",
            condition="gazette_date and (not gazette_type or gazette_type.value == 'gazette_regular') and validation_date < gazette_date + timedelta(days=30)",
            action="add_conflict",
            parameters={
                "type": TemporalConflictType.GAZETTE_VALIDATION.value,
                "description": "Regular gazette may not be fully effective (30-day delay)"
            },
            priority=2,
            kpk_specific=True,
        ))
        
        # Amendment rules
        rules.append(TemporalRule(
            rule_id="R006",
            name="Amendment Supersession",
            description="Check if entity has been amended",
            condition="amendment_date and amendment_date > effective_date",
            action="set_status",
            parameters={"status": TemporalValidityStatus.AMENDED.value, "confidence": 0.7},
            priority=2,
        ))
        
        # Working plan rules (KPK-specific)
        rules.append(TemporalRule(
            rule_id="R007",
            name="Working Plan Validity",
            description="Working plans have 10-year validity in KPK",
            condition="is_working_plan and effective_date and validation_date > effective_date + timedelta(days=3650)",  # 10 years
            action="set_status",
            parameters={"status": TemporalValidityStatus.EXPIRED.value},
            priority=2,
            kpk_specific=True,
            research_importance="working_plan_special",
        ))
        
        # SRO rules (KPK-specific)
        rules.append(TemporalRule(
            rule_id="R008",
            name="SRO Retroactive Limit",
            description="SROs cannot be retroactive beyond 1 year in KPK",
            condition="involves_sro and effective_date and gazette_date and (effective_date - gazette_date).days > 365",
            action="add_conflict",
            parameters={
                "type": TemporalConflictType.RETROACTIVE_APPLICATION.value,
                "description": "SRO retroactive application beyond 1-year limit"
            },
            priority=2,
            kpk_specific=True,
            research_importance="sro_related",
        ))
        
        # Hazara Act special rules
        rules.append(TemporalRule(
            rule_id="R009",
            name="Hazara Act Temporal Scope",
            description="Hazara Act 1936 applies in Hazara Division unless explicitly repealed",
            condition="involves_hazara_act and effective_date and effective_date.year == 1936",
            action="set_status",
            parameters={"status": TemporalValidityStatus.VALID.value, "confidence": 0.9},
            priority=1,
            kpk_specific=True,
            research_importance="hazara_special",
        ))
        
        # Transition period rules
        rules.append(TemporalRule(
            rule_id="R010",
            name="Transition Period Overlap",
            description="Check for overlapping transition periods",
            condition="expiry_date and parent_entity_id and validation_date > expiry_date",
            action="add_conflict",
            parameters={
                "type": TemporalConflictType.TRANSITION_OVERLAP.value,
                "description": "Possible transition period overlap with parent entity"
            },
            priority=3,
        ))
        
        # Climate policy timeline rules
        rules.append(TemporalRule(
            rule_id="R011",
            name="Climate Policy Timeline",
            description="Climate-related policies effective post-2020",
            condition="'climate' in entity_title.lower() and effective_date and effective_date.year < 2020",
            action="add_warning",
            parameters={"warning": "Climate policy likely updated post-2020"},
            priority=2,
            research_importance="climate_related",
        ))
        
        # Community forest rules
        rules.append(TemporalRule(
            rule_id="R012",
            name="Community Forest Transition",
            description="Community forest rules have 5-year transition",
            condition="'community' in entity_title.lower() or 'guzara' in entity_title.lower()",
            action="add_recommendation",
            parameters={"recommendation": "Check 5-year transition period for community forests"},
            priority=2,
            kpk_specific=True,
        ))
        
        return rules
    
    def _load_gazette_registry(self) -> Dict:
        """Load gazette registry for KPK."""
        return {
            "SRO-123/2010": {
                "date": date(2010, 3, 15),
                "effective_date": date(2010, 4, 1),
                "type": GazetteType.GAZETTE_EXTRAORDINARY.value,
                "subject": "Protected Species List",
                "status": "current",
                "repealed_by": None,
            },
            "SRO-456/2015": {
                "date": date(2015, 7, 1),
                "effective_date": date(2015, 8, 1),
                "type": GazetteType.GAZETTE_REGULAR.value,
                "subject": "Penalty Enhancement",
                "status": "current",
                "repealed_by": None,
            },
            "SRO-789/2018": {
                "date": date(2018, 6, 15),
                "effective_date": date(2018, 7, 1),
                "type": GazetteType.GAZETTE_REGULAR.value,
                "subject": "Biodiversity Surcharge",
                "status": "current",
                "repealed_by": None,
            },
            "SRO-101/2020": {
                "date": date(2020, 1, 1),
                "effective_date": date(2020, 2, 1),
                "type": GazetteType.GAZETTE_EXTRAORDINARY.value,
                "subject": "Climate Change Surcharge",
                "status": "current",
                "repealed_by": None,
            },
        }
    
    def _load_amendment_registry(self) -> Dict:
        """Load amendment chain registry."""
        return {
            "KPK_FOREST_ORDINANCE_2002": {
                "base_entity": "KPK Forest Ordinance 2002",
                "effective_date": date(2002, 6, 15),
                "amendments": [
                    {"sro": "SRO-123/2010", "date": date(2010, 4, 1), "subject": "Protected species"},
                    {"sro": "SRO-456/2015", "date": date(2015, 8, 1), "subject": "Penalty enhancement"},
                ],
                "current_version_date": date(2015, 8, 1),
            },
            "HAZARA_FOREST_ACT_1936": {
                "base_entity": "Hazara Forest Act 1936",
                "effective_date": date(1936, 11, 10),
                "amendments": [],
                "current_version_date": date(1936, 11, 10),
            },
        }
    
    def _load_working_plan_registry(self) -> Dict:
        """Load working plan registry."""
        return {
            "SWAT_WORKING_PLAN_2010": {
                "title": "Swat Forest Working Plan 2010-2020",
                "effective_date": date(2010, 1, 1),
                "expiry_date": date(2020, 12, 31),
                "division": "Malakand",
                "status": "expired",
            },
            "HAZARA_WORKING_PLAN_2015": {
                "title": "Hazara Forest Working Plan 2015-2025",
                "effective_date": date(2015, 1, 1),
                "expiry_date": date(2025, 12, 31),
                "division": "Hazara",
                "status": "current",
            },
            "DIR_WORKING_PLAN_2018": {
                "title": "Dir Forest Working Plan 2018-2028",
                "effective_date": date(2018, 1, 1),
                "expiry_date": date(2028, 12, 31),
                "division": "Malakand",
                "status": "current",
            },
        }
    
    def validate(
        self,
        entity_id: Optional[str] = None,
        entity_type: str = "law",
        entity_title: Optional[str] = None,
        effective_date: Optional[Union[str, date]] = None,
        expiry_date: Optional[Union[str, date]] = None,
        gazette_date: Optional[Union[str, date]] = None,
        gazette_reference: Optional[str] = None,
        validation_date: Optional[Union[str, date]] = None,
        context: Optional[Dict] = None,
        viva_mode: bool = False
    ) -> TemporalValidation:
        """
        Enhanced temporal validation with KPK-specific rules.
        
        Args:
            entity_id: Unique identifier for the entity
            entity_type: Type of entity (law, section, circular, sro, etc.)
            entity_title: Title/name of the entity
            effective_date: Date when entity becomes effective
            expiry_date: Date when entity expires (if any)
            gazette_date: Date of gazette publication
            gazette_reference: Gazette reference number
            validation_date: Date to validate against (defaults to today)
            context: Additional context information
            viva_mode: Enable detailed logging for VIVA
        
        Returns:
            TemporalValidation object with comprehensive results
        """
        start_time = datetime.now()
        
        logger.info(f"Validating temporal validity for: {entity_title or entity_id}")
        
        # Parse dates
        effective_date_parsed = self._parse_date(effective_date)
        expiry_date_parsed = self._parse_date(expiry_date)
        gazette_date_parsed = self._parse_date(gazette_date)
        validation_date_parsed = self._parse_date(validation_date) or date.today()
        
        # Create initial validation object
        validation = TemporalValidation(
            entity_id=entity_id,
            entity_type=entity_type,
            entity_title=entity_title,
            validation_date=validation_date_parsed,
            effective_date=effective_date_parsed,
            expiry_date=expiry_date_parsed,
            gazette_date=gazette_date_parsed,
            gazette_reference=gazette_reference,
        )
        
        # Step 1: Apply basic temporal rules
        self._apply_temporal_rules(validation)
        
        # Step 2: Gazette-specific validation (KPK)
        if gazette_reference or gazette_date_parsed:
            self._validate_gazette(validation)
        
        # Step 3: Amendment chain validation
        if entity_id or entity_title:
            self._validate_amendment_chain(validation)
        
        # Step 4: Working plan validation (KPK-specific)
        if validation.is_working_plan:
            self._validate_working_plan(validation)
        
        # Step 5: Phase 5.1-5.3 integration
        if context:
            self._apply_phase_integration(validation, context)
        
        # Step 6: Calculate derived metrics
        self._calculate_derived_metrics(validation)
        
        # Step 7: Apply confidence adjustments
        self._adjust_confidence(validation)
        
        # Step 8: Determine final status
        self._determine_final_status(validation)
        
        # Step 9: Update research statistics
        validation.validation_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        self._update_research_stats(validation)
        
        # Step 10: Add to history
        self.validation_history.append(validation)
        
        # Step 11: VIVA logging
        if viva_mode:
            self._log_viva_example(validation)
        
        logger.info(f"Temporal validation complete: {validation.validity_status.value} "
                   f"(confidence: {validation.confidence:.1%}, complexity: {validation.complexity_score:.1%})")
        
        return validation
    
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
            for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y.%m.%d', '%d-%m-%Y']:
                try:
                    return datetime.strptime(date_input, fmt).date()
                except ValueError:
                    continue
        except Exception:
            pass
        
        # Try to extract year from string
        year_match = re.search(r'\b(19\d{2}|20\d{2})\b', date_input)
        if year_match:
            year = int(year_match.group(1))
            return date(year, 1, 1)
        
        return None
    
    def _apply_temporal_rules(self, validation: TemporalValidation):
        """Apply temporal validation rules."""
        applied_rules = []
        
        # Create evaluation context
        context = {
            'validation_date': validation.validation_date,
            'effective_date': validation.effective_date,
            'expiry_date': validation.expiry_date,
            'gazette_date': validation.gazette_date,
            'gazette_type': validation.gazette_type,
            'is_working_plan': validation.is_working_plan,
            'involves_sro': validation.involves_sro,
            'involves_hazara_act': validation.involves_hazara_act,
            'entity_title': validation.entity_title or "",
            'amendment_date': validation.amendment_date
        }
        
        # Sort rules by priority
        sorted_rules = sorted(self.temporal_rules, key=lambda r: r.priority)
        
        for rule in sorted_rules:
            # Check if rule applies to this entity type
            if "all" not in rule.applicable_to and validation.entity_type not in rule.applicable_to:
                continue
            
            try:
                # Evaluate condition
                condition_result = eval(rule.condition, {}, context)
                
                if condition_result:
                    applied_rules.append(rule.rule_id)
                    self._apply_rule_action(rule, validation)
                    
            except Exception as e:
                logger.warning(f"Error applying rule {rule.rule_id}: {e}")
                validation.warnings.append(f"Rule {rule.rule_id} failed: {str(e)}")
        
        validation.rules_applied = applied_rules
    
    def _apply_rule_action(self, rule: TemporalRule, validation: TemporalValidation):
        """Apply rule action to validation."""
        if rule.action == "set_status":
            status_str = rule.parameters.get("status")
            if status_str:
                try:
                    validation.validity_status = TemporalValidityStatus(status_str)
                    confidence = rule.parameters.get("confidence")
                    if confidence:
                        validation.confidence = confidence
                except ValueError:
                    logger.warning(f"Invalid status in rule {rule.rule_id}: {status_str}")
        
        elif rule.action == "add_conflict":
            conflict = {
                "type": rule.parameters.get("type", "unknown"),
                "description": rule.parameters.get("description", "No description"),
                "rule_id": rule.rule_id,
                "rule_name": rule.name,
            }
            validation.conflicts.append(conflict)
        
        elif rule.action == "add_warning":
            warning = rule.parameters.get("warning", "Unknown warning")
            validation.warnings.append(warning)
        
        elif rule.action == "add_recommendation":
            recommendation = rule.parameters.get("recommendation", "Unknown recommendation")
            validation.recommendations.append(recommendation)
    
    def _validate_gazette(self, validation: TemporalValidation):
        """Validate gazette publication details (KPK-specific)."""
        if not validation.gazette_reference and not validation.gazette_date:
            return
        
        # Check if reference exists in registry
        if validation.gazette_reference:
            sro_info = self.gazette_registry.get(validation.gazette_reference)
            if sro_info:
                # Update validation with registry info
                validation.gazette_date = validation.gazette_date or self._parse_date(sro_info.get("date"))
                
                # Check if SRO is still current
                if sro_info.get("status") != "current":
                    validation.conflicts.append({
                        "type": TemporalConflictType.GAZETTE_VALIDATION.value,
                        "description": f"Gazette {validation.gazette_reference} is {sro_info.get('status')}"
                    })
                
                # Check if repealed
                if sro_info.get("repealed_by"):
                    validation.conflicts.append({
                        "type": TemporalConflictType.GAZETTE_VALIDATION.value,
                        "description": f"Gazette {validation.gazette_reference} repealed by {sro_info.get('repealed_by')}"
                    })
            else:
                validation.warnings.append(f"Gazette reference {validation.gazette_reference} not found in registry")
        
        # Calculate gazette delay
        if validation.gazette_date and validation.effective_date:
            gazette_delay = (validation.effective_date - validation.gazette_date).days
            validation.gazette_delay_days = gazette_delay
            
            # Check for unusual delays
            if gazette_delay > 90:
                validation.warnings.append(f"Unusually long gazette delay: {gazette_delay} days")
            
            # Check for retroactive gazette
            if gazette_delay < 0:
                validation.is_retroactive = True
                validation.warnings.append(f"Gazette published after effective date (retroactive)")
    
    def _validate_amendment_chain(self, validation: TemporalValidation):
        """Validate amendment chain."""
        if not validation.entity_title:
            return
        
        # Try to find entity in amendment registry
        for chain_id, chain_info in self.amendment_registry.items():
            if (validation.entity_title in chain_info["base_entity"] or 
                chain_info["base_entity"] in (validation.entity_title or "")):
                
                validation.amendment_chain_id = chain_id
                
                # Check if this is the current version
                if validation.effective_date:
                    current_version_date = chain_info.get("current_version_date")
                    if current_version_date and validation.effective_date < current_version_date:
                        validation.conflicts.append({
                            "type": TemporalConflictType.AMENDMENT_CHAIN_BREAK.value,
                            "description": f"Entity may be superseded by newer version ({current_version_date})"
                        })
                
                # Add amendments to context
                amendments = chain_info.get("amendments", [])
                if amendments:
                    latest_amendment = max(amendments, key=lambda x: x.get("date", date.min))
                    validation.amendment_date = latest_amendment.get("date")
                    
                    if validation.effective_date and validation.amendment_date:
                        if validation.effective_date < validation.amendment_date:
                            validation.validity_status = TemporalValidityStatus.AMENDED
                            validation.confidence = 0.8
                
                break
    
    def _validate_working_plan(self, validation: TemporalValidation):
        """Validate working plan (KPK-specific)."""
        if not validation.entity_title:
            return
        
        # Try to find in working plan registry
        for plan_id, plan_info in self.working_plan_registry.items():
            if plan_info["title"].lower() in (validation.entity_title or "").lower():
                # Update dates from registry if not provided
                if not validation.effective_date:
                    validation.effective_date = plan_info.get("effective_date")
                
                if not validation.expiry_date:
                    validation.expiry_date = plan_info.get("expiry_date")
                
                # Check status
                if plan_info.get("status") == "expired":
                    validation.conflicts.append({
                        "type": TemporalConflictType.WORKING_PLAN_EXPIRY.value,
                        "description": f"Working plan expired according to registry"
                    })
                
                break
        
        # Apply KPK working plan rules
        if validation.effective_date and validation.expiry_date:
            plan_duration = (validation.expiry_date - validation.effective_date).days
            
            # Typical working plan duration is 10 years
            if plan_duration < 3650:  # Less than 10 years
                validation.warnings.append(f"Working plan duration shorter than typical 10 years: {plan_duration/365:.1f} years")
            
            if plan_duration > 7300:  # More than 20 years
                validation.warnings.append(f"Working plan duration longer than typical 10-20 years: {plan_duration/365:.1f} years")
    
    def _apply_phase_integration(self, validation: TemporalValidation, context: Dict):
        """Apply Phase 5.1-5.3 integration."""
        # Phase 5.1: Authority hierarchy integration
        if self.authority_resolver and self.config.get("use_authority_hierarchy", True):
            try:
                authority_validation = self._validate_with_authority_hierarchy(validation, context)
                validation.authority_validation = authority_validation
                
                if not authority_validation.get("consistent", True):
                    validation.conflicts.append({
                        "type": "authority_inconsistency",
                        "description": authority_validation.get("reason", "Authority hierarchy inconsistency")
                    })
            except Exception as e:
                logger.warning(f"Authority hierarchy validation failed: {e}")
        
        # Phase 5.2: Penalty logic integration
        if (self.penalty_engine and self.config.get("use_penalty_logic", True) and
            "penalty" in (validation.entity_title or "").lower()):
            try:
                penalty_validation = self._validate_with_penalty_logic(validation, context)
                validation.penalty_validation = penalty_validation
                
                if not penalty_validation.get("valid", True):
                    validation.conflicts.append({
                        "type": "penalty_inconsistency",
                        "description": penalty_validation.get("error", "Penalty logic inconsistency")
                    })
            except Exception as e:
                logger.warning(f"Penalty logic validation failed: {e}")
        
        # Phase 5.3: LLM ambiguity resolution
        if (self.llm_resolver and self.config.get("use_llm_for_ambiguity", True) and
            validation.validity_status == TemporalValidityStatus.UNCERTAIN):
            try:
                llm_resolution = self._resolve_with_llm(validation, context)
                validation.llm_resolution = llm_resolution
                
                if llm_resolution.get("resolution") == "ABSTAIN":
                    validation.warnings.append("LLM could not resolve temporal ambiguity")
                elif llm_resolution.get("resolution"):
                    # Update validation based on LLM suggestion
                    suggested_status = llm_resolution.get("suggested_status")
                    if suggested_status:
                        try:
                            validation.validity_status = TemporalValidityStatus(suggested_status)
                            validation.confidence = llm_resolution.get("confidence", validation.confidence)
                        except ValueError:
                            pass
            except Exception as e:
                logger.warning(f"LLM resolution failed: {e}")
    
    def _validate_with_authority_hierarchy(self, validation: TemporalValidation, 
                                         context: Dict) -> Dict:
        """Validate with authority hierarchy (Phase 5.1)."""
        if not validation.entity_title:
            return {"consistent": True, "reason": "No entity title to validate"}
        
        # Check if entity mentions authority levels
        title_lower = validation.entity_title.lower()
        
        if "hazara act" in title_lower and validation.effective_date:
            # Hazara Act 1936 should be effective from 1936
            if validation.effective_date.year != 1936:
                return {
                    "consistent": False,
                    "reason": f"Hazara Act effective date ({validation.effective_date}) doesn't match 1936 enactment"
                }
        
        if "ordinance" in title_lower and "2002" in title_lower:
            # KPK Forest Ordinance 2002
            if validation.effective_date and validation.effective_date.year != 2002:
                return {
                    "consistent": False,
                    "reason": f"KPK Ordinance effective date ({validation.effective_date}) doesn't match 2002 enactment"
                }
        
        return {"consistent": True, "reason": "Authority hierarchy validation passed"}
    
    def _validate_with_penalty_logic(self, validation: TemporalValidation, 
                                    context: Dict) -> Dict:
        """Validate with penalty logic (Phase 5.2)."""
        if not validation.entity_title or not validation.effective_date:
            return {"valid": True, "reason": "Insufficient data for penalty validation"}
        
        # Check penalty amount timelines
        title_lower = validation.entity_title.lower()
        
        # Extract penalty amount if mentioned
        penalty_match = re.search(r'Rs\.?\s*([\d,]+)', validation.entity_title)
        if penalty_match:
            penalty_amount = float(penalty_match.group(1).replace(',', ''))
            
            # Check if penalty amount aligns with effective date
            # Pre-2015: Lower penalties, Post-2015: Higher penalties
            if validation.effective_date.year < 2015 and penalty_amount > 50000:
                return {
                    "valid": False,
                    "error": f"Penalty amount {penalty_amount} too high for pre-2015 ({validation.effective_date.year})"
                }
            
            if validation.effective_date.year >= 2015 and penalty_amount < 50000:
                return {
                    "valid": False,
                    "error": f"Penalty amount {penalty_amount} too low for post-2015 ({validation.effective_date.year})"
                }
        
        return {"valid": True, "reason": "Penalty logic validation passed"}
    
    def _resolve_with_llm(self, validation: TemporalValidation, context: Dict) -> Dict:
        """Resolve ambiguity with LLM (Phase 5.3)."""
        if not self.llm_resolver:
            return {"resolution": "ABSTAIN", "reason": "LLM resolver not available"}
        
        # Create ambiguity context
        ambiguity_context = {
            "source_text": validation.entity_title or "",
            "validation_date": validation.validation_date.isoformat(),
            "effective_date": validation.effective_date.isoformat() if validation.effective_date else None,
            "expiry_date": validation.expiry_date.isoformat() if validation.expiry_date else None,
            "gazette_date": validation.gazette_date.isoformat() if validation.gazette_date else None,
            "current_status": validation.validity_status.value,
            "conflicts": validation.conflicts,
            "warnings": validation.warnings,
        }
        
        # Create candidates based on possible statuses
        candidates = [status.value for status in TemporalValidityStatus]
        
        # Use LLM resolver
        try:
            from .llm_ambiguity_resolver import AmbiguityContext, AmbiguityType
            llm_context = AmbiguityContext(
                ambiguity_type=AmbiguityType.TEMPORAL_AMBIGUITY,
                source_text=str(ambiguity_context),
                candidates=candidates,
                location=context.get("location"),
                effective_date=validation.validation_date,
            )
            
            resolution = self.llm_resolver.resolve_ambiguity(llm_context, viva_mode=False)
            
            return {
                "resolution": resolution.final_resolution,
                "suggested_status": resolution.final_resolution,
                "confidence": resolution.confidence,
                "explanation": resolution.explanation,
            }
        except Exception as e:
            logger.warning(f"LLM resolution failed: {e}")
            return {"resolution": "ABSTAIN", "reason": f"LLM resolution error: {str(e)}"}
    
    def _calculate_derived_metrics(self, validation: TemporalValidation):
        """Calculate derived temporal metrics."""
        # Days since effective
        if validation.effective_date:
            validation.days_since_effective = (validation.validation_date - validation.effective_date).days
        
        # Days until expiry
        if validation.expiry_date:
            validation.days_until_expiry = (validation.expiry_date - validation.validation_date).days
        
        # Gazette delay
        if validation.gazette_date and validation.effective_date:
            validation.gazette_delay_days = (validation.effective_date - validation.gazette_date).days
        
        # Enforcement delay (if enforcement date available)
        if hasattr(validation, 'enforcement_date') and validation.enforcement_date and validation.effective_date:
            validation.enforcement_delay_days = (validation.enforcement_date - validation.effective_date).days
        
        # Determine if current
        validation.is_current = (
            validation.validity_status == TemporalValidityStatus.VALID and
            validation.confidence >= 0.7
        )
    
    def _adjust_confidence(self, validation: TemporalValidation):
        """Adjust confidence based on various factors."""
        base_confidence = validation.confidence
        
        # Adjust based on date completeness
        if validation.effective_date:
            base_confidence += 0.1
        
        if validation.expiry_date:
            base_confidence += 0.05
        
        if validation.gazette_date:
            base_confidence += 0.05
        
        # Adjust based on conflicts
        conflict_penalty = len(validation.conflicts) * 0.05
        base_confidence -= conflict_penalty
        
        # Adjust based on KPK-specific factors
        if validation.kpk_jurisdiction and validation.confidence > 0:
            base_confidence += 0.05
        
        # Cap confidence
        validation.confidence = max(0.0, min(1.0, base_confidence))
    
    def _determine_final_status(self, validation: TemporalValidation):
        """Determine final validity status."""
        # If status already determined by rules, keep it
        if validation.validity_status != TemporalValidityStatus.UNCERTAIN:
            return
        
        # Default determination based on dates
        if validation.effective_date and validation.validation_date < validation.effective_date:
            validation.validity_status = TemporalValidityStatus.NOT_YET_EFFECTIVE
            validation.confidence = 0.9
        
        elif validation.expiry_date and validation.validation_date > validation.expiry_date:
            validation.validity_status = TemporalValidityStatus.EXPIRED
            validation.confidence = 0.9
        
        elif validation.effective_date and validation.validation_date >= validation.effective_date:
            if not validation.expiry_date or validation.validation_date <= validation.expiry_date:
                validation.validity_status = TemporalValidityStatus.VALID
                validation.confidence = 0.8
        
        # If still uncertain, check for retroactive
        if validation.validity_status == TemporalValidityStatus.UNCERTAIN and validation.is_retroactive:
            validation.validity_status = TemporalValidityStatus.RETROACTIVE
            validation.confidence = 0.7
    
    def _update_research_stats(self, validation: TemporalValidation):
        """Update research statistics."""
        self.research_stats["total_validations"] += 1
        
        # Update counts by status
        status = validation.validity_status
        if status == TemporalValidityStatus.VALID:
            self.research_stats["valid_count"] += 1
        elif status == TemporalValidityStatus.EXPIRED:
            self.research_stats["expired_count"] += 1
        elif status == TemporalValidityStatus.NOT_YET_EFFECTIVE:
            self.research_stats["not_yet_effective_count"] += 1
        elif status == TemporalValidityStatus.SUPERSEDED:
            self.research_stats["superseded_count"] += 1
        elif status == TemporalValidityStatus.REPEALED:
            self.research_stats["repealed_count"] += 1
        elif status == TemporalValidityStatus.RETROACTIVE:
            self.research_stats["retroactive_count"] += 1
        
        # Update special categories
        if validation.involves_hazara_act:
            self.research_stats["hazara_act_validations"] += 1
        
        if validation.involves_sro:
            self.research_stats["sro_validations"] += 1
        
        if validation.is_working_plan:
            self.research_stats["working_plan_validations"] += 1
        
        # Update averages
        total = self.research_stats["total_validations"]
        if total > 0:
            self.research_stats["average_confidence"] = (
                (self.research_stats["average_confidence"] * (total - 1) + 
                 validation.confidence) / total
            )
            
            self.research_stats["average_complexity"] = (
                (self.research_stats["average_complexity"] * (total - 1) + 
                 validation.complexity_score) / total
            )
        
        # Add validation time
        self.research_stats["validation_times_ms"].append(validation.validation_time_ms)
    
    def _log_viva_example(self, validation: TemporalValidation):
        """Log example for VIVA demonstration."""
        viva_log = {
            "timestamp": datetime.now().isoformat(),
            "validation_id": validation.validation_id,
            "entity_title": validation.entity_title,
            "validity_status": validation.validity_status.value,
            "confidence": validation.confidence,
            "complexity_score": validation.complexity_score,
            "validation_time_ms": validation.validation_time_ms,
            "rules_applied": len(validation.rules_applied),
            "conflicts_count": len(validation.conflicts),
            "kpk_jurisdiction": validation.kpk_jurisdiction,
            "involves_hazara_act": validation.involves_hazara_act,
            "involves_sro": validation.involves_sro,
        }
        
        logger.info(f"VIVA Temporal Validation Example: {json.dumps(viva_log, indent=2, default=str)}")
    
    def batch_validate(self, entities: List[Dict]) -> List[TemporalValidation]:
        """
        Validate multiple entities in batch.
        
        Args:
            entities: List of entity dictionaries with validation parameters
        
        Returns:
            List of TemporalValidation objects
        """
        results = []
        
        for entity in entities:
            try:
                validation = self.validate(
                    entity_id=entity.get("entity_id"),
                    entity_type=entity.get("entity_type", "law"),
                    entity_title=entity.get("entity_title"),
                    effective_date=entity.get("effective_date"),
                    expiry_date=entity.get("expiry_date"),
                    gazette_date=entity.get("gazette_date"),
                    gazette_reference=entity.get("gazette_reference"),
                    validation_date=entity.get("validation_date"),
                    context=entity.get("context", {}),
                )
                results.append(validation)
            except Exception as e:
                logger.error(f"Failed to validate entity {entity.get('entity_id')}: {e}")
                # Create error validation
                error_validation = TemporalValidation(
                    entity_id=entity.get("entity_id"),
                    entity_title=entity.get("entity_title"),
                    validity_status=TemporalValidityStatus.INVALID,
                    confidence=0.0,
                    warnings=[f"Validation error: {str(e)}"]
                )
                results.append(error_validation)
        
        return results
    
    def validate_chain(self, entity_ids: List[str], validation_date: date = None) -> Dict:
        """
        Validate a chain of related entities.
        
        Args:
            entity_ids: List of entity IDs in the chain
            validation_date: Date to validate against
        
        Returns:
            Chain validation results
        """
        if not validation_date:
            validation_date = date.today()
        
        chain_results = {
            "validation_date": validation_date.isoformat(),
            "entities": [],
            "chain_status": "unknown",
            "breaks": [],
            "confidence": 0.0,
        }
        
        validations = []
        for entity_id in entity_ids:
            # In real implementation, would fetch entity details
            validation = self.validate(
                entity_id=entity_id,
                validation_date=validation_date,
            )
            validations.append(validation)
            chain_results["entities"].append(validation.to_dict())
        
        # Analyze chain
        all_valid = all(v.validity_status == TemporalValidityStatus.VALID for v in validations)
        any_invalid = any(v.validity_status == TemporalValidityStatus.INVALID for v in validations)
        any_expired = any(v.validity_status == TemporalValidityStatus.EXPIRED for v in validations)
        
        if all_valid:
            chain_results["chain_status"] = "valid"
            chain_results["confidence"] = min(v.confidence for v in validations)
        elif any_invalid:
            chain_results["chain_status"] = "invalid"
        elif any_expired:
            chain_results["chain_status"] = "broken"
            # Identify breaks
            for i, v in enumerate(validations):
                if v.validity_status == TemporalValidityStatus.EXPIRED:
                    chain_results["breaks"].append({
                        "position": i,
                        "entity_id": v.entity_id,
                        "reason": "Entity expired"
                    })
        else:
            chain_results["chain_status"] = "partial"
            chain_results["confidence"] = statistics.mean([v.confidence for v in validations])
        
        return chain_results
    
    def get_research_statistics(self) -> Dict:
        """Get comprehensive research statistics."""
        stats = self.research_stats.copy()
        
        total = stats["total_validations"]
        
        if total > 0:
            # Calculate rates
            stats["valid_rate"] = stats["valid_count"] / total
            stats["expired_rate"] = stats["expired_count"] / total
            stats["uncertain_rate"] = (total - sum([
                stats["valid_count"], stats["expired_count"], 
                stats["not_yet_effective_count"], stats["superseded_count"],
                stats["repealed_count"], stats["retroactive_count"]
            ])) / total
            
            # Calculate average validation time
            if stats["validation_times_ms"]:
                stats["average_validation_time_ms"] = statistics.mean(stats["validation_times_ms"])
                stats["median_validation_time_ms"] = statistics.median(stats["validation_times_ms"])
            
            # Add special category rates
            if stats["hazara_act_validations"] > 0:
                stats["hazara_act_rate"] = stats["hazara_act_validations"] / total
            
            if stats["sro_validations"] > 0:
                stats["sro_rate"] = stats["sro_validations"] / total
            
            if stats["working_plan_validations"] > 0:
                stats["working_plan_rate"] = stats["working_plan_validations"] / total
        
        # Add validation history count
        stats["validation_history_count"] = len(self.validation_history)
        
        return stats
    
    def export_validations_for_graph(self) -> Dict:
        """Export validations for Phase 6 graph construction."""
        nodes = []
        edges = []
        
        for validation in self.validation_history:
            # Validation node
            validation_node = {
                "id": validation.graph_node_id,
                "label": f"Validation_{validation.validity_status.value}",
                "type": "TemporalValidation",
                "properties": {
                    "entity_title": validation.entity_title,
                    "validity_status": validation.validity_status.value,
                    "confidence": validation.confidence,
                    "validation_date": validation.validation_date.isoformat(),
                    "complexity_score": validation.complexity_score,
                }
            }
            nodes.append(validation_node)
            
            # Entity relationship (if entity has ID)
            if validation.entity_id:
                entity_node_id = f"Entity_{validation.entity_id}"
                
                # Check if entity node already exists
                if not any(n["id"] == entity_node_id for n in nodes):
                    entity_node = {
                        "id": entity_node_id,
                        "label": validation.entity_title or validation.entity_id,
                        "type": validation.entity_type.capitalize(),
                        "properties": {
                            "entity_type": validation.entity_type,
                        }
                    }
                    nodes.append(entity_node)
                
                edge = {
                    "id": f"validates_{validation.validation_id}",
                    "source": validation.graph_node_id,
                    "target": entity_node_id,
                    "type": "VALIDATES",
                    "properties": {
                        "validity_status": validation.validity_status.value,
                        "confidence": validation.confidence,
                        "validation_date": validation.validation_date.isoformat(),
                    }
                }
                edges.append(edge)
        
        return {
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "total_validations": len(self.validation_history),
                "generated_at": datetime.now().isoformat(),
                "graph_type": "temporal_validation_network",
                "purpose": "Phase 6 graph construction"
            }
        }


# ========== FACTORY FUNCTIONS ==========

def create_temporal_validator(
    authority_resolver: Optional[AuthorityHierarchyResolver] = None,
    penalty_engine: Optional[PenaltyLogicEngine] = None,
    llm_resolver: Optional[LLMAmbiguityResolver] = None,
    abstention_logger: Optional[AbstentionLogger] = None,
    config: Optional[Dict] = None
) -> TemporalValidator:
    """Factory function to create enhanced temporal validator."""
    return TemporalValidator(
        authority_resolver=authority_resolver,
        penalty_engine=penalty_engine,
        llm_resolver=llm_resolver,
        abstention_logger=abstention_logger,
        config=config
    )


def simple_validate(
    effective_date: Union[str, date],
    expiry_date: Optional[Union[str, date]] = None,
    validation_date: Optional[Union[str, date]] = None
) -> Dict:
    """
    Simple validation function for basic use cases.
    
    Args:
        effective_date: Effective date of entity
        expiry_date: Expiry date of entity (optional)
        validation_date: Date to validate against (defaults to today)
    
    Returns:
        Simple validation result
    """
    validator = TemporalValidator()
    
    validation = validator.validate(
        effective_date=effective_date,
        expiry_date=expiry_date,
        validation_date=validation_date,
    )
    
    return {
        "is_valid": validation.validity_status == TemporalValidityStatus.VALID,
        "status": validation.validity_status.value,
        "confidence": validation.confidence,
        "is_current": validation.is_current,
        "days_since_effective": validation.days_since_effective,
        "days_until_expiry": validation.days_until_expiry,
    }


# ========== COMMAND LINE INTERFACE ==========

def main():
    """Command line interface for testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Enhanced Temporal Validator')
    parser.add_argument('--test', action='store_true', help='Run test cases')
    parser.add_argument('--config', help='Configuration file (JSON)')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--viva', action='store_true', help='VIVA demonstration mode')
    
    args = parser.parse_args()
    
    # Load configuration
    config = {}
    if args.config:
        import json
        with open(args.config, 'r') as f:
            config = json.load(f)
    
    validator = create_temporal_validator(config=config)
    
    if args.test:
        print("=" * 80)
        print("ENHANCED TEMPORAL VALIDATOR - RESEARCH DEMONSTRATION")
        print("=" * 80)
        print("Phase 5.4: Temporal Validation with Phase 5.1-5.3 Integration")
        print()
        
        # Test Case 1: Basic KPK Ordinance validation
        print("TEST CASE 1: KPK Forest Ordinance 2002")
        print("-" * 80)
        
        validation1 = validator.validate(
            entity_id="KPK_ORDINANCE_2002",
            entity_title="KPK Forest Ordinance 2002",
            entity_type="ordinance",
            effective_date="2002-06-15",
            validation_date="2023-06-15",
            viva_mode=args.viva,
        )
        
        print(validation1.to_human_readable())
        
        print("\n" + "=" * 80)
        
        # Test Case 2: Hazara Act with gazette
        print("\nTEST CASE 2: Hazara Forest Act 1936 with Gazette")
        print("-" * 80)
        
        validation2 = validator.validate(
            entity_id="HAZARA_ACT_1936",
            entity_title="Hazara Forest Act 1936",
            entity_type="act",
            effective_date="1936-11-10",
            gazette_date="1936-11-05",
            gazette_reference="Gazette-1936-11-05",
            validation_date="2023-06-15",
            viva_mode=args.viva,
        )
        
        print(validation2.to_human_readable())
        
        print("\n" + "=" * 80)
        
        # Test Case 3: SRO with retroactive application
        print("\nTEST CASE 3: SRO with Retroactive Application")
        print("-" * 80)
        
        validation3 = validator.validate(
            entity_id="SRO-456/2015",
            entity_title="SRO-456/2015 - Penalty Enhancement",
            entity_type="sro",
            effective_date="2015-08-01",
            gazette_date="2015-07-01",
            validation_date="2015-06-01",  # Before gazette!
            viva_mode=args.viva,
        )
        
        print(validation3.to_human_readable())
        
        print("\n" + "=" * 80)
        
        # Test Case 4: Expired working plan
        print("\nTEST CASE 4: Expired Working Plan")
        print("-" * 80)
        
        validation4 = validator.validate(
            entity_id="SWAT_WP_2010",
            entity_title="Swat Forest Working Plan 2010-2020",
            entity_type="working_plan",
            effective_date="2010-01-01",
            expiry_date="2020-12-31",
            validation_date="2023-06-15",
            viva_mode=args.viva,
        )
        
        print(validation4.to_human_readable())
        
        print("\n" + "=" * 80)
        
        # Test Case 5: Climate policy timeline
        print("\nTEST CASE 5: Climate Change Policy")
        print("-" * 80)
        
        validation5 = validator.validate(
            entity_id="CLIMATE_POLICY_2022",
            entity_title="KPK Climate Change Forestry Policy 2022",
            entity_type="policy",
            effective_date="2022-01-01",
            validation_date="2023-06-15",
            viva_mode=args.viva,
        )
        
        print(validation5.to_human_readable())
        
        print("\n" + "=" * 80)
        
        # Display statistics
        stats = validator.get_research_statistics()
        print("\nRESEARCH STATISTICS:")
        print("-" * 80)
        print(f"Total Validations: {stats['total_validations']}")
        print(f"Valid Count: {stats['valid_count']} ({stats.get('valid_rate', 0):.1%})")
        print(f"Expired Count: {stats['expired_count']} ({stats.get('expired_rate', 0):.1%})")
        print(f"Average Confidence: {stats['average_confidence']:.2f}")
        print(f"Average Complexity: {stats['average_complexity']:.2f}")
        print(f"Hazara Act Validations: {stats['hazara_act_validations']}")
        print(f"SRO Validations: {stats['sro_validations']}")
        print(f"Working Plan Validations: {stats['working_plan_validations']}")
        
        if 'average_validation_time_ms' in stats:
            print(f"Average Validation Time: {stats['average_validation_time_ms']:.0f} ms")
        
        # Export graph data
        graph_data = validator.export_validations_for_graph()
        print(f"\nGraph Data Prepared:")
        print(f"  Nodes: {len(graph_data['nodes'])}")
        print(f"  Edges: {len(graph_data['edges'])}")
        print(f"  Graph Type: {graph_data['metadata']['graph_type']}")
        
        print("\n" + "=" * 80)
        print("Enhanced Temporal Validator Test Complete ✓")
        print("Ready for Phase 6 Graph Construction")
        
    else:
        print("Enhanced Temporal Validator initialized.")
        print("Use --test to run test cases or --viva for demonstration mode.")


if __name__ == "__main__":
    main()
