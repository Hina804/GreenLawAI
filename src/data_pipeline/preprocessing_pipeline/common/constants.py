"""
CONSTANTS.PY - System Constants
"""
from enum import Enum

# KPK Specific Terms
KPK_CITIES = ["Peshawar", "Abbottabad", "Mardan", "Swat", "Kohat"]
FOREST_TYPES = ["Reserved", "Protected", "Guzara", "Private"]

# Legal Hierarchies
AUTHORITY_LEVELS = {
    "Federal": 100,
    "Provincial": 80,
    "Divisional": 60,
    "District": 40
}

# Regex Patterns
SECTION_PATTERN = r"Section\s+(\d+)"
ACT_PATTERN = r"Act\s+No\.\s+(\d+)"

class DocumentType(Enum):
    STATUTE = "statute"
    CIRCULAR = "circular"
    NOTIFICATION = "notification"
    WORKING_PLAN = "working_plan"
    RULE = "rule"
    UNKNOWN = "unknown"

class ProcessingStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ABSTAINED = "abstained"

class QualityThresholds:
    MIN_DOC_QUALITY = 0.5
    MIN_TEXT_LENGTH = 100
    MIN_RESTORATION_QUALITY = 0.6
    MIN_STRUCTURE_QUALITY = 0.5
    MIN_EXTRACTION_QUALITY = 0.5
    MIN_AUTHORITY_CONFIDENCE = 0.4

class ABSTENTION_REASONS:
    POOR_OCR_QUALITY = "poor_ocr_quality"
    INCOMPLETE_STRUCTURE = "incomplete_structure"
    AUTHORITY_CONFLICT = "authority_conflict"
    TEMPORAL_CONFLICT = "temporal_conflict"
    GRAPH_INTEGRITY_ISSUE = "graph_integrity_issue"
    QUALITY_CHECK_FAILED = "quality_check_failed"
    AMBIGUOUS_LEGAL_TERM = "ambiguous_legal_term"
    MISSING_JURISDICTION = "missing_jurisdiction"
