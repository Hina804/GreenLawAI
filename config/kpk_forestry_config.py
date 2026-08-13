"""
KPK FORESTRY CONFIGURATION - Single Source of Truth for Khyber Pakhtunkhwa Forestry System
This file contains ALL KPK-specific constants, patterns, and configurations.
"""

from typing import Dict, List, Set, Tuple, Any
from dataclasses import dataclass
from enum import Enum

# ============================================================================
# ENUMERATIONS
# ============================================================================

class KPKDocumentType(Enum):
    """Enhanced document types specific to KPK forestry"""
    STATUTE = "statute"                    # Forest Act 1927, KPK Ordinance 2002
    AMENDMENT = "amendment"                # Amendment Act 2022
    RULES = "rules"                        # Transport Rules 2004, Guzara Rules
    CIRCULAR = "circular"                  # Office Memorandums, S.R.O.s
    SOP = "sop"                            # Standard Operating Procedures
    WORKING_PLAN = "working_plan"          # 10-year Forest Division Plans
    POLICY = "policy"                      # Climate Change Policy 2022
    REPORT = "report"                      # Annual Reports, Assessment Reports
    FORM = "form"                          # FIR Forms, Permit Applications
    GAZETTE = "gazette"                    # Official Gazette Notifications
    MANUAL = "manual"                      # West Pakistan Forest Manual
    
class KPKJurisdiction(Enum):
    """Jurisdiction levels within KPK"""
    PROVINCIAL = "provincial"              # Applies to entire KPK
    DIVISION = "division"                  # Forest Division level
    REGION = "region"                      # Hazara, Malakand, etc.
    DISTRICT = "district"                  # District-specific rules
    BEAT = "beat"                          # Beat-level procedures

class TreeLegalStatus(Enum):
    """Legal status of tree species"""
    PROTECTED = "protected"                # Cannot be cut without special permission
    NON_PROTECTED = "non_protected"        # Can be cut with permit
    BANNED = "banned"                      # Complete prohibition
    ENDANGERED = "endangered"              # IUCN Red List species
    MEDICINAL = "medicinal"                # Protected for medicinal value

# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class TreeSpecies:
    """Complete information about a tree species"""
    common_name: str
    scientific_name: str
    local_names: Dict[str, str]            # {"pashto": "", "hindko": "", "urdu": ""}
    legal_status: TreeLegalStatus
    economic_value: str                    # "high", "medium", "low"
    typical_fine_amount: float             # Typical fine for illegal cutting (PKR)

@dataclass
class OfficerRank:
    """Forest Department hierarchy"""
    rank: str
    abbreviation: str
    authority_level: str                   # "provincial", "division", "range", "beat"
    typical_powers: List[str]
    reporting_to: str                      # Who they report to

@dataclass
class KPKForestDivision:
    """Forest Division information"""
    name: str
    code: str
    districts_covered: List[str]
    total_area_hectares: float
    forest_types: List[str]
    working_plan_period: str               # "2020-2030"

# ============================================================================
# CORE CONFIGURATION - EDIT HERE FOR UPDATES
# ============================================================================

# ----------------------------------------------------------------------------
# 1. KPK GOVERNMENT ENTITIES
# ----------------------------------------------------------------------------
KPK_GOVERNMENT_ENTITIES: Dict[str, Dict[str, Any]] = {
    "forest_department": {
        "full_name": "Khyber Pakhtunkhwa Forest Department",
        "abbreviation": "KPK FD",
        "hierarchy_keywords": ["Forest Department", "FD", "کا جنگلات محکمہ"],
        "sub_departments": ["Wildlife", "Climate Change Wing", "Planning & Development"]
    },
    "epa_kpk": {
        "full_name": "Environmental Protection Agency Khyber Pakhtunkhwa",
        "abbreviation": "EPA KPK", 
        "hierarchy_keywords": ["EPA", "Environmental Protection", "ماحولیاتی تحفظ"],
        "authority_source": "KPK Environmental Protection Act 2014"
    },
    "climate_change_wing": {
        "full_name": "Climate Change Wing, KPK Forest Department",
        "abbreviation": "CCW KPK",
        "hierarchy_keywords": ["Climate Change", "CCW", "موسمیاتی تبدیلی"],
        "established": "2020"
    }
}

# ----------------------------------------------------------------------------
# 2. FOREST OFFICER HIERARCHY (COMPLETE RANK STRUCTURE)
# ----------------------------------------------------------------------------
KPK_OFFICER_RANKS: List[OfficerRank] = [
    OfficerRank(
        rank="Chief Conservator of Forests",
        abbreviation="CCF",
        authority_level="provincial",
        typical_powers=["Policy making", "Budget approval", "Allocation of funds"],
        reporting_to="Secretary Forest"
    ),
    OfficerRank(
        rank="Conservator of Forests",
        abbreviation="CF",
        authority_level="regional",
        typical_powers=["Regional supervision", "Plan implementation", "Case review"],
        reporting_to="CCF"
    ),
    OfficerRank(
        rank="Divisional Forest Officer",
        abbreviation="DFO",
        authority_level="division", 
        typical_powers=["Timber marking", "Permit issuance", "FIR registration", "Auction supervision"],
        reporting_to="CF"
    ),
    OfficerRank(
        rank="Sub-Divisional Forest Officer", 
        abbreviation="SDFO",
        authority_level="subdivision",
        typical_powers=["Field inspections", "Report preparation", "Preliminary investigations"],
        reporting_to="DFO"
    ),
    OfficerRank(
        rank="Range Officer",
        abbreviation="RO",
        authority_level="range",
        typical_powers=["Beat supervision", "Patrolling", "Incident reporting", "Community meetings"],
        reporting_to="SDFO"
    ),
    OfficerRank(
        rank="Beat Guard",
        abbreviation="BG",
        authority_level="beat",
        typical_powers=["Daily patrolling", "Illegal activity detection", "First information report"],
        reporting_to="Range Officer"
    ),
    OfficerRank(
        rank="Forest Guard",
        abbreviation="FG",
        authority_level="beat",
        typical_powers=["Assist Beat Guard", "Surveillance", "Data collection"],
        reporting_to="Beat Guard"
    )
]

# ----------------------------------------------------------------------------
# 3. TREE SPECIES DATABASE (COMPLETE WITH LOCAL NAMES)
# ----------------------------------------------------------------------------
KPK_TREE_SPECIES: Dict[str, TreeSpecies] = {
    "deodar": TreeSpecies(
        common_name="Deodar Cedar",
        scientific_name="Cedrus deodara",
        local_names={
            "pashto": "دیار",
            "hindko": "دیار",
            "urdu": "دیار"
        },
        legal_status=TreeLegalStatus.PROTECTED,
        economic_value="very_high",
        typical_fine_amount=50000.0
    ),
    "chir_pine": TreeSpecies(
        common_name="Chir Pine",
        scientific_name="Pinus roxburghii",
        local_names={
            "pashto": "نښتر",
            "hindko": "چلغوزہ",
            "urdu": "چیر"
        },
        legal_status=TreeLegalStatus.NON_PROTECTED,
        economic_value="high",
        typical_fine_amount=20000.0
    ),
    "kail": TreeSpecies(
        common_name="Kail/Blue Pine",
        scientific_name="Pinus wallichiana",
        local_names={
            "pashto": "کایل",
            "hindko": "کایل",
            "urdu": "کائل"
        },
        legal_status=TreeLegalStatus.PROTECTED,
        economic_value="high",
        typical_fine_amount=30000.0
    ),
    "fir": TreeSpecies(
        common_name="Himalayan Fir",
        scientific_name="Abies pindrow",
        local_names={
            "pashto": "توت",
            "hindko": "راغ",
            "urdu": "راگھ"
        },
        legal_status=TreeLegalStatus.PROTECTED,
        economic_value="medium",
        typical_fine_amount=25000.0
    ),
    "spruce": TreeSpecies(
        common_name="Himalayan Spruce",
        scientific_name="Picea smithiana",
        local_names={
            "pashto": "روچ",
            "hindko": "روچ",
            "urdu": "روچ"
        },
        legal_status=TreeLegalStatus.PROTECTED,
        economic_value="medium",
        typical_fine_amount=25000.0
    ),
    "walnut": TreeSpecies(
        common_name="Walnut",
        scientific_name="Juglans regia",
        local_names={
            "pashto": "غوز",
            "hindko": "اخروٹ",
            "urdu": "اخروٹ"
        },
        legal_status=TreeLegalStatus.BANNED,
        economic_value="very_high",
        typical_fine_amount=100000.0
    )
}

# ----------------------------------------------------------------------------
# 4. FOREST DIVISIONS OF KPK
# ----------------------------------------------------------------------------
KPK_FOREST_DIVISIONS: Dict[str, KPKForestDivision] = {
    "abbottabad": KPKForestDivision(
        name="Abbottabad Forest Division",
        code="ABD",
        districts_covered=["Abbottabad", "Haripur"],
        total_area_hectares=125000.0,
        forest_types=["Subtropical Pine", "Temperate Coniferous"],
        working_plan_period="2020-2030"
    ),
    "mansehra": KPKForestDivision(
        name="Mansehra Forest Division",
        code="MSD",
        districts_covered=["Mansehra", "Torghar"],
        total_area_hectares=145000.0,
        forest_types=["Moist Temperate", "Alpine"],
        working_plan_period="2019-2029"
    ),
    "swat": KPKForestDivision(
        name="Swat Forest Division",
        code="SWD",
        districts_covered=["Swat", "Shangla"],
        total_area_hectares=185000.0,
        forest_types=["Deodar", "Chir Pine", "Blue Pine"],
        working_plan_period="2021-2031"
    ),
    "dir": KPKForestDivision(
        name="Dir Forest Division",
        code="DIR",
        districts_covered=["Upper Dir", "Lower Dir"],
        total_area_hectares=135000.0,
        forest_types=["Dry Temperate", "Subalpine"],
        working_plan_period="2018-2028"
    ),
    "malakand": KPKForestDivision(
        name="Malakand Forest Division",
        code="MLD",
        districts_covered=["Malakand", "Buner"],
        total_area_hectares=95000.0,
        forest_types=["Subtropical Chir Pine"],
        working_plan_period="2022-2032"
    ),
    "hazara": KPKForestDivision(
        name="Hazara Forest Division",
        code="HZD",
        districts_covered=["Mansehra", "Abbottabad", "Haripur", "Batagram"],
        total_area_hectares=210000.0,
        forest_types=["Mixed Coniferous", "Broadleaf"],
        working_plan_period="2017-2027"
    )
}

# ----------------------------------------------------------------------------
# 5. FOREST TYPES AND THEIR LEGAL DEFINITIONS
# ----------------------------------------------------------------------------
KPK_FOREST_TYPES: Dict[str, Dict[str, Any]] = {
    "reserved_forest": {
        "definition": "Forests declared as Reserved under Section 3 of Forest Act 1927",
        "legal_protection": "highest",
        "permits_required": ["special permit from CCF"],
        "keywords": ["Reserved Forest", "متحفظہ جنگل", "ریزروڈ فارسٹ"]
    },
    "protected_forest": {
        "definition": "Forests declared as Protected under Section 29 of Forest Act 1927",
        "legal_protection": "high",
        "permits_required": ["permit from DFO"],
        "keywords": ["Protected Forest", "محفوظ جنگل", "پروٹیکٹڈ فارسٹ"]
    },
    "guzara_forest": {
        "definition": "Forests assigned to village communities for subsistence use",
        "legal_protection": "medium",
        "permits_required": ["community permission", "range officer approval"],
        "keywords": ["Guzara Forest", "گزارہ جنگل", "گزارہ فارسٹ"]
    },
    "riverine_forest": {
        "definition": "Forests along river banks protected under KPK River Protection Ordinance 2002",
        "legal_protection": "very_high",
        "permits_required": ["EPA clearance", "forest department permit"],
        "keywords": ["Riverine Forest", "دریائی جنگل", "رورین فارسٹ"]
    }
}

# ----------------------------------------------------------------------------
# 6. DOCUMENT TYPE SIGNATURES (How to identify each document type)
# ----------------------------------------------------------------------------
KPK_DOCUMENT_SIGNATURES: Dict[KPKDocumentType, Dict[str, Any]] = {
    KPKDocumentType.STATUTE: {
        "patterns": [
            r"ACT\s+(?:No\.?\s*)?\w+\s+OF\s+\d{4}",
            r"THE\s+[A-Z\s]+ACT,\s*\d{4}",
            r"ordinance\s+no\.\s*\d+\s+of\s+\d{4}",
            r"WHEREAS\s+it\s+is\s+expedient"
        ],
        "metadata_fields": ["act_number", "year", "assent_date", "commencement_date"]
    },
    KPKDocumentType.AMENDMENT: {
        "patterns": [
            r"AMENDMENT\s+ACT\s+\d{4}",
            r"to\s+amend\s+the\s+[A-Z\s]+Act",
            r"Substituted\s+by",
            r"Inserted\s+by",
            r"Omitted\s+by"
        ],
        "metadata_fields": ["amends_act", "amendment_number", "effective_date"]
    },
    KPKDocumentType.RULES: {
        "patterns": [
            r"RULES\s+UNDER\s+SECTION\s+\d+",
            r"^KPK\s+[A-Z\s]+RULES,\s*\d{4}",
            r"made\s+by\s+the\s+Government",
            r"In\s+exercise\s+of\s+the\s+powers"
        ],
        "metadata_fields": ["parent_act", "rule_year", "gazette_notification"]
    },
    KPKDocumentType.CIRCULAR: {
        "patterns": [
            r"CIRCULAR\s+(?:No\.?\s*)?[A-Z0-9\/\-]+",
            r"OFFICE\s+MEMORANDUM",
            r"S\.R\.O\.\s*\d+",
            r"To\s+all\s+(?:DFOs|Officers)"
        ],
        "metadata_fields": ["circular_no", "subject", "issue_date", "distribution_list"]
    },
    KPKDocumentType.WORKING_PLAN: {
        "patterns": [
            r"WORKING\s+PLAN\s+FOR\s+[A-Z\s]+DIVISION",
            r"TEN\s+YEAR\s+MANAGEMENT\s+PLAN",
            r"COMPARTMENT\s+NO\.\s*\d+",
            r"SILVICULTURAL\s+PRESCRIPTIONS"
        ],
        "metadata_fields": ["division", "period", "compartment_count", "area_hectares"]
    },
    KPKDocumentType.FORM: {
        "patterns": [
            r"FORM\s+[A-Z0-9\-]+",
            r"APPLICATION\s+FORM",
            r"^\s*Name:\s*\_+",
            r"^\s*Date:\s*\_+",
            r"check\s+boxes?|tick\s+marks?"
        ],
        "metadata_fields": ["form_type", "form_number", "purpose", "issuing_authority"]
    }
}

# ----------------------------------------------------------------------------
# 7. REGEX PATTERNS FOR KPK-SPECIFIC EXTRACTION
# ----------------------------------------------------------------------------
KPK_EXTRACTION_PATTERNS: Dict[str, str] = {
    # Financial patterns
    "fine_amount": r"fine\s+of\s+Rs\.?\s*([\d,]+(?:\.\d{2})?)",
    "compensation_amount": r"compensation\s+of\s+Rs\.?\s*([\d,]+(?:\.\d{2})?)",
    "auction_rate": r"rate\s+of\s+Rs\.?\s*([\d,]+(?:\.\d{2})?)\s+per\s+(?:cubic\s+foot|ton|meter)",
    
    # Officer reference patterns
    "officer_reference": r"(DFO|SDFO|Range\s+Officer|Beat\s+Guard)\s+of\s+([A-Za-z\s]+)",
    
    # Geographic patterns
    "division_reference": r"(?:Division|Div\.)\s+([A-Za-z]+)",
    "range_reference": r"Range\s+([A-Za-z\s]+)",
    "beat_reference": r"Beat\s+([A-Za-z\s]+)",
    
    # Species in text
    "species_mention": r"\b(deodar|chir\s+pine|kail|fir|spruce|walnut)\b",
    
    # Amendment markers (CRITICAL)
    "amendment_marker": r"\[(\d+)\]\s*(Substituted|Inserted|Omitted|Deleted)\s+by\s+(.+?)(?=\n|\[)",
    
    # Gazette references
    "gazette_reference": r"Gazette\s+(?:of\s+)?(?:Pakistan|KPK|Khyber\s+Pakhtunkhwa)[^.]*?(?:Extraordinary)?[^.]*?(\d{1,2}\s+\w+\s+\d{4})",
    
    # Circular references
    "circular_reference": r"(?:Circular|Memorandum)\s+(?:No\.?\s*)?([A-Z0-9\/\-\.]+)",
    
    # Form references
    "form_reference": r"Form\s+([A-Z0-9\-]+)",
}

# ----------------------------------------------------------------------------
# 8. MULTILINGUAL TERM MAPPING
# ----------------------------------------------------------------------------
KPK_MULTILINGUAL_TERMS: Dict[str, Dict[str, str]] = {
    "forest": {
        "english": "forest",
        "urdu": "جنگل",
        "pashto": "ځنګل",
        "hindko": "جنگل"
    },
    "tree": {
        "english": "tree",
        "urdu": "درخت",
        "pashto": "ونه",
        "hindko": "رُک"
    },
    "officer": {
        "english": "officer",
        "urdu": "افسر",
        "pashto": "افسر",
        "hindko": "افسر"
    },
    "permit": {
        "english": "permit",
        "urdu": "اجازت نامہ",
        "pashto": "اجازت",
        "hindko": "پرمٹ"
    },
    "fine": {
        "english": "fine",
        "urdu": "جرمانہ",
        "pashto": "جریمه",
        "hindko": "جرمانہ"
    },
    "section": {
        "english": "section",
        "urdu": "دفعہ",
        "pashto": "ماده",
        "hindko": "سیکشن"
    },
    "act": {
        "english": "act",
        "urdu": "ایکٹ",
        "pashto": "قانون",
        "hindko": "ایکٹ"
    }
}

# ----------------------------------------------------------------------------
# 9. QUALITY VALIDATION RULES
# ----------------------------------------------------------------------------
KPK_QUALITY_RULES: Dict[str, List[str]] = {
    "must_have": [
        "kpk_jurisdiction_mentioned",  # Must mention KPK or Khyber Pakhtunkhwa
        "forest_related_terms",        # Must contain forest/tree/timber terms
        "legal_language_present",      # Shall/must/may/prohibited
    ],
    "should_have": [
        "officer_references",          # DFO, Range Officer, etc.
        "financial_terms",             # Fine, compensation, rate
        "geographic_references",       # Division, range, beat
    ],
    "nice_to_have": [
        "multilingual_terms",          # Urdu/Pashto terms present
        "amendment_markers",           # [1] Substituted by...
        "gazette_references",          # Gazette of Pakistan/KPK
    ]
}

# ----------------------------------------------------------------------------
# 10. PROCESSING CONFIGURATION
# ----------------------------------------------------------------------------
KPK_PROCESSING_CONFIG: Dict[str, Any] = {
    # OCR Configuration
    "ocr_languages": ["eng", "urd", "pus"],  # English, Urdu, Pashto
    "ocr_confidence_threshold": 60,
    
    # Normalization rules
    "preserve_multilingual_terms": True,
    "preserve_amendment_markers": True,
    "preserve_gazette_references": True,
    
    # Entity extraction
    "extract_financial_data": True,
    "extract_geographic_data": True,
    "extract_officer_data": True,
    "extract_species_data": True,
    
    # Version control
    "track_amendments": True,
    "build_version_history": True,
    
    # Output format
    "include_kpk_metadata": True,
    "include_multilingual_terms": True,
    "include_quality_score": True
}

# ----------------------------------------------------------------------------
# 11. UTILITY FUNCTIONS
# ----------------------------------------------------------------------------

def get_officer_hierarchy() -> List[Dict[str, str]]:
    """Returns officer hierarchy for display"""
    return [
        {"rank": rank.rank, "abbreviation": rank.abbreviation, "authority": rank.authority_level}
        for rank in KPK_OFFICER_RANKS
    ]

def get_species_by_status(status: TreeLegalStatus) -> List[str]:
    """Get all species with given legal status"""
    return [
        species.common_name 
        for species in KPK_TREE_SPECIES.values() 
        if species.legal_status == status
    ]

def get_division_by_district(district: str) -> List[str]:
    """Get forest divisions covering a district"""
    return [
        division.name
        for division in KPK_FOREST_DIVISIONS.values()
        if district.lower() in [d.lower() for d in division.districts_covered]
    ]

def is_kpk_document(text: str) -> bool:
    """Check if document is KPK-specific"""
    kpk_keywords = [
        "khyber pakhtunkhwa", "kpk", "north-west frontier",
        "پختونخوا", "خیبر", "سرحد"
    ]
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in kpk_keywords)

def get_document_type_signatures() -> Dict[str, List[str]]:
    """Get simplified document type patterns"""
    return {
        doc_type.value: signatures["patterns"]
        for doc_type, signatures in KPK_DOCUMENT_SIGNATURES.items()
    }

# ----------------------------------------------------------------------------
# 12. EXPORTS
# ----------------------------------------------------------------------------
__all__ = [
    # Enums
    "KPKDocumentType",
    "KPKJurisdiction", 
    "TreeLegalStatus",
    
    # Data classes
    "TreeSpecies",
    "OfficerRank",
    "KPKForestDivision",
    
    # Core configurations
    "KPK_GOVERNMENT_ENTITIES",
    "KPK_OFFICER_RANKS",
    "KPK_TREE_SPECIES", 
    "KPK_FOREST_DIVISIONS",
    "KPK_FOREST_TYPES",
    "KPK_DOCUMENT_SIGNATURES",
    "KPK_EXTRACTION_PATTERNS",
    "KPK_MULTILINGUAL_TERMS",
    "KPK_QUALITY_RULES",
    "KPK_PROCESSING_CONFIG",
    
    # Utility functions
    "get_officer_hierarchy",
    "get_species_by_status", 
    "get_division_by_district",
    "is_kpk_document",
    "get_document_type_signatures",
    
    # New Constants
    "KPK_LEGAL_HIERARCHY",
    "KPK_GAZETTE_PATTERNS",
    "KPK_AMENDMENT_KEYWORDS",
    "KPK_LEGAL_JURISDICTIONS",
    "KPK_CITATION_PATTERNS",
    "KPK_LEGAL_TERMS",
    "KPK_MULTILINGUAL_CITATIONS"
]

# ----------------------------------------------------------------------------
# 13. LEGAL HIERARCHY & ADDITIONAL PATTERNS
# ----------------------------------------------------------------------------
KPK_LEGAL_HIERARCHY = {
    'Federal': {
        'level': 1,
        'overrides': ['Provincial', 'Local'],
        'laws': ['Pakistan Forest Act 1927', 'Environmental Protection Act 1997']
    },
    'Provincial': {
        'level': 2,
        'overrides': ['Local'],
        'under': ['Federal'],
        'laws': ['KPK Forest Ordinance 2002', 'KPK Wildlife Act 2015']
    },
    'Local': {
        'level': 3,
        'under': ['Federal', 'Provincial'],
        'rules': ['Municipal bylaws', 'Local council rules']
    }
}

KPK_GAZETTE_PATTERNS = [
    r'Gazette of (?:Pakistan|KPK|Khyber Pakhtunkhwa)[^,]*?(?:No\.?\s*(\d+))?[^,]*?(\d{1,2}\s+\w+\s+\d{4})',
    r'سرکاری گزٹ[^,]*?(?:نمبر\s*(\d+))?[^,]*?(\d{1,2}\s+\w+\s+\d{4})',
    r'S\.R\.O\.\s*No\.?\s*(\d+/\d+)',
    r'ایس\s*آر\s*او\s*نمبر\s*(\d+/\d+)',
]

KPK_AMENDMENT_KEYWORDS = ["substituted", "inserted", "omitted", "deleted", "added", "amended", "repealed"]

KPK_LEGAL_JURISDICTIONS = ["Federal", "Provincial", "Local"]

KPK_CITATION_PATTERNS = [
    (r'(?:see|refer to|under|pursuant to)\s+(?:section|s\.)\s+(\d+[A-Z]?(?:-\d+)?(?:\(\d+\)(?:\(\w+\))?)?)', 'explicit_section'),
    (r'as\s+per\s+(?:sub-?section|clause)\s+\((\d+|\w+)\)', 'explicit_subsection'),
    (r'in\s+(?:subsection|clause)\s+\((\d+|\w+)\)', 'explicit_subsection'),
    (r'section\s+(\d+[A-Z]?)', 'implicit_section'),
    (r's\.\s*(\d+)', 'abbreviated_section'),
    (r'ss\.\s*(\d+)', 'abbreviated_subsection'),
    (r'(?:دیکھیں|ملاحظہ کریں|دیکھو)\s+(?:دفعہ|سیکشن)\s+(\d+)', 'urdu_explicit'),
    (r'دفعہ\s+(\d+)', 'urdu_implicit'),
    (r'ذیلی دفعہ\s+\((\d+|\w+)\)', 'urdu_subsection'),
    (r'شق\s+\((\d+|\w+)\)', 'urdu_clause')
]

KPK_LEGAL_TERMS = {
    "Act": ["ایکٹ", "قانون"],
    "Ordinance": ["آرڈیننس"],
    "Rule": ["قاعدہ", "قواعد"],
    "Section": ["دفعہ", "دفعات"],
    "Subsection": ["ذیلی دفعہ"],
    "Clause": ["شق"],
    "Schedule": ["شیڈول", "جدول"],
    "Notification": ["اعلامیہ", "نوٹیفکیشن"]
}

KPK_MULTILINGUAL_CITATIONS = True

# ============================================================================
# CONFIGURATION VALIDATION
# ============================================================================
if __name__ == "__main__":
    """Validate configuration on direct execution"""
    print("✅ KPK Forestry Configuration Loaded Successfully")
    print(f"   - Officer Ranks: {len(KPK_OFFICER_RANKS)}")
    print(f"   - Tree Species: {len(KPK_TREE_SPECIES)}")
    print(f"   - Forest Divisions: {len(KPK_FOREST_DIVISIONS)}")
    print(f"   - Document Types: {len(KPK_DOCUMENT_SIGNATURES)}")
    print(f"   - Extraction Patterns: {len(KPK_EXTRACTION_PATTERNS)}")
    print(f"   - Legal Hierarchy levels: {len(KPK_LEGAL_HIERARCHY)}")
    print(f"   - Citation Patterns: {len(KPK_CITATION_PATTERNS)}")
    print("\nConfiguration is ready for use in the preprocessing pipeline.")
