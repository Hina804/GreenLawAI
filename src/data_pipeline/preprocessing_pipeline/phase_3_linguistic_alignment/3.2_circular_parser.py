"""
ENHANCED CIRCULAR_PARSER.PY - KPK Forestry Circular & Notification Parser
WITH PIPELINE INTEGRATION AND GRAPH-RAG OPTIMIZATION

Key Enhancements:
1. PipelineState integration for flow tracking
2. Enhanced OCR error handling for circular-specific patterns
3. Graph schema mapping for Neo4j integration
4. RAG-optimized chunking for circular content
5. Abstention framework for uncertain parsing
6. Temporal relationship extraction for version control
7. Authority hierarchy mapping
8. Structured output for phase 4-6 processing
"""

import re
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set, Union
from datetime import datetime
from dataclasses import dataclass, asdict, field
import sys
from enum import Enum
import hashlib

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add common module path for pipeline integration
sys.path.append(str(Path(__file__).parent.parent / "common"))
try:
    from config import PipelineConfig
    from constants import ABSTENTION_REASONS
except ImportError:
    # Fallback if common modules not available
    class PipelineConfig:
        MIN_CIRCULAR_CONFIDENCE = 0.6
        MAX_CIRCULAR_CHUNKS = 50
    
    ABSTENTION_REASONS = {
        'low_confidence': 'Parsing confidence below threshold',
        'missing_metadata': 'Essential metadata not found',
        'ocr_quality': 'Poor OCR quality affecting parsing',
        'format_violation': 'Document format not recognized',
        'language_issue': 'Unsupported language mix'
    }


@dataclass
class PipelineState:
    """Enhanced pipeline state tracking"""
    doc_id: str
    phase: int = 3
    subphase: str = "3.2_circular_parser"
    status: str = "processing"
    metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    abstention_reasons: List[str] = field(default_factory=list)
    confidence: float = 1.0
    dependencies: List[str] = field(default_factory=list)  # Dependencies on other phases
    
    def add_abstention(self, reason: str, context: str = ""):
        self.abstention_reasons.append(f"{reason}: {context}")
        self.status = "abstained"
        self.confidence = 0.0
    
    def add_warning(self, warning: str):
        self.warnings.append(f"{datetime.now().isoformat()}: {warning}")
    
    def to_dict(self) -> Dict:
        return asdict(self)


class CircularType(Enum):
    """Enhanced circular types with Graph-RAG relevance"""
    CIRCULAR = {"code": "circular", "priority": 0.7, "requires_implementation": True}
    NOTIFICATION = {"code": "notification", "priority": 0.8, "requires_implementation": False}
    OFFICE_MEMORANDUM = {"code": "office_memo", "priority": 0.6, "requires_implementation": True}
    ORDER = {"code": "order", "priority": 0.9, "requires_implementation": True}
    LETTER = {"code": "letter", "priority": 0.4, "requires_implementation": False}
    INSTRUCTION = {"code": "instruction", "priority": 0.7, "requires_implementation": True}
    ADVISORY = {"code": "advisory", "priority": 0.5, "requires_implementation": False}
    REMINDER = {"code": "reminder", "priority": 0.4, "requires_implementation": False}
    AMENDMENT = {"code": "amendment", "priority": 0.8, "requires_implementation": True}
    CLARIFICATION = {"code": "clarification", "priority": 0.6, "requires_implementation": False}
    
    @property
    def graph_node_type(self) -> str:
        """Map circular type to Neo4j node type"""
        if self == CircularType.AMENDMENT:
            return "AmendmentCircular"
        elif self in [CircularType.ORDER, CircularType.INSTRUCTION]:
            return "Directive"
        elif self == CircularType.NOTIFICATION:
            return "Notification"
        else:
            return "Circular"


class PriorityLevel(Enum):
    """Enhanced priority levels with temporal implications"""
    IMMEDIATE = {"code": "immediate", "response_days": 1}
    URGENT = {"code": "urgent", "response_days": 3}
    ROUTINE = {"code": "routine", "response_days": 7}
    CONFIDENTIAL = {"code": "confidential", "response_days": None}
    RESTRICTED = {"code": "restricted", "response_days": None}
    
    @property
    def is_time_sensitive(self) -> bool:
        """Whether this priority implies time sensitivity"""
        return self in [PriorityLevel.IMMEDIATE, PriorityLevel.URGENT]


@dataclass
class TemporalRelationship:
    """Temporal relationships for version control"""
    supersedes: Optional[str] = None
    amended_by: Optional[str] = None
    clarifies: Optional[str] = None
    implements: Optional[str] = None
    referenced_by: List[str] = field(default_factory=list)
    
    def to_dict(self):
        return asdict(self)


@dataclass
class GraphSchemaMapping:
    """Mapping of circular data to Neo4j graph schema"""
    node_type: str
    node_properties: Dict[str, Any]
    relationships: List[Dict[str, Any]]
    
    def to_dict(self):
        return asdict(self)


@dataclass
class ReferenceInfo:
    """Enhanced reference information with graph relationships"""
    parent_circular: Optional[str] = None
    parent_notification: Optional[str] = None
    referenced_section: Optional[str] = None
    referenced_act: Optional[str] = None
    supersedes: Optional[str] = None
    amended_by: Optional[str] = None
    clarifies: Optional[str] = None
    implements: Optional[str] = None
    sro_references: List[str] = field(default_factory=list)
    gazette_references: List[str] = field(default_factory=list)
    
    def to_dict(self):
        return asdict(self)


@dataclass
class DistributionInfo:
    """Enhanced distribution with authority hierarchy"""
    primary_recipients: List[str]
    secondary_recipients: Optional[List[str]] = None
    for_information: Optional[List[str]] = None
    for_compliance: Optional[List[str]] = None
    for_implementation: Optional[List[str]] = None
    authority_hierarchy: Dict[str, List[str]] = field(default_factory=dict)
    
    def to_dict(self):
        return asdict(self)


@dataclass
class ComplianceInfo:
    """Enhanced compliance with enforcement tracking"""
    deadline: Optional[str] = None
    reporting_requirement: Optional[str] = None
    compliance_format: Optional[str] = None
    reporting_officer: Optional[str] = None
    submission_channel: Optional[str] = None
    enforcement_mechanism: Optional[str] = None
    penalty_clause: Optional[str] = None
    grace_period_days: Optional[int] = None
    
    def to_dict(self):
        return asdict(self)


@dataclass
class CircularMetadata:
    """Enhanced metadata with OCR quality tracking"""
    circular_number: str
    circular_type: CircularType
    subject: str
    issue_date: Optional[str] = None
    issuing_authority: Optional[str] = None
    issuing_department: Optional[str] = None
    priority: Optional[PriorityLevel] = None
    classification: Optional[str] = None
    pages: Optional[int] = None
    enclosures: Optional[List[str]] = None
    signature_authority: Optional[str] = None
    signature_designation: Optional[str] = None
    ocr_confidence: float = 1.0
    language_mix: Dict[str, float] = field(default_factory=dict)
    
    def to_dict(self):
        result = asdict(self)
        # Handle enums
        if self.circular_type:
            result['circular_type'] = self.circular_type.value
        if self.priority:
            result['priority'] = self.priority.value
        return result


@dataclass
class RAGChunk:
    """Optimized chunk for RAG retrieval"""
    chunk_id: str
    text: str
    chunk_type: str
    metadata: Dict[str, Any]
    embedding_context: List[str]
    legal_significance: float = 0.5
    contains_directives: bool = False
    language_distribution: Dict[str, float] = field(default_factory=dict)
    
    def to_dict(self):
        return asdict(self)


@dataclass
class CircularContent:
    """Enhanced content with RAG-optimized chunks"""
    preamble: Optional[str] = None
    body_sections: List[Dict[str, str]] = field(default_factory=list)
    directives: List[Dict[str, Any]] = field(default_factory=list)
    tables: List[Dict[str, Any]] = field(default_factory=list)
    annexures: List[Dict[str, Any]] = field(default_factory=list)
    concluding_remarks: Optional[str] = None
    rag_chunks: List[RAGChunk] = field(default_factory=list)
    
    def to_dict(self):
        return asdict(self)


@dataclass
class ParsedCircular:
    """Enhanced parsed circular with pipeline integration"""
    metadata: CircularMetadata
    references: ReferenceInfo
    distribution: DistributionInfo
    compliance: ComplianceInfo
    content: CircularContent
    extracted_entities: Dict[str, Any]
    pipeline_state: PipelineState
    temporal_relationships: TemporalRelationship
    graph_schema_mapping: Optional[GraphSchemaMapping] = None
    processing_metrics: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self):
        result = {
            "metadata": self.metadata.to_dict(),
            "references": self.references.to_dict(),
            "distribution": self.distribution.to_dict(),
            "compliance": self.compliance.to_dict(),
            "content": self.content.to_dict(),
            "extracted_entities": self.extracted_entities,
            "pipeline_state": self.pipeline_state.to_dict(),
            "temporal_relationships": self.temporal_relationships.to_dict(),
            "processing_metrics": self.processing_metrics
        }
        if self.graph_schema_mapping:
            result["graph_schema_mapping"] = self.graph_schema_mapping.to_dict()
        return result


class EnhancedKPFCircularParser:
    """
    Enhanced parser with pipeline integration and Graph-RAG optimization.
    """
    
    def __init__(self, pipeline_state: Optional[PipelineState] = None):
        self.pipeline_state = pipeline_state or PipelineState(
            doc_id="unknown",
            phase=3,
            subphase="3.2_circular_parser"
        )
        
        # OCR error patterns specific to circulars
        self.ocr_error_patterns = {
            # Common OCR errors in KPK circulars
            'f0rest': 'forest',
            'far est': 'forest',
            'fores t': 'forest',
            'De0dar': 'Deodar',
            'Kai1': 'Kail',
            'chi r': 'chir',
            'secti0n': 'section',
            'penaltyy': 'penalty',
            'جرم انہ': 'جرمانہ',
            'سی کشن': 'سیکشن',
            'فار سٹ': 'فارسٹ',
            'نوٹیفیکیشن': 'نوٹیفیکیشن',
            'سرکولر': 'سرکولر',
            'میمورنڈم': 'میمورنڈم',
        }
        
        # Enhanced circular number patterns with OCR awareness
        self.circular_number_patterns = [
            # Standard with OCR error handling
            r'(?:No\.|Number|N0\.|Numb3r)\s*[:=]?\s*([A-Z0-9\-\./]+(?:\s*\([^)]+\))?)',
            # With department and OCR errors
            r'(?:[A-Z]+)\s+(?:Circular|Circu1ar|Notification|N0tification)\s+(?:No\.|Number)\s*[:=]?\s*([A-Z0-9\-\./]+)',
            # Simple with OCR
            r'(?:Circular|Circu1ar|Notification|Memo|Mem0)\s+([A-Z0-9\-\./]+)',
            # S.R.O style with OCR
            r'(?:S\.R\.O\.|SRO|S\.R\.0\.)\s+([A-Z0-9\-\./]+)',
        ]
        
        # Enhanced date patterns with OCR
        self.date_patterns = [
            r'(?:Dated|Dat3d|Datad)\s*[:=]?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
            r'(?:Date|Dat3)\s*[:=]?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
            r'(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})',
            r'Issued\s+(?:on|0n)\s*[:=]?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
        ]
        
        # Authority hierarchy patterns
        self.authority_hierarchy = {
            "SECRETARY": ["ADDITIONAL_SECRETARY", "DEPUTY_SECRETARY", "SECTION_OFFICER"],
            "CONSERVATOR": ["DFO", "SDFO"],
            "DFO": ["RANGE_OFFICER", "BEAT_OFFICER"],
            "RANGE_OFFICER": ["BEAT_OFFICER", "FOREST_GUARD"],
        }
        
        # KPK-specific officer designations with abbreviations
        self.kpk_officer_designations = {
            "SECRETARY_FOREST": ["Secretary Forest", "سکریٹری فارسٹ"],
            "CONSERVATOR": ["Conservator", "کنسرویٹر"],
            "DFO": ["Divisional Forest Officer", "ڈویژنل فارسٹ آفیسر"],
            "SDFO": ["Sub-Divisional Forest Officer", "سب ڈویژنل فارسٹ آفیسر"],
            "RANGE_OFFICER": ["Range Forest Officer", "رینج فارسٹ آفیسر"],
            "BEAT_OFFICER": ["Beat Officer", "بیٹ آفیسر"],
            "FOREST_GUARD": ["Forest Guard", "فارسٹ گارڈ"],
        }
        
        # Legal significance patterns for RAG chunking
        self.legal_significance_patterns = {
            "high": [
                r'shall\s+(?:not|be|have)',
                r'must\s+(?:comply|submit|report)',
                r'penalty\s+of',
                r'fine\s+of\s+Rs\.',
                r'imprisonment',
                r'cancellation\s+of',
                r'suspension\s+of',
            ],
            "medium": [
                r'should\s+(?:ensure|verify)',
                r'are\s+requested\s+to',
                r'may\s+(?:apply|submit)',
                r'it\s+is\s+advisable',
                r'in\s+accordance\s+with',
            ],
            "low": [
                r'for\s+information',
                r'please\s+note',
                r'this\s+is\s+to',
                r'reference\s+is',
            ]
        }
        
        # Graph schema mapping patterns
        self.graph_relationship_patterns = {
            "AMENDS": [r'amends?\s+(?:circular|notification)', r'tamendment\s+to'],
            "SUPERSEDES": [r'supersedes?\s+(?:circular|notification)', r'replaces?\s+(?:the\s+)?previous'],
            "REFERENCES": [r'references?\s+(?:section|act)', r'in\s+accordance\s+with'],
            "IMPLEMENTS": [r'implements?\s+(?:act|policy)', r'gives\s+effect\s+to'],
            "CLARIFIES": [r'clarifies?\s+(?:provision|section)', r'explains?\s+(?:the\s+)?meaning'],
        }
        
        logger.info("Enhanced KPK Circular Parser initialized")
    
    def parse_circular(self, text: str, doc_type: str = "circular") -> ParsedCircular:
        """
        Enhanced main parsing function with pipeline integration.
        
        Args:
            text: Normalized text from the circular document
            doc_type: Document type from previous phase
            
        Returns:
            ParsedCircular object with all enhanced features
        """
        self.pipeline_state.metadata['doc_type'] = doc_type
        self.pipeline_state.metadata['input_length'] = len(text)
        
        logger.info(f"Starting enhanced circular parsing for {doc_type}")
        
        # Step 0: Pre-process with OCR correction
        cleaned_text, ocr_metrics = self._preprocess_with_ocr(text)
        
        # Step 1: Extract enhanced metadata
        metadata = self.extract_enhanced_metadata(cleaned_text)
        metadata.ocr_confidence = ocr_metrics.get('confidence', 1.0)
        
        # Step 2: Extract temporal relationships
        temporal_relationships = self.extract_temporal_relationships(cleaned_text)
        
        # Step 3: Extract enhanced references
        references = self.extract_enhanced_references(cleaned_text)
        
        # Step 4: Extract enhanced distribution with hierarchy
        distribution = self.extract_enhanced_distribution(cleaned_text)
        
        # Step 5: Extract enhanced compliance
        compliance = self.extract_enhanced_compliance(cleaned_text)
        
        # Step 6: Parse content with RAG optimization
        content = self.parse_enhanced_content(cleaned_text)
        
        # Step 7: Extract KPK-specific entities with authority mapping
        extracted_entities = self.extract_enhanced_kpk_entities(cleaned_text)
        
        # Step 8: Create graph schema mapping
        graph_mapping = self.create_graph_schema_mapping(
            metadata, references, distribution, compliance, content
        )
        
        # Step 9: Calculate processing metrics
        processing_metrics = self.calculate_processing_metrics(
            cleaned_text, metadata, references, distribution, compliance, content
        )
        
        # Step 10: Apply quality gates
        self.apply_circular_quality_gates(metadata, content, processing_metrics)
        
        # Step 11: Update pipeline state
        self.pipeline_state.confidence = processing_metrics.get('overall_confidence', 0.0)
        self.pipeline_state.metadata.update({
            'parsing_completed': datetime.now().isoformat(),
            'circular_number': metadata.circular_number,
            'circular_type': metadata.circular_type.name,
            'rag_chunks_generated': len(content.rag_chunks)
        })
        
        # Create final parsed circular
        parsed_circular = ParsedCircular(
            metadata=metadata,
            references=references,
            distribution=distribution,
            compliance=compliance,
            content=content,
            extracted_entities=extracted_entities,
            pipeline_state=self.pipeline_state,
            temporal_relationships=temporal_relationships,
            graph_schema_mapping=graph_mapping,
            processing_metrics=processing_metrics
        )
        
        logger.info(f"Enhanced circular parsing complete: {metadata.circular_number}")
        return parsed_circular
    
    def _preprocess_with_ocr(self, text: str) -> Tuple[str, Dict]:
        """Enhanced preprocessing with OCR error correction"""
        # Apply OCR corrections
        corrected_text = text
        corrections_applied = 0
        
        for error, correction in self.ocr_error_patterns.items():
            if error in corrected_text:
                corrected_text = corrected_text.replace(error, correction)
                corrections_applied += 1
        
        # Remove excessive whitespace but preserve paragraph structure
        lines = corrected_text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if line:
                # Clean up common OCR artifacts
                line = re.sub(r'\s+', ' ', line)  # Normalize spaces
                line = re.sub(r'[^\x00-\x7F]+', ' ', line)  # Remove non-ASCII chars
                cleaned_lines.append(line)
        
        cleaned_text = '\n\n'.join(cleaned_lines)  # Preserve paragraph breaks
        
        # Calculate OCR metrics
        ocr_metrics = {
            'original_length': len(text),
            'cleaned_length': len(cleaned_text),
            'corrections_applied': corrections_applied,
            'confidence': max(0.0, 1.0 - (corrections_applied / max(1, len(text.split())))),
            'ocr_errors_per_1000': (corrections_applied / max(1, len(text) / 1000))
        }
        
        return cleaned_text, ocr_metrics
    
    def extract_enhanced_metadata(self, text: str) -> CircularMetadata:
        """Extract enhanced metadata with OCR awareness"""
        # Extract circular number with fallback
        circular_number = self._extract_enhanced_circular_number(text)
        
        # Determine circular type with confidence
        circular_type = self._determine_enhanced_circular_type(text)
        
        # Extract subject with context
        subject = self._extract_enhanced_subject(text)
        
        # Extract date with validation
        issue_date = self._extract_enhanced_date(text)
        
        # Extract issuing authority with hierarchy
        issuing_authority = self._extract_enhanced_authority(text)
        
        # Extract issuing department with validation
        issuing_department = self._extract_enhanced_department(text)
        
        # Determine priority with time sensitivity
        priority = self._determine_enhanced_priority(text)
        
        # Extract classification
        classification = self._extract_enhanced_classification(text)
        
        # Extract page count
        pages = self._extract_enhanced_page_count(text)
        
        # Extract enclosures
        enclosures = self._extract_enhanced_enclosures(text)
        
        # Extract signature information with validation
        signature_info = self._extract_enhanced_signature_info(text)
        
        # Analyze language mix
        language_mix = self._analyze_language_mix(text)
        
        return CircularMetadata(
            circular_number=circular_number,
            circular_type=circular_type,
            subject=subject,
            issue_date=issue_date,
            issuing_authority=signature_info.get('authority') or issuing_authority,
            issuing_department=issuing_department,
            priority=priority,
            classification=classification,
            pages=pages,
            enclosures=enclosures,
            signature_authority=signature_info.get('authority'),
            signature_designation=signature_info.get('designation'),
            language_mix=language_mix
        )
    
    def extract_temporal_relationships(self, text: str) -> TemporalRelationship:
        """Extract temporal relationships for version control"""
        supersedes = None
        amended_by = None
        clarifies = None
        implements = None
        referenced_by = []
        
        # Check for supersession
        supersedes_patterns = [
            r'supersedes?\s+(?:Circular|Notification)\s+([A-Z0-9\-\./]+)',
            r'replaces?\s+(?:the\s+)?(?:previous\s+)?(?:Circular|Notification)\s+([A-Z0-9\-\./]+)',
            r'in\s+supersession\s+of\s+([A-Z0-9\-\./]+)',
        ]
        
        for pattern in supersedes_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                supersedes = match.group(1)
                break
        
        # Check for amendments
        amendment_patterns = [
            r'amended\s+by\s+(?:Circular|Notification)\s+([A-Z0-9\-\./]+)',
            r'amendment\s+vide\s+([A-Z0-9\-\./]+)',
            r'as\s+amended\s+by\s+([A-Z0-9\-\./]+)',
        ]
        
        for pattern in amendment_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amended_by = match.group(1)
                break
        
        # Check for clarifications
        clarify_patterns = [
            r'clarifies?\s+(?:Circular|Notification)\s+([A-Z0-9\-\./]+)',
            r'clarification\s+of\s+([A-Z0-9\-\./]+)',
            r'in\s+clarification\s+of\s+([A-Z0-9\-\./]+)',
        ]
        
        for pattern in clarify_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                clarifies = match.group(1)
                break
        
        # Check for implementation
        implement_patterns = [
            r'implements?\s+(?:Act|Ordinance)\s+([A-Z0-9\-\./]+)',
            r'for\s+implementation\s+of\s+([A-Z0-9\-\./]+)',
            r'gives?\s+effect\s+to\s+([A-Z0-9\-\./]+)',
        ]
        
        for pattern in implement_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                implements = match.group(1)
                break
        
        # Extract references to this circular (future relationships)
        reference_pattern = r'(?:Circular|Notification)\s+([A-Z0-9\-\./]+)\s+(?:dated|of)'
        referenced_by = re.findall(reference_pattern, text, re.IGNORECASE)
        
        return TemporalRelationship(
            supersedes=supersedes,
            amended_by=amended_by,
            clarifies=clarifies,
            implements=implements,
            referenced_by=list(set(referenced_by))  # Remove duplicates
        )
    
    def extract_enhanced_references(self, text: str) -> ReferenceInfo:
        """Extract enhanced reference information"""
        # First extract all reference patterns
        sro_references = re.findall(r'S\.?R\.?O\.?\s+([A-Z0-9\-\./]+)', text, re.IGNORECASE)
        gazette_references = re.findall(r'Gazette\s+([A-Z0-9\-\./]+)', text, re.IGNORECASE)
        
        # Extract section references with context
        section_refs = re.findall(r'Section\s+(\d+[A-Z]?(?:\s*\([^)]+\))?)', text, re.IGNORECASE)
        referenced_section = section_refs[0] if section_refs else None
        
        # Extract act references
        act_refs = re.findall(r'the\s+([A-Z][a-zA-Z\s]+Act,\s+\d{4})', text, re.IGNORECASE)
        referenced_act = act_refs[0] if act_refs else None
        
        # Extract parent references
        parent_patterns = [
            r'in\s+reference\s+to\s+(?:Circular|Notification)\s+([A-Z0-9\-\./]+)',
            r'Reference\s+(?:Circular|Notification)\s+([A-Z0-9\-\./]+)',
            r'Ref\.?\s+(?:Circular|Notification)\s+([A-Z0-9\-\./]+)',
        ]
        
        parent_circular = None
        parent_notification = None
        
        for pattern in parent_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                ref = match.group(1)
                if 'circular' in text[match.start():match.end()].lower():
                    parent_circular = ref
                else:
                    parent_notification = ref
                break
        
        return ReferenceInfo(
            parent_circular=parent_circular,
            parent_notification=parent_notification,
            referenced_section=referenced_section,
            referenced_act=referenced_act,
            sro_references=list(set(sro_references)),
            gazette_references=list(set(gazette_references))
        )
    
    def extract_enhanced_distribution(self, text: str) -> DistributionInfo:
        """Extract enhanced distribution with authority hierarchy"""
        primary_recipients = self._extract_enhanced_primary_recipients(text)
        secondary_recipients = self._extract_enhanced_secondary_recipients(text)
        for_information = self._extract_enhanced_for_information(text)
        for_compliance = self._extract_enhanced_for_compliance(text)
        for_implementation = self._extract_enhanced_for_implementation(text)
        
        # Build authority hierarchy
        authority_hierarchy = self._build_authority_hierarchy(
            primary_recipients + (secondary_recipients or []) +
            (for_information or []) + (for_compliance or []) +
            (for_implementation or [])
        )
        
        return DistributionInfo(
            primary_recipients=primary_recipients,
            secondary_recipients=secondary_recipients,
            for_information=for_information,
            for_compliance=for_compliance,
            for_implementation=for_implementation,
            authority_hierarchy=authority_hierarchy
        )
    
    def extract_enhanced_compliance(self, text: str) -> ComplianceInfo:
        """Extract enhanced compliance requirements"""
        deadline = self._extract_enhanced_deadline(text)
        reporting_requirement = self._extract_enhanced_reporting_requirement(text)
        compliance_format = self._extract_enhanced_compliance_format(text)
        reporting_officer = self._extract_enhanced_reporting_officer(text)
        submission_channel = self._extract_enhanced_submission_channel(text)
        enforcement_mechanism = self._extract_enforcement_mechanism(text)
        penalty_clause = self._extract_penalty_clause(text)
        grace_period_days = self._extract_grace_period(text)
        
        return ComplianceInfo(
            deadline=deadline,
            reporting_requirement=reporting_requirement,
            compliance_format=compliance_format,
            reporting_officer=reporting_officer,
            submission_channel=submission_channel,
            enforcement_mechanism=enforcement_mechanism,
            penalty_clause=penalty_clause,
            grace_period_days=grace_period_days
        )
    
    def parse_enhanced_content(self, text: str) -> CircularContent:
        """Parse enhanced content with RAG optimization"""
        # Extract traditional content components
        preamble = self._extract_enhanced_preamble(text)
        body_sections = self._extract_enhanced_body_sections(text)
        directives = self._extract_enhanced_directives(text)
        tables = self._extract_enhanced_tables(text)
        annexures = self._extract_enhanced_annexures(text)
        concluding_remarks = self._extract_enhanced_concluding_remarks(text)
        
        # Create RAG-optimized chunks
        rag_chunks = self._create_rag_optimized_chunks(
            text, preamble, body_sections, directives, tables, annexures
        )
        
        return CircularContent(
            preamble=preamble,
            body_sections=body_sections,
            directives=directives,
            tables=tables,
            annexures=annexures,
            concluding_remarks=concluding_remarks,
            rag_chunks=rag_chunks
        )
    
    def extract_enhanced_kpk_entities(self, text: str) -> Dict[str, Any]:
        """Extract enhanced KPK-specific entities"""
        entities = {
            "divisions": [],
            "ranges": [],
            "beats": [],
            "officers": [],
            "forest_types": [],
            "financial_terms": [],
            "species_mentioned": [],
            "locations": [],
            "authorities": [],
        }
        
        # Extract with enhanced patterns
        entities["divisions"] = self._extract_kpk_divisions(text)
        entities["ranges"] = self._extract_kpk_ranges(text)
        entities["beats"] = self._extract_kpk_beats(text)
        entities["officers"] = self._extract_kpk_officers(text)
        entities["forest_types"] = self._extract_forest_types(text)
        entities["financial_terms"] = self._extract_financial_terms(text)
        entities["species_mentioned"] = self._extract_species_mentioned(text)
        entities["locations"] = self._extract_locations(text)
        entities["authorities"] = self._extract_authorities(text)
        
        return entities
    
    def create_graph_schema_mapping(self, metadata: CircularMetadata,
                                   references: ReferenceInfo,
                                   distribution: DistributionInfo,
                                   compliance: ComplianceInfo,
                                   content: CircularContent) -> Optional[GraphSchemaMapping]:
        """Create Neo4j graph schema mapping for this circular"""
        if self.pipeline_state.status == "abstained":
            return None
        
        # Determine node type
        node_type = metadata.circular_type.graph_node_type
        
        # Build node properties
        node_properties = {
            "circular_id": metadata.circular_number,
            "subject": metadata.subject,
            "issue_date": metadata.issue_date,
            "issuing_authority": metadata.issuing_authority,
            "priority": metadata.priority.name if metadata.priority else None,
            "classification": metadata.classification,
            "directives_count": len(content.directives),
            "rag_chunks_count": len(content.rag_chunks),
            "parsing_confidence": self.pipeline_state.confidence,
            "timestamp": datetime.now().isoformat(),
        }
        
        # Build relationships
        relationships = []
        
        # Temporal relationships
        if references.supersedes:
            relationships.append({
                "type": "SUPERSEDES",
                "target": references.supersedes,
                "properties": {"relationship_type": "temporal"}
            })
        
        if references.amended_by:
            relationships.append({
                "type": "AMENDED_BY",
                "target": references.amended_by,
                "properties": {"relationship_type": "temporal"}
            })
        
        # Reference relationships
        if references.referenced_section:
            relationships.append({
                "type": "REFERENCES_SECTION",
                "target": references.referenced_section,
                "properties": {"reference_type": "section"}
            })
        
        if references.referenced_act:
            relationships.append({
                "type": "IMPLEMENTS",
                "target": references.referenced_act,
                "properties": {"reference_type": "act"}
            })
        
        # Distribution relationships
        for recipient in distribution.primary_recipients[:5]:  # Limit to 5
            relationships.append({
                "type": "ADDRESSED_TO",
                "target": recipient,
                "properties": {"distribution_type": "primary"}
            })
        
        # Content relationships
        for i, directive in enumerate(content.directives[:3]):
            relationships.append({
                "type": "CONTAINS_DIRECTIVE",
                "target": f"directive_{i}",
                "properties": {
                    "directive_type": directive.get("type"),
                    "has_deadline": bool(directive.get("deadline"))
                }
            })
        
        return GraphSchemaMapping(
            node_type=node_type,
            node_properties=node_properties,
            relationships=relationships
        )
    
    def calculate_processing_metrics(self, text: str, metadata: CircularMetadata,
                                    references: ReferenceInfo, distribution: DistributionInfo,
                                    compliance: ComplianceInfo, content: CircularContent) -> Dict[str, Any]:
        """Calculate comprehensive processing metrics"""
        metrics = {
            "text_metrics": {
                "length": len(text),
                "word_count": len(text.split()),
                "paragraph_count": text.count('\n\n') + 1,
            },
            "metadata_completeness": self._calculate_metadata_completeness(metadata),
            "parsing_coverage": self._calculate_parsing_coverage(
                metadata, references, distribution, compliance, content
            ),
            "rag_optimization": {
                "chunks_generated": len(content.rag_chunks),
                "avg_chunk_length": sum(len(c.text) for c in content.rag_chunks) / max(1, len(content.rag_chunks)),
                "chunks_with_directives": sum(1 for c in content.rag_chunks if c.contains_directives),
            },
            "entity_extraction": {
                "total_entities": sum(len(v) for v in content.extracted_entities.values()),
                "unique_entities": len(set().union(*[set(v) for v in content.extracted_entities.values() if isinstance(v, list)])),
            },
            "overall_confidence": self._calculate_overall_confidence(
                metadata, content, self.pipeline_state
            ),
        }
        
        return metrics
    
    def apply_circular_quality_gates(self, metadata: CircularMetadata,
                                    content: CircularContent, metrics: Dict[str, Any]):
        """Apply quality gates for circular parsing"""
        # Gate 1: Metadata completeness
        if metrics.get("metadata_completeness", 0) < 0.5:
            self.pipeline_state.add_abstention(
                "insufficient_metadata",
                f"Completeness: {metrics['metadata_completeness']:.2f}"
            )
        
        # Gate 2: OCR confidence
        if metadata.ocr_confidence < 0.7:
            self.pipeline_state.add_warning(
                f"Low OCR confidence: {metadata.ocr_confidence:.2f}"
            )
        
        # Gate 3: Essential fields missing
        if not metadata.circular_number or metadata.circular_number.startswith("UNKNOWN"):
            self.pipeline_state.add_warning("Circular number not properly extracted")
        
        if metadata.subject == "No Subject Found":
            self.pipeline_state.add_warning("Subject not properly extracted")
        
        # Gate 4: Too few directives for a circular
        if metadata.circular_type.requires_implementation and len(content.directives) == 0:
            self.pipeline_state.add_warning(
                f"No directives found for {metadata.circular_type.name} that requires implementation"
            )
        
        # Gate 5: RAG chunk quality
        rag_metrics = metrics.get("rag_optimization", {})
        if rag_metrics.get("chunks_generated", 0) == 0:
            self.pipeline_state.add_abstention(
                "no_rag_chunks",
                "Failed to generate RAG-optimized chunks"
            )
    
    # ========== Enhanced Helper Methods ==========
    
    def _extract_enhanced_circular_number(self, text: str) -> str:
        """Extract circular number with OCR correction"""
        for pattern in self.circular_number_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                number = match.group(1).strip()
                # Clean up OCR errors in the number itself
                number = re.sub(r'[Oo]', '0', number)  # Replace O/o with 0
                number = re.sub(r'[Il]', '1', number)  # Replace I/l with 1
                return number
        
        # Generate a hash-based identifier if no number found
        doc_hash = hashlib.md5(text.encode()).hexdigest()[:8].upper()
        return f"UNKNOWN-{doc_hash}"
    
    def _determine_enhanced_circular_type(self, text: str) -> CircularType:
        """Determine circular type with confidence"""
        text_upper = text.upper()
        
        # Check for specific patterns with priority
        type_patterns = [
            (r'S\.?R\.?O\.?\s+[IVXLCDM\d]', CircularType.NOTIFICATION, 0.9),
            (r'OFFICE\s+MEMORANDUM', CircularType.OFFICE_MEMORANDUM, 0.8),
            (r'GOVERNMENT\s+OF\s+KHYBER', CircularType.NOTIFICATION, 0.8),
            (r'ORDER\s+NO\.', CircularType.ORDER, 0.9),
            (r'AMENDMENT\s+TO', CircularType.AMENDMENT, 0.85),
            (r'CLARIFICATION\s+REGARDING', CircularType.CLARIFICATION, 0.8),
            (r'INSTRUCTION\s+(?:NO\.|NUMBER)', CircularType.INSTRUCTION, 0.8),
            (r'CIRCULAR\s+NO\.', CircularType.CIRCULAR, 0.7),
            (r'NOTIFICATION\s+NO\.', CircularType.NOTIFICATION, 0.7),
            (r'LETTER\s+NO\.', CircularType.LETTER, 0.6),
            (r'ADVISORY\s+ON', CircularType.ADVISORY, 0.5),
            (r'REMINDER\s+REGARDING', CircularType.REMINDER, 0.4),
        ]
        
        for pattern, circular_type, confidence in type_patterns:
            if re.search(pattern, text_upper):
                # Additional confidence check based on content
                if confidence >= 0.7 or 'TO:' in text_upper[:500]:
                    return circular_type
        
        # Default based on structural analysis
        if 'TO:' in text_upper and 'SUBJECT:' in text_upper:
            return CircularType.CIRCULAR
        elif 'GOVERNMENT OF KHYBER PAKHTUNKHWA' in text_upper:
            return CircularType.NOTIFICATION
        else:
            return CircularType.CIRCULAR
    
    def _extract_enhanced_subject(self, text: str) -> str:
        """Extract subject with context analysis"""
        # Try multiple patterns
        subject_patterns = [
            (r'Subject\s*[:=]\s*(.+?)(?=\n{2,}|\n[A-Z]{3,}|$)', re.IGNORECASE | re.DOTALL),
            (r'Re\s*[:=]\s*(.+?)(?=\n{2,}|\n[A-Z]{3,}|$)', re.IGNORECASE | re.DOTALL),
            (r'Regarding\s*[:=]\s*(.+?)(?=\n{2,}|\n[A-Z]{3,}|$)', re.IGNORECASE | re.DOTALL),
            (r'SUBJECT\s*[:=]\s*(.+?)(?=\n(?:CIRCULAR|NOTIFICATION|TO|REFERENCE))', re.DOTALL),
        ]
        
        for pattern, flags in subject_patterns:
            match = re.search(pattern, text, flags)
            if match:
                subject = match.group(1).strip()
                # Clean and truncate
                subject = re.sub(r'\s+', ' ', subject)
                if len(subject) > 200:
                    subject = subject[:197] + "..."
                return subject
        
        # Extract from first meaningful line after header
        lines = text.split('\n')
        for i, line in enumerate(lines[:10]):
            line = line.strip()
            if (len(line) > 20 and len(line) < 150 and 
                line[0].isupper() and any(c.islower() for c in line) and
                not any(keyword in line.upper() for keyword in 
                       ['CIRCULAR', 'NOTIFICATION', 'NO.', 'DATE', 'TO:'])):
                return line
        
        return "No Subject Found"
    
    def _extract_enhanced_date(self, text: str) -> Optional[str]:
        """Extract date with validation"""
        for pattern in self.date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                date_str = match.group(1).strip()
                # Normalize and validate
                try:
                    # Remove ordinal indicators
                    date_str = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str)
                    
                    # Try different formats
                    date_formats = [
                        '%d-%m-%Y', '%d/%m/%Y', '%d %B %Y',
                        '%d-%b-%Y', '%d/%b/%Y', '%B %d, %Y'
                    ]
                    
                    for fmt in date_formats:
                        try:
                            dt = datetime.strptime(date_str, fmt)
                            # Validate it's a reasonable date (not future and after 1900)
                            if dt.year >= 1900 and dt <= datetime.now():
                                return dt.strftime('%d-%m-%Y')
                        except ValueError:
                            continue
                    
                    # If parsing fails, return cleaned string
                    return date_str
                except:
                    return date_str
        
        return None
    
    def _extract_enhanced_authority(self, text: str) -> Optional[str]:
        """Extract issuing authority with hierarchy mapping"""
        authority_patterns = [
            r'Issued\s+by\s*[:=]\s*([A-Z][a-zA-Z\s,\.]+?)(?:\.|$)',
            r'Issuing\s+Authority\s*[:=]\s*([A-Z][a-zA-Z\s,\.]+?)(?:\.|$)',
            r'By\s+order\s+of\s*[:=]\s*([A-Z][a-zA-Z\s,\.]+?)(?:\.|$)',
            r'Signed\s+by\s*[:=]\s*([A-Z][a-zA-Z\s,\.]+?)(?:\.|$)',
        ]
        
        for pattern in authority_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                authority = match.group(1).strip()
                # Clean and map to standard designation
                for designation, variations in self.kpk_officer_designations.items():
                    for variation in variations:
                        if variation.lower() in authority.lower():
                            return variation
                return authority
        
        # Try to extract from signature section
        lines = text.split('\n')
        for i in range(max(0, len(lines)-10), len(lines)):
            line = lines[i].strip()
            for designation in self.kpk_officer_designations.keys():
                if designation in line.upper().replace(' ', '_'):
                    return line
        
        return None
    
    def _extract_enhanced_department(self, text: str) -> Optional[str]:
        """Extract issuing department with validation"""
        department_patterns = [
            r'Department\s+of\s+([A-Z][a-zA-Z\s]+?)(?:\.|$)',
            r'([A-Z][a-zA-Z\s]+?)\s+Department(?:\.|$)',
            r'Forest\s+Department\s*[:=]\s*([A-Z][a-zA-Z\s]*?)(?:\.|$)',
            r'Government\s+of\s+Khyber\s+Pakhtunkhwa,\s+([A-Z][a-zA-Z\s]+?)(?:\.|$)',
        ]
        
        for pattern in department_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                department = match.group(1).strip()
                # Validate against known KPK departments
                valid_departments = ['Forest', 'Wildlife', 'Environment', 'Agriculture']
                if any(dept.lower() in department.lower() for dept in valid_departments):
                    return department
        
        return None
    
    def _determine_enhanced_priority(self, text: str) -> Optional[PriorityLevel]:
        """Determine priority level with context"""
        text_upper = text.upper()
        
        priority_mapping = {
            PriorityLevel.IMMEDIATE: ['IMMEDIATE', 'MOST URGENT', 'ACTION TODAY', 'WITHIN 24 HOURS'],
            PriorityLevel.URGENT: ['URGENT', 'EXPEDITE', 'PRIORITY', 'WITHIN 3 DAYS'],
            PriorityLevel.ROUTINE: ['ROUTINE', 'NORMAL', 'REGULAR', 'WITHIN 7 DAYS'],
            PriorityLevel.CONFIDENTIAL: ['CONFIDENTIAL', 'RESTRICTED', 'SECRET'],
            PriorityLevel.RESTRICTED: ['FOR OFFICIAL USE ONLY', 'INTERNAL', 'LIMITED DISTRIBUTION'],
        }
        
        for priority_level, keywords in priority_mapping.items():
            for keyword in keywords:
                if keyword in text_upper:
                    return priority_level
        
        # Infer from deadline if present
        if re.search(r'within\s+(?:24|48)\s+hours', text_upper):
            return PriorityLevel.IMMEDIATE
        elif re.search(r'within\s+\d+\s+days', text_upper):
            days_match = re.search(r'within\s+(\d+)\s+days', text_upper)
            if days_match:
                days = int(days_match.group(1))
                if days <= 3:
                    return PriorityLevel.URGENT
                elif days <= 7:
                    return PriorityLevel.ROUTINE
        
        return None
    
    def _extract_enhanced_classification(self, text: str) -> Optional[str]:
        """Extract classification with validation"""
        classification_patterns = [
            r'CLASSIFICATION\s*[:=]\s*([A-Z][a-zA-Z\s]+?)(?:\.|$)',
            r'CATEGORY\s*[:=]\s*([A-Z][a-zA-Z\s]+?)(?:\.|$)',
            r'This\s+is\s+a\s+([a-z]+)\s+document',
        ]
        
        for pattern in classification_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                classification = match.group(1).strip().upper()
                # Map to standard classifications
                standard_classifications = ['CONFIDENTIAL', 'RESTRICTED', 'UNCLASSIFIED', 'PUBLIC']
                for std in standard_classifications:
                    if std in classification:
                        return std
                return classification
        
        return None
    
    def _extract_enhanced_page_count(self, text: str) -> Optional[int]:
        """Extract page count with validation"""
        page_patterns = [
            r'Pages?\s*[:=]\s*(\d+)',
            r'(\d+)\s+pages?',
            r'Enclosures?\s*[:=]\s*\d+\s*\((\d+)\s+pages?\)',
        ]
        
        for pattern in page_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    pages = int(match.group(1))
                    if 1 <= pages <= 1000:  # Reasonable range
                        return pages
                except ValueError:
                    pass
        
        # Estimate from text length (assuming ~500 words per page)
        word_count = len(text.split())
        estimated_pages = max(1, word_count // 500)
        return estimated_pages
    
    def _extract_enhanced_enclosures(self, text: str) -> Optional[List[str]]:
        """Extract enclosure list with validation"""
        enclosure_patterns = [
            r'Enclosures?\s*[:=]\s*(.+?)(?=\n{2,}|\n[A-Z]{3,}|$)',
            r'Annexures?\s*[:=]\s*(.+?)(?=\n{2,}|\n[A-Z]{3,}|$)',
            r'Attachments?\s*[:=]\s*(.+?)(?=\n{2,}|\n[A-Z]{3,}|$)',
        ]
        
        for pattern in enclosure_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                enclosures_text = match.group(1).strip()
                # Split and clean
                enclosures = re.split(r'[,;]|\d+\.', enclosures_text)
                enclosures = [e.strip() for e in enclosures if e.strip()]
                # Remove common false positives
                enclosures = [e for e in enclosures if len(e) > 3 and not e.upper() in ['NONE', 'NIL', 'NA']]
                return enclosures if enclosures else None
        
        return None
    
    def _extract_enhanced_signature_info(self, text: str) -> Dict[str, Optional[str]]:
        """Extract enhanced signature information"""
        result = {"authority": None, "designation": None}
        
        # Look for signature block (last 30 lines)
        lines = text.split('\n')
        signature_lines = []
        
        for i in range(max(0, len(lines)-30), len(lines)):
            line = lines[i].strip()
            if line and (any(word in line.upper() for word in 
                           ['SIGNED', 'APPROVED', 'AUTHORIZED', 'NAME', 'DESIGNATION']) or
                        any(title in line.upper() for title in 
                           ['DFO', 'SDFO', 'OFFICER', 'DIRECTOR', 'SECRETARY'])):
                signature_lines.append(line)
        
        if signature_lines:
            # Try to extract name and designation
            for line in signature_lines:
                # Look for name (Title Case with at least 2 words)
                name_match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})', line)
                if name_match and len(name_match.group(1).split()) >= 2:
                    result["authority"] = name_match.group(1)
                
                # Look for designation
                for designation, variations in self.kpk_officer_designations.items():
                    for variation in variations:
                        if variation.lower() in line.lower():
                            result["designation"] = variation
                            break
                    if result["designation"]:
                        break
        
        return result
    
    def _analyze_language_mix(self, text: str) -> Dict[str, float]:
        """Analyze language distribution in text"""
        # Simple language detection (enhance with proper NLP if available)
        urdu_pattern = re.compile(r'[\u0600-\u06FF]')
        english_pattern = re.compile(r'[A-Za-z]')
        pashto_pattern = re.compile(r'[\u069A-\u06FF]')  # Pashto specific
        
        urdu_chars = len(urdu_pattern.findall(text))
        english_chars = len(english_pattern.findall(text))
        pashto_chars = len(pashto_pattern.findall(text))
        total_chars = urdu_chars + english_chars + pashto_chars
        
        if total_chars == 0:
            return {"english": 1.0}
        
        return {
            "urdu": urdu_chars / total_chars,
            "english": english_chars / total_chars,
            "pashto": pashto_chars / total_chars
        }
    
    def _extract_enhanced_primary_recipients(self, text: str) -> List[str]:
        """Extract primary recipients with standardization"""
        to_pattern = r'To\s*[:=]\s*(.+?)(?=\n{2,}|\n(?:Copy|For|Subject|$))'
        match = re.search(to_pattern, text, re.IGNORECASE | re.DOTALL)
        
        if match:
            recipients_text = match.group(1).strip()
            recipients = self._parse_enhanced_recipients_list(recipients_text)
            # Standardize recipients
            standardized = []
            for recipient in recipients:
                # Map to standard designations
                for designation, variations in self.kpk_officer_designations.items():
                    for variation in variations:
                        if variation.lower() in recipient.lower():
                            standardized.append(variation)
                            break
                else:
                    standardized.append(recipient)
            return standardized
        
        return []
    
    def _extract_enhanced_secondary_recipients(self, text: str) -> Optional[List[str]]:
        """Extract secondary recipients"""
        copy_pattern = r'Copy\s+(?:To|to)\s*[:=]\s*(.+?)(?=\n{2,}|\n(?:For|Subject|$))'
        match = re.search(copy_pattern, text, re.IGNORECASE | re.DOTALL)
        
        if match:
            recipients_text = match.group(1).strip()
            return self._parse_enhanced_recipients_list(recipients_text)
        
        return None
    
    def _extract_enhanced_for_information(self, text: str) -> Optional[List[str]]:
        """Extract 'For Information' recipients"""
        return self._extract_info_compliance_recipients(text, 'information')
    
    def _extract_enhanced_for_compliance(self, text: str) -> Optional[List[str]]:
        """Extract 'For Compliance' recipients"""
        return self._extract_info_compliance_recipients(text, 'compliance')
    
    def _extract_enhanced_for_implementation(self, text: str) -> Optional[List[str]]:
        """Extract 'For Implementation' recipients"""
        return self._extract_info_compliance_recipients(text, 'implementation')
    
    def _extract_info_compliance_recipients(self, text: str, type_key: str) -> Optional[List[str]]:
        """Extract recipients for information/compliance/implementation"""
        patterns = {
            'information': r'For\s+information\s*[:=]\s*(.+?)(?=\n{2,}|\n[A-Z]{3,}|$)',
            'compliance': r'For\s+compliance\s*[:=]\s*(.+?)(?=\n{2,}|\n[A-Z]{3,}|$)',
            'implementation': r'For\s+implementation\s*[:=]\s*(.+?)(?=\n{2,}|\n[A-Z]{3,}|$)',
        }
        
        pattern = patterns.get(type_key)
        if pattern:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                recipients_text = match.group(1).strip()
                recipients = self._parse_enhanced_recipients_list(recipients_text)
                return recipients if recipients else None
        
        return None
    
    def _parse_enhanced_recipients_list(self, text: str) -> List[str]:
        """Parse recipients list with standardization"""
        # Split by common delimiters
        parts = re.split(r'[,;]|\n', text)
        recipients = []
        
        for part in parts:
            part = part.strip()
            if part and part.upper() != 'ALL':
                # Clean and standardize
                recipient = re.sub(r'^[\.\-\s]+|[\.\-\s]+$', '', part)
                # Remove common prefixes
                recipient = re.sub(r'^(?:The\s+)?', '', recipient, flags=re.IGNORECASE)
                # Capitalize properly
                recipient = ' '.join(word.capitalize() for word in recipient.split())
                
                if recipient and len(recipient) > 2:
                    recipients.append(recipient)
        
        return list(set(recipients))  # Remove duplicates
    
    def _build_authority_hierarchy(self, recipients: List[str]) -> Dict[str, List[str]]:
        """Build authority hierarchy from recipients"""
        hierarchy = {}
        
        for recipient in recipients:
            # Determine level in hierarchy
            level = None
            for designation, variations in self.kpk_officer_designations.items():
                for variation in variations:
                    if variation.lower() in recipient.lower():
                        level = designation
                        break
                if level:
                    break
            
            if level:
                if level not in hierarchy:
                    hierarchy[level] = []
                hierarchy[level].append(recipient)
        
        return hierarchy
    
    def _extract_enhanced_deadline(self, text: str) -> Optional[str]:
        """Extract deadline with context"""
        deadline_patterns = [
            r'within\s+(\d+)\s+(?:days|weeks|months|hours)',
            r'by\s+(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
            r'not\s+later\s+than\s+(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
            r'deadline\s*[:=]\s*(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
            r'to\s+be\s+complied\s+with\s+by\s+(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
        ]
        
        for pattern in deadline_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                deadline = match.group(1).strip()
                # Try to format if it's a date
                if re.match(r'\d{1,2}[-/]\d{1,2}[-/]\d{4}', deadline):
                    try:
                        for fmt in ['%d-%m-%Y', '%d/%m/%Y']:
                            try:
                                dt = datetime.strptime(deadline, fmt)
                                return dt.strftime('%d-%m-%Y')
                            except ValueError:
                                continue
                    except:
                        pass
                return deadline
        
        return None
    
    def _extract_enhanced_reporting_requirement(self, text: str) -> Optional[str]:
        """Extract reporting requirements"""
        reporting_patterns = [
            r'report\s+(?:should|must|shall)\s+be\s+submitted\s+(.+?)(?=\.|$)',
            r'submit\s+a\s+report\s+(.+?)(?=\.|$)',
            r'furnish\s+(?:a\s+)?report\s+(.+?)(?=\.|$)',
            r'reporting\s+requirement\s*[:=]\s*(.+?)(?=\.|$)',
        ]
        
        for pattern in reporting_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_enhanced_compliance_format(self, text: str) -> Optional[str]:
        """Extract compliance format"""
        format_patterns = [
            r'in\s+the\s+prescribed\s+form',
            r'using\s+Form\s+([A-Z0-9\-]+)',
            r'as\s+per\s+proforma',
            r'in\s+(?:duplicate|triplicate|quadruplicate)',
            r'format\s*[:=]\s*(.+?)(?=\.|$)',
        ]
        
        for pattern in format_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if len(match.groups()) > 0 and match.group(1):
                    return f"Form {match.group(1)}"
                else:
                    return pattern.split()[-1]  # Last word of pattern
        
        return None
    
    def _extract_enhanced_reporting_officer(self, text: str) -> Optional[str]:
        """Extract reporting officer"""
        officer_patterns = [
            r'to\s+the\s+([A-Z][a-zA-Z\s]+Officer)',
            r'through\s+([A-Z][a-zA-Z\s]+Officer)',
            r'submit\s+to\s+([A-Z][a-zA-Z\s]+)',
            r'report\s+to\s+([A-Z][a-zA-Z\s]+)',
        ]
        
        for pattern in officer_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                officer = match.group(1).strip()
                # Map to standard designation
                for designation, variations in self.kpk_officer_designations.items():
                    for variation in variations:
                        if variation.lower() in officer.lower():
                            return variation
                return officer
        
        return None
    
    def _extract_enhanced_submission_channel(self, text: str) -> Optional[str]:
        """Extract submission channel"""
        channel_patterns = [
            r'by\s+email\s+to\s+([\w\.@]+)',
            r'to\s+the\s+email\s+([\w\.@]+)',
            r'through\s+proper\s+channel',
            r'by\s+registered\s+post',
            r'personally\s+to',
            r'fax\s+to\s+(\d+)',
        ]
        
        for pattern in channel_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if len(match.groups()) > 0 and match.group(1):
                    return match.group(1).strip()
        
        return None
    
    def _extract_enforcement_mechanism(self, text: str) -> Optional[str]:
        """Extract enforcement mechanism"""
        enforcement_patterns = [
            r'failure\s+to\s+comply\s+will\s+result\s+in\s+(.+?)(?=\.|$)',
            r'non-compliance\s+may\s+lead\s+to\s+(.+?)(?=\.|$)',
            r'enforcement\s+mechanism\s*[:=]\s*(.+?)(?=\.|$)',
            r'penalty\s+for\s+non-compliance\s+is\s+(.+?)(?=\.|$)',
        ]
        
        for pattern in enforcement_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_penalty_clause(self, text: str) -> Optional[str]:
        """Extract penalty clause"""
        penalty_patterns = [
            r'penalty\s+of\s+(?:Rs\.|rupees)\s*([\d,]+\.?\d*)(?:\s*(?:or|and)\s*.+?)?(?=\.|$)',
            r'fine\s+of\s+(?:Rs\.|rupees)\s*([\d,]+\.?\d*)(?:\s*.+?)?(?=\.|$)',
            r'penalty\s+clause\s*[:=]\s*(.+?)(?=\.|$)',
        ]
        
        for pattern in penalty_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if len(match.groups()) > 0 and match.group(1):
                    return f"Rs. {match.group(1)}"
                else:
                    return match.group(0)
        
        return None
    
    def _extract_grace_period(self, text: str) -> Optional[int]:
        """Extract grace period in days"""
        grace_patterns = [
            r'grace\s+period\s+of\s+(\d+)\s+days',
            r'within\s+(\d+)\s+days\s+of\s+receipt',
            r'(\d+)\s+day\s+grace\s+period',
        ]
        
        for pattern in grace_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    pass
        
        return None
    
    def _extract_enhanced_preamble(self, text: str) -> Optional[str]:
        """Extract enhanced preamble"""
        lines = text.split('\n')
        preamble_lines = []
        
        # Skip metadata lines
        skip_patterns = [
            r'^\s*(?:CIRCULAR|NOTIFICATION|MEMO|LETTER|ORDER)\s*',
            r'^\s*(?:No\.|Number|Date|Dated|Subject|To|Copy|Reference|Issued)',
            r'^\s*$',
        ]
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            
            if any(re.match(pattern, line_stripped, re.IGNORECASE) for pattern in skip_patterns):
                continue
            
            preamble_lines.append(line)
            
            # Stop when we hit a directive or section header
            if (re.search(r'shall|must|are\s+directed|are\s+instructed', line_stripped, re.IGNORECASE) or
                re.match(r'^\s*\d+\.\s+[A-Z]', line_stripped)):
                break
        
        preamble = ' '.join(preamble_lines).strip()
        return preamble if preamble else None
    
    def _extract_enhanced_body_sections(self, text: str) -> List[Dict[str, str]]:
        """Extract enhanced body sections"""
        sections = []
        lines = text.split('\n')
        current_section = None
        current_content = []
        
        for line in lines:
            line_stripped = line.strip()
            
            # Check if this is a section header
            is_header = (re.match(r'^\s*\d+\.\s+[A-Z][^a-z]*$', line_stripped) or
                        re.match(r'^\s*[A-Z][A-Z\s]{5,50}$', line_stripped) or
                        re.match(r'^\s*\d+\.\d+\s+[A-Z][^\.]*$', line_stripped))
            
            if is_header:
                if current_section is not None and current_content:
                    sections.append({
                        "header": current_section,
                        "content": ' '.join(current_content).strip()
                    })
                
                current_section = line_stripped
                current_content = []
            elif current_section is not None:
                if line_stripped:
                    current_content.append(line_stripped)
        
        if current_section is not None and current_content:
            sections.append({
                "header": current_section,
                "content": ' '.join(current_content).strip()
            })
        
        return sections
    
    def _extract_enhanced_directives(self, text: str) -> List[Dict[str, Any]]:
        """Extract enhanced directives"""
        directives = []
        
        directive_patterns = [
            r'([A-Z][^\.!?]*?(?:shall|must|are\s+directed|are\s+instructed|should|are\s+required)[^\.!?]*[\.!?])',
            r'Directive\s*[:=]\s*(.+?)(?=\n{2,}|$)',
            r'Instruction\s*[:=]\s*(.+?)(?=\n{2,}|$)',
            r'It\s+is\s+(?:hereby\s+)?(?:directed|instructed|ordered)\s+that\s+(.+?)(?=\.|$)',
        ]
        
        for pattern in directive_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, str):
                    directive_text = match.strip()
                elif isinstance(match, tuple) and match:
                    directive_text = match[0].strip() if match[0] else match[1].strip() if len(match) > 1 else ""
                else:
                    continue
                
                if directive_text:
                    # Classify directive
                    directive_type = "instruction"
                    if 'shall' in directive_text.lower() or 'must' in directive_text.lower():
                        directive_type = "mandatory"
                    elif 'should' in directive_text.lower() or 'are requested to' in directive_text.lower():
                        directive_type = "advisory"
                    
                    # Extract legal significance
                    legal_significance = 0.5
                    for significance_level, patterns in self.legal_significance_patterns.items():
                        for sig_pattern in patterns:
                            if re.search(sig_pattern, directive_text, re.IGNORECASE):
                                if significance_level == "high":
                                    legal_significance = 0.9
                                elif significance_level == "medium":
                                    legal_significance = 0.7
                                break
                    
                    # Extract deadline
                    deadline = None
                    for deadline_pattern in self.deadline_patterns:
                        deadline_match = re.search(deadline_pattern, directive_text, re.IGNORECASE)
                        if deadline_match:
                            deadline = deadline_match.group(1)
                            break
                    
                    directives.append({
                        "text": directive_text,
                        "type": directive_type,
                        "legal_significance": legal_significance,
                        "deadline": deadline,
                        "has_compliance": bool(deadline) or 'report' in directive_text.lower() or 'submit' in directive_text.lower(),
                        "language_distribution": self._analyze_language_mix(directive_text)
                    })
        
        return directives
    
    def _extract_enhanced_tables(self, text: str) -> List[Dict[str, Any]]:
        """Extract enhanced tables"""
        tables = []
        
        table_patterns = [
            r'TABLE\s+[IVXLCDM\d]+\s*\n(?:.+\n){3,}',
            r'\n\s*(?:\||\+-)[\s\S]+?(?:\n{2,}|\n[A-Z])',
            r'^\s*\d+\s+[\w\s]+\s+\d+\s*$',
        ]
        
        for pattern in table_patterns:
            matches = re.finditer(pattern, text, re.MULTILINE)
            for match in matches:
                table_text = match.group(0).strip()
                
                rows = table_text.split('\n')
                if len(rows) >= 3:
                    header_row = None
                    data_rows = []
                    
                    for i, row in enumerate(rows):
                        row = row.strip()
                        if row:
                            if row.isupper() and len(row.split()) <= 10:
                                header_row = row
                            elif i > 0:
                                data_rows.append(row)
                    
                    tables.append({
                        "raw_text": table_text[:500],
                        "has_header": header_row is not None,
                        "row_count": len(data_rows),
                        "type": self._classify_enhanced_table(table_text),
                        "contains_financial_data": 'Rs.' in table_text or 'rupees' in table_text.lower()
                    })
        
        return tables
    
    def _classify_enhanced_table(self, table_text: str) -> str:
        """Classify enhanced table type"""
        table_text_lower = table_text.lower()
        
        if any(word in table_text_lower for word in ['rate', 'price', 'fee', 'charge', 'cost']):
            return "rate_chart"
        elif any(word in table_text_lower for word in ['form', 'application', 'proforma']):
            return "form_template"
        elif any(word in table_text_lower for word in ['inventory', 'stock', 'quantity']):
            return "inventory"
        elif any(word in table_text_lower for word in ['schedule', 'timetable', 'calendar']):
            return "schedule"
        elif any(word in table_text_lower for word in ['penalty', 'fine', 'punishment']):
            return "penalty_schedule"
        else:
            return "data_table"
    
    def _extract_enhanced_annexures(self, text: str) -> List[Dict[str, Any]]:
        """Extract enhanced annexures"""
        annexures = []
        
        annexure_patterns = [
            r'ANNEXURE\s+([IVXLCDM]+)\s*\n(.+?)(?=\n(?:ANNEXURE|APPENDIX|$))',
            r'APPENDIX\s+([A-Z\d]+)\s*\n(.+?)(?=\n(?:ANNEXURE|APPENDIX|$))',
            r'Annex\s+(\d+)\s*\n(.+?)(?=\n(?:Annex|Appendix|$))',
        ]
        
        for pattern in annexure_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
            for match in matches:
                if len(match) >= 2:
                    annexure_id = match[0]
                    annexure_content = match[1].strip()
                    
                    annexures.append({
                        "id": annexure_id,
                        "content_preview": annexure_content[:200] + "..." if len(annexure_content) > 200 else annexure_content,
                        "content_length": len(annexure_content),
                        "has_table": bool(re.search(r'TABLE|\|\s*\|', annexure_content)),
                        "language_distribution": self._analyze_language_mix(annexure_content)
                    })
        
        return annexures
    
    def _extract_enhanced_concluding_remarks(self, text: str) -> Optional[str]:
        """Extract enhanced concluding remarks"""
        concluding_phrases = [
            r'This\s+issues\s+with[^\.]+\.',
            r'This\s+is\s+for[^\.]+\.',
            r'You\s+are\s+requested[^\.]+\.',
            r'Immediate\s+compliance[^\.]+\.',
        ]
        
        lines = text.split('\n')
        concluding_lines = []
        
        for i in range(max(0, len(lines)-10), len(lines)):
            line = lines[i].strip()
            if line:
                for phrase_pattern in concluding_phrases:
                    if re.search(phrase_pattern, line, re.IGNORECASE):
                        concluding_lines.append(line)
                        break
        
        if concluding_lines:
            return ' '.join(concluding_lines).strip()
        
        return None
    
    def _create_rag_optimized_chunks(self, full_text: str, preamble: Optional[str],
                                     body_sections: List[Dict], directives: List[Dict],
                                     tables: List[Dict], annexures: List[Dict]) -> List[RAGChunk]:
        """Create RAG-optimized chunks for circular content"""
        chunks = []
        
        # Chunk 1: Preamble (if exists)
        if preamble and len(preamble) > 50:
            chunks.append(RAGChunk(
                chunk_id="chunk_preamble",
                text=preamble,
                chunk_type="preamble",
                metadata={"section": "preamble", "contains_metadata": True},
                embedding_context=["circular", "introduction", "background"],
                legal_significance=0.3,
                language_distribution=self._analyze_language_mix(preamble)
            ))
        
        # Chunk 2: Body sections
        for i, section in enumerate(body_sections):
            section_text = section.get("content", "")
            if section_text and len(section_text) > 50:
                contains_directives = any(
                    directive["text"] in section_text 
                    for directive in directives[:5]
                )
                
                chunks.append(RAGChunk(
                    chunk_id=f"chunk_section_{i:03d}",
                    text=f"{section.get('header', '')}\n{section_text}",
                    chunk_type="body_section",
                    metadata={
                        "section_index": i,
                        "header": section.get("header", ""),
                        "word_count": len(section_text.split())
                    },
                    embedding_context=["circular", "section", "content"],
                    legal_significance=0.6 if contains_directives else 0.4,
                    contains_directives=contains_directives,
                    language_distribution=self._analyze_language_mix(section_text)
                ))
        
        # Chunk 3: Directives (grouped by type)
        directive_groups = {}
        for i, directive in enumerate(directives):
            directive_type = directive.get("type", "instruction")
            if directive_type not in directive_groups:
                directive_groups[directive_type] = []
            directive_groups[directive_type].append(directive)
        
        for directive_type, group_directives in directive_groups.items():
            directive_texts = [d.get("text", "") for d in group_directives[:3]]  # Limit to 3 per group
            if directive_texts:
                chunk_text = f"{directive_type.upper()} DIRECTIVES:\n" + "\n".join(directive_texts)
                
                chunks.append(RAGChunk(
                    chunk_id=f"chunk_directives_{directive_type}",
                    text=chunk_text,
                    chunk_type="directives",
                    metadata={
                        "directive_type": directive_type,
                        "count": len(group_directives),
                        "has_deadlines": any(d.get("deadline") for d in group_directives)
                    },
                    embedding_context=["circular", "directive", "instruction", directive_type],
                    legal_significance=0.9 if directive_type == "mandatory" else 0.7,
                    contains_directives=True,
                    language_distribution=self._analyze_language_mix(chunk_text)
                ))
        
        # Chunk 4: Tables summary
        if tables:
            table_summary = "TABLES AND SCHEDULES:\n"
            for i, table in enumerate(tables[:3]):  # Limit to 3 tables
                table_type = table.get("type", "data_table")
                table_summary += f"{i+1}. {table_type}: {table.get('row_count', 0)} rows\n"
            
            chunks.append(RAGChunk(
                chunk_id="chunk_tables_summary",
                text=table_summary,
                chunk_type="tables_summary",
                metadata={
                    "total_tables": len(tables),
                    "table_types": list(set(t.get("type") for t in tables))
                },
                embedding_context=["circular", "tables", "data", "schedules"],
                legal_significance=0.5,
                language_distribution=self._analyze_language_mix(table_summary)
            ))
        
        # Chunk 5: Annexures summary
        if annexures:
            annexure_summary = "ANNEXURES:\n"
            for annexure in annexures[:3]:  # Limit to 3 annexures
                annexure_id = annexure.get("id", "")
                annexure_summary += f"{annexure_id}. Length: {annexure.get('content_length', 0)} chars\n"
            
            chunks.append(RAGChunk(
                chunk_id="chunk_annexures_summary",
                text=annexure_summary,
                chunk_type="annexures_summary",
                metadata={
                    "total_annexures": len(annexures),
                    "annexure_ids": [a.get("id") for a in annexures]
                },
                embedding_context=["circular", "annexures", "appendices", "attachments"],
                legal_significance=0.4,
                language_distribution=self._analyze_language_mix(annexure_summary)
            ))
        
        # Ensure we have at least one chunk
        if not chunks and full_text:
            # Fallback: chunk the whole text
            chunks.append(RAGChunk(
                chunk_id="chunk_fallback",
                text=full_text[:1000],  # Limit length
                chunk_type="full_text",
                metadata={"fallback": True, "length": len(full_text)},
                embedding_context=["circular", "full_text", "fallback"],
                legal_significance=0.5,
                language_distribution=self._analyze_language_mix(full_text)
            ))
        
        return chunks
    
    # Entity extraction helper methods
    def _extract_kpk_divisions(self, text: str) -> List[str]:
        divisions = re.findall(r'Division\s+([A-Z][a-zA-Z\s\-]+?)(?:\.|$)', text, re.IGNORECASE)
        return list(set(divisions))
    
    def _extract_kpk_ranges(self, text: str) -> List[str]:
        ranges = re.findall(r'Range\s+([A-Z][a-zA-Z\s\-]+?)(?:\.|$)', text, re.IGNORECASE)
        return list(set(ranges))
    
    def _extract_kpk_beats(self, text: str) -> List[str]:
        beats = re.findall(r'Beat\s+([A-Z][a-zA-Z\s\-]+?)(?:\.|$)', text, re.IGNORECASE)
        return list(set(beats))
    
    def _extract_kpk_officers(self, text: str) -> List[str]:
        officers = []
        for designation, variations in self.kpk_officer_designations.items():
            for variation in variations:
                if variation.lower() in text.lower():
                    officers.append(variation)
        return list(set(officers))
    
    def _extract_forest_types(self, text: str) -> List[str]:
        types = re.findall(r'(Reserved|Protected|Guzara|Riverine)\s+Forest', text, re.IGNORECASE)
        return list(set(types))
    
    def _extract_financial_terms(self, text: str) -> List[Dict]:
        financial_terms = []
        patterns = [
            (r'Rs\.\s*([\d,]+\.?\d*)', 'rupees'),
            (r'rupees?\s+([\d,]+\.?\d*)', 'rupees'),
            (r'fine\s+of\s+([\d,]+\.?\d*)', 'fine'),
            (r'fee\s+of\s+([\d,]+\.?\d*)', 'fee'),
        ]
        
        for pattern, term_type in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for amount in matches:
                financial_terms.append({
                    "amount": amount.replace(',', ''),
                    "type": term_type,
                    "context": "circular_provision"
                })
        
        return financial_terms
    
    def _extract_species_mentioned(self, text: str) -> List[Dict]:
        species = []
        common_species = ['Deodar', 'Kail', 'Chir', 'Walnut', 'Oak', 'Pine']
        
        for species_name in common_species:
            if species_name.lower() in text.lower():
                species.append({
                    "species": species_name,
                    "context": "mentioned_in_circular"
                })
        
        return species
    
    def _extract_locations(self, text: str) -> List[str]:
        locations = re.findall(r'([A-Z][a-zA-Z\s\-]+?)\s+(?:District|Division)', text)
        return list(set(locations))
    
    def _extract_authorities(self, text: str) -> List[str]:
        authorities = []
        for designation in self.kpk_officer_designations.keys():
            if designation.lower().replace('_', ' ') in text.lower():
                authorities.append(designation)
        return list(set(authorities))
    
    # Metrics calculation methods
    def _calculate_metadata_completeness(self, metadata: CircularMetadata) -> float:
        """Calculate metadata completeness score"""
        required_fields = [
            ('circular_number', metadata.circular_number),
            ('subject', metadata.subject),
            ('circular_type', metadata.circular_type),
        ]
        
        optional_fields = [
            ('issue_date', metadata.issue_date),
            ('issuing_authority', metadata.issuing_authority),
            ('issuing_department', metadata.issuing_department),
            ('priority', metadata.priority),
        ]
        
        score = 0.0
        
        # Required fields (70% weight)
        for field_name, value in required_fields:
            if value and (field_name != 'circular_number' or not value.startswith('UNKNOWN')):
                if field_name != 'subject' or value != 'No Subject Found':
                    score += 0.233  # 0.7 / 3
        
        # Optional fields (30% weight)
        for field_name, value in optional_fields:
            if value:
                score += 0.075  # 0.3 / 4
        
        return min(score, 1.0)
    
    def _calculate_parsing_coverage(self, metadata: CircularMetadata, references: ReferenceInfo,
                                   distribution: DistributionInfo, compliance: ComplianceInfo,
                                   content: CircularContent) -> float:
        """Calculate parsing coverage score"""
        scores = []
        
        # Metadata coverage
        if metadata.circular_number and not metadata.circular_number.startswith('UNKNOWN'):
            scores.append(0.2)
        if metadata.subject and metadata.subject != 'No Subject Found':
            scores.append(0.15)
        if metadata.issue_date:
            scores.append(0.1)
        
        # Content coverage
        if content.preamble:
            scores.append(0.05)
        if content.body_sections:
            scores.append(0.1)
        if content.directives:
            scores.append(0.15)
        
        # Distribution coverage
        if distribution.primary_recipients:
            scores.append(0.1)
        
        # Compliance coverage
        if compliance.deadline or compliance.reporting_requirement:
            scores.append(0.1)
        
        # References coverage
        if references.referenced_section or references.referenced_act:
            scores.append(0.05)
        
        return min(sum(scores), 1.0)
    
    def _calculate_overall_confidence(self, metadata: CircularMetadata,
                                     content: CircularContent,
                                     pipeline_state: PipelineState) -> float:
        """Calculate overall confidence score"""
        confidence_scores = []
        
        # OCR confidence
        confidence_scores.append(metadata.ocr_confidence * 0.2)
        
        # Metadata confidence
        metadata_completeness = self._calculate_metadata_completeness(metadata)
        confidence_scores.append(metadata_completeness * 0.3)
        
        # Content confidence
        if content.directives:
            confidence_scores.append(0.2)
        if content.rag_chunks:
            confidence_scores.append(0.2)
        
        # Pipeline state confidence
        if pipeline_state.status != "abstained":
            confidence_scores.append(0.1)
        
        # Average with weights
        weighted_sum = sum(confidence_scores)
        total_weight = len(confidence_scores) / 10  # Normalize
        
        return min(weighted_sum / max(total_weight, 0.1), 1.0)


# ========== ENHANCED INTEGRATION FUNCTION ==========

def integrate_enhanced_circular_with_pipeline(phase_2_output: Dict, 
                                             circular_data: ParsedCircular,
                                             multilingual_handler_output: Optional[Dict] = None) -> Dict:
    """
    Enhanced integration with pipeline phases.
    
    Args:
        phase_2_output: Output from phase 2 (restoration)
        circular_data: Enhanced parsed circular
        multilingual_handler_output: Optional output from phase 3.1
        
    Returns:
        Integrated data for phase 4
    """
    integrated_data = {
        "pipeline_progress": {
            "phase_2_completed": bool(phase_2_output),
            "phase_3_1_completed": bool(multilingual_handler_output),
            "phase_3_2_completed": True,
            "current_phase": 3,
            "ready_for_phase_4": circular_data.pipeline_state.status != "abstained"
        },
        "document_analysis": {
            "type": "circular",
            "subtype": circular_data.metadata.circular_type.name,
            "processing_confidence": circular_data.pipeline_state.confidence,
            "abstention_reasons": circular_data.pipeline_state.abstention_reasons,
            "warnings": circular_data.pipeline_state.warnings
        },
        "circular_analysis": circular_data.to_dict(),
        "multilingual_context": multilingual_handler_output or {},
        "phase_2_context": phase_2_output.get("processing_metrics", {}) if phase_2_output else {},
        "recommendations_for_phase_4": {
            "focus_areas": [],
            "extraction_priority": "high" if circular_data.content.directives else "medium",
            "temporal_analysis_needed": bool(circular_data.temporal_relationships.supersedes or 
                                           circular_data.temporal_relationships.amended_by),
            "authority_hierarchy_present": bool(circular_data.distribution.authority_hierarchy),
            "compliance_extraction_needed": bool(circular_data.compliance.deadline or 
                                               circular_data.compliance.reporting_requirement)
        }
    }
    
    # Set focus areas based on content
    if circular_data.content.directives:
        integrated_data["recommendations_for_phase_4"]["focus_areas"].append("directive_extraction")
    if circular_data.compliance.deadline:
        integrated_data["recommendations_for_phase_4"]["focus_areas"].append("compliance_tracking")
    if circular_data.temporal_relationships.supersedes:
        integrated_data["recommendations_for_phase_4"]["focus_areas"].append("version_control")
    if circular_data.distribution.authority_hierarchy:
        integrated_data["recommendations_for_phase_4"]["focus_areas"].append("authority_mapping")
    
    # Add RAG chunks for phase 6
    if circular_data.content.rag_chunks:
        integrated_data["rag_ready_chunks"] = [
            chunk.to_dict() for chunk in circular_data.content.rag_chunks
        ]
    
    # Add graph schema for phase 6
    if circular_data.graph_schema_mapping:
        integrated_data["graph_schema"] = circular_data.graph_schema_mapping.to_dict()
    
    return integrated_data


# ========== COMMAND LINE INTERFACE ==========

def main():
    """Enhanced command line interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Enhanced KPK Circular Parser')
    parser.add_argument('--input', required=True, help='Input text file or JSON')
    parser.add_argument('--output', help='Output JSON path')
    parser.add_argument('--doc-type', default='circular', help='Document type')
    parser.add_argument('--integrate-phase2', help='Phase 2 output JSON')
    parser.add_argument('--integrate-phase3-1', help='Phase 3.1 output JSON')
    parser.add_argument('--verbose', action='store_true', help='Verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Load input
    input_path = Path(args.input)
    if input_path.suffix == '.json':
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        text = data.get('normalized_text', '') if 'normalized_text' in data else str(data)
    else:
        with open(input_path, 'r', encoding='utf-8') as f:
            text = f.read()
    
    # Load phase 2 output if provided
    phase2_output = None
    if args.integrate_phase2:
        with open(args.integrate_phase2, 'r', encoding='utf-8') as f:
            phase2_output = json.load(f)
    
    # Load phase 3.1 output if provided
    phase31_output = None
    if args.integrate_phase3_1:
        with open(args.integrate_phase3_1, 'r', encoding='utf-8') as f:
            phase31_output = json.load(f)
    
    # Parse circular
    parser = EnhancedKPFCircularParser()
    parsed_circular = parser.parse_circular(text, args.doc_type)
    
    # Integrate with pipeline
    integrated_result = integrate_enhanced_circular_with_pipeline(
        phase2_output, parsed_circular, phase31_output
    )
    
    # Save or output result
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(integrated_result, f, indent=2, ensure_ascii=False)
        print(f"Enhanced circular analysis saved to {args.output}")
    else:
        print(json.dumps(integrated_result, indent=2))
    
    # Print enhanced summary
    print(f"\n{'='*60}")
    print("ENHANCED CIRCULAR PARSING SUMMARY")
    print(f"{'='*60}")
    metadata = parsed_circular.metadata
    print(f"Circular No: {metadata.circular_number}")
    print(f"Type: {metadata.circular_type.name}")
    print(f"Subject: {metadata.subject[:80]}...")
    print(f"Date: {metadata.issue_date or 'Not found'}")
    print(f"Authority: {metadata.issuing_authority or 'Not found'}")
    print(f"Priority: {metadata.priority.name if metadata.priority else 'Not specified'}")
    print(f"Directives: {len(parsed_circular.content.directives)}")
    print(f"RAG Chunks: {len(parsed_circular.content.rag_chunks)}")
    print(f"Primary Recipients: {len(parsed_circular.distribution.primary_recipients)}")
    print(f"Pipeline Status: {parsed_circular.pipeline_state.status}")
    print(f"Overall Confidence: {parsed_circular.pipeline_state.confidence:.2%}")
    print(f"{'='*60}")
    
    # Show recommendations for next phase
    print("\nRECOMMENDATIONS FOR PHASE 4:")
    recs = integrated_result["recommendations_for_phase_4"]
    for focus_area in recs.get("focus_areas", []):
        print(f"  • Focus on: {focus_area}")
    print(f"  • Extraction priority: {recs.get('extraction_priority', 'medium')}")
    print(f"  • Ready for Phase 4: {recs.get('ready_for_phase_4', False)}")


if __name__ == "__main__":
    main()
