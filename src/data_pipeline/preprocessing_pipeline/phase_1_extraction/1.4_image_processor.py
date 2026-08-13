"""
IMAGE_PROCESSOR.PY - Phase 1.4: KPK Forestry Document Image Extraction & Processing
Extracts and processes images from KPK forestry documents: stamps, signatures, photos, maps.
Author: Hina Ali, Eman Irfan
Date: January 29, 2026
"""

import re
import json
import logging
import hashlib
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union, Set, BinaryIO
from dataclasses import dataclass, asdict, field
from datetime import datetime
from collections import defaultdict
from enum import Enum
import statistics

# Third-party imports
import fitz  # PyMuPDF
import pdfplumber
from PIL import Image, ImageFilter, ImageEnhance
import cv2
import numpy as np
import pytesseract
from sklearn.cluster import DBSCAN
from scipy import ndimage

# Import from common modules
try:
    from preprocessing_pipeline.common.config import PipelineConfig, ImageProcessingConfig
    from preprocessing_pipeline.common.constants import *
    USE_COMMON_CONFIG = True
except ImportError:
    USE_COMMON_CONFIG = False
    print("Warning: common.config not found. Using default configuration.")

# Import from previous phases
try:
    from preprocessing_pipeline.phase_1_extraction import PDFParseResult, PDFPage
    from preprocessing_pipeline.phase_1_extraction import DocumentLayout, PageLayout, LayoutElement, LayoutElementType
    from preprocessing_pipeline.phase_1_extraction import TableExtractor, ExtractedTable
    from preprocessing_pipeline.phase_0_foundation import (
        AbstentionLogger, AbstentionType, AbstentionSeverity, 
        PipelineStage, create_abstention_context
    )
    PHASE_1_MODULES_AVAILABLE = True
except ImportError:
    PHASE_1_MODULES_AVAILABLE = False
    print("Warning: Phase 1 modules not available. Running in standalone mode.")

# ============================================================================
# CONFIGURATION
# ============================================================================

class ImageProcessingConfig:
    """Configuration for image processing"""
    
    # Extraction settings
    EXTRACT_IMAGES: bool = True
    EXTRACT_SIGNATURES: bool = True
    EXTRACT_STAMPS: bool = True
    EXTRACT_MAPS: bool = True
    EXTRACT_PHOTOS: bool = True
    
    # Image quality thresholds
    MIN_IMAGE_DIMENSION: int = 50  # pixels
    MAX_IMAGE_DIMENSION: int = 5000  # pixels
    MIN_IMAGE_SIZE_KB: int = 1
    MAX_IMAGE_SIZE_KB: int = 5000
    MIN_IMAGE_AREA_RATIO: float = 0.01  # Min image area / page area ratio
    MAX_IMAGE_AREA_RATIO: float = 0.95  # Max image area / page area ratio
    
    # Signature detection
    SIGNATURE_DETECTION_ENABLED: bool = True
    SIGNATURE_MIN_ASPECT_RATIO: float = 2.0
    SIGNATURE_MAX_ASPECT_RATIO: float = 8.0
    SIGNATURE_MIN_INK_DENSITY: float = 0.05
    SIGNATURE_MAX_INK_DENSITY: float = 0.5
    
    # Stamp detection
    STAMP_DETECTION_ENABLED: bool = True
    STAMP_MIN_CIRCULARITY: float = 0.6
    STAMP_MIN_RED_INTENSITY: float = 50  # For red stamps
    STAMP_SHAPE_TOLERANCE: float = 0.15
    
    # Map detection
    MAP_DETECTION_ENABLED: bool = True
    MAP_MIN_SIZE: int = 200  # pixels
    MAP_COLOR_VARIANCE_THRESHOLD: float = 0.3
    
    # Photo detection
    PHOTO_DETECTION_ENABLED: bool = True
    PHOTO_MIN_CONTRAST: float = 20.0
    PHOTO_COLOR_RANGE_THRESHOLD: float = 0.7
    
    # OCR settings for image text
    PERFORM_IMAGE_OCR: bool = True
    OCR_LANGUAGES: List[str] = ['eng', 'urd']  # English, Urdu
    OCR_ENGINE: str = 'tesseract'
    OCR_DPI: int = 300
    OCR_TIMEOUT: int = 30  # seconds
    
    # Image enhancement
    ENHANCE_IMAGES: bool = True
    ENHANCE_CONTRAST: bool = True
    ENHANCE_BRIGHTNESS: bool = True
    ENHANCE_SHARPNESS: bool = True
    DENOISE_IMAGES: bool = True
    
    # Processing settings
    PARALLEL_PROCESSING: bool = False
    MAX_WORKERS: int = 4
    CACHE_RESULTS: bool = True
    TEMP_DIR: Optional[str] = None
    
    # Output settings
    SAVE_EXTRACTED_IMAGES: bool = True
    OUTPUT_IMAGE_FORMAT: str = 'png'
    OUTPUT_QUALITY: int = 90
    GENERATE_THUMBNAILS: bool = True
    THUMBNAIL_SIZE: Tuple[int, int] = (200, 200)
    
    # KPK-specific settings
    DETECT_KPK_STAMPS: bool = True
    DETECT_FORESTRY_SEALS: bool = True
    EXTRACT_STAMP_TEXT: bool = True
    DETECT_GOVERNMENT_LOGO: bool = True
    
    # Quality control
    MIN_EXTRACTION_CONFIDENCE: float = 0.3
    VALIDATE_IMAGE_CONTENT: bool = True
    REMOVE_DUPLICATE_IMAGES: bool = True
    DUPLICATE_THRESHOLD: float = 0.95
    
    # Error handling
    CONTINUE_ON_ERROR: bool = True
    LOG_DETAILED_ERRORS: bool = True

# ============================================================================
# ENUMERATIONS
# ============================================================================

class ImageType(Enum):
    """Types of images in KPK forestry documents"""
    SIGNATURE = "signature"
    OFFICIAL_STAMP = "official_stamp"
    GOVERNMENT_SEAL = "government_seal"
    PHOTOGRAPH = "photograph"
    MAP = "map"
    DIAGRAM = "diagram"
    CHART = "chart"
    GRAPH = "graph"
    LOGO = "logo"
    WATERMARK = "watermark"
    BACKGROUND_IMAGE = "background_image"
    DECORATIVE = "decorative"
    UNKNOWN = "unknown"

class StampType(Enum):
    """Types of official stamps in KPK forestry"""
    KPK_GOVERNMENT_STAMP = "kpk_government_stamp"
    FOREST_DEPARTMENT_SEAL = "forest_department_seal"
    DFO_OFFICE_STAMP = "dfo_office_stamp"
    RANGE_OFFICE_STAMP = "range_office_stamp"
    RECEIPT_STAMP = "receipt_stamp"
    APPROVED_STAMP = "approved_stamp"
    PAID_STAMP = "paid_stamp"
    CANCELLED_STAMP = "cancelled_stamp"
    CONFIDENTIAL_STAMP = "confidential_stamp"
    URGENT_STAMP = "urgent_stamp"

class SignatureType(Enum):
    """Types of signatures in KPK forestry"""
    DFO_SIGNATURE = "dfo_signature"
    RANGE_OFFICER_SIGNATURE = "range_officer_signature"
    BEAT_GUARD_SIGNATURE = "beat_guard_signature"
    CONTRACTOR_SIGNATURE = "contractor_signature"
    WITNESS_SIGNATURE = "witness_signature"
    APPLICANT_SIGNATURE = "applicant_signature"
    VERIFIED_SIGNATURE = "verified_signature"
    UNKNOWN_SIGNATURE = "unknown_signature"

class ProcessingStatus(Enum):
    """Image processing status"""
    EXTRACTED = "extracted"
    ENHANCED = "enhanced"
    OCR_PROCESSED = "ocr_processed"
    CLASSIFIED = "classified"
    VALIDATED = "validated"
    ERROR = "error"
    SKIPPED = "skipped"

# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class ImageMetadata:
    """Metadata for an extracted image"""
    image_id: str
    image_type: ImageType
    page_num: int
    bbox: Tuple[float, float, float, float]  # x0, y0, x1, y1 in PDF coordinates
    
    # Dimensions
    width_pixels: int
    height_pixels: int
    dpi: Optional[int] = None
    
    # Content
    has_text: bool = False
    ocr_text: Optional[str] = None
    ocr_confidence: float = 0.0
    
    # Processing info
    extraction_method: str = "unknown"
    processing_status: ProcessingStatus = ProcessingStatus.EXTRACTED
    confidence: float = 1.0
    
    # KPK-specific
    is_kpk_official: bool = False
    stamp_type: Optional[StampType] = None
    signature_type: Optional[SignatureType] = None
    contains_government_logo: bool = False
    kpk_division: Optional[str] = None
    
    # File info
    file_path: Optional[str] = None
    file_size_kb: Optional[float] = None
    file_format: Optional[str] = None
    thumbnail_path: Optional[str] = None
    
    # Relationships
    associated_text: Optional[str] = None
    nearby_text: Optional[str] = None
    in_table: bool = False
    table_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['image_type'] = self.image_type.value
        data['processing_status'] = self.processing_status.value
        if self.stamp_type:
            data['stamp_type'] = self.stamp_type.value
        if self.signature_type:
            data['signature_type'] = self.signature_type.value
        return data

@dataclass
class Signature:
    """Extracted signature information"""
    signature_id: str
    image_id: str
    page_num: int
    bbox: Tuple[float, float, float, float]
    
    # Signature properties
    signature_type: SignatureType
    confidence: float = 1.0
    is_official: bool = False
    
    # Person information (if detectable)
    person_name: Optional[str] = None
    designation: Optional[str] = None
    department: Optional[str] = None
    
    # Verification
    is_verified: bool = False
    verification_method: Optional[str] = None
    verification_date: Optional[datetime] = None
    
    # Image data
    image_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    
    # Context
    associated_document_part: Optional[str] = None
    signing_purpose: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['signature_type'] = self.signature_type.value
        if self.verification_date:
            data['verification_date'] = self.verification_date.isoformat()
        return data

@dataclass
class Stamp:
    """Extracted stamp information"""
    stamp_id: str
    image_id: str
    page_num: int
    bbox: Tuple[float, float, float, float]
    
    # Stamp properties
    stamp_type: StampType
    confidence: float = 1.0
    is_official: bool = True
    color: str = "red"  # Usually red for KPK stamps
    
    # Stamp text
    stamp_text: Optional[str] = None
    ocr_confidence: Optional[float] = None
    
    # Organization info
    organization: Optional[str] = None
    division: Optional[str] = None
    office_name: Optional[str] = None
    
    # Date and numbers
    stamp_date: Optional[str] = None
    stamp_number: Optional[str] = None
    
    # Verification
    is_verified: bool = False
    verification_status: str = "unknown"
    
    # Image data
    image_path: Optional[str] = None
    enhanced_image_path: Optional[str] = None
    
    # Context
    stamp_purpose: Optional[str] = None
    associated_document_type: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['stamp_type'] = self.stamp_type.value
        return data

@dataclass
class MapInfo:
    """Extracted map information"""
    map_id: str
    image_id: str
    page_num: int
    bbox: Tuple[float, float, float, float]
    
    # Map properties
    map_type: str = "forest_map"
    scale: Optional[str] = None
    orientation: Optional[str] = None
    
    # Geographic info
    forest_division: Optional[str] = None
    compartment: Optional[str] = None
    beat_range: Optional[str] = None
    coordinates: Optional[List[Tuple[float, float]]] = None
    
    # Legend info
    has_legend: bool = False
    legend_text: Optional[str] = None
    
    # Quality
    clarity_score: float = 0.0
    detail_level: str = "unknown"
    
    # Processing
    is_georeferenced: bool = False
    georef_accuracy: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

@dataclass
class PhotoInfo:
    """Extracted photo information"""
    photo_id: str
    image_id: str
    page_num: int
    bbox: Tuple[float, float, float, float]
    
    # Photo properties
    photo_type: str = "tree_photo"
    subject: Optional[str] = None  # e.g., "deodar_tree", "forest_fire", "illegal_logging"
    
    # Tree-specific (if applicable)
    tree_species: Optional[str] = None
    tree_diameter: Optional[float] = None
    tree_health: Optional[str] = None
    
    # Location info
    location: Optional[str] = None
    gps_coordinates: Optional[Tuple[float, float]] = None
    
    # Date and time
    photo_date: Optional[str] = None
    photo_time: Optional[str] = None
    
    # Quality
    clarity_score: float = 0.0
    is_in_focus: bool = False
    lighting_condition: str = "unknown"
    
    # Context
    caption: Optional[str] = None
    related_incident: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

@dataclass
class ImageExtractionResult:
    """Result of image extraction and processing"""
    document_path: str
    document_hash: str
    extraction_timestamp: datetime
    
    # Extracted content
    images: List[ImageMetadata]
    signatures: List[Signature]
    stamps: List[Stamp]
    maps: List[MapInfo]
    photos: List[PhotoInfo]
    
    # Statistics
    total_images: int = 0
    total_signatures: int = 0
    total_stamps: int = 0
    total_maps: int = 0
    total_photos: int = 0
    kpk_official_images: int = 0
    
    # Processing info
    extraction_methods: List[str] = field(default_factory=list)
    processing_time: float = 0.0
    confidence_score: float = 0.0
    
    # Output files
    extracted_image_dir: Optional[str] = None
    thumbnail_dir: Optional[str] = None
    
    # Errors and warnings
    extraction_errors: List[str] = field(default_factory=list)
    extraction_warnings: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Calculate derived fields"""
        self.total_images = len(self.images)
        self.total_signatures = len(self.signatures)
        self.total_stamps = len(self.stamps)
        self.total_maps = len(self.maps)
        self.total_photos = len(self.photos)
        self.kpk_official_images = sum(1 for img in self.images if img.is_kpk_official)
        
        # Calculate overall confidence
        if self.images:
            confidences = [img.confidence for img in self.images]
            self.confidence_score = statistics.mean(confidences)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['images'] = [img.to_dict() for img in self.images]
        data['signatures'] = [sig.to_dict() for sig in self.signatures]
        data['stamps'] = [stamp.to_dict() for stamp in self.stamps]
        data['maps'] = [map_info.to_dict() for map_info in self.maps]
        data['photos'] = [photo.to_dict() for photo in self.photos]
        data['extraction_timestamp'] = self.extraction_timestamp.isoformat()
        return data
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get extraction statistics"""
        return {
            'total_images': self.total_images,
            'total_signatures': self.total_signatures,
            'total_stamps': self.total_stamps,
            'total_maps': self.total_maps,
            'total_photos': self.total_photos,
            'kpk_official_images': self.kpk_official_images,
            'confidence_score': self.confidence_score,
            'processing_time': self.processing_time,
            'extraction_methods': list(set(self.extraction_methods)),
        }

# ============================================================================
# KPK IMAGE PATTERNS
# ============================================================================

class KPKImagePatterns:
    """KPK forestry image patterns and templates"""
    
    # Stamp patterns and text
    STAMP_PATTERNS = {
        'kpk_government_stamp': {
            'keywords': ['GOVERNMENT OF KHYBER PAKHTUNKHWA', 'KPK GOVERNMENT', 'PROVINCIAL GOVERNMENT'],
            'color': 'red',
            'shape': 'circular',
            'typical_size': (150, 150),
        },
        'forest_department_seal': {
            'keywords': ['FOREST DEPARTMENT', 'FORESTRY WILDLIFE & FISHERIES', 'CONSERVATOR OF FORESTS'],
            'color': 'red',
            'shape': 'circular',
            'typical_size': (120, 120),
        },
        'dfo_office_stamp': {
            'keywords': ['DIVISIONAL FOREST OFFICER', 'DFO OFFICE', 'FOREST DIVISION'],
            'color': 'red',
            'shape': 'rectangular',
            'typical_size': (100, 60),
        },
        'range_office_stamp': {
            'keywords': ['RANGE OFFICER', 'FOREST RANGE', 'BEAT OFFICE'],
            'color': 'red',
            'shape': 'rectangular',
            'typical_size': (80, 50),
        },
        'receipt_stamp': {
            'keywords': ['RECEIVED', 'PAID', 'CASH RECEIVED', 'PAYMENT RECEIVED'],
            'color': 'red',
            'shape': 'rectangular',
            'typical_size': (70, 40),
        },
        'approved_stamp': {
            'keywords': ['APPROVED', 'SANCTIONED', 'PERMISSION GRANTED'],
            'color': 'green',  # Sometimes green
            'shape': 'rectangular',
            'typical_size': (60, 35),
        },
        'cancelled_stamp': {
            'keywords': ['CANCELLED', 'REJECTED', 'NOT APPROVED'],
            'color': 'red',
            'shape': 'rectangular',
            'typical_size': (60, 35),
        },
    }
    
    # Signature patterns
    SIGNATURE_PATTERNS = {
        'dfo_signature': {
            'keywords': ['DIVISIONAL FOREST OFFICER', 'DFO', 'FOREST OFFICER'],
            'location': 'bottom_right',
            'typical_size': (200, 60),
        },
        'range_officer_signature': {
            'keywords': ['RANGE OFFICER', 'FOREST RANGE OFFICER'],
            'location': 'bottom_right',
            'typical_size': (180, 50),
        },
        'contractor_signature': {
            'keywords': ['CONTRACTOR', 'LICENSE HOLDER', 'PERMIT HOLDER'],
            'location': 'bottom',
            'typical_size': (150, 40),
        },
        'applicant_signature': {
            'keywords': ['APPLICANT', 'PETITIONER', 'REQUESTOR'],
            'location': 'bottom',
            'typical_size': (150, 40),
        },
        'witness_signature': {
            'keywords': ['WITNESS', 'ATTESTED BY', 'VERIFIED BY'],
            'location': 'bottom',
            'typical_size': (150, 40),
        },
    }
    
    # Map patterns
    MAP_INDICATORS = [
        'MAP', 'SKETCH', 'DIAGRAM', 'PLAN',
        'COMPARTMENT', 'BEAT', 'RANGE',
        'NORTH', 'SCALE', 'LEGEND',
        'نقشہ', 'خاکہ', 'منصوبہ',
    ]
    
    # Photo patterns
    PHOTO_INDICATORS = [
        'PHOTO', 'PICTURE', 'IMAGE',
        'TREE', 'TIMBER', 'FOREST',
        'DAMAGE', 'FIRE', 'ENCROACHMENT',
        'تصویر', 'فوٹو', 'درخت',
    ]
    
    # Logo patterns
    KPK_LOGOS = {
        'government_logo': {
            'keywords': ['KPK LOGO', 'GOVERNMENT LOGO', 'SEAL'],
            'color_pattern': ['blue', 'white', 'green'],
        },
        'forest_department_logo': {
            'keywords': ['TREE LOGO', 'FOREST LOGO', 'WILDLIFE LOGO'],
            'color_pattern': ['green', 'brown'],
        },
    }
    
    @classmethod
    def detect_stamp_type(cls, image_text: str, color_info: str) -> Tuple[Optional[StampType], float]:
        """Detect stamp type based on text and color"""
        text_upper = image_text.upper()
        best_match = None
        best_score = 0.0
        
        for stamp_type, pattern in cls.STAMP_PATTERNS.items():
            score = 0.0
            
            # Check keywords
            for keyword in pattern['keywords']:
                if keyword.upper() in text_upper:
                    score += 0.3
            
            # Check color
            if color_info == pattern['color']:
                score += 0.2
            
            if score > best_score:
                best_score = score
                best_match = stamp_type
        
        if best_match and best_score >= 0.3:
            return StampType(best_match), best_score
        
        return None, 0.0
    
    @classmethod
    def detect_signature_type(cls, context_text: str, location: str) -> Tuple[Optional[SignatureType], float]:
        """Detect signature type based on context"""
        text_upper = context_text.upper()
        best_match = None
        best_score = 0.0
        
        for sig_type, pattern in cls.SIGNATURE_PATTERNS.items():
            score = 0.0
            
            # Check keywords
            for keyword in pattern['keywords']:
                if keyword.upper() in text_upper:
                    score += 0.3
            
            # Check location
            if location == pattern['location']:
                score += 0.1
            
            if score > best_score:
                best_score = score
                best_match = sig_type
        
        if best_match and best_score >= 0.3:
            return SignatureType(best_match), best_score
        
        return None, 0.0
    
    @classmethod
    def is_map_indicator(cls, text: str) -> bool:
        """Check if text indicates a map"""
        text_upper = text.upper()
        return any(indicator in text_upper for indicator in cls.MAP_INDICATORS)
    
    @classmethod
    def is_photo_indicator(cls, text: str) -> bool:
        """Check if text indicates a photo"""
        text_upper = text.upper()
        return any(indicator in text_upper for indicator in cls.PHOTO_INDICATORS)

# ============================================================================
# IMAGE PROCESSOR
# ============================================================================

class ImageProcessor:
    """
    Phase 1.4: KPK Forestry Document Image Extraction & Processing
    Extracts and processes images from KPK forestry documents.
    """
    
    def __init__(self, 
                 config: Optional[Union[ImageProcessingConfig, Dict]] = None,
                 enable_abstention_logging: bool = True,
                 logger: Optional[logging.Logger] = None):
        """
        Initialize image processor.
        
        Args:
            config: Configuration object or dictionary
            enable_abstention_logging: Whether to log abstentions
            logger: Optional logger instance
        """
        
        # Configuration
        if isinstance(config, dict):
            self.config = ImageProcessingConfig()
            # Update config from dict
            for key, value in config.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
        else:
            self.config = config or ImageProcessingConfig()
        
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
        
        # Pattern matcher
        self.patterns = KPKImagePatterns()
        
        # Create temporary directory if not specified
        if not self.config.TEMP_DIR:
            self.temp_dir = tempfile.mkdtemp(prefix="gl_ai_images_")
        else:
            self.temp_dir = Path(self.config.TEMP_DIR)
            Path(self.temp_dir).mkdir(parents=True, exist_ok=True)
        
        # Statistics
        self.stats = self._init_statistics()
        
        # Cache
        self._extraction_cache = {}
        
        self.logger.info(f"ImageProcessor initialized with temp dir: {self.temp_dir}")
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging"""
        logger = logging.getLogger('ImageProcessor')
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
            'documents_processed': 0,
            'total_pages_processed': 0,
            'processing_time_total': 0.0,
            'avg_processing_time': 0.0,
            
            'images_extracted': {
                'total': 0,
                'signatures': 0,
                'stamps': 0,
                'maps': 0,
                'photos': 0,
                'kpk_official': 0,
            },
            
            'extraction_methods': {
                'pdf_image': 0,
                'ocr_based': 0,
                'layout_based': 0,
                'manual_detection': 0,
            },
            
            'image_quality': {
                'high_quality': 0,
                'medium_quality': 0,
                'low_quality': 0,
                'enhanced': 0,
            },
            
            'ocr_results': {
                'images_with_text': 0,
                'avg_confidence': 0.0,
                'total_text_chars': 0,
            },
            
            'kpk_detections': {
                'government_stamps': 0,
                'forest_stamps': 0,
                'official_signatures': 0,
                'government_logos': 0,
            },
            
            'performance': {
                'fastest_processing': float('inf'),
                'slowest_processing': 0.0,
                'processing_times': [],
            },
            
            'issues': {
                'extraction_errors': 0,
                'low_quality_images': 0,
                'failed_ocr': 0,
            },
        }
    
    def process_images(self, 
                      input_data: Union[PDFParseResult, DocumentLayout, Path, Dict],
                      document_path: Optional[Union[str, Path]] = None,
                      output_dir: Optional[Union[str, Path]] = None) -> ImageExtractionResult:
        """
        Extract and process images from input data.
        
        Args:
            input_data: PDFParseResult, DocumentLayout, PDF path, or dictionary
            document_path: Optional document path for identification
            output_dir: Optional directory for saving extracted images
            
        Returns:
            ImageExtractionResult with processed images
        """
        import time
        start_time = time.time()
        
        try:
            # Generate cache key
            cache_key = self._generate_cache_key(input_data, document_path)
            
            # Check cache
            if self.config.CACHE_RESULTS and cache_key in self._extraction_cache:
                self.logger.info(f"Returning cached image processing for {document_path or 'document'}")
                return self._extraction_cache[cache_key]
            
            self.logger.info(f"Processing images from {document_path or 'document'}")
            
            # Setup output directories
            if output_dir:
                output_dir = Path(output_dir)
                output_dir.mkdir(parents=True, exist_ok=True)
                images_dir = output_dir / "images"
                thumbs_dir = output_dir / "thumbnails"
            else:
                # Use temp directory
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                images_dir = Path(self.temp_dir) / f"images_{timestamp}"
                thumbs_dir = Path(self.temp_dir) / f"thumbnails_{timestamp}"
            
            images_dir.mkdir(parents=True, exist_ok=True)
            thumbs_dir.mkdir(parents=True, exist_ok=True)
            
            # Process based on input type
            if isinstance(input_data, PDFParseResult):
                result = self._process_from_pdf_parse(input_data, document_path, images_dir, thumbs_dir)
            elif isinstance(input_data, DocumentLayout):
                result = self._process_from_document_layout(input_data, document_path, images_dir, thumbs_dir)
            elif isinstance(input_data, Path) or isinstance(input_data, str):
                result = self._process_from_pdf_file(Path(input_data), images_dir, thumbs_dir)
            elif isinstance(input_data, dict):
                result = self._process_from_dict(input_data, document_path, images_dir, thumbs_dir)
            else:
                raise ValueError(f"Unsupported input type: {type(input_data)}")
            
            # Set output directories
            result.extracted_image_dir = str(images_dir)
            result.thumbnail_dir = str(thumbs_dir)
            
            # Cache result
            if self.config.CACHE_RESULTS:
                self._extraction_cache[cache_key] = result
            
            # Update statistics
            processing_time = time.time() - start_time
            result.processing_time = processing_time
            self._update_statistics(result, processing_time)
            
            # Log abstention if image quality is poor
            if (self.enable_abstention_logging and self.abstention_logger and 
                result.confidence_score < 0.5):
                
                self._log_image_abstention(result, document_path)
            
            self.logger.info(
                f"Image processing complete: {document_path or 'document'} - "
                f"Images: {len(result.images)}, "
                f"Signatures: {len(result.signatures)}, "
                f"Stamps: {len(result.stamps)}, "
                f"Confidence: {result.confidence_score:.2%}, "
                f"Time: {processing_time:.2f}s"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Image processing failed: {e}")
            
            # Create minimal result with error
            return self._create_error_result(document_path, str(e))
    
    def _generate_cache_key(self, input_data: Any, document_path: Optional[Union[str, Path]]) -> str:
        """Generate cache key for processing"""
        try:
            if isinstance(input_data, PDFParseResult):
                doc_hash = input_data.document_hash
            elif isinstance(input_data, DocumentLayout):
                doc_hash = input_data.document_hash
            elif document_path:
                doc_hash = hashlib.md5(str(document_path).encode()).hexdigest()[:16]
            else:
                doc_hash = hashlib.md5(str(input_data).encode()).hexdigest()[:16]
            
            return f"images_{doc_hash}"
        except:
            return "images_unknown"
    
    def _process_from_pdf_parse(self, pdf_result: PDFParseResult,
                               document_path: Optional[Union[str, Path]],
                               images_dir: Path,
                               thumbs_dir: Path) -> ImageExtractionResult:
        """Process images from PDFParseResult"""
        all_images = []
        all_signatures = []
        all_stamps = []
        all_maps = []
        all_photos = []
        extraction_methods = set()
        
        for page in pdf_result.pages:
            try:
                page_images, page_sigs, page_stamps, page_maps, page_photos, methods = self._process_page_images(
                    page, pdf_result, page.page_number, images_dir, thumbs_dir
                )
                
                all_images.extend(page_images)
                all_signatures.extend(page_sigs)
                all_stamps.extend(page_stamps)
                all_maps.extend(page_maps)
                all_photos.extend(page_photos)
                extraction_methods.update(methods)
                
                self.stats['total_pages_processed'] += 1
                
            except Exception as e:
                self.logger.warning(f"Failed to process images from page {page.page_number}: {e}")
                if not self.config.CONTINUE_ON_ERROR:
                    raise
        
        # Create result
        result = ImageExtractionResult(
            document_path=pdf_result.document_path,
            document_hash=pdf_result.document_hash,
            extraction_timestamp=datetime.now(),
            images=all_images,
            signatures=all_signatures,
            stamps=all_stamps,
            maps=all_maps,
            photos=all_photos,
            extraction_methods=list(extraction_methods),
        )
        
        return result
    
    def _process_from_document_layout(self, layout: DocumentLayout,
                                    document_path: Optional[Union[str, Path]],
                                    images_dir: Path,
                                    thumbs_dir: Path) -> ImageExtractionResult:
        """Process images from DocumentLayout"""
        # Note: Layout might not contain actual image data, just positions
        # We need to extract from the original PDF
        
        all_images = []
        all_signatures = []
        all_stamps = []
        all_maps = []
        all_photos = []
        
        # Try to get PDF path from layout
        pdf_path = Path(layout.document_path) if hasattr(layout, 'document_path') else None
        
        if pdf_path and pdf_path.exists() and pdf_path.suffix.lower() == '.pdf':
            # Process directly from PDF file
            return self._process_from_pdf_file(pdf_path, images_dir, thumbs_dir)
        
        # Fallback: Try to extract image info from layout elements
        for page_layout in layout.pages:
            try:
                page_images = self._extract_images_from_layout(page_layout, images_dir, thumbs_dir)
                all_images.extend(page_images)
                
            except Exception as e:
                self.logger.warning(f"Failed to process images from page {page_layout.page_num}: {e}")
        
        # Create result
        result = ImageExtractionResult(
            document_path=layout.document_path,
            document_hash=layout.document_hash,
            extraction_timestamp=datetime.now(),
            images=all_images,
            signatures=[],
            stamps=[],
            maps=[],
            photos=[],
            extraction_methods=['layout_based'],
        )
        
        return result
    
    def _process_from_pdf_file(self, pdf_path: Path,
                              images_dir: Path,
                              thumbs_dir: Path) -> ImageExtractionResult:
        """Process images directly from PDF file"""
        all_images = []
        all_signatures = []
        all_stamps = []
        all_maps = []
        all_photos = []
        extraction_methods = set()
        
        try:
            # Open PDF with PyMuPDF for image extraction
            pdf_doc = fitz.open(str(pdf_path))
            
            for page_num in range(len(pdf_doc)):
                try:
                    page = pdf_doc[page_num]
                    
                    # Extract images from page
                    page_images, page_sigs, page_stamps, page_maps, page_photos, methods = self._extract_images_from_pymupdf_page(
                        page, page_num, pdf_path, images_dir, thumbs_dir
                    )
                    
                    all_images.extend(page_images)
                    all_signatures.extend(page_sigs)
                    all_stamps.extend(page_stamps)
                    all_maps.extend(page_maps)
                    all_photos.extend(page_photos)
                    extraction_methods.update(methods)
                    
                    self.stats['total_pages_processed'] += 1
                    
                except Exception as e:
                    self.logger.warning(f"Failed to process page {page_num}: {e}")
                    if not self.config.CONTINUE_ON_ERROR:
                        raise
            
            pdf_doc.close()
            
        except Exception as e:
            self.logger.error(f"Failed to open PDF {pdf_path}: {e}")
            return self._create_error_result(pdf_path, str(e))
        
        # Create result
        result = ImageExtractionResult(
            document_path=str(pdf_path),
            document_hash=hashlib.md5(str(pdf_path).encode()).hexdigest()[:16],
            extraction_timestamp=datetime.now(),
            images=all_images,
            signatures=all_signatures,
            stamps=all_stamps,
            maps=all_maps,
            photos=all_photos,
            extraction_methods=list(extraction_methods),
        )
        
        return result
    
    def _process_from_dict(self, data_dict: Dict,
                          document_path: Optional[Union[str, Path]],
                          images_dir: Path,
                          thumbs_dir: Path) -> ImageExtractionResult:
        """Process images from dictionary"""
        # This is a simplified implementation for data already extracted
        all_images = []
        
        # Check for image data in dictionary
        if 'images' in data_dict and isinstance(data_dict['images'], list):
            for img_data in data_dict['images']:
                try:
                    image_meta = self._create_image_metadata_from_dict(img_data)
                    if image_meta:
                        all_images.append(image_meta)
                except Exception as e:
                    self.logger.warning(f"Failed to process image data: {e}")
        
        # Create result
        result = ImageExtractionResult(
            document_path=str(document_path) if document_path else 'unknown',
            document_hash=hashlib.md5(str(data_dict).encode()).hexdigest()[:16],
            extraction_timestamp=datetime.now(),
            images=all_images,
            signatures=[],
            stamps=[],
            maps=[],
            photos=[],
            extraction_methods=['dictionary_extraction'],
        )
        
        return result
    
    def _process_page_images(self, page: PDFPage,
                            pdf_result: PDFParseResult,
                            page_num: int,
                            images_dir: Path,
                            thumbs_dir: Path) -> Tuple[List[ImageMetadata], List[Signature], List[Stamp], List[MapInfo], List[PhotoInfo], Set[str]]:
        """Process images from a single PDF page"""
        images = []
        signatures = []
        stamps = []
        maps = []
        photos = []
        methods = set()
        
        # Get page text for context
        page_text = page.cleaned_text if hasattr(page, 'cleaned_text') else ''
        
        # Method 1: Extract using PyMuPDF
        try:
            fitz_images, fitz_methods = self._extract_images_fitz(page, page_num, pdf_result, images_dir, thumbs_dir)
            images.extend(fitz_images)
            methods.update(fitz_methods)
        except Exception as e:
            self.logger.debug(f"PyMuPDF image extraction failed for page {page_num}: {e}")
        
        # Method 2: Detect from layout
        if hasattr(page, 'layout') and page.layout:
            try:
                layout_images = self._extract_images_from_layout_element(page.layout, images_dir, thumbs_dir)
                images.extend(layout_images)
                methods.add('layout_detection')
            except Exception as e:
                self.logger.debug(f"Layout-based extraction failed: {e}")
        
        # Method 3: OCR-based detection (for scanned signatures/stamps)
        if self.config.PERFORM_IMAGE_OCR and page_text:
            try:
                ocr_images = self._detect_images_from_ocr(page_text, page_num, images_dir, thumbs_dir)
                images.extend(ocr_images)
                methods.add('ocr_detection')
            except Exception as e:
                self.logger.debug(f"OCR-based detection failed: {e}")
        
        # Classify and enhance images
        classified_images = []
        for image in images:
            try:
                # Classify image type
                classified = self._classify_image(image, page_text)
                
                # Enhance if needed
                if self.config.ENHANCE_IMAGES and classified.confidence < 0.8:
                    enhanced = self._enhance_image(classified, images_dir)
                    if enhanced:
                        classified = enhanced
                
                # Perform OCR on image
                if self.config.PERFORM_IMAGE_OCR and classified.has_text:
                    ocr_result = self._perform_image_ocr(classified, images_dir)
                    if ocr_result:
                        classified = ocr_result
                
                classified_images.append(classified)
                
                # Extract specific types
                if classified.image_type == ImageType.SIGNATURE:
                    signature = self._extract_signature(classified, page_text)
                    if signature:
                        signatures.append(signature)
                
                elif classified.image_type == ImageType.OFFICIAL_STAMP or classified.image_type == ImageType.GOVERNMENT_SEAL:
                    stamp = self._extract_stamp(classified, page_text)
                    if stamp:
                        stamps.append(stamp)
                
                elif classified.image_type == ImageType.MAP:
                    map_info = self._extract_map_info(classified, page_text)
                    if map_info:
                        maps.append(map_info)
                
                elif classified.image_type == ImageType.PHOTOGRAPH:
                    photo_info = self._extract_photo_info(classified, page_text)
                    if photo_info:
                        photos.append(photo_info)
                
            except Exception as e:
                self.logger.warning(f"Failed to process image {image.image_id}: {e}")
        
        return classified_images, signatures, stamps, maps, photos, methods
    
    def _extract_images_fitz(self, page: PDFPage,
                            page_num: int,
                            pdf_result: PDFParseResult,
                            images_dir: Path,
                            thumbs_dir: Path) -> Tuple[List[ImageMetadata], Set[str]]:
        """Extract images using PyMuPDF (fitz)"""
        images = []
        methods = set()
        
        # This is a placeholder - in actual implementation, you would:
        # 1. Get the PDF page as fitz page
        # 2. Use page.get_images() to get image list
        # 3. Extract each image
        
        # For now, return empty
        return images, methods
    
    def _extract_images_from_layout(self, page_layout: Any,
                                   images_dir: Path,
                                   thumbs_dir: Path) -> List[ImageMetadata]:
        """Extract images from layout information"""
        images = []
        
        # This would parse layout elements to find images
        # For now, return empty list
        
        return images
    
    def _extract_images_from_pymupdf_page(self, page: fitz.Page,
                                         page_num: int,
                                         pdf_path: Path,
                                         images_dir: Path,
                                         thumbs_dir: Path) -> Tuple[List[ImageMetadata], List[Signature], List[Stamp], List[MapInfo], List[PhotoInfo], Set[str]]:
        """Extract images from PyMuPDF page"""
        images = []
        signatures = []
        stamps = []
        maps = []
        photos = []
        methods = set()
        
        try:
            # Get image list from page
            image_list = page.get_images(full=True)
            
            for img_index, img_info in enumerate(image_list):
                try:
                    # Extract the image
                    xref = img_info[0]
                    base_image = page.parent.extract_image(xref)
                    
                    if not base_image:
                        continue
                    
                    # Get image data
                    image_data = base_image["image"]
                    image_ext = base_image["ext"]
                    
                    # Create unique ID
                    image_id = f"page{page_num}_img{img_index}_{hashlib.md5(image_data).hexdigest()[:8]}"
                    
                    # Save image to file
                    image_filename = f"{image_id}.{self.config.OUTPUT_IMAGE_FORMAT}"
                    image_path = images_dir / image_filename
                    
                    with open(image_path, "wb") as f:
                        f.write(image_data)
                    
                    # Get image properties
                    pil_image = Image.open(image_path)
                    width, height = pil_image.size
                    
                    # Get bounding box (estimate from PDF coordinates)
                    # In real implementation, you'd get this from the image location on page
                    bbox = (0, 0, 100, 100)  # Placeholder
                    
                    # Create metadata
                    image_meta = ImageMetadata(
                        image_id=image_id,
                        image_type=ImageType.UNKNOWN,
                        page_num=page_num,
                        bbox=bbox,
                        width_pixels=width,
                        height_pixels=height,
                        file_path=str(image_path),
                        file_size_kb=image_path.stat().st_size / 1024,
                        file_format=self.config.OUTPUT_IMAGE_FORMAT,
                        extraction_method="pymupdf",
                        confidence=0.7,
                    )
                    
                    images.append(image_meta)
                    methods.add('pdf_image')
                    
                    # Generate thumbnail
                    if self.config.GENERATE_THUMBNAILS:
                        thumbnail_path = thumbs_dir / f"thumb_{image_filename}"
                        self._generate_thumbnail(pil_image, thumbnail_path)
                        image_meta.thumbnail_path = str(thumbnail_path)
                    
                    pil_image.close()
                    
                except Exception as e:
                    self.logger.warning(f"Failed to extract image {img_index} from page {page_num}: {e}")
        
        except Exception as e:
            self.logger.warning(f"Failed to get images from page {page_num}: {e}")
        
        return images, signatures, stamps, maps, photos, methods
    
    def _generate_thumbnail(self, image: Image.Image, output_path: Path):
        """Generate thumbnail for image"""
        try:
            thumbnail_size = self.config.THUMBNAIL_SIZE
            image.thumbnail(thumbnail_size, Image.Resampling.LANCZOS)
            image.save(output_path, format=self.config.OUTPUT_IMAGE_FORMAT, 
                      quality=self.config.OUTPUT_QUALITY)
        except Exception as e:
            self.logger.warning(f"Failed to generate thumbnail: {e}")
    
    def _create_image_metadata_from_dict(self, img_data: Dict) -> Optional[ImageMetadata]:
        """Create ImageMetadata from dictionary"""
        try:
            return ImageMetadata(
                image_id=img_data.get('image_id', 'unknown'),
                image_type=ImageType(img_data.get('image_type', 'unknown')),
                page_num=img_data.get('page_num', 0),
                bbox=tuple(img_data.get('bbox', (0, 0, 0, 0))),
                width_pixels=img_data.get('width_pixels', 0),
                height_pixels=img_data.get('height_pixels', 0),
                has_text=img_data.get('has_text', False),
                ocr_text=img_data.get('ocr_text'),
                confidence=img_data.get('confidence', 0.5),
                is_kpk_official=img_data.get('is_kpk_official', False),
            )
        except Exception as e:
            self.logger.warning(f"Failed to create image metadata from dict: {e}")
            return None
    
    def _detect_images_from_ocr(self, page_text: str,
                               page_num: int,
                               images_dir: Path,
                               thumbs_dir: Path) -> List[ImageMetadata]:
        """Detect images from OCR text (for scanned documents)"""
        images = []
        
        # Look for image indicators in text
        # This is a simplified approach - in production, you'd use proper image detection
        
        return images
    
    def _classify_image(self, image: ImageMetadata, context_text: str) -> ImageMetadata:
        """Classify image type based on properties and context"""
        
        # Check if it's likely a signature
        if self.config.EXTRACT_SIGNATURES and self._is_likely_signature(image):
            image.image_type = ImageType.SIGNATURE
            image.confidence = 0.8
            
            # Check for KPK official signature
            if self._is_kpk_official_signature(image, context_text):
                image.is_kpk_official = True
                image.confidence = 0.9
        
        # Check if it's likely a stamp
        elif self.config.EXTRACT_STAMPS and self._is_likely_stamp(image):
            image.image_type = ImageType.OFFICIAL_STAMP
            image.confidence = 0.85
            
            # Check for KPK government stamp
            if self._is_kpk_government_stamp(image, context_text):
                image.is_kpk_official = True
                image.contains_government_logo = True
                image.confidence = 0.95
        
        # Check if it's likely a map
        elif self.config.EXTRACT_MAPS and self._is_likely_map(image, context_text):
            image.image_type = ImageType.MAP
            image.confidence = 0.7
        
        # Check if it's likely a photo
        elif self.config.EXTRACT_PHOTOS and self._is_likely_photo(image, context_text):
            image.image_type = ImageType.PHOTOGRAPH
            image.confidence = 0.75
        
        # Check for text content
        if image.file_path and Path(image.file_path).exists():
            try:
                # Quick check for text in image
                pil_image = Image.open(image.file_path)
                
                # Convert to grayscale for analysis
                if pil_image.mode != 'L':
                    gray_image = pil_image.convert('L')
                else:
                    gray_image = pil_image
                
                # Calculate ink density
                np_image = np.array(gray_image)
                ink_density = np.sum(np_image < 128) / np_image.size
                
                image.has_text = ink_density > 0.05
                
                pil_image.close()
                
            except Exception as e:
                self.logger.debug(f"Failed to analyze image for text: {e}")
        
        return image
    
    def _is_likely_signature(self, image: ImageMetadata) -> bool:
        """Check if image is likely a signature"""
        # Signature characteristics:
        # 1. Aspect ratio typically > 2:1 (wider than tall)
        # 2. Moderate ink density
        # 3. Usually not too large
        
        if image.width_pixels == 0 or image.height_pixels == 0:
            return False
        
        aspect_ratio = image.width_pixels / image.height_pixels
        
        return (aspect_ratio >= self.config.SIGNATURE_MIN_ASPECT_RATIO and 
                aspect_ratio <= self.config.SIGNATURE_MAX_ASPECT_RATIO)
    
    def _is_kpk_official_signature(self, image: ImageMetadata, context_text: str) -> bool:
        """Check if signature appears to be KPK official"""
        # Look for KPK-related text near signature location
        kpk_keywords = ['DFO', 'RANGE OFFICER', 'FOREST OFFICER', 'KPK', 'KHYBER PAKHTUNKHWA']
        
        if not context_text:
            return False
        
        context_upper = context_text.upper()
        return any(keyword in context_upper for keyword in kpk_keywords)
    
    def _is_likely_stamp(self, image: ImageMetadata) -> bool:
        """Check if image is likely a stamp"""
        # Stamp characteristics:
        # 1. Often circular or rectangular
        # 2. Specific size range
        # 3. Often red color
        
        if image.width_pixels == 0 or image.height_pixels == 0:
            return False
        
        # Check size range
        min_dim = min(image.width_pixels, image.height_pixels)
        max_dim = max(image.width_pixels, image.height_pixels)
        
        # Stamps are usually not too large or too small
        if min_dim < 20 or max_dim > 300:
            return False
        
        # Check aspect ratio (stamps are often square or slightly rectangular)
        aspect_ratio = image.width_pixels / image.height_pixels
        return 0.7 <= aspect_ratio <= 1.3
    
    def _is_kpk_government_stamp(self, image: ImageMetadata, context_text: str) -> bool:
        """Check if stamp appears to be KPK government stamp"""
        # In production, you'd analyze the image for:
        # 1. Red color dominance
        # 2. Circular shape
        # 3. Government logo patterns
        
        # For now, use context text
        gov_keywords = ['GOVERNMENT', 'KPK', 'KHYBER PAKHTUNKHWA', 'OFFICIAL', 'SEAL']
        
        if not context_text:
            return False
        
        context_upper = context_text.upper()
        keyword_count = sum(1 for keyword in gov_keywords if keyword in context_upper)
        
        return keyword_count >= 2
    
    def _is_likely_map(self, image: ImageMetadata, context_text: str) -> bool:
        """Check if image is likely a map"""
        # Map characteristics:
        # 1. Often larger images
        # 2. May have text like "MAP", "SCALE", "NORTH"
        # 3. Complex color patterns
        
        if image.width_pixels < self.config.MAP_MIN_SIZE or image.height_pixels < self.config.MAP_MIN_SIZE:
            return False
        
        # Check context
        if context_text and self.patterns.is_map_indicator(context_text):
            return True
        
        return False
    
    def _is_likely_photo(self, image: ImageMetadata, context_text: str) -> bool:
        """Check if image is likely a photograph"""
        # Photo characteristics:
        # 1. Often rectangular
        # 2. Moderate to high resolution
        # 3. May have photo-related text nearby
        
        # Check context first
        if context_text and self.patterns.is_photo_indicator(context_text):
            return True
        
        # Check size (photos are usually larger)
        min_dim = min(image.width_pixels, image.height_pixels)
        return min_dim >= 100
    
    def _enhance_image(self, image: ImageMetadata, images_dir: Path) -> Optional[ImageMetadata]:
        """Enhance image quality"""
        if not image.file_path or not Path(image.file_path).exists():
            return None
        
        try:
            pil_image = Image.open(image.file_path)
            
            # Apply enhancements
            if self.config.ENHANCE_CONTRAST:
                enhancer = ImageEnhance.Contrast(pil_image)
                pil_image = enhancer.enhance(1.2)
            
            if self.config.ENHANCE_BRIGHTNESS:
                enhancer = ImageEnhance.Brightness(pil_image)
                pil_image = enhancer.enhance(1.1)
            
            if self.config.ENHANCE_SHARPNESS:
                enhancer = ImageEnhance.Sharpness(pil_image)
                pil_image = enhancer.enhance(1.1)
            
            if self.config.DENOISE_IMAGES:
                # Simple denoise
                pil_image = pil_image.filter(ImageFilter.MedianFilter(size=3))
            
            # Save enhanced image
            enhanced_filename = f"enhanced_{Path(image.file_path).name}"
            enhanced_path = images_dir / enhanced_filename
            pil_image.save(enhanced_path, format=self.config.OUTPUT_IMAGE_FORMAT,
                          quality=self.config.OUTPUT_QUALITY)
            
            # Update metadata
            image.file_path = str(enhanced_path)
            image.confidence = min(1.0, image.confidence + 0.1)
            image.processing_status = ProcessingStatus.ENHANCED
            
            pil_image.close()
            return image
            
        except Exception as e:
            self.logger.warning(f"Failed to enhance image {image.image_id}: {e}")
            return None
    
    def _perform_image_ocr(self, image: ImageMetadata, images_dir: Path) -> Optional[ImageMetadata]:
        """Perform OCR on image to extract text"""
        if not image.file_path or not Path(image.file_path).exists():
            return None
        
        try:
            # Use pytesseract for OCR
            pil_image = Image.open(image.file_path)
            
            # Configure OCR
            ocr_config = f'--dpi {self.config.OCR_DPI}'
            if self.config.OCR_LANGUAGES:
                lang_str = '+'.join(self.config.OCR_LANGUAGES)
                ocr_config += f' -l {lang_str}'
            
            # Perform OCR
            ocr_result = pytesseract.image_to_data(pil_image, config=ocr_config, 
                                                  output_type=pytesseract.Output.DICT)
            
            # Extract text and confidence
            all_text = []
            confidences = []
            
            for i, text in enumerate(ocr_result['text']):
                if text.strip():
                    all_text.append(text)
                    conf = ocr_result['conf'][i] / 100.0  # Convert to 0-1 scale
                    confidences.append(conf)
            
            if all_text:
                image.ocr_text = ' '.join(all_text)
                if confidences:
                    image.ocr_confidence = statistics.mean(confidences)
                else:
                    image.ocr_confidence = 0.5
                
                image.processing_status = ProcessingStatus.OCR_PROCESSED
            
            pil_image.close()
            return image
            
        except Exception as e:
            self.logger.warning(f"OCR failed for image {image.image_id}: {e}")
            return None
    
    def _extract_signature(self, image: ImageMetadata, context_text: str) -> Optional[Signature]:
        """Extract signature information"""
        if image.image_type != ImageType.SIGNATURE:
            return None
        
        # Determine signature type
        sig_type, confidence = self.patterns.detect_signature_type(context_text, "bottom_right")
        
        # Create signature object
        signature = Signature(
            signature_id=f"sig_{image.image_id}",
            image_id=image.image_id,
            page_num=image.page_num,
            bbox=image.bbox,
            signature_type=sig_type or SignatureType.UNKNOWN_SIGNATURE,
            confidence=min(image.confidence, confidence),
            is_official=image.is_kpk_official,
            image_path=image.file_path,
            thumbnail_path=image.thumbnail_path,
        )
        
        # Try to extract person info from context
        if context_text:
            # Look for name patterns near signature
            name_patterns = [
                r'Name\s*[:.]\s*([A-Za-z\s.]+)',
                r'Signature of\s*([A-Za-z\s.]+)',
                r'Signed by\s*([A-Za-z\s.]+)',
            ]
            
            for pattern in name_patterns:
                match = re.search(pattern, context_text, re.IGNORECASE)
                if match:
                    signature.person_name = match.group(1).strip()
                    break
        
        return signature
    
    def _extract_stamp(self, image: ImageMetadata, context_text: str) -> Optional[Stamp]:
        """Extract stamp information"""
        if image.image_type not in [ImageType.OFFICIAL_STAMP, ImageType.GOVERNMENT_SEAL]:
            return None
        
        # Get OCR text if available
        stamp_text = image.ocr_text or ""
        
        # Determine stamp type
        stamp_type, confidence = self.patterns.detect_stamp_type(stamp_text, "red")
        
        # Create stamp object
        stamp = Stamp(
            stamp_id=f"stamp_{image.image_id}",
            image_id=image.image_id,
            page_num=image.page_num,
            bbox=image.bbox,
            stamp_type=stamp_type or StampType.KPK_GOVERNMENT_STAMP,
            confidence=min(image.confidence, confidence),
            is_official=image.is_kpk_official,
            stamp_text=stamp_text,
            ocr_confidence=image.ocr_confidence,
            image_path=image.file_path,
            enhanced_image_path=image.file_path if image.processing_status == ProcessingStatus.ENHANCED else None,
        )
        
        # Try to extract organization info
        if stamp_text:
            # Look for organization patterns
            org_patterns = [
                r'FOREST\s+(?:DEPT|DEPARTMENT)',
                r'DIVISIONAL FOREST OFFICER',
                r'RANGE OFFICE',
                r'GOVERNMENT OF KHYBER PAKHTUNKHWA',
            ]
            
            for pattern in org_patterns:
                if re.search(pattern, stamp_text, re.IGNORECASE):
                    stamp.organization = pattern.replace(r'\s+', ' ')
                    break
        
        return stamp
    
    def _extract_map_info(self, image: ImageMetadata, context_text: str) -> Optional[MapInfo]:
        """Extract map information"""
        if image.image_type != ImageType.MAP:
            return None
        
        # Create map object
        map_info = MapInfo(
            map_id=f"map_{image.image_id}",
            image_id=image.image_id,
            page_num=image.page_num,
            bbox=image.bbox,
            clarity_score=image.confidence,
        )
        
        # Try to extract forest division from context
        if context_text:
            division_patterns = [
                r'Compartment\s+([A-Z0-9-]+)',
                r'Division\s*[:.]\s*([A-Za-z\s]+)',
                r'Beat\s*[:.]\s*([A-Za-z\s]+)',
                r'Range\s*[:.]\s*([A-Za-z\s]+)',
            ]
            
            for pattern in division_patterns:
                match = re.search(pattern, context_text, re.IGNORECASE)
                if match:
                    if 'Compartment' in pattern:
                        map_info.compartment = match.group(1)
                    elif 'Division' in pattern:
                        map_info.forest_division = match.group(1)
                    elif 'Beat' in pattern:
                        map_info.beat_range = match.group(1)
                    elif 'Range' in pattern:
                        map_info.beat_range = match.group(1)
        
        return map_info
    
    def _extract_photo_info(self, image: ImageMetadata, context_text: str) -> Optional[PhotoInfo]:
        """Extract photo information"""
        if image.image_type != ImageType.PHOTOGRAPH:
            return None
        
        # Create photo object
        photo_info = PhotoInfo(
            photo_id=f"photo_{image.image_id}",
            image_id=image.image_id,
            page_num=image.page_num,
            bbox=image.bbox,
            clarity_score=image.confidence,
        )
        
        # Try to extract photo subject from context
        if context_text:
            # Look for tree species
            species_patterns = [
                r'Species\s*[:.]\s*([A-Za-z\s]+)',
                r'Tree\s+([A-Za-z\s]+)',
                r'Type\s*[:.]\s*([A-Za-z\s]+)',
            ]
            
            for pattern in species_patterns:
                match = re.search(pattern, context_text, re.IGNORECASE)
                if match:
                    photo_info.tree_species = match.group(1).strip()
                    break
            
            # Look for location
            location_patterns = [
                r'Location\s*[:.]\s*([A-Za-z\s,]+)',
                r'Place\s*[:.]\s*([A-Za-z\s,]+)',
                r'Site\s*[:.]\s*([A-Za-z\s,]+)',
            ]
            
            for pattern in location_patterns:
                match = re.search(pattern, context_text, re.IGNORECASE)
                if match:
                    photo_info.location = match.group(1).strip()
                    break
        
        return photo_info
    
    def _update_statistics(self, result: ImageExtractionResult, processing_time: float):
        """Update processor statistics"""
        self.stats['documents_processed'] += 1
        self.stats['processing_time_total'] += processing_time
        
        # Update image counts
        self.stats['images_extracted']['total'] += result.total_images
        self.stats['images_extracted']['signatures'] += result.total_signatures
        self.stats['images_extracted']['stamps'] += result.total_stamps
        self.stats['images_extracted']['maps'] += result.total_maps
        self.stats['images_extracted']['photos'] += result.total_photos
        self.stats['images_extracted']['kpk_official'] += result.kpk_official_images
        
        # Update extraction methods
        for method in result.extraction_methods:
            if method in self.stats['extraction_methods']:
                self.stats['extraction_methods'][method] += 1
        
        # Update image quality metrics
        for image in result.images:
            if image.confidence >= 0.8:
                self.stats['image_quality']['high_quality'] += 1
            elif image.confidence >= 0.5:
                self.stats['image_quality']['medium_quality'] += 1
            else:
                self.stats['image_quality']['low_quality'] += 1
            
            if image.processing_status == ProcessingStatus.ENHANCED:
                self.stats['image_quality']['enhanced'] += 1
        
        # Update OCR statistics
        ocr_stats = self.stats['ocr_results']
        for image in result.images:
            if image.ocr_text:
                ocr_stats['images_with_text'] += 1
                ocr_stats['total_text_chars'] += len(image.ocr_text)
                ocr_stats['avg_confidence'] = (
                    (ocr_stats['avg_confidence'] * (ocr_stats['images_with_text'] - 1) + image.ocr_confidence) 
                    / ocr_stats['images_with_text']
                )
        
        # Update KPK detection statistics
        for image in result.images:
            if image.is_kpk_official:
                if image.image_type == ImageType.OFFICIAL_STAMP:
                    self.stats['kpk_detections']['government_stamps'] += 1
                elif image.image_type == ImageType.SIGNATURE:
                    self.stats['kpk_detections']['official_signatures'] += 1
        
        # Update performance metrics
        perf = self.stats['performance']
        perf['processing_times'].append(processing_time)
        perf['fastest_processing'] = min(perf['fastest_processing'], processing_time)
        perf['slowest_processing'] = max(perf['slowest_processing'], processing_time)
        
        # Calculate averages
        total_docs = self.stats['documents_processed']
        if total_docs > 0:
            self.stats['avg_processing_time'] = self.stats['processing_time_total'] / total_docs
    
    def _log_image_abstention(self, result: ImageExtractionResult, 
                            document_path: Optional[Union[str, Path]]):
        """Log abstention for poor image quality"""
        if self.enable_abstention_logging and self.abstention_logger:
            try:
                context = create_abstention_context(
                    stage=PipelineStage.IMAGE_PROCESSING,
                    component="ImageProcessor",
                    document_path=str(document_path) if document_path else 'unknown',
                    reason="poor_image_quality_or_extraction",
                    details={
                        'confidence_score': result.confidence_score,
                        'images_found': result.total_images,
                        'signatures_found': result.total_signatures,
                        'stamps_found': result.total_stamps,
                        'kpk_official_images': result.kpk_official_images,
                        'extraction_methods': result.extraction_methods,
                    }
                )
                
                self.abstention_logger.log_abstention(
                    abstention_type=AbstentionType.IMAGE_ISSUE,
                    severity=AbstentionSeverity.MEDIUM,
                    context=context,
                    suggested_action="Manual review of images or improve source quality",
                    confidence=1.0 - result.confidence_score,
                    component_state=result.to_dict(),
                )
                
                self.logger.info(f"Logged image abstention for {document_path or 'document'}")
                
            except Exception as e:
                self.logger.warning(f"Failed to log image abstention: {e}")
    
    def _create_error_result(self, document_path: Optional[Union[str, Path]], 
                           error_message: str) -> ImageExtractionResult:
        """Create error result when processing fails"""
        return ImageExtractionResult(
            document_path=str(document_path) if document_path else 'unknown',
            document_hash=hashlib.md5(str(document_path or '').encode()).hexdigest()[:16],
            extraction_timestamp=datetime.now(),
            images=[],
            signatures=[],
            stamps=[],
            maps=[],
            photos=[],
            extraction_errors=[error_message],
            confidence_score=0.0,
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get current processor statistics"""
        stats = self.stats.copy()
        
        # Calculate derived statistics
        total_processed = stats['documents_processed']
        if total_processed > 0:
            stats['avg_processing_time'] = stats['processing_time_total'] / total_processed
            
            # Calculate percentages
            total_images = stats['images_extracted']['total']
            if total_images > 0:
                for key in ['signatures', 'stamps', 'maps', 'photos', 'kpk_official']:
                    count = stats['images_extracted'][key]
                    stats['images_extracted'][f'{key}_pct'] = count / total_images * 100
        
        # Add performance summary
        perf = stats['performance']
        if perf['processing_times']:
            perf['avg_processing_time'] = sum(perf['processing_times']) / len(perf['processing_times'])
        else:
            perf['avg_processing_time'] = 0.0
            perf['fastest_processing'] = 0.0
        
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
# MAIN FUNCTION
# ============================================================================

def main():
    """Main function for standalone testing"""
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description="KPK Image Processor")
    parser.add_argument("--input", required=True, help="Input PDF file")
    parser.add_argument("--output", help="Output directory for images and results")
    parser.add_argument("--config", help="Configuration file (JSON)")
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
        processor = ImageProcessor()
        processor.cleanup_temp_files(args.cleanup_days)
        print(f"Cleanup complete")
        return
    
    # Load configuration
    config = {}
    if args.config:
        with open(args.config, 'r') as f:
            config = json.load(f)
    
    # Initialize processor
    processor = ImageProcessor(config=config)
    
    # Process PDF
    input_path = Path(args.input)
    output_dir = Path(args.output) if args.output else Path("image_extraction_output")
    
    result = processor.process_images(input_path, output_dir=output_dir)
    
    # Save results
    result_file = output_dir / "image_extraction_results.json"
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
    
    print(f"Results saved to {result_file}")
    print(f"Extracted images saved to: {result.extracted_image_dir}")
    print(f"Thumbnails saved to: {result.thumbnail_dir}")
    
    # Print summary
    print(f"\nImage Processing Summary:")
    print(f"  Total Images: {result.total_images}")
    print(f"  Signatures: {result.total_signatures}")
    print(f"  Stamps: {result.total_stamps}")
    print(f"  Maps: {result.total_maps}")
    print(f"  Photos: {result.total_photos}")
    print(f"  KPK Official Images: {result.kpk_official_images}")
    print(f"  Confidence Score: {result.confidence_score:.2%}")
    print(f"  Processing Time: {result.processing_time:.2f}s")
    print(f"  Extraction Methods: {', '.join(result.extraction_methods)}")
    
    if result.images:
        print(f"\nImage Details (first 5):")
        for i, image in enumerate(result.images[:5]):
            print(f"  Image {i+1}: {image.image_type.value} ({image.width_pixels}x{image.height_pixels})")
            if image.is_kpk_official:
                print(f"    KPK Official: Yes")
            if image.ocr_text:
                print(f"    OCR Text: {image.ocr_text[:50]}...")
    
    # Print statistics
    stats = processor.get_statistics()
    print(f"\nProcessor Statistics:")
    print(f"  Documents Processed: {stats['documents_processed']}")
    print(f"  Total Images Extracted: {stats['images_extracted']['total']}")
    print(f"  KPK Official Images: {stats['images_extracted']['kpk_official']}")
    print(f"  Average Processing Time: {stats['avg_processing_time']:.2f}s")

if __name__ == "__main__":
    main()
