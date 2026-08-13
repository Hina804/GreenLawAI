"""
SECTION_DETECTOR.PY - KPK Legal Section Detector
===========================================================
PHASE 3.4: LEGAL SECTION DETECTION AND STRUCTURE ANALYSIS

Enhanced detector for KPK forestry legal documents with:
- Multi-level section detection (Sections, Subsections, Clauses, Sub-clauses)
- KPK-specific legal section patterns
- OCR error handling for section numbers
- Temporal section versioning
- Authority hierarchy integration
- Cross-references and amendment tracking
- Multilingual section detection (Urdu/English)

Key Features:
1. Detects sections, subsections, articles, clauses, provisos
2. Handles OCR errors in section numbers
3. Tracks section amendments and supersessions
4. Identifies section authority and jurisdiction
5. Extracts section metadata and relationships
6. Creates hierarchical section structure
7. Links sections to KPK-specific legal context
8. Prepares sections for Graph-RAG integration

Philosophy: "Rules Decide" - deterministic detection with LLM fallback for ambiguous cases
"""

import re
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set, Union
from datetime import datetime
from dataclasses import dataclass, asdict, field
from enum import Enum
import hashlib

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SectionLevel(Enum):
    """Levels of legal section hierarchy"""
    CHAPTER = "chapter"       # CHAPTER I, CHAPTER II
    PART = "part"            # PART A, PART 1
    SECTION = "section"      # Section 1, Section 1A
    SUBSECTION = "subsection" # (1), (a), (i)
    CLAUSE = "clause"        # Clause 1, Clause (a)
    SUB_CLAUSE = "sub_clause" # (i), (A)
    PROVISO = "proviso"      # Provided that, Provided further
    EXPLANATION = "explanation" # Explanation.
    SCHEDULE = "schedule"    # SCHEDULE I, FIRST SCHEDULE
    RULE = "rule"            # Rule 1, Rule 1A
    REGULATION = "regulation" # Regulation 1
    ORDER = "order"          # Order 1
    
    @property
    def precedence(self) -> int:
        """Precedence order for section levels"""
        precedence_map = {
            "chapter": 1,
            "part": 2,
            "section": 3,
            "subsection": 4,
            "clause": 5,
            "sub_clause": 6,
            "proviso": 7,
            "explanation": 8,
            "schedule": 9,
            "rule": 10,
            "regulation": 11,
            "order": 12
        }
        return precedence_map.get(self.value, 99)
    
    @property
    def graph_node_type(self) -> str:
        """Map to Neo4j node type"""
        return self.value.capitalize()


class SectionStatus(Enum):
    """Status of legal sections"""
    ACTIVE = "active"
    AMENDED = "amended"
    REPEALED = "repealed"
    SUPERSEDED = "superseded"
    ADDED = "added"
    OBSOLETE = "obsolete"
    PROPOSED = "proposed"
    
    @property
    def is_valid(self) -> bool:
        """Whether this status indicates the section is currently valid"""
        return self in [SectionStatus.ACTIVE, SectionStatus.AMENDED, SectionStatus.ADDED]


class AuthorityLevel(Enum):
    """Authority level for sections"""
    FEDERAL = "federal"          # Federal laws (Pakistan Forest Act)
    PROVINCIAL = "provincial"    # KPK Forest Ordinance
    DIVISIONAL = "divisional"    # Divisional notifications
    RANGE = "range"              # Range office orders
    BEAT = "beat"                # Beat level instructions
    
    @property
    def jurisdiction_scope(self) -> str:
        """Jurisdiction scope description"""
        scopes = {
            "federal": "Whole of Pakistan",
            "provincial": "Khyber Pakhtunkhwa Province",
            "divisional": "Forest Division",
            "range": "Forest Range",
            "beat": "Forest Beat"
        }
        return scopes.get(self.value, "Unknown")


@dataclass
class SectionMetadata:
    """Metadata for detected sections"""
    section_id: str
    section_number: str
    section_level: SectionLevel
    title: Optional[str] = None
    authority: AuthorityLevel = AuthorityLevel.PROVINCIAL
    status: SectionStatus = SectionStatus.ACTIVE
    effective_date: Optional[str] = None
    amendment_date: Optional[str] = None
    amendment_reference: Optional[str] = None
    superseded_by: Optional[str] = None
    parent_section: Optional[str] = None
    jurisdiction: str = "KPK"
    legal_act: Optional[str] = None  # Forest Ordinance 2002, etc.
    penalty_provision: bool = False
    definition_provision: bool = False
    procedural_provision: bool = False
    enforcement_provision: bool = False
    compliance_required: bool = True
    language: str = "english"  # english, urdu, mixed
    
    def to_dict(self) -> Dict:
        result = asdict(self)
        result["section_level"] = self.section_level.value
        result["authority"] = self.authority.value
        result["status"] = self.status.value
        return result


@dataclass
class SectionContent:
    """Content of detected section"""
    text: str
    raw_text: str
    start_position: int
    end_position: int
    word_count: int
    sentence_count: int
    contains_definitions: bool = False
    contains_penalties: bool = False
    contains_procedures: bool = False
    contains_exceptions: bool = False
    key_phrases: List[str] = field(default_factory=list)
    legal_terms: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)  # References to other sections
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class SectionRelationship:
    """Relationship between sections"""
    source_section: str
    target_section: str
    relationship_type: str  # AMENDS, REFERENCES, SUPERSEDES, CLARIFIES, etc.
    confidence: float = 0.8
    context: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class DetectedSection:
    """Complete detected section"""
    metadata: SectionMetadata
    content: SectionContent
    child_sections: List['DetectedSection'] = field(default_factory=list)
    relationships: List[SectionRelationship] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "metadata": self.metadata.to_dict(),
            "content": self.content.to_dict(),
            "child_sections": [child.to_dict() for child in self.child_sections],
            "relationships": [rel.to_dict() for rel in self.relationships]
        }


@dataclass 
class SectionDetectionResult:
    """Complete section detection result"""
    document_id: str
    sections: List[DetectedSection]
    section_hierarchy: Dict[str, Any]
    statistics: Dict[str, Any]
    processing_metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict:
        return {
            "document_id": self.document_id,
            "sections": [section.to_dict() for section in self.sections],
            "section_hierarchy": self.section_hierarchy,
            "statistics": self.statistics,
            "processing_metadata": self.processing_metadata
        }


class KPKSectionDetector:
    """
    Advanced section detector for KPK forestry legal documents.
    Handles OCR errors, multilingual content, and complex hierarchies.
    """
    
    def __init__(self, document_type: str = "statute"):
        self.document_type = document_type
        
        # OCR error patterns for section numbers
        self.ocr_error_patterns = {
            'Secti0n': 'Section',
            'Secti0n': 'Section',
            'Seciton': 'Section',
            'Sectoin': 'Section',
            'Secton': 'Section',
            'Artcile': 'Article',
            'Artic1e': 'Article',
            'Articie': 'Article',
            'Clasue': 'Clause',
            'Cluase': 'Clause',
            'Sub-secti0n': 'Sub-section',
            'Sub-secton': 'Sub-section',
            'Provis0': 'Proviso',
            'Explanaton': 'Explanation',
            'Schedu1e': 'Schedule'
        }
        
        # Enhanced section patterns with OCR awareness
        self.section_patterns = {
            SectionLevel.CHAPTER: [
                r'(?:CHAPTER|CHAP\.?|Chapitre)\s+([IVXLCDM]+)(?:\.|\s|$)',  # CHAPTER I, CHAP. II
                r'(?:باب|ب)\.?\s+([\u0660-\u0669\u06F0-\u06F9IVXLCDM]+)',  # Urdu chapters
            ],
            SectionLevel.PART: [
                r'(?:PART|PT\.?)\s+([IVXLCDM\d]+[A-Z]?)(?:\.|\s|$)',  # PART A, PT. 1
                r'(?:حصہ|حص)\s+([\u0660-\u0669\u06F0-\u06F9A-Z]+)',  # Urdu parts
            ],
            SectionLevel.SECTION: [
                # English sections with OCR correction
                r'(?:Section|Sec\.?|S\.)\s*(\d+[A-Z]?(?:\(\w+\))?)(?:\.|\s|$)',  # Section 1, Sec. 1A
                r'(?:^|[\.\:\u2014]|Pag\s*e\s*)\s*(\d+[A-Z]?)[\.\s](?=[^\d])',  # Line start or following separator or page tag
                r'S\.\s*(\d+[A-Z]?)(?:\s+of|\.|\s|$)',  # S. 1 of
                
                # Urdu sections
                r'(?:سیکشن|سیک)\s*(\d+[A-Z]?)(?:\.|\s|$)',  # Urdu sections
                r'سیکشن\s+(\d+)\s+کی',  # Section 1 of
                
                # OCR error variants
                r'Secti0n\s*(\d+[A-Z]?)(?:\.|\s|$)',  # Secti0n 1
                r'Secton\s*(\d+[A-Z]?)(?:\.|\s|$)',  # Secton 1
            ],
            SectionLevel.SUBSECTION: [
                r'\((\d+[a-z]?)\)',  # (1), (a)
                r'\(([a-z])\)',  # (a), (b)
                r'(\d+)\.\d+',  # 1.1, 1.2
                r'\((\d+)\)\s+[A-Z]',  # (1) Text starts
            ],
            SectionLevel.CLAUSE: [
                r'(?:Clause|Cl\.?)\s*(\d+[a-z]?)(?:\.|\s|$)',  # Clause 1, Cl. 1
                r'\(([a-z])\)\s+[A-Z]',  # (a) Text - FIXED: only single lowercase letter
                r'شق\s*(\d+[a-z]?)(?:\.|\s|$)',  # Urdu clause
            ],
            SectionLevel.SUB_CLAUSE: [
                r'\(([ivxlcdm]+)\)',  # (i), (ii)
                r'\(([A-Z])\)',  # (A), (B)
                r'(\d+)\s*-\s*[A-Z]',  # 1-A, 2-B
            ],
            SectionLevel.PROVISO: [
                r'Provided\s+(?:that|further)',  # Provided that, Provided further
                r'بشرطیکہ',  # Urdu proviso
                r'مشروط ہے کہ',  # Urdu conditional
            ],
            SectionLevel.EXPLANATION: [
                r'Explanation\.',  # Explanation.
                r'Explanation\s*[:\-]',  # Explanation:
                r'تشریح',  # Urdu explanation
            ],
            SectionLevel.SCHEDULE: [
                r'(?:SCHEDULE|SCH\.?)\s+([IVXLCDM]+)',  # SCHEDULE I
                r'(?:First|Second|Third)\s+Schedule',  # First Schedule
                r'شیڈول\s+([\u0660-\u0669\u06F0-\u06F9]+)',  # Urdu schedule
            ],
            SectionLevel.RULE: [
                r'(?:Rule|R\.)\s*(\d+[A-Z]?)(?:\.|\s|$)',  # Rule 1, R. 1
                r'قاعدہ\s*(\d+)(?:\.|\s|$)',  # Urdu rule
            ],
            SectionLevel.REGULATION: [
                r'(?:Regulation|Reg\.?)\s*(\d+[A-Z]?)(?:\.|\s|$)',  # Regulation 1
                r'ضابطہ\s*(\d+)(?:\.|\s|$)',  # Urdu regulation
            ],
            SectionLevel.ORDER: [
                r'(?:Order|O\.)\s*(\d+[A-Z]?)(?:\.|\s|$)',  # Order 1
                r'حکم\s*(\d+)(?:\.|\s|$)',  # Urdu order
            ]
        }
        
        # KPK-specific legal act patterns
        self.kpk_legal_acts = {
            "KPK_FOREST_ORDINANCE": [
                r'Khyber Pakhtunkhwa Forest Ordinance',
                r'KPK Forest Ordinance',
                r'خیبر پختونخوا فارسٹ آرڈیننس'
            ],
            "FOREST_ACT_1927": [
                r'Forest Act, 1927',
                r'فارسٹ ایکٹ ۱۹۲۷'
            ],
            "WILDLIFE_ACT": [
                r'KPK Wildlife Act',
                r'وائلڈ لائف ایکٹ'
            ],
            "ENVIRONMENT_PROTECTION_ACT": [
                r'Environment Protection Act',
                r'ماحولیاتی تحفظ ایکٹ'
            ]
        }
        
        # Authority indicators
        self.authority_indicators = {
            AuthorityLevel.FEDERAL: [
                r'Government of Pakistan',
                r'Federal Government',
                r'وفاقی حکومت'
            ],
            AuthorityLevel.PROVINCIAL: [
                r'Government of Khyber Pakhtunkhwa',
                r'Provincial Government',
                r'صوبائی حکومت'
            ],
            AuthorityLevel.DIVISIONAL: [
                r'Divisional Forest Officer',
                r'DFO',
                r'ڈویژنل فارسٹ آفیسر'
            ],
            AuthorityLevel.RANGE: [
                r'Range Forest Officer',
                r'RFO',
                r'رینج فارسٹ آفیسر'
            ],
            AuthorityLevel.BEAT: [
                r'Beat Officer',
                r'Forest Guard',
                r'بیٹ آفیسر'
            ]
        }
        
        # Status indicators
        self.status_indicators = {
            SectionStatus.AMENDED: [
                r'amended by',
                r'as amended',
                r'ترمیم شدہ'
            ],
            SectionStatus.REPEALED: [
                r'repealed',
                r'shall stand repealed',
                r'منسوخ'
            ],
            SectionStatus.SUPERSEDED: [
                r'superseded by',
                r'replaced by',
                r'متروک'
            ],
            SectionStatus.ADDED: [
                r'inserted by',
                r'added by',
                r'شامل کردہ'
            ],
            SectionStatus.OBSOLETE: [
                r'obsolete',
                r'not in force',
                r'فرسودہ'
            ]
        }
        
        # Content type indicators
        self.content_indicators = {
            "penalty": [
                r'penalty',
                r'fine',
                r'imprisonment',
                r'punishable',
                r'جرمانہ',
                r'سزا'
            ],
            "definition": [
                r'means',
                r'includes',
                r'shall mean',
                r'defined as',
                r'denotes',
                r'تعریف',
                r'مطلب'
            ],
            "procedure": [
                r'shall apply',
                r'may apply',
                r'make application',
                r'procedure',
                r'طریقہ کار'
            ],
            "exception": [
                r'except',
                r'provided that',
                r'however',
                r'ماسوائے',
                r'بشرطیکہ'
            ]
        }
        
        # Relationship patterns
        self.relationship_patterns = {
            "AMENDS": r'amends?\s+(?:section|sec\.?)\s*(\d+[A-Z]?)',
            "REFERENCES": r'(?:see|refer to)\s+(?:section|sec\.?)\s*(\d+[A-Z]?)',
            "SUPERSEDES": r'supersedes?\s+(?:section|sec\.?)\s*(\d+[A-Z]?)',
            "CLARIFIES": r'clarifies?\s+(?:section|sec\.?)\s*(\d+[A-Z]?)',
            "REPLACES": r'replaces?\s+(?:section|sec\.?)\s*(\d+[A-Z]?)',
            "QUALIFIES": r'subject to\s+(?:section|sec\.?)\s*(\d+[A-Z]?)'
        }
        
        # Key legal terms for KPK forestry
        self.kpk_legal_terms = [
            "forest", "tree", "timber", "logging", "deodar", "chir", "kail",
            "permit", "license", "royalty", "auction", "conservation", "protection",
            "reserved forest", "protected forest", "guzara forest",
            "فارسٹ", "درخت", "لکڑی", "اجازت", "لائسنس", "محفوظہ جنگل", "محمودہ جنگل"
        ]
        
        # Section number normalization
        self.section_number_normalization = {
            'I': '1', 'II': '2', 'III': '3', 'IV': '4', 'V': '5',
            'VI': '6', 'VII': '7', 'VIII': '8', 'IX': '9', 'X': '10',
            'i': '1', 'ii': '2', 'iii': '3', 'iv': '4', 'v': '5',
            'vi': '6', 'vii': '7', 'viii': '8', 'ix': '9', 'x': '10'
        }
        
        logger.info(f"KPK Section Detector initialized for {document_type}")
    
    def detect_sections(self, text: str, document_id: str = None) -> SectionDetectionResult:
        """
        Main method to detect sections in legal text.
        
        Args:
            text: The legal text to process
            document_id: Optional document identifier
            
        Returns:
            SectionDetectionResult with all detected sections
        """
        if document_id is None:
            document_id = f"doc_{hashlib.md5(text.encode()).hexdigest()[:8]}"
        
        logger.info(f"Starting section detection for document: {document_id}")
        
        # Step 1: Preprocess text
        cleaned_text, preprocessing_stats = self._preprocess_text(text)
        
        # Step 2: Detect all section markers
        section_markers = self._detect_section_markers(cleaned_text)
        
        # Step 3: Extract section content
        sections = self._extract_section_content(cleaned_text, section_markers)
        
        # Step 4: Build section hierarchy
        hierarchy = self._build_section_hierarchy(sections)
        
        # Step 5: Analyze section relationships
        relationships = self._analyze_section_relationships(cleaned_text, sections)
        
        # Step 6: Calculate statistics
        statistics = self._calculate_section_statistics(sections, relationships)
        
        # Step 7: Create result
        result = SectionDetectionResult(
            document_id=document_id,
            sections=sections,
            section_hierarchy=hierarchy,
            statistics=statistics,
            processing_metadata={
                "detector_version": "3.4_enhanced",
                "processing_timestamp": datetime.now().isoformat(),
                "document_type": self.document_type,
                "text_length": len(text),
                "preprocessing_stats": preprocessing_stats
            }
        )
        
        logger.info(f"Section detection complete: {len(sections)} sections detected")
        return result
    
    def _preprocess_text(self, text: str) -> Tuple[str, Dict[str, Any]]:
        """
        Preprocess text for section detection.
        
        Args:
            text: Raw text
            
        Returns:
            Tuple of (cleaned_text, preprocessing_stats)
        """
        original_length = len(text)
        
        # Fix OCR errors
        corrected_text = text
        corrections_applied = 0
        
        for error, correction in self.ocr_error_patterns.items():
            if error in corrected_text:
                corrected_text = corrected_text.replace(error, correction)
                corrections_applied += 1
        
        # Standardize section markers
        section_variations = {
            'Sec.': 'Section',
            'Sec ': 'Section ',
            'S. ': 'Section ',
            'Art.': 'Article',
            'Cl.': 'Clause',
            'Sch.': 'Schedule',
            'Reg.': 'Regulation'
        }
        
        for variation, standard in section_variations.items():
            corrected_text = re.sub(rf'\b{variation}\b', standard, corrected_text)
        
        # Remove excessive whitespace but preserve structure
        lines = corrected_text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if line:
                # Normalize spaces
                line = re.sub(r'\s+', ' ', line)
                cleaned_lines.append(line)
        
        cleaned_text = '\n'.join(cleaned_lines)
        
        # Calculate statistics
        stats = {
            "original_length": original_length,
            "cleaned_length": len(cleaned_text),
            "ocr_corrections": corrections_applied,
            "ocr_confidence": max(0.0, 1.0 - (corrections_applied / max(1, len(text.split())))),
            "line_count": len(cleaned_lines)
        }
        
        return cleaned_text, stats
    
    def _detect_section_markers(self, text: str) -> List[Dict[str, Any]]:
        """
        Detect all section markers in text.
        
        Args:
            text: Cleaned text
            
        Returns:
            List of section markers with metadata
        """
        markers = []
        
        # Detect markers for each section level
        for level, patterns in self.section_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
                for match in matches:
                    section_number = match.group(1) if match.groups() else ""
                    
                    # Normalize section number
                    normalized_number = self._normalize_section_number(section_number)
                    
                    # Determine if this is a title line
                    is_title = False
                    line = text[match.start():match.end() + 100]  # Look ahead
                    if len(line.strip()) < 150 and line.strip().isupper():
                        is_title = True
                    
                    # REJECTION LOGIC: Filter out page numbers and footnotes
                    # If marker is just digits (e.g. "14") and it's the only thing on the line, reject it.
                    if level == SectionLevel.SECTION and re.match(r'^\d+$', section_number):
                        # Use the lookahead 'line' to see if there's significant text after it on the same line
                        current_line_tail = line.split('\n')[0].strip()
                        if len(current_line_tail) < 10: # Very little text after the number
                            if not is_title:
                                logger.debug(f"Rejecting potential page number: {match.group(0)}")
                                continue
                                
                    marker = {
                        "level": level,
                        "pattern": pattern,
                        "match": match.group(0),
                        "section_number": normalized_number,
                        "original_number": section_number,
                        "start_position": match.start(),
                        "end_position": match.end(),
                        "is_title": is_title,
                        "confidence": self._calculate_marker_confidence(match.group(0), level)
                    }
                    
                    markers.append(marker)
        
        # Sort markers by position
        markers.sort(key=lambda x: x["start_position"])
        
        # Filter overlapping markers
        filtered_markers = []
        last_position = -1
        
        for marker in markers:
            if marker["start_position"] > last_position:
                filtered_markers.append(marker)
                last_position = marker["end_position"]
            else:
                # Choose higher confidence marker
                existing = filtered_markers[-1]
                if marker["confidence"] > existing["confidence"]:
                    filtered_markers[-1] = marker
        
        logger.info(f"Detected {len(filtered_markers)} section markers")
        return filtered_markers
    
    def _extract_section_content(self, text: str, markers: List[Dict]) -> List[DetectedSection]:
        """
        Extract content for each detected section with deduplication.
        """
        all_detected = []
        
        for i, marker in enumerate(markers):
            # Determine content boundaries
            if marker.get("confidence", 1.0) < 0.7:
                start_pos = marker["start_position"]
            else:
                start_pos = marker["end_position"]
            
            end_pos = markers[i + 1]["start_position"] if i + 1 < len(markers) else len(text)
            
            # Extract content
            content_text = text[start_pos:end_pos].strip()
            raw_content = content_text
            
            # Clean content
            content_text = self._clean_section_content(content_text)
            
            # Generate section ID
            section_id = self._generate_section_id(
                marker["level"],
                marker["section_number"],
                marker["start_position"]
            )
            
            # Extract metadata
            metadata = self._extract_section_metadata(
                marker, content_text, text, i
            )
            
            # Analyze content
            content_analysis = self._analyze_section_content(content_text)
            
            # Create SectionContent
            section_content = SectionContent(
                text=content_text,
                raw_text=raw_content,
                start_position=start_pos,
                end_position=end_pos,
                word_count=len(content_text.split()),
                sentence_count=len(re.findall(r'[.!?۔]+', content_text)),
                contains_definitions=content_analysis["contains_definitions"],
                contains_penalties=content_analysis["contains_penalties"],
                contains_procedures=content_analysis["contains_procedures"],
                contains_exceptions=content_analysis["contains_exceptions"],
                key_phrases=content_analysis["key_phrases"],
                legal_terms=content_analysis["legal_terms"],
                references=content_analysis["references"]
            )
            
            # Create DetectedSection
            section = DetectedSection(
                metadata=metadata,
                content=section_content
            )
            
            all_detected.append(section)
            
        # Deduplication Logic:
        # If we have multiple sections with same level and number, prefer the one with the most content.
        # This naturally filters out Table of Contents entries because the actual law section
        # will almost always be longer than the TOC entry.
        
        registry = {} # (level, number) -> DetectedSection
        for section in all_detected:
            level = section.metadata.section_level
            num = section.metadata.section_number
            if not num: continue # Skip segments without numbers for deduplication
            
            key = (level, num)
            if key not in registry:
                registry[key] = section
            else:
                # Keep the one with more words (likely the actual section vs TOC entry)
                if section.content.word_count > registry[key].content.word_count:
                    registry[key] = section
                elif section.content.word_count == registry[key].content.word_count:
                    # If same length, keep the first one
                    pass
        
        # Sort final sections by their original position
        final_sections = sorted(registry.values(), key=lambda x: x.content.start_position)
        
        # If we lost all sections due to numbering issues, return all (fallback)
        if not final_sections and all_detected:
            logger.warning("Deduplication removed all sections, falling back to raw detection")
            return all_detected
            
        return final_sections
    
    def _build_section_hierarchy(self, sections: List[DetectedSection]) -> Dict[str, Any]:
        """
        Build hierarchical structure of sections.
        
        Args:
            sections: List of detected sections
            
        Returns:
            Hierarchical structure
        """
        hierarchy = {
            "root": None,
            "levels": {},
            "depth": 0,
            "max_branching": 0
        }
        
        # Group sections by level
        sections_by_level = {}
        for section in sections:
            level = section.metadata.section_level
            if level not in sections_by_level:
                sections_by_level[level] = []
            sections_by_level[level].append(section)
        
        # Build parent-child relationships
        for i, section in enumerate(sections):
            # Find parent (higher level section before this one)
            parent = None
            for j in range(i-1, -1, -1):
                if sections[j].metadata.section_level.precedence < section.metadata.section_level.precedence:
                    parent = sections[j]
                    break
            
            if parent:
                parent.metadata.parent_section = section.metadata.section_id
                # Add as child
                parent.child_sections.append(section)
        
        # Find root sections (sections without parent)
        root_sections = [s for s in sections if s.metadata.parent_section is None]
        
        if root_sections:
            hierarchy["root"] = root_sections[0].metadata.section_id
            hierarchy["root_sections"] = [s.metadata.section_id for s in root_sections]
        
        # Calculate hierarchy metrics
        hierarchy["levels"] = {getattr(level, 'value', str(level)): len(sections) for level, sections in sections_by_level.items()}
        hierarchy["depth"] = self._calculate_hierarchy_depth(sections)
        hierarchy["max_branching"] = self._calculate_max_branching(sections)
        
        return hierarchy
    
    def _analyze_section_relationships(self, text: str, sections: List[DetectedSection]) -> List[SectionRelationship]:
        """
        Analyze relationships between sections.
        
        Args:
            text: Full text
            sections: Detected sections
            
        Returns:
            List of section relationships
        """
        relationships = []
        
        # Create section number to ID mapping
        section_map = {}
        for section in sections:
            key = f"{section.metadata.section_level.value}_{section.metadata.section_number}"
            section_map[key] = section.metadata.section_id
        
        # Analyze each section for relationships
        for section in sections:
            section_text = section.content.text
            
            for rel_type, pattern in self.relationship_patterns.items():
                matches = re.finditer(pattern, section_text, re.IGNORECASE)
                for match in matches:
                    if match.groups():
                        target_number = match.group(1)
                        
                        # Try to find target section
                        target_section_id = None
                        for level in SectionLevel:
                            key = f"{level.value}_{target_number}"
                            if key in section_map:
                                target_section_id = section_map[key]
                                break
                        
                        if target_section_id:
                            relationship = SectionRelationship(
                                source_section=section.metadata.section_id,
                                target_section=target_section_id,
                                relationship_type=rel_type,
                                confidence=0.8,
                                context=match.group(0)[:100]
                            )
                            relationships.append(relationship)
                            section.relationships.append(relationship)
        
        # Add hierarchical relationships
        for section in sections:
            if section.metadata.parent_section:
                relationship = SectionRelationship(
                    source_section=section.metadata.section_id,
                    target_section=section.metadata.parent_section,
                    relationship_type="CHILD_OF",
                    confidence=1.0,
                    context="hierarchy"
                )
                relationships.append(relationship)
                section.relationships.append(relationship)
        
        return relationships
    
    def _calculate_section_statistics(self, sections: List[DetectedSection], 
                                    relationships: List[SectionRelationship]) -> Dict[str, Any]:
        """
        Calculate statistics about detected sections.
        
        Args:
            sections: Detected sections
            relationships: Section relationships
            
        Returns:
            Statistics dictionary
        """
        stats = {
            "total_sections": len(sections),
            "section_levels": {},
            "content_metrics": {},
            "relationship_metrics": {},
            "quality_metrics": {}
        }
        
        # Count by level
        level_counts = {}
        for section in sections:
            level = section.metadata.section_level.value
            level_counts[level] = level_counts.get(level, 0) + 1
        stats["section_levels"] = level_counts
        
        # Content metrics
        total_words = sum(s.content.word_count for s in sections)
        total_sentences = sum(s.content.sentence_count for s in sections)
        
        stats["content_metrics"] = {
            "total_words": total_words,
            "total_sentences": total_sentences,
            "avg_words_per_section": total_words / len(sections) if sections else 0,
            "avg_sentences_per_section": total_sentences / len(sections) if sections else 0,
            "sections_with_penalties": sum(1 for s in sections if s.content.contains_penalties),
            "sections_with_definitions": sum(1 for s in sections if s.content.contains_definitions),
            "sections_with_procedures": sum(1 for s in sections if s.content.contains_procedures),
            "sections_with_exceptions": sum(1 for s in sections if s.content.contains_exceptions)
        }
        
        # Relationship metrics
        relationship_counts = {}
        for rel in relationships:
            relationship_counts[rel.relationship_type] = relationship_counts.get(rel.relationship_type, 0) + 1
        
        stats["relationship_metrics"] = {
            "total_relationships": len(relationships),
            "relationship_types": relationship_counts,
            "avg_relationships_per_section": len(relationships) / len(sections) if sections else 0
        }
        
        # Quality metrics
        sections_with_content = sum(1 for s in sections if s.content.word_count > 10)
        sections_with_metadata = sum(1 for s in sections if s.metadata.title or s.metadata.legal_act)
        
        stats["quality_metrics"] = {
            "content_coverage": sections_with_content / len(sections) if sections else 0,
            "metadata_completeness": sections_with_metadata / len(sections) if sections else 0,
            "hierarchy_depth": self._calculate_hierarchy_depth(sections),
            "relationship_density": len(relationships) / len(sections) if sections else 0
        }
        
        return stats
    
    def _normalize_section_number(self, number: str) -> str:
        """
        Normalize section number.
        
        Args:
            number: Raw section number
            
        Returns:
            Normalized section number
        """
        if not number:
            return ""
        
        # Convert Roman numerals
        if number in self.section_number_normalization:
            return self.section_number_normalization[number]
        
        # Remove parentheses
        number = re.sub(r'[()]', '', number)
        
        # Standardize formatting
        number = number.strip().upper()
        
        return number
    
    def _calculate_marker_confidence(self, marker_text: str, level: SectionLevel) -> float:
        """
        Calculate confidence for a section marker.
        
        Args:
            marker_text: The matched marker text
            level: Section level
            
        Returns:
            Confidence score (0-1)
        """
        confidence = 0.5  # Base confidence
        
        # Length check
        if len(marker_text) >= 5:
            confidence += 0.1
        
        # Pattern completeness
        if 'Section' in marker_text or 'سیکشن' in marker_text:
            confidence += 0.2
        
        # Level-specific checks
        if level == SectionLevel.SECTION:
            # Sections should have numbers
            if re.search(r'\d', marker_text):
                confidence += 0.2
        
        # Upper case check for titles
        if marker_text.isupper():
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def _generate_section_id(self, level: SectionLevel, number: str, position: int) -> str:
        """
        Generate unique section ID.
        
        Args:
            level: Section level
            number: Section number
            position: Start position
            
        Returns:
            Unique section ID
        """
        level_code = level.value[:3].upper()
        number_code = number if number else "UNK"
        position_code = str(position)[-4:]  # Last 4 digits of position
        
        return f"{level_code}_{number_code}_{position_code}"
    
    def _extract_section_metadata(self, marker: Dict, content: str, 
                                full_text: str, index: int) -> SectionMetadata:
        """
        Extract metadata for a section.
        
        Args:
            marker: Section marker
            content: Section content
            full_text: Full document text
            index: Section index
            
        Returns:
            SectionMetadata object
        """
        # Determine authority level
        authority = self._determine_authority_level(full_text, marker["start_position"])
        
        # Determine status
        status = self._determine_section_status(content, full_text)
        
        # Extract title
        title = self._extract_section_title(content, marker["is_title"])
        
        # Determine if this is a penalty provision
        penalty_provision = self._is_penalty_provision(content)
        
        # Determine if this is a definition provision
        definition_provision = self._is_definition_provision(content)
        
        # Determine if this is a procedural provision
        procedural_provision = self._is_procedural_provision(content)
        
        # Extract legal act
        legal_act = self._extract_legal_act(full_text)
        
        # Determine language
        language = self._determine_language(content)
        
        metadata = SectionMetadata(
            section_id=self._generate_section_id(marker["level"], marker["section_number"], marker["start_position"]),
            section_number=marker["section_number"],
            section_level=marker["level"],
            title=title,
            authority=authority,
            status=status,
            penalty_provision=penalty_provision,
            definition_provision=definition_provision,
            procedural_provision=procedural_provision,
            legal_act=legal_act,
            language=language,
            compliance_required=not (status == SectionStatus.REPEALED or status == SectionStatus.OBSOLETE)
        )
        
        return metadata
    
    def _analyze_section_content(self, content: str) -> Dict[str, Any]:
        """
        Analyze section content.
        
        Args:
            content: Section content
            
        Returns:
            Analysis dictionary
        """
        analysis = {
            "contains_definitions": False,
            "contains_penalties": False,
            "contains_procedures": False,
            "contains_exceptions": False,
            "key_phrases": [],
            "legal_terms": [],
            "references": []
        }
        
        # Check for content types
        for content_type, patterns in self.content_indicators.items():
            for pattern in patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    analysis[f"contains_{content_type}"] = True
                    break
        
        # Extract key phrases (first sentence or short phrases)
        sentences = re.split(r'[.!?۔]+', content)
        if sentences:
            first_sentence = sentences[0].strip()
            if 20 < len(first_sentence) < 100:
                analysis["key_phrases"].append(first_sentence)
        
        # Extract legal terms
        for term in self.kpk_legal_terms:
            if re.search(rf'\b{term}\b', content, re.IGNORECASE):
                analysis["legal_terms"].append(term)
        
        # Extract references to other sections
        reference_patterns = [
            r'section\s+(\d+[A-Z]?)',
            r'sec\.\s*(\d+[A-Z]?)',
            r'سیکشن\s+(\d+[A-Z]?)'
        ]
        
        for pattern in reference_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            analysis["references"].extend(matches)
        
        # Remove duplicates
        analysis["references"] = list(set(analysis["references"]))
        analysis["legal_terms"] = list(set(analysis["legal_terms"]))
        
        return analysis
    
    def _clean_section_content(self, content: str) -> str:
        """
        Clean section content.
        
        Args:
            content: Raw section content
            
        Returns:
            Cleaned content
        """
        # Remove leading/trailing whitespace
        content = content.strip()
        
        # Remove excessive whitespace
        content = re.sub(r'\s+', ' ', content)
        
        # Remove page numbers and headers
        content = re.sub(r'\[Page\s+\d+\]', '', content)
        content = re.sub(r'-\s*\d+\s*-', '', content)
        
        # Remove footnote markers
        content = re.sub(r'\d+\s*\(footnote\)', '', content)
        
        return content
    
    def _determine_authority_level(self, text: str, position: int) -> AuthorityLevel:
        """
        Determine authority level for a section.
        
        Args:
            text: Full text
            position: Section position
            
        Returns:
            AuthorityLevel
        """
        # Look for authority indicators in surrounding text
        context_start = max(0, position - 500)
        context_end = min(len(text), position + 500)
        context = text[context_start:context_end]
        
        for level, indicators in self.authority_indicators.items():
            for indicator in indicators:
                if re.search(indicator, context, re.IGNORECASE):
                    return level
        
        # Default based on document type
        if self.document_type == "statute":
            return AuthorityLevel.PROVINCIAL
        elif self.document_type == "circular":
            return AuthorityLevel.DIVISIONAL
        elif self.document_type == "notification":
            return AuthorityLevel.PROVINCIAL
        else:
            return AuthorityLevel.PROVINCIAL
    
    def _determine_section_status(self, content: str, full_text: str) -> SectionStatus:
        """
        Determine section status.
        
        Args:
            content: Section content
            full_text: Full text
            
        Returns:
            SectionStatus
        """
        # Check for status indicators in content
        for status, indicators in self.status_indicators.items():
            for indicator in indicators:
                if re.search(indicator, content, re.IGNORECASE):
                    return status
        
        # Check in surrounding context
        if "repealed" in full_text.lower() and "section" in content.lower():
            # Check if this section is mentioned in repealed sections
            section_match = re.search(r'section\s+(\d+[A-Z]?)', content, re.IGNORECASE)
            if section_match:
                section_num = section_match.group(1)
                if f"section {section_num}" in full_text.lower() and "repealed" in full_text.lower():
                    return SectionStatus.REPEALED
        
        return SectionStatus.ACTIVE
    
    def _extract_section_title(self, content: str, is_title_line: bool) -> Optional[str]:
        """
        Extract section title.
        
        Args:
            content: Section content
            is_title_line: Whether this appears to be a title line
            
        Returns:
            Title string or None
        """
        if is_title_line:
            # Use first line as title
            lines = content.split('\n')
            if lines:
                title = lines[0].strip()
                if len(title) < 150:  # Reasonable title length
                    return title
        
        # Look for title patterns
        title_patterns = [
            r'^([A-Z][A-Z\s]{5,100}?)[\.:]',  # ALL CAPS TITLE:
            r'^\s*["“]([^"”]+)["”]',  # Quoted title (including smart quotes)
            r'^\s*(.+?)\n\n',  # Text before double newline
        ]
        
        for pattern in title_patterns:
            match = re.search(pattern, content, re.MULTILINE)
            if match:
                title = match.group(1).strip()
                if 10 < len(title) < 200:
                    return title
        
        return None
    
    def _is_penalty_provision(self, content: str) -> bool:
        """Check if content contains penalty provisions."""
        penalty_indicators = [
            r'shall be punishable',
            r'liable to',
            r'fine.*rupees',
            r'imprisonment',
            r'Rs\.\s*\d',
            r'جرمانہ',
            r'سزا'
        ]
        
        for indicator in penalty_indicators:
            if re.search(indicator, content, re.IGNORECASE):
                return True
        
        return False
    
    def _is_definition_provision(self, content: str) -> bool:
        """Check if content contains definitions."""
        definition_indicators = [
            r'means',
            r'includes',
            r'shall mean',
            r'defined as',
            r'denotes',
            r'in this Act',
            r'تعریف',
            r'مطلب'
        ]
        
        for indicator in definition_indicators:
            if re.search(indicator, content, re.IGNORECASE):
                return True
        
        return False
    
    def _is_procedural_provision(self, content: str) -> bool:
        """Check if content contains procedural provisions."""
        procedure_indicators = [
            r'shall apply',
            r'may apply',
            r'application',
            r'procedure',
            r'manner',
            r'form',
            r'طریقہ کار',
            r'درخواست'
        ]
        
        for indicator in procedure_indicators:
            if re.search(indicator, content, re.IGNORECASE):
                return True
        
        return False
    
    def _extract_legal_act(self, text: str) -> Optional[str]:
        """Extract legal act from text."""
        for act_name, patterns in self.kpk_legal_acts.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    # Return formatted act name
                    return act_name.replace('_', ' ').title()
        
        return None
    
    def _determine_language(self, content: str) -> str:
        """Determine language of content."""
        # Check for Urdu script
        urdu_chars = re.findall(r'[\u0600-\u06FF]', content)
        english_chars = re.findall(r'[A-Za-z]', content)
        
        if urdu_chars and english_chars:
            return "mixed"
        elif urdu_chars:
            return "urdu"
        else:
            return "english"
    
    def _calculate_hierarchy_depth(self, sections: List[DetectedSection]) -> int:
        """Calculate maximum hierarchy depth."""
        if not sections:
            return 0
        
        # Find root sections
        root_sections = [s for s in sections if s.metadata.parent_section is None]
        
        if not root_sections:
            return 1
        
        max_depth = 0
        for root in root_sections:
            depth = self._calculate_section_depth(root, sections)
            max_depth = max(max_depth, depth)
        
        return max_depth
    
    def _calculate_section_depth(self, section: DetectedSection, 
                               all_sections: List[DetectedSection]) -> int:
        """Calculate depth for a specific section."""
        if not section.child_sections:
            return 1
        

        
        max_child_depth = 0
        for child in section.child_sections:
            child_depth = self._calculate_section_depth(child, all_sections)
            max_child_depth = max(max_child_depth, child_depth)
        
        return max_child_depth + 1
    
    def _calculate_max_branching(self, sections: List[DetectedSection]) -> int:
        """Calculate maximum branching factor."""
        if not sections:
            return 0
        
        max_branching = 0
        for section in sections:
            branching = len(section.child_sections)
            max_branching = max(max_branching, branching)
        
        return max_branching


# ========== INTEGRATION WITH OTHER PHASES ==========

def integrate_section_detection_with_phases(phase_2_output: Dict,
                                          phase_3_1_output: Dict,
                                          phase_3_2_output: Dict,
                                          phase_3_3_output: Dict,
                                          section_detection_result: SectionDetectionResult) -> Dict:
    """
    Integrate section detection with other pipeline phases.
    
    Args:
        phase_2_output: Output from phase 2 (restoration)
        phase_3_1_output: Output from phase 3.1 (multilingual)
        phase_3_2_output: Output from phase 3.2 (circulars)
        phase_3_3_output: Output from phase 3.3 (working plans)
        section_detection_result: Section detection result
        
    Returns:
        Integrated results
    """
    integrated = {
        "pipeline_progress": {
            "phase_2_completed": bool(phase_2_output),
            "phase_3_1_completed": bool(phase_3_1_output),
            "phase_3_2_completed": bool(phase_3_2_output),
            "phase_3_3_completed": bool(phase_3_3_output),
            "phase_3_4_completed": True,
            "current_phase": 3,
            "ready_for_phase_4": True
        },
        "section_detection": section_detection_result.to_dict(),
        "multilingual_context": phase_3_1_output.get("language_analysis", {}) if phase_3_1_output else {},
        "circular_context": phase_3_2_output.get("circular_analysis", {}) if phase_3_2_output else {},
        "working_plan_context": phase_3_3_output.get("plan_analysis", {}) if phase_3_3_output else {},
        "phase_2_context": phase_2_output.get("processing_metrics", {}) if phase_2_output else {},
        "recommendations_for_phase_4": {
            "legal_extraction_focus": [],
            "priority_sections": [],
            "temporal_analysis_needed": False,
            "authority_conflicts": False,
            "multilingual_challenges": False
        }
    }
    
    # Analyze section detection results for phase 4 recommendations
    sections = section_detection_result.sections
    statistics = section_detection_result.statistics
    
    # Identify focus areas for phase 4
    focus_areas = []
    
    if statistics["content_metrics"]["sections_with_penalties"] > 0:
        focus_areas.append("penalty_extraction")
    
    if statistics["content_metrics"]["sections_with_definitions"] > 0:
        focus_areas.append("definition_extraction")
    
    if statistics["content_metrics"]["sections_with_procedures"] > 0:
        focus_areas.append("procedure_extraction")
    
    # Identify priority sections (penalty provisions, key definitions)
    priority_sections = []
    for section in sections[:10]:  # Limit to first 10
        if (section.content.contains_penalties or 
            section.content.contains_definitions or
            section.metadata.penalty_provision):
            priority_sections.append({
                "section_id": section.metadata.section_id,
                "section_number": section.metadata.section_number,
                "reason": "penalty_provision" if section.content.contains_penalties else 
                         "definition_provision" if section.content.contains_definitions else
                         "key_provision"
            })
    
    integrated["recommendations_for_phase_4"]["legal_extraction_focus"] = focus_areas
    integrated["recommendations_for_phase_4"]["priority_sections"] = priority_sections[:5]  # Limit to 5
    
    # Check for temporal analysis needs
    amended_sections = [s for s in sections if s.metadata.status == SectionStatus.AMENDED]
    if amended_sections:
        integrated["recommendations_for_phase_4"]["temporal_analysis_needed"] = True
    
    # Check for authority conflicts
    authority_levels = set(s.metadata.authority for s in sections)
    if len(authority_levels) > 1:
        integrated["recommendations_for_phase_4"]["authority_conflicts"] = True
    
    # Check for multilingual challenges
    languages = set(s.metadata.language for s in sections)
    if "mixed" in languages or "urdu" in languages:
        integrated["recommendations_for_phase_4"]["multilingual_challenges"] = True
    
    # Prepare structured data for phase 4
    integrated["phase_4_input"] = {
        "sections_for_extraction": [
            {
                "section_id": section.metadata.section_id,
                "section_number": section.metadata.section_number,
                "level": section.metadata.section_level.value,
                "content_preview": section.content.text[:200] + "..." if len(section.content.text) > 200 else section.content.text,
                "contains_penalties": section.content.contains_penalties,
                "contains_definitions": section.content.contains_definitions,
                "penalty_provision": section.metadata.penalty_provision,
                "authority_level": section.metadata.authority.value,
                "legal_terms": section.content.legal_terms[:5]  # Limit to 5 terms
            }
            for section in sections[:20]  # Limit to 20 sections
        ],
        "section_relationships": [
            {
                "source": rel.source_section,
                "target": rel.target_section,
                "type": rel.relationship_type,
                "confidence": rel.confidence
            }
            for rel in section_detection_result.sections[0].relationships[:10] if section_detection_result.sections
        ] if section_detection_result.sections else []
    }
    
    # Prepare data for phase 6 (graph construction)
    integrated["phase_6_input"] = {
        "section_nodes": [
            {
                "id": section.metadata.section_id,
                "type": section.metadata.section_level.graph_node_type,
                "properties": {
                    "number": section.metadata.section_number,
                    "level": section.metadata.section_level.value,
                    "authority": section.metadata.authority.value,
                    "status": section.metadata.status.value,
                    "penalty_provision": section.metadata.penalty_provision,
                    "word_count": section.content.word_count
                }
            }
            for section in sections[:50]  # Limit to 50
        ],
        "section_relationships": [
            {
                "source": rel.source_section,
                "target": rel.target_section,
                "type": rel.relationship_type,
                "properties": {"confidence": rel.confidence}
            }
            for rel in section_detection_result.sections[0].relationships[:20] if section_detection_result.sections
        ] if section_detection_result.sections else []
    }
    
    return integrated


# ========== UTILITY FUNCTIONS ==========

def detect_sections_from_file(filepath: str, document_type: str = "statute") -> Dict:
    """
    Detect sections from a file.
    
    Args:
        filepath: Path to text file
        document_type: Type of document
        
    Returns:
        Section detection results
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read()
        
        detector = KPKSectionDetector(document_type=document_type)
        result = detector.detect_sections(text, Path(filepath).stem)
        
        return result.to_dict()
    except Exception as e:
        logger.error(f"Error detecting sections from file {filepath}: {e}")
        return {"error": str(e)}


def validate_section_detection(result: Dict) -> Dict[str, Any]:
    """
    Validate section detection results.
    
    Args:
        result: Section detection result dictionary
        
    Returns:
        Validation results
    """
    validation = {
        "is_valid": True,
        "issues": [],
        "warnings": [],
        "suggestions": []
    }
    
    if "error" in result:
        validation["is_valid"] = False
        validation["issues"].append(f"Error in detection: {result['error']}")
        return validation
    
    sections = result.get("sections", [])
    statistics = result.get("statistics", {})
    
    # Check for basic requirements
    if len(sections) == 0:
        validation["is_valid"] = False
        validation["issues"].append("No sections detected")
    
    # Check section count
    total_sections = statistics.get("total_sections", 0)
    if total_sections < 3:
        validation["warnings"].append(f"Low section count: {total_sections}")
    
    # Check content quality
    content_metrics = statistics.get("content_metrics", {})
    avg_words = content_metrics.get("avg_words_per_section", 0)
    if avg_words < 10:
        validation["warnings"].append(f"Low average words per section: {avg_words}")
    
    # Check hierarchy depth
    hierarchy = result.get("section_hierarchy", {})
    depth = hierarchy.get("depth", 0)
    if depth > 5:
        validation["warnings"].append(f"Deep hierarchy detected: {depth} levels")
    
    # Check relationship density
    relationship_metrics = statistics.get("relationship_metrics", {})
    rel_density = relationship_metrics.get("avg_relationships_per_section", 0)
    if rel_density > 3:
        validation["warnings"].append(f"High relationship density: {rel_density}")
    
    # Generate suggestions
    if avg_words < 20:
        validation["suggestions"].append("Consider adjusting section boundary detection")
    
    if len(sections) > 50:
        validation["suggestions"].append("Consider chunking large sections for better RAG performance")
    
    return validation


# ========== COMMAND LINE INTERFACE ==========

def main():
    """Command line interface for section detector."""
    import argparse
    
    parser = argparse.ArgumentParser(description='KPK Legal Section Detector')
    parser.add_argument('--input', required=True, help='Input text file or JSON')
    parser.add_argument('--output', help='Output JSON path')
    parser.add_argument('--document-type', default='statute', 
                       choices=['statute', 'circular', 'notification', 'working_plan', 'rule'],
                       help='Type of document')
    parser.add_argument('--integrate-phase2', help='Phase 2 output JSON')
    parser.add_argument('--integrate-phase3-1', help='Phase 3.1 output JSON')
    parser.add_argument('--integrate-phase3-2', help='Phase 3.2 output JSON')
    parser.add_argument('--integrate-phase3-3', help='Phase 3.3 output JSON')
    parser.add_argument('--validate', action='store_true', help='Validate detection results')
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
    
    # Load pipeline outputs if provided
    phase2_output = None
    if args.integrate_phase2:
        with open(args.integrate_phase2, 'r', encoding='utf-8') as f:
            phase2_output = json.load(f)
    
    phase31_output = None
    if args.integrate_phase3_1:
        with open(args.integrate_phase3_1, 'r', encoding='utf-8') as f:
            phase31_output = json.load(f)
    
    phase32_output = None
    if args.integrate_phase3_2:
        with open(args.integrate_phase3_2, 'r', encoding='utf-8') as f:
            phase32_output = json.load(f)
    
    phase33_output = None
    if args.integrate_phase3_3:
        with open(args.integrate_phase3_3, 'r', encoding='utf-8') as f:
            phase33_output = json.load(f)
    
    # Detect sections
    detector = KPKSectionDetector(document_type=args.document_type)
    result = detector.detect_sections(text, input_path.stem)
    
    # Integrate with other phases if provided
    if any([phase2_output, phase31_output, phase32_output, phase33_output]):
        integrated_result = integrate_section_detection_with_phases(
            phase2_output, phase31_output, phase32_output, phase33_output, result
        )
        final_result = integrated_result
    else:
        final_result = result.to_dict()
    
    # Validate if requested
    if args.validate:
        validation = validate_section_detection(final_result)
        final_result["validation"] = validation
    
    # Save or output result
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(final_result, f, indent=2, ensure_ascii=False)
        print(f"Section detection saved to {args.output}")
    else:
        print(json.dumps(final_result, indent=2))
    
    # Print summary
    print(f"\n{'='*60}")
    print("SECTION DETECTION SUMMARY")
    print(f"{'='*60}")
    
    sections = final_result.get("section_detection", {}).get("sections", []) or final_result.get("sections", [])
    statistics = final_result.get("section_detection", {}).get("statistics", {}) or final_result.get("statistics", {})
    
    print(f"Total sections detected: {len(sections)}")
    print(f"Document type: {args.document_type}")
    
    if statistics:
        content_metrics = statistics.get("content_metrics", {})
        print(f"Total words: {content_metrics.get('total_words', 0)}")
        print(f"Avg words per section: {content_metrics.get('avg_words_per_section', 0):.1f}")
        print(f"Penalty provisions: {content_metrics.get('sections_with_penalties', 0)}")
        print(f"Definition provisions: {content_metrics.get('sections_with_definitions', 0)}")
    
    # Show validation results if available
    if args.validate and "validation" in final_result:
        validation = final_result["validation"]
        print(f"\nValidation: {'VALID' if validation['is_valid'] else 'INVALID'}")
        if validation["issues"]:
            print("Issues:")
            for issue in validation["issues"]:
                print(f"  - {issue}")
        if validation["warnings"]:
            print("Warnings:")
            for warning in validation["warnings"]:
                print(f"  - {warning}")
    
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
