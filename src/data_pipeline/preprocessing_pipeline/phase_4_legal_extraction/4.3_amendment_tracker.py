"""
AMENDMENT TRACKER - Phase 4.3 of KPK Legal Extraction
Deterministic tracking of legal amendments and version chains.
OPERATING PRINCIPLE: "Rules track changes, deterministically."
"""

import re
import json
import logging
import hashlib
from typing import Dict, List, Any, Tuple, Optional, Set
from dataclasses import dataclass, asdict, field
from collections import defaultdict, OrderedDict
from datetime import datetime, date
from enum import Enum
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from config.kpk_forestry_config import (
        KPK_LEGAL_HIERARCHY, KPK_GAZETTE_PATTERNS,
        KPK_AMENDMENT_KEYWORDS
    )
    KPK_CONFIG_LOADED = True
except ImportError:
    KPK_CONFIG_LOADED = False
    print("WARNING: KPK Configuration not found. Using default patterns.")

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class AmendmentAction(Enum):
    """Deterministic amendment actions"""
    SUBSTITUTED = "substituted"
    INSERTED = "inserted"
    OMITTED = "omitted"
    DELETED = "deleted"
    ADDED = "added"
    AMENDED = "amended"
    REPEALED = "repealed"


class AuthorityLevel(Enum):
    """Deterministic authority hierarchy"""
    CONSTITUTION = 1
    FEDERAL_ACT = 2
    PROVINCIAL_ORDINANCE = 3
    HAZARA_ACT = 4  # KPK-specific
    GAZETTE_NOTIFICATION = 5
    SRO = 6  # Statutory Regulatory Order
    DEPARTMENT_CIRCULAR = 7
    OFFICER_ORDER = 8


@dataclass
class AmendmentRecord:
    """Deterministic amendment record"""
    action: AmendmentAction
    section_number: str
    amending_law: str
    amending_year: str
    marker_number: str = ""
    effective_date: str = ""
    gazette_reference: str = ""
    confidence: float = 1.0
    validation_rules: List[str] = field(default_factory=list)
    is_conflicting: bool = False
    
    def __post_init__(self):
        # Generate deterministic ID
        content_hash = hashlib.md5(
            f"{self.action.value}:{self.section_number}:{self.amending_law}".encode()
        ).hexdigest()[:8]
        self.amendment_id = f"amend_{content_hash}"


@dataclass
class SectionVersion:
    """Complete version history of a section"""
    section_number: str
    versions: List[Dict]  # Ordered from oldest to newest
    current_version: Dict = None
    is_repealed: bool = False
    repeal_date: str = ""
    repeal_authority: str = ""
    
    def add_version(self, version_data: Dict):
        """Add new version deterministically"""
        self.versions.append(version_data)
        
        # Update current version if not repealed
        if version_data.get('action') not in ['repealed', 'omitted', 'deleted']:
            self.current_version = version_data
            self.is_repealed = False
        else:
            self.is_repealed = True
            self.repeal_date = version_data.get('effective_date', '')
            self.repeal_authority = version_data.get('amending_law', '')


@dataclass
class TemporalQueryResult:
    """Result of temporal query"""
    section_number: str
    query_date: str
    active_version: Optional[Dict]
    active_action: str
    version_chain: List[Dict]
    authority_level: int
    is_current: bool
    confidence: float


class KPAmendmentTracker:
    """Enhanced amendment tracker for KPK legal documents."""
    
    def __init__(self, config: Optional[Any] = None):
        self.config = config if config is not None else {}
        self.jurisdiction = self.config.get("jurisdiction", "KPK")
        self.amendment_records = []
        self.section_versions = {}
        self.version_chains = {}
        self.abstention_log = []
        
        # Initialize deterministic patterns
        self.initialize_amendment_patterns()
        self.initialize_gazette_patterns()
        self.initialize_date_patterns()
        
        # Statistics
        self.stats = {
            "amendments_found": 0,
            "version_chains_built": 0,
            "temporal_queries": 0,
            "conflicts_detected": 0,
            "abstention_decisions": 0
        }
        
        logger.info(f"Amendment Tracker initialized for jurisdiction: {self.jurisdiction}")
    
    def initialize_amendment_patterns(self):
        """Initialize deterministic amendment patterns"""
        
        # Primary amendment patterns (bracket notation)
        self.amendment_patterns = [
            # [1] Substituted by XYZ Act 2005
            (r'\[(\d+)\]\s+(Substituted|Inserted|Omitted|Deleted|Added)\s+by\s+(.+?)(?=\n|\[|$)',
             lambda m: (m.group(1), m.group(2).lower(), m.group(3))),
            
            # Substituted by XYZ Act 2005 [1]
            (r'(Substituted|Inserted|Omitted|Deleted|Added)\s+by\s+(.+?)\s*\[(\d+)\]',
             lambda m: (m.group(3), m.group(1).lower(), m.group(2))),
            
            # Amendment by XYZ Act 2005
            (r'Amended\s+by\s+(.+?)(?:\s+Act)?\s+(\d{4})',
             lambda m: ("", "amended", f"{m.group(1)} {m.group(2)}")),
            
            # Urdu amendment patterns
            (r'\[(\d+)\]\s+(متبادل|شامل|حذف|خارج|اضافہ)\s+بذریعہ\s+(.+?)(?=\n|\[|$)',
             lambda m: (m.group(1), self._translate_urdu_action(m.group(2)), m.group(3))),
            
            # Repealed patterns
            (r'Repealed\s+by\s+(.+?)\s+(\d{4})',
             lambda m: ("", "repealed", f"{m.group(1)} {m.group(2)}")),
            (r'منسوخ\s+بذریعہ\s+(.+?)\s+(\d{4})',
             lambda m: ("", "repealed", f"{m.group(1)} {m.group(2)}")),
        ]
        
        # Section reference patterns for context
        self.section_patterns = [
            r'Section\s+(\d+[A-Z]?(?:-\d+)?(?:\(\d+\))?)',
            r'S\.\s*(\d+)',
            r'دَفْعَہ\s*(\d+)',
            r'مادہ\s*(\d+)',
        ]
    
    def initialize_gazette_patterns(self):
        """Initialize gazette reference patterns"""
        self.gazette_patterns = [
            r'Gazette of (?:Pakistan|KPK|Khyber Pakhtunkhwa)[^,]*?(?:No\.?\s*(\d+))?[^,]*?(\d{1,2}\s+\w+\s+\d{4})',
            r'سرکاری گزٹ[^,]*?(?:نمبر\s*(\d+))?[^,]*?(\d{1,2}\s+\w+\s+\d{4})',
            r'S\.R\.O\.\s*No\.?\s*(\d+/\d+)',
            r'ایس\s*آر\s*او\s*نمبر\s*(\d+/\d+)',
        ]
    
    def initialize_date_patterns(self):
        """Initialize date extraction patterns"""
        self.date_patterns = [
            r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})',
            r'(\d{1,2})\s+(جنوری|فروری|مارچ|اپریل|مئی|جون|جولائی|اگست|ستمبر|اکتوبر|نومبر|دسمبر)\s+(\d{4})',
            r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})',
            r'سال\s+(\d{4})',
        ]
        
        self.month_map = {
            'January': 1, 'February': 2, 'March': 3, 'April': 4, 'May': 5, 'June': 6,
            'July': 7, 'August': 8, 'September': 9, 'October': 10, 'November': 11, 'December': 12,
            'جنوری': 1, 'فروری': 2, 'مارچ': 3, 'اپریل': 4, 'مئی': 5, 'جون': 6,
            'جولائی': 7, 'اگست': 8, 'ستمبر': 9, 'اکتوبر': 10, 'نومبر': 11, 'دسمبر': 12
        }
    
    def _translate_urdu_action(self, urdu_action: str) -> str:
        """Translate Urdu action to English deterministically"""
        translation_map = {
            'متبادل': 'substituted',
            'شامل': 'inserted',
            'حذف': 'omitted',
            'خارج': 'deleted',
            'اضافہ': 'added',
            'منسوخ': 'repealed'
        }
        return translation_map.get(urdu_action, 'amended')
    
    def extract_amendments(self, text: str, base_law_info: Dict = None) -> Dict[str, Any]:
        """
        Extract amendments from text deterministically.
        
        Args:
            text: Text to analyze
            base_law_info: Information about the base law being amended
            
        Returns:
            Dictionary with extracted amendments and metadata
        """
        logger.info("Extracting amendments deterministically...")
        
        amendments = []
        section_amendments = defaultdict(list)
        gazette_references = []
        
        # Extract using deterministic patterns
        for pattern, extractor in self.amendment_patterns:
            regex = re.compile(pattern, re.IGNORECASE | re.UNICODE)
            for match in regex.finditer(text):
                try:
                    marker_num, action_str, amending_law = extractor(match)
                    
                    # Extract year from amending law
                    year_match = re.search(r'\b(19\d{2}|20\d{2})\b', amending_law)
                    amending_year = year_match.group(1) if year_match else ""
                    
                    # Extract affected section from context
                    section_num = self._extract_affected_section(text, match.start())
                    
                    # Extract gazette reference if present
                    gazette_ref = self._extract_gazette_reference(match.group())
                    
                    # Extract effective date
                    effective_date = self._extract_effective_date(text, match.start())
                    
                    # Create amendment record
                    amendment = AmendmentRecord(
                        action=AmendmentAction(action_str),
                        section_number=section_num,
                        amending_law=amending_law.strip(),
                        amending_year=amending_year,
                        marker_number=marker_num,
                        effective_date=effective_date,
                        gazette_reference=gazette_ref,
                        confidence=self._calculate_amendment_confidence(match.group(), section_num)
                    )
                    
                    amendments.append(asdict(amendment))
                    section_amendments[section_num].append(asdict(amendment))
                    self.stats["amendments_found"] += 1
                    
                    logger.debug(f"Found amendment: {action_str} for section {section_num} "
                               f"by {amending_law}")
                    
                except Exception as e:
                    self._log_abstention(f"Failed to parse amendment: {e}", match.group())
                    continue
        
        # Extract gazette references separately
        gazette_references = self._extract_all_gazette_references(text)
        
        # Build preliminary version chains
        version_chains = self._build_preliminary_chains(section_amendments, base_law_info)
        
        # Detect conflicts
        conflicts = self._detect_amendment_conflicts(section_amendments)
        
        return {
            "amendments": amendments,
            "section_amendments": dict(section_amendments),
            "gazette_references": gazette_references,
            "version_chains": version_chains,
            "conflicts_detected": conflicts,
            "statistics": self.stats.copy(),
            "metadata": {
                "extraction_timestamp": datetime.now().isoformat(),
                "base_law": base_law_info,
                "jurisdiction": self.jurisdiction,
                "deterministic_extraction": True
            }
        }
    
    def _extract_affected_section(self, text: str, amendment_pos: int) -> str:
        """Extract affected section number near amendment"""
        # Look backward for section reference
        context_before = text[max(0, amendment_pos - 300):amendment_pos]
        
        for pattern in self.section_patterns:
            matches = list(re.finditer(pattern, context_before, re.IGNORECASE | re.UNICODE))
            if matches:
                # Take the closest match
                return matches[-1].group(1)
        
        # Look forward if not found
        context_after = text[amendment_pos:amendment_pos + 300]
        for pattern in self.section_patterns:
            match = re.search(pattern, context_after, re.IGNORECASE | re.UNICODE)
            if match:
                return match.group(1)
        
        return "unknown"
    
    def _extract_gazette_reference(self, text: str) -> str:
        """Extract gazette reference from text"""
        for pattern in self.gazette_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.UNICODE)
            if match:
                return match.group()
        return ""
    
    def _extract_effective_date(self, text: str, amendment_pos: int) -> str:
        """Extract effective date near amendment"""
        context_window = text[max(0, amendment_pos - 200):amendment_pos + 200]
        
        for pattern in self.date_patterns:
            match = re.search(pattern, context_window, re.IGNORECASE | re.UNICODE)
            if match:
                try:
                    if len(match.groups()) == 3:
                        # Full date
                        if match.group(2) in self.month_map:
                            day = int(match.group(1))
                            month = self.month_map[match.group(2)]
                            year = int(match.group(3))
                            return f"{year:04d}-{month:02d}-{day:02d}"
                        else:
                            # Numeric date
                            year = int(match.group(1))
                            month = int(match.group(2))
                            day = int(match.group(3))
                            return f"{year:04d}-{month:02d}-{day:02d}"
                    elif len(match.groups()) == 1:
                        # Year only
                        year = int(match.group(1))
                        return f"{year:04d}-01-01"
                except (ValueError, IndexError):
                    continue
        
        return ""
    
    def _extract_all_gazette_references(self, text: str) -> List[Dict]:
        """Extract all gazette references from text"""
        references = []
        
        for pattern in self.gazette_patterns:
            regex = re.compile(pattern, re.IGNORECASE | re.UNICODE)
            for match in regex.finditer(text):
                ref = {
                    "reference": match.group(),
                    "type": "gazette",
                    "position": match.start(),
                    "confidence": 0.9
                }
                
                # Try to extract date
                date_match = re.search(r'(\d{1,2}\s+\w+\s+\d{4})', match.group())
                if date_match:
                    ref["date"] = date_match.group(1)
                
                # Try to extract number
                num_match = re.search(r'No\.?\s*(\d+/\d+|\d+)', match.group())
                if num_match:
                    ref["number"] = num_match.group(1)
                
                references.append(ref)
        
        # Deduplicate
        seen = set()
        deduplicated = []
        for ref in references:
            key = ref["reference"]
            if key not in seen:
                deduplicated.append(ref)
                seen.add(key)
        
        return deduplicated
    
    def _calculate_amendment_confidence(self, match_text: str, section_num: str) -> float:
        """Calculate confidence for amendment extraction"""
        confidence = 0.8
        
        # Has marker number increases confidence
        if '[' in match_text and ']' in match_text:
            confidence += 0.1
        
        # Has year increases confidence
        if re.search(r'\b(19\d{2}|20\d{2})\b', match_text):
            confidence += 0.1
        
        # Specific section mentioned increases confidence
        if section_num != "unknown":
            confidence += 0.1
        
        # Gazette reference increases confidence
        if any(pattern in match_text.lower() for pattern in ['gazette', 'گزٹ', 's.r.o', 'ایس آر او']):
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def _build_preliminary_chains(self, section_amendments: Dict, base_law_info: Dict) -> Dict:
        """Build preliminary version chains"""
        chains = {}
        
        for section_num, amendments in section_amendments.items():
            if not amendments:
                continue
            
            # Sort amendments by year deterministically
            sorted_amendments = sorted(
                amendments,
                key=lambda x: (
                    x.get('amending_year', '0000'),
                    x.get('effective_date', '0000-00-00')
                )
            )
            
            # Create version chain
            chain = []
            
            # Add original version
            chain.append({
                "version": "1.0",
                "action": "original",
                "year": base_law_info.get('year', '') if base_law_info else "",
                "law": base_law_info.get('title', '') if base_law_info else "",
                "effective_date": base_law_info.get('effective_date', '') if base_law_info else "",
                "is_current": False
            })
            
            # Add amendment versions
            for i, amendment in enumerate(sorted_amendments, start=2):
                chain.append({
                    "version": f"{i}.0",
                    "action": amendment['action'],
                    "amending_law": amendment['amending_law'],
                    "amending_year": amendment['amending_year'],
                    "effective_date": amendment['effective_date'],
                    "gazette_reference": amendment['gazette_reference'],
                    "is_current": False,
                    "confidence": amendment['confidence']
                })
            
            # Mark current version (last non-repealed/omitted)
            for i in range(len(chain) - 1, -1, -1):
                if chain[i]['action'] not in ['repealed', 'omitted', 'deleted']:
                    chain[i]['is_current'] = True
                    break
            
            chains[section_num] = chain
        
        self.stats["version_chains_built"] = len(chains)
        return chains
    
    def _detect_amendment_conflicts(self, section_amendments: Dict) -> List[Dict]:
        """Detect conflicts between amendments"""
        conflicts = []
        
        for section_num, amendments in section_amendments.items():
            if len(amendments) < 2:
                continue
            
            # Check for multiple amendments in same year by different laws
            amendments_by_year = defaultdict(list)
            for amendment in amendments:
                year = amendment.get('amending_year', '')
                if year:
                    amendments_by_year[year].append(amendment)
            
            for year, year_amendments in amendments_by_year.items():
                if len(year_amendments) > 1:
                    # Check if different laws
                    laws = set(a['amending_law'] for a in year_amendments)
                    if len(laws) > 1:
                        conflict = {
                            "section": section_num,
                            "year": year,
                            "conflict_type": "multiple_amendments_same_year",
                            "amending_laws": list(laws),
                            "severity": "high"
                        }
                        conflicts.append(conflict)
                        self.stats["conflicts_detected"] += 1
            
            # Check for logical conflicts
            actions = [a['action'] for a in amendments]
            if 'repealed' in actions and len(actions) > actions.index('repealed') + 1:
                # Amendments after repeal
                conflict = {
                    "section": section_num,
                    "conflict_type": "amendments_after_repeal",
                    "description": "Amendments found after section was repealed",
                    "severity": "high"
                }
                conflicts.append(conflict)
                self.stats["conflicts_detected"] += 1
        
        return conflicts
    
    def build_complete_version_chains(self, 
                                     extracted_data: Dict,
                                     base_law_info: Dict) -> Dict[str, Any]:
        """
        Build complete version chains from extracted data.
        
        Args:
            extracted_data: Dictionary from extract_amendments()
            base_law_info: Information about the base law
            
        Returns:
            Complete version chains with temporal analysis
        """
        logger.info("Building complete version chains...")
        
        section_amendments = extracted_data.get('section_amendments', {})
        chains = extracted_data.get('version_chains', {})
        
        # Enhance chains with temporal analysis
        enhanced_chains = {}
        temporal_validity = {}
        
        for section_num, chain in chains.items():
            if not chain:
                continue
            
            enhanced_chain = self._enhance_chain_with_temporal(chain, base_law_info)
            enhanced_chains[section_num] = enhanced_chain
            
            # Determine current validity
            validity = self._determine_section_validity(enhanced_chain)
            temporal_validity[section_num] = validity
        
        # Build authority hierarchy
        authority_hierarchy = self._build_authority_hierarchy(extracted_data, base_law_info)
        
        return {
            "version_chains": enhanced_chains,
            "temporal_validity": temporal_validity,
            "authority_hierarchy": authority_hierarchy,
            "amendment_summary": self._create_amendment_summary(extracted_data),
            "conflict_resolution": self._resolve_conflicts(extracted_data.get('conflicts_detected', [])),
            "metadata": {
                "generation_timestamp": datetime.now().isoformat(),
                "base_law": base_law_info,
                "jurisdiction": self.jurisdiction,
                "deterministic": True
            }
        }
    
    def _enhance_chain_with_temporal(self, chain: List[Dict], base_law_info: Dict) -> List[Dict]:
        """Enhance version chain with temporal information"""
        enhanced = []
        
        for i, version in enumerate(chain):
            enhanced_version = version.copy()
            
            # Add temporal information
            enhanced_version['temporal_index'] = i
            enhanced_version['is_earliest'] = (i == 0)
            enhanced_version['is_latest'] = (i == len(chain) - 1)
            
            # Calculate version duration if possible
            if i > 0 and enhanced_version.get('effective_date') and chain[i-1].get('effective_date'):
                try:
                    start_date = datetime.strptime(chain[i-1]['effective_date'], '%Y-%m-%d')
                    end_date = datetime.strptime(enhanced_version['effective_date'], '%Y-%m-%d')
                    days_active = (end_date - start_date).days
                    enhanced_version['days_since_previous'] = days_active
                except (ValueError, KeyError):
                    pass
            
            # Add authority level
            enhanced_version['authority_level'] = self._determine_authority_level(
                enhanced_version.get('amending_law', ''),
                base_law_info
            )
            
            enhanced.append(enhanced_version)
        
        return enhanced
    
    def _determine_authority_level(self, law_reference: str, base_law_info: Dict) -> int:
        """Determine authority level of a law reference"""
        law_lower = law_reference.lower()
        
        # Check for federal acts
        if any(keyword in law_lower for keyword in ['federal', 'act of parliament', 'پارلیمنٹ']):
            return AuthorityLevel.FEDERAL_ACT.value
        
        # Check for provincial ordinances
        if any(keyword in law_lower for keyword in ['ordinance', 'آرڈیننس', 'kpk', 'khyber', 'خیبر']):
            return AuthorityLevel.PROVINCIAL_ORDINANCE.value
        
        # Check for Hazara Act (KPK-specific)
        if 'hazara' in law_lower or 'ہزارہ' in law_lower:
            return AuthorityLevel.HAZARA_ACT.value
        
        # Check for SROs
        if any(keyword in law_lower for keyword in ['s.r.o', 'sro', 'ایس آر او']):
            return AuthorityLevel.SRO.value
        
        # Check for gazette notifications
        if any(keyword in law_lower for keyword in ['gazette', 'گزٹ', 'notification', 'نوٹیفیکیشن']):
            return AuthorityLevel.GAZETTE_NOTIFICATION.value
        
        # Check for circulars
        if any(keyword in law_lower for keyword in ['circular', 'سرکلر']):
            return AuthorityLevel.DEPARTMENT_CIRCULAR.value
        
        return AuthorityLevel.OFFICER_ORDER.value
    
    def _determine_section_validity(self, chain: List[Dict]) -> Dict:
        """Determine current validity of a section"""
        if not chain:
            return {"status": "unknown", "reason": "No version chain"}
        
        # Find current version
        current_versions = [v for v in chain if v.get('is_current')]
        if not current_versions:
            # All versions repealed/omitted
            return {
                "status": "invalid",
                "reason": "All versions repealed or omitted",
                "last_valid_version": chain[-1] if chain else None
            }
        
        current = current_versions[0]
        
        # Check if expired (simplified logic)
        current_date = datetime.now().date()
        effective_date = current.get('effective_date')
        
        is_expired = False
        if effective_date:
            try:
                eff_date = datetime.strptime(effective_date, '%Y-%m-%d').date()
                # Simple check: if effective date > 10 years ago, might need renewal
                if (current_date - eff_date).days > 3650:  # 10 years
                    is_expired = True
            except ValueError:
                pass
        
        return {
            "status": "valid" if not is_expired else "needs_review",
            "current_version": current['version'],
            "effective_since": effective_date,
            "authority_level": current.get('authority_level'),
            "expiry_warning": is_expired,
            "confidence": current.get('confidence', 0.8)
        }
    
    def _build_authority_hierarchy(self, extracted_data: Dict, base_law_info: Dict) -> Dict:
        """Build authority hierarchy from amendments"""
        hierarchy = {
            "base_law": {
                "title": base_law_info.get('title', ''),
                "authority": self._determine_authority_level(
                    base_law_info.get('title', ''), 
                    base_law_info
                ),
                "year": base_law_info.get('year', '')
            },
            "amending_instruments": []
        }
        
        amendments = extracted_data.get('amendments', [])
        for amendment in amendments:
            instrument = {
                "law": amendment['amending_law'],
                "year": amendment['amending_year'],
                "authority": self._determine_authority_level(
                    amendment['amending_law'],
                    base_law_info
                ),
                "gazette_reference": amendment['gazette_reference'],
                "sections_amended": []
            }
            
            # Find which sections this instrument amended
            section_amendments = extracted_data.get('section_amendments', {})
            for section_num, section_amends in section_amendments.items():
                if any(a['amendment_id'] == amendment.get('amendment_id', '') for a in section_amends):
                    instrument["sections_amended"].append(section_num)
            
            hierarchy["amending_instruments"].append(instrument)
        
        # Sort by authority level
        hierarchy["amending_instruments"].sort(key=lambda x: x['authority'])
        
        return hierarchy
    
    def _create_amendment_summary(self, extracted_data: Dict) -> Dict:
        """Create summary of amendments"""
        amendments = extracted_data.get('amendments', [])
        section_amendments = extracted_data.get('section_amendments', {})
        
        # Count by action type
        action_counts = defaultdict(int)
        for amendment in amendments:
            action_counts[amendment['action']] += 1
        
        # Count by year
        year_counts = defaultdict(int)
        for amendment in amendments:
            if amendment['amending_year']:
                year_counts[amendment['amending_year']] += 1
        
        return {
            "total_amendments": len(amendments),
            "sections_affected": len(section_amendments),
            "action_distribution": dict(action_counts),
            "year_distribution": dict(year_counts),
            "gazette_references": len(extracted_data.get('gazette_references', [])),
            "conflicts": len(extracted_data.get('conflicts_detected', [])),
            "deterministic_confidence": self._calculate_overall_confidence(extracted_data)
        }
    
    def _resolve_conflicts(self, conflicts: List[Dict]) -> List[Dict]:
        """Resolve amendment conflicts deterministically"""
        resolved = []
        
        for conflict in conflicts:
            resolution = {
                "conflict": conflict,
                "resolution_method": "deterministic_rule",
                "resolved_at": datetime.now().isoformat()
            }
            
            if conflict['conflict_type'] == "multiple_amendments_same_year":
                # Rule: Take the one with highest authority
                resolution["resolution"] = "select_highest_authority"
                resolution["confidence"] = 0.8
            
            elif conflict['conflict_type'] == "amendments_after_repeal":
                # Rule: Amendments after repeal are invalid
                resolution["resolution"] = "ignore_post_repeal_amendments"
                resolution["confidence"] = 0.9
            
            else:
                resolution["resolution"] = "require_human_review"
                resolution["confidence"] = 0.5
            
            resolved.append(resolution)
        
        return resolved
    
    def _calculate_overall_confidence(self, extracted_data: Dict) -> float:
        """Calculate overall confidence for amendment extraction"""
        amendments = extracted_data.get('amendments', [])
        if not amendments:
            return 0.0
        
        # Average confidence of amendments
        total_confidence = sum(a.get('confidence', 0) for a in amendments)
        avg_confidence = total_confidence / len(amendments)
        
        # Penalize for conflicts
        conflicts = len(extracted_data.get('conflicts_detected', []))
        conflict_penalty = min(conflicts * 0.05, 0.2)
        
        # Penalize for unknown sections
        unknown_sections = sum(1 for a in amendments if a.get('section_number') == 'unknown')
        unknown_penalty = min(unknown_sections * 0.02, 0.1)
        
        final_confidence = avg_confidence - conflict_penalty - unknown_penalty
        return max(0.0, min(final_confidence, 1.0))
    
    def temporal_query(self, 
                      section_num: str, 
                      query_date: str,
                      version_chains: Dict) -> TemporalQueryResult:
        """
        Query which version was active at a specific date.
        
        Args:
            section_num: Section number
            query_date: Date in YYYY-MM-DD format
            version_chains: Version chains from build_complete_version_chains()
            
        Returns:
            Temporal query result
        """
        self.stats["temporal_queries"] += 1
        
        if section_num not in version_chains:
            # Log abstention
            self._log_abstention(
                "section_not_found",
                f"Section {section_num} not found in version chains",
                {"query_date": query_date}
            )
            
            return TemporalQueryResult(
                section_number=section_num,
                query_date=query_date,
                active_version=None,
                active_action="unknown",
                version_chain=[],
                authority_level=0,
                is_current=False,
                confidence=0.0
            )
        
        chain = version_chains[section_num]
        
        # Parse query date
        try:
            query_dt = datetime.strptime(query_date, '%Y-%m-%d').date()
        except ValueError:
            self._log_abstention(
                "invalid_date_format",
                f"Invalid date format: {query_date}",
                {"section": section_num}
            )
            query_dt = None
        
        # Find active version at query date
        active_version = None
        for version in chain:
            if version.get('effective_date'):
                try:
                    version_dt = datetime.strptime(version['effective_date'], '%Y-%m-%d').date()
                    if query_dt and version_dt <= query_dt:
                        active_version = version
                except ValueError:
                    continue
        
        if not active_version and chain:
            active_version = chain[0]  # Use earliest version
        
        # Prepare result
        if active_version:
            result = TemporalQueryResult(
                section_number=section_num,
                query_date=query_date,
                active_version=active_version,
                active_action=active_version.get('action', 'unknown'),
                version_chain=chain,
                authority_level=active_version.get('authority_level', 0),
                is_current=active_version.get('is_current', False),
                confidence=active_version.get('confidence', 0.8)
            )
        else:
            result = TemporalQueryResult(
                section_number=section_num,
                query_date=query_date,
                active_version=None,
                active_action="unknown",
                version_chain=chain,
                authority_level=0,
                is_current=False,
                confidence=0.0
            )
        
        return result
    
    def _log_abstention(self, abstention_type: str, reason: str, context: Dict = None):
        """Log abstention decision"""
        abstention = {
            "timestamp": datetime.now().isoformat(),
            "type": abstention_type,
            "reason": reason,
            "context": context or {},
            "component": "amendment_tracker"
        }
        self.abstention_log.append(abstention)
        self.stats["abstention_decisions"] += 1


# ========== INTEGRATION WITH PIPELINE ==========

class AmendmentProcessor:
    """
    Processor for integrating amendment tracking into the pipeline.
    """
    
    def __init__(self, jurisdiction: str = "KPK"):
        self.tracker = KPKAmendmentTracker(jurisdiction)
    
    def process_document(self, 
                        document_data: Dict,
                        rule_extracted_entities: Dict = None) -> Dict:
        """
        Process document through amendment tracking.
        
        Args:
            document_data: Document data from previous phases
            rule_extracted_entities: Entities from 4.1_rule_extractor
            
        Returns:
            Enhanced document data with amendment tracking
        """
        try:
            text = document_data.get('normalized_text', '')
            metadata = document_data.get('metadata', {})
            
            # Extract base law information
            base_law_info = {
                "title": metadata.get('law_title', ''),
                "year": metadata.get('year', ''),
                "jurisdiction": metadata.get('jurisdiction', 'KPK'),
                "effective_date": metadata.get('effective_date', '')
            }
            
            # Extract amendments
            extracted = self.tracker.extract_amendments(text, base_law_info)
            
            # Build complete version chains
            version_chains = self.tracker.build_complete_version_chains(extracted, base_law_info)
            
            # Integrate with rule-extracted entities if available
            if rule_extracted_entities:
                self._integrate_with_entities(extracted, rule_extracted_entities)
            
            # Enhance document data
            document_data['amendment_tracking'] = {
                "extracted_amendments": extracted,
                "version_chains": version_chains,
                "temporal_analysis": self._create_temporal_analysis(version_chains),
                "statistics": self.tracker.stats.copy(),
                "abstention_log": self.tracker.abstention_log[-20:]  # Last 20
            }
            
            document_data['amendment_timestamp'] = datetime.now().isoformat()
            
            return document_data
            
        except Exception as e:
            logger.error(f"Error in amendment processing: {e}")
            document_data['amendment_tracking'] = {"error": str(e)}
            return document_data
    
    def _integrate_with_entities(self, amendment_data: Dict, rule_entities: Dict):
        """Integrate amendment data with rule-extracted entities"""
        # This would cross-reference sections found by rule extractor
        # with amendment records for validation
        pass
    
    def _create_temporal_analysis(self, version_chains: Dict) -> Dict:
        """Create temporal analysis from version chains"""
        chains = version_chains.get('version_chains', {})
        validity = version_chains.get('temporal_validity', {})
        
        analysis = {
            "total_sections_tracked": len(chains),
            "sections_with_amendments": sum(1 for c in chains.values() if len(c) > 1),
            "validity_summary": {
                "valid": sum(1 for v in validity.values() if v.get('status') == 'valid'),
                "invalid": sum(1 for v in validity.values() if v.get('status') == 'invalid'),
                "needs_review": sum(1 for v in validity.values() if v.get('status') == 'needs_review'),
                "unknown": sum(1 for v in validity.values() if v.get('status') == 'unknown')
            },
            "temporal_range": self._calculate_temporal_range(chains),
            "amendment_frequency": self._calculate_amendment_frequency(chains)
        }
        
        return analysis
    
    def _calculate_temporal_range(self, chains: Dict) -> Dict:
        """Calculate temporal range of amendments"""
        all_dates = []
        
        for chain in chains.values():
            for version in chain:
                if version.get('effective_date'):
                    all_dates.append(version['effective_date'])
                if version.get('amending_year'):
                    all_dates.append(f"{version['amending_year']}-01-01")
        
        if all_dates:
            try:
                sorted_dates = sorted(all_dates)
                return {
                    "earliest": sorted_dates[0],
                    "latest": sorted_dates[-1],
                    "total_years": len(set(d[:4] for d in all_dates if len(d) >= 4))
                }
            except:
                pass
        
        return {"earliest": "", "latest": "", "total_years": 0}
    
    def _calculate_amendment_frequency(self, chains: Dict) -> Dict:
        """Calculate amendment frequency"""
        amendments_by_year = defaultdict(int)
        
        for chain in chains.values():
            for version in chain:
                if version.get('action') not in ['original', 'unknown']:
                    year = version.get('amending_year') or version.get('effective_date', '')[:4]
                    if year and year.isdigit():
                        amendments_by_year[year] += 1
        
        return {
            "total_amendments": sum(amendments_by_year.values()),
            "amendments_by_year": dict(amendments_by_year),
            "average_per_year": sum(amendments_by_year.values()) / max(len(amendments_by_year), 1)
        }


# ========== COMMAND LINE INTERFACE ==========

def main():
    """Command line interface for amendment tracking"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Deterministic amendment tracking for KPK forestry laws")
    parser.add_argument("--input", "-i", required=True, help="Input JSON file from normalization")
    parser.add_argument("--output", "-o", help="Output JSON file")
    parser.add_argument("--jurisdiction", "-j", default="KPK", help="Jurisdiction (default: KPK)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Load document data
        with open(args.input, 'r', encoding='utf-8') as f:
            document_data = json.load(f)
        
        # Process amendments
        processor = AmendmentProcessor(args.jurisdiction)
        result = processor.process_document(document_data)
        
        # Print summary
        amendment_data = result.get('amendment_tracking', {})
        extracted = amendment_data.get('extracted_amendments', {})
        summary = extracted.get('amendment_summary', {}) if isinstance(extracted, dict) else {}
        
        print("\n" + "=" * 60)
        print("AMENDMENT TRACKING RESULTS")
        print("=" * 60)
        
        if isinstance(summary, dict):
            print(f"Total Amendments: {summary.get('total_amendments', 0)}")
            print(f"Sections Affected: {summary.get('sections_affected', 0)}")
            print(f"Gazette References: {summary.get('gazette_references', 0)}")
            print(f"Conflicts Detected: {summary.get('conflicts', 0)}")
        else:
            print(f"Amendments Found: {len(extracted.get('amendments', []))}")
        
        chains = amendment_data.get('version_chains', {})
        if isinstance(chains, dict):
            print(f"Version Chains Built: {len(chains.get('version_chains', {}))}")
        
        temporal = amendment_data.get('temporal_analysis', {})
        if isinstance(temporal, dict):
            validity = temporal.get('validity_summary', {})
            print(f"\nValidity Summary:")
            for status, count in validity.items():
                print(f"  {status.title()}: {count}")
        
        stats = amendment_data.get('statistics', {})
        print(f"\nStatistics:")
        for key, value in stats.items():
            print(f"  {key.replace('_', ' ').title()}: {value}")
        
        # Save if output specified
        if args.output:
            os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else '.', exist_ok=True)
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"\nResults saved to: {args.output}")
        
        # Show sample amendments
        if args.verbose:
            amendments = extracted.get('amendments', []) if isinstance(extracted, dict) else []
            if amendments:
                print(f"\nSample Amendments:")
                for i, amendment in enumerate(amendments[:3]):
                    print(f"  {i+1}. {amendment.get('action', 'unknown')} "
                          f"Section {amendment.get('section_number', 'unknown')} "
                          f"by {amendment.get('amending_law', 'unknown')}")
        
        print("\n" + "=" * 60)
        print("Amendment tracking complete. Deterministic version chains built. ✓")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


if __name__ == "__main__":
    main()
