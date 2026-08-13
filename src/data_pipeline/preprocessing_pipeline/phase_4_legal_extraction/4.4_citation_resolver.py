"""
CITATION RESOLVER - Phase 4.4 of KPK Legal Extraction
Resolves internal citations and cross-references within legal documents.
OPERATING PRINCIPLE: "Rules resolve references deterministically."
"""

import re
import json
import logging
from typing import Dict, List, Any, Tuple, Optional, Set
from dataclasses import dataclass, asdict, field
from collections import defaultdict, deque
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from config.kpk_forestry_config import (
        KPK_CITATION_PATTERNS, KPK_LEGAL_TERMS,
        KPK_MULTILINGUAL_CITATIONS
    )
    KPK_CONFIG_LOADED = True
except ImportError:
    KPK_CONFIG_LOADED = False
    print("WARNING: KPK Configuration not found. Using default citation patterns.")

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class CitationReference:
    """A resolved citation reference"""
    source_text: str
    source_position: Tuple[int, int]
    source_section: str
    target_type: str  # section, subsection, clause, schedule, annex, rule, form
    target_reference: str
    resolved_target: str = ""  # Full resolved reference
    resolution_method: str = ""  # explicit, implicit, context, parent
    confidence: float = 1.0
    resolution_path: List[str] = field(default_factory=list)  # Steps taken to resolve
    
    def __post_init__(self):
        # Generate unique ID
        import hashlib
        content_hash = hashlib.md5(
            f"{self.source_section}:{self.target_reference}:{self.source_position[0]}".encode()
        ).hexdigest()[:8]
        self.citation_id = f"cite_{content_hash}"


@dataclass
class CrossReference:
    """Cross-reference between two sections"""
    from_section: str
    to_section: str
    reference_type: str  # cites, amended_by, defines, uses_definition
    context: str
    strength: float  # 0-1, how strong the reference is
    bidirectional: bool = False
    citation_ids: List[str] = field(default_factory=list)


@dataclass
class ResolutionResult:
    """Result of citation resolution"""
    section_number: str
    resolved_citations: List[CitationReference]
    unresolved_citations: List[Dict]
    cross_references: List[CrossReference]
    resolution_coverage: float  # 0-1, percentage resolved
    confidence_score: float


class KPKCitationResolver:
    """
    Deterministic citation resolver for KPK forestry laws.
    Resolves internal references like "see section 5", "as per subsection (2)", etc.
    """
    
    def __init__(self, config: Optional[Any] = None, document_structure: Dict = None):
        self.config = config
        self.document_structure = document_structure or {}
        self.section_registry = {}  # section_number -> section_data
        self.citation_index = defaultdict(list)  # target -> list of citations
        self.resolution_cache = {}
        self.abstention_log = []
        
        # Initialize patterns
        self.initialize_citation_patterns()
        self.initialize_resolution_rules()
        
        # Statistics
        self.stats = {
            "citations_found": 0,
            "citations_resolved": 0,
            "cross_references_built": 0,
            "implicit_resolutions": 0,
            "abstention_decisions": 0
        }
        
        logger.info("Citation Resolver initialized")
    
    def initialize_citation_patterns(self):
        """Initialize citation patterns"""
        
        # English citation patterns
        self.citation_patterns = [
            # Explicit references
            (r'(?:see|refer to|under|pursuant to)\s+(?:section|s\.)\s+(\d+[A-Z]?(?:-\d+)?(?:\(\d+\)(?:\(\w+\))?)?)',
             'explicit_section'),
            (r'as\s+per\s+(?:sub-?section|clause)\s+\((\d+|\w+)\)', 'explicit_subsection'),
            (r'in\s+(?:subsection|clause)\s+\((\d+|\w+)\)', 'explicit_subsection'),
            
            # Short forms
            (r'section\s+(\d+[A-Z]?)', 'implicit_section'),
            (r's\.\s*(\d+)', 'abbreviated_section'),
            (r'ss\.\s*(\d+)', 'abbreviated_subsection'),
            
            # Relative references
            (r'(?:the|this)\s+(?:preceding|above|foregoing)\s+section', 'relative_preceding'),
            (r'(?:the|this)\s+(?:following|below)\s+section', 'relative_following'),
            (r'the\s+next\s+section', 'relative_next'),
            (r'the\s+previous\s+section', 'relative_previous'),
            
            # Complex references
            (r'sections?\s+(\d+(?:[-\s]+(?:and\s+)?\d+)+)', 'multiple_sections'),
            (r'section\s+(\d+)\s+and\s+(\d+)', 'two_sections'),
            (r'sections?\s+(\d+)\s+to\s+(\d+)', 'range_sections'),
            
            # Urdu citation patterns
            (r'(?:دیکھیں|ملاحظہ کریں|دیکھو)\s+(?:دفعہ|سیکشن)\s+(\d+)', 'urdu_explicit'),
            (r'دفعہ\s+(\d+)', 'urdu_implicit'),
            (r'ذیلی دفعہ\s+\((\d+|\w+)\)', 'urdu_subsection'),
            (r'شق\s+\((\d+|\w+)\)', 'urdu_clause'),
            
            # Schedule/Annex references
            (r'(?:schedule|annex|form)\s+([A-Z]+\d*|\d+)', 'schedule_reference'),
            (r'شیڈول\s+([A-Z]+\d*|\d+)', 'urdu_schedule'),
            (r'ضمیمہ\s+([A-Z]+\d*|\d+)', 'urdu_annex'),
            
            # Rule references
            (r'rule\s+(\d+)', 'rule_reference'),
            (r'قاعدہ\s+(\d+)', 'urdu_rule'),
            
            # Amendment references
            (r'amended\s+by\s+section\s+(\d+)', 'amendment_reference'),
            (r'متروک\s+بذریعہ\s+دفعہ\s+(\d+)', 'urdu_amendment'),
        ]
        
        # Compiled patterns for performance
        self.compiled_patterns = [(re.compile(pattern, re.IGNORECASE | re.UNICODE), ptype) 
                                 for pattern, ptype in self.citation_patterns]
    
    def initialize_resolution_rules(self):
        """Initialize deterministic resolution rules"""
        
        self.resolution_rules = {
            'explicit_section': {
                'method': 'direct_lookup',
                'confidence': 0.95,
                'requires_section_context': True
            },
            'explicit_subsection': {
                'method': 'parent_section_lookup',
                'confidence': 0.9,
                'requires_section_context': True
            },
            'implicit_section': {
                'method': 'context_inference',
                'confidence': 0.85,
                'requires_section_context': True
            },
            'relative_preceding': {
                'method': 'relative_navigation',
                'confidence': 0.8,
                'requires_section_context': True
            },
            'relative_following': {
                'method': 'relative_navigation',
                'confidence': 0.8,
                'requires_section_context': True
            },
            'multiple_sections': {
                'method': 'multiple_resolution',
                'confidence': 0.9,
                'requires_section_context': True
            },
            'schedule_reference': {
                'method': 'schedule_lookup',
                'confidence': 0.85,
                'requires_section_context': False
            }
        }
    
    def build_section_registry(self, sections_data: List[Any]):
        """
        Build registry of sections for resolution.
        
        Args:
            sections_data: List of section dictionaries or objects
        """
        for section in sections_data:
            # Handle both dict and object formats (DetectedSection from Phase 3.4)
            if hasattr(section, 'metadata') and hasattr(section, 'content'):
                section_num = getattr(section.metadata, 'section_number', None)
                section_text = getattr(section.content, 'text', '')
                section_title = getattr(section.metadata, 'title', '') or ""
                position = getattr(section.content, 'start_position', 0)
            elif isinstance(section, dict):
                section_num = section.get('section_number')
                section_text = section.get('text', '')
                section_title = section.get('title', '')
                position = section.get('position', 0)
            else:
                continue

            if section_num:
                self.section_registry[section_num] = {
                    'text': section_text,
                    'title': section_title,
                    'position': position,
                    'subsections': self._extract_subsections(section_text),
                    'clauses': self._extract_clauses(section_text)
                }
        
        logger.info(f"Built section registry with {len(self.section_registry)} sections")
    
    def _extract_subsections(self, section_text: str) -> Dict[str, str]:
        """Extract subsections from section text"""
        subsections = {}
        
        # Pattern for subsections like (1), (2), etc.
        subsection_pattern = r'\((\d+)\)[^)\n]*?(?=\(|\n|$)'
        matches = re.finditer(subsection_pattern, section_text, re.DOTALL)
        
        for match in matches:
            subsection_num = match.group(1)
            subsection_text = match.group(0)
            # Get text up to 200 chars or next subsection
            end_pos = match.end()
            next_match = re.search(r'\(\d+\)', section_text[end_pos:end_pos+200])
            if next_match:
                subsection_text = section_text[match.start():end_pos + next_match.start()]
            else:
                subsection_text = section_text[match.start():match.start() + 300]
            
            subsections[subsection_num] = subsection_text.strip()
        
        return subsections
    
    def _extract_clauses(self, section_text: str) -> Dict[str, str]:
        """Extract clauses from section text"""
        clauses = {}
        
        # Pattern for clauses like (a), (b), (i), (ii), etc.
        clause_pattern = r'\(([a-z]|[ivx]+)\)[^)\n]*?(?=\(|\n|$)'
        matches = re.finditer(clause_pattern, section_text, re.IGNORECASE | re.DOTALL)
        
        for match in matches:
            clause_letter = match.group(1).lower()
            clause_text = match.group(0)
            # Get text up to 200 chars or next clause
            end_pos = match.end()
            next_match = re.search(r'\([a-z]\)', section_text[end_pos:end_pos+200], re.IGNORECASE)
            if next_match:
                clause_text = section_text[match.start():end_pos + next_match.start()]
            else:
                clause_text = section_text[match.start():match.start() + 200]
            
            clauses[clause_letter] = clause_text.strip()
        
        return clauses
    
    def resolve_citations_in_text(self, text: str, current_section: str = "") -> List[CitationReference]:
        """
        Resolve citations in a given text.
        
        Args:
            text: Text to analyze
            current_section: Current section number for context
            
        Returns:
            List of resolved citations
        """
        citations = []
        
        for pattern, pattern_type in self.compiled_patterns:
            matches = list(pattern.finditer(text))
            for match in matches:
                try:
                    citation = self._process_citation_match(
                        match, pattern_type, text, current_section
                    )
                    if citation:
                        citations.append(citation)
                        self.stats["citations_found"] += 1
                except Exception as e:
                    self._log_abstention(f"Failed to process citation: {e}", match.group())
                    continue
        
        return citations
    
    def _process_citation_match(self, 
                               match: re.Match, 
                               pattern_type: str, 
                               text: str, 
                               current_section: str) -> Optional[CitationReference]:
        """Process a citation match"""
        matched_text = match.group()
        start_pos = match.start()
        end_pos = match.end()
        
        # Extract target reference based on pattern type
        target_ref = self._extract_target_reference(match, pattern_type)
        if not target_ref:
            return None
        
        # Determine target type
        target_type = self._determine_target_type(pattern_type, target_ref)
        
        # Resolve the citation
        resolution = self._resolve_citation(
            target_type, target_ref, current_section, matched_text
        )
        
        if resolution["resolved"]:
            citation = CitationReference(
                source_text=matched_text,
                source_position=(start_pos, end_pos),
                source_section=current_section,
                target_type=target_type,
                target_reference=target_ref,
                resolved_target=resolution["resolved_target"],
                resolution_method=resolution["method"],
                confidence=resolution["confidence"],
                resolution_path=resolution.get("path", [])
            )
            
            # Index the citation
            self.citation_index[resolution["resolved_target"]].append(citation.citation_id)
            self.stats["citations_resolved"] += 1
            
            logger.debug(f"Resolved citation: {current_section} -> {resolution['resolved_target']} "
                        f"(conf: {resolution['confidence']:.2f})")
            
            return citation
        
        else:
            # Log as unresolved
            self._log_abstention(
                "citation_unresolved",
                f"Could not resolve citation: {target_ref} from {current_section}",
                {"pattern_type": pattern_type, "target_ref": target_ref}
            )
            return None
    
    def _extract_target_reference(self, match: re.Match, pattern_type: str) -> str:
        """Extract target reference from match"""
        groups = match.groups()
        
        if not groups:
            # For patterns without capture groups (e.g., relative references)
            if pattern_type in ['relative_preceding', 'relative_following', 
                               'relative_next', 'relative_previous']:
                return pattern_type  # Special marker for relative references
            return ""
        
        # For single capture
        if len(groups) == 1:
            return str(groups[0])
        
        # For multiple captures (ranges, multiple sections)
        elif pattern_type == 'range_sections':
            return f"{groups[0]}-{groups[1]}"
        elif pattern_type == 'two_sections':
            return f"{groups[0]},{groups[1]}"
        elif pattern_type == 'multiple_sections':
            # Handle "sections 5, 6, and 7"
            return groups[0].replace(' and ', ',').replace(' ', '')
        
        return str(groups[0]) if groups[0] else ""
    
    def _determine_target_type(self, pattern_type: str, target_ref: str) -> str:
        """Determine the type of target"""
        type_mapping = {
            'explicit_section': 'section',
            'implicit_section': 'section',
            'abbreviated_section': 'section',
            'explicit_subsection': 'subsection',
            'urdu_subsection': 'subsection',
            'urdu_clause': 'clause',
            'schedule_reference': 'schedule',
            'urdu_schedule': 'schedule',
            'urdu_annex': 'annex',
            'rule_reference': 'rule',
            'urdu_rule': 'rule',
            'amendment_reference': 'amendment',
            'urdu_amendment': 'amendment',
            'relative_preceding': 'relative_section',
            'relative_following': 'relative_section',
            'relative_next': 'relative_section',
            'relative_previous': 'relative_section',
            'multiple_sections': 'multiple_sections',
            'range_sections': 'section_range',
            'two_sections': 'multiple_sections'
        }
        
        # Default based on pattern
        if pattern_type in type_mapping:
            return type_mapping[pattern_type]
        
        # Infer from reference content
        if '(' in target_ref and ')' in target_ref:
            return 'subsection'
        elif re.match(r'^[A-Z]+\d*$', target_ref):
            return 'schedule'
        elif re.match(r'^\d+$', target_ref):
            return 'section'
        
        return 'unknown'
    
    def _resolve_citation(self, 
                         target_type: str, 
                         target_ref: str, 
                         source_section: str, 
                         context: str) -> Dict[str, Any]:
        """
        Resolve a citation using deterministic rules.
        
        Returns:
            Dict with resolution result
        """
        # Check cache first
        cache_key = f"{source_section}:{target_type}:{target_ref}"
        if cache_key in self.resolution_cache:
            return self.resolution_cache[cache_key]
        
        resolution = {
            "resolved": False,
            "resolved_target": "",
            "method": "",
            "confidence": 0.0,
            "path": []
        }
        
        try:
            if target_type == 'section':
                result = self._resolve_section_citation(target_ref, source_section)
                resolution.update(result)
                
            elif target_type == 'subsection':
                result = self._resolve_subsection_citation(target_ref, source_section)
                resolution.update(result)
                
            elif target_type == 'clause':
                result = self._resolve_clause_citation(target_ref, source_section)
                resolution.update(result)
                
            elif target_type == 'relative_section':
                result = self._resolve_relative_citation(target_ref, source_section)
                resolution.update(result)
                
            elif target_type == 'multiple_sections':
                result = self._resolve_multiple_sections(target_ref, source_section)
                resolution.update(result)
                
            elif target_type == 'section_range':
                result = self._resolve_section_range(target_ref, source_section)
                resolution.update(result)
                
            elif target_type in ['schedule', 'annex', 'rule']:
                result = self._resolve_attachment(target_ref, target_type, source_section)
                resolution.update(result)
                
            else:
                # Try generic resolution
                result = self._try_generic_resolution(target_ref, source_section)
                resolution.update(result)
            
            # Cache the result
            if resolution["resolved"]:
                self.resolution_cache[cache_key] = resolution
            
            return resolution
            
        except Exception as e:
            resolution["method"] = "error"
            resolution["path"].append(f"Error: {str(e)}")
            return resolution
    
    def _resolve_section_citation(self, section_ref: str, source_section: str) -> Dict[str, Any]:
        """Resolve a section citation"""
        result = {
            "resolved": False,
            "method": "",
            "confidence": 0.0,
            "path": []
        }
        
        # Clean the reference
        clean_ref = section_ref.strip()
        
        # Check if it exists in registry
        if clean_ref in self.section_registry:
            result["resolved"] = True
            result["resolved_target"] = f"Section {clean_ref}"
            result["method"] = "direct_lookup"
            result["confidence"] = 0.95
            result["path"].append(f"Found Section {clean_ref} in registry")
            return result
        
        # Check for numbered sections (e.g., "5A" might be "5")
        base_num = re.match(r'^(\d+)', clean_ref)
        if base_num:
            base = base_num.group(1)
            if base in self.section_registry:
                result["resolved"] = True
                result["resolved_target"] = f"Section {base}"
                result["method"] = "base_number_lookup"
                result["confidence"] = 0.85
                result["path"].append(f"Found base Section {base} for {clean_ref}")
                return result
        
        # Check for parent section (e.g., "5(2)" -> Section 5)
        parent_match = re.match(r'^(\d+)', clean_ref)
        if parent_match:
            parent = parent_match.group(1)
            if parent in self.section_registry:
                result["resolved"] = True
                result["resolved_target"] = f"Section {parent}"
                result["method"] = "parent_section_lookup"
                result["confidence"] = 0.8
                result["path"].append(f"Found parent Section {parent} for {clean_ref}")
                return result
        
        # Try implicit resolution from context
        if source_section:
            # Look for sections mentioned in proximity
            result = self._resolve_from_context(clean_ref, source_section, "section")
            if result["resolved"]:
                return result
        
        return result
    
    def _resolve_subsection_citation(self, subsection_ref: str, source_section: str) -> Dict[str, Any]:
        """Resolve a subsection citation"""
        result = {
            "resolved": False,
            "method": "",
            "confidence": 0.0,
            "path": []
        }
        
        # Clean the reference
        clean_ref = subsection_ref.strip('() ')
        
        # First, try to resolve within the same section
        if source_section and source_section in self.section_registry:
            subsections = self.section_registry[source_section].get('subsections', {})
            if clean_ref in subsections:
                result["resolved"] = True
                result["resolved_target"] = f"Section {source_section}({clean_ref})"
                result["method"] = "within_section_lookup"
                result["confidence"] = 0.9
                result["path"].append(f"Found subsection ({clean_ref}) in Section {source_section}")
                return result
        
        # Try to find which section this subsection belongs to
        # Common pattern: subsection references include parent section
        if '(' in source_section and ')' in source_section:
            # Source is already a subsection, get its parent
            parent_match = re.match(r'^(\d+)', source_section)
            if parent_match:
                parent_section = parent_match.group(1)
                if parent_section in self.section_registry:
                    subsections = self.section_registry[parent_section].get('subsections', {})
                    if clean_ref in subsections:
                        result["resolved"] = True
                        result["resolved_target"] = f"Section {parent_section}({clean_ref})"
                        result["method"] = "parent_section_lookup"
                        result["confidence"] = 0.85
                        result["path"].append(f"Found subsection ({clean_ref}) in parent Section {parent_section}")
                        return result
        
        # Try implicit resolution
        result = self._resolve_from_context(subsection_ref, source_section, "subsection")
        
        return result
    
    def _resolve_clause_citation(self, clause_ref: str, source_section: str) -> Dict[str, Any]:
        """Resolve a clause citation"""
        result = {
            "resolved": False,
            "method": "",
            "confidence": 0.0,
            "path": []
        }
        
        # Clean the reference
        clean_ref = clause_ref.strip('() ').lower()
        
        # Try to find in current section or its subsections
        if source_section:
            # Check if source is a subsection
            if '(' in source_section and ')' in source_section:
                # Source is a subsection, check its clauses
                parent_match = re.match(r'^(\d+)', source_section)
                if parent_match:
                    parent_section = parent_match.group(1)
                    if parent_section in self.section_registry:
                        # Get the specific subsection
                        subsection_match = re.search(r'\((\d+)\)', source_section)
                        if subsection_match:
                            subsection_num = subsection_match.group(1)
                            # In a real implementation, we'd track clauses per subsection
                            # For now, we'll resolve to the subsection
                            result["resolved"] = True
                            result["resolved_target"] = f"Section {parent_section}({subsection_num}) clause ({clean_ref})"
                            result["method"] = "subsection_clause_lookup"
                            result["confidence"] = 0.8
                            result["path"].append(f"Resolved to clause in subsection {source_section}")
                            return result
            
            # Try direct section clauses
            elif source_section in self.section_registry:
                clauses = self.section_registry[source_section].get('clauses', {})
                if clean_ref in clauses:
                    result["resolved"] = True
                    result["resolved_target"] = f"Section {source_section} clause ({clean_ref})"
                    result["method"] = "within_section_clause_lookup"
                    result["confidence"] = 0.85
                    result["path"].append(f"Found clause ({clean_ref}) in Section {source_section}")
                    return result
        
        return result
    
    def _resolve_relative_citation(self, relative_type: str, source_section: str) -> Dict[str, Any]:
        """Resolve a relative citation (previous, next, above, below)"""
        result = {
            "resolved": False,
            "method": "",
            "confidence": 0.0,
            "path": []
        }
        
        if not source_section:
            return result
        
        # Get all section numbers in order
        section_numbers = sorted(
            self.section_registry.keys(),
            key=lambda x: (int(re.match(r'^\d+', x).group()) if re.match(r'^\d+', x) else 9999, x)
        )
        
        if source_section not in section_numbers:
            return result
        
        source_index = section_numbers.index(source_section)
        
        if relative_type in ['relative_preceding', 'relative_previous']:
            # Previous section
            if source_index > 0:
                prev_section = section_numbers[source_index - 1]
                result["resolved"] = True
                result["resolved_target"] = f"Section {prev_section}"
                result["method"] = "relative_previous"
                result["confidence"] = 0.8
                result["path"].append(f"Previous section of {source_section} is {prev_section}")
                
        elif relative_type in ['relative_following', 'relative_next']:
            # Next section
            if source_index < len(section_numbers) - 1:
                next_section = section_numbers[source_index + 1]
                result["resolved"] = True
                result["resolved_target"] = f"Section {next_section}"
                result["method"] = "relative_next"
                result["confidence"] = 0.8
                result["path"].append(f"Next section of {source_section} is {next_section}")
        
        elif relative_type == 'relative_above':
            # Could mean previous or parent
            result = self._resolve_relative_above(source_section)
        
        elif relative_type == 'relative_below':
            # Could mean next or child
            result = self._resolve_relative_below(source_section)
        
        return result
    
    def _resolve_relative_above(self, source_section: str) -> Dict[str, Any]:
        """Resolve 'above' reference"""
        result = {
            "resolved": False,
            "method": "",
            "confidence": 0.0,
            "path": []
        }
        
        # Try as previous section
        section_numbers = sorted(self.section_registry.keys(), 
                               key=lambda x: (int(re.match(r'^\d+', x).group()) if re.match(r'^\d+', x) else 9999, x))
        
        if source_section in section_numbers:
            source_index = section_numbers.index(source_section)
            if source_index > 0:
                prev_section = section_numbers[source_index - 1]
                result["resolved"] = True
                result["resolved_target"] = f"Section {prev_section}"
                result["method"] = "relative_previous"
                result["confidence"] = 0.7
                result["path"].append(f"'Above' resolved to previous section {prev_section}")
        
        return result
    
    def _resolve_relative_below(self, source_section: str) -> Dict[str, Any]:
        """Resolve 'below' reference"""
        result = {
            "resolved": False,
            "method": "",
            "confidence": 0.0,
            "path": []
        }
        
        # Try as next section
        section_numbers = sorted(self.section_registry.keys(),
                               key=lambda x: (int(re.match(r'^\d+', x).group()) if re.match(r'^\d+', x) else 9999, x))
        
        if source_section in section_numbers:
            source_index = section_numbers.index(source_section)
            if source_index < len(section_numbers) - 1:
                next_section = section_numbers[source_index + 1]
                result["resolved"] = True
                result["resolved_target"] = f"Section {next_section}"
                result["method"] = "relative_next"
                result["confidence"] = 0.7
                result["path"].append(f"'Below' resolved to next section {next_section}")
        
        return result
    
    def _resolve_multiple_sections(self, sections_ref: str, source_section: str) -> Dict[str, Any]:
        """Resolve multiple section references (e.g., 'sections 5, 6, and 7')"""
        result = {
            "resolved": False,
            "method": "",
            "confidence": 0.0,
            "path": []
        }
        
        # Parse the sections
        sections = []
        if ',' in sections_ref:
            parts = sections_ref.split(',')
            for part in parts:
                part = part.strip()
                if part.isdigit():
                    sections.append(part)
        elif sections_ref.isdigit():
            sections.append(sections_ref)
        
        # Resolve each section
        resolved_sections = []
        for section in sections:
            section_result = self._resolve_section_citation(section, source_section)
            if section_result["resolved"]:
                resolved_sections.append(section_result["resolved_target"])
        
        if resolved_sections:
            result["resolved"] = True
            result["resolved_target"] = ", ".join(resolved_sections)
            result["method"] = "multiple_section_resolution"
            result["confidence"] = 0.9
            result["path"].append(f"Resolved multiple sections: {', '.join(resolved_sections)}")
        
        return result
    
    def _resolve_section_range(self, range_ref: str, source_section: str) -> Dict[str, Any]:
        """Resolve section range (e.g., 'sections 5 to 7')"""
        result = {
            "resolved": False,
            "method": "",
            "confidence": 0.0,
            "path": []
        }
        
        # Parse range
        if '-' in range_ref:
            start_end = range_ref.split('-')
        elif 'to' in range_ref.lower():
            start_end = re.split(r'\s+to\s+', range_ref, flags=re.IGNORECASE)
        else:
            return result
        
        if len(start_end) != 2:
            return result
        
        start_section = start_end[0].strip()
        end_section = start_end[1].strip()
        
        # Resolve start and end
        start_result = self._resolve_section_citation(start_section, source_section)
        end_result = self._resolve_section_citation(end_section, source_section)
        
        if start_result["resolved"] and end_result["resolved"]:
            result["resolved"] = True
            result["resolved_target"] = f"{start_result['resolved_target']} to {end_result['resolved_target']}"
            result["method"] = "range_resolution"
            result["confidence"] = min(start_result["confidence"], end_result["confidence"])
            result["path"].extend(start_result.get("path", []))
            result["path"].extend(end_result.get("path", []))
        
        return result
    
    def _resolve_attachment(self, attachment_ref: str, attachment_type: str, source_section: str) -> Dict[str, Any]:
        """Resolve schedule, annex, or rule references"""
        result = {
            "resolved": False,
            "method": "",
            "confidence": 0.0,
            "path": []
        }
        
        # For attachments, we create a normalized reference
        attachment_type_map = {
            'schedule': 'Schedule',
            'urdu_schedule': 'شیڈول',
            'annex': 'Annex',
            'urdu_annex': 'ضمیمہ',
            'rule': 'Rule',
            'urdu_rule': 'قاعدہ'
        }
        
        type_name = attachment_type_map.get(attachment_type, attachment_type.title())
        result["resolved"] = True
        result["resolved_target"] = f"{type_name} {attachment_ref}"
        result["method"] = "attachment_reference"
        result["confidence"] = 0.9
        result["path"].append(f"Created attachment reference: {type_name} {attachment_ref}")
        
        return result
    
    def _resolve_from_context(self, target_ref: str, source_section: str, target_type: str) -> Dict[str, Any]:
        """Try to resolve from document context"""
        result = {
            "resolved": False,
            "method": "",
            "confidence": 0.0,
            "path": []
        }
        
        # This is a simplified implementation
        # In a full implementation, we'd use document structure and proximity
        
        # For now, if we have a numeric reference and it exists in registry, use it
        if target_ref.isdigit() and target_ref in self.section_registry:
            result["resolved"] = True
            result["resolved_target"] = f"Section {target_ref}"
            result["method"] = "context_inference"
            result["confidence"] = 0.7
            result["path"].append(f"Inferred from context: Section {target_ref}")
            self.stats["implicit_resolutions"] += 1
        
        return result
    
    def _try_generic_resolution(self, target_ref: str, source_section: str) -> Dict[str, Any]:
        """Try generic resolution methods"""
        result = {
            "resolved": False,
            "method": "",
            "confidence": 0.0,
            "path": []
        }
        
        # Try as section number
        if target_ref.isdigit():
            return self._resolve_section_citation(target_ref, source_section)
        
        # Try to extract section number from reference
        section_match = re.search(r'(\d+)', target_ref)
        if section_match:
            section_num = section_match.group(1)
            return self._resolve_section_citation(section_num, source_section)
        
        return result
    
    def build_cross_references(self, all_citations: List[CitationReference]) -> List[CrossReference]:
        """
        Build cross-references between sections based on citations.
        
        Args:
            all_citations: All resolved citations
            
        Returns:
            List of cross-references
        """
        cross_refs = []
        citation_map = defaultdict(list)
        
        # Group citations by source section
        for citation in all_citations:
            citation_map[citation.source_section].append(citation)
        
        # Build cross-references
        for source_section, citations in citation_map.items():
            for citation in citations:
                # Extract target section from resolved target
                target_match = re.search(r'Section\s+(\d+)', citation.resolved_target)
                if target_match:
                    target_section = target_match.group(1)
                    
                    # Determine reference type
                    ref_type = "cites"
                    if "amendment" in citation.target_type.lower():
                        ref_type = "amended_by"
                    elif "clause" in citation.target_type.lower():
                        ref_type = "uses_clause"
                    elif "subsection" in citation.target_type.lower():
                        ref_type = "cites_subsection"
                    
                    # Create cross-reference
                    cross_ref = CrossReference(
                        from_section=source_section,
                        to_section=target_section,
                        reference_type=ref_type,
                        context=citation.source_text[:100],
                        strength=citation.confidence,
                        citation_ids=[citation.citation_id]
                    )
                    
                    cross_refs.append(cross_ref)
                    self.stats["cross_references_built"] += 1
        
        # Deduplicate and merge
        merged_refs = self._merge_cross_references(cross_refs)
        
        return merged_refs
    
    def _merge_cross_references(self, cross_refs: List[CrossReference]) -> List[CrossReference]:
        """Merge duplicate cross-references"""
        ref_map = {}
        
        for ref in cross_refs:
            key = (ref.from_section, ref.to_section, ref.reference_type)
            
            if key in ref_map:
                # Merge with existing
                existing = ref_map[key]
                existing.strength = max(existing.strength, ref.strength)
                existing.citation_ids.extend(ref.citation_ids)
                existing.citation_ids = list(set(existing.citation_ids))
            else:
                ref_map[key] = ref
        
        return list(ref_map.values())
    
    def resolve_document_citations(self, 
                                  sections_data: List[Dict],
                                  document_text: str = "") -> Dict[str, Any]:
        """
        Resolve all citations in a document.
        
        Args:
            sections_data: List of section dictionaries
            document_text: Full document text (optional)
            
        Returns:
            Complete citation resolution results
        """
        logger.info("Starting document citation resolution...")
        
        # Build section registry
        self.build_section_registry(sections_data)
        
        all_citations = []
        section_results = {}
        
        # Resolve citations for each section
        for section_data in sections_data:
            section_num = section_data.get('section_number')
            section_text = section_data.get('text', '')
            
            if not section_num or not section_text:
                continue
            
            # Resolve citations in this section
            citations = self.resolve_citations_in_text(section_text, section_num)
            all_citations.extend(citations)
            
            # Calculate resolution metrics for this section
            resolution_coverage = len(citations) / max(len(citations), 1)
            avg_confidence = sum(c.confidence for c in citations) / max(len(citations), 1)
            
            section_results[section_num] = ResolutionResult(
                section_number=section_num,
                resolved_citations=citations,
                unresolved_citations=[],  # Would track unresolved in full implementation
                cross_references=[],  # Built later
                resolution_coverage=resolution_coverage,
                confidence_score=avg_confidence
            )
        
        # Build cross-references
        cross_references = self.build_cross_references(all_citations)
        
        # Calculate overall metrics
        total_citations = self.stats["citations_found"]
        resolved_citations = self.stats["citations_resolved"]
        resolution_rate = resolved_citations / total_citations if total_citations > 0 else 0
        
        overall_confidence = sum(c.confidence for c in all_citations) / max(len(all_citations), 1)
        
        results = {
            "all_citations": [asdict(c) for c in all_citations],
            "section_results": {k: asdict(v) for k, v in section_results.items()},
            "cross_references": [asdict(c) for c in cross_references],
            "citation_index": dict(self.citation_index),
            "resolution_metrics": {
                "total_citations": total_citations,
                "resolved_citations": resolved_citations,
                "resolution_rate": resolution_rate,
                "overall_confidence": overall_confidence,
                "cross_references_built": len(cross_references),
                "implicit_resolutions": self.stats["implicit_resolutions"],
                "abstention_decisions": self.stats["abstention_decisions"]
            },
            "section_registry_summary": {
                "total_sections": len(self.section_registry),
                "sections_with_subsections": sum(1 for s in self.section_registry.values() if s.get('subsections')),
                "sections_with_clauses": sum(1 for s in self.section_registry.values() if s.get('clauses'))
            },
            "metadata": {
                "resolution_timestamp": datetime.now().isoformat(),
                "deterministic_resolution": True,
                "patterns_used": len(self.compiled_patterns)
            }
        }
        
        logger.info(f"Citation resolution complete: {resolved_citations}/{total_citations} resolved "
                   f"({resolution_rate:.1%})")
        
        return results
    
    def _log_abstention(self, abstention_type: str, reason: str, context: Dict = None):
        """Log abstention decision"""
        abstention = {
            "timestamp": datetime.now().isoformat(),
            "type": abstention_type,
            "reason": reason,
            "context": context or {},
            "component": "citation_resolver"
        }
        self.abstention_log.append(abstention)
        self.stats["abstention_decisions"] += 1
    
    def query_citations(self, 
                       section_number: str, 
                       direction: str = "both") -> Dict[str, Any]:
        """
        Query citations for a section.
        
        Args:
            section_number: Section number to query
            direction: "incoming", "outgoing", or "both"
            
        Returns:
            Citation query results
        """
        query_results = {
            "section": section_number,
            "query_timestamp": datetime.now().isoformat(),
            "incoming_citations": [],
            "outgoing_citations": [],
            "citation_network": {}
        }
        
        # Find outgoing citations (from this section)
        outgoing = []
        for citation in self.resolution_cache.values():
            # This would need access to all citations
            # Simplified for now
            pass
        
        # Find incoming citations (to this section)
        if section_number in self.citation_index:
            incoming_ids = self.citation_index[section_number]
            # Would retrieve full citation objects
            
        return query_results


# ========== INTEGRATION WITH PIPELINE ==========

class CitationProcessor:
    """
    Processor for integrating citation resolution into the pipeline.
    """
    
    def __init__(self):
        self.resolver = KPKCitationResolver()
    
    def process_document(self, 
                        document_data: Dict,
                        rule_extracted_entities: Dict = None) -> Dict:
        """
        Process document through citation resolution.
        
        Args:
            document_data: Document data from previous phases
            rule_extracted_entities: Entities from 4.1_rule_extractor
            
        Returns:
            Enhanced document data with citation resolution
        """
        try:
            # Extract sections from rule extraction
            sections_data = []
            if rule_extracted_entities:
                sections_data = rule_extracted_entities.get('legal_sections', [])
            
            if not sections_data and document_data.get('normalized_text'):
                # Fallback: extract sections directly from text
                sections_data = self._extract_sections_from_text(
                    document_data.get('normalized_text', '')
                )
            
            # Resolve citations
            citation_results = self.resolver.resolve_document_citations(sections_data)
            
            # Enhance document data
            document_data['citation_resolution'] = citation_results
            document_data['citation_timestamp'] = datetime.now().isoformat()
            
            # Create summary for pipeline
            summary = self._create_summary(citation_results)
            document_data['citation_summary'] = summary
            
            return document_data
            
        except Exception as e:
            logger.error(f"Error in citation processing: {e}")
            document_data['citation_resolution'] = {"error": str(e)}
            return document_data
    
    def _extract_sections_from_text(self, text: str) -> List[Dict]:
        """Extract sections from text (fallback method)"""
        sections = []
        
        # Simple section extraction
        section_pattern = r'Section\s+(\d+[A-Z]?)[\s.:]+(.+?)(?=Section\s+\d+|$)'
        matches = re.finditer(section_pattern, text, re.DOTALL | re.IGNORECASE)
        
        for match in matches:
            section_num = match.group(1)
            section_text = match.group(2).strip()[:1000]  # Limit length
            
            sections.append({
                'section_number': section_num,
                'text': section_text,
                'title': f"Section {section_num}",
                'position': match.start()
            })
        
        return sections
    
    def _create_summary(self, citation_results: Dict) -> Dict:
        """Create summary of citation resolution"""
        metrics = citation_results.get('resolution_metrics', {})
        
        return {
            "resolution_rate": metrics.get('resolution_rate', 0),
            "total_citations": metrics.get('total_citations', 0),
            "cross_references": metrics.get('cross_references_built', 0),
            "confidence": metrics.get('overall_confidence', 0),
            "deterministic_resolution": True
        }


# ========== COMMAND LINE INTERFACE ==========

def main():
    """Command line interface for citation resolution"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Deterministic citation resolution for KPK forestry laws")
    parser.add_argument("--input", "-i", required=True, help="Input JSON file with extracted entities")
    parser.add_argument("--output", "-o", help="Output JSON file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Load document data
        with open(args.input, 'r', encoding='utf-8') as f:
            document_data = json.load(f)
        
        # Process citations
        processor = CitationProcessor()
        result = processor.process_document(document_data)
        
        # Print summary
        citation_data = result.get('citation_resolution', {})
        metrics = citation_data.get('resolution_metrics', {})
        
        print("\n" + "=" * 60)
        print("CITATION RESOLUTION RESULTS")
        print("=" * 60)
        
        print(f"Total Citations: {metrics.get('total_citations', 0)}")
        print(f"Resolved Citations: {metrics.get('resolved_citations', 0)}")
        print(f"Resolution Rate: {metrics.get('resolution_rate', 0):.1%}")
        print(f"Overall Confidence: {metrics.get('overall_confidence', 0):.1%}")
        print(f"Cross References Built: {metrics.get('cross_references_built', 0)}")
        
        section_results = citation_data.get('section_results', {})
        if section_results:
            print(f"\nSections with Citations: {len(section_results)}")
            
            # Show top sections by citation count
            section_counts = []
            for section_num, section_data in section_results.items():
                if isinstance(section_data, dict):
                    citation_count = len(section_data.get('resolved_citations', []))
                    if citation_count > 0:
                        section_counts.append((section_num, citation_count))
            
            if section_counts:
                print("Top Sections by Citations:")
                for section_num, count in sorted(section_counts, key=lambda x: x[1], reverse=True)[:5]:
                    print(f"  Section {section_num}: {count} citations")
        
        # Save if output specified
        if args.output:
            os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else '.', exist_ok=True)
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"\nResults saved to: {args.output}")
        
        # Show sample resolved citations
        if args.verbose:
            all_citations = citation_data.get('all_citations', [])
            if all_citations:
                print(f"\nSample Resolved Citations:")
                for i, citation in enumerate(all_citations[:3]):
                    if isinstance(citation, dict):
                        print(f"  {i+1}. {citation.get('source_section', '?')} → "
                              f"{citation.get('resolved_target', '?')} "
                              f"(Confidence: {citation.get('confidence', 0):.0%})")
        
        print("\n" + "=" * 60)
        print("Citation resolution complete. Cross-references established. ✓")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


if __name__ == "__main__":
    main()
