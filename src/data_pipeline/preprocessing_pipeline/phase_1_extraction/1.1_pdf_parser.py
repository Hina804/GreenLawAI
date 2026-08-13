"""
PDF_PARSER.PY - Phase 1.1: PDF Text Extraction with Layout Preservation
Extracts text from KPK forestry PDFs while preserving document structure.
Author: Hina Ali, Eman Irfan
Date: January 29, 2026
"""

import os
import logging
import json
import re
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, asdict, field
from datetime import datetime
import tempfile
import sys

# Third-party imports
import pdfplumber
import pymupdf  # PyMuPDF
from PIL import Image
import numpy as np

# Import from common modules
try:
    from preprocessing_pipeline.common.config import PipelineConfig, PDFParsingConfig
    from preprocessing_pipeline.common.constants import *
    USE_COMMON_CONFIG = True
except ImportError:
    USE_COMMON_CONFIG = False
    print("Warning: common.config not found. Using default configuration.")

# Import from previous phases
try:
    from preprocessing_pipeline.phase_0_foundation import (
        AbstentionLogger, AbstentionType, AbstentionSeverity, 
        PipelineStage, create_abstention_context,
        DocProfiler, DocumentProfile, DocumentQualityAssessor, QualityAssessment
    )
    PHASE_0_MODULES_AVAILABLE = True
except ImportError:
    PHASE_0_MODULES_AVAILABLE = False
    DocProfiler = None
    DocumentProfile = None
    DocumentQualityAssessor = None
    QualityAssessment = Any
    AbstentionLogger = None
    AbstentionType = None
    AbstentionSeverity = None
    PipelineStage = None
    create_abstention_context = None
    print("Warning: Phase 0 modules not available. Running in standalone mode.")

# ============================================================================
# CONFIGURATION
# ============================================================================

class PDFParsingConfig:
    """Configuration for PDF parsing"""
    
    # Extraction methods (in order of preference)
    EXTRACTION_METHODS = ["pdfplumber", "pymupdf", "ocr_fallback"]
    
    # Layout preservation
    PRESERVE_LAYOUT = True
    DETECT_COLUMNS = True
    PRESERVE_TABLES = True
    EXTRACT_METADATA = True
    PRESERVE_FORMATTING = True
    
    # Text cleaning
    REMOVE_HYPHENATION = True
    FIX_LINE_BREAKS = True
    NORMALIZE_WHITESPACE = True
    REMOVE_HEADERS_FOOTERS = True
    PRESERVE_PAGE_NUMBERS = False
    
    # KPK-specific
    DETECT_KPK_PATTERNS = True
    EXTRACT_KPK_METADATA = True
    IDENTIFY_KPK_DOC_TYPES = True
    
    # Performance
    PARALLEL_PROCESSING = False
    BATCH_SIZE = 5
    MAX_PAGES = None  # None = all pages
    PAGE_CHUNK_SIZE = 10
    
    # Error handling
    CONTINUE_ON_ERROR = True
    LOG_ERRORS = True
    RETRY_FAILED_PAGES = True
    MAX_RETRIES = 2
    
    # Quality thresholds
    MIN_TEXT_DENSITY = 0.01  # Minimum text per page area
    MIN_WORDS_PER_PAGE = 10
    OCR_FALLBACK_THRESHOLD = 0.3  # Use OCR if <30% text extracted
    
    # Table extraction
    EXTRACT_TABLES = True
    MIN_TABLE_ROWS = 2
    MIN_TABLE_COLUMNS = 2
    PRESERVE_TABLE_STRUCTURE = True
    
    # Image extraction
    EXTRACT_IMAGES = False  # Can be memory intensive
    MIN_IMAGE_SIZE = 100  # pixels
    MAX_IMAGE_EXTRACTION = 10  # Max images per document
    
    # Output
    SAVE_PARSED_TEXT = True
    SAVE_METADATA = True
    SAVE_STRUCTURE = True
    COMPRESS_OUTPUT = False

# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class TextBlock:
    """Represents a block of text with layout information"""
    text: str
    bbox: Tuple[float, float, float, float]  # x0, y0, x1, y1
    page_num: int
    block_type: str  # 'paragraph', 'heading', 'list_item', 'table', 'caption', 'header', 'footer'
    font_size: Optional[float] = None
    font_name: Optional[str] = None
    is_bold: Optional[bool] = None
    is_italic: Optional[bool] = None
    language: Optional[str] = None  # 'en', 'ur', 'mixed'
    confidence: float = 1.0
    children: List['TextBlock'] = field(default_factory=list)  # For nested structures
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['children'] = [child.to_dict() for child in self.children]
        return data
    
    @property
    def area(self) -> float:
        """Calculate block area"""
        x0, y0, x1, y1 = self.bbox
        return (x1 - x0) * (y1 - y0)
    
    @property
    def aspect_ratio(self) -> float:
        """Calculate aspect ratio (width/height)"""
        x0, y0, x1, y1 = self.bbox
        width = x1 - x0
        height = y1 - y0
        return width / height if height > 0 else 0

@dataclass
class PDFPage:
    """Represents a parsed PDF page"""
    page_number: int
    width: float
    height: float
    text_blocks: List[TextBlock]
    images: List[Dict[str, Any]] = field(default_factory=list)
    tables: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Text content
    raw_text: str = ""
    cleaned_text: str = ""
    
    # Statistics
    word_count: int = 0
    char_count: int = 0
    text_density: float = 0.0
    
    # Layout information
    columns: List[Dict[str, Any]] = field(default_factory=list)
    margins: Dict[str, float] = field(default_factory=dict)
    headings: List[Dict[str, Any]] = field(default_factory=list)
    
    # Processing information
    parsing_method: Optional[str] = None
    parsing_errors: List[str] = field(default_factory=list)
    parsing_warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['text_blocks'] = [block.to_dict() for block in self.text_blocks]
        return data
    
    def get_text_by_type(self, block_type: str) -> str:
        """Get text from specific block types"""
        blocks = [block for block in self.text_blocks if block.block_type == block_type]
        return " ".join(block.text for block in blocks)
    
    def get_main_text(self) -> str:
        """Get main text (excluding headers, footers, etc.)"""
        excluded_types = ['header', 'footer', 'page_number', 'watermark']
        blocks = [block for block in self.text_blocks 
                 if block.block_type not in excluded_types]
        return " ".join(block.text for block in blocks)

@dataclass
class PDFParseResult:
    """Result of PDF parsing"""
    # Document identification
    document_path: str
    document_hash: str
    parsing_timestamp: datetime
    
    # Parsing results
    pages: List[PDFPage]
    metadata: Dict[str, Any]
    kpk_metadata: Dict[str, Any]
    structure: Dict[str, Any]
    
    # Processing information
    parsing_method: str
    parsing_duration: float  # seconds
    success_rate: float  # 0-1
    
    # Statistics
    total_pages: int
    total_words: int
    total_characters: int
    average_words_per_page: float
    
    # KPK-specific
    is_kpk_document: bool = False
    kpk_document_type: Optional[str] = None
    kpk_jurisdiction: Optional[str] = None
    
    # Quality indicators
    has_tables: bool = False
    has_images: bool = False
    has_ocr_content: bool = False
    layout_preserved: bool = False
    
    # Errors and warnings
    parsing_errors: List[str] = field(default_factory=list)
    parsing_warnings: List[str] = field(default_factory=list)
    
    # Abstention information
    abstention_reasons: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Calculate derived fields"""
        # Calculate KPK relevance if not already set
        if not hasattr(self, 'is_kpk_document'):
            self.is_kpk_document = self._calculate_kpk_relevance()
        
        # Calculate layout preservation score
        if not hasattr(self, 'layout_preserved'):
            self.layout_preserved = self._calculate_layout_preservation()
    
    def _calculate_kpk_relevance(self) -> bool:
        """Calculate if document is KPK-related"""
        # Check metadata
        if self.kpk_metadata.get('is_kpk_document', False):
            return True
        
        # Check text content
        kpk_keywords = ['kpk', 'khyber', 'pakhtunkhwa', 'hazara', 'malakand', 'خیبر', 'پختونخوا']
        all_text = self.get_all_text().lower()
        
        for keyword in kpk_keywords:
            if keyword in all_text:
                return True
        
        return False
    
    def _calculate_layout_preservation(self) -> bool:
        """Calculate if layout was preserved"""
        if not self.pages:
            return False
        
        # Check if we have text blocks with bounding boxes
        pages_with_blocks = sum(1 for page in self.pages if page.text_blocks)
        pages_with_layout = sum(1 for page in self.pages if page.columns or page.margins)
        
        return (pages_with_blocks / len(self.pages) > 0.5 or 
                pages_with_layout / len(self.pages) > 0.3)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['pages'] = [page.to_dict() for page in self.pages]
        data['parsing_timestamp'] = self.parsing_timestamp.isoformat()
        return data
    
    def get_all_text(self) -> str:
        """Get all text from document"""
        return "\n".join(page.cleaned_text for page in self.pages)
    
    def get_structured_text(self) -> Dict[str, List[str]]:
        """Get text organized by structure"""
        structured = {
            'headings': [],
            'paragraphs': [],
            'tables': [],
            'lists': [],
            'captions': [],
        }
        
        for page in self.pages:
            for block in page.text_blocks:
                if block.block_type in structured:
                    structured[block.block_type].append(block.text)
        
        return structured
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get document statistics"""
        return {
            'total_pages': self.total_pages,
            'total_words': self.total_words,
            'total_characters': self.total_characters,
            'average_words_per_page': self.average_words_per_page,
            'kpk_relevance_score': self.is_kpk_document,
            'has_tables': self.has_tables,
            'has_images': self.has_images,
            'layout_preserved': self.layout_preserved,
            'parsing_success_rate': self.success_rate,
            'parsing_method': self.parsing_method,
        }

# ============================================================================
# KPK PDF PARSER
# ============================================================================

class KPKPDFParser:
    """
    PDF parser optimized for KPK forestry documents.
    Preserves document structure, handles multi-column layouts,
    and extracts metadata.
    """
    
    def __init__(self, 
                 config: Optional[Union[PDFParsingConfig, Dict]] = None,
                 enable_abstention_logging: bool = True,
                 logger: Optional[logging.Logger] = None):
        """
        Initialize PDF parser with KPK-specific configuration.
        
        Args:
            config: Configuration object or dictionary
            enable_abstention_logging: Whether to log abstentions
            logger: Optional logger instance
        """
        
        # Configuration (ignore unrelated PipelineConfig from orchestrator)
        if isinstance(config, PDFParsingConfig):
            self.config = config
        elif isinstance(config, dict):
            self.config = PDFParsingConfig()
            for key, value in config.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
        else:
            self.config = PDFParsingConfig()
        
        # Setup logging
        self.logger = logger or self._setup_logging()
        
        # Abstention logging
        self.enable_abstention_logging = enable_abstention_logging
        self.abstention_logger = None
        if enable_abstention_logging and PHASE_0_MODULES_AVAILABLE:
            try:
                self.abstention_logger = AbstentionLogger()
            except Exception as e:
                self.logger.warning(f"Could not initialize abstention logger: {e}")
        
        # KPK patterns
        self.kpk_patterns = self._load_kpk_patterns()
        
        # Statistics
        self.stats = self._init_statistics()
        
        # Cache for document hashes
        self._document_cache = {}
        
        self.logger.info("KPKPDFParser initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging"""
        logger = logging.getLogger('KPKPDFParser')
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
            'documents_parsed': 0,
            'total_pages_parsed': 0,
            'parsing_time_total': 0.0,
            'avg_parsing_time': 0.0,
            
            'by_parsing_method': {
                'pdfplumber': 0,
                'pymupdf': 0,
                'ocr_fallback': 0,
                'hybrid': 0,
            },
            
            'kpk_documents': 0,
            'hazara_documents': 0,
            'malakand_documents': 0,
            
            'success_rate': 0.0,
            'avg_success_rate': 0.0,
            
            'tables_extracted': 0,
            'images_extracted': 0,
            'ocr_pages': 0,
            
            'issues': {
                'parsing_errors': 0,
                'low_text_density': 0,
                'layout_issues': 0,
                'kpk_identification_failed': 0,
            },
            
            'performance': {
                'fastest_parse': float('inf'),
                'slowest_parse': 0.0,
                'parse_times': [],
            },
        }
    
    def _load_kpk_patterns(self) -> Dict[str, List[str]]:
        """Load KPK-specific patterns for document analysis"""
        return {
            "document_type_indicators": [
                # English patterns
                r"KHYBER\s+PAKHTUNKHWA\s+FOREST",
                r"KPK\s+FOREST\s+(?:ORDINANCE|ACT|DEPARTMENT)",
                r"HAZARA\s+FOREST\s+(?:ACT|DIVISION)",
                r"MALAKAND\s+FOREST",
                r"FOREST\s+DEPARTMENT\s+(?:KPK|KHYBER)",
                r"GOVERNMENT\s+OF\s+KHYBER\s+PAKHTUNKHWA",
                
                # Urdu patterns
                r"حکومتِ خیبر پختونخوا",
                r"محکمہ جنگلات",
                r"خیبر پختونخوا جنگلات",
                r"ہزارہ ڈویژن",
                r"مالاکنڈ ڈویژن",
                r"جنگلات کا محکمہ",
                
                # Legal document patterns
                r"ORDINANCE\s+NO\.?\s*[IVXLCDM]+\s+OF\s+\d{4}",
                r"ACT\s+NO\.?\s*\d+\s+OF\s+\d{4}",
                r"S\.?R\.?O\.?\s+NO\.?\s*\d+\s+OF\s+\d{4}",
                r"NOTIFICATION\s+NO\.?\s*\d+",
            ],
            
            "section_patterns": [
                r"Section\s+\d+[A-Z]?",
                r"Sec\.\s*\d+[A-Z]?",
                r"SECTION\s+\d+[A-Z]?",
                r"فصل\s+\d+",
                r"دفعہ\s+\d+",
                r"\d+\.\s+[A-Z]",  # Numbered sections
                r"Article\s+\d+",
                r"Clause\s+\d+",
            ],
            
            "penalty_patterns": [
                r"fine\s+of\s+Rs\.?\s*[\d,]+(?:\s*/\s*[a-zA-Z]+)?",
                r"penalty\s+of\s+Rs\.?\s*[\d,]+",
                r"punishable\s+with\s+(?:imprisonment|fine)",
                r"liable\s+to\s+(?:imprisonment|fine)",
                r"جرمانہ\s+[\d,]+(?:\s*روپے)?",
                r"سزا\s+(?:قید|جرمانہ)",
                r"ماخوذ ہوگا",
            ],
            
            "officer_patterns": [
                r"DFO\s*\([^)]+\)",
                r"Divisional Forest Officer",
                r"Range\s+Officer",
                r"Forest\s+Guard",
                r"Conservator\s+of\s+Forests",
                r"ڈویژنل فارسٹ آفیسر",
                r"رینج آفیسر",
                r"فارسٹ گارڈ",
                r"محافظ جنگلات",
            ],
            
            "date_patterns": [
                r"\d{1,2}[-/]\d{1,2}[-/]\d{4}",
                r"\d{4}[-/]\d{1,2}[-/]\d{1,2}",
                r"\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}",
                r"\d{1,2}\s+(?:جنوری|فروری|مارچ|اپریل|مئی|جون|جولائی|اگست|ستمبر|اکتوبر|نومبر|دسمبر)\s+\d{4}",
                r"(?:مئی|جون|جولائی|اگست|ستمبر)\s+\d{4}",
            ],
            
            "geographic_patterns": [
                r"Hazara\s+Division",
                r"Malakand\s+Division",
                r"Peshawar\s+Division",
                r"Kohat\s+Division",
                r"Bannu\s+Division",
                r"D\.?I\.?\.?Khan\s+Division",
                r"ہزارہ ڈویژن",
                r"مالاکنڈ ڈویژن",
                r"پشاور ڈویژن",
                r"کوہاٹ ڈویژن",
                r"بنوں ڈویژن",
                r"ڈیرہ اسماعیل خان ڈویژن",
            ],
            
            "species_patterns": [
                r"Chir\s+Pine",
                r"Deodar",
                r"Kail",
                r"Partal",
                r"چلغوزہ",
                r"دیودار",
                r"چلغوزہ کے درخت",
                r"صنوبر",
            ],
        }
    
    def parse_pdf(self, 
                  pdf_path: Union[str, Path],
                  pages: Optional[List[int]] = None,
                  profile: Optional[DocumentProfile] = None,
                  quality_assessment: Optional[QualityAssessment] = None) -> PDFParseResult:
        """
        Parse PDF document with structure preservation.
        
        Args:
            pdf_path: Path to PDF file
            pages: Specific pages to parse (None = all pages)
            profile: Optional document profile from Phase 0.1
            quality_assessment: Optional quality assessment from Phase 0.4
            
        Returns:
            PDFParseResult object with parsed content and structure
        """
        import time
        start_time = time.time()
        
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        
        self.logger.info(f"Starting PDF parsing: {pdf_path.name}")
        
        # Generate document hash for caching/identification
        document_hash = self._calculate_document_hash(pdf_path)
        
        # Check cache
        cache_key = f"{document_hash}_{pages}"
        if cache_key in self._document_cache:
            self.logger.info(f"Returning cached result for {pdf_path.name}")
            return self._document_cache[cache_key]
        
        try:
            # Try different parsing methods in order
            parsing_methods = self.config.EXTRACTION_METHODS
            parse_results = []
            parsing_method_used = None
            
            for method in parsing_methods:
                try:
                    self.logger.debug(f"Trying parsing method: {method}")
                    
                    if method == "pdfplumber":
                        result = self._parse_with_pdfplumber(pdf_path, pages)
                        parsing_method_used = "pdfplumber"
                        
                    elif method == "pymupdf":
                        result = self._parse_with_pymupdf(pdf_path, pages)
                        parsing_method_used = "pymupdf"
                        
                    elif method == "ocr_fallback":
                        # This integrates with ocr_engine.py (Phase 1.5)
                        result = self._parse_with_ocr_fallback(pdf_path, pages)
                        parsing_method_used = "ocr_fallback"
                        
                    else:
                        continue
                    
                    # Check if parsing was successful enough
                    if self._is_parsing_successful(result):
                        parse_results.append((method, result))
                        break
                    else:
                        self.logger.warning(f"Parsing method {method} produced insufficient results")
                        parse_results.append((method, result))
                        
                except Exception as e:
                    self.logger.warning(f"Parsing method {method} failed: {e}")
                    if self.config.CONTINUE_ON_ERROR:
                        continue
                    else:
                        raise
            
            # If no method succeeded individually, try hybrid approach
            if not parse_results or not self._is_parsing_successful(parse_results[-1][1]):
                self.logger.info("Attempting hybrid parsing approach")
                hybrid_result = self._parse_hybrid(pdf_path, pages, parse_results)
                if hybrid_result:
                    parse_results.append(("hybrid", hybrid_result))
                    parsing_method_used = "hybrid"
            
            # Get the best result
            if not parse_results:
                raise Exception("All parsing methods failed")
            
            # Use the last successful result
            parsing_method_used = parse_results[-1][0]
            parsed_data = parse_results[-1][1]
            
            # Enhance with KPK metadata
            kpk_metadata = self._extract_kpk_metadata(parsed_data)
            
            # Analyze structure
            structure = self._analyze_structure(parsed_data)
            
            # Calculate success rate
            success_rate = self._calculate_success_rate(parsed_data)
            
            # Create PDFParseResult
            result = PDFParseResult(
                document_path=str(pdf_path),
                document_hash=document_hash,
                parsing_timestamp=datetime.now(),
                
                pages=parsed_data.get("pages", []),
                metadata=parsed_data.get("metadata", {}),
                kpk_metadata=kpk_metadata,
                structure=structure,
                
                parsing_method=parsing_method_used,
                parsing_duration=time.time() - start_time,
                success_rate=success_rate,
                
                total_pages=len(parsed_data.get("pages", [])),
                total_words=parsed_data.get("text_statistics", {}).get("total_words", 0),
                total_characters=parsed_data.get("text_statistics", {}).get("total_characters", 0),
                average_words_per_page=parsed_data.get("text_statistics", {}).get("average_words_per_page", 0),
                
                is_kpk_document=kpk_metadata.get("is_kpk_document", False),
                kpk_document_type=kpk_metadata.get("document_type"),
                kpk_jurisdiction=kpk_metadata.get("jurisdiction"),
                
                has_tables=bool(parsed_data.get("tables")),
                has_images=bool(parsed_data.get("images")),
                has_ocr_content=parsed_data.get("has_ocr_content", False),
                
                parsing_errors=parsed_data.get("errors", []),
                parsing_warnings=parsed_data.get("warnings", []),
            )
            
            # Cache the result
            self._document_cache[cache_key] = result
            
            # Update statistics
            self._update_statistics(result, time.time() - start_time)
            
            # Log abstention if parsing quality is poor
            if (self.enable_abstention_logging and self.abstention_logger and 
                success_rate < 0.5):
                
                self._log_parsing_abstention(result, pdf_path)
            
            self.logger.info(
                f"PDF parsing complete: {pdf_path.name} - "
                f"Method: {parsing_method_used}, "
                f"Pages: {len(result.pages)}, "
                f"Success: {success_rate:.2%}, "
                f"KPK: {result.is_kpk_document}"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"PDF parsing failed for {pdf_path.name}: {e}")
            
            # Create minimal result with error
            return self._create_error_result(pdf_path, str(e))
    
    def _calculate_document_hash(self, pdf_path: Path) -> str:
        """Calculate hash for document identification"""
        try:
            # Use file metadata for hash
            stat = pdf_path.stat()
            hash_input = f"{pdf_path.name}_{stat.st_size}_{stat.st_mtime}"
            return hashlib.md5(hash_input.encode()).hexdigest()[:16]
        except:
            return hashlib.md5(str(pdf_path).encode()).hexdigest()[:16]
    
    def _is_parsing_successful(self, parsed_data: Dict) -> bool:
        """Check if parsing produced sufficient results"""
        if not parsed_data or "pages" not in parsed_data:
            return False
        
        pages = parsed_data.get("pages", [])
        if not pages:
            return False
        
        # Check text density
        total_words = parsed_data.get("text_statistics", {}).get("total_words", 0)
        if total_words < len(pages) * self.config.MIN_WORDS_PER_PAGE:
            return False
        
        return True
    
    def _parse_with_pdfplumber(self, pdf_path: Path, pages: Optional[List[int]]) -> Dict[str, Any]:
        """Parse PDF using pdfplumber (best for text-based PDFs)"""
        results = {
            "pages": [],
            "metadata": {},
            "text_statistics": {},
            "tables": [],
            "images": [],
            "errors": [],
            "warnings": [],
            "has_ocr_content": False,
        }
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                # Extract metadata
                results["metadata"] = self._extract_pdf_metadata(pdf.metadata)
                
                # Determine pages to process
                total_pages = len(pdf.pages)
                if pages is None:
                    pages_to_process = range(total_pages)
                else:
                    pages_to_process = [p-1 for p in pages if 0 <= p-1 < total_pages]
                
                if self.config.MAX_PAGES:
                    pages_to_process = pages_to_process[:self.config.MAX_PAGES]
                
                # Process pages in chunks if configured
                if self.config.PAGE_CHUNK_SIZE and len(pages_to_process) > self.config.PAGE_CHUNK_SIZE:
                    self.logger.info(f"Processing {len(pages_to_process)} pages in chunks")
                    chunked_pages = self._chunk_pages(pages_to_process, self.config.PAGE_CHUNK_SIZE)
                else:
                    chunked_pages = [pages_to_process]
                
                total_text = ""
                total_words = 0
                
                for chunk in chunked_pages:
                    for page_idx in chunk:
                        page_num = page_idx + 1
                        try:
                            page = pdf.pages[page_idx]
                            page_result = self._parse_pdfplumber_page(page, page_num)
                            
                            results["pages"].append(page_result)
                            
                            # Accumulate statistics
                            total_text += page_result.raw_text + " "
                            total_words += page_result.word_count
                            
                        except Exception as e:
                            error_msg = f"Page {page_num}: {str(e)}"
                            results["errors"].append(error_msg)
                            self.logger.warning(error_msg)
                            
                            # Create empty page result
                            empty_page = PDFPage(
                                page_number=page_num,
                                width=0,
                                height=0,
                                text_blocks=[],
                                parsing_errors=[error_msg]
                            )
                            results["pages"].append(empty_page)
                
                # Calculate overall statistics
                results["text_statistics"] = {
                    "total_pages": len(results["pages"]),
                    "total_characters": len(total_text),
                    "total_words": total_words,
                    "average_words_per_page": total_words / len(results["pages"]) if results["pages"] else 0,
                    "estimated_reading_time_minutes": total_words / 200,  # 200 wpm
                }
                
                # Extract tables if enabled
                if self.config.EXTRACT_TABLES:
                    results["tables"] = self._extract_tables_with_pdfplumber(pdf, pages_to_process)
                
                # Check for OCR content
                results["has_ocr_content"] = self._detect_ocr_content(results)
                
        except Exception as e:
            results["errors"].append(f"PDFPlumber parsing failed: {str(e)}")
            self.logger.error(f"PDFPlumber parsing failed: {e}")
        
        return results
    
    def _extract_pdf_metadata(self, raw_metadata: Dict) -> Dict[str, Any]:
        """Extract and clean PDF metadata"""
        metadata = {
            "author": raw_metadata.get("Author"),
            "title": raw_metadata.get("Title"),
            "subject": raw_metadata.get("Subject"),
            "creator": raw_metadata.get("Creator"),
            "producer": raw_metadata.get("Producer"),
            "creation_date": raw_metadata.get("CreationDate"),
            "modification_date": raw_metadata.get("ModDate"),
            "keywords": raw_metadata.get("Keywords"),
        }
        
        # Clean up values
        for key, value in metadata.items():
            if value and isinstance(value, str):
                # Remove PDF-specific encoding artifacts
                value = value.replace("\x00", "").strip()
                if value.startswith("D:"):  # PDF date format
                    value = self._parse_pdf_date(value)
                metadata[key] = value
        
        return metadata
    
    def _parse_pdf_date(self, date_str: str) -> str:
        """Parse PDF date format (D:YYYYMMDDHHMMSS)"""
        try:
            if date_str.startswith("D:"):
                date_str = date_str[2:]
            
            # Extract date components
            year = date_str[:4] if len(date_str) >= 4 else "0000"
            month = date_str[4:6] if len(date_str) >= 6 else "01"
            day = date_str[6:8] if len(date_str) >= 8 else "01"
            
            return f"{year}-{month}-{day}"
        except:
            return date_str
    
    def _chunk_pages(self, pages: List[int], chunk_size: int) -> List[List[int]]:
        """Split pages into chunks"""
        return [pages[i:i + chunk_size] for i in range(0, len(pages), chunk_size)]
    
    def _parse_pdfplumber_page(self, page, page_num: int) -> PDFPage:
        """Parse single page with pdfplumber"""
        
        # Initialize page result
        page_result = PDFPage(
            page_number=page_num,
            width=page.width,
            height=page.height,
            text_blocks=[],
        )
        
        try:
            # Extract text with layout
            if self.config.PRESERVE_LAYOUT:
                text = page.extract_text(
                    layout=True,
                    keep_blank_chars=False,
                    x_tolerance=3,
                    y_tolerance=3,
                    use_text_flow=True,
                ) or ""
            else:
                text = page.extract_text() or ""
            
            page_result.raw_text = text
            page_result.word_count = len(text.split())
            page_result.char_count = len(text)
            
            # Clean text
            clean_text = self._clean_text(text)
            page_result.cleaned_text = clean_text
            
            # Extract text blocks with positions if layout preservation is enabled
            if self.config.PRESERVE_LAYOUT:
                try:
                    words = page.extract_words(
                        x_tolerance=3,
                        y_tolerance=3,
                        keep_blank_chars=False,
                        use_text_flow=True,
                        extra_attrs=["fontname", "size", "object_type"],
                    )
                    
                    # Group words into text blocks
                    text_blocks = self._create_text_blocks_from_words(words, page_num)
                    page_result.text_blocks = text_blocks
                    
                    # Fallback: If text is empty but blocks exist, reconstruct text
                    if not text.strip() and text_blocks:
                        reconstructed = "\n".join([b.text for b in text_blocks])
                        page_result.raw_text = reconstructed
                        page_result.cleaned_text = self._clean_text(reconstructed)
                    
                    # Analyze layout
                    layout_info = self._analyze_page_layout(words, page.width, page.height)
                    page_result.columns = layout_info.get("columns", [])
                    page_result.margins = layout_info.get("margins", {})
                    page_result.headings = layout_info.get("headings", [])
                    
                except Exception as e:
                    self.logger.debug(f"Layout analysis failed for page {page_num}: {e}")
                    page_result.parsing_warnings.append(f"Layout analysis: {str(e)}")
            
            # Extract fonts if available
            try:
                chars = page.chars
                fonts = {char.get("fontname") for char in chars if char.get("fontname")}
                page_result.metadata["fonts"] = list(fonts)
            except:
                pass
            
            # Calculate text density
            if page.width > 0 and page.height > 0:
                page_result.text_density = page_result.word_count / (page.width * page.height)
            
            # Check for KPK patterns
            if self.config.DETECT_KPK_PATTERNS:
                kpk_patterns_found = self._find_kpk_patterns_in_text(text)
                if kpk_patterns_found:
                    page_result.metadata["kpk_patterns"] = kpk_patterns_found
            
            # Set parsing method
            page_result.parsing_method = "pdfplumber"
            
        except Exception as e:
            error_msg = f"Page parsing failed: {str(e)}"
            page_result.parsing_errors.append(error_msg)
            self.logger.warning(f"Error parsing page {page_num} with pdfplumber: {e}")
        
        return page_result
    
    def _create_text_blocks_from_words(self, words: List[Dict], page_num: int) -> List[TextBlock]:
        """Create text blocks from extracted words"""
        if not words:
            return []
        
        # Sort words by position
        sorted_words = sorted(words, key=lambda w: (w.get("top", 0), w.get("x0", 0)))
        
        blocks = []
        current_line = []
        current_y = None
        y_tolerance = 5
        
        for word in sorted_words:
            word_y = word.get("top", 0)
            word_text = word.get("text", "").strip()
            
            if not word_text:
                continue
            
            if current_y is None:
                current_y = word_y
                current_line.append(word)
            elif abs(word_y - current_y) <= y_tolerance:
                # Same line
                current_line.append(word)
            else:
                # New line - create block from current line
                if current_line:
                    block = self._create_block_from_line(current_line, page_num)
                    if block:
                        blocks.append(block)
                current_line = [word]
                current_y = word_y
        
        # Add last line
        if current_line:
            block = self._create_block_from_line(current_line, page_num)
            if block:
                blocks.append(block)
        
        return blocks
    
    def _create_block_from_line(self, words: List[Dict], page_num: int) -> Optional[TextBlock]:
        """Create a text block from a line of words"""
        if not words:
            return None
        
        # Calculate bounding box
        x0 = min(w.get("x0", 0) for w in words)
        y0 = min(w.get("top", 0) for w in words)
        x1 = max(w.get("x1", 0) for w in words)
        y1 = max(w.get("bottom", 0) for w in words)
        
        # Extract text
        text = " ".join(w.get("text", "").strip() for w in words)
        
        # Get font information
        font_name = words[0].get("fontname") if words else None
        font_size = words[0].get("size") if words else None
        
        # Determine block type
        block_type = self._determine_block_type(text, words)
        
        # Determine language
        language = self._detect_language(text)
        
        return TextBlock(
            text=text,
            bbox=(x0, y0, x1, y1),
            page_num=page_num,
            block_type=block_type,
            font_name=font_name,
            font_size=font_size,
            language=language,
        )
    
    def _determine_block_type(self, text: str, words: List[Dict]) -> str:
        """Determine the type of text block"""
        if not text:
            return "unknown"
        
        # Check for headers/footers
        if self._is_header_or_footer(text, words):
            return "header_footer"
        
        # Check for page numbers
        if text.strip().isdigit() and len(text.strip()) <= 4:
            return "page_number"
        
        # Check for headings
        if self._is_heading(text, words):
            return "heading"
        
        # Check for list items
        if re.match(r'^[•\-*◦›»]\s+', text) or re.match(r'^\d+[\.\)]\s+', text):
            return "list_item"
        
        # Check for captions
        if re.match(r'^(?:Figure|Table|Fig\.|Tab\.)\s+\d+', text, re.IGNORECASE):
            return "caption"
        
        # Default to paragraph
        return "paragraph"
    
    def _is_header_or_footer(self, text: str, words: List[Dict]) -> bool:
        """Check if text is likely a header or footer"""
        if not text or not words:
            return False
        
        # Check position on page
        first_word = words[0]
        last_word = words[-1]
        
        # Headers are typically at the top
        if first_word.get("top", 0) < 100:  # Within 100 pixels from top
            return True
        
        # Footers are typically at the bottom
        if last_word.get("bottom", 0) > 700:  # Within 100 pixels from bottom (assuming 800px height)
            return True
        
        # Check for common header/footer patterns
        header_patterns = [
            r'^\d+$',  # Page numbers
            r'^Chapter\s+\d+',
            r'^Section\s+\d+',
            r'^\d+/\d+/\d+',  # Dates
        ]
        
        for pattern in header_patterns:
            if re.match(pattern, text.strip()):
                return True
        
        return False
    
    def _is_heading(self, text: str, words: List[Dict]) -> bool:
        """Check if text is likely a heading"""
        if not text:
            return False
        
        # Heading heuristics
        is_all_caps = text.isupper()
        is_title_case = text.istitle()
        has_short_length = len(text.split()) <= 10
        
        # Check font characteristics if available
        is_large_font = False
        is_bold = False
        
        if words:
            avg_font_size = sum(w.get("size", 0) for w in words) / len(words)
            is_large_font = avg_font_size > 12  # Larger than normal text
            
            # Check for bold (simplified)
            font_name = words[0].get("fontname", "").lower()
            is_bold = "bold" in font_name or "b" in font_name or "bd" in font_name
        
        # Heading if:
        # 1. All caps and short
        # 2. Title case and large font
        # 3. Short and bold
        return ((is_all_caps and has_short_length) or
                (is_title_case and is_large_font) or
                (has_short_length and is_bold))
    
    def _detect_language(self, text: str) -> str:
        """Detect language of text"""
        if not text:
            return "unknown"
        
        # Count characters
        english_chars = len(re.findall(r'[a-zA-Z]', text))
        urdu_chars = len(re.findall(r'[\u0600-\u06FF]', text))
        total_chars = len(text)
        
        if total_chars == 0:
            return "unknown"
        
        english_ratio = english_chars / total_chars
        urdu_ratio = urdu_chars / total_chars
        
        if english_ratio > 0.8:
            return "en"
        elif urdu_ratio > 0.8:
            return "ur"
        elif english_ratio > 0.3 and urdu_ratio > 0.3:
            return "mixed"
        else:
            return "unknown"
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize extracted text"""
        if not text:
            return ""
        
        cleaned = text
        
        # Remove hyphenation at line breaks
        if self.config.REMOVE_HYPHENATION:
            cleaned = re.sub(r'(\w)-\s+(\w)', r'\1\2', cleaned)
        
        # Fix line breaks in middle of sentences
        if self.config.FIX_LINE_BREAKS:
            # Join lines that don't end with punctuation
            lines = cleaned.split('\n')
            joined_lines = []
            
            for i, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue
                
                # Check if line should be joined with next
                if (i < len(lines) - 1 and 
                    not re.search(r'[.!?:۔؟]$', line) and
                    lines[i+1].strip() and
                    not lines[i+1].strip()[0].isupper()):
                    # Join with next line
                    if joined_lines:
                        joined_lines[-1] = joined_lines[-1] + " " + line
                    else:
                        joined_lines.append(line)
                else:
                    if joined_lines and not re.search(r'[.!?:۔؟]$', joined_lines[-1]):
                        joined_lines[-1] = joined_lines[-1] + " " + line
                    else:
                        joined_lines.append(line)
            
            cleaned = '\n'.join(joined_lines)
        
        # Normalize whitespace
        if self.config.NORMALIZE_WHITESPACE:
            cleaned = re.sub(r'\s+', ' ', cleaned)  # Multiple spaces to single
            cleaned = re.sub(r'\s*\.\s*', '. ', cleaned)  # Fix spacing around periods
            cleaned = re.sub(r'\s*,\s*', ', ', cleaned)   # Fix spacing around commas
            cleaned = re.sub(r'\s*;\s*', '; ', cleaned)   # Fix spacing around semicolons
            cleaned = re.sub(r'\s*:\s*', ': ', cleaned)   # Fix spacing around colons
        
        # Remove headers/footers if configured
        if self.config.REMOVE_HEADERS_FOOTERS:
            # Simple header/footer removal (can be enhanced)
            lines = cleaned.split('\n')
            filtered_lines = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Skip likely page numbers
                if line.isdigit() and len(line) <= 4:
                    continue
                
                # Skip short lines at beginning/end
                if len(line.split()) <= 3:
                    continue
                
                filtered_lines.append(line)
            
            cleaned = '\n'.join(filtered_lines)
        
        return cleaned.strip()
    
    def _analyze_page_layout(self, words: List[Dict], page_width: float, page_height: float) -> Dict[str, Any]:
        """Analyze page layout structure"""
        if not words:
            return {}
        
        # Find columns
        columns = self._detect_columns(words, page_width)
        
        # Find margins
        margins = self._detect_margins(words, page_width, page_height)
        
        # Find headings
        headings = self._detect_headings(words)
        
        return {
            "columns": columns,
            "margins": margins,
            "headings": headings,
            "word_density": len(words) / (page_width * page_height) if page_width * page_height > 0 else 0,
        }
    
    def _detect_columns(self, words: List[Dict], page_width: float) -> List[Dict]:
        """Detect text columns on page"""
        if not words:
            return []
        
        # Group words by x-position clusters
        x_positions = [w.get("x0", 0) for w in words]
        
        # Simple clustering: assume 1 or 2 columns
        if len(x_positions) < 10:
            return [{"type": "single_column", "x_range": (0, page_width)}]
        
        # Find gaps in x-positions
        sorted_x = sorted(x_positions)
        gaps = []
        
        for i in range(1, len(sorted_x)):
            gap = sorted_x[i] - sorted_x[i-1]
            if gap > page_width * 0.1:  # Significant gap
                gaps.append((sorted_x[i-1], sorted_x[i], gap))
        
        if not gaps:
            return [{"type": "single_column", "x_range": (0, page_width)}]
        
        # Find largest gap (likely column separator)
        largest_gap = max(gaps, key=lambda x: x[2])
        separator = (largest_gap[0] + largest_gap[1]) / 2
        
        return [
            {"type": "left_column", "x_range": (0, separator)},
            {"type": "right_column", "x_range": (separator, page_width)},
        ]
    
    def _detect_margins(self, words: List[Dict], page_width: float, page_height: float) -> Dict[str, float]:
        """Detect page margins"""
        if not words:
            return {"left": 0, "right": 0, "top": 0, "bottom": 0}
        
        left_margin = min(w.get("x0", 0) for w in words)
        right_margin = page_width - max(w.get("x1", 0) for w in words)
        top_margin = min(w.get("top", 0) for w in words)
        bottom_margin = page_height - max(w.get("bottom", 0) for w in words)
        
        return {
            "left": left_margin,
            "right": right_margin,
            "top": top_margin,
            "bottom": bottom_margin,
        }
    
    def _detect_headings(self, words: List[Dict]) -> List[Dict]:
        """Detect heading text blocks"""
        headings = []
        
        # Group words into lines first
        lines = []
        current_line = []
        current_y = None
        y_tolerance = 5
        
        for word in sorted(words, key=lambda w: w.get("top", 0)):
            word_y = word.get("top", 0)
            word_text = word.get("text", "").strip()
            
            if not word_text:
                continue
            
            if current_y is None:
                current_y = word_y
                current_line.append(word)
            elif abs(word_y - current_y) <= y_tolerance:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(current_line)
                current_line = [word]
                current_y = word_y
        
        if current_line:
            lines.append(current_line)
        
        # Check each line for heading characteristics
        for line in lines:
            if len(line) == 0:
                continue
            
            # Combine text
            text = " ".join(w.get("text", "").strip() for w in line)
            
            # Heading detection heuristics
            is_heading = False
            heading_type = None
            
            # Check all caps
            if text.isupper() and 2 <= len(text.split()) <= 10:
                is_heading = True
                heading_type = "main_heading"
            
            # Check numbered headings
            elif re.match(r'^\d+\.\s+[A-Z]', text):
                is_heading = True
                heading_type = "numbered_heading"
            
            # Check title case
            elif text.istitle() and len(text.split()) <= 5:
                is_heading = True
                heading_type = "sub_heading"
            
            # Check for section markers
            elif re.match(r'^(?:Section|Article|Chapter)\s+\d+', text, re.IGNORECASE):
                is_heading = True
                heading_type = "section_heading"
            
            if is_heading:
                # Calculate bounding box
                x0 = min(w.get("x0", 0) for w in line)
                y0 = min(w.get("top", 0) for w in line)
                x1 = max(w.get("x1", 0) for w in line)
                y1 = max(w.get("bottom", 0) for w in line)
                
                headings.append({
                    "text": text,
                    "type": heading_type,
                    "position": {"x0": x0, "y0": y0, "x1": x1, "y1": y1},
                })
        
        return headings
    
    def _extract_tables_with_pdfplumber(self, pdf, pages_to_process: List[int]) -> List[Dict]:
        """Extract tables from PDF using pdfplumber"""
        tables = []
        
        for page_idx in pages_to_process:
            if page_idx >= len(pdf.pages):
                continue
            
            page = pdf.pages[page_idx]
            
            try:
                page_tables = page.extract_tables()
                
                for table_idx, table in enumerate(page_tables):
                    if table and len(table) >= self.config.MIN_TABLE_ROWS:
                        # Clean table data
                        cleaned_table = []
                        for row in table:
                            cleaned_row = [self._clean_table_cell(cell) if cell else "" for cell in row]
                            cleaned_table.append(cleaned_row)
                        
                        # Remove empty rows
                        cleaned_table = [row for row in cleaned_table if any(cell.strip() for cell in row)]
                        
                        if len(cleaned_table) >= self.config.MIN_TABLE_ROWS:
                            formatted_table = {
                                "page": page_idx + 1,
                                "table_number": table_idx + 1,
                                "row_count": len(cleaned_table),
                                "column_count": len(cleaned_table[0]) if cleaned_table[0] else 0,
                                "data": cleaned_table,
                                "has_header": self._table_has_header(cleaned_table),
                            }
                            tables.append(formatted_table)
                            
            except Exception as e:
                self.logger.debug(f"Failed to extract tables from page {page_idx + 1}: {e}")
                continue
        
        return tables
    
    def _clean_table_cell(self, cell: str) -> str:
        """Clean table cell content"""
        if not cell:
            return ""
        
        cleaned = cell.strip()
        cleaned = re.sub(r'\s+', ' ', cleaned)  # Normalize whitespace
        cleaned = re.sub(r'\n', ' ', cleaned)   # Remove newlines
        
        return cleaned
    
    def _table_has_header(self, table: List[List[str]]) -> bool:
        """Check if table likely has a header row"""
        if len(table) < 2:
            return False
        
        first_row = table[0]
        
        # Check if first row looks like a header
        non_empty_cells = [cell for cell in first_row if cell and cell.strip()]
        if len(non_empty_cells) == 0:
            return False
        
        # Header rows often have:
        caps_count = sum(1 for cell in first_row if cell and cell.isupper())
        short_text_count = sum(1 for cell in first_row if cell and len(cell.split()) <= 3)
        numeric_count = sum(1 for cell in first_row if cell and re.match(r'^\d+$', cell.strip()))
        
        # More caps and short text, fewer numbers
        header_score = (caps_count + short_text_count - numeric_count) / len(first_row)
        
        return header_score > 0.3
    
    def _detect_ocr_content(self, parsed_data: Dict) -> bool:
        """Detect if content likely came from OCR"""
        # Simple heuristic: check for common OCR errors
        all_text = ""
        for page in parsed_data.get("pages", []):
            all_text += getattr(page, "raw_text", "") + " "
        
        if not all_text:
            return False
        
        # Common OCR error patterns
        ocr_error_patterns = [
            r'[l1I|]{2,}',      # Multiple confusions
            r'[o0O]{2,}',       # Zero vs O confusions
            r'\b\w\b',          # Single character words
            r'[nm]{3,}',        # Multiple n/m confusions
        ]
        
        error_count = 0
        for pattern in ocr_error_patterns:
            error_count += len(re.findall(pattern, all_text))
        
        # More than 5% of words have OCR characteristics
        total_words = len(all_text.split())
        return (error_count / total_words) > 0.05 if total_words > 0 else False
    
    def _parse_with_pymupdf(self, pdf_path: Path, pages: Optional[List[int]]) -> Dict[str, Any]:
        """Parse PDF using PyMuPDF (good for complex layouts)"""
        import fitz  # PyMuPDF
        
        results = {
            "pages": [],
            "metadata": {},
            "text_statistics": {},
            "tables": [],
            "images": [],
            "errors": [],
            "warnings": [],
            "has_ocr_content": False,
        }
        
        doc = None
        try:
            doc = fitz.open(str(pdf_path))
            
            # Extract metadata
            metadata = doc.metadata
            results["metadata"] = {
                "author": metadata.get("author"),
                "title": metadata.get("title"),
                "subject": metadata.get("subject"),
                "creator": metadata.get("creator"),
                "producer": metadata.get("producer"),
                "creation_date": metadata.get("creationDate"),
                "modification_date": metadata.get("modDate"),
                "page_count": len(doc),
            }
            
            # Determine pages to process
            total_pages = len(doc)
            if pages is None:
                pages_to_process = range(total_pages)
            else:
                pages_to_process = [p-1 for p in pages if 0 <= p-1 < total_pages]
            
            if self.config.MAX_PAGES:
                pages_to_process = pages_to_process[:self.config.MAX_PAGES]
            
            # Process each page
            total_text = ""
            total_words = 0
            
            for page_idx in pages_to_process:
                page_num = page_idx + 1
                try:
                    page = doc[page_idx]
                    page_result = self._parse_pymupdf_page(page, page_num)
                    
                    results["pages"].append(page_result)
                    
                    # Accumulate statistics
                    total_text += page_result.raw_text + " "
                    total_words += page_result.word_count
                    
                except Exception as e:
                    error_msg = f"Page {page_num}: {str(e)}"
                    results["errors"].append(error_msg)
                    self.logger.warning(error_msg)
                    
                    # Create empty page result
                    empty_page = PDFPage(
                        page_number=page_num,
                        width=0,
                        height=0,
                        text_blocks=[],
                        parsing_errors=[error_msg]
                    )
                    results["pages"].append(empty_page)
            
            # Calculate statistics
            results["text_statistics"] = {
                "total_pages": len(results["pages"]),
                "total_characters": len(total_text),
                "total_words": total_words,
                "average_words_per_page": total_words / len(results["pages"]) if results["pages"] else 0,
            }
            
            # Check for OCR content
            results["has_ocr_content"] = self._detect_ocr_content(results)
            
        except Exception as e:
            results["errors"].append(f"PyMuPDF parsing failed: {str(e)}")
            self.logger.error(f"PyMuPDF parsing failed: {e}")
        finally:
            if doc:
                doc.close()
        
        return results
    
    def _parse_pymupdf_page(self, page, page_num: int) -> PDFPage:
        """Parse single page with PyMuPDF"""
        
        page_result = PDFPage(
            page_number=page_num,
            width=page.rect.width,
            height=page.rect.height,
            text_blocks=[],
        )
        
        try:
            # Extract text
            if self.config.PRESERVE_LAYOUT:
                text = page.get_text("dict")
                # Process dictionary text extraction
                blocks = text.get("blocks", [])
                extracted_text = ""
                
                for block in blocks:
                    if "lines" in block:
                        for line in block["lines"]:
                            for span in line.get("spans", []):
                                extracted_text += span.get("text", "") + " "
                
                text_content = extracted_text
            else:
                text_content = page.get_text("text") or ""
            
            page_result.raw_text = text_content
            page_result.word_count = len(text_content.split())
            page_result.char_count = len(text_content)
            
            # Clean text
            clean_text = self._clean_text(text_content)
            page_result.cleaned_text = clean_text
            
            # Extract blocks with layout if enabled
            if self.config.PRESERVE_LAYOUT:
                try:
                    blocks = page.get_text("blocks")
                    text_blocks = []
                    
                    for block in blocks:
                        # block format: (x0, y0, x1, y1, text, block_no, block_type)
                        if len(block) >= 6:
                            text = block[4]
                            if text.strip():
                                # Determine block type
                                block_type = self._determine_block_type(text, [])
                                
                                text_block = TextBlock(
                                    text=text,
                                    bbox=block[:4],
                                    page_num=page_num,
                                    block_type=block_type,
                                )
                                text_blocks.append(text_block)
                    
                    page_result.text_blocks = text_blocks
                    
                except Exception as e:
                    self.logger.debug(f"PyMuPDF layout extraction failed for page {page_num}: {e}")
                    page_result.parsing_warnings.append(f"Layout extraction: {str(e)}")
            
            # Calculate text density
            if page.rect.width > 0 and page.rect.height > 0:
                page_result.text_density = page_result.word_count / (page.rect.width * page.rect.height)
            
            # Check for KPK patterns
            if self.config.DETECT_KPK_PATTERNS:
                kpk_patterns_found = self._find_kpk_patterns_in_text(text_content)
                if kpk_patterns_found:
                    page_result.metadata["kpk_patterns"] = kpk_patterns_found
            
            # Set parsing method
            page_result.parsing_method = "pymupdf"
            
        except Exception as e:
            error_msg = f"Page parsing failed: {str(e)}"
            page_result.parsing_errors.append(error_msg)
            self.logger.warning(f"Error parsing page {page_num} with PyMuPDF: {e}")
        
        return page_result
    
    def _parse_with_ocr_fallback(self, pdf_path: Path, pages: Optional[List[int]]) -> Dict[str, Any]:
        """Fallback to OCR when text extraction fails"""
        # This would integrate with ocr_engine.py (Phase 1.5)
        # For now, return minimal structure with integration hint
        return {
            "pages": [],
            "metadata": {"method": "ocr_fallback"},
            "text_statistics": {},
            "errors": ["OCR fallback not fully implemented - integrate with ocr_engine.py"],
            "warnings": ["Document may require OCR processing"],
            "has_ocr_content": True,
        }
    
    def _parse_hybrid(self, pdf_path: Path, pages: Optional[List[int]], 
                     previous_results: List[Tuple[str, Dict]]) -> Dict[str, Any]:
        """Combine results from multiple parsing methods"""
        # Simple hybrid approach: combine text from all successful methods
        combined_text = {}
        
        for method, result in previous_results:
            if result and "pages" in result:
                for page in result["pages"]:
                    # Handle both PDFPage object and dictionary
                    if hasattr(page, 'page_number'):
                        page_num = page.page_number
                        text = getattr(page, 'raw_text', '')
                    else:
                        page_num = page.get("page_number")
                        text = page.get("text", "") or page.get("raw_text", "")
                        
                    if page_num not in combined_text:
                        combined_text[page_num] = text
                    else:
                        # Append if current text is longer/better
                        current_text = combined_text[page_num]
                        new_text = text
                        if len(new_text) > len(current_text):
                            combined_text[page_num] = new_text
        
        # Create combined result
        pages_list = []
        total_words = 0
        total_chars = 0
        
        for page_num, text in sorted(combined_text.items()):
            page_result = PDFPage(
                page_number=page_num,
                width=0,
                height=0,
                text_blocks=[],
                raw_text=text,
                cleaned_text=self._clean_text(text),
                word_count=len(text.split()),
                char_count=len(text),
                parsing_method="hybrid",
            )
            pages_list.append(page_result)
            
            total_words += page_result.word_count
            total_chars += page_result.char_count
        
        return {
            "pages": pages_list,
            "metadata": {"method": "hybrid", "source_methods": [m for m, _ in previous_results]},
            "text_statistics": {
                "total_pages": len(pages_list),
                "total_characters": total_chars,
                "total_words": total_words,
                "average_words_per_page": total_words / len(pages_list) if pages_list else 0,
            },
            "errors": [],
            "warnings": ["Used hybrid parsing approach"],
            "has_ocr_content": any(r[1].get("has_ocr_content", False) for r in previous_results),
        }
    
    def _find_kpk_patterns_in_text(self, text: str) -> Dict[str, List[str]]:
        """Find KPK-specific patterns in text"""
        found_patterns = {}
        
        for pattern_type, patterns in self.kpk_patterns.items():
            matches = []
            for pattern in patterns:
                try:
                    pattern_matches = re.findall(pattern, text, re.IGNORECASE | re.UNICODE)
                    if pattern_matches:
                        matches.extend(pattern_matches)
                except re.error:
                    self.logger.debug(f"Invalid regex pattern: {pattern}")
                    continue
            
            if matches:
                # Remove duplicates while preserving order
                unique_matches = []
                seen = set()
                for match in matches:
                    if match not in seen:
                        seen.add(match)
                        unique_matches.append(match)
                found_patterns[pattern_type] = unique_matches
        
        return found_patterns
    
    def _extract_kpk_metadata(self, parsed_data: Dict) -> Dict[str, Any]:
        """Extract KPK-specific metadata from parsed document"""
        metadata = {
            "is_kpk_document": False,
            "document_type": "unknown",
            "jurisdiction": "unknown",
            "detected_patterns": {},
            "estimated_year": None,
            "has_penalty_sections": False,
            "has_species_mentions": False,
        }
        
        # Combine text from all pages
        all_text = ""
        for page in parsed_data.get("pages", []):
            if hasattr(page, 'cleaned_text') and page.cleaned_text:
                all_text += page.cleaned_text + " "
            elif hasattr(page, 'raw_text') and page.raw_text:
                all_text += page.raw_text + " "
            elif isinstance(page, dict):
                all_text += (page.get("cleaned_text") or page.get("text") or page.get("raw_text") or "") + " "
        
        # Check for KPK indicators
        kpk_indicators = self.kpk_patterns["document_type_indicators"]
        for indicator in kpk_indicators:
            try:
                if re.search(indicator, all_text, re.IGNORECASE | re.UNICODE):
                    metadata["is_kpk_document"] = True
                    break
            except re.error:
                continue
        
        # Determine document type
        text_lower = all_text.lower()
        if "ordinance" in text_lower:
            metadata["document_type"] = "ordinance"
        elif "act" in text_lower:
            metadata["document_type"] = "act"
        elif "circular" in text_lower:
            metadata["document_type"] = "circular"
        elif "working plan" in text_lower or "working-plan" in text_lower:
            metadata["document_type"] = "working_plan"
        elif "notification" in text_lower:
            metadata["document_type"] = "notification"
        elif "s.r.o" in text_lower or "sro" in text_lower:
            metadata["document_type"] = "sro"
        elif "report" in text_lower:
            metadata["document_type"] = "report"
        
        # Extract year
        year_match = re.search(r'\b(19\d{2}|20\d{2})\b', all_text)
        if year_match:
            metadata["estimated_year"] = year_match.group(1)
        
        # Check for specific divisions
        if re.search(r'\bhazara\b', all_text, re.IGNORECASE):
            metadata["jurisdiction"] = "hazara_division"
        elif re.search(r'\bmalakand\b', all_text, re.IGNORECASE):
            metadata["jurisdiction"] = "malakand_division"
        elif re.search(r'\bkpk\b|\bkhyber\b', all_text, re.IGNORECASE):
            metadata["jurisdiction"] = "kpk_provincial"
        
        # Check for penalty sections
        penalty_patterns = self.kpk_patterns["penalty_patterns"]
        for pattern in penalty_patterns:
            if re.search(pattern, all_text, re.IGNORECASE | re.UNICODE):
                metadata["has_penalty_sections"] = True
                break
        
        # Check for species mentions
        species_patterns = self.kpk_patterns["species_patterns"]
        for pattern in species_patterns:
            if re.search(pattern, all_text, re.IGNORECASE | re.UNICODE):
                metadata["has_species_mentions"] = True
                break
        
        # Count detected patterns across pages
        total_pages = len(parsed_data.get("pages", []))
        pattern_counts = {}
        
        for page in parsed_data.get("pages", []):
            page_metadata = getattr(page, 'metadata', {}) if hasattr(page, 'metadata') else page
            if "kpk_patterns" in page_metadata:
                for pattern_type, patterns in page_metadata["kpk_patterns"].items():
                    pattern_counts[pattern_type] = pattern_counts.get(pattern_type, 0) + len(patterns)
        
        metadata["detected_patterns"] = pattern_counts
        metadata["pattern_density"] = sum(pattern_counts.values()) / total_pages if total_pages > 0 else 0
        
        return metadata
    
    def _analyze_structure(self, parsed_data: Dict) -> Dict[str, Any]:
        """Analyze document structure"""
        structure = {
            "page_count": len(parsed_data.get("pages", [])),
            "sections": [],
            "headings": [],
            "tables": parsed_data.get("tables", []),
            "layout_consistency": {},
            "document_flow": {},
        }
        
        # Extract sections and headings
        for page in parsed_data.get("pages", []):
            if hasattr(page, 'cleaned_text'):
                text = page.cleaned_text
            elif hasattr(page, 'raw_text'):
                text = page.raw_text
            else:
                text = page.get("text", "") or page.get("raw_text", "") if isinstance(page, dict) else ""
            
            # Find section markers
            section_matches = re.findall(r'Section\s+\d+[A-Z]?|Sec\.\s*\d+[A-Z]?|فصل\s+\d+', text, re.IGNORECASE | re.UNICODE)
            
            for match in section_matches:
                section_num = re.search(r'\d+[A-Z]?', match)
                if section_num:
                    structure["sections"].append({
                        "page": getattr(page, 'page_number', 0),
                        "section": section_num.group(),
                        "context": text[:100] + "..." if len(text) > 100 else text,
                    })
            
            # Extract headings
            if hasattr(page, 'headings'):
                for heading in page.headings:
                    structure["headings"].append({
                        "page": page.page_number,
                        "text": heading.get("text"),
                        "type": heading.get("type"),
                        "position": heading.get("position", {}),
                    })
        
        # Analyze layout consistency
        if parsed_data.get("pages"):
            pages_with_layout = [p for p in parsed_data["pages"] if hasattr(p, 'margins') and p.margins]
            
            if len(pages_with_layout) >= 2:
                first_page = pages_with_layout[0]
                last_page = pages_with_layout[-1]
                
                margin_diff = {
                    "left": abs(first_page.margins.get("left", 0) - last_page.margins.get("left", 0)),
                    "right": abs(first_page.margins.get("right", 0) - last_page.margins.get("right", 0)),
                    "top": abs(first_page.margins.get("top", 0) - last_page.margins.get("top", 0)),
                    "bottom": abs(first_page.margins.get("bottom", 0) - last_page.margins.get("bottom", 0)),
                }
                
                structure["layout_consistency"] = {
                    "margin_consistency": max(margin_diff.values()) < 20,  # Within 20 pixels
                    "margin_variation": margin_diff,
                    "average_margins": {
                        "left": (first_page.margins.get("left", 0) + last_page.margins.get("left", 0)) / 2,
                        "right": (first_page.margins.get("right", 0) + last_page.margins.get("right", 0)) / 2,
                        "top": (first_page.margins.get("top", 0) + last_page.margins.get("top", 0)) / 2,
                        "bottom": (first_page.margins.get("bottom", 0) + last_page.margins.get("bottom", 0)) / 2,
                    }
                }
        
        # Analyze document flow (headings per page)
        heading_counts = {}
        for heading in structure["headings"]:
            page = heading["page"]
            heading_counts[page] = heading_counts.get(page, 0) + 1
        
        structure["document_flow"] = {
            "heading_distribution": heading_counts,
            "pages_with_headings": len(heading_counts),
            "total_headings": len(structure["headings"]),
            "average_headings_per_page": len(structure["headings"]) / structure["page_count"] if structure["page_count"] > 0 else 0,
        }
        
        return structure
    
    def _calculate_success_rate(self, parsed_data: Dict) -> float:
        """Calculate parsing success rate"""
        pages = parsed_data.get("pages", [])
        if not pages:
            return 0.0
        
        successful_pages = 0
        
        for page in pages:
            # Check if page has reasonable content
            if hasattr(page, 'word_count'):
                word_count = page.word_count
                text = getattr(page, 'cleaned_text', '') or getattr(page, 'raw_text', '')
            else:
                word_count = page.get("word_count", 0)
                text = page.get("text", "") or page.get("raw_text", "")
            
            if word_count >= self.config.MIN_WORDS_PER_PAGE and len(text.strip()) > 0:
                successful_pages += 1
        
        return successful_pages / len(pages)
    
    def _update_statistics(self, result: PDFParseResult, parsing_time: float):
        """Update parser statistics"""
        self.stats['documents_parsed'] += 1
        self.stats['total_pages_parsed'] += result.total_pages
        self.stats['parsing_time_total'] += parsing_time
        
        # Update method statistics
        method = result.parsing_method
        if method in self.stats['by_parsing_method']:
            self.stats['by_parsing_method'][method] += 1
        else:
            self.stats['by_parsing_method'][method] = 1
        
        # Update KPK statistics
        if result.is_kpk_document:
            self.stats['kpk_documents'] += 1
        
        if result.kpk_jurisdiction == "hazara_division":
            self.stats['hazara_documents'] += 1
        elif result.kpk_jurisdiction == "malakand_division":
            self.stats['malakand_documents'] += 1
        
        # Update success statistics
        self.stats['success_rate'] = result.success_rate
        total_docs = self.stats['documents_parsed']
        old_avg = self.stats['avg_success_rate']
        self.stats['avg_success_rate'] = (
            (old_avg * (total_docs - 1) + result.success_rate) / total_docs
        )
        
        # Update extraction statistics
        if result.has_tables:
            self.stats['tables_extracted'] += len(result.structure.get('tables', []))
        
        if result.has_ocr_content:
            self.stats['ocr_pages'] += sum(1 for page in result.pages if page.parsing_method == 'ocr_fallback')
        
        # Update performance metrics
        perf = self.stats['performance']
        perf['parse_times'].append(parsing_time)
        perf['fastest_parse'] = min(perf['fastest_parse'], parsing_time)
        perf['slowest_parse'] = max(perf['slowest_parse'], parsing_time)
    
    def _log_parsing_abstention(self, result: PDFParseResult, pdf_path: Path):
        """Log abstention for poor parsing results"""
        try:
            context = create_abstention_context(
                stage=PipelineStage.PDF_PARSING,
                component="KPKPDFParser",
                document_path=str(pdf_path),
                reason="parsing_quality_too_low",
                details={
                    'success_rate': result.success_rate,
                    'parsing_method': result.parsing_method,
                    'total_pages': result.total_pages,
                    'total_words': result.total_words,
                    'is_kpk_document': result.is_kpk_document,
                }
            )
            
            self.abstention_logger.log_abstention(
                abstention_type=AbstentionType.PARSING_ISSUE,
                severity=AbstentionSeverity.MEDIUM,
                context=context,
                suggested_action="Use OCR fallback or manual extraction",
                confidence=1.0 - result.success_rate,
                component_state=result.to_dict(),
            )
            
            self.logger.info(f"Logged parsing abstention for {pdf_path.name}")
            
        except Exception as e:
            self.logger.warning(f"Failed to log parsing abstention: {e}")
    
    def _create_error_result(self, pdf_path: Path, error_message: str) -> PDFParseResult:
        """Create minimal result when parsing fails"""
        return PDFParseResult(
            document_path=str(pdf_path),
            document_hash=hashlib.md5(str(pdf_path).encode()).hexdigest()[:16],
            parsing_timestamp=datetime.now(),
            
            pages=[],
            metadata={"error": error_message},
            kpk_metadata={},
            structure={},
            
            parsing_method="failed",
            parsing_duration=0,
            success_rate=0,
            
            total_pages=0,
            total_words=0,
            total_characters=0,
            average_words_per_page=0,
            
            parsing_errors=[error_message],
            abstention_reasons=["parsing_failed"],
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get current parser statistics"""
        stats = self.stats.copy()
        
        # Calculate derived statistics
        total_parsed = stats['documents_parsed']
        if total_parsed > 0:
            stats['avg_parsing_time'] = stats['parsing_time_total'] / total_parsed
            
            # Calculate method percentages
            total_by_method = sum(stats['by_parsing_method'].values())
            percentages = {}
            for method, count in stats['by_parsing_method'].items():
                percentages[f"{method}_pct"] = (
                    count / total_by_method * 100 if total_by_method > 0 else 0
                )
            stats['by_parsing_method'].update(percentages)
        
        # Add performance summary
        perf = stats['performance']
        if perf['parse_times']:
            perf['avg_parse_time'] = sum(perf['parse_times']) / len(perf['parse_times'])
        else:
            perf['avg_parse_time'] = 0.0
            perf['fastest_parse'] = 0.0
        
        return stats
    
    def batch_process(self, 
                      pdf_paths: List[Union[str, Path]],
                      output_dir: Optional[Union[str, Path]] = None) -> List[PDFParseResult]:
        """
        Process multiple PDFs in batch.
        
        Args:
            pdf_paths: List of PDF file paths
            output_dir: Optional directory to save results
            
        Returns:
            List of PDFParseResult objects
        """
        results = []
        
        for i, pdf_path in enumerate(pdf_paths, 1):
            try:
                self.logger.info(f"Processing PDF {i}/{len(pdf_paths)}: {pdf_path}")
                
                result = self.parse_pdf(pdf_path)
                results.append(result)
                
                # Save if output directory specified
                if output_dir:
                    self._save_parse_result(result, output_dir)
                
            except Exception as e:
                self.logger.error(f"Failed to process {pdf_path}: {e}")
                
                # Create error result
                error_result = self._create_error_result(Path(pdf_path), str(e))
                results.append(error_result)
        
        return results
    
    def _save_parse_result(self, result: PDFParseResult, output_dir: Union[str, Path]):
        """Save parse result to file"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename
        doc_name = Path(result.document_path).stem
        timestamp = result.parsing_timestamp.strftime("%Y%m%d_%H%M%S")
        filename = f"parse_{doc_name}_{timestamp}"
        
        # Save as JSON
        json_path = output_dir / f"{filename}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
        
        # Save text content
        text_path = output_dir / f"{filename}.txt"
        with open(text_path, 'w', encoding='utf-8') as f:
            f.write(result.get_all_text())
        
        # Save statistics
        stats_path = output_dir / f"{filename}_stats.json"
        with open(stats_path, 'w', encoding='utf-8') as f:
            json.dump(result.get_statistics(), f, indent=2)
        
        self.logger.info(f"Saved parse results to {json_path}")

# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    """Main function for standalone testing"""
    import argparse
    
    parser = argparse.ArgumentParser(description="KPK PDF Parser")
    parser.add_argument("--input", required=True, help="Input PDF file")
    parser.add_argument("--output", help="Output directory for results")
    parser.add_argument("--config", help="Configuration file (JSON)")
    parser.add_argument("--pages", help="Specific pages (e.g., '1,3,5' or '1-5')")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    
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
    
    # Parse pages argument
    pages = None
    if args.pages:
        pages = []
        for part in args.pages.split(','):
            if '-' in part:
                start, end = map(int, part.split('-'))
                pages.extend(range(start, end + 1))
            else:
                pages.append(int(part))
    
    # Parse PDF
    parser = KPKPDFParser(config=config)
    result = parser.parse_pdf(args.input, pages)
    
    # Print summary
    print("\n" + "="*60)
    print("PDF PARSING SUMMARY")
    print("="*60)
    print(f"Document: {Path(args.input).name}")
    print(f"Parsing Method: {result.parsing_method}")
    print(f"Success Rate: {result.success_rate:.2%}")
    print(f"Pages Parsed: {result.total_pages}")
    print(f"Total Words: {result.total_words:,}")
    print(f"Average Words/Page: {result.average_words_per_page:.1f}")
    
    if result.is_kpk_document:
        print(f"\nKPK Document: YES")
        print(f"Document Type: {result.kpk_document_type}")
        print(f"Jurisdiction: {result.kpk_jurisdiction}")
    else:
        print(f"\nKPK Document: NO")
    
    print(f"\nStructure Analysis:")
    print(f"  Sections Found: {len(result.structure.get('sections', []))}")
    print(f"  Headings Found: {len(result.structure.get('headings', []))}")
    print(f"  Tables Found: {len(result.structure.get('tables', []))}")
    print(f"  Layout Preserved: {'YES' if result.layout_preserved else 'NO'}")
    
    if result.parsing_errors:
        print(f"\nErrors ({len(result.parsing_errors)}):")
        for error in result.parsing_errors[:3]:
            print(f"  - {error}")
    
    # Save results if output directory specified
    if args.output:
        parser._save_parse_result(result, args.output)
        print(f"\nResults saved to: {args.output}")
    
    # Print statistics
    stats = parser.get_statistics()
    print(f"\nParser Statistics:")
    print(f"  Documents Parsed: {stats['documents_parsed']}")
    print(f"  KPK Documents: {stats['kpk_documents']}")
    print(f"  Average Success Rate: {stats['avg_success_rate']:.2%}")
    print(f"  Average Parsing Time: {stats['avg_parsing_time']:.2f}s")

if __name__ == "__main__":
    main()
