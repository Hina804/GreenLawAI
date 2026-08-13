"""
OCR_ENGINE.PY - Phase 1.5: Advanced KPK Forestry OCR Engine
Enhanced Tesseract-based OCR for KPK forestry documents with specialized preprocessing,
language support, and integration with KPK-specific training data.
Author: Hina Ali, Eman Irfan
Date: January 29, 2026
"""

import os
import sys
import re
import json
import logging
import hashlib
import io
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union, BinaryIO
from dataclasses import dataclass, asdict, field
from datetime import datetime
from collections import defaultdict, Counter
from enum import Enum
import statistics
import pickle

# Third-party imports
import pytesseract
from PIL import Image, ImageFilter, ImageEnhance, ImageOps
import cv2
import numpy as np
import pdf2image
import fitz  # PyMuPDF
from scipy import ndimage
from sklearn.cluster import KMeans

# Import from common modules
try:
    from preprocessing_pipeline.common.config import PipelineConfig, OCRConfig
    from preprocessing_pipeline.common.constants import *
    from preprocessing_pipeline.common.llm_client import LLMClient
    USE_COMMON_CONFIG = True
except ImportError:
    USE_COMMON_CONFIG = False
    print("Warning: common.config not found. Using default configuration.")

# Import shared types to avoid circularity
from .types import OCREngineResult

# Import from other modules using local relative imports for stability
try:
    import importlib
    _pdf_parser_mod = importlib.import_module('.1.1_pdf_parser', package=__package__)
    KPKPDFParser = _pdf_parser_mod.KPKPDFParser
    PDFParseResult = _pdf_parser_mod.PDFParseResult
    PDFPage = _pdf_parser_mod.PDFPage
    PHASE_1_MODULES_AVAILABLE = True
except (ImportError, ValueError) as e:
    PHASE_1_MODULES_AVAILABLE = False
    print(f"Warning: Phase 1 modules not available: {e}. Falling back.")


# Import KPK-specific OCR trainer
try:
    from preprocessing_pipeline.phase_1_extraction import KPKOCRTrainer, KPKFontDatabase
    KPK_TRAINER_AVAILABLE = True
except ImportError:
    KPK_TRAINER_AVAILABLE = False
    print("Warning: KPK OCR trainer not available. Using generic OCR.")

# ============================================================================
# CONFIGURATION
# ============================================================================

class OCRConfig:
    """Configuration for OCR engine"""
    
    # Core OCR settings
    OCR_ENGINE: str = 'tesseract'  # 'tesseract', 'easyocr', 'paddleocr'
    TESSERACT_CMD: Optional[str] = None  # Auto-detect if None
    
    # Language support
    PRIMARY_LANGUAGE: str = 'eng'  # English
    SECONDARY_LANGUAGES: List[str] = ['urd']  # Urdu
    LANGUAGE_MODE: str = 'mixed'  # 'single', 'mixed', 'auto'
    ENABLE_MULTILINGUAL_OCR: bool = True
    
    # KPK-specific OCR
    USE_KPK_TRAINED_DATA: bool = True
    KPK_FONT_PRIORITY: bool = True
    DETECT_KPK_SPECIAL_CHARS: bool = True
    FORESTRY_TERM_CORRECTION: bool = True
    
    # Image preprocessing
    DEFAULT_DPI: int = 300
    MIN_DPI: int = 200
    MAX_DPI: int = 600
    IMAGE_ENHANCEMENT: bool = True
    DENOISE_LEVEL: int = 2  # 0=none, 1=light, 2=medium, 3=aggressive
    DESKEW_ENABLED: bool = True
    DESKEW_MAX_ANGLE: float = 15.0  # degrees
    
    # Adaptive preprocessing
    ADAPTIVE_THRESHOLDING: bool = True
    ADAPTIVE_BLOCK_SIZE: int = 35
    ADAPTIVE_C: int = 10
    
    # Binarization
    BINARIZATION_METHOD: str = 'adaptive'  # 'adaptive', 'otsu', 'sauvola', 'niblack'
    BINARIZATION_THRESHOLD: int = 128
    INVERT_IF_WHITE_TEXT: bool = True
    
    # Page segmentation
    PAGE_SEGMENTATION_MODE: int = 6  # PSM 6: Assume uniform block of text
    OCR_ENGINE_MODE: int = 3  # OEM 3: Default
    
    # Confidence thresholds
    MIN_WORD_CONFIDENCE: int = 60  # 0-100
    MIN_CHAR_CONFIDENCE: int = 40  # 0-100
    REJECT_LOW_CONFIDENCE: bool = False
    CONFIDENCE_SMOOTHING: bool = True
    
    # Text cleaning
    REMOVE_ISOLATED_CHARS: bool = True
    FIX_COMMON_OCR_ERRORS: bool = True
    CORRECT_LEGAL_TERMS: bool = True
    NORMALIZE_WHITESPACE: bool = True
    
    # Performance
    PARALLEL_PROCESSING: bool = False
    MAX_WORKERS: int = 4
    BATCH_SIZE: int = 10
    CACHE_RESULTS: bool = False
    TEMP_DIR: Optional[str] = None
    
    # Output
    PRESERVE_LAYOUT: bool = True
    INCLUDE_CONFIDENCE_SCORES: bool = True
    GENERATE_HOCR: bool = False
    GENERATE_ALTOXML: bool = False
    SAVE_PROCESSED_IMAGES: bool = False
    
    # Error handling
    CONTINUE_ON_ERROR: bool = True
    RETRY_FAILED_PAGES: bool = True
    MAX_RETRIES: int = 2
    FALLBACK_STRATEGIES: List[str] = ['lower_dpi', 'different_psm', 'enhance_more']
    
    # Quality control
    VALIDATE_OCR_OUTPUT: bool = True
    MIN_TEXT_LENGTH_PAGE: int = 50
    MIN_WORDS_PER_PAGE: int = 5
    CHECK_FOR_GARBLED_TEXT: bool = True
    GARBLED_THRESHOLD: float = 0.3

# ============================================================================
# ENUMERATIONS
# ============================================================================

class OCREngineMode(Enum):
    """OCR engine modes"""
    TESSERACT = "tesseract"
    EASYOCR = "easyocr"
    PADDLEOCR = "paddleocr"
    CLOUD_VISION = "cloud_vision"
    AZURE_VISION = "azure_vision"

class ImagePreprocessingMethod(Enum):
    """Image preprocessing methods"""
    NONE = "none"
    BASIC = "basic"  # Grayscale + threshold
    ENHANCED = "enhanced"  # Denoise + deskew
    ADVANCED = "advanced"  # Adaptive + enhancement
    KPK_OPTIMIZED = "kpk_optimized"  # KPK-specific

class OCRQuality(Enum):
    """OCR quality levels"""
    EXCELLENT = "excellent"  # > 90% confidence
    GOOD = "good"          # 70-90% confidence
    FAIR = "fair"          # 50-70% confidence
    POOR = "poor"          # 30-50% confidence
    UNACCEPTABLE = "unacceptable"  # < 30% confidence

class PageType(Enum):
    """Page types for OCR optimization"""
    TEXT_ONLY = "text_only"
    TEXT_WITH_IMAGES = "text_with_images"
    FORMS_TABLES = "forms_tables"
    SCANNED_DOCUMENT = "scanned_document"
    MIXED_CONTENT = "mixed_content"
    HANDWRITTEN = "handwritten"
    LOW_QUALITY_SCAN = "low_quality_scan"

# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class OCRWord:
    """A single recognized word with metadata"""
    text: str
    confidence: float  # 0-100
    bbox: Tuple[int, int, int, int]  # x0, y0, x1, y1
    line_num: int
    word_num: int
    language: Optional[str] = None
    is_corrected: bool = False
    original_text: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

@dataclass
class OCRLine:
    """A line of text with words"""
    line_num: int
    text: str
    confidence: float  # Average confidence
    bbox: Tuple[int, int, int, int]
    words: List[OCRWord]
    is_header: bool = False
    is_footer: bool = False
    alignment: str = "left"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'line_num': self.line_num,
            'text': self.text,
            'confidence': self.confidence,
            'bbox': self.bbox,
            'word_count': len(self.words),
            'is_header': self.is_header,
            'is_footer': self.is_footer,
            'alignment': self.alignment,
        }

@dataclass
class OCRBlock:
    """A block of text (paragraph, heading, etc.)"""
    block_num: int
    block_type: str  # 'paragraph', 'heading', 'list', 'table', 'caption'
    text: str
    confidence: float
    bbox: Tuple[int, int, int, int]
    lines: List[OCRLine]
    page_num: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'block_num': self.block_num,
            'block_type': self.block_type,
            'text': self.text,
            'confidence': self.confidence,
            'bbox': self.bbox,
            'line_count': len(self.lines),
            'page_num': self.page_num,
        }

@dataclass
class OCRPageResult:
    """OCR result for a single page"""
    page_num: int
    page_type: PageType
    text: str
    confidence: float  # Overall confidence
    bbox: Tuple[int, int, int, int]  # Page dimensions
    
    # Detailed data
    words: List[OCRWord]
    lines: List[OCRLine]
    blocks: List[OCRBlock]
    
    # Processing info
    preprocessing_method: ImagePreprocessingMethod
    ocr_config: Dict[str, Any]
    processing_time: float
    dpi: int
    
    # Quality metrics
    quality: OCRQuality
    word_count: int = 0
    char_count: int = 0
    avg_word_confidence: float = 0.0
    low_confidence_words: int = 0
    
    # KPK-specific
    detected_languages: List[str] = field(default_factory=list)
    kpk_terms_found: int = 0
    forestry_terms: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Calculate derived fields"""
        self.word_count = len(self.words)
        self.char_count = sum(len(word.text) for word in self.words)
        
        if self.words:
            self.avg_word_confidence = sum(w.confidence for w in self.words) / len(self.words)
            self.low_confidence_words = sum(1 for w in self.words if w.confidence < 60)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['page_type'] = self.page_type.value
        data['preprocessing_method'] = self.preprocessing_method.value
        data['quality'] = self.quality.value
        data['words'] = [w.to_dict() for w in self.words]
        data['lines'] = [l.to_dict() for l in self.lines]
        data['blocks'] = [b.to_dict() for b in self.blocks]
        return data
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get page statistics"""
        return {
            'page_num': self.page_num,
            'page_type': self.page_type.value,
            'word_count': self.word_count,
            'char_count': self.char_count,
            'confidence': self.confidence,
            'avg_word_confidence': self.avg_word_confidence,
            'low_confidence_words': self.low_confidence_words,
            'quality': self.quality.value,
            'processing_time': self.processing_time,
            'detected_languages': self.detected_languages,
            'kpk_terms_found': self.kpk_terms_found,
        }

# module aliasing for pickle compatibility with dynamic module names
for cls in [OCREngineMode, ImagePreprocessingMethod, OCRQuality, PageType, 
            OCRWord, OCRLine, OCRBlock, OCRPageResult, OCREngineResult]:
    cls.__module__ = "KPKOCREngine"

@dataclass
class OCREngineResult:
    """Complete OCR result for a document"""
    document_path: str
    document_hash: str
    processing_timestamp: datetime
    
    # Results
    pages: List[OCRPageResult]
    full_text: str
    
    # Processing info
    engine_mode: OCREngineMode
    languages_used: List[str]
    preprocessing_summary: Dict[str, int]  # method -> count
    
    # Statistics
    total_pages: int = 0
    total_words: int = 0
    total_chars: int = 0
    avg_confidence: float = 0.0
    processing_time: float = 0.0
    
    # Quality assessment
    overall_quality: OCRQuality = OCRQuality.GOOD
    low_quality_pages: int = 0
    pages_with_errors: int = 0
    
    # KPK-specific
    kpk_pages: int = 0
    forestry_terms_total: int = 0
    mixed_language_pages: int = 0
    
    # Errors and warnings
    processing_errors: List[str] = field(default_factory=list)
    processing_warnings: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Calculate derived fields"""
        self.total_pages = len(self.pages)
        self.total_words = sum(p.word_count for p in self.pages)
        self.total_chars = sum(p.char_count for p in self.pages)
        
        if self.pages:
            self.avg_confidence = sum(p.confidence for p in self.pages) / len(self.pages)
            self.low_quality_pages = sum(1 for p in self.pages if p.quality in [OCRQuality.POOR, OCRQuality.UNACCEPTABLE])
            self.kpk_pages = sum(1 for p in self.pages if p.kpk_terms_found > 0)
            self.forestry_terms_total = sum(p.kpk_terms_found for p in self.pages)
            self.mixed_language_pages = sum(1 for p in self.pages if len(p.detected_languages) > 1)
            
            # Determine overall quality
            confidences = [p.confidence for p in self.pages]
            avg_conf = statistics.mean(confidences) if confidences else 0
            
            if avg_conf >= 90:
                self.overall_quality = OCRQuality.EXCELLENT
            elif avg_conf >= 70:
                self.overall_quality = OCRQuality.GOOD
            elif avg_conf >= 50:
                self.overall_quality = OCRQuality.FAIR
            elif avg_conf >= 30:
                self.overall_quality = OCRQuality.POOR
            else:
                self.overall_quality = OCRQuality.UNACCEPTABLE
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['engine_mode'] = self.engine_mode.value
        data['overall_quality'] = self.overall_quality.value
        data['pages'] = [p.to_dict() for p in self.pages]
        data['processing_timestamp'] = self.processing_timestamp.isoformat()
        return data
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get document statistics"""
        return {
            'document_path': self.document_path,
            'total_pages': self.total_pages,
            'total_words': self.total_words,
            'total_chars': self.total_chars,
            'avg_confidence': self.avg_confidence,
            'overall_quality': self.overall_quality.value,
            'low_quality_pages': self.low_quality_pages,
            'kpk_pages': self.kpk_pages,
            'forestry_terms_total': self.forestry_terms_total,
            'mixed_language_pages': self.mixed_language_pages,
            'processing_time': self.processing_time,
            'engine_mode': self.engine_mode.value,
            'languages_used': self.languages_used,
        }

# ============================================================================
# KPK OCR SPECIALIZED COMPONENTS
# ============================================================================

class KPKOCRCorrector:
    """KPK-specific OCR correction and validation"""
    
    # Common OCR errors in KPK forestry documents
    COMMON_OCR_ERRORS = {
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
    
    # KPK forestry terms that should be preserved
    FORESTRY_TERMS = [
        'deodar', 'chir pine', 'blue pine', 'kail', 'fir', 'spruce',
        'poplar', 'willow', 'sheesham', 'mango', 'neem', 'oak', 'walnut',
        'timber', 'firewood', 'forest', 'forestry', 'compartment',
        'beat', 'range', 'division', 'conservator', 'dfo', 'range officer',
        'beat guard', 'forest guard', 'contractor', 'license', 'permit',
        'auction', 'transit', 'seizure', 'confiscation', 'penalty', 'fine',
        'sapling', 'plantation', 'afforestation', 'deforestation',
        'encroachment', 'violation', 'offence', 'illegal logging',
    ]
    
    # Urdu terms that might appear in mixed documents
    URDU_TERMS = [
        'جنگل', 'درخت', 'لکڑی', 'اشجار', 'تحفظ', 'محکمہ',
        'جنگلات', 'سرکاری', 'غیرقانونی', 'سزا', 'جرمانہ', 'اجازت نامہ',
        'منڈی', 'بولی', 'ٹھیکیدار', 'مشاہدہ', 'رپورٹ', 'درخواست',
    ]
    
    @classmethod
    def correct_common_errors(cls, text: str) -> Tuple[str, List[str]]:
        """Correct common OCR errors in forestry documents"""
        corrections = []
        corrected_text = text
        
        for error, correction in cls.COMMON_OCR_ERRORS.items():
            if error in corrected_text.lower():
                # Use regex for case-insensitive replacement
                pattern = re.compile(re.escape(error), re.IGNORECASE)
                matches = pattern.findall(corrected_text)
                if matches:
                    corrected_text = pattern.sub(correction, corrected_text)
                    corrections.append(f"{error} -> {correction}")
        
        return corrected_text, corrections
    
    @classmethod
    def detect_forestry_terms(cls, text: str) -> List[str]:
        """Detect forestry terms in text"""
        detected = []
        text_lower = text.lower()
        
        for term in cls.FORESTRY_TERMS:
            if term in text_lower:
                detected.append(term)
        
        return detected
    
    @classmethod
    def detect_urdu_text(cls, text: str) -> bool:
        """Detect if text contains Urdu characters"""
        # Urdu Unicode range: U+0600 to U+06FF
        urdu_pattern = re.compile(r'[\u0600-\u06FF]')
        return bool(urdu_pattern.search(text))
    
    @classmethod
    def validate_legal_references(cls, text: str) -> List[str]:
        """Validate and extract legal references"""
        # Patterns for KPK legal references
        patterns = [
            r'Section\s+(\d+[A-Z]?)',
            r'section\s+(\d+[A-Z]?)',
            r'Sec\.\s*(\d+[A-Z]?)',
            r'sec\.\s*(\d+[A-Z]?)',
            r'Article\s+(\d+)',
            r'article\s+(\d+)',
            r'Art\.\s*(\d+)',
            r'art\.\s*(\d+)',
            r'Ordinance\s+(\d{4})',
            r'ordinance\s+(\d{4})',
            r'Act\s+(\d{4})',
            r'act\s+(\d{4})',
            r'S\.R\.O\.\s+(\d+)',
            r'SRO\s+(\d+)',
            r's\.r\.o\.\s+(\d+)',
            r'sro\s+(\d+)',
        ]
        
        references = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                # Format the reference nicely
                if 'section' in pattern.lower():
                    ref = f"Section {match}"
                elif 'article' in pattern.lower():
                    ref = f"Article {match}"
                elif 'ordinance' in pattern.lower():
                    ref = f"Ordinance {match}"
                elif 'act' in pattern.lower():
                    ref = f"Act {match}"
                elif 'sro' in pattern.lower():
                    ref = f"SRO {match}"
                else:
                    ref = match
                
                references.append(ref)
        
        return list(set(references))

class KPKPageAnalyzer:
    """Analyze pages for KPK-specific characteristics"""
    
    @staticmethod
    def detect_page_type(image: np.ndarray) -> PageType:
        """Detect page type for OCR optimization"""
        # Analyze image characteristics
        height, width = image.shape[:2]
        
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # Calculate image statistics
        mean_intensity = np.mean(gray)
        std_intensity = np.std(gray)
        
        # Edge detection for structure analysis
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.sum(edges > 0) / (height * width)
        
        # Detect text regions using contours
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Analyze contour characteristics
        text_contours = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = w / h if h > 0 else 0
            area = w * h
            
            # Text-like contours are typically small and elongated
            if 10 < area < 5000 and 0.1 < aspect_ratio < 10:
                text_contours.append(contour)
        
        text_density = len(text_contours) / (height * width / 10000)  # Contours per 100x100 area
        
        # Determine page type based on characteristics
        if edge_density < 0.01 and text_density < 0.5:
            return PageType.TEXT_ONLY
        elif edge_density > 0.05 and text_density > 2:
            return PageType.FORMS_TABLES
        elif mean_intensity < 100 and std_intensity > 50:
            return PageType.SCANNED_DOCUMENT
        elif mean_intensity > 200 and std_intensity < 20:
            return PageType.LOW_QUALITY_SCAN
        else:
            return PageType.MIXED_CONTENT
    
    @staticmethod
    def detect_languages(text: str) -> List[str]:
        """Detect languages in text"""
        languages = []
        
        # Check for English
        english_chars = len(re.findall(r'[a-zA-Z]', text))
        total_chars = len(text)
        
        if total_chars > 0:
            english_ratio = english_chars / total_chars
            if english_ratio > 0.3:
                languages.append('eng')
        
        # Check for Urdu
        urdu_chars = len(re.findall(r'[\u0600-\u06FF]', text))
        if urdu_chars > 0:
            urdu_ratio = urdu_chars / total_chars
            if urdu_ratio > 0.1:
                languages.append('urd')
        
        return languages

# ============================================================================
# OCR ENGINE
# ============================================================================

class KPKOCREngine:
    """
    Phase 1.5: Advanced KPK Forestry OCR Engine
    Specialized OCR for KPK forestry documents with advanced preprocessing,
    multilingual support, and KPK-specific optimizations.
    """
    
    def __init__(self, 
                 config: Optional[Union[OCRConfig, Dict]] = None,
                 enable_abstention_logging: bool = True,
                 logger: Optional[logging.Logger] = None):
        """
        Initialize KPK OCR Engine.
        
        Args:
            config: Configuration object or dictionary
            enable_abstention_logging: Whether to log abstentions
            logger: Optional logger instance
        """
        
        # Configuration
        if isinstance(config, dict):
            self.config = OCRConfig()
            # Update config from dict
            for key, value in config.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
        else:
            self.config = config or OCRConfig()
            
        # SAFETY: Merge OCRConfig defaults if attributes are missing (e.g. from PipelineConfig)
        defaults = OCRConfig()
        for attr in dir(defaults):
            if not attr.startswith('_') and not hasattr(self.config, attr):
                setattr(self.config, attr, getattr(defaults, attr))
        
        # Setup logging
        self.logger = logger or self._setup_logging()
        
        # Abstention logging
        self.enable_abstention_logging = enable_abstention_logging
        self.abstention_logger = None
        if enable_abstention_logging and PHASE_1_MODULES_AVAILABLE:
            try:
                self.abstention_logger = AbstentionLogger()
            except Exception as e:
                self.logger.warning(f"Could not initialize abstention logger: {e}")
        
        # Set Tesseract command if specified
        if self.config.TESSERACT_CMD:
            pytesseract.pytesseract.tesseract_cmd = self.config.TESSERACT_CMD
        else:
            # Try to auto-detect
            self._auto_detect_tesseract()
        
        # Initialize components
        self.corrector = KPKOCRCorrector()
        self.analyzer = KPKPageAnalyzer()
        
        # KPK trainer integration
        self.kpk_trainer = None
        if KPK_TRAINER_AVAILABLE and self.config.USE_KPK_TRAINED_DATA:
            try:
                self.kpk_trainer = KPKOCRTrainer()
                self.logger.info("KPK OCR trainer integrated")
            except Exception as e:
                self.logger.warning(f"Could not initialize KPK trainer: {e}")
        
        # Create temporary directory
        if not self.config.TEMP_DIR:
            self.temp_dir = tempfile.mkdtemp(prefix="gl_ai_ocr_")
        else:
            self.temp_dir = Path(self.config.TEMP_DIR)
            Path(self.temp_dir).mkdir(parents=True, exist_ok=True)
        
        # Statistics
        self.stats = self._init_statistics()
        
        # Cache
        self._ocr_cache = {}
        self.ocr_cache_dir = Path("e:/GL_AI/data_processed/ocr_cache")
        self.ocr_cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Register module alias for pickle if name exists
        if __name__ in sys.modules:
            sys.modules["KPKOCREngine"] = sys.modules[__name__]
        
        self.logger.info(f"KPKOCREngine initialized with temp dir: {self.temp_dir}, cache: {self.ocr_cache_dir}")
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging"""
        logger = logging.getLogger('KPKOCREngine')
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
    
    def _auto_detect_tesseract(self):
        """Auto-detect Tesseract installation"""
        try:
            # Try default path
            pytesseract.get_tesseract_version()
            self.logger.info("Tesseract auto-detected successfully")
        except Exception:
            # Try common installation paths
            common_paths = [
                r'C:\Program Files\Tesseract-OCR\tesseract.exe',
                r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
                '/usr/bin/tesseract',
                '/usr/local/bin/tesseract',
                '/opt/homebrew/bin/tesseract',
            ]
            
            for path in common_paths:
                if Path(path).exists():
                    pytesseract.pytesseract.tesseract_cmd = path
                    self.logger.info(f"Tesseract found at: {path}")
                    return
            
            self.logger.warning("Tesseract not found. Please install Tesseract-OCR or specify path in config.")
    
    def _init_statistics(self) -> Dict[str, Any]:
        """Initialize statistics structure"""
        return {
            'documents_processed': 0,
            'total_pages_processed': 0,
            'ocr_time_total': 0.0,
            'avg_ocr_time': 0.0,
            
            'page_types': {
                'text_only': 0,
                'text_with_images': 0,
                'forms_tables': 0,
                'scanned_document': 0,
                'low_quality_scan': 0,
                'mixed_content': 0,
            },
            
            'preprocessing_methods': {
                'none': 0,
                'basic': 0,
                'enhanced': 0,
                'advanced': 0,
                'kpk_optimized': 0,
            },
            
            'ocr_quality': {
                'excellent': 0,
                'good': 0,
                'fair': 0,
                'poor': 0,
                'unacceptable': 0,
            },
            
            'language_usage': {
                'english_only': 0,
                'urdu_only': 0,
                'mixed_english_urdu': 0,
                'other_languages': 0,
            },
            
            'kpk_metrics': {
                'pages_with_kpk_terms': 0,
                'forestry_terms_total': 0,
                'corrected_errors': 0,
                'legal_references_found': 0,
            },
            
            'performance': {
                'fastest_page': float('inf'),
                'slowest_page': 0.0,
                'ocr_times': [],
            },
            
            'issues': {
                'low_confidence_pages': 0,
                'failed_pages': 0,
                'retry_attempts': 0,
            },
        }
    
    def process_document(self, 
                        document_path: Union[str, Path],
                        document_type: Optional[str] = None,
                        output_dir: Optional[Union[str, Path]] = None) -> OCREngineResult:
        """
        Main entry point for OCR processing of a document.
        
        Args:
            document_path: Path to PDF or image file
            document_type: Optional document type for optimization
            output_dir: Optional directory for saving processed images
        
        Returns:
            OCREngineResult with OCR data
        """
        import time
        start_time = time.time()
        
        try:
            document_path = Path(document_path)
            
            # Generate cache key
            cache_key = self._generate_cache_key(document_path)
            
            # Check cache
            if self.config.CACHE_RESULTS and cache_key in self._ocr_cache:
                self.logger.info(f"Returning cached OCR for {document_path}")
                return self._ocr_cache[cache_key]
            
            self.logger.info(f"Processing document with OCR: {document_path}")
            
            # Setup output directory
            if output_dir:
                output_dir = Path(output_dir)
                output_dir.mkdir(parents=True, exist_ok=True)
                processed_dir = output_dir / "processed_images"
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                processed_dir = Path(self.temp_dir) / f"processed_{timestamp}"
            
            processed_dir.mkdir(parents=True, exist_ok=True)
            
            # Determine file type and process accordingly
            ext = document_path.suffix.lower()
            
            if ext == '.pdf':
                result = self._process_pdf(document_path, processed_dir, document_type)
            elif ext in ['.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp']:
                result = self._process_image(document_path, processed_dir, document_type)
            elif ext in ['.json', '.csv', '.xlsx']:
                result = self._process_structured(document_path)
            else:
                raise ValueError(f"Unsupported file format: {ext}")
            
            # Cache result
            if self.config.CACHE_RESULTS:
                self._ocr_cache[cache_key] = result
            
            # Update statistics
            processing_time = time.time() - start_time
            result.processing_time = processing_time
            self._update_statistics(result, processing_time)
            
            # Log abstention if OCR quality is poor
            if (self.enable_abstention_logging and self.abstention_logger and 
                result.overall_quality in [OCRQuality.POOR, OCRQuality.UNACCEPTABLE]):
                
                self._log_ocr_abstention(result, document_path)
            
            self.logger.info(
                f"OCR processing complete: {document_path} - "
                f"Pages: {len(result.pages)}, "
                f"Words: {result.total_words}, "
                f"Quality: {result.overall_quality.value}, "
                f"Time: {processing_time:.2f}s"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"OCR processing failed for {document_path}: {e}")
            
            # Create minimal result with error
            return self._create_error_result(document_path, str(e))
    
    def process_image_data(self, 
                          image_data: Union[Image.Image, np.ndarray, bytes],
                          page_num: int = 1,
                          page_type: Optional[PageType] = None) -> OCRPageResult:
        """
        Process a single image with OCR.
        
        Args:
            image_data: PIL Image, numpy array, or bytes
            page_num: Page number for metadata
            page_type: Optional page type for optimization
        
        Returns:
            OCRPageResult for the image
        """
        import time
        start_time = time.time()
        
        try:
            # Convert input to PIL Image
            if isinstance(image_data, Image.Image):
                pil_image = image_data
            elif isinstance(image_data, np.ndarray):
                if len(image_data.shape) == 2:
                    pil_image = Image.fromarray(image_data)
                else:
                    pil_image = Image.fromarray(cv2.cvtColor(image_data, cv2.COLOR_BGR2RGB))
            elif isinstance(image_data, bytes):
                pil_image = Image.open(io.BytesIO(image_data))
            else:
                raise ValueError(f"Unsupported image data type: {type(image_data)}")
            
            # Analyze page if type not provided
            if not page_type:
                np_image = np.array(pil_image)
                page_type = self.analyzer.detect_page_type(np_image)
            
            # Determine preprocessing method
            preprocessing = self._select_preprocessing_method(page_type)
            
            # Preprocess image
            processed_image, preprocessing_info = self._preprocess_image(pil_image, preprocessing)
            
            # Perform OCR
            ocr_data = self._perform_ocr(processed_image, page_type)
            
            # Extract structured data
            words, lines, blocks = self._extract_structured_data(ocr_data, processed_image)
            
            # Combine text
            full_text = ocr_data['text']
            
            # Apply KPK-specific corrections
            corrected_text, corrections = self.corrector.correct_common_errors(full_text)
            
            # Detect languages
            detected_languages = self.analyzer.detect_languages(corrected_text)
            
            # Detect forestry terms
            forestry_terms = self.corrector.detect_forestry_terms(corrected_text)
            
            # Validate legal references
            legal_references = self.corrector.validate_legal_references(corrected_text)
            
            # Calculate confidence
            confidence = ocr_data.get('confidence', 0.0)
            
            # Determine quality
            quality = self._determine_quality(confidence, len(words))
            
            # Update word objects with correction info
            if corrections:
                self._apply_corrections_to_words(words, full_text, corrected_text)
            
            processing_time = time.time() - start_time
            
            # Create page result
            page_result = OCRPageResult(
                page_num=page_num,
                page_type=page_type,
                text=corrected_text,
                confidence=confidence,
                bbox=(0, 0, pil_image.width, pil_image.height),
                words=words,
                lines=lines,
                blocks=blocks,
                preprocessing_method=preprocessing,
                ocr_config=ocr_data.get('config', {}),
                processing_time=processing_time,
                dpi=preprocessing_info.get('dpi', self.config.DEFAULT_DPI),
                quality=quality,
                detected_languages=detected_languages,
                kpk_terms_found=len(forestry_terms),
                forestry_terms=forestry_terms,
            )
            
            return page_result
            
        except Exception as e:
            self.logger.error(f"Failed to process image for page {page_num}: {e}")
            
            # Create error page result
            return self._create_error_page_result(page_num, str(e))
    
    def _generate_cache_key(self, document_path: Path) -> str:
        """Generate cache key for document"""
        try:
            # Use file hash and modification time
            stat = document_path.stat()
            file_hash = hashlib.md5(f"{document_path}_{stat.st_mtime}".encode()).hexdigest()[:16]
            return f"ocr_{file_hash}"
        except:
            return f"ocr_{hashlib.md5(str(document_path).encode()).hexdigest()[:16]}"
    
    def _process_pdf(self, pdf_path: Path, output_dir: Path, document_type: Optional[str]) -> OCREngineResult:
        """Process PDF document using PyMuPDF (fitz)"""
        import io  # Ensure io is available
        pages = []
        full_text_parts = []
        preprocessing_summary = defaultdict(int)
        
        try:
            # Open PDF with PyMuPDF
            doc = fitz.open(pdf_path)
            doc_key = self._generate_cache_key(pdf_path)
            self.logger.info(f"Processing PDF {pdf_path.name} ({len(doc)} pages) with persistent cache key: {doc_key}")
            
            # Process each page
            for i in range(len(doc)):
                page_num = i + 1
                page_result = None
                
                # Persistent Cache Check
                cache_file = self.ocr_cache_dir / f"{doc_key}_p{page_num}.pkl"
                if cache_file.exists():
                    try:
                        with open(cache_file, 'rb') as f:
                            page_result = pickle.load(f)
                        self.logger.info(f"Loaded cached OCR for {pdf_path.name} page {page_num}")
                    except Exception as ce:
                        self.logger.warning(f"Failed to load cache for page {page_num}: {ce}")
                
                if not page_result:
                    try:
                        # Render page to image
                        page = doc.load_page(i)
                        # Use higher DPI for better OCR
                        pix = page.get_pixmap(dpi=self.config.DEFAULT_DPI)
                        
                        # Convert to PIL Image
                        img_data = pix.tobytes("png")
                        pil_image = Image.open(io.BytesIO(img_data))
                        
                        # Process page
                        page_result = self.process_image_data(pil_image, page_num)
                        
                        # Save to Persistent Cache
                        try:
                            with open(cache_file, 'wb') as f:
                                pickle.dump(page_result, f)
                        except Exception as ce:
                            self.logger.warning(f"Failed to save cache for page {page_num}: {ce}")
                            
                    except Exception as e:
                        self.logger.warning(f"Failed to process page {page_num}: {e}")
                        if not self.config.CONTINUE_ON_ERROR:
                            raise
                        
                        # Add error page
                        page_result = self._create_error_page_result(page_num, str(e))
                
                pages.append(page_result)
                full_text_parts.append(page_result.text)
                
                # Update preprocessing summary
                method = page_result.preprocessing_method.value
                preprocessing_summary[method] += 1
                self.stats['total_pages_processed'] += 1

                # Retry failed pages if enabled (only if not from cache or if quality still poor)
                if (self.config.RETRY_FAILED_PAGES and 
                    page_result.quality in [OCRQuality.POOR, OCRQuality.UNACCEPTABLE] and
                    self.stats['issues']['retry_attempts'] < self.config.MAX_RETRIES):
                    
                    self.logger.info(f"Retrying page {page_num} with different settings")
                    # Need to regenerate PIL image for retry since previous might be closed/modified
                    # Re-render at same DPI (retry logic might change DPI internally)
                    retry_result = self._retry_page(pil_image, page_num)
                    if retry_result and retry_result.quality.value > page_result.quality.value:
                        pages[-1] = retry_result
                        full_text_parts[-1] = retry_result.text
                        self.stats['issues']['retry_attempts'] += 1
            
            # Close document
            doc.close()
            
            # Combine full text
            full_text = "\n\n".join(full_text_parts)
            
            # Determine languages used
            all_languages = []
            for page in pages:
                all_languages.extend(page.detected_languages)
            languages_used = list(set(all_languages)) or ['eng']  # Default to English
            
        except Exception as e:
            self.logger.error(f"Failed to process PDF {pdf_path}: {e}")
            raise
        
        # Create result
        result = OCREngineResult(
            document_path=str(pdf_path),
            document_hash=hashlib.md5(str(pdf_path).encode()).hexdigest()[:16],
            processing_timestamp=datetime.now(),
            pages=pages,
            full_text=full_text,
            engine_mode=OCREngineMode.TESSERACT,
            languages_used=languages_used,
            preprocessing_summary=dict(preprocessing_summary),
        )
        
        return result
    
    def _process_image(self, image_path: Path, output_dir: Path, document_type: Optional[str]) -> OCREngineResult:
        """Process single image file"""
        try:
            # Open image
            pil_image = Image.open(image_path)
            
            # Process image
            page_result = self.process_image_data(pil_image, 1)
            
            # Clean up
            pil_image.close()
            
            # Create single-page result
            result = OCREngineResult(
                document_path=str(image_path),
                document_hash=hashlib.md5(str(image_path).encode()).hexdigest()[:16],
                processing_timestamp=datetime.now(),
                pages=[page_result],
                full_text=page_result.text,
                engine_mode=OCREngineMode.TESSERACT,
                languages_used=page_result.detected_languages or ['eng'],
                preprocessing_summary={page_result.preprocessing_method.value: 1},
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to process image {image_path}: {e}")
            raise

    def _process_structured(self, file_path: Path) -> OCREngineResult:
        """Process structured files (JSON, CSV, XLSX) without OCR"""
        ext = file_path.suffix.lower()
        full_text = ""
        
        try:
            if ext == '.json':
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    full_text = json.dumps(data, indent=2, ensure_ascii=False)
            elif ext == '.csv':
                import csv
                rows = []
                with open(file_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    for row in reader:
                        rows.append(" | ".join(row))
                full_text = "\n".join(rows)
            elif ext == '.xlsx':
                import pandas as pd
                df = pd.read_excel(file_path)
                full_text = df.to_string()
        except Exception as e:
            self.logger.error(f"Structured parse failed for {file_path}: {e}")
            full_text = f"[Structured Parse Error: {e}]"

        # Create a mock page result
        page_result = OCRPageResult(
            page_num=1,
            page_type=PageType.TEXT_ONLY,
            text=full_text,
            confidence=100.0,
            bbox=(0, 0, 0, 0),
            words=[],
            lines=[],
            blocks=[],
            preprocessing_method=ImagePreprocessingMethod.NONE,
            ocr_config={},
            processing_time=0.1,
            dpi=0,
            quality=OCRQuality.EXCELLENT,
            detected_languages=['eng'],
            kpk_terms_found=0,
            forestry_terms=[],
        )
        
        return OCREngineResult(
            document_path=str(file_path),
            document_hash=hashlib.md5(str(file_path).encode()).hexdigest()[:16],
            processing_timestamp=datetime.now(),
            pages=[page_result],
            full_text=full_text,
            engine_mode=OCREngineMode.TESSERACT,
            languages_used=['eng'],
            preprocessing_summary={"none": 1},
        )
    
    def _retry_page(self, image: Image.Image, page_num: int) -> Optional[OCRPageResult]:
        """Retry OCR on a page with different settings"""
        retry_strategies = getattr(self.config, 'FALLBACK_STRATEGIES', ['lower_dpi', 'different_psm', 'enhance_more'])
        
        for strategy in retry_strategies:
            try:
                if strategy == 'lower_dpi':
                    # Resize to lower DPI
                    width, height = image.size
                    new_size = (int(width * 0.7), int(height * 0.7))
                    resized_image = image.resize(new_size, Image.Resampling.LANCZOS)
                    return self.process_image_data(resized_image, page_num)
                
                elif strategy == 'different_psm':
                    # Use different page segmentation mode
                    # Save current config
                    original_psm = self.config.PAGE_SEGMENTATION_MODE
                    self.config.PAGE_SEGMENTATION_MODE = 3  # PSM 3: Fully automatic
                    result = self.process_image_data(image, page_num)
                    self.config.PAGE_SEGMENTATION_MODE = original_psm
                    return result
                
                elif strategy == 'enhance_more':
                    # Apply aggressive enhancement
                    enhanced = self._aggressive_enhancement(image)
                    return self.process_image_data(enhanced, page_num)
                    
            except Exception as e:
                self.logger.debug(f"Retry strategy {strategy} failed: {e}")
                continue
        
        return None
    
    def _select_preprocessing_method(self, page_type: PageType) -> ImagePreprocessingMethod:
        """Select preprocessing method based on page type"""
        if not self.config.IMAGE_ENHANCEMENT:
            return ImagePreprocessingMethod.NONE
        
        if page_type == PageType.LOW_QUALITY_SCAN:
            return ImagePreprocessingMethod.ADVANCED
        elif page_type == PageType.SCANNED_DOCUMENT:
            return ImagePreprocessingMethod.ENHANCED
        elif page_type == PageType.FORMS_TABLES:
            return ImagePreprocessingMethod.KPK_OPTIMIZED
        elif page_type == PageType.TEXT_ONLY:
            return ImagePreprocessingMethod.BASIC
        else:
            return ImagePreprocessingMethod.ENHANCED
    
    def _preprocess_image(self, image: Image.Image, 
                         method: ImagePreprocessingMethod) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Preprocess image based on selected method"""
        info = {'method': method.value, 'dpi': self.config.DEFAULT_DPI}
        
        # Convert to numpy array
        np_image = np.array(image)
        
        if method == ImagePreprocessingMethod.NONE:
            # Just convert to grayscale
            if len(np_image.shape) == 3:
                gray = cv2.cvtColor(np_image, cv2.COLOR_RGB2GRAY)
            else:
                gray = np_image
            return gray, info
        
        # Start with grayscale
        if len(np_image.shape) == 3:
            gray = cv2.cvtColor(np_image, cv2.COLOR_RGB2GRAY)
        else:
            gray = np_image
        
        # Apply method-specific preprocessing
        if method == ImagePreprocessingMethod.BASIC:
            # Basic: thresholding
            _, processed = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
        elif method == ImagePreprocessingMethod.ENHANCED:
            # Enhanced: denoise + deskew + threshold
            # Denoise
            denoised = cv2.fastNlMeansDenoising(gray, h=10)
            
            # Deskew if enabled
            if self.config.DESKEW_ENABLED:
                deskewed = self._deskew_image(denoised)
            else:
                deskewed = denoised
            
            # Threshold
            _, processed = cv2.threshold(deskewed, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
        elif method == ImagePreprocessingMethod.ADVANCED:
            # Advanced: adaptive thresholding + enhancement
            # Denoise aggressively
            denoised = cv2.fastNlMeansDenoising(gray, h=20)
            
            # Enhance contrast
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(denoised)
            
            # Adaptive thresholding
            if self.config.ADAPTIVE_THRESHOLDING:
                processed = cv2.adaptiveThreshold(
                    enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY, self.config.ADAPTIVE_BLOCK_SIZE, self.config.ADAPTIVE_C
                )
            else:
                _, processed = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
        elif method == ImagePreprocessingMethod.KPK_OPTIMIZED:
            # KPK optimized for forestry documents
            # Special handling for stamps, forms, tables
            
            # Enhance for stamp/ink detection
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Invert if needed (white text on dark background)
            if self.config.INVERT_IF_WHITE_TEXT:
                white_pixels = np.sum(binary == 255)
                black_pixels = np.sum(binary == 0)
                if white_pixels > black_pixels * 1.5:
                    binary = cv2.bitwise_not(binary)
            
            processed = binary
            
        else:
            # Default to enhanced
            denoised = cv2.fastNlMeansDenoising(gray, h=10)
            _, processed = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        info['processed_shape'] = processed.shape
        return processed, info
    
    def _deskew_image(self, image: np.ndarray) -> np.ndarray:
        """Deskew image using Hough transform"""
        # Threshold image
        _, binary = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Find contours
        contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        
        # Get contour angles
        angles = []
        for contour in contours:
            if len(contour) > 5:  # Need at least 5 points for ellipse fitting
                ellipse = cv2.fitEllipse(contour)
                angle = ellipse[2]
                if angle > 90:
                    angle = angle - 180
                angles.append(angle)
        
        if not angles:
            return image
        
        # Get median angle
        median_angle = np.median(angles)
        
        # Limit angle
        if abs(median_angle) > self.config.DESKEW_MAX_ANGLE:
            median_angle = 0
        
        # Rotate image
        if abs(median_angle) > 0.5:  # Only rotate if significant
            (h, w) = image.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
            deskewed = cv2.warpAffine(image, M, (w, h), 
                                     flags=cv2.INTER_CUBIC, 
                                     borderMode=cv2.BORDER_REPLICATE)
            return deskewed
        
        return image
    
    def _aggressive_enhancement(self, image: Image.Image) -> Image.Image:
        """Apply aggressive enhancement for difficult images"""
        # Convert to numpy
        np_image = np.array(image)
        
        if len(np_image.shape) == 3:
            gray = cv2.cvtColor(np_image, cv2.COLOR_RGB2GRAY)
        else:
            gray = np_image
        
        # Multiple enhancement steps
        # 1. Denoise aggressively
        denoised = cv2.fastNlMeansDenoising(gray, h=30)
        
        # 2. CLAHE for contrast
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(denoised)
        
        # 3. Sharpening
        kernel = np.array([[-1, -1, -1],
                          [-1,  9, -1],
                          [-1, -1, -1]])
        sharpened = cv2.filter2D(enhanced, -1, kernel)
        
        # 4. Threshold with Sauvola method
        window_size = 25
        thresh_sauvola = cv2.ximgproc.niBlackThreshold(
            sharpened, 255, cv2.THRESH_BINARY, window_size,
            k=0.2, binarizationMethod=cv2.ximgproc.BINARIZATION_SAUVOLA
        )
        
        # Convert back to PIL
        return Image.fromarray(thresh_sauvola)
    
    def _perform_ocr(self, image: np.ndarray, page_type: PageType) -> Dict[str, Any]:
        """Perform OCR on preprocessed image"""
        # Build Tesseract configuration
        config = self._build_tesseract_config(page_type)
        
        # Perform OCR with detailed output
        data = pytesseract.image_to_data(
            image,
            config=config,
            output_type=pytesseract.Output.DICT
        )
        
        # Extract text
        text = pytesseract.image_to_string(image, config=config)
        
        # Calculate confidence
        confidences = [float(conf) for conf in data['conf'] if conf != '-1']
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        return {
            'text': text,
            'data': data,
            'confidence': avg_confidence,
            'config': config,
        }
    
    def _build_tesseract_config(self, page_type: PageType) -> str:
        """Build Tesseract configuration string"""
        config_parts = []
        
        # OCR Engine mode
        config_parts.append(f'--oem {self.config.OCR_ENGINE_MODE}')
        
        # Page segmentation mode
        psm = self._determine_psm(page_type)
        config_parts.append(f'--psm {psm}')
        
        # Languages
        if self.config.ENABLE_MULTILINGUAL_OCR:
            langs = [self.config.PRIMARY_LANGUAGE] + self.config.SECONDARY_LANGUAGES
            lang_str = '+'.join(langs)
        else:
            lang_str = self.config.PRIMARY_LANGUAGE
        
        config_parts.append(f'-l {lang_str}')
        
        # Confidence threshold
        if self.config.REJECT_LOW_CONFIDENCE:
            config_parts.append(f'--user-words {self.config.MIN_WORD_CONFIDENCE}')
        
        # KPK-specific configurations
        if self.config.USE_KPK_TRAINED_DATA and self.kpk_trainer:
            # Add KPK-trained data path if available
            pass
        
        # Additional parameters for better accuracy
        config_parts.append('-c preserve_interword_spaces=1')
        config_parts.append('-c tessedit_char_whitelist=abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.,;:!?()-"\' \t\n\u0600-\u06FF')
        
        return ' '.join(config_parts)
    
    def _determine_psm(self, page_type: PageType) -> int:
        """Determine page segmentation mode based on page type"""
        if page_type == PageType.FORMS_TABLES:
            return 6  # Assume uniform block of text
        elif page_type == PageType.TEXT_ONLY:
            return 3  # Fully automatic page segmentation
        elif page_type == PageType.SCANNED_DOCUMENT:
            return 4  # Assume single column of text of variable sizes
        else:
            return 6  # Default
    
    def _extract_structured_data(self, ocr_data: Dict[str, Any], 
                                image: np.ndarray) -> Tuple[List[OCRWord], List[OCRLine], List[OCRBlock]]:
        """Extract structured data from OCR output"""
        data = ocr_data['data']
        
        # Extract words
        words = []
        current_line = None
        lines_dict = {}
        
        for i in range(len(data['level'])):
            if data['level'][i] == 5:  # Word level
                word = OCRWord(
                    text=data['text'][i],
                    confidence=float(data['conf'][i]) if data['conf'][i] != '-1' else 0.0,
                    bbox=(data['left'][i], data['top'][i], 
                          data['left'][i] + data['width'][i], 
                          data['top'][i] + data['height'][i]),
                    line_num=data['line_num'][i],
                    word_num=data['word_num'][i],
                )
                words.append(word)
                
                # Group by line
                line_num = data['line_num'][i]
                if line_num not in lines_dict:
                    lines_dict[line_num] = []
                lines_dict[line_num].append(word)
        
        # Create lines
        lines = []
        for line_num, line_words in sorted(lines_dict.items()):
            if not line_words:
                continue
            
            # Calculate line bbox
            x0 = min(w.bbox[0] for w in line_words)
            y0 = min(w.bbox[1] for w in line_words)
            x1 = max(w.bbox[2] for w in line_words)
            y1 = max(w.bbox[3] for w in line_words)
            
            line_text = ' '.join(w.text for w in line_words)
            avg_confidence = sum(w.confidence for w in line_words) / len(line_words)
            
            line = OCRLine(
                line_num=line_num,
                text=line_text,
                confidence=avg_confidence,
                bbox=(x0, y0, x1, y1),
                words=line_words,
            )
            lines.append(line)
        
        # Group lines into blocks (simple paragraph detection)
        blocks = self._group_lines_into_blocks(lines)
        
        return words, lines, blocks
    
    def _group_lines_into_blocks(self, lines: List[OCRLine]) -> List[OCRBlock]:
        """Group lines into logical blocks (paragraphs, headings, etc.)"""
        if not lines:
            return []
        
        blocks = []
        current_block = []
        block_num = 1
        
        for i, line in enumerate(lines):
            if not current_block:
                current_block.append(line)
                continue
            
            # Check if this line belongs to current block
            prev_line = current_block[-1]
            
            # Calculate vertical gap
            gap = line.bbox[1] - prev_line.bbox[3]
            
            # Check horizontal alignment (roughly)
            x_overlap = (line.bbox[0] < prev_line.bbox[2] and line.bbox[2] > prev_line.bbox[0])
            
            # Determine block type (simple heuristic)
            is_same_block = gap < 50 and x_overlap  # Small vertical gap and horizontal overlap
            
            if is_same_block:
                current_block.append(line)
            else:
                # Create block from current lines
                block = self._create_block_from_lines(current_block, block_num)
                if block:
                    blocks.append(block)
                    block_num += 1
                current_block = [line]
        
        # Add last block
        if current_block:
            block = self._create_block_from_lines(current_block, block_num)
            if block:
                blocks.append(block)
        
        return blocks
    
    def _create_block_from_lines(self, lines: List[OCRLine], block_num: int) -> Optional[OCRBlock]:
        """Create OCRBlock from lines"""
        if not lines:
            return None
        
        # Calculate block bbox
        x0 = min(l.bbox[0] for l in lines)
        y0 = min(l.bbox[1] for l in lines)
        x1 = max(l.bbox[2] for l in lines)
        y1 = max(l.bbox[3] for l in lines)
        
        # Combine text
        block_text = '\n'.join(l.text for l in lines)
        
        # Calculate average confidence
        avg_confidence = sum(l.confidence for l in lines) / len(lines)
        
        # Determine block type
        block_type = self._determine_block_type(lines)
        
        # Use first line's page number
        page_num = 1  # Default, would need to be passed in real implementation
        
        return OCRBlock(
            block_num=block_num,
            block_type=block_type,
            text=block_text,
            confidence=avg_confidence,
            bbox=(x0, y0, x1, y1),
            lines=lines,
            page_num=page_num,
        )
    
    def _determine_block_type(self, lines: List[OCRLine]) -> str:
        """Determine block type based on line characteristics"""
        if not lines:
            return 'paragraph'
        
        # Check if it's a heading
        if len(lines) == 1:
            line = lines[0]
            text = line.text.strip()
            
            # Heading indicators
            heading_indicators = [
                len(text) < 100,  # Short text
                text.isupper(),  # All caps
                text.endswith(':'),  # Ends with colon
                re.match(r'^\d+\.', text),  # Numbered
                re.match(r'^[A-Z]\.', text),  # Letter with dot
            ]
            
            if any(heading_indicators):
                return 'heading'
        
        # Check if it's a list
        if len(lines) <= 5:
            list_indicators = 0
            for line in lines:
                text = line.text.strip()
                if (re.match(r'^\d+\.', text) or 
                    re.match(r'^[•\-*]', text) or
                    re.match(r'^[a-z]\.', text)):
                    list_indicators += 1
            
            if list_indicators >= len(lines) * 0.5:  # Majority are list items
                return 'list'
        
        # Default to paragraph
        return 'paragraph'
    
    def _apply_corrections_to_words(self, words: List[OCRWord], original_text: str, corrected_text: str):
        """Apply corrections to word objects based on text corrections"""
        # This is a simplified implementation
        # In production, you'd map corrections to specific words
        
        for word in words:
            # Check if word needs correction
            original_word = word.text
            # Look for corrections in the common errors dictionary
            for error, correction in self.corrector.COMMON_OCR_ERRORS.items():
                if error in original_word.lower():
                    word.is_corrected = True
                    word.original_text = original_word
                    # Simple replacement (would need more sophisticated in production)
                    word.text = word.text.replace(error, correction)
                    break
    
    def _determine_quality(self, confidence: float, word_count: int) -> OCRQuality:
        """Determine OCR quality based on confidence and other factors"""
        if confidence >= 90:
            return OCRQuality.EXCELLENT
        elif confidence >= 70:
            return OCRQuality.GOOD
        elif confidence >= 50:
            return OCRQuality.FAIR
        elif confidence >= 30:
            return OCRQuality.POOR
        else:
            return OCRQuality.UNACCEPTABLE
    
    def _create_error_page_result(self, page_num: int, error_message: str) -> OCRPageResult:
        """Create error page result"""
        return OCRPageResult(
            page_num=page_num,
            page_type=PageType.TEXT_ONLY,
            text=f"[OCR Error: {error_message}]",
            confidence=0.0,
            bbox=(0, 0, 100, 100),
            words=[],
            lines=[],
            blocks=[],
            preprocessing_method=ImagePreprocessingMethod.NONE,
            ocr_config={},
            processing_time=0.0,
            dpi=self.config.DEFAULT_DPI,
            quality=OCRQuality.UNACCEPTABLE,
        )
    
    def _update_statistics(self, result: OCREngineResult, processing_time: float):
        """Update OCR statistics"""
        self.stats['documents_processed'] += 1
        self.stats['ocr_time_total'] += processing_time
        
        for page in result.pages:
            # Update page types
            page_type = page.page_type.value
            if page_type in self.stats['page_types']:
                self.stats['page_types'][page_type] += 1
            
            # Update preprocessing methods
            method = page.preprocessing_method.value
            if method in self.stats['preprocessing_methods']:
                self.stats['preprocessing_methods'][method] += 1
            
            # Update OCR quality
            quality = page.quality.value
            if quality in self.stats['ocr_quality']:
                self.stats['ocr_quality'][quality] += 1
            
            # Update language usage
            langs = page.detected_languages
            if len(langs) == 1:
                if 'eng' in langs:
                    self.stats['language_usage']['english_only'] += 1
                elif 'urd' in langs:
                    self.stats['language_usage']['urdu_only'] += 1
                else:
                    self.stats['language_usage']['other_languages'] += 1
            elif len(langs) > 1:
                self.stats['language_usage']['mixed_english_urdu'] += 1
            
            # Update KPK metrics
            if page.kpk_terms_found > 0:
                self.stats['kpk_metrics']['pages_with_kpk_terms'] += 1
            self.stats['kpk_metrics']['forestry_terms_total'] += page.kpk_terms_found
            
            # Update performance
            perf = self.stats['performance']
            perf['ocr_times'].append(page.processing_time)
            perf['fastest_page'] = min(perf['fastest_page'], page.processing_time)
            perf['slowest_page'] = max(perf['slowest_page'], page.processing_time)
        
        # Calculate averages
        total_docs = self.stats['documents_processed']
        if total_docs > 0:
            self.stats['avg_ocr_time'] = self.stats['ocr_time_total'] / total_docs
    
    def _log_ocr_abstention(self, result: OCREngineResult, document_path: Path):
        """Log abstention for poor OCR quality"""
        if self.enable_abstention_logging and self.abstention_logger:
            try:
                context = create_abstention_context(
                    stage=PipelineStage.OCR_PROCESSING,
                    component="KPKOCREngine",
                    document_path=str(document_path),
                    reason="poor_ocr_quality",
                    details={
                        'overall_quality': result.overall_quality.value,
                        'avg_confidence': result.avg_confidence,
                        'low_quality_pages': result.low_quality_pages,
                        'total_pages': result.total_pages,
                        'languages_used': result.languages_used,
                    }
                )
                
                self.abstention_logger.log_abstention(
                    abstention_type=AbstentionType.OCR_ISSUE,
                    severity=AbstentionSeverity.MEDIUM,
                    context=context,
                    suggested_action="Manual OCR review or use better quality scans",
                    confidence=1.0 - (result.avg_confidence / 100),
                    component_state=result.to_dict(),
                )
                
                self.logger.info(f"Logged OCR abstention for {document_path}")
                
            except Exception as e:
                self.logger.warning(f"Failed to log OCR abstention: {e}")
    
    def _create_error_result(self, document_path: Path, error_message: str) -> OCREngineResult:
        """Create error result when processing fails"""
        return OCREngineResult(
            document_path=str(document_path),
            document_hash=hashlib.md5(str(document_path).encode()).hexdigest()[:16],
            processing_timestamp=datetime.now(),
            pages=[],
            full_text=f"[OCR Processing Error: {error_message}]",
            engine_mode=OCREngineMode.TESSERACT,
            languages_used=['eng'],
            preprocessing_summary={},
            overall_quality=OCRQuality.UNACCEPTABLE,
            processing_errors=[error_message],
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get current OCR statistics"""
        stats = self.stats.copy()
        
        # Calculate derived statistics
        total_processed = stats['documents_processed']
        if total_processed > 0:
            stats['avg_ocr_time'] = stats['ocr_time_total'] / total_processed
            
            # Calculate percentages
            total_pages = sum(stats['page_types'].values())
            if total_pages > 0:
                for key in stats['page_types']:
                    count = stats['page_types'][key]
                    stats['page_types'][f'{key}_pct'] = count / total_pages * 100
            
            # Performance summary
            perf = stats['performance']
            if perf['ocr_times']:
                perf['avg_page_time'] = sum(perf['ocr_times']) / len(perf['ocr_times'])
            else:
                perf['avg_page_time'] = 0.0
                perf['fastest_page'] = 0.0
        
        return stats
    
    def cleanup_temp_files(self, older_than_days: int = 1):
        """Clean up temporary files older than specified days"""
        import time
        current_time = time.time()
        cutoff = current_time - (older_than_days * 24 * 60 * 60)
        
        temp_path = Path(self.temp_dir)
        if not temp_path.exists():
            return
        
        deleted_count = 0
        for file_path in temp_path.rglob('*'):
            if file_path.is_file():
                try:
                    file_age = current_time - file_path.stat().st_mtime
                    if file_age > cutoff:
                        file_path.unlink()
                        deleted_count += 1
                except Exception as e:
                    self.logger.debug(f"Failed to delete {file_path}: {e}")
        
        self.logger.info(f"Cleaned up {deleted_count} temporary files older than {older_than_days} days")

# ============================================================================
# SIMPLIFIED INTERFACE (for backward compatibility)
# ============================================================================

class SimplifiedKPKOCREngine:
    """
    Simplified interface for backward compatibility.
    Uses the full KPKOCREngine internally.
    """
    
    def __init__(self, tesseract_cmd: Optional[str] = None):
        config = OCRConfig()
        if tesseract_cmd:
            config.TESSERACT_CMD = tesseract_cmd
        
        self.engine = KPKOCREngine(config=config, enable_abstention_logging=False)
    
    def process_document(self, file_path: str) -> Dict[str, Any]:
        """Legacy interface for processing documents"""
        try:
            result = self.engine.process_document(file_path)
            
            # Convert to legacy format
            pages = []
            full_text = []
            
            for page in result.pages:
                page_info = {
                    "page_number": page.page_num,
                    "text": page.text,
                    "confidence": page.confidence
                }
                pages.append(page_info)
                full_text.append(page.text)
            
            return {
                "file_path": file_path,
                "text": "\n".join(full_text),
                "pages": pages,
                "metadata": {
                    "total_pages": len(pages),
                    "method": "ocr_pdf" if Path(file_path).suffix.lower() == '.pdf' else "ocr_image",
                    "quality": result.overall_quality.value,
                    "avg_confidence": result.avg_confidence,
                }
            }
            
        except Exception as e:
            return {"error": str(e), "file_path": file_path}
    
    def extract_text_from_image(self, image_path: str) -> Dict[str, Any]:
        """Legacy interface for image OCR"""
        try:
            result = self.engine.process_document(image_path)
            
            if result.pages:
                page = result.pages[0]
                return {
                    "file_path": image_path,
                    "text": page.text,
                    "confidence": page.confidence,
                    "metadata": {
                        "method": "ocr_image",
                        "quality": page.quality.value,
                    }
                }
            else:
                return {"error": "No OCR result", "file_path": image_path}
                
        except Exception as e:
            return {"error": str(e), "file_path": image_path}

# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    """Main function for standalone testing"""
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description="KPK OCR Engine")
    parser.add_argument("--input", required=True, help="Input PDF or image file")
    parser.add_argument("--output", help="Output JSON file")
    parser.add_argument("--config", help="Configuration file (JSON)")
    parser.add_argument("--mode", choices=['full', 'simple'], default='full',
                       help="OCR mode: full (advanced) or simple (legacy)")
    parser.add_argument("--cleanup", action="store_true", help="Clean up temporary files")
    parser.add_argument("--cleanup-days", type=int, default=1, help="Cleanup files older than X days")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Cleanup if requested
    if args.cleanup:
        engine = KPKOCREngine()
        engine.cleanup_temp_files(args.cleanup_days)
        print(f"Cleanup complete")
        return
    
    # Load configuration
    config = {}
    if args.config:
        with open(args.config, 'r') as f:
            config = json.load(f)
    
    # Process document
    input_path = Path(args.input)
    
    if args.mode == 'simple':
        # Use simplified interface
        engine = SimplifiedKPKOCREngine()
        result = engine.process_document(input_path)
    else:
        # Use full engine
        engine = KPKOCREngine(config=config)
        result = engine.process_document(input_path)
    
    # Save or display results
    if args.output:
        output_path = Path(args.output)
        if args.mode == 'simple':
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
        else:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
        print(f"Results saved to {output_path}")
    else:
        if args.mode == 'simple':
            print(json.dumps(result, indent=2))
        else:
            print(json.dumps(result.to_dict(), indent=2))
    
    # Print summary
    if args.mode == 'full':
        print(f"\nOCR Processing Summary:")
        print(f"  Document: {input_path.name}")
        print(f"  Total Pages: {result.total_pages}")
        print(f"  Total Words: {result.total_words}")
        print(f"  Overall Quality: {result.overall_quality.value}")
        print(f"  Average Confidence: {result.avg_confidence:.1f}%")
        print(f"  Processing Time: {result.processing_time:.2f}s")
        print(f"  Languages Used: {', '.join(result.languages_used)}")
        print(f"  KPK Pages: {result.kpk_pages}")
        print(f"  Forestry Terms: {result.forestry_terms_total}")
        
        if result.pages:
            print(f"\nPage Details (first 3):")
            for i, page in enumerate(result.pages[:3]):
                print(f"  Page {i+1}: {page.page_type.value} ({page.word_count} words, {page.confidence:.1f}% confidence)")
                if page.forestry_terms:
                    print(f"    Forestry Terms: {', '.join(page.forestry_terms[:3])}")
    
    # Print statistics
    if args.mode == 'full':
        stats = engine.get_statistics()
        print(f"\nOCR Engine Statistics:")
        print(f"  Documents Processed: {stats['documents_processed']}")
        print(f"  Total Pages Processed: {sum(stats['page_types'].values())}")
        print(f"  Average OCR Time: {stats['avg_ocr_time']:.2f}s")
        print(f"  Excellent Quality Pages: {stats['ocr_quality']['excellent']}")
        print(f"  Poor Quality Pages: {stats['ocr_quality']['poor']}")

if __name__ == "__main__":
    main()
