"""
KPK RULE EXTRACTOR - Phase 4.1 of KPK Legal Extraction
Deterministic extraction of legal entities and rules from normalized text.
OPERATING PRINCIPLE: "Rules Decide" - LLMs only suggest, rules make final decisions.
"""

import re
import json
import logging
import hashlib
from typing import Dict, List, Any, Tuple, Optional, Set, Generator
from dataclasses import dataclass, asdict, field
from collections import defaultdict, deque
import sys
import os
from preprocessing_pipeline.common.identity import IdentityFactory
from datetime import datetime
import yaml  # For rule configuration

# Add project root to path for config import
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from config.kpk_forestry_config import (
        KPK_GOVERNMENT_ENTITIES, KPK_OFFICER_RANKS, KPK_TREE_SPECIES,
        KPK_FOREST_DIVISIONS, KPK_FOREST_TYPES, KPK_EXTRACTION_PATTERNS,
        KPK_MULTILINGUAL_TERMS, KPK_LEGAL_HIERARCHY, TreeLegalStatus, 
        OfficerRank, TreeSpecies, KPK_LEGAL_JURISDICTIONS
    )
    KPK_CONFIG_LOADED = True
except ImportError:
    KPK_CONFIG_LOADED = False
    print("Warning: KPK Configuration not found. Using fallback rule sets.")

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class ExtractionRule:
    """A deterministic extraction rule"""
    name: str
    pattern: str
    pattern_type: str  # regex, keyword, context_window
    entity_type: str
    confidence: float = 1.0
    multilingual: bool = False
    jurisdiction: str = "KPK"  # KPK, Federal, Both
    validation_logic: Optional[str] = None
    priority: int = 1  # 1-3, higher = more specific
    
    def __post_init__(self):
        # Compile regex if pattern_type is regex
        if self.pattern_type == "regex":
            flags = re.IGNORECASE | re.MULTILINE | re.DOTALL
            if self.multilingual:
                flags |= re.UNICODE
            self.compiled_pattern = re.compile(self.pattern, flags)
        else:
            self.compiled_pattern = None


@dataclass
class ExtractedEntity:
    """Base extracted entity with deterministic confidence"""
    entity_type: str
    value: Any
    context: str
    position: Tuple[int, int]
    rule_used: str
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    entity_id: str = ""
    
    def __post_init__(self):
        if not self.entity_id:
            # Standardize identity using IdentityFactory contract
            canon = IdentityFactory.canonicalize(str(self.value), role=self.entity_type)
            self.metadata["canonical_name"] = canon["canonical_name"]
            self.metadata["identity_namespace"] = canon["identity_namespace"]
            self.metadata["display_name"] = canon["display_name"]
            
            # Generate deterministic ID using standard factory
            self.entity_id = IdentityFactory.generate_deterministic_id(
                namespace=self.metadata.get("namespace", "greenlaw_kpk"),
                label=self.entity_type,
                name=str(self.value),
                role=self.entity_type
            )


@dataclass
class LegalSection:
    """Extracted legal section with hierarchical structure"""
    section_number: str
    title: str = ""
    raw_text: str = ""        # Original PDF/OCR text (unmodified)
    sanitized_text: str = ""  # LLM-sanitized text (clean)
    text: str = ""            # Default (maps to sanitized_text)
    subsection: str = ""
    clause: str = ""
    subclause: str = ""
    parent_section: str = ""
    section_path: str = ""  # e.g., 5.2.a.i
    parent_id: str = ""     # Deterministic ID of parent section
    amendments: List[str] = field(default_factory=list)
    effective_date: str = ""
    repealed_date: str = ""
    confidence: float = 1.0
    
    def get_full_reference(self) -> str:
        """Get full section reference (e.g., Section 5(2)(a))"""
        ref = f"Section {self.section_number}"
        if self.subsection:
            ref += f"({self.subsection})"
        if self.clause:
            ref += f"({self.clause})"
        return ref


@dataclass
class PenaltyRule:
    """Deterministic penalty calculation rule"""
    offense: str
    base_amount: float
    calculation_logic: str  # fixed, per_unit, percentage, escalating
    unit: str = ""
    conditions: List[str] = field(default_factory=list)
    jurisdiction: str = "KPK"
    legal_basis: str = ""  # Section reference
    confidence: float = 1.0
    
    def calculate_penalty(self, quantity: float = 1.0, aggravating_factors: List[str] = None) -> float:
        """Calculate penalty based on deterministic rules"""
        amount = self.base_amount
        
        if self.calculation_logic == "per_unit":
            amount *= quantity
        elif self.calculation_logic == "escalating" and aggravating_factors:
            # 20% increase per aggravating factor (deterministic)
            amount *= (1.0 + (0.2 * len(aggravating_factors)))
        
        # Round to nearest 100
        amount = round(amount / 100) * 100
        return amount


class KPKRuleExtractor:
    """
    Deterministic rule-based extractor for KPK forestry legal documents.
    Implements "Rules Decide" philosophy - no LLM interpretation.
    """
    
    def __init__(self, config: Optional[Any] = None, rule_config_path: str = None):
        self.config = config
        self.initialize_rules(rule_config_path)
        self.initialize_deterministic_patterns()
        self.extraction_stats = defaultdict(int)
        self.abstention_log = []
        
    def initialize_rules(self, rule_config_path: str = None):
        """Initialize extraction rules from config or defaults"""
        self.rules = []
        
        # Try to load from config file first
        if rule_config_path and os.path.exists(rule_config_path):
            try:
                with open(rule_config_path, 'r', encoding='utf-8') as f:
                    rule_configs = yaml.safe_load(f)
                
                for rule_config in rule_configs.get('extraction_rules', []):
                    rule = ExtractionRule(**rule_config)
                    self.rules.append(rule)
                logger.info(f"Loaded {len(self.rules)} rules from {rule_config_path}")
                return
            except Exception as e:
                logger.warning(f"Failed to load rule config: {e}. Using defaults.")
        
        # Default deterministic rules for KPK forestry
        default_rules = [
            # SECTION RULES
            ExtractionRule(
                name="section_reference_main",
                pattern=r'(?:Section|S\.|دَفْعَہ|دفعہ|مادہ)\s+(\d+[A-Z]?(?:-\d+)?(?:\(\d+\)(?:\(\w+\))?)?)',
                pattern_type="regex",
                entity_type="legal_section",
                confidence=0.95,
                multilingual=True,
                priority=3
            ),
            
            # PENALTY/FINE RULES
            ExtractionRule(
                name="penalty_amount_pkr",
                pattern=r'fine\s+(?:of|not\s+exceeding)\s+Rs\.?\s*([\d,]+(?:\.\d{2})?(?:\s*lakh|\s*crore|\s*thousand)?)',
                pattern_type="regex",
                entity_type="penalty_amount",
                confidence=0.9,
                multilingual=False,
                priority=2
            ),
            ExtractionRule(
                name="penalty_amount_urdu",
                pattern=r'جرمانہ\s+(?:کی\s+)?رقم\s+روپے\s*([\d,]+(?:\s*لاکھ|\s*کروڑ|\s*ہزار)?)',
                pattern_type="regex",
                entity_type="penalty_amount",
                confidence=0.9,
                multilingual=True,
                priority=2
            ),
            
            # TREE SPECIES RULES
            ExtractionRule(
                name="protected_species",
                pattern=r'\b(?:protected|prohibited|restricted|ممنوع|محفوظ)\s+(?:tree|species|درخت)\s+(?:named|called|کے\s+نام)\s+["\']?([^"\'.]+?)["\']?',
                pattern_type="regex",
                entity_type="tree_species",
                confidence=0.85,
                multilingual=True,
                priority=2
            ),
            
            # OFFICER RULES
            ExtractionRule(
                name="officer_with_powers",
                pattern=r'\b(?:DFO|SDFO|RO|Range Officer|بیٹ گارڈ|فورسٹ گارڈ)\s+(?:may|shall|is\s+authorized|مقرر|اختیار)\s+(?:to\s+)?([^\.]+?)(?=\.|\n|;)',
                pattern_type="regex",
                entity_type="officer_power",
                confidence=0.8,
                multilingual=True,
                priority=2
            ),
            
            # AMENDMENT RULES
            ExtractionRule(
                name="amendment_marker",
                pattern=r'\[(\d+)\]\s+(?:Substituted|Inserted|Omitted|Deleted|Added)\s+by\s+(.+?)(?=\[|\n|$)',
                pattern_type="regex",
                entity_type="amendment",
                confidence=0.95,
                multilingual=False,
                priority=3
            ),
            
            # DATE RULES
            ExtractionRule(
                name="gazette_date",
                pattern=r'Gazette\s+(?:of\s+)?(?:Pakistan|KPK|Khyber\s+Pakhtunkhwa)[^,]*?(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December|جنوری|فروری|مارچ|اپریل|مئی|جون|جولائی|اگست|ستمبر|اکتوبر|نومبر|دسمبر)\s+\d{4})',
                pattern_type="regex",
                entity_type="gazette_date",
                confidence=0.9,
                multilingual=True,
                priority=2
            ),
            
            # JURISDICTION RULES
            ExtractionRule(
                name="kpk_jurisdiction",
                pattern=r'\b(?:KPK|Khyber\s+Pakhtunkhwa|صوبہ\s+خیبر\s+پختونخوا)\s+(?:Forest|جنگلات)\s+(?:Department|Act|Rules|محکمہ|ایکٹ|قواعد)',
                pattern_type="regex",
                entity_type="jurisdiction",
                confidence=0.95,
                multilingual=True,
                priority=3
            ),
        ]
        
        self.rules.extend(default_rules)
        logger.info(f"Initialized {len(self.rules)} default extraction rules")
    
    def initialize_deterministic_patterns(self):
        """Initialize deterministic patterns for specific entity types"""
        
        # Tree species patterns (deterministic lookup)
        self.species_patterns = {
            'deodar': {
                'regex': r'\b(deodar|cedar|دیار)\b',
                'common_name': 'Deodar Cedar',
                'scientific_name': 'Cedrus deodara',
                'legal_status': 'protected'
            },
            'chir_pine': {
                'regex': r'\b(chir\s+pine|chirpine|چیر)\b',
                'common_name': 'Chir Pine',
                'scientific_name': 'Pinus roxburghii',
                'legal_status': 'regulated'
            },
            'kail': {
                'regex': r'\b(kail|blue\s+pine|کائل)\b',
                'common_name': 'Kail/Blue Pine',
                'scientific_name': 'Pinus wallichiana',
                'legal_status': 'protected'
            },
            # Add more species...
        }
        
        # Officer hierarchy patterns
        self.officer_patterns = {
            'DFO': {
                'regex': r'\b(Divisional Forest Officer|DFO)\b',
                'authority_level': 3,
                'reports_to': 'CF'
            },
            'SDFO': {
                'regex': r'\b(Sub-Divisional Forest Officer|SDFO)\b',
                'authority_level': 4,
                'reports_to': 'DFO'
            },
            'RO': {
                'regex': r'\b(Range Officer|RO|رینج آفیسر)\b',
                'authority_level': 5,
                'reports_to': 'SDFO'
            },
            # Add more officers...
        }
        
        # Penalty calculation rules (deterministic)
        self.penalty_rules = [
            PenaltyRule(
                offense="illegal cutting of protected tree",
                base_amount=50000.0,
                calculation_logic="per_unit",
                unit="tree",
                conditions=["without permit", "in protected area"],
                jurisdiction="KPK",
                legal_basis="Section 26(2)",
                confidence=0.95
            ),
            PenaltyRule(
                offense="transport without transit permit",
                base_amount=25000.0,
                calculation_logic="fixed",
                unit="vehicle",
                conditions=["no permit", "false documentation"],
                jurisdiction="KPK",
                legal_basis="Section 33(1)",
                confidence=0.9
            ),
            # Add more penalty rules...
        ]
        
        # Legal hierarchy (deterministic)
        self.legal_hierarchy = {
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
    
    def extract_all_entities(self, text: str, doc_metadata: Dict = None) -> Dict[str, Any]:
        """
        Extract all entities using deterministic rules only.
        
        Args:
            text: Normalized text to extract from
            doc_metadata: Document metadata for context
            
        Returns:
            Dictionary containing all extracted entities and confidence metrics
        """
        logger.info("Starting deterministic rule extraction...")
        
        # Reset stats and logs
        self.extraction_stats = defaultdict(int)
        self.abstention_log = []
        
        try:
            # Apply all extraction rules in order of priority
            all_entities = {
                "legal_sections": self.extract_legal_sections(text),
                "penalties": self.extract_penalties(text),
                "tree_species": self.extract_tree_species(text),
                "officers": self.extract_officers(text),
                "amendments": self.extract_amendments(text),
                "jurisdictions": self.extract_jurisdictions(text),
                "dates": self.extract_dates(text),
                "gazettes": self.extract_gazette_references(text),
                "cross_references": self.extract_cross_references(text),
                "deterministic_rules_applied": len(self.rules),
                "abstention_decisions": len(self.abstention_log),
                "extraction_metadata": self._generate_extraction_metadata(text, doc_metadata)
            }
            
            # Apply deterministic relationship extraction
            all_entities["relationships"] = self.extract_relationships(
                all_entities, text, doc_metadata
            )
            
            # Apply legal hierarchy resolution
            all_entities["hierarchy_resolved"] = self.resolve_legal_hierarchy(
                all_entities, doc_metadata
            )
            
            # Calculate overall confidence
            all_entities["confidence_metrics"] = self._calculate_confidence_metrics(all_entities)
            
            # Log extraction summary
            self._log_extraction_summary(all_entities)
            
            # Forensic Invariants Injection (v2.3 Hardened)
            source_doc_id = doc_metadata.get('document_id') or doc_metadata.get('source_doc_id', 'unknown') if doc_metadata else 'unknown'
            source_bbox = doc_metadata.get('bbox') or doc_metadata.get('logical_span', 'N/A') if doc_metadata else 'N/A'
            
            for entity_list_key in ["legal_sections", "penalties", "tree_species", "officers", "amendments", "jurisdictions", "dates", "gazettes", "cross_references"]:
                for entity in all_entities.get(entity_list_key, []):
                    if isinstance(entity, dict):
                        # Inject into properties if present, else top-level
                        target = entity.get("properties", entity)
                        target["source_doc_id"] = source_doc_id
                        target["bbox"] = source_bbox
                        target["extraction_phase"] = "phase_4.1"
                        if "confidence_score" not in target:
                            target["confidence_score"] = entity.get("confidence", 0.8)
            
            return all_entities
            
        except Exception as e:
            logger.error(f"Error during rule extraction: {e}")
            return self._create_error_response(e, text)
    
    def extract_legal_sections(self, text: str) -> List[Dict]:
        """Extract legal sections using deterministic patterns"""
        sections = []
        seen_sections = set()
        
        # Pattern 1: Main section numbers
        patterns = [
            (r'Section\s+(\d+[A-Z]?)', 'main'),
            (r'S\.\s*(\d+)', 'abbrev'),
            (r'دَفْعَہ\s*(\d+)', 'urdu'),
            (r'مادہ\s*(\d+)', 'urdu_alt'),
        ]
        
        for pattern, pattern_type in patterns:
            regex = re.compile(pattern, re.IGNORECASE | re.UNICODE)
            for match in regex.finditer(text):
                section_num = match.group(1)
                if section_num in seen_sections:
                    continue
                
                # Get section text (next 200 chars or until next section)
                start_pos = match.end()
                next_section_match = re.search(r'Section\s+\d+', text[start_pos:start_pos+500])
                if next_section_match:
                    end_pos = start_pos + next_section_match.start()
                else:
                    end_pos = start_pos + 500
                
                section_text = text[start_pos:end_pos].strip()
                
                # Improved hierarchical parsing for section numbers like 5(2)(a)(i)
                parts = re.findall(r'([^()]+|\([^()]+\))', section_num)
                clean_parts = []
                for p in parts:
                    clean_p = p.strip('()')
                    if clean_p:
                        clean_parts.append(clean_p)
                
                main_num = clean_parts[0] if clean_parts else section_num
                sub = clean_parts[1] if len(clean_parts) > 1 else ""
                clsz = clean_parts[2] if len(clean_parts) > 2 else ""
                subclsz = clean_parts[3] if len(clean_parts) > 3 else ""
                
                # Build canonical section path for Identity Layer
                section_path = ".".join(clean_parts)
                
                # Build identity contract
                canon = IdentityFactory.canonicalize(section_num, role="Section")
                
                section = LegalSection(
                    section_number=main_num,
                    raw_text=section_text[:1000],
                    sanitized_text=section_text[:1000],
                    text=section_text[:1000],
                    subsection=sub,
                    clause=clsz,
                    subclause=subclsz,
                    section_path=section_path,
                    confidence=self._calculate_section_confidence(section_num, section_text)
                )
                
                # Attach identity contract to metadata
                section_dict = asdict(section)
                section_dict["canonical_name"] = canon["canonical_name"]
                section_dict["identity_namespace"] = canon["identity_namespace"]
                
                # Generate stable ID
                section_dict["node_id"] = IdentityFactory.generate_deterministic_id(
                    namespace="greenlaw_kpk",
                    label="Section",
                    name=section_num,
                    role="Section"
                )
                
                sections.append(section_dict)
                seen_sections.add(section_num)
                self.extraction_stats["legal_sections"] += 1
        
        # Sort sections by number
        sections.sort(key=lambda x: self._parse_section_number(x['section_number']))
        
        return sections
    
    def extract_penalties(self, text: str) -> List[Dict]:
        """Extract penalty rules deterministically"""
        penalties = []
        
        # Pattern 1: Fine amounts with Rs.
        fine_patterns = [
            (r'fine\s+(?:of|not\s+exceeding)\s+Rs\.?\s*([\d,]+(?:\.\d{2})?)', 'fine'),
            (r'Rs\.?\s*([\d,]+)\s+(?:as\s+)?fine', 'fine_reverse'),
            (r'جرمانہ\s+(?:کی\s+)?رقم\s+روپے\s*([\d,]+)', 'fine_urdu'),
            (r'لاکھ\s+روپے\s+تک\s+جرمانہ', 'lakh_fine'),
            (r'کروڑ\s+روپے\s+تک\s+جرمانہ', 'crore_fine'),
        ]
        
        for pattern, pattern_type in fine_patterns:
            regex = re.compile(pattern, re.IGNORECASE | re.UNICODE)
            for match in regex.finditer(text):
                try:
                    amount_str = match.group(1) if pattern_type in ['fine', 'fine_reverse', 'fine_urdu'] else ""
                    
                    if pattern_type == 'lakh_fine':
                        amount = 100000  # 1 lakh
                    elif pattern_type == 'crore_fine':
                        amount = 10000000  # 1 crore
                    elif amount_str:
                        amount = float(amount_str.replace(',', ''))
                    else:
                        continue
                    
                    # Get context
                    context = self._get_context(text, match.start(), match.end())
                    
                    # Determine offense from context
                    offense = self._extract_offense_from_context(context)
                    
                    # Apply penalty rules if available
                    calculated_amount = amount
                    applicable_rule = None
                    for rule in self.penalty_rules:
                        if rule.offense.lower() in offense.lower():
                            calculated_amount = rule.calculate_penalty()
                            applicable_rule = rule.offense
                            break
                    
                    penalty = {
                        'amount': calculated_amount,
                        'original_amount': amount,
                        'currency': 'PKR',
                        'offense': offense,
                        'context': context[:300],
                        'rule_applied': applicable_rule,
                        'confidence': self._calculate_penalty_confidence(match.group(), context),
                        'deterministic': True
                    }
                    
                    penalties.append(penalty)
                    self.extraction_stats["penalties"] += 1
                    
                except (ValueError, AttributeError) as e:
                    self._log_abstention(f"Failed to parse penalty: {e}", match.group())
                    continue
        
        return penalties
    
    def extract_tree_species(self, text: str) -> List[Dict]:
        """Extract tree species using deterministic lookup"""
        species_list = []
        seen_species = set()
        
        # Check against known species patterns
        for species_key, species_info in self.species_patterns.items():
            regex = re.compile(species_info['regex'], re.IGNORECASE | re.UNICODE)
            if regex.search(text):
                if species_key in seen_species:
                    continue
                
                # Get context around match
                match = regex.search(text)
                if match:
                    context = self._get_context(text, match.start(), match.end())
                    
                    # Check for legal status indicators in context
                    status_keywords = {
                        'protected': ['protected', 'prohibited', 'banned', 'ممنوع', 'محفوظ'],
                        'regulated': ['regulated', 'permitted', 'with license', 'اجازت'],
                        'unprotected': ['unprotected', 'common', 'عام']
                    }
                    
                    legal_status = species_info.get('legal_status', 'unknown')
                    for status, keywords in status_keywords.items():
                        if any(keyword in context.lower() for keyword in keywords):
                            legal_status = status
                            break
                    
                    species = {
                        'key': species_key,
                        'common_name': species_info['common_name'],
                        'scientific_name': species_info['scientific_name'],
                        'legal_status': legal_status,
                        'context': context[:300],
                        'confidence': self._calculate_species_confidence(context),
                        'deterministic_match': True
                    }
                    
                    species_list.append(species)
                    seen_species.add(species_key)
                    self.extraction_stats["tree_species"] += 1
        
        # Also look for generic species mentions
        generic_patterns = [
            (r'\b(tree|درخت)\s+(?:species|قسم)\s+(?:named|called|کا\s+نام)\s+["\']?([^"\'.]+?)["\']?', 'named_species'),
            (r'\b(?:oak|poplar|walnut|fir|spruce|willow)\b', 'english_name'),
            (r'\b(شیشم|پاپلر|اخروٹ|دیار)\b', 'urdu_name'),
        ]
        
        for pattern, pattern_type in generic_patterns:
            regex = re.compile(pattern, re.IGNORECASE | re.UNICODE)
            for match in regex.finditer(text):
                species_name = match.group(2) if pattern_type == 'named_species' else match.group()
                if species_name.lower() in seen_species:
                    continue
                
                context = self._get_context(text, match.start(), match.end())
                
                species = {
                    'key': species_name.lower().replace(' ', '_'),
                    'common_name': species_name.title(),
                    'scientific_name': '',
                    'legal_status': 'unknown',
                    'context': context[:300],
                    'confidence': 0.6,
                    'deterministic_match': pattern_type != 'named_species'
                }
                
                species_list.append(species)
                seen_species.add(species_name.lower())
                self.extraction_stats["tree_species"] += 1
        
        return species_list
    
    def extract_officers(self, text: str) -> List[Dict]:
        """Extract officer mentions with deterministic authority hierarchy"""
        officers = []
        seen_officers = set()
        
        for officer_key, officer_info in self.officer_patterns.items():
            regex = re.compile(officer_info['regex'], re.IGNORECASE | re.UNICODE)
            matches = list(regex.finditer(text))
            
            for match in matches:
                officer_title = match.group()
                officer_id = f"{officer_key}_{match.start()}"
                
                if officer_id in seen_officers:
                    continue
                
                context = self._get_context(text, match.start(), match.end())
                
                # Extract powers from context
                powers = self._extract_officer_powers(context)
                
                # Extract location from context
                location = self._extract_location_from_context(context)
                
                officer = {
                    'title': officer_title,
                    'abbreviation': officer_key,
                    'authority_level': officer_info['authority_level'],
                    'reports_to': officer_info['reports_to'],
                    'powers': powers[:3],  # Limit to 3 powers
                    'location': location,
                    'context': context[:300],
                    'confidence': self._calculate_officer_confidence(context),
                    'deterministic': True
                }
                
                officers.append(officer)
                seen_officers.add(officer_id)
                self.extraction_stats["officers"] += 1
        
        return officers
    
    def extract_amendments(self, text: str) -> List[Dict]:
        """Extract amendment markers deterministically"""
        amendments = []
        
        amendment_patterns = [
            (r'\[(\d+)\]\s+(Substituted|Inserted|Omitted|Deleted|Added)\s+by\s+(.+?)(?=\[|\n|$)', 'bracket_marker'),
            (r'Amended\s+by\s+(.+?)(?:\s+Act)?\s+(\d{4})', 'amended_by'),
            (r'Substituted\s+by\s+(.+?)\s+Act', 'substituted_by'),
            (r'متروک\s+ہو\s+گیا\s+بذریعہ\s+(.+?)(?=\s+ایکٹ|\n|$)', 'urdu_repealed'),
        ]
        
        for pattern, pattern_type in amendment_patterns:
            regex = re.compile(pattern, re.IGNORECASE | re.UNICODE)
            for match in regex.finditer(text):
                try:
                    if pattern_type == 'bracket_marker':
                        marker_num = match.group(1)
                        action = match.group(2)
                        amending_law = match.group(3)
                    elif pattern_type == 'amended_by':
                        marker_num = ''
                        action = 'amended'
                        amending_law = match.group(1)
                        year = match.group(2)
                    elif pattern_type == 'substituted_by':
                        marker_num = ''
                        action = 'substituted'
                        amending_law = match.group(1)
                        year = ''
                    elif pattern_type == 'urdu_repealed':
                        marker_num = ''
                        action = 'repealed'
                        amending_law = match.group(1)
                        year = ''
                    else:
                        continue
                    
                    context = self._get_context(text, match.start(), match.end())
                    
                    # Try to extract affected section
                    affected_section = self._extract_affected_section(text, match.start())
                    
                    amendment = {
                        'marker_number': marker_num,
                        'action': action,
                        'amending_law': amending_law,
                        'year': year if 'year' in locals() else '',
                        'affected_section': affected_section,
                        'context': context[:300],
                        'confidence': 0.95,  # Amendments are usually clear
                        'deterministic': True
                    }
                    
                    amendments.append(amendment)
                    self.extraction_stats["amendments"] += 1
                    
                except (IndexError, AttributeError) as e:
                    self._log_abstention(f"Failed to parse amendment: {e}", match.group())
                    continue
        
        return amendments
    
    def extract_jurisdictions(self, text: str) -> List[Dict]:
        """Extract jurisdiction information"""
        jurisdictions = []
        
        jurisdiction_patterns = [
            (r'\b(KPK|Khyber\s+Pakhtunkhwa|صوبہ\s+خیبر\s+پختونخوا)\b', 'provincial'),
            (r'\b(Pakistan|Government of Pakistan|وفاقی\s+حکومت)\b', 'federal'),
            (r'\b(Provincial|صوبائی)\s+Government', 'provincial_gov'),
            (r'\b(Federal|وفاقی)\s+Government', 'federal_gov'),
        ]
        
        for pattern, jurisdiction_type in jurisdiction_patterns:
            regex = re.compile(pattern, re.IGNORECASE | re.UNICODE)
            if regex.search(text):
                # Check if already added
                if any(j.get('type') == jurisdiction_type for j in jurisdictions):
                    continue
                
                jurisdiction = {
                    'type': jurisdiction_type,
                    'name': 'Khyber Pakhtunkhwa' if jurisdiction_type == 'provincial' else 'Pakistan',
                    'confidence': 0.9,
                    'deterministic': True
                }
                
                jurisdictions.append(jurisdiction)
                self.extraction_stats["jurisdictions"] += 1
        
        return jurisdictions
    
    def extract_dates(self, text: str) -> List[Dict]:
        """Extract dates deterministically"""
        dates = []
        
        date_patterns = [
            (r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})', 'english_date'),
            (r'(\d{1,2})\s+(جنوری|فروری|مارچ|اپریل|مئی|جون|جولائی|اگست|ستمبر|اکتوبر|نومبر|دسمبر)\s+(\d{4})', 'urdu_date'),
            (r'(\d{1,2})[-\/](\d{1,2})[-\/](\d{4})', 'numeric_date'),
            (r'سال\s+(\d{4})', 'year_only'),
        ]
        
        month_map = {
            'January': 1, 'February': 2, 'March': 3, 'April': 4, 'May': 5, 'June': 6,
            'July': 7, 'August': 8, 'September': 9, 'October': 10, 'November': 11, 'December': 12,
            'جنوری': 1, 'فروری': 2, 'مارچ': 3, 'اپریل': 4, 'مئی': 5, 'جون': 6,
            'جولائی': 7, 'اگست': 8, 'ستمبر': 9, 'اکتوبر': 10, 'نومبر': 11, 'دسمبر': 12
        }
        
        for pattern, pattern_type in date_patterns:
            regex = re.compile(pattern, re.IGNORECASE | re.UNICODE)
            for match in regex.finditer(text):
                try:
                    if pattern_type == 'english_date':
                        day = int(match.group(1))
                        month_name = match.group(2)
                        year = int(match.group(3))
                        month = month_map.get(month_name.capitalize(), 1)
                    elif pattern_type == 'urdu_date':
                        day = int(match.group(1))
                        month_name = match.group(2)
                        year = int(match.group(3))
                        month = month_map.get(month_name, 1)
                    elif pattern_type == 'numeric_date':
                        day = int(match.group(1))
                        month = int(match.group(2))
                        year = int(match.group(3))
                    elif pattern_type == 'year_only':
                        day = 1
                        month = 1
                        year = int(match.group(1))
                    else:
                        continue
                    
                    # Validate date
                    if 1 <= day <= 31 and 1 <= month <= 12 and 1800 <= year <= 2100:
                        date_str = f"{year:04d}-{month:02d}-{day:02d}"
                        
                        date_info = {
                            'date': date_str,
                            'original_text': match.group(),
                            'type': pattern_type,
                            'confidence': 0.95,
                            'deterministic': True
                        }
                        
                        dates.append(date_info)
                        self.extraction_stats["dates"] += 1
                        
                except (ValueError, IndexError):
                    continue
        
        return dates
    
    def extract_gazette_references(self, text: str) -> List[Dict]:
        """Extract gazette references"""
        gazettes = []
        
        gazette_patterns = [
            (r'Gazette of (?:Pakistan|KPK|Khyber Pakhtunkhwa)[^,]*?(?:No\.?\s*(\d+))?[^,]*?(\d{1,2}\s+\w+\s+\d{4})', 'english_gazette'),
            (r'سرکاری گزٹ[^,]*?(?:نمبر\s*(\d+))?[^,]*?(\d{1,2}\s+\w+\s+\d{4})', 'urdu_gazette'),
        ]
        
        for pattern, pattern_type in gazette_patterns:
            regex = re.compile(pattern, re.IGNORECASE | re.UNICODE)
            for match in regex.finditer(text):
                gazette_number = match.group(1) if match.lastindex >= 1 else ""
                date_info = match.group(2) if match.lastindex >= 2 else ""
                
                gazette = {
                    'reference': match.group(),
                    'gazette_number': gazette_number,
                    'date': date_info,
                    'type': pattern_type,
                    'confidence': 0.9,
                    'deterministic': True
                }
                
                gazettes.append(gazette)
                self.extraction_stats["gazettes"] += 1
        
        return gazettes
    
    def extract_cross_references(self, text: str) -> List[Dict]:
        """Extract cross-references to other sections/laws"""
        cross_refs = []
        
        cross_ref_patterns = [
            (r'see\s+(?:section|S\.|دَفْعَہ)\s+(\d+)', 'see_section'),
            (r'refer\s+to\s+(?:section|S\.)\s+(\d+)', 'refer_to'),
            (r'under\s+(?:section|S\.)\s+(\d+)', 'under_section'),
            (r'مذکورہ\s+دفعہ\s+(\d+)', 'urdu_mentioned'),
            (r'مندرجہ\s+دفعہ\s+(\d+)', 'urdu_listed'),
        ]
        
        for pattern, pattern_type in cross_ref_patterns:
            regex = re.compile(pattern, re.IGNORECASE | re.UNICODE)
            for match in regex.finditer(text):
                referenced_section = match.group(1)
                context = self._get_context(text, match.start(), match.end())
                
                cross_ref = {
                    'type': pattern_type,
                    'referenced_section': referenced_section,
                    'context': context[:200],
                    'confidence': 0.85,
                    'deterministic': True
                }
                
                cross_refs.append(cross_ref)
                self.extraction_stats["cross_references"] += 1
        
        return cross_refs
    
    def extract_relationships(self, entities: Dict, text: str, doc_metadata: Dict = None) -> List[Dict]:
        """Extract deterministic relationships between entities"""
        relationships = []
        # Section Hierarchy (PARENT_OF)
        # We link subsections to their parent sections
        sections = entities.get('legal_sections', [])
        for i, section in enumerate(sections):
            if section.get('subsection'):
                # Try to find parent (same section number but no subsection)
                for other in sections:
                    if other['section_number'] == section['section_number'] and not other['subsection']:
                        relationships.append({
                            'from': f"Section {other['section_number']}",
                            'to': f"Section {section['section_number']}({section['subsection']})",
                            'type': 'PARENT_OF',
                            'confidence': 1.0,
                            'deterministic': True
                        })
                        break
        
        # Officer -> Power relationships
        for officer in entities.get('officers', []):
            for power in officer.get('powers', []):
                relationships.append({
                    'from': officer['abbreviation'],
                    'to': power,
                    'type': 'has_power',
                    'confidence': officer.get('confidence', 0.7),
                    'deterministic': True
                })
        
        # Section -> Amendment relationships
        for section in entities.get('legal_sections', []):
            for amendment in entities.get('amendments', []):
                if amendment.get('affected_section') == section.get('section_number'):
                    relationships.append({
                        'from': f"Section {section['section_number']}",
                        'to': amendment['amending_law'],
                        'type': 'amended_by',
                        'confidence': min(section.get('confidence', 0.8), amendment.get('confidence', 0.9)),
                        'deterministic': True
                    })
        
        # Species -> Penalty relationships
        for species in entities.get('tree_species', []):
            for penalty in entities.get('penalties', []):
                if species['common_name'].lower() in penalty.get('context', '').lower():
                    relationships.append({
                        'from': species['common_name'],
                        'to': f"Rs. {penalty['amount']} fine",
                        'type': 'subject_to_penalty',
                        'confidence': min(species.get('confidence', 0.6), penalty.get('confidence', 0.8)),
                        'deterministic': True
                    })
        
        # Jurisdiction hierarchy relationships
        jurisdictions = entities.get('jurisdictions', [])
        if len(jurisdictions) > 1:
            for i, j1 in enumerate(jurisdictions):
                for j2 in jurisdictions[i+1:]:
                    if j1['type'] == 'federal' and j2['type'] == 'provincial':
                        relationships.append({
                            'from': j1['name'],
                            'to': j2['name'],
                            'type': 'overrides',
                            'confidence': 0.95,
                            'deterministic': True
                        })
        
        return relationships
    
    def resolve_legal_hierarchy(self, entities: Dict, doc_metadata: Dict = None) -> Dict:
        """Resolve legal hierarchy conflicts deterministically"""
        resolution = {
            'applied_hierarchy': self.legal_hierarchy,
            'conflicts_detected': 0,
            'conflicts_resolved': 0,
            'final_authority': 'KPK'  # Default for KPK documents
        }
        
        # Check for jurisdiction conflicts
        jurisdictions = entities.get('jurisdictions', [])
        if len(jurisdictions) > 1:
            resolution['conflicts_detected'] += 1
            
            # Deterministic rule: Federal overrides Provincial
            federal_present = any(j.get('type') == 'federal' for j in jurisdictions)
            provincial_present = any(j.get('type') == 'provincial' for j in jurisdictions)
            
            if federal_present and provincial_present:
                resolution['final_authority'] = 'Federal'
                resolution['conflicts_resolved'] += 1
        
        # Check for amendment conflicts (newer overrides older)
        amendments = entities.get('amendments', [])
        if len(amendments) > 1:
            resolution['conflicts_detected'] += 1
            
            # Get years from amendments
            years = []
            for amendment in amendments:
                if amendment.get('year'):
                    try:
                        years.append(int(amendment['year']))
                    except ValueError:
                        pass
            
            if years:
                resolution['latest_amendment_year'] = max(years)
                resolution['conflicts_resolved'] += 1
        
        return resolution
    
    # ========== HELPER METHODS ==========
    
    def _get_context(self, text: str, start: int, end: int, window: int = 200) -> str:
        """Get context window around match"""
        context_start = max(0, start - window)
        context_end = min(len(text), end + window)
        return text[context_start:context_end].strip()
    
    def _extract_offense_from_context(self, context: str) -> str:
        """Extract offense description from context"""
        offense_keywords = [
            ('cutting', 'illegal cutting'),
            ('felling', 'illegal felling'),
            ('transport', 'illegal transport'),
            ('possession', 'illegal possession'),
            ('burning', 'forest burning'),
            ('encroachment', 'forest encroachment'),
            ('قلم', 'غیر قانونی قلم'),
            ('کاٹنا', 'غیر قانونی کاٹنا'),
        ]
        
        context_lower = context.lower()
        for keyword, offense in offense_keywords:
            if keyword in context_lower:
                return offense
        
        return 'unspecified offense'
    
    def _extract_officer_powers(self, context: str) -> List[str]:
        """Extract officer powers from context"""
        powers = []
        power_verbs = ['issue', 'grant', 'approve', 'seize', 'arrest', 'investigate',
                      'mark', 'auction', 'permit', 'license', 'fine', 'confiscate',
                      'اجازت', 'روک', 'ضبط', 'تفتیش']
        
        sentences = re.split(r'[.!?]+', context)
        for sentence in sentences:
            sentence_lower = sentence.lower()
            for verb in power_verbs:
                if verb in sentence_lower and 'may' in sentence_lower:
                    powers.append(f"Can {verb}")
                    break
        
        return list(set(powers))
    
    def _extract_location_from_context(self, context: str) -> str:
        """Extract location from context"""
        location_patterns = [
            r'Division\s+([A-Z][a-z]+)',
            r'Range\s+([A-Z][a-z]+)',
            r'Beat\s+([A-Z][a-z]+)',
            r'ڈویژن\s+([^\s،]+)',
            r'رینج\s+([^\s،]+)',
            r'بیٹ\s+([^\s،]+)',
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, context, re.IGNORECASE | re.UNICODE)
            if match:
                return match.group()
        
        return ""
    
    def _extract_affected_section(self, text: str, amendment_pos: int) -> str:
        """Extract affected section number near amendment"""
        # Look backward for section reference
        text_before = text[max(0, amendment_pos - 200):amendment_pos]
        
        section_patterns = [
            r'Section\s+(\d+)',
            r'S\.\s*(\d+)',
            r'دَفْعَہ\s*(\d+)'
        ]
        
        for pattern in section_patterns:
            matches = list(re.finditer(pattern, text_before, re.IGNORECASE | re.UNICODE))
            if matches:
                return matches[-1].group(1)
        
        return ""
    
    def _parse_section_number(self, section_num: str) -> Tuple[int, int, int]:
        """Parse section number for sorting (e.g., '5', '5A', '5-2')"""
        try:
            # Extract main number
            main_match = re.match(r'(\d+)', section_num)
            if main_match:
                main_num = int(main_match.group(1))
                
                # Check for letters
                letter_match = re.search(r'(\d+)([A-Z])', section_num)
                if letter_match:
                    letter = ord(letter_match.group(2).upper()) - 64  # A=1, B=2, etc.
                else:
                    letter = 0
                
                # Check for sub-numbers
                sub_match = re.search(r'(\d+)-(\d+)', section_num)
                if sub_match:
                    sub_num = int(sub_match.group(2))
                else:
                    sub_num = 0
                
                return (main_num, letter, sub_num)
        except:
            pass
        
        return (9999, 0, 0)  # Put unparseable sections at end
    
    def _calculate_section_confidence(self, section_num: str, section_text: str) -> float:
        """Calculate confidence for section extraction"""
        confidence = 0.8
        
        # More text = higher confidence
        if len(section_text) > 50:
            confidence += 0.1
        
        # Contains legal keywords = higher confidence
        legal_keywords = ['shall', 'may', 'must', 'prohibited', 'authorized']
        if any(keyword in section_text.lower() for keyword in legal_keywords):
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def _calculate_penalty_confidence(self, match_text: str, context: str) -> float:
        """Calculate confidence for penalty extraction"""
        confidence = 0.85
        
        # Complete sentence = higher confidence
        if match_text.endswith('.') or len(match_text.split()) > 5:
            confidence += 0.1
        
        # Contains offense description = higher confidence
        if any(word in context.lower() for word in ['offense', 'violation', 'offence', 'جرم']):
            confidence += 0.05
        
        return min(confidence, 1.0)
    
    def _calculate_species_confidence(self, context: str) -> float:
        """Calculate confidence for species extraction"""
        confidence = 0.7
        
        # Mentioned with legal terms = higher confidence
        legal_terms = ['protected', 'prohibited', 'permitted', 'ممنوع', 'اجازت']
        if any(term in context.lower() for term in legal_terms):
            confidence += 0.2
        
        # Specific species name = higher confidence
        specific_species = ['deodar', 'chir pine', 'kail', 'دیار', 'چیر', 'کائل']
        if any(species in context.lower() for species in specific_species):
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def _calculate_officer_confidence(self, context: str) -> float:
        """Calculate confidence for officer extraction"""
        confidence = 0.75
        
        # Has powers mentioned = higher confidence
        if 'may' in context.lower() or 'shall' in context.lower():
            confidence += 0.15
        
        # Has location mentioned = higher confidence
        location_words = ['division', 'range', 'beat', 'ڈویژن', 'رینج']
        if any(word in context.lower() for word in location_words):
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def _calculate_confidence_metrics(self, entities: Dict) -> Dict:
        """Calculate overall confidence metrics"""
        metrics = {
            'average_confidence': 0.0,
            'deterministic_percentage': 0.0,
            'entity_counts': {},
            'low_confidence_entities': []
        }
        
        total_confidence = 0
        total_entities = 0
        deterministic_entities = 0
        
        # Calculate for each entity type
        for entity_type, entity_list in entities.items():
            if isinstance(entity_list, list) and entity_list:
                entity_count = len(entity_list)
                metrics['entity_counts'][entity_type] = entity_count
                
                for entity in entity_list:
                    confidence = entity.get('confidence', 0.5)
                    total_confidence += confidence
                    total_entities += 1
                    
                    if entity.get('deterministic', False):
                        deterministic_entities += 1
                    
                    if confidence < 0.6:
                        metrics['low_confidence_entities'].append({
                            'type': entity_type,
                            'value': entity.get('common_name') or entity.get('title') or str(entity),
                            'confidence': confidence
                        })
        
        if total_entities > 0:
            metrics['average_confidence'] = total_confidence / total_entities
            metrics['deterministic_percentage'] = (deterministic_entities / total_entities) * 100
        
        return metrics
    
    def _generate_extraction_metadata(self, text: str, doc_metadata: Dict = None) -> Dict:
        """Generate metadata about the extraction process"""
        metadata = {
            'extraction_timestamp': datetime.now().isoformat(),
            'text_length': len(text),
            'rules_applied': len(self.rules),
            'kpk_config_loaded': KPK_CONFIG_LOADED,
            'abstention_count': len(self.abstention_log),
            'deterministic_extraction': True
        }
        
        if doc_metadata:
            metadata.update({
                'document_type': doc_metadata.get('document_type', 'unknown'),
                'source': doc_metadata.get('source', 'unknown'),
                'jurisdiction': doc_metadata.get('jurisdiction', 'KPK')
            })
        
        return metadata
    
    def _log_extraction_summary(self, entities: Dict):
        """Log extraction summary"""
        total_entities = sum(len(entities.get(key, [])) for key in 
                           ['legal_sections', 'penalties', 'tree_species', 'officers', 'amendments'])
        
        logger.info(f"Extraction complete: {total_entities} entities found")
        for entity_type in ['legal_sections', 'penalties', 'tree_species', 'officers', 'amendments']:
            count = len(entities.get(entity_type, []))
            if count > 0:
                logger.info(f"  {entity_type.replace('_', ' ').title()}: {count}")
        
        if self.abstention_log:
            logger.info(f"  Abstentions: {len(self.abstention_log)}")
    
    def _log_abstention(self, reason: str, context: str):
        """Log an abstention decision"""
        abstention = {
            'timestamp': datetime.now().isoformat(),
            'reason': reason,
            'context': context[:100],
            'component': 'rule_extractor'
        }
        self.abstention_log.append(abstention)
    
    def _create_error_response(self, error: Exception, text: str) -> Dict:
        """Create error response when extraction fails"""
        return {
            'error': str(error),
            'entities': {},
            'extraction_metadata': {
                'extraction_timestamp': datetime.now().isoformat(),
                'text_length': len(text),
                'success': False,
                'error_type': type(error).__name__
            },
            'abstention_decisions': len(self.abstention_log),
            'confidence_metrics': {
                'average_confidence': 0.0,
                'deterministic_percentage': 0.0,
                'entity_counts': {}
            }
        }


# ========== INTEGRATION METHODS ==========

    @classmethod
    def process_normalized_document(cls, normalized_data: Dict, rule_config_path: str = None) -> Dict:
        """
        Process normalized document through rule extraction.
        
        Args:
            normalized_data: Dictionary from phase 2/3 normalization
            rule_config_path: Optional path to rule configuration
            
        Returns:
            Dictionary with extracted entities
        """
        try:
            text = normalized_data.get('normalized_text', '')
            metadata = normalized_data.get('metadata', {})
            
            extractor = cls(rule_config_path)
            entities = extractor.extract_all_entities(text, metadata)
            
            # Add to original data
            normalized_data['rule_extracted_entities'] = entities
            normalized_data['extraction_timestamp'] = datetime.now().isoformat()
            
            return normalized_data
            
        except Exception as e:
            logger.error(f"Error in rule extraction: {e}")
            return {
                'error': str(e),
                'normalized_data': normalized_data,
                'rule_extracted_entities': {}
            }


# ========== COMMAND LINE INTERFACE ==========

def main():
    """Command line interface for rule extraction"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Deterministic rule extraction for KPK forestry documents")
    parser.add_argument("--input", "-i", required=True, help="Input JSON file from normalization phase")
    parser.add_argument("--output", "-o", help="Output JSON file")
    parser.add_argument("--rules", "-r", help="Path to rule configuration YAML")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Load normalized data
        with open(args.input, 'r', encoding='utf-8') as f:
            normalized_data = json.load(f)
        
        # Apply rule extraction
        extractor = KPKRuleExtractor(args.rules)
        result = extractor.process_normalized_document(normalized_data, args.rules)
        
        # Print summary
        entities = result.get('rule_extracted_entities', {})
        print("\n" + "=" * 60)
        print("RULE-BASED EXTRACTION RESULTS")
        print("=" * 60)
        
        for entity_type in ['legal_sections', 'penalties', 'tree_species', 'officers', 'amendments']:
            count = len(entities.get(entity_type, []))
            if count > 0:
                print(f"{entity_type.replace('_', ' ').title()}: {count}")
        
        metrics = entities.get('confidence_metrics', {})
        if metrics:
            print(f"\nAverage Confidence: {metrics.get('average_confidence', 0):.2%}")
            print(f"Deterministic: {metrics.get('deterministic_percentage', 0):.1f}%")
        
        abstentions = entities.get('abstention_decisions', 0)
        if abstentions > 0:
            print(f"Abstentions (I don't know): {abstentions}")
        
        print(f"\nTotal Rules Applied: {entities.get('deterministic_rules_applied', 0)}")
        
        # Save if output specified
        if args.output:
            os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else '.', exist_ok=True)
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"\nResults saved to: {args.output}")
        
        # Show sample deterministic extractions
        if args.verbose:
            print("\n" + "=" * 60)
            print("SAMPLE EXTRACTIONS (Deterministic)")
            print("=" * 60)
            
            for entity_type in ['legal_sections', 'penalties']:
                items = entities.get(entity_type, [])
                if items:
                    print(f"\n{entity_type.replace('_', ' ').title()} (first 2):")
                    for i, item in enumerate(items[:2]):
                        if entity_type == 'legal_sections':
                            print(f"  {i+1}. Section {item.get('section_number')} - Confidence: {item.get('confidence', 0):.0%}")
                            print(f"     Text: {item.get('text', '')[:80]}...")
                        elif entity_type == 'penalties':
                            print(f"  {i+1}. Rs. {item.get('amount')} - {item.get('offense', 'Unknown')}")
                            print(f"     Confidence: {item.get('confidence', 0):.0%}")
        
        print("\n" + "=" * 60)
        print("Extraction complete. Remember: 'Rules Decide' ✓")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


if __name__ == "__main__":
    main()
