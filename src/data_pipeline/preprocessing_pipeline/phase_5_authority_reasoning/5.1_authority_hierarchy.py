"""
authority_hierarchy.py
===========================================================
KPK LEGAL AUTHORITY HIERARCHY RESOLUTION ENGINE - ENHANCED

Core Module for Phase 5: Temporal & Authority Resolution

ENHANCEMENTS:
1. ✅ Direct integration with Phase 4 (amendment_tracker.py, citation_resolver.py)
2. ✅ Enhanced abstention logging for VIVA/Research demonstration
3. ✅ Connection to Phase 6 graph schema for seamless graph construction
4. ✅ Precedence matrix for KPK-specific conflicts
5. ✅ Retroactive application handling (special for legal systems)
6. ✅ Gazette publication date validation

Key Philosophy Maintained:
- LLM only suggests, Rules decide
- System knows when it doesn't know
- Deterministic resolution for legal certainty
"""

import re
import json
import logging
from typing import Dict, List, Tuple, Optional, Union, Any, Set
from dataclasses import dataclass, asdict, field
from enum import Enum, auto
from datetime import datetime, date, timedelta
from collections import defaultdict, OrderedDict
import hashlib
from pathlib import Path
import pickle

# Import from your pipeline (adjust paths as needed)
try:
    from ..phase_4_legal_extraction.amendment_tracker import AmendmentChain
    from ..phase_4_legal_extraction.citation_resolver import CitationResolver
    from ..common.config import KPK_FORESTRY_CONFIG
    from ..phase_0_foundation.abstention_log import AbstentionLogger
except ImportError:
    # Fallback for standalone testing
    class AmendmentChain:
        pass
    class CitationResolver:
        pass
    class AbstentionLogger:
        def log_abstention(self, *args, **kwargs):
            pass
    KPK_FORESTRY_CONFIG = {}

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class AuthorityLevel(Enum):
    """
    KPK-specific legal authority hierarchy.
    Lower number = Higher authority.
    """
    # Constitutional level (supreme)
    CONSTITUTION = 1
    
    # Federal level
    FEDERAL_ACT = 2
    FEDERAL_ORDINANCE = 3
    FEDERAL_RULES = 4
    
    # Provincial level (KPK)
    KPK_ORDINANCE = 5          # KPK Forest Ordinance 2002 (The MAIN law)
    KPK_ACT = 6                # Provincial Acts (e.g., KPK Wildlife Act)
    KPK_RULES = 7              # KPK Forest Rules 2004
    
    # Regional level (Hazara special case - IMPORTANT for research)
    HAZARA_ACT = 8             # Hazara Forest Act 1936 (special regional law)
    REGIONAL_REGULATION = 9    # Malakand Regulations etc.
    
    # Notification level (SROs are critical for temporal tracking)
    GAZETTE_NOTIFICATION = 10  # SROs (Statutory Regulatory Orders)
    OFFICIAL_GAZETTE = 11      # Regular gazette publications
    
    # Department level (Forest Department hierarchy)
    DEPARTMENT_CIRCULAR = 12   # Forest Department Circulars
    DEPARTMENT_ORDER = 13      # Secretary/DG orders
    POLICY_GUIDELINE = 14      # Policy documents
    
    # Operational level (Field implementation)
    WORKING_PLAN = 15          # Forest Working Plans (10-20 year plans)
    MANAGEMENT_PLAN = 16       # Short-term management plans
    OPERATIONAL_GUIDE = 17     # Field guides
    
    # Officer level (Hierarchy within department)
    DIVISIONAL_ORDER = 18      # DFO (Divisional Forest Officer) Orders
    RANGE_ORDER = 19           # RFO (Range Forest Officer) Orders
    BLOCK_ORDER = 20           # Block Officer orders
    
    # Local level (Community/Customary)
    LOCAL_CUSTOM = 21          # Local customs/traditions (riaaj)
    COMMUNITY_AGREEMENT = 22   # Jirga/Community agreements
    
    # Special categories for your research
    AMENDMENT = 90             # Amendment documents
    REPEALED = 91              # Repealed laws (for historical tracking)
    DRAFT = 92                 # Draft/Proposed laws
    JUDGEMENT = 93             # Court judgements (if included)
    
    # Unknown/ambiguous
    UNKNOWN = 99
    CONFLICTING = 100          # When authorities directly conflict
    
    @classmethod
    def from_string(cls, authority_str: str) -> 'AuthorityLevel':
        """Convert string to AuthorityLevel with enhanced detection."""
        authority_lower = authority_str.lower().strip()
        
        # Remove common prefixes/suffixes
        authority_lower = re.sub(r'^the\s+', '', authority_lower)
        authority_lower = re.sub(r'\s+act$', '', authority_lower)
        authority_lower = re.sub(r'\s+ordinance$', '', authority_lower)
        authority_lower = authority_lower.replace(' ', '_').replace('-', '_')
        
        mapping = {
            # Constitutional
            'constitution': cls.CONSTITUTION,
            'دستور': cls.CONSTITUTION,
            'دستور_پاکستان': cls.CONSTITUTION,
            
            # Federal
            'federal_act': cls.FEDERAL_ACT,
            'federal_ordinance': cls.FEDERAL_ORDINANCE,
            'federal_rules': cls.FEDERAL_RULES,
            'وفاقی_ایکٹ': cls.FEDERAL_ACT,
            'مرکزی_ایکٹ': cls.FEDERAL_ACT,
            'پاکستان_ایکٹ': cls.FEDERAL_ACT,
            
            # Provincial (KPK)
            'kpk_ordinance': cls.KPK_ORDINANCE,
            'kp_ordinance': cls.KPK_ORDINANCE,
            'khyber_pakhtunkhwa_ordinance': cls.KPK_ORDINANCE,
            'kpk_act': cls.KPK_ACT,
            'kpk_rules': cls.KPK_RULES,
            'خیبر_پختونخوا_آرڈیننس': cls.KPK_ORDINANCE,
            'صوبائی_آرڈیننس': cls.KPK_ORDINANCE,
            'خیبر_پختونخوا_قواعد': cls.KPK_RULES,
            
            # Regional (Hazara) - RESEARCH FOCUS
            'hazara_act': cls.HAZARA_ACT,
            'hazara_forest_act': cls.HAZARA_ACT,
            'regional_regulation': cls.REGIONAL_REGULATION,
            'ہزارہ_ایکٹ': cls.HAZARA_ACT,
            'ہزارہ_فاریسٹ_ایکٹ': cls.HAZARA_ACT,
            'علاقائی_قانون': cls.REGIONAL_REGULATION,
            'مالاکنڈ_ریگولیشن': cls.REGIONAL_REGULATION,
            
            # Gazette (SROs) - CRITICAL for temporal
            'gazette_notification': cls.GAZETTE_NOTIFICATION,
            'sro': cls.GAZETTE_NOTIFICATION,
            'statutory_regulatory_order': cls.GAZETTE_NOTIFICATION,
            'official_gazette': cls.OFFICIAL_GAZETTE,
            'ایس_آر_او': cls.GAZETTE_NOTIFICATION,
            'گزیٹ': cls.OFFICIAL_GAZETTE,
            'سرکاری_گزیٹ': cls.OFFICIAL_GAZETTE,
            
            # Department
            'department_circular': cls.DEPARTMENT_CIRCULAR,
            'circular': cls.DEPARTMENT_CIRCULAR,
            'department_order': cls.DEPARTMENT_ORDER,
            'policy_guideline': cls.POLICY_GUIDELINE,
            'policy': cls.POLICY_GUIDELINE,
            'سرکلر': cls.DEPARTMENT_CIRCULAR,
            'محکمانہ_حکم': cls.DEPARTMENT_ORDER,
            'پالیسی': cls.POLICY_GUIDELINE,
            
            # Operational
            'working_plan': cls.WORKING_PLAN,
            'management_plan': cls.MANAGEMENT_PLAN,
            'operational_guide': cls.OPERATIONAL_GUIDE,
            'ورکنگ_پلان': cls.WORKING_PLAN,
            'منیجمنٹ_پلان': cls.MANAGEMENT_PLAN,
            'آپریشنل_گائیڈ': cls.OPERATIONAL_GUIDE,
            
            # Officer
            'divisional_order': cls.DIVISIONAL_ORDER,
            'dfo_order': cls.DIVISIONAL_ORDER,
            'range_order': cls.RANGE_ORDER,
            'rfo_order': cls.RANGE_ORDER,
            'block_order': cls.BLOCK_ORDER,
            'ڈی_ایف_او_حکم': cls.DIVISIONAL_ORDER,
            'آر_ایف_او_حکم': cls.RANGE_ORDER,
            
            # Local
            'local_custom': cls.LOCAL_CUSTOM,
            'custom': cls.LOCAL_CUSTOM,
            'community_agreement': cls.COMMUNITY_AGREEMENT,
            'jirga_decision': cls.COMMUNITY_AGREEMENT,
            'مقامی_رواج': cls.LOCAL_CUSTOM,
            'رواج': cls.LOCAL_CUSTOM,
            'اجتماعی_معاہدہ': cls.COMMUNITY_AGREEMENT,
            'جرگہ_فیصلہ': cls.COMMUNITY_AGREEMENT,
            
            # Special categories
            'amendment': cls.AMENDMENT,
            'repealed': cls.REPEALED,
            'draft': cls.DRAFT,
            'judgement': cls.JUDGEMENT,
            'court_case': cls.JUDGEMENT,
            'ترمیم': cls.AMENDMENT,
            'منسوخ': cls.REPEALED,
            'مسودہ': cls.DRAFT,
            'فیصلہ': cls.JUDGEMENT,
        }
        
        # Try exact match first
        if authority_lower in mapping:
            return mapping[authority_lower]
        
        # Try partial matches (for research flexibility)
        for key, value in mapping.items():
            if key in authority_lower or authority_lower in key:
                return value
        
        # Try to infer from common patterns
        if 'sro' in authority_lower or 'notification' in authority_lower:
            return cls.GAZETTE_NOTIFICATION
        elif 'circular' in authority_lower or 'سرکلر' in authority_lower:
            return cls.DEPARTMENT_CIRCULAR
        elif 'ordinance' in authority_lower or 'آرڈیننس' in authority_lower:
            return cls.KPK_ORDINANCE
        elif 'act' in authority_lower or 'ایکٹ' in authority_lower:
            # Check if it's Hazara Act specifically
            if 'hazara' in authority_lower or 'ہزارہ' in authority_lower:
                return cls.HAZARA_ACT
            return cls.FEDERAL_ACT
        
        return cls.UNKNOWN
    
    def get_rank(self) -> int:
        """Get numerical rank (lower = higher authority)."""
        return self.value
    
    def is_higher_than(self, other: 'AuthorityLevel') -> bool:
        """Check if this authority is higher than another."""
        return self.get_rank() < other.get_rank()
    
    def is_lower_than(self, other: 'AuthorityLevel') -> bool:
        """Check if this authority is lower than another."""
        return self.get_rank() > other.get_rank()
    
    def can_override(self, other: 'AuthorityLevel') -> bool:
        """
        Check if this authority level can override another.
        Some special rules apply in KPK context.
        """
        # Same level cannot override each other (needs temporal check)
        if self == other:
            return False
        
        # Hazara Act special case: Overrides KPK Ordinance in Hazara region
        if self == AuthorityLevel.HAZARA_ACT and other == AuthorityLevel.KPK_ORDINANCE:
            return True  # Special regional law takes precedence in its region
        
        # Federal always overrides provincial
        if self.value <= 4 and other.value >= 5:  # Federal vs Provincial
            return True
        
        # Standard hierarchy check
        return self.is_higher_than(other)
    
    def get_hierarchy_name(self) -> str:
        """Get human-readable hierarchy level."""
        hierarchy_names = {
            self.CONSTITUTION: "Constitutional Law",
            self.FEDERAL_ACT: "Federal Act",
            self.FEDERAL_ORDINANCE: "Federal Ordinance",
            self.FEDERAL_RULES: "Federal Rules",
            self.KPK_ORDINANCE: "KPK Forest Ordinance",
            self.KPK_ACT: "KPK Act",
            self.KPK_RULES: "KPK Forest Rules",
            self.HAZARA_ACT: "Hazara Forest Act (Special Regional)",
            self.REGIONAL_REGULATION: "Regional Regulation",
            self.GAZETTE_NOTIFICATION: "Gazette Notification (SRO)",
            self.OFFICIAL_GAZETTE: "Official Gazette",
            self.DEPARTMENT_CIRCULAR: "Department Circular",
            self.DEPARTMENT_ORDER: "Department Order",
            self.POLICY_GUIDELINE: "Policy Guideline",
            self.WORKING_PLAN: "Working Plan",
            self.MANAGEMENT_PLAN: "Management Plan",
            self.OPERATIONAL_GUIDE: "Operational Guide",
            self.DIVISIONAL_ORDER: "Divisional Order (DFO)",
            self.RANGE_ORDER: "Range Order (RFO)",
            self.BLOCK_ORDER: "Block Order",
            self.LOCAL_CUSTOM: "Local Custom (Riaaj)",
            self.COMMUNITY_AGREEMENT: "Community Agreement (Jirga)",
            self.AMENDMENT: "Amendment Document",
            self.REPEALED: "Repealed Law",
            self.DRAFT: "Draft/Proposed Law",
            self.JUDGEMENT: "Court Judgement",
            self.UNKNOWN: "Unknown Authority",
            self.CONFLICTING: "Conflicting Authority"
        }
        return hierarchy_names.get(self, "Unknown Authority")


class JurisdictionLevel(Enum):
    """KPK jurisdiction levels (geographical hierarchy)."""
    FEDERAL = 1          # Entire Pakistan
    PROVINCIAL = 2       # Khyber Pakhtunkhwa province
    DIVISION = 3         # Malakand, Hazara, Peshawar, etc.
    DISTRICT = 4         # Swat, Dir, Mansehra, etc.
    TEHSIL = 5           # Sub-district level
    UNION_COUNCIL = 6    # Local government
    FOREST_COMPARTMENT = 7  # Specific forest area
    PROTECTED_AREA = 8   # National Park, Wildlife Sanctuary
    COMMUNITY_FOREST = 9 # Guzara/Community forest
    UNKNOWN = 99


@dataclass
class LegalSource:
    """
    Enhanced LegalSource with Phase 4 integration.
    Connects to amendment tracking and citation resolution.
    """
    # Core identification
    title: str
    authority_level: AuthorityLevel
    jurisdiction: JurisdictionLevel
    short_title: Optional[str] = None
    document_id: Optional[str] = None  # From Phase 0.1 doc_profiler
    jurisdiction_details: Dict[str, Any] = field(default_factory=dict)
    
    # Temporal metadata (CRITICAL for your research)
    effective_date: Optional[date] = None
    expiry_date: Optional[date] = None
    gazette_date: Optional[date] = None  # When published in gazette
    enforcement_date: Optional[date] = None  # When actually enforced
    
    # Integration with Phase 4
    amendment_chain_id: Optional[str] = None  # Link to AmendmentChain
    parent_document_id: Optional[str] = None  # If this amends another
    citation_references: List[str] = field(default_factory=list)  # From citation_resolver
    
    # Source quality (from Phase 0.4)
    confidence: float = 1.0
    quality_score: float = 1.0
    is_current: bool = True
    is_verified: bool = False
    
    # Gazette/reference info
    gazette_reference: Optional[str] = None
    gazette_number: Optional[str] = None
    gazette_page: Optional[str] = None
    
    # KPK-specific
    kpk_division: Optional[str] = None
    kpk_district: Optional[str] = None
    forest_type: Optional[str] = None  # Reserved, Protected, Guzara, etc.
    
    # For graph construction (Phase 6)
    node_id: Optional[str] = None  # Will be used in Neo4j
    
    # Content (optional, for reference)
    key_provisions: List[str] = field(default_factory=list)
    penalties: List[Dict] = field(default_factory=list)
    species_mentioned: List[str] = field(default_factory=list)
    
    # Metadata
    version: str = "1.0"
    amendments: List[Dict] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        # Generate document_id if not provided
        if not self.document_id and self.title:
            # Create deterministic ID from title and date
            title_hash = hashlib.md5(self.title.encode()).hexdigest()[:8]
            date_str = self.effective_date.strftime('%Y%m%d') if self.effective_date else 'nodate'
            self.document_id = f"KPK_{title_hash}_{date_str}"
        
        # Generate node_id for graph (Phase 6)
        if not self.node_id and self.document_id:
            self.node_id = f"LegalSource_{self.document_id}"
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        
        # Convert dates to strings
        date_fields = ['effective_date', 'expiry_date', 'gazette_date', 'enforcement_date', 'last_updated']
        for field in date_fields:
            value = getattr(self, field)
            if value:
                if isinstance(value, datetime):
                    data[field] = value.isoformat()
                elif isinstance(value, date):
                    data[field] = value.isoformat()
        
        # Convert enums to their values
        if self.authority_level:
            data['authority_level'] = self.authority_level.value
        if self.jurisdiction:
            data['jurisdiction'] = self.jurisdiction.value
        
        return data
    
    def is_valid_on(self, target_date: date) -> bool:
        """
        Enhanced validity check with gazette date consideration.
        In KPK, laws often published in gazette before becoming effective.
        """
        # Not valid if target date before effective date
        if self.effective_date and target_date < self.effective_date:
            return False
        
        # Not valid if target date after expiry date
        if self.expiry_date and target_date > self.expiry_date:
            return False
        
        # Special case: If gazette date exists but no enforcement date,
        # assume 30 days after gazette for effectiveness
        if self.gazette_date and not self.enforcement_date:
            enforcement_date = self.gazette_date + timedelta(days=30)
            if target_date < enforcement_date:
                return False
        
        return True
    
    def has_temporal_conflict_with(self, other: 'LegalSource') -> bool:
        """Check if two sources are temporally conflicting."""
        # If either has no dates, assume no temporal conflict
        if not self.effective_date or not other.effective_date:
            return False
        
        # If both have same effective date, they might conflict
        if self.effective_date == other.effective_date:
            return True
        
        # Check if validity periods overlap
        self_end = self.expiry_date or date(2100, 12, 31)  # Far future if no expiry
        other_end = other.expiry_date or date(2100, 12, 31)
        
        latest_start = max(self.effective_date, other.effective_date)
        earliest_end = min(self_end, other_end)
        
        return latest_start <= earliest_end
    
    def get_temporal_relationship(self, other: 'LegalSource') -> str:
        """Describe temporal relationship between two sources."""
        if not self.effective_date or not other.effective_date:
            return "unknown_temporal_relationship"
        
        if self.effective_date < other.effective_date:
            return "precedes"
        elif self.effective_date > other.effective_date:
            return "succeeds"
        else:
            return "contemporaneous"


@dataclass
class AuthorityConflict:
    """
    Enhanced conflict representation with research tracking.
    """
    entity: str
    conflicting_sources: List[LegalSource]
    conflict_type: str  # 'hierarchy', 'temporal', 'jurisdiction', 'substantive', 'procedural'
    conflict_details: Dict[str, Any]
    conflict_id: str = field(default_factory=lambda: f"conflict_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hashlib.md5(str(datetime.now()).encode()).hexdigest()[:6]}")
    
    # Resolution tracking
    detected_at: datetime = field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None
    resolution: Optional[Dict] = None
    resolution_method: Optional[str] = None
    
    # Research metrics
    complexity_score: float = 0.0  # 0-1 scale
    involves_hazara_act: bool = False
    involves_sro: bool = False
    is_cross_jurisdictional: bool = False
    
    # For VIVA demonstration
    viva_example: bool = False
    viva_notes: Optional[str] = None
    
    def __post_init__(self):
        # Auto-calculate some metrics
        self.complexity_score = self._calculate_complexity()
        self.involves_hazara_act = any(
            s.authority_level == AuthorityLevel.HAZARA_ACT 
            for s in self.conflicting_sources
        )
        self.involves_sro = any(
            s.authority_level == AuthorityLevel.GAZETTE_NOTIFICATION
            for s in self.conflicting_sources
        )
        
        # Check if cross-jurisdictional
        jurisdictions = set(s.jurisdiction for s in self.conflicting_sources)
        self.is_cross_jurisdictional = len(jurisdictions) > 1
    
    def _calculate_complexity(self) -> float:
        """Calculate conflict complexity score."""
        score = 0.0
        
        # More sources = more complex
        score += min(len(self.conflicting_sources) * 0.1, 0.3)
        
        # More authority levels involved = more complex
        authority_levels = set(s.authority_level for s in self.conflicting_sources)
        score += min(len(authority_levels) * 0.15, 0.4)
        
        # Temporal complexity
        dates_present = sum(1 for s in self.conflicting_sources if s.effective_date)
        if dates_present >= 2:
            score += 0.2
        
        # Special KPK factors
        if self.involves_hazara_act:
            score += 0.1
        if self.involves_sro:
            score += 0.1
        
        return min(score, 1.0)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary with enhanced details."""
        data = asdict(self)
        
        # Convert dates
        data['detected_at'] = self.detected_at.isoformat()
        if self.resolved_at:
            data['resolved_at'] = self.resolved_at.isoformat()
        
        # Convert sources
        data['conflicting_sources'] = [s.to_dict() for s in self.conflicting_sources]
        
        return data


@dataclass
class ResolutionResult:
    """
    Enhanced resolution result with research metrics.
    """
    entity: str
    selected_source: Optional[LegalSource]
    resolution_method: str
    applied_rules: List[str]
    confidence: float
    rule_descriptions: List[str] = field(default_factory=list)
    resolution_id: str = field(default_factory=lambda: f"res_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hashlib.md5(str(datetime.now()).encode()).hexdigest()[:6]}")
    
    # Confidence metrics
    confidence_breakdown: Dict[str, float] = field(default_factory=dict)
    
    # Abstention tracking (VIVA ready)
    abstention_reason: Optional[str] = None
    abstention_category: Optional[str] = None  # 'temporal', 'jurisdictional', 'substantive', 'procedural'
    
    # Warnings and alternatives
    warnings: List[str] = field(default_factory=list)
    alternatives: List[LegalSource] = field(default_factory=list)
    overridden_sources: List[LegalSource] = field(default_factory=list)
    
    # Research metrics
    resolution_time_ms: int = 0
    rules_considered: int = 0
    rules_applied: int = 0
    temporal_factors: List[str] = field(default_factory=list)
    jurisdictional_factors: List[str] = field(default_factory=list)
    
    # For Phase 6 graph construction
    graph_node_id: Optional[str] = None
    graph_relationship_type: Optional[str] = None
    
    # For Phase 7 quality gates
    passed_quality_gates: List[str] = field(default_factory=list)
    failed_quality_gates: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        # Set graph node ID if source exists
        if self.selected_source and self.selected_source.node_id:
            self.graph_node_id = self.selected_source.node_id
        
        # Default relationship type
        self.graph_relationship_type = "GOVERNED_BY"
    
    def to_dict(self) -> Dict:
        """Convert to dictionary with all details."""
        data = asdict(self)
        
        # Convert sources
        if self.selected_source:
            data['selected_source'] = self.selected_source.to_dict()
        if self.alternatives:
            data['alternatives'] = [s.to_dict() for s in self.alternatives]
        if self.overridden_sources:
            data['overridden_sources'] = [s.to_dict() for s in self.overridden_sources]
        
        # Remove callable fields
        data.pop('__post_init__', None)
        
        return data
    
    def is_abstention(self) -> bool:
        """Check if this result is an abstention."""
        return self.abstention_reason is not None
    
    def get_confidence_level(self) -> str:
        """Get human-readable confidence level."""
        if self.confidence >= 0.9:
            return "Very High"
        elif self.confidence >= 0.7:
            return "High"
        elif self.confidence >= 0.5:
            return "Moderate"
        elif self.confidence >= 0.3:
            return "Low"
        else:
            return "Very Low"


class KPKJurisdictionMapper:
    """
    Enhanced jurisdiction mapper with Phase 3 integration.
    Uses multilingual handling from Phase 3.1.
    """
    
    def __init__(self):
        # KPK administrative hierarchy (detailed for research)
        self.kpk_hierarchy = self._build_kpk_hierarchy()
        
        # Forest types and their legal implications
        self.forest_types = self._build_forest_type_regimes()
        
        # Default authorities for each jurisdiction level
        self.default_authorities = {
            JurisdictionLevel.FEDERAL: AuthorityLevel.FEDERAL_ACT,
            JurisdictionLevel.PROVINCIAL: AuthorityLevel.KPK_ORDINANCE,
            JurisdictionLevel.DIVISION: AuthorityLevel.DEPARTMENT_CIRCULAR,
            JurisdictionLevel.DISTRICT: AuthorityLevel.DIVISIONAL_ORDER,
            JurisdictionLevel.TEHSIL: AuthorityLevel.RANGE_ORDER,
            JurisdictionLevel.UNION_COUNCIL: AuthorityLevel.LOCAL_CUSTOM,
            JurisdictionLevel.FOREST_COMPARTMENT: AuthorityLevel.WORKING_PLAN,
            JurisdictionLevel.PROTECTED_AREA: AuthorityLevel.FEDERAL_ACT,  # Federal laws often govern
            JurisdictionLevel.COMMUNITY_FOREST: AuthorityLevel.COMMUNITY_AGREEMENT,
        }
        
        # Special jurisdiction cases (RESEARCH FOCUS)
        self.special_jurisdictions = {
            # Hazara region - SPECIAL FOR YOUR RESEARCH
            'Hazara': {
                'authority': AuthorityLevel.HAZARA_ACT,
                'divisions': ['Mansehra', 'Abbottabad', 'Haripur', 'Batagram', 'Kohistan'],
                'legal_implications': [
                    "Hazara Act 1936 applies alongside KPK Ordinance",
                    "Special penalties for certain species",
                    "Different forest classification system"
                ],
                'viva_importance': "High - Demonstrates regional law vs provincial law conflict"
            },
            # Malakand region - special regulations
            'Malakand': {
                'authority': AuthorityLevel.REGIONAL_REGULATION,
                'districts': ['Swat', 'Dir', 'Malakand', 'Shangla', 'Buner', 'Charsadda'],
                'legal_implications': [
                    "Special regulations for tourism areas",
                    "Different permit requirements",
                    "Community forest management variations"
                ]
            },
            # Tribal districts (merged areas) - complex jurisdiction
            'Tribal': {
                'authority': AuthorityLevel.FEDERAL_ORDINANCE,
                'districts': ['Bajaur', 'Mohmand', 'Khyber', 'Kurram', 'Orakzai', 
                             'North Waziristan', 'South Waziristan'],
                'legal_implications': [
                    "Transition from FATA to KPK jurisdiction",
                    "Special federal regulations apply",
                    "Different enforcement mechanisms"
                ]
            },
            # Protected Areas - highest conservation status
            'Protected Area': {
                'authority': AuthorityLevel.FEDERAL_ACT,
                'types': ['National Park', 'Wildlife Sanctuary', 'Game Reserve', 'Biosphere Reserve'],
                'legal_implications': [
                    "Highest level of protection",
                    "Federal laws take precedence",
                    "Restricted human activities"
                ]
            }
        }
        
        # Gazette publication tracking
        self.gazette_registry = self._load_gazette_registry()
    
    def _build_kpk_hierarchy(self) -> Dict[str, Any]:
        """Build detailed KPK administrative hierarchy."""
        return {
            'divisions': {
                'Malakand': {
                    'districts': ['Swat', 'Dir', 'Malakand', 'Shangla', 'Buner', 'Charsadda'],
                    'forest_cover': 'High',
                    'major_species': ['Deodar', 'Chir Pine', 'Blue Pine'],
                    'protected_areas': ['Kalam', 'Malam Jabba', 'Miandam'],
                    'authorities': ['DFO Malakand', 'Conservator Malakand']
                },
                'Hazara': {
                    'districts': ['Mansehra', 'Abbottabad', 'Haripur', 'Batagram', 'Kohistan'],
                    'forest_cover': 'Very High',
                    'major_species': ['Deodar', 'Spruce', 'Fir', 'Walnut'],
                    'protected_areas': ['Ayubia National Park', 'Siran Valley', 'Kaghan Valley'],
                    'authorities': ['DFO Hazara', 'Conservator Hazara']
                },
                'Peshawar': {
                    'districts': ['Peshawar', 'Nowshera', 'Mardan', 'Swabi'],
                    'forest_cover': 'Low',
                    'major_species': ['Sheesham', 'Babul', 'Eucalyptus'],
                    'protected_areas': [],
                    'authorities': ['DFO Peshawar', 'Conservator Peshawar']
                },
                'Kohat': {
                    'districts': ['Kohat', 'Hangu', 'Karak'],
                    'forest_cover': 'Medium',
                    'major_species': ['Acacia', 'Wild Olive', 'Pistachio'],
                    'protected_areas': [],
                    'authorities': ['DFO Kohat', 'Conservator Kohat']
                },
                'Bannu': {
                    'districts': ['Bannu', 'Lakki Marwat'],
                    'forest_cover': 'Low',
                    'major_species': ['Acacia', 'Prosopis'],
                    'protected_areas': [],
                    'authorities': ['DFO Bannu', 'Conservator Bannu']
                },
                'Dera Ismail Khan': {
                    'districts': ['Dera Ismail Khan', 'Tank'],
                    'forest_cover': 'Very Low',
                    'major_species': ['Mazri Palm', 'Kandi'],
                    'protected_areas': [],
                    'authorities': ['DFO D.I. Khan', 'Conservator D.I. Khan']
                }
            },
            'protected_areas': {
                'National Parks': [
                    {'name': 'Chitral Gol', 'established': '1984', 'area_hectares': 7750},
                    {'name': 'Ayubia', 'established': '1984', 'area_hectares': 3312},
                    {'name': 'Saiful Muluk', 'established': '2003', 'area_hectares': 4800}
                ],
                'Wildlife Sanctuaries': [
                    {'name': 'Kalam', 'established': '1984', 'area_hectares': 4000},
                    {'name': 'Bishigram', 'established': '1983', 'area_hectares': 405}
                ],
                'Game Reserves': [
                    {'name': 'Siran Valley', 'established': '1975', 'area_hectares': 42000},
                    {'name': 'Kaghan Valley', 'established': '1983', 'area_hectares': 33200}
                ]
            }
        }
    
    def _build_forest_type_regimes(self) -> Dict[str, Dict]:
        """Build forest type legal regimes."""
        return {
            'Reserved Forest': {
                'definition': 'Forests reserved under Section 26 of KPK Forest Ordinance',
                'authority': AuthorityLevel.KPK_ORDINANCE,
                'management': 'Forest Department',
                'restrictions': ['No rights without permission', 'Strict protection'],
                'penalty_multiplier': 2.0  # Higher penalties
            },
            'Protected Forest': {
                'definition': 'Forests protected under Section 29 of KPK Forest Ordinance',
                'authority': AuthorityLevel.KPK_ORDINANCE,
                'management': 'Forest Department with community rights',
                'restrictions': ['Controlled rights', 'Permission required'],
                'penalty_multiplier': 1.5
            },
            'Guzara Forest': {
                'definition': 'Community-owned forests (Guzara means livelihood)',
                'authority': AuthorityLevel.COMMUNITY_AGREEMENT,
                'management': 'Local community with FD oversight',
                'restrictions': ['Community rules apply', 'Limited commercial use'],
                'penalty_multiplier': 1.0
            },
            'Unclassed Forest': {
                'definition': 'Forests not yet classified',
                'authority': AuthorityLevel.LOCAL_CUSTOM,
                'management': 'Mixed',
                'restrictions': ['Varies by location'],
                'penalty_multiplier': 0.5
            }
        }
    
    def _load_gazette_registry(self) -> Dict[str, List]:
        """Load gazette publication registry."""
        # In real implementation, this would load from a database
        # For now, return sample data
        return {
            '2023': [
                {'number': 'SRO-123(I)/2023', 'date': '2023-01-15', 'subject': 'Forest fines revision'},
                {'number': 'SRO-456(I)/2023', 'date': '2023-03-20', 'subject': 'Protected species list'},
            ],
            '2022': [
                {'number': 'SRO-789(I)/2022', 'date': '2022-06-10', 'subject': 'Working plan approval'},
            ]
        }
    
    def map_location(self, location: str) -> Dict[str, Any]:
        """
        Enhanced location mapping with multilingual support.
        
        Args:
            location: Location string (e.g., "Swat, Malakand Division" or "سوات، ملاکنڈ ڈویژن")
            
        Returns:
            Dict with comprehensive jurisdiction details
        """
        # Normalize location (handle Urdu/English mix)
        location_normalized = self._normalize_location_string(location)
        
        result = {
            'input': location,
            'normalized': location_normalized,
            'jurisdiction_level': JurisdictionLevel.UNKNOWN,
            'division': None,
            'district': None,
            'tehsil': None,
            'special_region': None,
            'protected_area': None,
            'forest_type': None,
            'authority_implications': [],
            'legal_regime': 'standard',
            'confidence': 0.0,
            'mapping_method': 'direct_match'
        }
        
        # Check for special regions first
        location_lower = location_normalized.lower()
        
        for region, info in self.special_jurisdictions.items():
            region_lower = region.lower()
            
            # Check region name
            if region_lower in location_lower:
                result['special_region'] = region
                result['legal_regime'] = 'special'
                result['authority_implications'].extend(info.get('legal_implications', []))
                result['confidence'] += 0.3
                
                # Check for districts in this region
                if 'districts' in info:
                    for district in info['districts']:
                        if district.lower() in location_lower:
                            result['district'] = district
                            result['jurisdiction_level'] = JurisdictionLevel.DISTRICT
                            result['confidence'] += 0.2
                            break
                break
        
        # Check divisions and districts
        for division, division_info in self.kpk_hierarchy['divisions'].items():
            division_lower = division.lower()
            
            if division_lower in location_lower:
                result['division'] = division
                if result['jurisdiction_level'] == JurisdictionLevel.UNKNOWN:
                    result['jurisdiction_level'] = JurisdictionLevel.DIVISION
                result['confidence'] += 0.3
                
                # Check districts within division
                districts = division_info['districts']
                for district in districts:
                    if district.lower() in location_lower:
                        result['district'] = district
                        result['jurisdiction_level'] = JurisdictionLevel.DISTRICT
                        result['confidence'] += 0.2
                        
                        # Add forest cover info
                        result['forest_cover'] = division_info.get('forest_cover', 'Unknown')
                        result['major_species'] = division_info.get('major_species', [])
                        break
        
        # Check for protected areas
        for area_type, areas in self.kpk_hierarchy['protected_areas'].items():
            for area_info in areas:
                area_name = area_info['name']
                if area_name.lower() in location_lower:
                    result['protected_area'] = {
                        'name': area_name,
                        'type': area_type,
                        'established': area_info.get('established'),
                        'area_hectares': area_info.get('area_hectares')
                    }
                    result['jurisdiction_level'] = JurisdictionLevel.PROTECTED_AREA
                    result['legal_regime'] = 'protected'
                    result['confidence'] += 0.4
                    
                    result['authority_implications'].append({
                        'type': 'protected_area',
                        'area_type': area_type,
                        'area_name': area_name,
                        'implication': 'Highest protection level applies'
                    })
                    break
        
        # Check for forest types
        for forest_type, regime_info in self.forest_types.items():
            if forest_type.lower() in location_lower:
                result['forest_type'] = forest_type
                result['legal_regime'] = 'forest_specific'
                result['confidence'] += 0.2
                
                result['authority_implications'].append({
                    'type': 'forest_type',
                    'forest_type': forest_type,
                    'definition': regime_info.get('definition'),
                    'penalty_multiplier': regime_info.get('penalty_multiplier')
                })
        
        # Check for tehsil level indicators
        tehsil_indicators = ['tehsil', 'تحصیل', 'taluka', 'تعلقہ']
        for indicator in tehsil_indicators:
            if indicator in location_lower:
                result['jurisdiction_level'] = JurisdictionLevel.TEHSIL
                result['confidence'] += 0.1
                break
        
        # Determine default authority based on jurisdiction level
        if result['jurisdiction_level'] != JurisdictionLevel.UNKNOWN:
            default_auth = self.default_authorities.get(result['jurisdiction_level'])
            if default_auth:
                result['default_authority'] = {
                    'level': default_auth.value,
                    'name': default_auth.name
                }
        
        # If still unknown jurisdiction but has district, assume district level
        if result['jurisdiction_level'] == JurisdictionLevel.UNKNOWN and result['district']:
            result['jurisdiction_level'] = JurisdictionLevel.DISTRICT
            result['confidence'] += 0.1
        
        # Cap confidence at 1.0
        result['confidence'] = min(1.0, result['confidence'])
        
        # Set mapping method
        if result['confidence'] >= 0.7:
            result['mapping_method'] = 'confident_match'
        elif result['confidence'] >= 0.4:
            result['mapping_method'] = 'partial_match'
        else:
            result['mapping_method'] = 'weak_match'
        
        return result
    
    def _normalize_location_string(self, location: str) -> str:
        """Normalize location string for better matching."""
        # Convert to lowercase
        normalized = location.lower()
        
        # Common replacements for multilingual support
        replacements = {
            'division': 'ڈویژن',
            'district': 'ضلع',
            'tehsil': 'تحصیل',
            'union council': 'یونین کونسل',
            'forest': 'جنگل',
            'protected': 'محفوظ',
            'reserved': 'مختص',
            'guzara': 'گزارہ',
            'national park': 'قومی پارک',
            'wildlife sanctuary': 'حیاتیاتی پناہ گاہ'
        }
        
        # Reverse replacements (Urdu to English)
        for eng, urdu in replacements.items():
            if urdu in normalized:
                normalized = normalized.replace(urdu, eng)
        
        # Remove common words that don't affect jurisdiction
        stop_words = ['in', 'near', 'around', 'close to', 'adjacent to', 'area of']
        for word in stop_words:
            normalized = normalized.replace(word, '')
        
        # Clean up extra spaces
        normalized = ' '.join(normalized.split())
        
        return normalized
    
    def get_applicable_authorities(self, location: str, 
                                 target_date: Optional[date] = None,
                                 entity_type: Optional[str] = None) -> List[Dict]:
        """
        Get all authorities that could apply to a location with explanations.
        Enhanced for research clarity.
        """
        jurisdiction_info = self.map_location(location)
        authorities = []
        
        # Always include federal and provincial authorities
        federal_auth = {
            'authority': AuthorityLevel.FEDERAL_ACT,
            'applicability': 'universal',
            'reason': 'Federal laws apply throughout Pakistan',
            'priority': 1
        }
        authorities.append(federal_auth)
        
        provincial_auth = {
            'authority': AuthorityLevel.KPK_ORDINANCE,
            'applicability': 'provincial',
            'reason': 'KPK Forest Ordinance applies throughout Khyber Pakhtunkhwa',
            'priority': 2
        }
        authorities.append(provincial_auth)
        
        # Add default authority for jurisdiction level
        if 'default_authority' in jurisdiction_info:
            default_auth = AuthorityLevel(jurisdiction_info['default_authority']['level'])
            auth_info = {
                'authority': default_auth,
                'applicability': 'jurisdictional',
                'reason': f'Default authority for {jurisdiction_info["jurisdiction_level"].name} level jurisdiction',
                'priority': 3
            }
            authorities.append(auth_info)
        
        # Add special region authorities
        if jurisdiction_info.get('special_region'):
            region = jurisdiction_info['special_region']
            special_auth = self.special_jurisdictions[region]['authority']
            auth_info = {
                'authority': special_auth,
                'applicability': 'special_region',
                'reason': f'Special regional law for {region} region',
                'priority': 2 if region == 'Hazara' else 3  # Hazara Act has higher priority
            }
            authorities.append(auth_info)
        
        # Add protected area authorities
        if jurisdiction_info.get('protected_area'):
            auth_info = {
                'authority': AuthorityLevel.FEDERAL_ACT,
                'applicability': 'protected_area',
                'reason': 'Protected areas governed by federal conservation laws',
                'priority': 1
            }
            authorities.append(auth_info)
        
        # Add forest type specific authorities
        if jurisdiction_info.get('forest_type'):
            forest_type = jurisdiction_info['forest_type']
            if forest_type in self.forest_types:
                auth = self.forest_types[forest_type]['authority']
                auth_info = {
                    'authority': auth,
                    'applicability': 'forest_type',
                    'reason': f'Special regime for {forest_type}',
                    'priority': 4
                }
                authorities.append(auth_info)
        
        # Add lower-level authorities for detailed jurisdiction
        if jurisdiction_info['jurisdiction_level'] in [JurisdictionLevel.DISTRICT, 
                                                      JurisdictionLevel.TEHSIL,
                                                      JurisdictionLevel.UNION_COUNCIL]:
            # Department circulars
            auth_info = {
                'authority': AuthorityLevel.DEPARTMENT_CIRCULAR,
                'applicability': 'administrative',
                'reason': 'Department circulars provide operational guidance',
                'priority': 5
            }
            authorities.append(auth_info)
            
            # Officer orders
            if jurisdiction_info['jurisdiction_level'] == JurisdictionLevel.DISTRICT:
                auth_info = {
                    'authority': AuthorityLevel.DIVISIONAL_ORDER,
                    'applicability': 'district',
                    'reason': 'DFO orders apply at district level',
                    'priority': 6
                }
                authorities.append(auth_info)
            elif jurisdiction_info['jurisdiction_level'] == JurisdictionLevel.TEHSIL:
                auth_info = {
                    'authority': AuthorityLevel.RANGE_ORDER,
                    'applicability': 'tehsil',
                    'reason': 'RFO orders apply at tehsil/range level',
                    'priority': 6
                }
                authorities.append(auth_info)
        
        # Sort by priority (lower number = higher priority)
        authorities.sort(key=lambda x: x['priority'])
        
        return authorities
    
    def validate_gazette_date(self, gazette_ref: str, 
                            purported_date: date) -> Tuple[bool, Optional[date]]:
        """
        Validate if a gazette notification was actually published on given date.
        """
        year = purported_date.year
        year_str = str(year)
        
        if year_str in self.gazette_registry:
            for gazette in self.gazette_registry[year_str]:
                if gazette['number'] == gazette_ref:
                    gazette_date = datetime.strptime(gazette['date'], '%Y-%m-%d').date()
                    return (gazette_date == purported_date, gazette_date)
        
        # If not in registry, we can't validate
        return (False, None)


class AuthorityHierarchyResolver:
    """
    Enhanced resolver with Phase 4 and 6 integration.
    Research-focused with detailed logging for VIVA.
    """
    
    def __init__(self, config: Optional[Any] = None, abstention_logger: Optional[AbstentionLogger] = None):
        self.config = config
        self.jurisdiction_mapper = KPKJurisdictionMapper()
        self.abstention_logger = abstention_logger or AbstentionLogger()
        
        # Initialize Phase 4 components
        self.amendment_tracker = None  # Will be initialized if available
        self.citation_resolver = None  # Will be initialized if available
        
        # Conflict and resolution tracking
        self.conflict_log = []
        self.resolution_history = []
        self.research_metrics = {
            'total_resolutions': 0,
            'successful_resolutions': 0,
            'abstentions': 0,
            'hazara_conflicts': 0,
            'sro_conflicts': 0,
            'cross_jurisdictional': 0,
            'average_confidence': 0.0,
            'total_processing_time_ms': 0
        }
        
        # Initialize resolution rules
        self.resolution_rules = self._initialize_resolution_rules()
        
        # Precedence matrix for KPK-specific conflicts
        self.precedence_matrix = self._build_precedence_matrix()
        
        logger.info("Enhanced AuthorityHierarchyResolver initialized")
    
    def _initialize_resolution_rules(self) -> List[Dict]:
        """Initialize KPK-specific resolution rules with research metrics."""
        return [
            {
                'name': 'federal_supremacy',
                'description': 'Federal laws override all lower laws (Article 142)',
                'function': self._apply_federal_supremacy,
                'priority': 1,
                'applicability': 'always',
                'success_rate': 0.95,
                'viva_example': 'Pakistan Forest Act 1927 vs KPK Ordinance'
            },
            {
                'name': 'constitutional_primacy',
                'description': 'Constitutional provisions override all laws',
                'function': self._apply_constitutional_primacy,
                'priority': 0,  # Highest priority
                'applicability': 'when_constitutional',
                'success_rate': 1.0,
                'viva_example': 'Fundamental rights vs forest restrictions'
            },
            {
                'name': 'lex_posterior',
                'description': 'Later laws override earlier laws (temporal precedence)',
                'function': self._apply_temporal_precedence,
                'priority': 2,
                'applicability': 'when_dates_available',
                'success_rate': 0.85,
                'requires': ['effective_date', 'gazette_date']
            },
            {
                'name': 'lex_specialis',
                'description': 'Special laws override general laws (Hazara Act special case)',
                'function': self._apply_special_over_general,
                'priority': 3,
                'applicability': 'when_special_law_exists',
                'success_rate': 0.8,
                'viva_example': 'Hazara Act 1936 vs KPK Ordinance 2002 in Hazara'
            },
            {
                'name': 'hierarchy_principle',
                'description': 'Higher authority overrides lower authority',
                'function': self._apply_hierarchy_principle,
                'priority': 4,
                'applicability': 'always',
                'success_rate': 0.9
            },
            {
                'name': 'jurisdiction_principle',
                'description': 'Local laws apply within their jurisdiction',
                'function': self._apply_jurisdiction_principle,
                'priority': 5,
                'applicability': 'when_location_specified',
                'success_rate': 0.75
            },
            {
                'name': 'gazette_validation',
                'description': 'Validate gazette publication dates',
                'function': self._apply_gazette_validation,
                'priority': 6,
                'applicability': 'when_gazette_references',
                'success_rate': 0.7
            },
            {
                'name': 'retroactive_application',
                'description': 'Handle retroactive application of laws',
                'function': self._apply_retroactive_check,
                'priority': 7,
                'applicability': 'when_retroactive_claimed',
                'success_rate': 0.6,
                'viva_example': 'SRO applied retroactively to past violations'
            }
        ]
    
    def _build_precedence_matrix(self) -> Dict[AuthorityLevel, Set[AuthorityLevel]]:
        """
        Build precedence matrix for KPK-specific authority relationships.
        Defines which authorities can override which.
        """
        matrix = {}
        
        # Federal level can override everything below
        federal_levels = [AuthorityLevel.FEDERAL_ACT, AuthorityLevel.FEDERAL_ORDINANCE, 
                         AuthorityLevel.FEDERAL_RULES]
        for federal in federal_levels:
            matrix[federal] = set([
                AuthorityLevel.KPK_ORDINANCE, AuthorityLevel.KPK_ACT, AuthorityLevel.KPK_RULES,
                AuthorityLevel.HAZARA_ACT, AuthorityLevel.REGIONAL_REGULATION,
                AuthorityLevel.GAZETTE_NOTIFICATION, AuthorityLevel.OFFICIAL_GAZETTE,
                AuthorityLevel.DEPARTMENT_CIRCULAR, AuthorityLevel.DEPARTMENT_ORDER,
                AuthorityLevel.POLICY_GUIDELINE, AuthorityLevel.WORKING_PLAN,
                AuthorityLevel.MANAGEMENT_PLAN, AuthorityLevel.OPERATIONAL_GUIDE,
                AuthorityLevel.DIVISIONAL_ORDER, AuthorityLevel.RANGE_ORDER,
                AuthorityLevel.BLOCK_ORDER, AuthorityLevel.LOCAL_CUSTOM,
                AuthorityLevel.COMMUNITY_AGREEMENT
            ])
        
        # KPK Ordinance can override everything below except federal
        matrix[AuthorityLevel.KPK_ORDINANCE] = set([
            AuthorityLevel.KPK_ACT, AuthorityLevel.KPK_RULES,
            AuthorityLevel.HAZARA_ACT,  # IMPORTANT: KPK Ordinance generally overrides Hazara Act
            AuthorityLevel.REGIONAL_REGULATION,
            AuthorityLevel.GAZETTE_NOTIFICATION, AuthorityLevel.OFFICIAL_GAZETTE,
            AuthorityLevel.DEPARTMENT_CIRCULAR, AuthorityLevel.DEPARTMENT_ORDER,
            AuthorityLevel.POLICY_GUIDELINE, AuthorityLevel.WORKING_PLAN,
            AuthorityLevel.MANAGEMENT_PLAN, AuthorityLevel.OPERATIONAL_GUIDE,
            AuthorityLevel.DIVISIONAL_ORDER, AuthorityLevel.RANGE_ORDER,
            AuthorityLevel.BLOCK_ORDER, AuthorityLevel.LOCAL_CUSTOM,
            AuthorityLevel.COMMUNITY_AGREEMENT
        ])
        
        # Hazara Act special case: Overrides KPK Ordinance in Hazara region
        matrix[AuthorityLevel.HAZARA_ACT] = set([
            AuthorityLevel.REGIONAL_REGULATION,
            AuthorityLevel.DEPARTMENT_CIRCULAR, AuthorityLevel.DEPARTMENT_ORDER,
            AuthorityLevel.POLICY_GUIDELINE, AuthorityLevel.WORKING_PLAN,
            AuthorityLevel.MANAGEMENT_PLAN, AuthorityLevel.OPERATIONAL_GUIDE,
            AuthorityLevel.DIVISIONAL_ORDER, AuthorityLevel.RANGE_ORDER,
            AuthorityLevel.BLOCK_ORDER, AuthorityLevel.LOCAL_CUSTOM,
            AuthorityLevel.COMMUNITY_AGREEMENT
        ])
        
        # Gazette notifications can override department-level documents
        matrix[AuthorityLevel.GAZETTE_NOTIFICATION] = set([
            AuthorityLevel.DEPARTMENT_CIRCULAR, AuthorityLevel.DEPARTMENT_ORDER,
            AuthorityLevel.POLICY_GUIDELINE, AuthorityLevel.WORKING_PLAN,
            AuthorityLevel.MANAGEMENT_PLAN, AuthorityLevel.OPERATIONAL_GUIDE,
            AuthorityLevel.DIVISIONAL_ORDER, AuthorityLevel.RANGE_ORDER,
            AuthorityLevel.BLOCK_ORDER
        ])
        
        # Department circulars can override operational documents
        matrix[AuthorityLevel.DEPARTMENT_CIRCULAR] = set([
            AuthorityLevel.WORKING_PLAN, AuthorityLevel.MANAGEMENT_PLAN,
            AuthorityLevel.OPERATIONAL_GUIDE, AuthorityLevel.DIVISIONAL_ORDER,
            AuthorityLevel.RANGE_ORDER, AuthorityLevel.BLOCK_ORDER
        ])
        
        # Working plans can override officer orders
        matrix[AuthorityLevel.WORKING_PLAN] = set([
            AuthorityLevel.DIVISIONAL_ORDER, AuthorityLevel.RANGE_ORDER,
            AuthorityLevel.BLOCK_ORDER
        ])
        
        # DFO orders can override RFO orders
        matrix[AuthorityLevel.DIVISIONAL_ORDER] = set([
            AuthorityLevel.RANGE_ORDER, AuthorityLevel.BLOCK_ORDER
        ])
        
        # RFO orders can override block orders
        matrix[AuthorityLevel.RANGE_ORDER] = set([
            AuthorityLevel.BLOCK_ORDER
        ])
        
        return matrix
    
    def resolve_conflict(self, 
                        entity: str,
                        conflicting_sources: List[Union[Dict, LegalSource]],
                        location: Optional[str] = None,
                        effective_date: Optional[Union[str, date]] = None,
                        context: Optional[Dict] = None,
                        viva_mode: bool = False) -> ResolutionResult:
        """
        Enhanced conflict resolution with research tracking.
        
        Args:
            entity: What's being conflicted
            conflicting_sources: List of conflicting legal sources
            location: Geographic location
            effective_date: Date when resolution should apply
            context: Additional context
            viva_mode: Enable detailed logging for VIVA demonstration
            
        Returns:
            Enhanced ResolutionResult
        """
        start_time = datetime.now()
        
        logger.info(f"Resolving authority conflict for: {entity}")
        if viva_mode:
            logger.info(f"VIVA Mode: Detailed logging enabled")
        
        # Parse inputs
        if isinstance(effective_date, str):
            try:
                effective_date = datetime.strptime(effective_date, '%Y-%m-%d').date()
            except ValueError:
                effective_date = None
        
        context = context or {}
        
        # Convert dict sources to LegalSource objects
        legal_sources = []
        for source in conflicting_sources:
            if isinstance(source, dict):
                legal_source = self._dict_to_legal_source(source)
                if legal_source:
                    legal_sources.append(legal_source)
            elif isinstance(source, LegalSource):
                legal_sources.append(source)
        
        if len(legal_sources) < 2:
            return ResolutionResult(
                entity=entity,
                selected_source=legal_sources[0] if legal_sources else None,
                resolution_method="no_conflict",
                applied_rules=["no_conflict_detected"],
                rule_descriptions=["No actual conflict between sources"],
                confidence=1.0,
                resolution_time_ms=int((datetime.now() - start_time).total_seconds() * 1000)
            )
        
        # Filter sources valid on effective_date
        if effective_date:
            valid_sources = [s for s in legal_sources if s.is_valid_on(effective_date)]
            if not valid_sources:
                abstention_reason = f"No sources valid on {effective_date}"
                
                # Log abstention with research context
                self.abstention_logger.log_abstention(
                    module="authority_hierarchy",
                    entity=entity,
                    reason=abstention_reason,
                    context={
                        'conflicting_sources': [s.title for s in legal_sources],
                        'effective_date': effective_date,
                        'location': location,
                        'viva_mode': viva_mode
                    },
                    category='temporal'
                )
                
                return ResolutionResult(
                    entity=entity,
                    selected_source=None,
                    resolution_method="abstention_temporal",
                    applied_rules=["temporal_validity_check"],
                    confidence=0.0,
                    abstention_reason=abstention_reason,
                    abstention_category="temporal",
                    resolution_time_ms=int((datetime.now() - start_time).total_seconds() * 1000),
                    warnings=["All sources invalid on target date"]
                )
            legal_sources = valid_sources
        
        # Log the conflict with enhanced details
        conflict = AuthorityConflict(
            entity=entity,
            conflicting_sources=legal_sources,
            conflict_type=self._determine_conflict_type(legal_sources),
            conflict_details={
                'location': location,
                'effective_date': effective_date.isoformat() if effective_date else None,
                'context': context,
                'viva_mode': viva_mode
            },
            viva_example=viva_mode
        )
        self.conflict_log.append(conflict)
        
        # Update research metrics
        if conflict.involves_hazara_act:
            self.research_metrics['hazara_conflicts'] += 1
        if conflict.involves_sro:
            self.research_metrics['sro_conflicts'] += 1
        if conflict.is_cross_jurisdictional:
            self.research_metrics['cross_jurisdictional'] += 1
        
        # Apply resolution rules in priority order
        applied_rules = []
        rule_descriptions = []
        selected_source = None
        resolution_method = "abstention"
        confidence = 0.5
        confidence_breakdown = {}
        
        sorted_rules = sorted(self.resolution_rules, key=lambda x: x['priority'])
        rules_considered = 0
        rules_applied = 0
        
        # For VIVA mode, track rule application details
        viva_rule_log = [] if viva_mode else None
        
        for rule in sorted_rules:
            rules_considered += 1
            
            # Check rule applicability
            if not self._is_rule_applicable(rule, legal_sources, location, effective_date, context):
                if viva_mode:
                    viva_rule_log.append({
                        'rule': rule['name'],
                        'applied': False,
                        'reason': 'Not applicable',
                        'priority': rule['priority']
                    })
                continue
            
            try:
                rule_func = rule['function']
                rule_result = rule_func(legal_sources, location, effective_date, context)
                
                if rule_result and rule_result.get('selected_source'):
                    selected_source = rule_result['selected_source']
                    applied_rules.append(rule['name'])
                    rule_descriptions.append(rule['description'])
                    resolution_method = f"rule_based:{rule['name']}"
                    confidence = rule_result.get('confidence', rule.get('success_rate', 0.8))
                    confidence_breakdown[rule['name']] = confidence
                    
                    # Track applied rules count
                    rules_applied += 1
                    
                    # Record which sources were overridden
                    overridden = [s for s in legal_sources if s != selected_source]
                    conflict.resolution = {
                        'applied_rule': rule['name'],
                        'selected_source': selected_source.title,
                        'overridden_sources': [s.title for s in overridden],
                        'confidence': confidence,
                        'rule_description': rule['description']
                    }
                    conflict.resolution_method = rule['name']
                    conflict.resolved_at = datetime.now()
                    
                    # For VIVA logging
                    if viva_mode:
                        viva_rule_log.append({
                            'rule': rule['name'],
                            'applied': True,
                            'selected_source': selected_source.title,
                            'confidence': confidence,
                            'overridden_count': len(overridden),
                            'priority': rule['priority']
                        })
                    
                    logger.info(f"Conflict resolved using {rule['name']}: {selected_source.title}")
                    break
                else:
                    if viva_mode:
                        viva_rule_log.append({
                            'rule': rule['name'],
                            'applied': False,
                            'reason': 'No resolution found',
                            'priority': rule['priority']
                        })
                    
            except Exception as e:
                logger.error(f"Error applying rule {rule['name']}: {e}")
                if viva_mode:
                    viva_rule_log.append({
                        'rule': rule['name'],
                        'applied': False,
                        'reason': f'Error: {str(e)}',
                        'priority': rule['priority']
                    })
                continue
        
        # If no rule resolved, use fallback strategies
        if not selected_source:
            fallback_result = self._apply_fallback_strategy(legal_sources, location, context)
            if fallback_result:
                selected_source = fallback_result['selected_source']
                resolution_method = fallback_result['method']
                applied_rules.extend(fallback_result.get('applied_rules', []))
                rule_descriptions.extend(fallback_result.get('rule_descriptions', []))
                confidence = fallback_result.get('confidence', 0.6)
                confidence_breakdown['fallback'] = confidence
                rules_applied += 1
                
                if viva_mode:
                    viva_rule_log.append({
                        'rule': 'fallback_strategy',
                        'applied': True,
                        'method': fallback_result['method'],
                        'confidence': confidence
                    })
            else:
                # Complete abstention
                abstention_reason = "No resolution rule could resolve conflict"
                
                self.abstention_logger.log_abstention(
                    module="authority_hierarchy",
                    entity=entity,
                    reason=abstention_reason,
                    context={
                        'conflicting_sources': [s.title for s in legal_sources],
                        'rules_considered': rules_considered,
                        'viva_rule_log': viva_rule_log,
                        'conflict_complexity': conflict.complexity_score
                    },
                    category='substantive'
                )
                
                # Update research metrics
                self.research_metrics['abstentions'] += 1
                
                return ResolutionResult(
                    entity=entity,
                    selected_source=None,
                    resolution_method="abstention_unresolvable",
                    applied_rules=applied_rules,
                    rule_descriptions=rule_descriptions,
                    confidence=0.0,
                    abstention_reason=abstention_reason,
                    abstention_category="substantive",
                    warnings=["System abstained due to unresolvable conflict"],
                    resolution_time_ms=int((datetime.now() - start_time).total_seconds() * 1000),
                    rules_considered=rules_considered,
                    rules_applied=rules_applied
                )
        
        # Generate warnings
        warnings = self._generate_warnings(legal_sources, selected_source, location, context)
        
        # Track temporal and jurisdictional factors
        temporal_factors = []
        jurisdictional_factors = []
        
        if effective_date:
            temporal_factors.append(f"Resolution for date: {effective_date}")
        
        if location:
            jurisdiction_info = self.jurisdiction_mapper.map_location(location)
            if jurisdiction_info.get('special_region'):
                jurisdictional_factors.append(f"Special region: {jurisdiction_info['special_region']}")
            if jurisdiction_info.get('protected_area'):
                jurisdictional_factors.append(f"Protected area: {jurisdiction_info['protected_area']['name']}")
        
        # Quality gates (for Phase 7 integration)
        passed_gates, failed_gates = self._apply_quality_gates(
            selected_source, legal_sources, confidence, location, effective_date
        )
        
        # Calculate resolution time
        resolution_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        
        # Generate result
        result = ResolutionResult(
            entity=entity,
            selected_source=selected_source,
            resolution_method=resolution_method,
            applied_rules=applied_rules,
            rule_descriptions=rule_descriptions,
            confidence=confidence,
            confidence_breakdown=confidence_breakdown,
            warnings=warnings,
            alternatives=[s for s in legal_sources if s != selected_source],
            overridden_sources=[s for s in legal_sources if s != selected_source],
            resolution_time_ms=resolution_time_ms,
            rules_considered=rules_considered,
            rules_applied=rules_applied,
            temporal_factors=temporal_factors,
            jurisdictional_factors=jurisdictional_factors,
            passed_quality_gates=passed_gates,
            failed_quality_gates=failed_gates
        )
        
        # Add to history
        self.resolution_history.append(result)
        
        # Update research metrics
        self.research_metrics['total_resolutions'] += 1
        self.research_metrics['successful_resolutions'] += 1
        self.research_metrics['total_processing_time_ms'] += resolution_time_ms
        self.research_metrics['average_confidence'] = (
            (self.research_metrics['average_confidence'] * (self.research_metrics['total_resolutions'] - 1) + confidence) 
            / self.research_metrics['total_resolutions']
        )
        
        # VIVA demonstration logging
        if viva_mode and viva_rule_log:
            logger.info(f"VIVA Rule Application Log for {entity}:")
            for log_entry in viva_rule_log:
                logger.info(f"  - {log_entry}")
        
        return result
    
    def _is_rule_applicable(self, rule: Dict, sources: List[LegalSource],
                           location: Optional[str], effective_date: Optional[date], 
                           context: Dict) -> bool:
        """Enhanced rule applicability checking."""
        applicability = rule.get('applicability', 'always')
        
        if applicability == 'always':
            return True
        elif applicability == 'when_constitutional':
            return any(s.authority_level == AuthorityLevel.CONSTITUTION for s in sources)
        elif applicability == 'when_dates_available':
            return any(s.effective_date for s in sources) and effective_date is not None
        elif applicability == 'when_special_law_exists':
            return any(s.authority_level in [AuthorityLevel.HAZARA_ACT, AuthorityLevel.REGIONAL_REGULATION] 
                      for s in sources)
        elif applicability == 'when_location_specified' and location:
            return True
        elif applicability == 'when_gazette_references':
            return any(s.gazette_reference for s in sources)
        elif applicability == 'when_retroactive_claimed':
            # Check context or source metadata for retroactive claims
            if context.get('retroactive_application'):
                return True
            return any(s.amendments and any('retroactive' in str(amendment).lower() 
                                           for amendment in s.amendments) 
                      for s in sources)
        elif applicability == 'when_context_available' and context:
            return True
        
        return False
    
    def _apply_constitutional_primacy(self, sources: List[LegalSource], 
                                     location: Optional[str], effective_date: Optional[date],
                                     context: Dict) -> Optional[Dict]:
        """Constitutional provisions override all other laws."""
        constitutional_sources = [s for s in sources 
                                 if s.authority_level == AuthorityLevel.CONSTITUTION]
        
        if constitutional_sources:
            return {
                'selected_source': constitutional_sources[0],
                'confidence': 1.0,
                'reasoning': 'Constitutional provisions have primacy over all laws'
            }
        
        return None
    
    def _apply_federal_supremacy(self, sources: List[LegalSource], 
                                location: Optional[str], effective_date: Optional[date],
                                context: Dict) -> Optional[Dict]:
        """Enhanced federal supremacy with precedence matrix check."""
        federal_sources = [s for s in sources 
                          if s.authority_level in [AuthorityLevel.FEDERAL_ACT, 
                                                  AuthorityLevel.FEDERAL_ORDINANCE,
                                                  AuthorityLevel.FEDERAL_RULES]]
        
        if federal_sources:
            # Check if federal law can override other sources using precedence matrix
            other_sources = [s for s in sources if s not in federal_sources]
            
            for federal_source in federal_sources:
                can_override_all = True
                for other_source in other_sources:
                    if other_source.authority_level in self.precedence_matrix.get(federal_source.authority_level, set()):
                        continue
                    else:
                        can_override_all = False
                        break
                
                if can_override_all:
                    return {
                        'selected_source': federal_source,
                        'confidence': 0.95,
                        'reasoning': f'Federal law ({federal_source.authority_level.value}) has supremacy over lower laws'
                    }
        
        return None
    
    def _apply_temporal_precedence(self, sources: List[LegalSource],
                                  location: Optional[str], effective_date: Optional[date],
                                  context: Dict) -> Optional[Dict]:
        """Enhanced temporal precedence with gazette date validation."""
        sources_with_dates = [s for s in sources if s.effective_date]
        
        if len(sources_with_dates) >= 2:
            # Sort by effective date (newest first)
            sorted_sources = sorted(sources_with_dates, 
                                   key=lambda x: x.effective_date, 
                                   reverse=True)
            
            # Check if they're from same authority level or one can override another
            newest_source = sorted_sources[0]
            
            # Check if newest source can override older ones
            can_override = True
            for older_source in sorted_sources[1:]:
                if newer_source.authority_level in self.precedence_matrix.get(older_source.authority_level, set()):
                    continue
                elif self._can_override_by_time(newer_source, older_source, effective_date):
                    continue
                else:
                    can_override = False
                    break
            
            if can_override:
                return {
                    'selected_source': newest_source,
                    'confidence': 0.9,
                    'reasoning': f'Later law ({newest_source.effective_date}) overrides earlier law'
                }
        
        return None
    
    def _apply_special_over_general(self, sources: List[LegalSource],
                                   location: Optional[str], effective_date: Optional[date],
                                   context: Dict) -> Optional[Dict]:
        """Enhanced special over general with Hazara Act focus."""
        # Check for Hazara Act (special regional law)
        hazara_sources = [s for s in sources 
                         if s.authority_level == AuthorityLevel.HAZARA_ACT]
        
        if hazara_sources and location:
            # Check if location is in Hazara region
            jurisdiction_info = self.jurisdiction_mapper.map_location(location)
            if jurisdiction_info.get('special_region') == 'Hazara':
                # Hazara Act applies in Hazara region and can override KPK Ordinance
                hazara_source = hazara_sources[0]
                
                # Check if there are KPK Ordinance sources
                kpk_sources = [s for s in sources 
                              if s.authority_level == AuthorityLevel.KPK_ORDINANCE]
                
                if kpk_sources:
                    # This is a key research case: Hazara Act vs KPK Ordinance
                    reasoning = (
                        f'Hazara Act 1936 (special regional law) applies in Hazara region '
                        f'and takes precedence over KPK Forest Ordinance 2002 for local matters'
                    )
                    return {
                        'selected_source': hazara_source,
                        'confidence': 0.85,  # Slightly lower due to complexity
                        'reasoning': reasoning
                    }
                else:
                    # Hazara Act vs other laws
                    return {
                        'selected_source': hazara_source,
                        'confidence': 0.8,
                        'reasoning': 'Hazara Act (special regional law) applies in Hazara region'
                    }
        
        # Check for other special laws (Malakand regulations, etc.)
        special_sources = [s for s in sources 
                          if s.authority_level == AuthorityLevel.REGIONAL_REGULATION]
        
        if special_sources and location:
            jurisdiction_info = self.jurisdiction_mapper.map_location(location)
            if jurisdiction_info.get('special_region') == 'Malakand':
                return {
                    'selected_source': special_sources[0],
                    'confidence': 0.75,
                    'reasoning': 'Special Malakand regulations apply in Malakand region'
                }
        
        # Check for species-specific or activity-specific provisions
        entity_type = context.get('entity_type')
        if entity_type == 'species':
            species_name = context.get('species_name', '').lower()
            
            # Look for sources that specifically mention this species
            # This would require content analysis in real implementation
            # For now, we'll use a simplified approach
            species_keywords = {
                'deodar': ['cedrus deodara', 'deodar', 'دیار'],
                'chir': ['pinus roxburghii', 'chir', 'چلغوزا'],
                'walnut': ['juglans regia', 'walnut', 'اخروٹ']
            }
            
            for species, keywords in species_keywords.items():
                if species in species_name:
                    # Check for sources with species-specific provisions
                    # This is a placeholder for actual content analysis
                    pass
        
        return None
    
    def _apply_hierarchy_principle(self, sources: List[LegalSource],
                                  location: Optional[str], effective_date: Optional[date],
                                  context: Dict) -> Optional[Dict]:
        """Enhanced hierarchy principle with precedence matrix."""
        # Sort by authority level (highest first)
        sorted_by_authority = sorted(sources, key=lambda x: x.authority_level.get_rank())
        
        highest_source = sorted_by_authority[0]
        
        # Check if highest source can override all others using precedence matrix
        can_override_all = True
        for other_source in sorted_by_authority[1:]:
            if other_source.authority_level in self.precedence_matrix.get(highest_source.authority_level, set()):
                continue
            else:
                can_override_all = False
                break
        
        if can_override_all:
            return {
                'selected_source': highest_source,
                'confidence': 0.85,
                'reasoning': f'Higher authority ({highest_source.authority_level.value}) overrides lower authority'
            }
        
        # If highest can't override all, check for pairwise overrides
        # This handles complex multi-source conflicts
        for i, source1 in enumerate(sorted_by_authority):
            can_override_others = True
            for source2 in sorted_by_authority[i+1:]:
                if source2.authority_level in self.precedence_matrix.get(source1.authority_level, set()):
                    continue
                else:
                    can_override_others = False
                    break
            
            if can_override_others:
                return {
                    'selected_source': source1,
                    'confidence': 0.8,
                    'reasoning': f'Authority ({source1.authority_level.value}) can override conflicting sources'
                }
        
        return None
    
    def _apply_jurisdiction_principle(self, sources: List[LegalSource],
                                     location: Optional[str], effective_date: Optional[date],
                                     context: Dict) -> Optional[Dict]:
        """Enhanced jurisdiction principle with KPK hierarchy."""
        if not location:
            return None
        
        jurisdiction_info = self.jurisdiction_mapper.map_location(location)
        
        # Get authorities applicable to this location
        applicable_authorities = self.jurisdiction_mapper.get_applicable_authorities(
            location, effective_date, context.get('entity_type')
        )
        
        # Find sources with authority levels applicable to location
        applicable_sources = []
        for auth_info in applicable_authorities:
            auth_level = auth_info['authority']
            for source in sources:
                if source.authority_level == auth_level:
                    # Additional check: does source mention this location or jurisdiction?
                    # Simplified - in real system would check source content
                    applicable_sources.append({
                        'source': source,
                        'applicability': auth_info['applicability'],
                        'priority': auth_info['priority'],
                        'reason': auth_info['reason']
                    })
        
        if applicable_sources:
            # Sort by priority and authority level
            applicable_sources.sort(key=lambda x: (x['priority'], x['source'].authority_level.get_rank()))
            
            selected = applicable_sources[0]['source']
            applicability_reason = applicable_sources[0]['reason']
            
            return {
                'selected_source': selected,
                'confidence': 0.75,
                'reasoning': f'Source applicable to location: {applicability_reason}'
            }
        
        return None
    
    def _apply_gazette_validation(self, sources: List[LegalSource],
                                 location: Optional[str], effective_date: Optional[date],
                                 context: Dict) -> Optional[Dict]:
        """Validate gazette publication dates."""
        sources_with_gazette = [s for s in sources if s.gazette_reference and s.gazette_date]
        
        if len(sources_with_gazette) >= 2:
            # Validate gazette dates
            valid_sources = []
            for source in sources_with_gazette:
                is_valid, actual_date = self.jurisdiction_mapper.validate_gazette_date(
                    source.gazette_reference, source.gazette_date
                )
                
                if is_valid:
                    valid_sources.append(source)
                else:
                    # Log discrepancy
                    logger.warning(f"Gazette date discrepancy for {source.gazette_reference}: "
                                 f"claimed {source.gazette_date}, actual {actual_date}")
            
            if valid_sources:
                # Among valid sources, pick most recent gazette
                most_recent = max(valid_sources, key=lambda x: x.gazette_date)
                return {
                    'selected_source': most_recent,
                    'confidence': 0.9,
                    'reasoning': f'Most recently gazetted source ({most_recent.gazette_date})'
                }
        
        return None
    
    def _apply_retroactive_check(self, sources: List[LegalSource],
                                location: Optional[str], effective_date: Optional[date],
                                context: Dict) -> Optional[Dict]:
        """
        Handle retroactive application of laws.
        Important for penalty calculations and SROs.
        """
        if not effective_date:
            return None
        
        # Check for sources claiming retroactive application
        retroactive_sources = []
        for source in sources:
            # Check amendments for retroactive claims
            if source.amendments:
                for amendment in source.amendments:
                    if isinstance(amendment, dict) and amendment.get('retroactive'):
                        retroactive_date_str = amendment.get('retroactive_from')
                        if retroactive_date_str:
                            try:
                                retroactive_date = datetime.strptime(retroactive_date_str, '%Y-%m-%d').date()
                                if effective_date >= retroactive_date:
                                    retroactive_sources.append({
                                        'source': source,
                                        'retroactive_from': retroactive_date,
                                        'amendment_details': amendment
                                    })
                            except ValueError:
                                continue
        
        if retroactive_sources:
            # Sort by retroactive date (most recent retroactive claim first)
            retroactive_sources.sort(key=lambda x: x['retroactive_from'], reverse=True)
            
            selected = retroactive_sources[0]['source']
            retroactive_date = retroactive_sources[0]['retroactive_from']
            
            return {
                'selected_source': selected,
                'confidence': 0.7,  # Lower confidence for retroactive applications
                'reasoning': f'Source applies retroactively from {retroactive_date}'
            }
        
        return None
    
    def _can_override_by_time(self, newer_source: LegalSource, 
                             older_source: LegalSource,
                             target_date: Optional[date]) -> bool:
        """
        Check if a newer source can override an older source based on timing rules.
        """
        if not newer_source.effective_date or not older_source.effective_date:
            return False
        
        # Newer source must be later than older source
        if newer_source.effective_date <= older_source.effective_date:
            return False
        
        # Check if newer source was valid when older source was made
        if target_date and newer_source.effective_date > target_date:
            # Newer source wasn't in effect at the time
            return False
        
        # Check precedence matrix
        if older_source.authority_level in self.precedence_matrix.get(newer_source.authority_level, set()):
            return True
        
        return False
    
    def _apply_fallback_strategy(self, sources: List[LegalSource],
                                location: Optional[str], context: Dict) -> Optional[Dict]:
        """Enhanced fallback strategies for research scenarios."""
        
        # Strategy 1: Most recent source with confidence weighting
        sources_with_dates = [s for s in sources if s.effective_date]
        if sources_with_dates:
            most_recent = max(sources_with_dates, key=lambda x: x.effective_date)
            confidence = 0.6 * most_recent.confidence if hasattr(most_recent, 'confidence') else 0.6
            return {
                'selected_source': most_recent,
                'method': 'fallback:most_recent',
                'confidence': confidence,
                'applied_rules': ['fallback_temporal'],
                'rule_descriptions': ['Selected most recent source as fallback'],
                'reasoning': f'Most recent source ({most_recent.effective_date}) selected'
            }
        
        # Strategy 2: Highest confidence source
        sources_with_conf = [s for s in sources if hasattr(s, 'confidence')]
        if sources_with_conf:
            highest_conf = max(sources_with_conf, key=lambda x: x.confidence)
            confidence = highest_conf.confidence * 0.8  # Reduce for fallback
            return {
                'selected_source': highest_conf,
                'method': 'fallback:highest_confidence',
                'confidence': confidence,
                'applied_rules': ['fallback_confidence'],
                'rule_descriptions': ['Selected source with highest confidence as fallback'],
                'reasoning': f'Highest confidence source ({highest_conf.confidence:.2f}) selected'
            }
        
        # Strategy 3: Authority-based deterministic choice
        if sources:
            # Sort by authority level, then by title for determinism
            sorted_sources = sorted(sources, 
                                   key=lambda x: (x.authority_level.get_rank(), x.title))
            selected = sorted_sources[0]
            return {
                'selected_source': selected,
                'method': 'fallback:deterministic_choice',
                'confidence': 0.5,
                'applied_rules': ['fallback_deterministic'],
                'rule_descriptions': ['Deterministic choice based on authority and title'],
                'reasoning': 'Deterministic fallback applied',
                'warning': 'Arbitrary deterministic choice made - low confidence'
            }
        
        return None
    
    def _determine_conflict_type(self, sources: List[LegalSource]) -> str:
        """Enhanced conflict type determination."""
        authority_levels = set(s.authority_level for s in sources)
        
        if len(authority_levels) > 1:
            # Check if it involves special KPK conflicts
            if AuthorityLevel.HAZARA_ACT in authority_levels and AuthorityLevel.KPK_ORDINANCE in authority_levels:
                return 'hazara_kpk_conflict'
            elif AuthorityLevel.GAZETTE_NOTIFICATION in authority_levels:
                return 'sro_conflict'
            return 'hierarchy'
        
        # Check dates
        dates = [s.effective_date for s in sources if s.effective_date]
        if len(dates) >= 2:
            # Check if dates are same but times different (rare but possible)
            unique_dates = set(dates)
            if len(unique_dates) == 1:
                return 'simultaneous_publication'
            return 'temporal'
        
        # Check jurisdictions
        jurisdictions = set(s.jurisdiction for s in sources)
        if len(jurisdictions) > 1:
            return 'jurisdiction'
        
        # Check gazette references
        gazette_refs = [s.gazette_reference for s in sources if s.gazette_reference]
        if len(gazette_refs) >= 2:
            return 'gazette_conflict'
        
        return 'substantive'
    
    def _dict_to_legal_source(self, source_dict: Dict) -> Optional[LegalSource]:
        """Enhanced conversion with Phase 4 integration."""
        try:
            # Parse dates
            effective_date = None
            if 'effective_date' in source_dict:
                effective_date = datetime.strptime(
                    source_dict['effective_date'], '%Y-%m-%d'
                ).date()
            
            expiry_date = None
            if 'expiry_date' in source_dict:
                expiry_date = datetime.strptime(
                    source_dict['expiry_date'], '%Y-%m-%d'
                ).date()
            
            gazette_date = None
            if 'gazette_date' in source_dict:
                gazette_date = datetime.strptime(
                    source_dict['gazette_date'], '%Y-%m-%d'
                ).date()
            
            enforcement_date = None
            if 'enforcement_date' in source_dict:
                enforcement_date = datetime.strptime(
                    source_dict['enforcement_date'], '%Y-%m-%d'
                ).date()
            
            # Parse authority level
            authority_str = source_dict.get('authority', 'unknown')
            authority_level = AuthorityLevel.from_string(authority_str)
            
            # Parse jurisdiction
            jurisdiction_str = source_dict.get('jurisdiction', 'unknown')
            jurisdiction = self._parse_jurisdiction(jurisdiction_str)
            
            # Extract KPK-specific details
            kpk_division = source_dict.get('kpk_division')
            kpk_district = source_dict.get('kpk_district')
            
            # If not provided, try to extract from location
            if not kpk_division or not kpk_district:
                location = source_dict.get('location')
                if location:
                    jurisdiction_info = self.jurisdiction_mapper.map_location(location)
                    kpk_division = kpk_division or jurisdiction_info.get('division')
                    kpk_district = kpk_district or jurisdiction_info.get('district')
            
            # Get Phase 4 integration data
            amendment_chain_id = source_dict.get('amendment_chain_id')
            parent_document_id = source_dict.get('parent_document_id')
            citation_references = source_dict.get('citation_references', [])
            
            return LegalSource(
                title=source_dict.get('title', 'Unknown'),
                short_title=source_dict.get('short_title'),
                document_id=source_dict.get('document_id'),
                authority_level=authority_level,
                jurisdiction=jurisdiction,
                jurisdiction_details=source_dict.get('jurisdiction_details', {}),
                effective_date=effective_date,
                expiry_date=expiry_date,
                gazette_date=gazette_date,
                enforcement_date=enforcement_date,
                amendment_chain_id=amendment_chain_id,
                parent_document_id=parent_document_id,
                citation_references=citation_references,
                confidence=source_dict.get('confidence', 1.0),
                quality_score=source_dict.get('quality_score', 1.0),
                is_current=source_dict.get('is_current', True),
                is_verified=source_dict.get('is_verified', False),
                gazette_reference=source_dict.get('gazette_reference'),
                gazette_number=source_dict.get('gazette_number'),
                gazette_page=source_dict.get('gazette_page'),
                kpk_division=kpk_division,
                kpk_district=kpk_district,
                forest_type=source_dict.get('forest_type'),
                node_id=source_dict.get('node_id'),
                key_provisions=source_dict.get('key_provisions', []),
                penalties=source_dict.get('penalties', []),
                species_mentioned=source_dict.get('species_mentioned', []),
                version=source_dict.get('version', '1.0'),
                amendments=source_dict.get('amendments', [])
            )
        except Exception as e:
            logger.error(f"Failed to convert dict to LegalSource: {e}")
            return None
    
    def _parse_jurisdiction(self, jurisdiction_str: str) -> JurisdictionLevel:
        """Enhanced jurisdiction parsing."""
        jurisdiction_lower = jurisdiction_str.lower()
        
        mapping = {
            'federal': JurisdictionLevel.FEDERAL,
            'وفاقی': JurisdictionLevel.FEDERAL,
            'provincial': JurisdictionLevel.PROVINCIAL,
            'صوبائی': JurisdictionLevel.PROVINCIAL,
            'division': JurisdictionLevel.DIVISION,
            'ڈویژن': JurisdictionLevel.DIVISION,
            'district': JurisdictionLevel.DISTRICT,
            'ضلع': JurisdictionLevel.DISTRICT,
            'tehsil': JurisdictionLevel.TEHSIL,
            'تحصیل': JurisdictionLevel.TEHSIL,
            'union council': JurisdictionLevel.UNION_COUNCIL,
            'یونین کونسل': JurisdictionLevel.UNION_COUNCIL,
            'forest compartment': JurisdictionLevel.FOREST_COMPARTMENT,
            'جنگل کا قطعہ': JurisdictionLevel.FOREST_COMPARTMENT,
            'protected area': JurisdictionLevel.PROTECTED_AREA,
            'محفوظ علاقہ': JurisdictionLevel.PROTECTED_AREA,
            'community forest': JurisdictionLevel.COMMUNITY_FOREST,
            'گزارہ جنگل': JurisdictionLevel.COMMUNITY_FOREST,
        }
        
        for key, value in mapping.items():
            if key in jurisdiction_lower:
                return value
        
        return JurisdictionLevel.UNKNOWN
    
    def _generate_warnings(self, all_sources: List[LegalSource], 
                          selected_source: LegalSource,
                          location: Optional[str],
                          context: Dict) -> List[str]:
        """Enhanced warning generation."""
        warnings = []
        
        # Check if selected source is not the highest authority
        highest_auth = min(all_sources, key=lambda x: x.authority_level.get_rank())
        if selected_source != highest_auth:
            warnings.append(
                f"Selected source ({selected_source.authority_level.value}) is not highest "
                f"authority ({highest_auth.authority_level.value} - {highest_auth.title})"
            )
        
        # Check temporal validity if date provided
        if 'effective_date' in context:
            target_date = context['effective_date']
            if isinstance(target_date, str):
                try:
                    target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
                except ValueError:
                    target_date = None
            
            if target_date and not selected_source.is_valid_on(target_date):
                warnings.append(
                    f"Selected source may not be valid on target date {target_date}"
                )
        
        # Check location applicability
        if location:
            jurisdiction_info = self.jurisdiction_mapper.map_location(location)
            
            # Special region check
            if jurisdiction_info.get('special_region'):
                if jurisdiction_info['special_region'] == 'Hazara':
                    if selected_source.authority_level != AuthorityLevel.HAZARA_ACT:
                        warnings.append(
                            f"Location is in Hazara region but selected source is not Hazara Act"
                        )
            
            # Protected area check
            if jurisdiction_info.get('protected_area'):
                if selected_source.authority_level != AuthorityLevel.FEDERAL_ACT:
                    warnings.append(
                        f"Location is protected area but selected source is not federal act"
                    )
        
        # Check confidence
        if selected_source.confidence < 0.7:
            warnings.append(
                f"Selected source has low confidence: {selected_source.confidence:.2f}"
            )
        
        # Check if source has been amended
        if selected_source.amendments:
            warnings.append(
                f"Selected source has {len(selected_source.amendments)} amendments"
            )
        
        # Check gazette validation
        if selected_source.gazette_reference and selected_source.gazette_date:
            is_valid, actual_date = self.jurisdiction_mapper.validate_gazette_date(
                selected_source.gazette_reference, selected_source.gazette_date
            )
            if not is_valid:
                warnings.append(
                    f"Gazette date may be incorrect: claimed {selected_source.gazette_date}, "
                    f"registry shows {actual_date}"
                )
        
        return warnings
    
    def _apply_quality_gates(self, selected_source: LegalSource,
                            all_sources: List[LegalSource],
                            confidence: float,
                            location: Optional[str],
                            effective_date: Optional[date]) -> Tuple[List[str], List[str]]:
        """
        Apply quality gates from Phase 7.
        Returns (passed_gates, failed_gates)
        """
        passed = []
        failed = []
        
        # Gate 1: Confidence threshold
        if confidence >= 0.7:
            passed.append('confidence_threshold')
        else:
            failed.append('confidence_threshold')
        
        # Gate 2: Source validity
        if effective_date and selected_source.is_valid_on(effective_date):
            passed.append('temporal_validity')
        elif not effective_date:
            passed.append('temporal_validity')  # No date to check
        else:
            failed.append('temporal_validity')
        
        # Gate 3: Authority coherence
        if selected_source == min(all_sources, key=lambda x: x.authority_level.get_rank()):
            passed.append('authority_coherence')
        else:
            failed.append('authority_coherence')
        
        # Gate 4: Location applicability (if location provided)
        if location:
            jurisdiction_info = self.jurisdiction_mapper.map_location(location)
            applicable_auths = self.jurisdiction_mapper.get_applicable_authorities(location, effective_date)
            applicable_levels = [auth['authority'] for auth in applicable_auths]
            
            if selected_source.authority_level in applicable_levels:
                passed.append('location_applicability')
            else:
                failed.append('location_applicability')
        else:
            passed.append('location_applicability')  # No location to check
        
        # Gate 5: Source quality
        if hasattr(selected_source, 'quality_score') and selected_source.quality_score >= 0.8:
            passed.append('source_quality')
        else:
            failed.append('source_quality')
        
        return passed, failed
    
    def get_resolution_statistics(self) -> Dict[str, Any]:
        """Enhanced statistics with research metrics."""
        total_resolutions = len(self.resolution_history)
        total_conflicts = len(self.conflict_log)
        
        stats = {
            'total_resolutions': total_resolutions,
            'total_conflicts': total_conflicts,
            'resolution_rate': total_resolutions / total_conflicts if total_conflicts > 0 else 0,
            'research_metrics': self.research_metrics,
            'abstention_rate': self.research_metrics['abstentions'] / total_resolutions if total_resolutions > 0 else 0,
            'average_confidence': self.research_metrics['average_confidence'],
            'average_resolution_time_ms': self.research_metrics['total_processing_time_ms'] / total_resolutions 
                                         if total_resolutions > 0 else 0,
        }
        
        # Resolution method distribution
        method_counts = defaultdict(int)
        for resolution in self.resolution_history:
            method_counts[resolution.resolution_method] += 1
        
        stats['resolution_methods'] = dict(method_counts)
        
        # Conflict type distribution
        conflict_type_counts = defaultdict(int)
        for conflict in self.conflict_log:
            conflict_type_counts[conflict.conflict_type] += 1
        
        stats['conflict_types'] = dict(conflict_type_counts)
        
        # Success rates by rule
        rule_success_counts = defaultdict(int)
        rule_total_counts = defaultdict(int)
        
        for resolution in self.resolution_history:
            for rule in resolution.applied_rules:
                rule_total_counts[rule] += 1
                if resolution.confidence >= 0.7:
                    rule_success_counts[rule] += 1
        
        rule_success_rates = {}
        for rule, total in rule_total_counts.items():
            success = rule_success_counts.get(rule, 0)
            rule_success_rates[rule] = success / total if total > 0 else 0
        
        stats['rule_success_rates'] = rule_success_rates
        
        return stats
    
    def export_authority_network(self) -> Dict[str, Any]:
        """Enhanced network export for Phase 6 graph construction."""
        nodes = []
        edges = []
        
        # Collect unique sources from conflicts
        all_sources = set()
        for conflict in self.conflict_log:
            all_sources.update(conflict.conflicting_sources)
        
        # Create nodes with enhanced attributes for Neo4j
        for i, source in enumerate(all_sources):
            node = {
                'id': source.node_id or f"source_{i}",
                'label': source.title,
                'type': 'LegalSource',
                'properties': {
                    'title': source.title,
                    'authority_level': source.authority_level.value,
                    'authority_name': source.authority_level.name,
                    'jurisdiction': source.jurisdiction.value,
                    'effective_date': source.effective_date.isoformat() if source.effective_date else None,
                    'confidence': source.confidence,
                    'document_id': source.document_id,
                    'gazette_reference': source.gazette_reference,
                    'kpk_division': source.kpk_division,
                    'kpk_district': source.kpk_district
                }
            }
            nodes.append(node)
        
        # Create edges from conflicts
        edge_id = 0
        for conflict in self.conflict_log:
            sources = conflict.conflicting_sources
            for i in range(len(sources)):
                for j in range(i + 1, len(sources)):
                    source1 = sources[i]
                    source2 = sources[j]
                    
                    edge = {
                        'id': f"conflict_{edge_id}",
                        'source': source1.node_id or f"source_{list(all_sources).index(source1)}",
                        'target': source2.node_id or f"source_{list(all_sources).index(source2)}",
                        'type': 'CONFLICTS_WITH',
                        'properties': {
                            'conflict_type': conflict.conflict_type,
                            'entity': conflict.entity,
                            'detected_at': conflict.detected_at.isoformat(),
                            'complexity_score': conflict.complexity_score,
                            'involves_hazara_act': conflict.involves_hazara_act,
                            'involves_sro': conflict.involves_sro
                        }
                    }
                    edges.append(edge)
                    edge_id += 1
        
        # Create resolution edges
        for resolution in self.resolution_history:
            if resolution.selected_source and resolution.overridden_sources:
                for overridden in resolution.overridden_sources:
                    edge = {
                        'id': f"resolution_{resolution.resolution_id}_{edge_id}",
                        'source': resolution.selected_source.node_id,
                        'target': overridden.node_id,
                        'type': 'OVERRIDES',
                        'properties': {
                            'resolution_method': resolution.resolution_method,
                            'entity': resolution.entity,
                            'confidence': resolution.confidence,
                            'applied_rules': resolution.applied_rules
                        }
                    }
                    edges.append(edge)
                    edge_id += 1
        
        return {
            'nodes': nodes,
            'edges': edges,
            'metadata': {
                'total_sources': len(all_sources),
                'total_conflicts': len(self.conflict_log),
                'total_resolutions': len(self.resolution_history),
                'generated_at': datetime.now().isoformat(),
                'graph_type': 'authority_conflict_network',
                'purpose': 'Phase 6 graph construction input'
            }
        }
    
    def save_research_data(self, filepath: str):
        """Save research data for VIVA demonstration."""
        data = {
            'conflict_log': [c.to_dict() for c in self.conflict_log],
            'resolution_history': [r.to_dict() for r in self.resolution_history],
            'research_metrics': self.research_metrics,
            'statistics': self.get_resolution_statistics(),
            'authority_network': self.export_authority_network(),
            'generated_at': datetime.now().isoformat()
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        logger.info(f"Research data saved to {filepath}")
    
    def load_research_data(self, filepath: str):
        """Load research data for VIVA demonstration."""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            # This would need proper deserialization logic
            # For now, just log success
            logger.info(f"Research data loaded from {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to load research data: {e}")
            return False


# Enhanced utility functions
def create_authority_resolver(abstention_logger: Optional[AbstentionLogger] = None) -> AuthorityHierarchyResolver:
    """Factory function to create enhanced authority resolver."""
    return AuthorityHierarchyResolver(abstention_logger)


def analyze_authority_strength(sources: List[Dict], 
                              location: Optional[str] = None,
                              target_date: Optional[date] = None) -> Dict:
    """Enhanced authority strength analysis."""
    resolver = AuthorityHierarchyResolver()
    
    legal_sources = []
    for source_dict in sources:
        legal_source = resolver._dict_to_legal_source(source_dict)
        if legal_source:
            legal_sources.append(legal_source)
    
    if not legal_sources:
        return {'error': 'No valid sources provided'}
    
    # Find strongest source by authority level
    strongest_by_hierarchy = min(legal_sources, key=lambda x: x.authority_level.get_rank())
    
    # Find most recent source
    sources_with_dates = [s for s in legal_sources if s.effective_date]
    most_recent = max(sources_with_dates, key=lambda x: x.effective_date) if sources_with_dates else None
    
    # Check for conflicts
    has_conflict = False
    if len(legal_sources) > 1:
        authority_levels = set(s.authority_level for s in legal_sources)
        has_conflict = len(authority_levels) > 1
        
        # Also check temporal conflicts
        if len(sources_with_dates) >= 2:
            dates_set = set(s.effective_date for s in sources_with_dates)
            if len(dates_set) < len(sources_with_dates):
                has_conflict = True  # Same date, different sources
    
    # Check location applicability
    location_applicable = []
    if location:
        jurisdiction_info = resolver.jurisdiction_mapper.map_location(location)
        applicable_auths = resolver.jurisdiction_mapper.get_applicable_authorities(location, target_date)
        applicable_levels = [auth['authority'] for auth in applicable_auths]
        
        for source in legal_sources:
            if source.authority_level in applicable_levels:
                location_applicable.append(source.title)
    
    return {
        'strongest_by_hierarchy': strongest_by_hierarchy.title,
        'strongest_authority': strongest_by_hierarchy.authority_level.value,
        'most_recent': most_recent.title if most_recent else None,
        'most_recent_date': most_recent.effective_date.isoformat() if most_recent else None,
        'has_conflicts': has_conflict,
        'sources_analyzed': len(legal_sources),
        'location_applicable': location_applicable,
        'conflict_types': resolver._determine_conflict_type(legal_sources) if has_conflict else 'none',
        'recommendation': 'Consult authority resolver for conflicts' if has_conflict else 'No conflicts detected'
    }


# Example usage and testing
if __name__ == "__main__":
    print("=== Enhanced KPK Authority Hierarchy Resolver ===\n")
    print("Designed for GreenLawAI-KPK Research Project")
    print("Phase 5: Temporal & Authority Resolution\n")
    
    # Initialize resolver
    resolver = AuthorityHierarchyResolver()
    
    # Test Case 1: RESEARCH FOCUS - Hazara Act vs KPK Ordinance
    print("TEST CASE 1: RESEARCH FOCUS - Hazara Act vs KPK Ordinance")
    print("-" * 70)
    
    sources = [
        {
            'title': 'KPK Forest Ordinance 2002',
            'authority': 'kpk_ordinance',
            'jurisdiction': 'provincial',
            'effective_date': '2002-06-15',
            'gazette_date': '2002-06-10',
            'gazette_reference': 'SRO-123(I)/2002',
            'confidence': 0.98,
            'location': 'Khyber Pakhtunkhwa'
        },
        {
            'title': 'Hazara Forest Act 1936',
            'authority': 'hazara_act',
            'jurisdiction': 'regional',
            'effective_date': '1936-11-10',
            'confidence': 0.90,
            'location': 'Hazara Division'
        },
        {
            'title': 'Circular No. 45/FD/2020 on Deodar Protection',
            'authority': 'department_circular',
            'jurisdiction': 'division',
            'effective_date': '2020-03-15',
            'confidence': 0.85,
            'location': 'Hazara Division'
        }
    ]
    
    result = resolver.resolve_conflict(
        entity="Deodar cedar protection and penalties",
        conflicting_sources=sources,
        location="Mansehra, Hazara Division",
        effective_date="2023-06-15",
        context={'entity_type': 'species', 'species_name': 'Deodar'},
        viva_mode=True  # Enable detailed logging for VIVA
    )
    
    print(f"Entity: {result.entity}")
    print(f"Selected Source: {result.selected_source.title if result.selected_source else 'ABSTENTION'}")
    if result.selected_source:
        print(f"Authority Level: {result.selected_source.authority_level.get_hierarchy_name()}")
    print(f"Resolution Method: {result.resolution_method}")
    print(f"Confidence: {result.confidence:.2f} ({result.get_confidence_level()})")
    print(f"Applied Rules: {', '.join(result.applied_rules)}")
    print(f"Rules Considered: {result.rules_considered}, Applied: {result.rules_applied}")
    print(f"Resolution Time: {result.resolution_time_ms} ms")
    
    if result.abstention_reason:
        print(f"Abstention Reason: {result.abstention_reason}")
        print(f"Abstention Category: {result.abstention_category}")
    
    if result.warnings:
        print(f"\nWarnings:")
        for warning in result.warnings:
            print(f"  - {warning}")
    
    print(f"\nQuality Gates: Passed {len(result.passed_quality_gates)}, "
          f"Failed {len(result.failed_quality_gates)}")
    
    print("\n" + "=" * 70)
    
    # Test Case 2: Temporal conflict with SROs
    print("\nTEST CASE 2: Temporal Conflict with Gazette Notifications (SROs)")
    print("-" * 70)
    
    sources2 = [
        {
            'title': 'KPK Forest Rules 2004',
            'authority': 'kpk_rules',
            'jurisdiction': 'provincial',
            'effective_date': '2004-05-20',
            'confidence': 0.95
        },
        {
            'title': 'SRO-456(I)/2023 - Revised Forest Fines',
            'authority': 'gazette_notification',
            'jurisdiction': 'federal',
            'effective_date': '2023-03-15',
            'gazette_date': '2023-03-10',
            'gazette_reference': 'SRO-456(I)/2023',
            'confidence': 0.88,
            'amendments': [
                {'type': 'revision', 'retroactive': True, 'retroactive_from': '2022-01-01'}
            ]
        },
        {
            'title': 'DFO Malakand Order on Pine Tree Protection',
            'authority': 'divisional_order',
            'jurisdiction': 'district',
            'effective_date': '2022-11-01',
            'confidence': 0.75
        }
    ]
    
    result2 = resolver.resolve_conflict(
        entity="Pine tree felling fine calculation",
        conflicting_sources=sources2,
        location="Swat, Malakand Division",
        effective_date="2023-06-15"
    )
    
    print(f"Selected Source: {result2.selected_source.title if result2.selected_source else 'ABSTENTION'}")
    print(f"Resolution Method: {result2.resolution_method}")
    print(f"Confidence: {result2.confidence:.2f}")
    
    if result2.temporal_factors:
        print(f"Temporal Factors: {', '.join(result2.temporal_factors)}")
    
    print("\n" + "=" * 70)
    
    # Test Case 3: Complex multi-jurisdictional conflict
    print("\nTEST CASE 3: Multi-Jurisdictional Conflict (Federal, Provincial, Local)")
    print("-" * 70)
    
    sources3 = [
        {
            'title': 'Pakistan Forest Act 1927',
            'authority': 'federal_act',
            'jurisdiction': 'federal',
            'effective_date': '1927-03-21',
            'confidence': 0.92
        },
        {
            'title': 'KPK Wildlife Act 2015',
            'authority': 'kpk_act',
            'jurisdiction': 'provincial',
            'effective_date': '2015-08-10',
            'confidence': 0.90
        },
        {
            'title': 'Community Forest Agreement - Kalam Valley',
            'authority': 'community_agreement',
            'jurisdiction': 'community_forest',
            'effective_date': '2018-06-01',
            'confidence': 0.80
        }
    ]
    
    result3 = resolver.resolve_conflict(
        entity="Wildlife habitat protection in community forest",
        conflicting_sources=sources3,
        location="Kalam, Swat, Malakand Division",
        effective_date="2023-06-15"
    )
    
    print(f"Selected Source: {result3.selected_source.title if result3.selected_source else 'ABSTENTION'}")
    print(f"Jurisdiction: {result3.selected_source.jurisdiction.name if result3.selected_source else 'N/A'}")
    print(f"Resolution Method: {result3.resolution_method}")
    
    if result3.jurisdictional_factors:
        print(f"Jurisdictional Factors: {', '.join(result3.jurisdictional_factors)}")
    
    print("\n" + "=" * 70)
    
    # Test Case 4: Authority analysis
    print("\nTEST CASE 4: Comprehensive Authority Analysis")
    print("-" * 70)
    
    analysis = analyze_authority_strength(sources, "Mansehra, Hazara Division", date(2023, 6, 15))
    print(f"Strongest by Hierarchy: {analysis['strongest_by_hierarchy']}")
    print(f"Authority Level: {analysis['strongest_authority']}")
    print(f"Most Recent: {analysis['most_recent']} ({analysis['most_recent_date']})")
    print(f"Has Conflicts: {analysis['has_conflicts']}")
    print(f"Conflict Type: {analysis['conflict_types']}")
    print(f"Location Applicable Sources: {len(analysis['location_applicable'])}")
    
    print("\n" + "=" * 70)
    
    # Test Case 5: Research statistics and reporting
    print("\nTEST CASE 5: Research Statistics and VIVA-Ready Reporting")
    print("-" * 70)
    
    stats = resolver.get_resolution_statistics()
    print(f"Total Resolutions: {stats['total_resolutions']}")
    print(f"Total Conflicts: {stats['total_conflicts']}")
    print(f"Resolution Rate: {stats['resolution_rate']:.2%}")
    print(f"Abstention Rate: {stats['abstention_rate']:.2%}")
    print(f"Average Confidence: {stats['average_confidence']:.2f}")
    print(f"Average Resolution Time: {stats['average_resolution_time_ms']:.0f} ms")
    
    print(f"\nResearch Metrics:")
    research_metrics = stats['research_metrics']
    print(f"  Hazara Conflicts: {research_metrics['hazara_conflicts']}")
    print(f"  SRO Conflicts: {research_metrics['sro_conflicts']}")
    print(f"  Cross-Jurisdictional: {research_metrics['cross_jurisdictional']}")
    print(f"  Successful Resolutions: {research_metrics['successful_resolutions']}")
    print(f"  Abstentions: {research_metrics['abstentions']}")
    
    print(f"\nConflict Types:")
    for conflict_type, count in stats['conflict_types'].items():
        print(f"  {conflict_type}: {count}")
    
    print(f"\nResolution Methods:")
    for method, count in stats['resolution_methods'].items():
        print(f"  {method}: {count}")
    
    print("\n" + "=" * 70)
    
    # Export authority network for Phase 6
    network = resolver.export_authority_network()
    print(f"\nAuthority Network for Phase 6 Graph Construction:")
    print(f"  Nodes: {len(network['nodes'])}")
    print(f"  Edges: {len(network['edges'])}")
    print(f"  Graph Type: {network['metadata']['graph_type']}")
    print(f"  Purpose: {network['metadata']['purpose']}")
    
    # Save research data for VIVA
    resolver.save_research_data("authority_research_data.json")
    print(f"\nResearch data saved to 'authority_research_data.json' for VIVA demonstration")
    
    print("\n" + "=" * 70)
    print("Enhanced Authority Hierarchy Resolver Test Complete ✓")
    print("Ready for Phase 6 Graph Construction and Phase 7 Quality Gates")

# =============================================================================
# COMPATIBILITY WRAPPER FOR RUN_SEQUENTIAL_PIPELINE.PY
# =============================================================================

class AuthorityHierarchy:
    """
    Compatibility wrapper for AuthorityHierarchyResolver to support 
    legacy calls from run_sequential_pipeline.py.
    """
    def __init__(self):
        self.resolver = AuthorityHierarchyResolver()
        
    def resolve_conflict(self, current_source: str, conflicting_sources: List[str]) -> Dict[str, Any]:
        """
        Adapter method to match run_sequential_pipeline.py's expectation.
        """
        # Convert string sources to Dicts as expected by Resolver
        sources_as_dicts = []
        for src in conflicting_sources:
            if isinstance(src, str):
                sources_as_dicts.append({
                    'title': src,
                    'authority': src, 
                    'confidence': 1.0
                })
            elif isinstance(src, dict):
                sources_as_dicts.append(src)
        
        # Call the actual resolver
        result = self.resolver.resolve_conflict(
            entity=current_source,
            conflicting_sources=sources_as_dicts
        )
        
        # Convert ResolutionResult to Dict
        result_dict = result.to_dict()
        
        # Add legacy fields if missing for pipeline compatibility
        if 'hierarchy_path' not in result_dict:
            if result.selected_source:
                 result_dict['hierarchy_path'] = [result.selected_source.authority_level.get_hierarchy_name()]
            else:
                 result_dict['hierarchy_path'] = []
                 
        return result_dict

# Alias AuthorityNode to LegalSource for compatibility
AuthorityNode = LegalSource
