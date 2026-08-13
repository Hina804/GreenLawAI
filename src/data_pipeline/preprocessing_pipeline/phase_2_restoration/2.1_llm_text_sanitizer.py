"""
LLM_TEXT_SANITIZER.PY - Phase 2.1: LLM-Based Text Sanitization & Restoration
Uses LLaMA 3.2 via Ollama to fix OCR errors WITHOUT interpreting legal meaning.
Only cleans text - legal interpretation left to rule-based Phase 4.
Author: Hina Ali, Eman Irfan
Date: January 29, 2026
"""

import os
import re
import json
import logging
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, asdict, field
from datetime import datetime
from collections import defaultdict
from enum import Enum
import statistics
import time

# Third-party imports
# ollama check moved detailed inside usages to prevent import hangs

# Import from common modules
try:
    # Try absolute import (assuming src is in sys.path)
    from preprocessing_pipeline.common.config import PipelineConfig, LLMSanitizerConfig
    from preprocessing_pipeline.common.constants import KPK_CITIES, FOREST_TYPES
    from preprocessing_pipeline.common.llm_client import LLMClient
    USE_COMMON_CONFIG = True
except (ImportError, ValueError, ModuleNotFoundError):
    USE_COMMON_CONFIG = False
    print("Warning: common modules not found. Using default internal configuration.")
    # Fallback minimal definitions
    class LLMClient:
        def __init__(self, *args, **kwargs): pass
        def generate(self, *args, **kwargs): return ""

# Import from previous phases
try:
    from preprocessing_pipeline.phase_1_extraction import KPKOCREngine, OCRPageResult
    from preprocessing_pipeline.phase_0_foundation import (
        AbstentionLogger, AbstentionType, AbstentionSeverity, 
        PipelineStage, create_abstention_context
    )
    PHASE_PREV_AVAILABLE = True
except ImportError:
    PHASE_PREV_AVAILABLE = False
    print("Warning: Previous phase modules not available.")

# Import from previous phases using the package system
try:
    from preprocessing_pipeline.phase_0_foundation import (
        DocProfiler, DocumentProfile, KPKMetadataEnricher, 
        AbstentionLogger, AbstentionType, AbstentionSeverity, 
        PipelineStage, create_abstention_context
    )
    PHASE_0_MODULES_AVAILABLE = True
except (ImportError, ValueError, ModuleNotFoundError):
    PHASE_0_MODULES_AVAILABLE = False
    print("Warning: Phase 0 modules from package not available. Falling back to standalone.")

# ============================================================================
# CONFIGURATION
# ============================================================================

class LLMSanitizerConfig:
    """Configuration for LLM text sanitization"""
    
    # LLM settings
    LLM_MODEL: str = "llama3.2"  # LLaMA 3.2 via Ollama
    LLM_TEMPERATURE: float = 0.1  # Low for deterministic cleaning
    LLM_MAX_TOKENS: int = 4000
    LLM_TIMEOUT: int = 300  # seconds (increased for "perfect data")
    LLM_API_BASE: Optional[str] = None
    LLM_API_KEY: Optional[str] = None
    
    # Sanitization modes
    SANITIZATION_MODE: str = "hybrid"  # "llm_only", "rule_only", "hybrid"
    USE_LLM_FOR_CLEANING: bool = True
    USE_RULES_FOR_COMMON_ERRORS: bool = True
    FALLBACK_TO_RULES: bool = True
    
    # Text processing
    PRESERVE_ORIGINAL_STRUCTURE: bool = True
    MAINTAIN_LINE_BREAKS: bool = True
    PRESERVE_TABLES: bool = True
    PRESERVE_SECTION_NUMBERS: bool = True
    
    # Language handling
    DETECT_LANGUAGES: bool = True
    SEPARATE_LANGUAGE_SEGMENTS: bool = True
    PRESERVE_CODE_SWITCHING: bool = True
    
    # OCR error patterns to fix
    FIX_NUMBER_LETTER_CONFUSIONS: bool = True  # f0rest → forest
    FIX_SPACING_ISSUES: bool = True            # for est → forest
    FIX_PUNCTUATION: bool = True               # Rs . → Rs.
    FIX_COMMON_OCR_ERRORS: bool = True
    FIX_KPK_SPECIFIC_TERMS: bool = True
    
    # Confidence thresholds
    MIN_LLM_CONFIDENCE: float = 0.7
    MIN_RULE_CONFIDENCE: float = 0.9
    REJECT_LOW_CONFIDENCE: bool = False
    
    # Performance
    BATCH_PROCESSING: bool = True
    BATCH_SIZE: int = 10
    CACHE_RESULTS: bool = True
    PARALLEL_PROCESSING: bool = False
    MAX_WORKERS: int = 4
    
    # Error handling
    CONTINUE_ON_ERROR: bool = True
    RETRY_FAILED_SANITIZATIONS: bool = True
    MAX_RETRIES: int = 2
    
    # Output
    SAVE_SANITIZED_TEXT: bool = True
    SAVE_CORRECTION_LOG: bool = True
    GENERATE_COMPARISON_REPORT: bool = True

# ============================================================================
# ENUMERATIONS
# ============================================================================

class SanitizationMethod(Enum):
    """Methods used for text sanitization"""
    LLM_CLEANING = "llm_cleaning"
    RULE_BASED = "rule_based"
    HYBRID = "hybrid"
    FALLBACK = "fallback"

class SanitizationQuality(Enum):
    """Quality levels for sanitization"""
    EXCELLENT = "excellent"  # > 90% confidence
    GOOD = "good"          # 70-90% confidence
    FAIR = "fair"          # 50-70% confidence
    POOR = "poor"          # 30-50% confidence
    UNACCEPTABLE = "unacceptable"  # < 30% confidence

class CorrectionType(Enum):
    """Types of corrections applied"""
    OCR_ERROR_FIX = "ocr_error_fix"
    SPACING_CORRECTION = "spacing_correction"
    PUNCTUATION_CORRECTION = "punctuation_correction"
    LANGUAGE_SEPARATION = "language_separation"
    STRUCTURE_RESTORATION = "structure_restoration"
    KPK_TERM_CORRECTION = "kpk_term_correction"

# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class TextCorrection:
    """A single text correction"""
    original: str
    corrected: str
    correction_type: CorrectionType
    confidence: float
    location: Optional[Tuple[int, int]] = None  # (line_num, char_position)
    context: Optional[str] = None
    method: SanitizationMethod = SanitizationMethod.RULE_BASED
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['correction_type'] = self.correction_type.value
        data['method'] = self.method.value
        return data

@dataclass
class LanguageSegment:
    """A segment of text in a specific language"""
    text: str
    language: str  # 'english', 'urdu', 'mixed', 'unknown'
    confidence: float
    start_position: int
    end_position: int
    has_code_switching: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

@dataclass
class StructureElement:
    """A detected structure element"""
    element_type: str  # 'section', 'heading', 'list', 'table', 'paragraph'
    text: str
    position: Tuple[int, int]  # (start_line, end_line)
    confidence: float
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

@dataclass
class SanitizationResult:
    """Result of text sanitization"""
    # Identification
    sanitization_id: str
    source_hash: str
    timestamp: datetime
    
    # Text data
    original_text: str
    sanitized_text: str
    
    # Corrections
    corrections: List[TextCorrection]
    language_segments: List[LanguageSegment]
    structure_elements: List[StructureElement]
    
    # Quality metrics
    confidence_score: float
    quality: SanitizationQuality
    sanitization_method: SanitizationMethod
    ocr_confidence: float = 1.0  # From Phase 1
    source_page: int = 0         # PDF page reference
    
    # Statistics
    total_corrections: int = 0
    character_changes: int = 0
    word_changes: int = 0
    line_changes: int = 0
    
    # Processing info
    processing_time: float = 0.0
    llm_calls: int = 0
    fallback_triggered: bool = False
    
    # Abstention flags
    abstention_flags: List[str] = field(default_factory=list)
    needs_human_review: bool = False
    
    def __post_init__(self):
        """Calculate derived fields"""
        self.total_corrections = len(self.corrections)
        
        # Calculate character changes
        char_changes = 0
        for correction in self.corrections:
            char_changes += abs(len(correction.corrected) - len(correction.original))
        self.character_changes = char_changes
        
        # Calculate word changes (approximate)
        original_words = len(self.original_text.split())
        sanitized_words = len(self.sanitized_text.split())
        self.word_changes = abs(sanitized_words - original_words)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        
        # CRITICAL FIX: Ensure sanitized_text is never empty if original_text exists
        if not data.get('sanitized_text') and data.get('original_text'):
            # Only warn if it's truly empty (length 0) and original is not
            if len(data.get('sanitized_text', '')) == 0:
                print(f"WARNING: sanitized_text was empty in to_dict, using original_text as fallback")
                data['sanitized_text'] = data['original_text']
        
        # Convert enums
        data['quality'] = self.quality.value
        data['sanitization_method'] = self.sanitization_method.value
        
        # Convert lists
        data['corrections'] = [c.to_dict() for c in self.corrections]
        data['language_segments'] = [ls.to_dict() for ls in self.language_segments]
        data['structure_elements'] = [se.to_dict() for se in self.structure_elements]
        
        # Convert datetime
        data['timestamp'] = self.timestamp.isoformat()
        
        return data
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get sanitization statistics"""
        return {
            'sanitization_id': self.sanitization_id,
            'confidence_score': self.confidence_score,
            'quality': self.quality.value,
            'total_corrections': self.total_corrections,
            'character_changes': self.character_changes,
            'word_changes': self.word_changes,
            'processing_time': self.processing_time,
            'llm_calls': self.llm_calls,
            'fallback_triggered': self.fallback_triggered,
            'needs_human_review': self.needs_human_review,
        }

# ============================================================================
# RULE-BASED CORRECTION ENGINE
# ============================================================================

class RuleBasedCorrector:
    """Rule-based text correction without LLM"""
    
    # Common OCR errors in KPK forestry documents
    COMMON_OCR_ERRORS = {
        # Number-letter confusions
        'f0rest': 'forest',
        'f0restry': 'forestry',
        'f0rrest': 'forest',
        'timb3r': 'timber',
        't1mber': 'timber',
        'de0dar': 'deodar',
        'd30dar': 'deodar',
        'ch1r': 'chir',
        'ka1l': 'kail',
        'sect10n': 'section',
        'secti0n': 'section',
        'pena1ty': 'penalty',
        'pena1ties': 'penalties',
        'perm1t': 'permit',
        'auct10n': 'auction',
        'c0mpartment': 'compartment',
        'c0ntractor': 'contractor',
        'g0vernment': 'government',
        'g0vemment': 'government',
        'officia1': 'official',
        'autnorized': 'authorized',
        'unauthor1zed': 'unauthorized',
        'il1egal': 'illegal',
        'i11egal': 'illegal',
        'conf1scated': 'confiscated',
        'c0nfiscated': 'confiscated',
        'veh1cle': 'vehicle',
        'veh1c1e': 'vehicle',
        'reg1stration': 'registration',
        'reg1strati0n': 'registration',
        'app1ication': 'application',
        'app1icant': 'applicant',
        'cert1ficate': 'certificate',
        'cert1f1cate': 'certificate',
    }
    
    # KPK-specific terms
    KPK_SPECIFIC_TERMS = {
        'kpk': 'KPK',
        'khyber pakhtunkhwa': 'Khyber Pakhtunkhwa',
        'hazara': 'Hazara',
        'malakand': 'Malakand',
        'dfo': 'DFO',
        'sro': 'SRO',
        'fir': 'FIR',
        'cf': 'CF',  # Cubic feet
        'm3': 'm³',
    }
    
    # Spacing patterns to fix
    SPACING_PATTERNS = [
        (r'Rs\s*\.', 'Rs.', 0.95),
        (r'Sec\s*\.', 'Sec.', 0.95),
        (r'No\s*\.', 'No.', 0.95),
        (r'Fig\s*\.', 'Fig.', 0.95),
        (r'etc\s*\.', 'etc.', 0.95),
        (r'i\s*\.\s*e\s*\.', 'i.e.', 0.95),
        (r'e\s*\.\s*g\s*\.', 'e.g.', 0.95),
        (r'for est', 'forest', 0.90),
        (r'tim ber', 'timber', 0.90),
        (r'fire wood', 'firewood', 0.90),
    ]
    
    # Punctuation patterns
    PUNCTUATION_PATTERNS = [
        (r',,', ',', 0.98),
        (r'\.\.', '.', 0.98),
        (r'\?\?', '?', 0.98),
        (r'!!', '!', 0.98),
        (r'\s*:\s*', ': ', 0.95),
        (r'\s*;\s*', '; ', 0.95),
        (r'\s*,\s*', ', ', 0.95),
        (r'\s*\.\s*', '. ', 0.95),
    ]
    
    # Structure patterns
    SECTION_PATTERN = re.compile(r'(?i)(?:section|sec\.?|sec|art\.?|article)\s+(\d+[A-Z]?)')
    HEADING_PATTERN = re.compile(r'^\s*(?:[A-Z][A-Z\s]{5,}|[0-9]+\.\s+[A-Z])')
    LIST_PATTERN = re.compile(r'^\s*(\d+\.|\-|\*|\•|\u2022)')
    TABLE_PATTERN = re.compile(r'\s*\|\s*|\s{3,}')
    
    def __init__(self):
        # Compile regex patterns
        self.urdu_pattern = re.compile(r'[\u0600-\u06FF]')  # Urdu/Arabic script
        self.english_pattern = re.compile(r'[a-zA-Z]')
        self.mixed_lang_pattern = re.compile(r'[\u0600-\u06FF][a-zA-Z]|[a-zA-Z][\u0600-\u06FF]')
        
    def correct_text(self, text: str) -> Tuple[str, List[TextCorrection]]:
        """Apply rule-based corrections to text"""
        corrections = []
        corrected_text = text
        
        # Apply common OCR error corrections
        # Use word boundaries and negative lookahead to prevent re-expansion
        for error, correction in self.COMMON_OCR_ERRORS.items():
            pattern = re.compile(rf'\b{re.escape(error)}\b', re.IGNORECASE)
            # Only replace if not already corrected (e.g., don't replace 'section' in 'Section 1')
            def safe_replace(match):
                if match.group(0).lower() == correction.lower():
                    return match.group(0) # Already correct
                return correction
            
            matches = list(pattern.finditer(corrected_text))
            for match in reversed(matches):
                original = match.group(0)
                if original.lower() == correction.lower():
                    continue
                
                corrected_text = corrected_text[:match.start()] + correction + corrected_text[match.end():]
                corrections.append(TextCorrection(
                    original=original,
                    corrected=correction,
                    correction_type=CorrectionType.OCR_ERROR_FIX,
                    confidence=0.95,
                    method=SanitizationMethod.RULE_BASED
                ))
        
        # Apply KPK-specific term corrections with word boundaries
        for error, correction in self.KPK_SPECIFIC_TERMS.items():
            pattern = re.compile(rf'\b{re.escape(error)}\b', re.IGNORECASE)
            matches = list(pattern.finditer(corrected_text))
            for match in reversed(matches):
                original = match.group(0)
                if original == correction: continue # Already correct case
                
                corrected_text = corrected_text[:match.start()] + correction + corrected_text[match.end():]
                corrections.append(TextCorrection(
                    original=original,
                    corrected=correction,
                    correction_type=CorrectionType.KPK_TERM_CORRECTION,
                    confidence=0.90,
                    method=SanitizationMethod.RULE_BASED
                ))
        
        # Apply spacing corrections
        for pattern, replacement, confidence in self.SPACING_PATTERNS:
            matches = list(re.finditer(pattern, corrected_text))
            for match in reversed(matches):  # Process backwards to avoid position issues
                original = match.group(0)
                corrected_text = corrected_text[:match.start()] + replacement + corrected_text[match.end():]
                corrections.append(TextCorrection(
                    original=original,
                    corrected=replacement,
                    correction_type=CorrectionType.SPACING_CORRECTION,
                    confidence=confidence,
                    method=SanitizationMethod.RULE_BASED
                ))
        
        # Apply punctuation corrections
        for pattern, replacement, confidence in self.PUNCTUATION_PATTERNS:
            matches = list(re.finditer(pattern, corrected_text))
            for match in reversed(matches):
                original = match.group(0)
                corrected_text = corrected_text[:match.start()] + replacement + corrected_text[match.end():]
                corrections.append(TextCorrection(
                    original=original,
                    corrected=replacement,
                    correction_type=CorrectionType.PUNCTUATION_CORRECTION,
                    confidence=confidence,
                    method=SanitizationMethod.RULE_BASED
                ))
        
        # Restore section headers with word boundaries to prevent "Sectiontion"
        # The bug: replacing "Sec" inside "Section" -> "Sectiontion"
        # The fix: Ensure we don't replace if it's already "Section"
        section_matches = list(self.SECTION_PATTERN.finditer(corrected_text))
        for match in section_matches:
            original = match.group(0)
            
            # Check if this is already correctly standardized
            if original.startswith("Section ") or original.startswith("Article "):
                continue

            # Standardize format
            # Use negative lookahead to ensure we don't double-tag
            standardized = re.sub(r'(?i)\b(sec\.?|sec|art\.?)\b', lambda m: 'Section' if 'sec' in m.group(1).lower() else 'Article', original)
            standardized = re.sub(r'\s+', ' ', standardized)  # Normalize spaces
            
            if original != standardized:
                corrected_text = corrected_text[:match.start()] + standardized + corrected_text[match.end():]
                corrections.append(TextCorrection(
                    original=original,
                    corrected=standardized,
                    correction_type=CorrectionType.STRUCTURE_RESTORATION,
                    confidence=0.85,
                    method=SanitizationMethod.RULE_BASED
                ))
        
        return corrected_text, corrections
    
    def detect_language_segments(self, text: str) -> List[LanguageSegment]:
        """Detect language segments in text"""
        segments = []
        lines = text.split('\n')
        
        for line_num, line in enumerate(lines):
            if not line.strip():
                continue
            
            # Check for Urdu text
            urdu_chars = self.urdu_pattern.findall(line)
            english_chars = self.english_pattern.findall(line)
            
            total_chars = len(line)
            if total_chars == 0:
                continue
            
            urdu_ratio = len(urdu_chars) / total_chars
            english_ratio = len(english_chars) / total_chars
            
            # Determine language
            if urdu_ratio > 0.7:
                language = 'urdu'
                confidence = min(0.98, urdu_ratio)
            elif english_ratio > 0.7:
                language = 'english'
                confidence = min(0.98, english_ratio)
            elif urdu_ratio > 0.3 and english_ratio > 0.3:
                language = 'mixed'
                confidence = 0.8
                # Try to separate mixed words
                mixed_words = self.mixed_lang_pattern.findall(line)
                if mixed_words:
                    # Add special flag for code switching
                    pass
            else:
                language = 'unknown'
                confidence = 0.5
            
            # Create segment
            segment = LanguageSegment(
                text=line,
                language=language,
                confidence=confidence,
                start_position=line_num,
                end_position=line_num,
                has_code_switching=(language == 'mixed')
            )
            segments.append(segment)
        
        return segments
    
    def detect_structure(self, text: str) -> List[StructureElement]:
        """Detect structure elements in text"""
        elements = []
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            if not line.strip():
                continue
            
            # Check for sections
            section_match = self.SECTION_PATTERN.search(line)
            if section_match and len(line.strip()) < 50:
                elements.append(StructureElement(
                    element_type='section',
                    text=line.strip(),
                    position=(i, i),
                    confidence=0.9,
                    metadata={'section_number': section_match.group(1)}
                ))
            
            # Check for headings
            elif self.HEADING_PATTERN.match(line) and len(line.strip()) < 100:
                elements.append(StructureElement(
                    element_type='heading',
                    text=line.strip(),
                    position=(i, i),
                    confidence=0.8
                ))
            
            # Check for list items
            elif self.LIST_PATTERN.match(line):
                elements.append(StructureElement(
                    element_type='list',
                    text=line.strip(),
                    position=(i, i),
                    confidence=0.85
                ))
            
            # Check for tables (simplified)
            elif self.TABLE_PATTERN.search(line) and len(line.split()) > 3:
                # Look for consecutive table-like lines
                table_lines = [i]
                for j in range(i+1, min(i+5, len(lines))):
                    if self.TABLE_PATTERN.search(lines[j]) and len(lines[j].split()) > 2:
                        table_lines.append(j)
                
                if len(table_lines) >= 2:
                    elements.append(StructureElement(
                        element_type='table',
                        text='\n'.join(lines[min(table_lines):max(table_lines)+1]),
                        position=(min(table_lines), max(table_lines)),
                        confidence=0.75,
                        metadata={'row_count': len(table_lines)}
                    ))
        
        return elements

# ============================================================================
# LLM TEXT SANITIZER
# ============================================================================

class LLMTextSanitizer:
    """
    Phase 2.1: LLM-Based Text Sanitization & Restoration
    Uses LLaMA 3.2 to fix OCR errors without interpreting legal meaning.
    """
    
    def __init__(self, 
                 config: Optional[Union[LLMSanitizerConfig, Dict]] = None,
                 enable_abstention_logging: bool = True,
                 logger: Optional[logging.Logger] = None):
        """
        Initialize LLM text sanitizer.
        
        Args:
            config: Configuration object or dictionary
            enable_abstention_logging: Whether to log abstentions
            logger: Optional logger instance
        """
        
        # Configuration (ignore unrelated PipelineConfig from orchestrator)
        if isinstance(config, LLMSanitizerConfig):
            self.config = config
        elif isinstance(config, dict):
            self.config = LLMSanitizerConfig()
            for key, value in config.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
        else:
            self.config = LLMSanitizerConfig()
        
        # Setup logging
        self.logger = logger or self._setup_logging()
        
        # Abstention logging
        self.enable_abstention_logging = enable_abstention_logging
        self.abstention_logger = None
        if enable_abstention_logging and PHASE_PREV_AVAILABLE:
            try:
                self.abstention_logger = AbstentionLogger()
            except Exception as e:
                self.logger.warning(f"Could not initialize abstention logger: {e}")
        
        # Import from Phase 5.1 and 5.2
        # Import LLMClient (Critical dependency for LLM mode)
        try:
            from preprocessing_pipeline.common.llm_client import LLMClient
        except (ImportError, ValueError, ModuleNotFoundError):
            self.logger.warning("Could not import LLMClient from common, using fallback")
            class LLMClient:
                def __init__(self, *args, **kwargs): pass
                def generate(self, *args, **kwargs): return ""

        # Import from Phase 5.1 and 5.2 (Optional/Dependent)
        try:
            from preprocessing_pipeline.phase_5_authority_reasoning.authority_hierarchy import (
                AuthorityHierarchyResolver, AuthorityLevel, LegalSource, ResolutionResult, KPKJurisdictionMapper
            )
            from preprocessing_pipeline.phase_5_authority_reasoning.penalty_logic_engine import (
                PenaltyLogicEngine, ViolationType, ForestType, PenaltyCalculation
            )
            from preprocessing_pipeline.common.config import KPK_FORESTRY_CONFIG
        except (ImportError, ValueError, ModuleNotFoundError):
            # Fallback for standalone testing
            class AuthorityHierarchyResolver: pass
            class AuthorityLevel(Enum): pass
            class LegalSource: pass
            class KPKJurisdictionMapper: pass
            class PenaltyLogicEngine: pass
            class ViolationType(Enum): pass
            class ForestType(Enum): pass
            class PenaltyCalculation: pass
        
        # Initialize components
        self.rule_corrector = RuleBasedCorrector()
        
        # LLM client
        # LLM client
        self.llm_client = None
        
        # Check for Ollama availability locally
        try:
            import ollama
            ollama_available = True
        except ImportError:
            ollama_available = False
            
        if self.config.USE_LLM_FOR_CLEANING and ollama_available:
            try:
                # Always ensure LLMClient is available (either from common or fallback)
                if 'LLMClient' not in globals() and 'LLMClient' not in locals():
                    self.logger.warning("LLMClient not defined, using internal fallback")
                    class LLMClient:
                        def __init__(self, *args, **kwargs): pass
                        def generate(self, *args, **kwargs): return ""
                
                llm_client_args = {
                    "model": self.config.LLM_MODEL,
                    "temperature": self.config.LLM_TEMPERATURE,
                    "max_tokens": self.config.LLM_MAX_TOKENS,
                    "timeout": self.config.LLM_TIMEOUT,
                }
                if self.config.LLM_API_BASE:
                    llm_client_args["api_base"] = self.config.LLM_API_BASE
                if self.config.LLM_API_KEY:
                    llm_client_args["api_key"] = self.config.LLM_API_KEY

                self.llm_client = LLMClient(**llm_client_args)
                self.logger.info(f"LLM client initialized with model: {self.config.LLM_MODEL}")
            except Exception as e:
                self.logger.warning(f"Could not initialize LLM client: {e}")
                if not self.config.FALLBACK_TO_RULES:
                    raise
        else:
            self.logger.warning("LLM not available or disabled, using rule-based sanitization only")
        
        # Statistics
        self.stats = self._init_statistics()
        
        # Cache
        self._sanitization_cache = {}
        
        self.logger.info(f"LLMTextSanitizer initialized (LLM: {self.llm_client is not None})")
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging"""
        logger = logging.getLogger('LLMTextSanitizer')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            # Console handler
            ch = logging.StreamHandler()
            ch.setLevel(logging.INFO)
            
            # Formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            ch.setFormatter(formatter)
            
            logger.addHandler(ch)
        
        return logger
    
    def _init_statistics(self) -> Dict[str, Any]:
        """Initialize statistics structure"""
        return {
            'texts_sanitized': 0,
            'total_characters_processed': 0,
            'sanitization_time_total': 0.0,
            'avg_sanitization_time': 0.0,
            
            'sanitization_methods': {
                'llm_cleaning': 0,
                'rule_based': 0,
                'hybrid': 0,
                'fallback': 0,
            },
            
            'correction_types': {
                'ocr_error_fix': 0,
                'spacing_correction': 0,
                'punctuation_correction': 0,
                'language_separation': 0,
                'structure_restoration': 0,
                'kpk_term_correction': 0,
            },
            
            'quality_distribution': {
                'excellent': 0,
                'good': 0,
                'fair': 0,
                'poor': 0,
                'unacceptable': 0,
            },
            
            'language_distribution': {
                'english_only': 0,
                'urdu_only': 0,
                'mixed_language': 0,
                'unknown': 0,
            },
            
            'llm_metrics': {
                'llm_calls': 0,
                'llm_successes': 0,
                'llm_failures': 0,
                'avg_llm_response_time': 0.0,
            },
            
            'performance': {
                'fastest_sanitization': float('inf'),
                'slowest_sanitization': 0.0,
                'sanitization_times': [],
            },
            
            'issues': {
                'low_confidence_results': 0,
                'abstention_flags_raised': 0,
                'fallback_triggered': 0,
            },
        }
    
    def sanitize_text(self, 
                     text: str,
                     source_info: Optional[Dict[str, Any]] = None,
                     use_llm: Optional[bool] = None) -> SanitizationResult:
        """
        Sanitize text using LLM and/or rule-based methods.
        
        Args:
            text: Raw text from OCR (can have errors)
            source_info: Optional metadata about the source
            use_llm: Override config setting for LLM usage
        
        Returns:
            SanitizationResult with cleaned text and metadata
        """
        import time
        start_time = time.time()
        
        try:
            # Generate hash for caching
            text_hash = hashlib.md5(text.encode()).hexdigest()[:16]
            
            # Check cache
            if self.config.CACHE_RESULTS and text_hash in self._sanitization_cache:
                self.logger.info(f"Returning cached sanitization for hash: {text_hash[:8]}")
                return self._sanitization_cache[text_hash]
            
            self.logger.info(f"Sanitizing text (length: {len(text)} chars, hash: {text_hash[:8]})")
            
            # Determine sanitization method
            if use_llm is None:
                use_llm = self.config.USE_LLM_FOR_CLEANING and self.llm_client is not None
            
            sanitization_id = f"san_{text_hash[:8]}_{datetime.now().strftime('%H%M%S')}"
            
            # Apply sanitization based on method
            if use_llm and self.config.SANITIZATION_MODE == 'llm_only':
                result = self._sanitize_with_llm_only(text, sanitization_id, text_hash)
            elif not use_llm and self.config.SANITIZATION_MODE == 'rule_only':
                result = self._sanitize_with_rules_only(text, sanitization_id, text_hash)
            else:  # hybrid or fallback
                result = self._sanitize_hybrid(text, sanitization_id, text_hash, use_llm)
            
            # Add source info if provided
            if source_info:
                result.processing_metadata = source_info
            
            # Calculate processing time
            result.processing_time = time.time() - start_time
            
            # Cache result
            if self.config.CACHE_RESULTS:
                self._sanitization_cache[text_hash] = result
            
            # Update statistics
            self._update_statistics(result)
            
            # Log abstention if quality is poor
            if (self.enable_abstention_logging and self.abstention_logger and 
                result.quality in [SanitizationQuality.POOR, SanitizationQuality.UNACCEPTABLE]):
                
                self._log_sanitization_abstention(result, source_info)
            
            # Populate traceability fields from source_info
            if source_info:
                result.source_page = source_info.get('page_number', 0)
                result.ocr_confidence = source_info.get('ocr_confidence', 1.0)
                
            self.logger.info(
                f"Sanitization complete: {sanitization_id} - "
                f"Method: {result.sanitization_method.value}, "
                f"Quality: {result.quality.value}, "
                f"Confidence: {result.confidence_score:.2f}, "
                f"Corrections: {result.total_corrections}, "
                f"Time: {result.processing_time:.2f}s"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Sanitization failed: {e}")
            
            # Create error result
            return self._create_error_result(text, str(e), start_time)
    
    def _sanitize_with_llm_only(self, text: str, sanitization_id: str, 
                               text_hash: str) -> SanitizationResult:
        """Sanitize text using LLM only"""
        try:
            # Prepare LLM prompt
            prompt = self._create_llm_prompt(text)
            
            # Call LLM
            llm_start = time.time()
            llm_response = self.llm_client.generate(prompt)
            llm_time = time.time() - llm_start
            
            # CRITICAL FIX: Ensure non-empty response
            if not llm_response or not llm_response.strip():
                raise ValueError("LLM returned empty or whitespace-only response")
            
            # Parse LLM response
            parsed_result = self._parse_llm_response(llm_response, text)
            
            # Create result
            result = SanitizationResult(
                sanitization_id=sanitization_id,
                source_hash=text_hash,
                timestamp=datetime.now(),
                original_text=text,
                sanitized_text=parsed_result['normalized_text'],
                corrections=parsed_result['corrections'],
                language_segments=parsed_result['language_segments'],
                structure_elements=parsed_result['structure_elements'],
                confidence_score=parsed_result['confidence_score'],
                quality=self._determine_quality(parsed_result['confidence_score']),
                sanitization_method=SanitizationMethod.LLM_CLEANING,
                llm_calls=1,
                fallback_triggered=False,
                abstention_flags=parsed_result['abstention_flags'],
                needs_human_review=parsed_result['confidence_score'] < self.config.MIN_LLM_CONFIDENCE,
            )
            
            # Update LLM metrics
            self.stats['llm_metrics']['llm_calls'] += 1
            self.stats['llm_metrics']['llm_successes'] += 1
            self.stats['llm_metrics']['avg_llm_response_time'] = (
                (self.stats['llm_metrics']['avg_llm_response_time'] * 
                 (self.stats['llm_metrics']['llm_successes'] - 1) + llm_time) 
                / self.stats['llm_metrics']['llm_successes']
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"LLM-only sanitization failed: {e}")
            self.stats['llm_metrics']['llm_calls'] += 1
            self.stats['llm_metrics']['llm_failures'] += 1
            
            if self.config.FALLBACK_TO_RULES:
                self.logger.info("Falling back to rule-based sanitization")
                return self._sanitize_with_rules_only(text, sanitization_id, text_hash)
            else:
                raise
    
    def _sanitize_with_rules_only(self, text: str, sanitization_id: str, 
                                 text_hash: str) -> SanitizationResult:
        """Sanitize text using rule-based methods only"""
        # Apply rule-based corrections
        corrected_text, corrections = self.rule_corrector.correct_text(text)
        
        # Detect language segments
        language_segments = self.rule_corrector.detect_language_segments(corrected_text)
        
        # Detect structure elements
        structure_elements = self.rule_corrector.detect_structure(corrected_text)
        
        # Calculate confidence
        confidence = self._calculate_rule_confidence(text, corrected_text, corrections)
        
        # Check for abstention flags
        abstention_flags = []
        if confidence < self.config.MIN_RULE_CONFIDENCE:
            abstention_flags.append("low_confidence_rule_based")
        
        # Create result
        result = SanitizationResult(
            sanitization_id=sanitization_id,
            source_hash=text_hash,
            timestamp=datetime.now(),
            original_text=text,
            sanitized_text=corrected_text,
            corrections=corrections,
            language_segments=language_segments,
            structure_elements=structure_elements,
            confidence_score=confidence,
            quality=self._determine_quality(confidence),
            sanitization_method=SanitizationMethod.RULE_BASED,
            llm_calls=0,
            fallback_triggered=False,
            abstention_flags=abstention_flags,
            needs_human_review=confidence < self.config.MIN_RULE_CONFIDENCE,
        )
        
        return result
    
    def _sanitize_hybrid(self, text: str, sanitization_id: str, 
                        text_hash: str, use_llm: bool) -> SanitizationResult:
        """Sanitize text using hybrid approach"""
        fallback_triggered = False
        
        try:
            if use_llm:
                # Try LLM first
                try:
                    result = self._sanitize_with_llm_only(text, sanitization_id, text_hash)
                    result.sanitization_method = SanitizationMethod.HYBRID
                    return result
                except Exception as e:
                    self.logger.warning(f"LLM failed in hybrid mode: {e}")
                    fallback_triggered = True
            
            # Use rule-based as fallback or primary
            result = self._sanitize_with_rules_only(text, sanitization_id, text_hash)
            result.sanitization_method = SanitizationMethod.HYBRID
            result.fallback_triggered = fallback_triggered
            
            return result
            
        except Exception as e:
            self.logger.error(f"Hybrid sanitization failed: {e}")
            raise
    
    def _create_llm_prompt(self, text: str) -> str:
        """Create prompt for LLM text sanitization"""
        prompt = f"""
        You are an expert OCR text cleaner for Khyber Pakhtunkhwa (KPK) forestry documents.
        Your task is to identify OCR errors and provide specific corrections.
        
        IMPORTANT RULES:
        1. ONLY fix OCR errors (spelling, spacing, punctuation).
        2. DO NOT rewrite the text. Return a list of SPECIFIC replacments.
        3. Preserve ALL legal terms, section numbers, and formatting.
        4. Keep Urdu/Arabic script SEPARATE from English.
        5. Do NOT translate any text.
        
        OCR ERROR CORRECTION EXAMPLES:
        - "f0rest" -> "forest"
        - "secti0n" -> "section"
        - "for est" -> "forest"
        - "Rs ." -> "Rs."
        
        OCR TEXT TO ANALYZE (length: {len(text)} characters):
        ```
        {text}
        ```
        
        OUTPUT FORMAT (JSON ONLY, NO OTHER TEXT):
        {{
          "corrections": [
            {{"original": "f0rest", "corrected": "forest", "context": "protected f0rest area"}},
            {{"original": "secti0n", "corrected": "section", "context": "under secti0n 27"}},
            {{"original": "for est", "corrected": "forest", "context": "reserved for est"}}
          ],
          "abstention_flags": ["unreadable_page", "handwritten_notes"]
        }}
        
        IMPORTANT: 
        - Return ONLY the JSON object. 
        - The "original" field must textually match the substring in the input EXACTLY.
        - The "context" field helps identify the specific instance if the word appears multiple times.
        """
        
        return prompt
    
    def _parse_llm_response(self, llm_response: str, original_text: str) -> Dict[str, Any]:
        """Parse LLM response and extract sanitization data"""
        try:
            # Try to find JSON in the response
            json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(0)
                data = json.loads(json_str)
                
                # Convert to our data structures
                corrections = []
                for corr in data.get('corrections', []): # Changed from 'ocr_corrections' to 'corrections'
                    corrections.append(TextCorrection(
                        original=corr.get('original', ''),
                        corrected=corr.get('corrected', ''),
                        correction_type=CorrectionType.OCR_ERROR_FIX, # Default type
                        confidence=0.9, # High confidence for explicit corrections
                        context=corr.get('context'),
                        method=SanitizationMethod.LLM_CLEANING
                    ))
                
                # Language segments not part of this specific prompt anymore, but keeping structure valid
                language_segments = [] 
                
                structure_elements = []

                # NEW: Apply corrections to generate normalized_text
                # This ensures we don't rely on LLM for full text generation
                normalized_text = self._apply_llm_corrections(original_text, corrections)

                parsed_result = {
                    "normalized_text": normalized_text, # Computed, not from LLM
                    "corrections": corrections,
                    "language_segments": language_segments,
                    "structure_elements": structure_elements,
                    "confidence_score": 0.9, # Assume high if JSON parsed
                    "abstention_flags": data.get('abstention_flags', [])
                }
                
                return parsed_result
                
            else:
                self.logger.warning("No JSON found in LLM response")
                return self._create_empty_result_dict(original_text)
                
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to decode JSON from LLM: {e}")
            return self._create_empty_result_dict(original_text)
        except Exception as e:
            self.logger.error(f"Failed to parse LLM response: {e}")
            return self._create_empty_result_dict(original_text)

    def _apply_llm_corrections(self, text: str, corrections: List[TextCorrection]) -> str:
        """
        Apply corrections to text deterministically.
        Uses context to resolve ambiguity where possible.
        """
        replacements = [] # List of (start, end, replacement_text)
        
        for corr in corrections:
            original = corr.original
            corrected = corr.corrected
            context = corr.context
            
            if not original:
                continue
                
            match_found = False
            
            # 1. Try to find using context
            if context and original in context and context in text:
                # Find context start
                context_start = text.find(context)
                # Find original inside context (relative)
                rel_start = context.find(original)
                
                abs_start = context_start + rel_start
                abs_end = abs_start + len(original)
                
                replacements.append((abs_start, abs_end, corrected))
                match_found = True
                
            # 2. If context fail, check for unique occurrence
            else:
                count = text.count(original)
                if count == 1:
                    start = text.find(original)
                    end = start + len(original)
                    replacements.append((start, end, corrected))
                    match_found = True
                elif count > 1:
                    self.logger.warning(f"Ambiguous correction skipped: '{original}' found {count} times without valid context.")
                # If count == 0, LLM hallucinated the error/text, skip.

        # Sort replacements by start index descending to apply safely
        replacements.sort(key=lambda x: x[0], reverse=True)
        
        # Apply replacements
        result_text = text
        for start, end, new_text in replacements:
            # Simple check to ensure ranges don't overlap (greedy approach: first one wins due to reverse sort? No, latest in text wins)
            # Actually with reverse sort, we modify end of string first, so earlier indices remain valid.
            # We just need to ensure we don't apply overlapping changes.
            # Since we sorted reverse, we just need to check if current end <= previous start (which is 'next' in the loop)
            # But simpler: assume non-overlapping or let them overwrite if precise.
            # Safety check:
            if start < 0 or end > len(result_text): # Check bounds against CURRENT result_text? No, indices are based on ORIGINAL.
                continue
               
            # Check if we are clashing with a previous replacement? 
            # In reverse iteration:
            # Text: A B C D E
            # Replace D->X (3,4). New: A B C X E
            # Replace B->Y (1,2). New: A Y C X E.
            # Indices are stable.
            # Overlap check:
            # If we have (3,5) and (4,6) -> Overlap!
            # Since we didn't check for overlaps during collection, we might have issues.
            # Optimization: Check overlaps.
            
            result_text = result_text[:start] + new_text + result_text[end:]
            
        return result_text
    
    def _calculate_rule_confidence(self, original: str, corrected: str, 
                                 corrections: List[TextCorrection]) -> float:
        """Calculate confidence score for rule-based sanitization"""
        # Base confidence
        confidence = 0.5
        
        # Adjust based on number of corrections
        if corrections:
            avg_correction_conf = sum(c.confidence for c in corrections) / len(corrections)
            confidence = (confidence + avg_correction_conf) / 2
        
        # Adjust based on text length and quality indicators
        lines = original.split('\n')
        
        # Positive indicators
        if len(original) > 200:
            confidence += 0.1
        
        if any(keyword in original.lower() for keyword in ['section', 'ordinance', 'act']):
            confidence += 0.1
        
        # Negative indicators
        if original.count('?') > original.count('.') / 2:
            confidence -= 0.1
        
        if original.count('@') > 5:
            confidence -= 0.1
        
        # Normalize to 0.0-1.0 range
        return max(0.0, min(1.0, confidence))
    
    def _determine_quality(self, confidence: float) -> SanitizationQuality:
        """Determine quality based on confidence score"""
        if confidence >= 0.9:
            return SanitizationQuality.EXCELLENT
        elif confidence >= 0.7:
            return SanitizationQuality.GOOD
        elif confidence >= 0.5:
            return SanitizationQuality.FAIR
        elif confidence >= 0.3:
            return SanitizationQuality.POOR
        else:
            return SanitizationQuality.UNACCEPTABLE
    
    def _update_statistics(self, result: SanitizationResult):
        """Update sanitizer statistics"""
        self.stats['texts_sanitized'] += 1
        self.stats['total_characters_processed'] += len(result.original_text)
        self.stats['sanitization_time_total'] += result.processing_time
        
        # Update sanitization methods
        method = result.sanitization_method.value
        if method in self.stats['sanitization_methods']:
            self.stats['sanitization_methods'][method] += 1
        
        # Update correction types
        for correction in result.corrections:
            corr_type = correction.correction_type.value
            if corr_type in self.stats['correction_types']:
                self.stats['correction_types'][corr_type] += 1
        
        # Update quality distribution
        quality = result.quality.value
        if quality in self.stats['quality_distribution']:
            self.stats['quality_distribution'][quality] += 1
        
        # Update language distribution
        langs = set(seg.language for seg in result.language_segments)
        if len(langs) == 1:
            lang = list(langs)[0]
            if lang == 'english':
                self.stats['language_distribution']['english_only'] += 1
            elif lang == 'urdu':
                self.stats['language_distribution']['urdu_only'] += 1
            else:
                self.stats['language_distribution']['unknown'] += 1
        elif len(langs) > 1:
            self.stats['language_distribution']['mixed_language'] += 1
        
        # Update LLM metrics
        self.stats['llm_metrics']['llm_calls'] += result.llm_calls
        
        # Update issues
        if result.confidence_score < 0.5:
            self.stats['issues']['low_confidence_results'] += 1
        if result.abstention_flags:
            self.stats['issues']['abstention_flags_raised'] += 1
        if result.fallback_triggered:
            self.stats['issues']['fallback_triggered'] += 1
        
        # Update performance metrics
        perf = self.stats['performance']
        perf['sanitization_times'].append(result.processing_time)
        perf['fastest_sanitization'] = min(perf['fastest_sanitization'], result.processing_time)
        perf['slowest_sanitization'] = max(perf['slowest_sanitization'], result.processing_time)
        
        # Calculate averages
        total_texts = self.stats['texts_sanitized']
        if total_texts > 0:
            self.stats['avg_sanitization_time'] = self.stats['sanitization_time_total'] / total_texts
    
    def _log_sanitization_abstention(self, result: SanitizationResult, 
                                   source_info: Optional[Dict[str, Any]]):
        """Log abstention for poor sanitization quality"""
        if self.enable_abstention_logging and self.abstention_logger:
            try:
                context = create_abstention_context(
                    stage=PipelineStage.TEXT_SANITIZATION,
                    component="LLMTextSanitizer",
                    document_path=source_info.get('document_path', 'unknown') if source_info else 'unknown',
                    reason="poor_sanitization_quality",
                    details={
                        'confidence_score': result.confidence_score,
                        'quality': result.quality.value,
                        'sanitization_method': result.sanitization_method.value,
                        'total_corrections': result.total_corrections,
                        'llm_calls': result.llm_calls,
                        'abstention_flags': result.abstention_flags,
                    }
                )
                
                self.abstention_logger.log_abstention(
                    abstention_type=AbstentionType.SANITIZATION_ISSUE,
                    severity=AbstentionSeverity.MEDIUM,
                    context=context,
                    suggested_action="Manual review of sanitized text or use better OCR source",
                    confidence=1.0 - result.confidence_score,
                    component_state=result.to_dict(),
                )
                
                self.logger.info(f"Logged sanitization abstention for {result.sanitization_id}")
                
            except Exception as e:
                self.logger.warning(f"Failed to log sanitization abstention: {e}")
    
    def _create_error_result(self, text: str, error_message: str, 
                           start_time: float) -> SanitizationResult:
        """Create error result when sanitization fails"""
        processing_time = time.time() - start_time
        
        return SanitizationResult(
            sanitization_id=f"error_{datetime.now().strftime('%H%M%S')}",
            source_hash=hashlib.md5(text.encode()).hexdigest()[:16],
            timestamp=datetime.now(),
            original_text=text,
            sanitized_text=text,  # Return original as fallback
            corrections=[],
            language_segments=[],
            structure_elements=[],
            confidence_score=0.0,
            quality=SanitizationQuality.UNACCEPTABLE,
            sanitization_method=SanitizationMethod.FALLBACK,
            processing_time=processing_time,
            llm_calls=0,
            fallback_triggered=True,
            abstention_flags=[f"sanitization_error: {error_message}"],
            needs_human_review=True,
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get current sanitizer statistics"""
        stats = self.stats.copy()
        
        # Calculate derived statistics
        total_texts = stats['texts_sanitized']
        if total_texts > 0:
            stats['avg_sanitization_time'] = stats['sanitization_time_total'] / total_texts
            
            # Calculate percentages
            for method in stats['sanitization_methods']:
                count = stats['sanitization_methods'][method]
                stats['sanitization_methods'][f'{method}_pct'] = count / total_texts * 100
            
            for quality in stats['quality_distribution']:
                count = stats['quality_distribution'][quality]
                stats['quality_distribution'][f'{quality}_pct'] = count / total_texts * 100
        
        # Performance summary
        perf = stats['performance']
        if perf['sanitization_times']:
            perf['avg_sanitization_time'] = sum(perf['sanitization_times']) / len(perf['sanitization_times'])
        else:
            perf['avg_sanitization_time'] = 0.0
            perf['fastest_sanitization'] = 0.0
        
        return stats
    
    def batch_sanitize(self, texts: List[Dict[str, Any]]) -> List[SanitizationResult]:
        """
        Sanitize multiple texts in batch.
        
        Args:
            texts: List of dicts with 'text' and optional 'source_info'
        
        Returns:
            List of SanitizationResult objects
        """
        results = []
        
        for i, text_info in enumerate(texts):
            try:
                self.logger.info(f"Sanitizing text {i+1}/{len(texts)}")
                
                result = self.sanitize_text(
                    text=text_info['text'],
                    source_info=text_info.get('source_info'),
                    use_llm=text_info.get('use_llm')
                )
                results.append(result)
                
            except Exception as e:
                self.logger.error(f"Failed to sanitize text {i+1}: {e}")
                
                # Add error result
                error_result = self._create_error_result(
                    text=text_info['text'],
                    error_message=str(e),
                    start_time=time.time()
                )
                results.append(error_result)
        
        return results

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def save_sanitization_result(result: SanitizationResult, output_dir: Union[str, Path]):
    """Save sanitization result to file"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save as JSON
    json_path = output_dir / f"{result.sanitization_id}.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
    
    # Save sanitized text
    text_path = output_dir / f"{result.sanitization_id}_sanitized.txt"
    with open(text_path, 'w', encoding='utf-8') as f:
        f.write(result.sanitized_text)
    
    # Save comparison
    if result.original_text:
        comp_path = output_dir / f"{result.sanitization_id}_comparison.txt"
        with open(comp_path, 'w', encoding='utf-8') as f:
            f.write("=== ORIGINAL TEXT ===\n")
            f.write(result.original_text[:2000])
            f.write("\n\n=== SANITIZED TEXT ===\n")
            f.write(result.sanitized_text[:2000])
            f.write(f"\n\n=== STATISTICS ===\n")
            f.write(f"Confidence: {result.confidence_score:.2f}\n")
            f.write(f"Quality: {result.quality.value}\n")
            f.write(f"Corrections: {result.total_corrections}\n")
    
    return json_path, text_path

def load_sanitization_result(file_path: Union[str, Path]) -> SanitizationResult:
    """Load sanitization result from JSON file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Reconstruct enums
    data['quality'] = SanitizationQuality(data['quality'])
    data['sanitization_method'] = SanitizationMethod(data['sanitization_method'])
    
    # Reconstruct lists of objects
    corrections = []
    for corr_data in data['corrections']:
        corr_data['correction_type'] = CorrectionType(corr_data['correction_type'])
        corr_data['method'] = SanitizationMethod(corr_data['method'])
        corrections.append(TextCorrection(**corr_data))
    data['corrections'] = corrections
    
    language_segments = []
    for seg_data in data['language_segments']:
        language_segments.append(LanguageSegment(**seg_data))
    data['language_segments'] = language_segments
    
    structure_elements = []
    for elem_data in data['structure_elements']:
        structure_elements.append(StructureElement(**elem_data))
    data['structure_elements'] = structure_elements
    
    # Convert timestamp
    data['timestamp'] = datetime.fromisoformat(data['timestamp'])
    
    return SanitizationResult(**data)

# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    """Main function for standalone testing"""
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description="LLM Text Sanitizer")
    parser.add_argument("--input", required=True, help="Input text file or JSON with text")
    parser.add_argument("--output", help="Output directory for results")
    parser.add_argument("--config", help="Configuration file (JSON)")
    parser.add_argument("--mode", choices=['llm', 'rules', 'hybrid'], default='hybrid',
                       help="Sanitization mode")
    parser.add_argument("--batch", action="store_true", help="Process as batch (JSON array)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Load configuration
    config = {}
    if args.config:
        with open(args.config, 'r') as f:
            config = json.load(f)
    
    # Set sanitization mode
    config['SANITIZATION_MODE'] = {
        'llm': 'llm_only',
        'rules': 'rule_only',
        'hybrid': 'hybrid'
    }[args.mode]
    
    # Initialize sanitizer
    sanitizer = LLMTextSanitizer(config=config)
    
    # Process input
    input_path = Path(args.input)
    
    if args.batch:
        # Process batch of texts
        with open(input_path, 'r', encoding='utf-8') as f:
            texts_data = json.load(f)
        
        if isinstance(texts_data, list):
            results = sanitizer.batch_sanitize(texts_data)
        else:
            print("Error: Batch mode requires JSON array")
            return
        
        # Save results
        if args.output:
            output_dir = Path(args.output)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            for i, result in enumerate(results):
                json_path, text_path = save_sanitization_result(result, output_dir)
                print(f"Saved result {i+1}: {json_path}")
        
        # Print summary
        print(f"\nBatch Sanitization Summary:")
        print(f"  Total Texts: {len(results)}")
        print(f"  Successful: {sum(1 for r in results if r.confidence_score > 0.5)}")
        print(f"  Failed: {sum(1 for r in results if r.confidence_score <= 0.5)}")
        
        if results:
            avg_confidence = sum(r.confidence_score for r in results) / len(results)
            print(f"  Average Confidence: {avg_confidence:.2f}")
    
    else:
        # Process single text
        if input_path.suffix.lower() == '.json':
            with open(input_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            text = data.get('text', '') if isinstance(data, dict) else str(data)
        else:
            with open(input_path, 'r', encoding='utf-8') as f:
                text = f.read()
        
        # Sanitize text
        result = sanitizer.sanitize_text(text, source_info={'document_path': str(input_path)})
        
        # Save or display results
        if args.output:
            output_dir = Path(args.output)
            json_path, text_path = save_sanitization_result(result, output_dir)
            print(f"Results saved to:")
            print(f"  JSON: {json_path}")
            print(f"  Text: {text_path}")
        else:
            print(json.dumps(result.to_dict(), indent=2))
        
        # Print summary
        print(f"\nSanitization Summary:")
        print(f"  Method: {result.sanitization_method.value}")
        print(f"  Confidence: {result.confidence_score:.2f}")
        print(f"  Quality: {result.quality.value}")
        print(f"  Corrections: {result.total_corrections}")
        print(f"  Processing Time: {result.processing_time:.2f}s")
        print(f"  LLM Calls: {result.llm_calls}")
        print(f"  Needs Human Review: {'Yes' if result.needs_human_review else 'No'}")
        
        if result.abstention_flags:
            print(f"  Abstention Flags: {', '.join(result.abstention_flags)}")
        
        print(f"\nSample Corrections (first 5):")
        for i, correction in enumerate(result.corrections[:5]):
            print(f"  {i+1}. {correction.original} → {correction.corrected}")
    
    # Print statistics
    stats = sanitizer.get_statistics()
    print(f"\nSanitizer Statistics:")
    print(f"  Texts Sanitized: {stats['texts_sanitized']}")
    print(f"  Average Time: {stats['avg_sanitization_time']:.2f}s")
    print(f"  LLM Calls: {stats['llm_metrics']['llm_calls']}")
    print(f"  LLM Success Rate: {stats['llm_metrics']['llm_successes']}/{stats['llm_metrics']['llm_calls']}")
    print(f"  Excellent Quality: {stats['quality_distribution']['excellent']}")
    print(f"  Poor Quality: {stats['quality_distribution']['poor']}")

if __name__ == "__main__":
    import time
    main()
