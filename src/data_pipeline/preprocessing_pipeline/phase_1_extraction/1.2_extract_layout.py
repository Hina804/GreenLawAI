"""
EXTRACT_LAYOUT.PY - Phase 1.2: Document Layout Analysis and Structure Extraction
Analyzes PDF structure to extract logical document layout for KPK forestry documents.
Author: Hina Ali, Eman Irfan
Date: January 29, 2026
"""

import logging
import json
import re
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union, Set
from dataclasses import dataclass, asdict, field
from datetime import datetime
import statistics
from enum import Enum

# Third-party imports
import pdfplumber
import pymupdf  # PyMuPDF
import numpy as np
from PIL import Image
import cv2

# Import from common modules
try:
    from preprocessing_pipeline.common.config import PipelineConfig, LayoutExtractionConfig
    from preprocessing_pipeline.common.constants import *
    USE_COMMON_CONFIG = True
except ImportError:
    USE_COMMON_CONFIG = False
    print("Warning: common.config not found. Using default configuration.")

# Import shared types to avoid circularity
from .types import (
    PDFParseResult, PDFPage, DocumentLayout, PageLayout, LayoutElement, 
    LayoutElementType, TableCell, ExtractedTable, ExtractedForm, 
    TableExtractionResult, TableType, FormField, BoundingBox
)

# Import from other phases
try:
    from preprocessing_pipeline.phase_0_foundation import (
        AbstentionLogger, AbstentionType, AbstentionSeverity, 
        PipelineStage, create_abstention_context
    )
    PHASE_1_MODULES_AVAILABLE = True
except ImportError:
    PHASE_1_MODULES_AVAILABLE = False
    PDFParseResult = None
    PDFPage = None
    AbstentionLogger = None
    AbstentionType = None
    AbstentionSeverity = None
    PipelineStage = None
    create_abstention_context = None
    print("Warning: Phase 1 or 0 modules not available. Running in standalone mode.")

# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class LayoutExtractionConfig:
    """Configuration for document layout extraction"""
    
    # Layout detection parameters
    COLUMN_DETECTION_ENABLED: bool = True
    MAX_COLUMNS: int = 3
    COLUMN_SEPARATION_THRESHOLD: float = 0.15  # 15% of page width
    
    # Margin detection
    MARGIN_DETECTION_ENABLED: bool = True
    DEFAULT_MARGINS: Dict[str, float] = field(default_factory=lambda: {
        'left': 72, 'right': 72, 'top': 72, 'bottom': 72  # 1 inch margins
    })
    
    # Header/Footer detection
    HEADER_FOOTER_ENABLED: bool = True
    HEADER_THRESHOLD: float = 0.1   # Top 10% of page
    FOOTER_THRESHOLD: float = 0.9   # Bottom 10% of page
    
    # Section detection
    SECTION_DETECTION_ENABLED: bool = True
    HEADING_FONT_SIZE_THRESHOLD: float = 1.2  # 20% larger than body text
    HEADING_ALL_CAPS_THRESHOLD: int = 3       # Min words for all-caps heading
    
    # Table detection
    TABLE_DETECTION_ENABLED: bool = True
    MIN_TABLE_ROWS: int = 2
    MIN_TABLE_COLUMNS: int = 2
    TABLE_LINE_THRESHOLD: int = 2
    
    # List detection
    LIST_DETECTION_ENABLED: bool = True
    LIST_PREFIX_PATTERNS: List[str] = field(default_factory=lambda: [
        r'^\d+\.',           # 1.
        r'^[a-z]\)',         # a)
        r'^[ivxlcdm]+\.',    # i., ii., iii.
        r'^[•\-*›»]',        # Bullets
    ])
    
    # KPK-specific patterns
    KPK_PATTERN_DETECTION: bool = True
    LEGAL_SECTION_PATTERNS: List[str] = field(default_factory=lambda: [
        r'Section\s+\d+[A-Z]?',
        r'Sec\.\s*\d+[A-Z]?',
        r'فصل\s+\d+',
        r'دفعہ\s+\d+',
        r'Article\s+\d+',
        r'Clause\s+\d+',
        r'Regulation\s+\d+',
    ])
    
    # Layout analysis
    LAYOUT_ANALYSIS_DEPTH: str = 'detailed'  # 'basic', 'standard', 'detailed'
    PRESERVE_HIERARCHY: bool = True
    MAX_HIERARCHY_LEVELS: int = 5
    
    # Performance
    PARALLEL_PROCESSING: bool = False
    MAX_WORKERS: int = 4
    CACHE_RESULTS: bool = True
    
    # Output
    GENERATE_LAYOUT_VISUALIZATION: bool = True
    SAVE_INTERMEDIATE_RESULTS: bool = False
    OUTPUT_FORMAT: str = 'json'  # 'json', 'xml', 'html'
    
    # Error handling
    CONTINUE_ON_ERROR: bool = True
    LOG_DETAILED_ERRORS: bool = True

# ============================================================================
# DATA CLASSES
# ============================================================================

class LayoutElementType(Enum):
    """Types of layout elements"""
    PAGE = "page"
    COLUMN = "column"
    TEXT_BLOCK = "text_block"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    LIST_ITEM = "list_item"
    TABLE = "table"
    TABLE_ROW = "table_row"
    TABLE_CELL = "table_cell"
    IMAGE = "image"
    HEADER = "header"
    FOOTER = "footer"
    PAGE_NUMBER = "page_number"
    FOOTNOTE = "footnote"
    CAPTION = "caption"
    SIDEBAR = "sidebar"
    UNKNOWN = "unknown"

@dataclass
class BoundingBox:
    """Bounding box with position information"""
    x0: float
    y0: float
    x1: float
    y1: float
    page_num: int
    
    @property
    def width(self) -> float:
        return self.x1 - self.x0
    
    @property
    def height(self) -> float:
        return self.y1 - self.y0
    
    @property
    def area(self) -> float:
        return self.width * self.height
    
    @property
    def center(self) -> Tuple[float, float]:
        return ((self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2)
    
    def overlaps(self, other: 'BoundingBox', threshold: float = 0.1) -> bool:
        """Check if two bounding boxes overlap"""
        # Calculate intersection
        inter_x0 = max(self.x0, other.x0)
        inter_y0 = max(self.y0, other.y0)
        inter_x1 = min(self.x1, other.x1)
        inter_y1 = min(self.y1, other.y1)
        
        if inter_x0 < inter_x1 and inter_y0 < inter_y1:
            intersection_area = (inter_x1 - inter_x0) * (inter_y1 - inter_y0)
            min_area = min(self.area, other.area)
            return (intersection_area / min_area) >= threshold
        
        return False
    
    def contains(self, other: 'BoundingBox') -> bool:
        """Check if this bounding box contains another"""
        return (self.x0 <= other.x0 and self.y0 <= other.y0 and
                self.x1 >= other.x1 and self.y1 >= other.y1)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "x0": self.x0,
            "y0": self.y0,
            "x1": self.x1,
            "y1": self.y1,
            "page_num": self.page_num
        }

@dataclass
class LayoutElement:
    """Base class for layout elements"""
    element_id: str
    element_type: LayoutElementType
    bbox: BoundingBox
    text: Optional[str] = None
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    children: List['LayoutElement'] = field(default_factory=list)
    parent: Optional['LayoutElement'] = None
    
    def __post_init__(self):
        # Set parent for children
        for child in self.children:
            child.parent = self
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary manually to avoid circular references"""
        return {
            "element_id": self.element_id,
            "element_type": self.element_type.value,
            "bbox": self.bbox.to_dict(),
            "text": self.text,
            "confidence": self.confidence,
            "metadata": self.metadata,
            "children": [child.to_dict() for child in self.children]
        }
    
    def add_child(self, child: 'LayoutElement'):
        """Add child element"""
        child.parent = self
        self.children.append(child)
    
    def get_descendants(self, element_type: Optional[LayoutElementType] = None) -> List['LayoutElement']:
        """Get all descendant elements, optionally filtered by type"""
        descendants = []
        
        for child in self.children:
            if element_type is None or child.element_type == element_type:
                descendants.append(child)
            descendants.extend(child.get_descendants(element_type))
        
        return descendants
    
    def get_elements_by_type(self, element_type: LayoutElementType) -> List['LayoutElement']:
        """Get all elements of specific type within this element"""
        elements = []
        
        if self.element_type == element_type:
            elements.append(self)
        
        for child in self.children:
            elements.extend(child.get_elements_by_type(element_type))
        
        return elements

@dataclass
class PageLayout:
    """Complete layout for a single page"""
    page_num: int
    width: float
    height: float
    elements: List[LayoutElement]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Detected structures
    columns: List[Dict[str, Any]] = field(default_factory=list)
    margins: Dict[str, float] = field(default_factory=dict)
    headers: List[LayoutElement] = field(default_factory=list)
    footers: List[LayoutElement] = field(default_factory=list)
    tables: List[LayoutElement] = field(default_factory=list)
    lists: List[LayoutElement] = field(default_factory=list)
    
    # Statistics
    text_density: float = 0.0
    layout_consistency_score: float = 0.0
    
    def get_elements_by_type(self, element_type: LayoutElementType) -> List[LayoutElement]:
        """Get all elements of specific type on this page"""
        results = []
        for element in self.elements:
            results.extend(element.get_elements_by_type(element_type))
        return results
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary manually to avoid circular references"""
        return {
            "page_num": self.page_num,
            "width": self.width,
            "height": self.height,
            "elements": [elem.to_dict() for elem in self.elements],
            "metadata": self.metadata,
            "columns": self.columns,
            "margins": self.margins,
            "headers": [h.to_dict() for h in self.headers],
            "footers": [f.to_dict() for f in self.footers],
            "tables": [t.to_dict() for t in self.tables],
            "lists": [l.to_dict() for l in self.lists],
            "text_density": self.text_density,
            "layout_consistency_score": self.layout_consistency_score
        }
    
    def get_text_elements(self) -> List[LayoutElement]:
        """Get all text elements"""
        return [e for e in self.elements if e.text and e.element_type in [
            LayoutElementType.TEXT_BLOCK, LayoutElementType.HEADING,
            LayoutElementType.PARAGRAPH, LayoutElementType.LIST_ITEM
        ]]
    
    def get_main_text_blocks(self) -> List[LayoutElement]:
        """Get main text blocks (excluding headers/footers)"""
        main_blocks = []
        
        for elem in self.elements:
            if (elem.text and elem.element_type == LayoutElementType.TEXT_BLOCK and
                not any(h.bbox.contains(elem.bbox) for h in self.headers) and
                not any(f.bbox.contains(elem.bbox) for f in self.footers)):
                main_blocks.append(elem)
        
        return main_blocks

@dataclass
class DocumentLayout:
    """Complete layout for entire document"""
    document_path: str
    document_hash: str
    pages: List[PageLayout]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Document structure
    sections: List[Dict[str, Any]] = field(default_factory=list)
    toc: List[Dict[str, Any]] = field(default_factory=list)  # Table of contents
    document_hierarchy: List[LayoutElement] = field(default_factory=list)
    
    # Statistics
    total_pages: int = 0
    avg_text_density: float = 0.0
    layout_consistency: float = 0.0
    
    def __post_init__(self):
        self.total_pages = len(self.pages)
        if self.pages:
            self.avg_text_density = statistics.mean(p.text_density for p in self.pages)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary manually to avoid circular references"""
        return {
            "document_path": self.document_path,
            "document_hash": self.document_hash,
            "pages": [page.to_dict() for page in self.pages],
            "metadata": self.metadata,
            "sections": self.sections,
            "toc": self.toc,
            "document_hierarchy": [elem.to_dict() for elem in self.document_hierarchy],
            "total_pages": self.total_pages,
            "avg_text_density": self.avg_text_density,
            "layout_consistency": self.layout_consistency
        }
    
    def get_all_text_elements(self) -> List[LayoutElement]:
        """Get all text elements from all pages"""
        elements = []
        for page in self.pages:
            elements.extend(page.get_text_elements())
        return elements
    
    def get_all_text(self) -> str:
        """Get all text from the document"""
        elements = self.get_all_text_elements()
        return "\n\n".join([e.text for e in elements if e.text])
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get document statistics"""
        return {
            "total_pages": self.total_pages,
            "avg_text_density": self.avg_text_density,
            "layout_consistency": self.layout_consistency,
            "section_count": len(self.sections),
            "toc_entries": len(self.toc)
        }
    
    def get_structured_text(self) -> Dict[str, List[str]]:
        """Get text organized by structure"""
        structured = {
            'headings': [],
            'paragraphs': [],
            'lists': [],
            'tables': [],
            'headers': [],
            'footers': [],
        }
        
        for page in self.pages:
            # Headings
            headings = page.get_elements_by_type(LayoutElementType.HEADING)
            structured['headings'].extend([h.text for h in headings if h.text])
            
            # Paragraphs
            paragraphs = page.get_elements_by_type(LayoutElementType.PARAGRAPH)
            structured['paragraphs'].extend([p.text for p in paragraphs if p.text])
            
            # Lists
            lists = page.get_elements_by_type(LayoutElementType.LIST)
            for lst in lists:
                list_items = lst.get_elements_by_type(LayoutElementType.LIST_ITEM)
                structured['lists'].extend([li.text for li in list_items if li.text])
            
            # Tables
            for table in page.tables:
                table_text = self._extract_table_text(table)
                if table_text:
                    structured['tables'].append(table_text)
            
            # Headers/Footers
            for header in page.headers:
                if header.text:
                    structured['headers'].append(header.text)
            for footer in page.footers:
                if footer.text:
                    structured['footers'].append(footer.text)
        
        return structured
    
    def _extract_table_text(self, table: LayoutElement) -> str:
        """Extract text from table element"""
        table_text = []
        rows = table.get_elements_by_type(LayoutElementType.TABLE_ROW)
        
        for row in rows:
            cells = row.get_elements_by_type(LayoutElementType.TABLE_CELL)
            row_text = [cell.text or '' for cell in cells]
            table_text.append(' | '.join(row_text))
        
        return '\n'.join(table_text)

# ============================================================================
# LAYOUT EXTRACTOR
# ============================================================================

class LayoutExtractor:
    """
    Phase 1.2: Document Layout Analysis and Structure Extraction
    Extracts logical layout from parsed PDF content for KPK forestry documents.
    """
    
    def __init__(self, 
                 config: Optional[Union[LayoutExtractionConfig, Dict]] = None,
                 enable_abstention_logging: bool = True,
                 logger: Optional[logging.Logger] = None):
        """
        Initialize layout extractor.
        
        Args:
            config: Configuration object or dictionary
            enable_abstention_logging: Whether to log abstentions
            logger: Optional logger instance
        """
        
        # Configuration
        if isinstance(config, dict):
            self.config = LayoutExtractionConfig()
            # Update config from dict
            for key, value in config.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
        elif config is None:
            self.config = LayoutExtractionConfig()
        else:
            self.config = config
        
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
        
        # KPK-specific patterns
        self.kpk_patterns = self._load_kpk_patterns()
        
        # Statistics
        self.stats = self._init_statistics()
        
        # Cache
        self._layout_cache = {}
        
        self.logger.info("LayoutExtractor initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging"""
        logger = logging.getLogger('LayoutExtractor')
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
            
            'layout_quality': {
                'excellent': 0,
                'good': 0,
                'fair': 0,
                'poor': 0,
            },
            
            'elements_detected': {
                'total': 0,
                'headings': 0,
                'paragraphs': 0,
                'lists': 0,
                'tables': 0,
                'headers': 0,
                'footers': 0,
            },
            
            'kpk_documents': 0,
            'legal_documents': 0,
            'multi_column_documents': 0,
            
            'performance': {
                'fastest_extraction': float('inf'),
                'slowest_extraction': 0.0,
                'extraction_times': [],
            },
            
            'issues': {
                'layout_parsing_errors': 0,
                'poor_layout_quality': 0,
                'missing_structure': 0,
            },
        }
    
    def _load_kpk_patterns(self) -> Dict[str, Any]:
        """Load KPK-specific patterns for layout analysis"""
        return {
            'legal_sections': self.config.LEGAL_SECTION_PATTERNS,
            
            'kpk_headers': [
                r'KHYBER\s+PAKHTUNKHWA\s+FOREST',
                r'FOREST\s+DEPARTMENT\s+KPK',
                r'حکومتِ خیبر پختونخوا',
                r'محکمہ جنگلات',
            ],
            
            'document_types': [
                r'ORDINANCE',
                r'ACT',
                r'NOTIFICATION',
                r'CIRCULAR',
                r'WORKING PLAN',
                r'REPORT',
                r'آرڈیننس',
                r'ایکٹ',
                r'نوٹیفیکیشن',
                r'سرکلر',
            ],
            
            'penalty_sections': [
                r'PENALTY',
                r'FINE',
                r'OFFENSE',
                r'PUNISHMENT',
                r'جرمانہ',
                r'سزا',
                r'ماخوذ',
            ],
        }
    
    def extract_layout(self, 
                      parsed_pdf: Union[PDFParseResult, Dict],
                      document_path: Optional[Union[str, Path]] = None) -> DocumentLayout:
        """
        Extract layout from parsed PDF.
        
        Args:
            parsed_pdf: PDFParseResult from Phase 1.1 or dictionary
            document_path: Optional document path for identification
            
        Returns:
            DocumentLayout with extracted structure
        """
        import time
        start_time = time.time()
        
        try:
            # Convert input if needed
            if isinstance(parsed_pdf, dict):
                # Convert dict to PDFParseResult-like structure
                pdf_result = self._dict_to_parse_result(parsed_pdf, document_path)
            else:
                pdf_result = parsed_pdf
            
            # Generate cache key
            cache_key = self._generate_cache_key(pdf_result, document_path)
            
            # Check cache
            if self.config.CACHE_RESULTS and cache_key in self._layout_cache:
                self.logger.info(f"Returning cached layout for {document_path or 'document'}")
                return self._layout_cache[cache_key]
            
            self.logger.info(f"Extracting layout from {document_path or 'document'}")
            
            # Extract layout for each page
            page_layouts = []
            for page in pdf_result.pages:
                try:
                    page_layout = self._extract_page_layout(page, pdf_result)
                    page_layouts.append(page_layout)
                except Exception as e:
                    self.logger.warning(f"Failed to extract layout for page {page.page_number}: {e}")
                    if self.config.CONTINUE_ON_ERROR:
                        # Create minimal page layout
                        empty_layout = self._create_empty_page_layout(page)
                        page_layouts.append(empty_layout)
                    else:
                        raise
            
            # Analyze document-level structure
            document_layout = self._analyze_document_structure(page_layouts, pdf_result, document_path)
            
            # Cache result
            if self.config.CACHE_RESULTS:
                self._layout_cache[cache_key] = document_layout
            
            # Update statistics
            processing_time = time.time() - start_time
            self._update_statistics(document_layout, processing_time)
            
            # Log abstention if layout quality is poor
            if (self.enable_abstention_logging and self.abstention_logger and 
                document_layout.layout_consistency < 0.5):
                
                self._log_layout_abstention(document_layout, document_path)
            
            self.logger.info(
                f"Layout extraction complete: {document_path or 'document'} - "
                f"Pages: {len(page_layouts)}, "
                f"Elements: {self.stats['elements_detected']['total']}, "
                f"Time: {processing_time:.2f}s"
            )
            
            return document_layout
            
        except Exception as e:
            self.logger.error(f"Layout extraction failed: {e}")
            
            # Create minimal layout with error
            return self._create_error_layout(document_path, str(e))
    
    def _dict_to_parse_result(self, parsed_dict: Dict, document_path: Optional[Union[str, Path]]) -> Dict:
        """Convert dictionary to PDFParseResult-like structure"""
        # This is a simplified conversion
        # In production, you'd properly reconstruct the PDFParseResult
        return {
            'pages': parsed_dict.get('pages', []),
            'metadata': parsed_dict.get('metadata', {}),
            'document_path': str(document_path) if document_path else 'unknown',
        }
    
    def _generate_cache_key(self, pdf_result: Union[PDFParseResult, Dict], 
                           document_path: Optional[Union[str, Path]]) -> str:
        """Generate cache key for document"""
        try:
            if isinstance(pdf_result, PDFParseResult):
                doc_hash = pdf_result.document_hash
            else:
                # Generate hash from document path or content
                if document_path:
                    doc_hash = hashlib.md5(str(document_path).encode()).hexdigest()[:16]
                else:
                    doc_hash = hashlib.md5(str(pdf_result).encode()).hexdigest()[:16]
            
            return f"layout_{doc_hash}"
        except:
            return "layout_unknown"
    
    def _extract_page_layout(self, page: Union[PDFPage, Dict], 
                            pdf_result: Union[PDFParseResult, Dict]) -> PageLayout:
        """Extract layout from single page"""
        page_num = page.page_number if hasattr(page, 'page_number') else page.get('page_number', 0)
        
        self.logger.debug(f"Extracting layout for page {page_num}")
        
        # Get page dimensions
        if hasattr(page, 'width') and hasattr(page, 'height'):
            width, height = page.width, page.height
        else:
            width, height = page.get('width', 612), page.get('height', 792)  # Default letter size
        
        # Extract text blocks
        text_blocks = self._extract_text_blocks(page)
        
        # Create base page layout
        page_layout = PageLayout(
            page_num=page_num,
            width=width,
            height=height,
            elements=[],
            metadata={
                'source_page': page_num,
                'extraction_method': 'layout_analysis',
            }
        )
        
        # Detect columns
        if self.config.COLUMN_DETECTION_ENABLED:
            page_layout.columns = self._detect_columns(text_blocks, width, height)
        
        # Detect margins
        if self.config.MARGIN_DETECTION_ENABLED:
            page_layout.margins = self._detect_margins(text_blocks, width, height)
        
        # Classify text blocks
        classified_elements = self._classify_text_blocks(text_blocks, page_layout)
        
        # Add classified elements to page
        for element in classified_elements:
            page_layout.elements.append(element)
            
            # Categorize elements
            if element.element_type == LayoutElementType.HEADING:
                # Headings are already added as elements
                pass
            elif element.element_type == LayoutElementType.LIST:
                page_layout.lists.append(element)
            elif element.element_type == LayoutElementType.TABLE:
                page_layout.tables.append(element)
        
        # Detect headers and footers
        if self.config.HEADER_FOOTER_ENABLED:
            page_layout.headers, page_layout.footers = self._detect_headers_footers(
                classified_elements, width, height
            )
        
        # Calculate text density
        page_layout.text_density = self._calculate_text_density(classified_elements, width, height)
        
        # Check for KPK patterns
        if self.config.KPK_PATTERN_DETECTION:
            kpk_patterns = self._detect_kpk_patterns(classified_elements)
            if kpk_patterns:
                page_layout.metadata['kpk_patterns'] = kpk_patterns
        
        return page_layout
    
    def _extract_text_blocks(self, page: Union[PDFPage, Dict]) -> List[LayoutElement]:
        """Extract text blocks from page"""
        text_blocks = []
        
        # Get text blocks from page
        if hasattr(page, 'text_blocks'):
            # From PDFPage object
            page_blocks = page.text_blocks
        else:
            # From dictionary
            page_blocks = page.get('text_blocks', [])
        
        for i, block in enumerate(page_blocks):
            try:
                # Get bounding box
                if hasattr(block, 'bbox'):
                    bbox = block.bbox
                else:
                    bbox = block.get('bbox', (0, 0, 100, 100))
                
                # Get text
                if hasattr(block, 'text'):
                    text = block.text
                else:
                    text = block.get('text', '')
                
                # Get font information
                font_size = None
                if hasattr(block, 'font_size'):
                    font_size = block.font_size
                elif isinstance(block, dict):
                    font_size = block.get('font_size')
                
                # Get block type
                block_type = LayoutElementType.UNKNOWN
                if hasattr(block, 'block_type'):
                    type_str = block.block_type
                else:
                    type_str = block.get('block_type', 'unknown')
                
                # Map to LayoutElementType
                type_mapping = {
                    'heading': LayoutElementType.HEADING,
                    'paragraph': LayoutElementType.PARAGRAPH,
                    'list_item': LayoutElementType.LIST_ITEM,
                    'table': LayoutElementType.TABLE,
                    'header': LayoutElementType.HEADER,
                    'footer': LayoutElementType.FOOTER,
                }
                element_type = type_mapping.get(type_str, LayoutElementType.TEXT_BLOCK)
                
                # Create bounding box
                bbox_obj = BoundingBox(
                    x0=bbox[0], y0=bbox[1], x1=bbox[2], y1=bbox[3],
                    page_num=page.page_number if hasattr(page, 'page_number') else page.get('page_number', 0)
                )
                
                # Create layout element
                element = LayoutElement(
                    element_id=f"block_{page.page_number if hasattr(page, 'page_number') else 0}_{i}",
                    element_type=element_type,
                    bbox=bbox_obj,
                    text=text,
                    metadata={
                        'font_size': font_size,
                        'original_type': type_str,
                    }
                )
                
                text_blocks.append(element)
                
            except Exception as e:
                self.logger.debug(f"Failed to extract text block {i}: {e}")
                continue
        
        return text_blocks
    
    def _detect_columns(self, elements: List[LayoutElement], 
                       page_width: float, page_height: float) -> List[Dict[str, Any]]:
        """Detect columns on page"""
        if not elements:
            return [{"type": "single_column", "x_range": (0, page_width)}]
        
        # Collect x-positions of elements
        x_positions = []
        for elem in elements:
            x_positions.append(elem.bbox.x0)
            x_positions.append(elem.bbox.x1)
        
        if len(x_positions) < 10:
            return [{"type": "single_column", "x_range": (0, page_width)}]
        
        # Sort and find gaps
        x_positions.sort()
        gaps = []
        
        for i in range(1, len(x_positions)):
            gap = x_positions[i] - x_positions[i-1]
            if gap > page_width * self.config.COLUMN_SEPARATION_THRESHOLD:
                gaps.append((x_positions[i-1], x_positions[i], gap))
        
        if not gaps:
            return [{"type": "single_column", "x_range": (0, page_width)}]
        
        # Find significant gaps (potential column separators)
        significant_gaps = []
        for gap in gaps:
            if gap[2] > page_width * 0.1:  # At least 10% of page width
                significant_gaps.append(gap)
        
        if not significant_gaps:
            return [{"type": "single_column", "x_range": (0, page_width)}]
        
        # Sort by gap size
        significant_gaps.sort(key=lambda x: x[2], reverse=True)
        
        # Limit to max columns
        max_gaps = min(len(significant_gaps), self.config.MAX_COLUMNS - 1)
        column_separators = []
        
        for i in range(max_gaps):
            separator = (significant_gaps[i][0] + significant_gaps[i][1]) / 2
            column_separators.append(separator)
        
        # Sort separators
        column_separators.sort()
        
        # Create column definitions
        columns = []
        prev_separator = 0
        
        for i, separator in enumerate(column_separators):
            columns.append({
                "type": f"column_{i+1}",
                "x_range": (prev_separator, separator),
                "width": separator - prev_separator,
            })
            prev_separator = separator
        
        # Add last column
        columns.append({
            "type": f"column_{len(column_separators)+1}",
            "x_range": (prev_separator, page_width),
            "width": page_width - prev_separator,
        })
        
        return columns
    
    def _detect_margins(self, elements: List[LayoutElement], 
                       page_width: float, page_height: float) -> Dict[str, float]:
        """Detect page margins"""
        if not elements:
            return self.config.DEFAULT_MARGINS.copy()
        
        # Find extreme positions
        left_margin = min(elem.bbox.x0 for elem in elements)
        right_margin = page_width - max(elem.bbox.x1 for elem in elements)
        top_margin = min(elem.bbox.y0 for elem in elements)
        bottom_margin = page_height - max(elem.bbox.y1 for elem in elements)
        
        # Ensure non-negative margins
        margins = {
            'left': max(0, left_margin),
            'right': max(0, right_margin),
            'top': max(0, top_margin),
            'bottom': max(0, bottom_margin),
        }
        
        # Use defaults if margins are too large (likely error)
        max_margin = page_width * 0.3  # 30% max margin
        for key in margins:
            if margins[key] > max_margin:
                margins[key] = self.config.DEFAULT_MARGINS[key]
        
        return margins
    
    def _classify_text_blocks(self, text_blocks: List[LayoutElement],
                             page_layout: PageLayout) -> List[LayoutElement]:
        """Classify text blocks into specific element types"""
        classified = []
        
        # First pass: basic classification
        for block in text_blocks:
            element_type = self._classify_single_block(block, page_layout)
            block.element_type = element_type
            classified.append(block)
        
        # Second pass: group related elements
        grouped = self._group_related_elements(classified, page_layout)
        
        return grouped
    
    def _classify_single_block(self, block: LayoutElement,
                              page_layout: PageLayout) -> LayoutElementType:
        """Classify a single text block"""
        text = block.text or ""
        
        # Check for headers/footers based on position
        if self._is_header_position(block.bbox, page_layout.height):
            return LayoutElementType.HEADER
        
        if self._is_footer_position(block.bbox, page_layout.height):
            return LayoutElementType.FOOTER
        
        # Check for page numbers
        if self._is_page_number(text, block.bbox, page_layout):
            return LayoutElementType.PAGE_NUMBER
        
        # Check for headings
        if self._is_heading(text, block):
            return LayoutElementType.HEADING
        
        # Check for list items
        if self._is_list_item(text):
            return LayoutElementType.LIST_ITEM
        
        # Check for KPK legal sections
        if self._is_legal_section(text):
            block.metadata['is_legal_section'] = True
            return LayoutElementType.HEADING
        
        # Default to paragraph
        return LayoutElementType.PARAGRAPH
    
    def _is_header_position(self, bbox: BoundingBox, page_height: float) -> bool:
        """Check if element is in header position"""
        header_threshold = page_height * self.config.HEADER_THRESHOLD
        return bbox.y1 < header_threshold
    
    def _is_footer_position(self, bbox: BoundingBox, page_height: float) -> bool:
        """Check if element is in footer position"""
        footer_threshold = page_height * self.config.FOOTER_THRESHOLD
        return bbox.y0 > footer_threshold
    
    def _is_page_number(self, text: str, bbox: BoundingBox, 
                       page_layout: PageLayout) -> bool:
        """Check if element is a page number"""
        # Page numbers are usually:
        # 1. Single numbers or Roman numerals
        # 2. Located at bottom center or corners
        # 3. Short text
        
        if not text or len(text.strip()) > 10:
            return False
        
        # Check if text looks like a page number
        cleaned = text.strip()
        if cleaned.isdigit() or self._is_roman_numeral(cleaned):
            # Check position (usually bottom of page)
            if bbox.y0 > page_layout.height * 0.8:  # Bottom 20%
                return True
        
        return False
    
    def _is_roman_numeral(self, text: str) -> bool:
        """Check if text is a Roman numeral"""
        roman_pattern = r'^[IVXLCDM]+$'
        return bool(re.match(roman_pattern, text.upper()))
    
    def _is_heading(self, text: str, block: LayoutElement) -> bool:
        """Check if text block is a heading"""
        if not text or len(text.strip()) == 0:
            return False
        
        text = text.strip()
        words = text.split()
        
        # Heading heuristics
        
        # 1. All caps with multiple words
        if text.isupper() and len(words) >= self.config.HEADING_ALL_CAPS_THRESHOLD:
            return True
        
        # 2. Title case with limited words
        if text.istitle() and len(words) <= 10:
            return True
        
        # 3. Font size larger than normal (if available)
        font_size = block.metadata.get('font_size')
        if font_size and font_size > 12:  # Assuming 12pt is normal
            return True
        
        # 4. Section patterns
        section_patterns = [
            r'^Section\s+\d+',
            r'^Chapter\s+\d+',
            r'^Article\s+\d+',
            r'^Appendix\s+[A-Z]',
        ]
        
        for pattern in section_patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return True
        
        return False
    
    def _is_list_item(self, text: str) -> bool:
        """Check if text is a list item"""
        if not text:
            return False
        
        text = text.strip()
        
        # Check for list prefixes
        for pattern in self.config.LIST_PREFIX_PATTERNS:
            if re.match(pattern, text):
                return True
        
        return False
    
    def _is_legal_section(self, text: str) -> bool:
        """Check if text contains legal section patterns"""
        if not text:
            return False
        
        for pattern in self.kpk_patterns['legal_sections']:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        return False
    
    def _group_related_elements(self, elements: List[LayoutElement],
                               page_layout: PageLayout) -> List[LayoutElement]:
        """Group related elements (lists, paragraphs in same column, etc.)"""
        if not elements:
            return elements
        
        # Group list items into lists
        grouped_elements = self._group_list_items(elements)
        
        # Group paragraphs in same column/region
        if page_layout.columns and len(page_layout.columns) > 1:
            grouped_elements = self._group_by_columns(grouped_elements, page_layout.columns)
        
        return grouped_elements
    
    def _group_list_items(self, elements: List[LayoutElement]) -> List[LayoutElement]:
        """Group consecutive list items into lists"""
        grouped = []
        current_list = None
        list_items = []
        
        for element in elements:
            if element.element_type == LayoutElementType.LIST_ITEM:
                list_items.append(element)
            else:
                # Process any accumulated list items
                if list_items:
                    current_list = self._create_list_element(list_items)
                    grouped.append(current_list)
                    list_items = []
                
                grouped.append(element)
        
        # Process any remaining list items
        if list_items:
            current_list = self._create_list_element(list_items)
            grouped.append(current_list)
        
        return grouped
    
    def _create_list_element(self, list_items: List[LayoutElement]) -> LayoutElement:
        """Create a list element from list items"""
        if not list_items:
            return None
        
        # Calculate combined bounding box
        x0 = min(item.bbox.x0 for item in list_items)
        y0 = min(item.bbox.y0 for item in list_items)
        x1 = max(item.bbox.x1 for item in list_items)
        y1 = max(item.bbox.y1 for item in list_items)
        
        # Create list element
        list_element = LayoutElement(
            element_id=f"list_{list_items[0].bbox.page_num}_{hashlib.md5(str(list_items).encode()).hexdigest()[:8]}",
            element_type=LayoutElementType.LIST,
            bbox=BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1, page_num=list_items[0].bbox.page_num),
            text=None,
            metadata={'item_count': len(list_items)},
            children=list_items
        )
        
        return list_element
    
    def _group_by_columns(self, elements: List[LayoutElement],
                         columns: List[Dict[str, Any]]) -> List[LayoutElement]:
        """Group elements by columns"""
        if not columns or len(columns) <= 1:
            return elements
        
        # Create column elements
        column_elements = []
        
        for i, column_def in enumerate(columns):
            # Find elements in this column
            col_elements = []
            x_range = column_def['x_range']
            
            for element in elements:
                # Check if element center is within column
                center_x = element.bbox.center[0]
                if x_range[0] <= center_x <= x_range[1]:
                    col_elements.append(element)
            
            if col_elements:
                # Create column element
                column_element = LayoutElement(
                    element_id=f"column_{i+1}_{col_elements[0].bbox.page_num}",
                    element_type=LayoutElementType.COLUMN,
                    bbox=BoundingBox(
                        x0=x_range[0], y0=0, x1=x_range[1], 
                        y1=max(e.bbox.y1 for e in col_elements),
                        page_num=col_elements[0].bbox.page_num
                    ),
                    text=None,
                    metadata={'column_index': i, 'element_count': len(col_elements)},
                    children=col_elements
                )
                column_elements.append(column_element)
        
        return column_elements
    
    def _detect_headers_footers(self, elements: List[LayoutElement],
                               page_width: float, page_height: float) -> Tuple[List[LayoutElement], List[LayoutElement]]:
        """Detect headers and footers"""
        headers = []
        footers = []
        
        header_threshold = page_height * self.config.HEADER_THRESHOLD
        footer_threshold = page_height * self.config.FOOTER_THRESHOLD
        
        for element in elements:
            if element.element_type == LayoutElementType.HEADER:
                headers.append(element)
            elif element.element_type == LayoutElementType.FOOTER:
                footers.append(element)
            elif element.bbox.y1 < header_threshold:
                # Element in header region but not classified as header
                element.element_type = LayoutElementType.HEADER
                headers.append(element)
            elif element.bbox.y0 > footer_threshold:
                # Element in footer region but not classified as footer
                element.element_type = LayoutElementType.FOOTER
                footers.append(element)
        
        return headers, footers
    
    def _calculate_text_density(self, elements: List[LayoutElement],
                               page_width: float, page_height: float) -> float:
        """Calculate text density on page"""
        if not elements:
            return 0.0
        
        # Calculate total area covered by text elements
        text_area = 0.0
        for element in elements:
            text_area += element.bbox.area
        
        page_area = page_width * page_height
        if page_area == 0:
            return 0.0
        
        return text_area / page_area
    
    def _detect_kpk_patterns(self, elements: List[LayoutElement]) -> Dict[str, List[str]]:
        """Detect KPK-specific patterns in elements"""
        found_patterns = {}
        
        for pattern_type, patterns in self.kpk_patterns.items():
            matches = []
            for element in elements:
                if element.text:
                    for pattern in patterns:
                        pattern_matches = re.findall(pattern, element.text, re.IGNORECASE)
                        if pattern_matches:
                            matches.extend(pattern_matches)
            
            if matches:
                found_patterns[pattern_type] = list(set(matches))
        
        return found_patterns
    
    def _analyze_document_structure(self, page_layouts: List[PageLayout],
                                   pdf_result: Union[PDFParseResult, Dict],
                                   document_path: Optional[Union[str, Path]]) -> DocumentLayout:
        """Analyze document-level structure"""
        # Generate document hash
        if isinstance(pdf_result, PDFParseResult):
            doc_hash = pdf_result.document_hash
            doc_path = pdf_result.document_path
        else:
            doc_hash = hashlib.md5(str(document_path or str(pdf_result)).encode()).hexdigest()[:16]
            doc_path = str(document_path) if document_path else 'unknown'
        
        # Extract sections and TOC
        sections = self._extract_sections(page_layouts)
        toc = self._extract_table_of_contents(page_layouts)
        
        # Calculate layout consistency
        layout_consistency = self._calculate_layout_consistency(page_layouts)
        
        # Create document hierarchy
        document_hierarchy = self._create_document_hierarchy(page_layouts)
        
        # Create document layout
        document_layout = DocumentLayout(
            document_path=doc_path,
            document_hash=doc_hash,
            pages=page_layouts,
            metadata={
                'extraction_timestamp': datetime.now().isoformat(),
                'source_document': doc_path,
                'layout_analysis_method': 'structured_extraction',
            },
            sections=sections,
            toc=toc,
            document_hierarchy=document_hierarchy,
            layout_consistency=layout_consistency,
        )
        
        return document_layout
    
    def _extract_sections(self, page_layouts: List[PageLayout]) -> List[Dict[str, Any]]:
        """Extract document sections from headings"""
        sections = []
        current_section = None
        
        for page in page_layouts:
            headings = page.get_elements_by_type(LayoutElementType.HEADING)
            
            for heading in headings:
                if heading.text:
                    section = {
                        'title': heading.text,
                        'page': page.page_num,
                        'position': heading.bbox.to_dict(),
                        'level': self._estimate_heading_level(heading),
                        'metadata': heading.metadata,
                    }
                    sections.append(section)
        
        return sections
    
    def _estimate_heading_level(self, heading: LayoutElement) -> int:
        """Estimate heading level (1=highest, 6=lowest)"""
        text = heading.text or ""
        font_size = heading.metadata.get('font_size', 12)
        
        # Simple heuristic based on font size and text properties
        if font_size > 20:
            return 1
        elif font_size > 16:
            return 2
        elif font_size > 14:
            return 3
        elif font_size > 12:
            return 4
        elif text.isupper() and len(text.split()) >= 3:
            return 2  # All-caps headings are often main headings
        else:
            return 5
    
    def _extract_table_of_contents(self, page_layouts: List[PageLayout]) -> List[Dict[str, Any]]:
        """Extract table of contents"""
        toc = []
        
        # Look for TOC on first few pages
        toc_pages = page_layouts[:min(5, len(page_layouts))]
        
        for page in toc_pages:
            # Look for TOC patterns
            for element in page.elements:
                if element.text and ('contents' in element.text.lower() or 
                                    'فہرست' in element.text or 
                                    'جدول' in element.text):
                    # This might be a TOC page
                    toc.extend(self._extract_toc_from_page(page))
                    break
        
        return toc
    
    def _extract_toc_from_page(self, page: PageLayout) -> List[Dict[str, Any]]:
        """Extract TOC entries from a page"""
        toc_entries = []
        
        # Look for patterns common in TOCs
        toc_patterns = [
            r'^\d+\s+\.',  # 1. Title
            r'^\d+\.\d+',  # 1.1 Title
            r'^[A-Z]\.',   # A. Title
            r'^Appendix',  # Appendix A
        ]
        
        for element in page.elements:
            if element.text:
                for pattern in toc_patterns:
                    if re.match(pattern, element.text.strip()):
                        # Extract page number if present
                        page_match = re.search(r'(\d+)$', element.text.strip())
                        page_num = int(page_match.group(1)) if page_match else None
                        
                        entry = {
                            'title': element.text.strip(),
                            'toc_page': page.page_num,
                            'target_page': page_num,
                            'position': element.bbox.to_dict(),
                        }
                        toc_entries.append(entry)
                        break
        
        return toc_entries
    
    def _calculate_layout_consistency(self, page_layouts: List[PageLayout]) -> float:
        """Calculate layout consistency across pages"""
        if len(page_layouts) < 2:
            return 1.0  # Single page is consistent by definition
        
        consistency_scores = []
        
        # Compare margins
        margin_scores = []
        for i in range(1, len(page_layouts)):
            prev_margins = page_layouts[i-1].margins
            curr_margins = page_layouts[i].margins
            
            if prev_margins and curr_margins:
                # Calculate margin similarity
                margin_diff = 0
                for key in ['left', 'right', 'top', 'bottom']:
                    if key in prev_margins and key in curr_margins:
                        diff = abs(prev_margins[key] - curr_margins[key])
                        max_margin = max(prev_margins[key], curr_margins[key])
                        if max_margin > 0:
                            margin_diff += diff / max_margin
                
                margin_similarity = 1.0 - (margin_diff / 4)  # Average over 4 margins
                margin_scores.append(max(0, margin_similarity))
        
        if margin_scores:
            consistency_scores.append(statistics.mean(margin_scores))
        
        # Compare column structure
        column_scores = []
        for i in range(1, len(page_layouts)):
            prev_cols = len(page_layouts[i-1].columns)
            curr_cols = len(page_layouts[i].columns)
            
            if prev_cols == curr_cols:
                column_scores.append(1.0)
            elif abs(prev_cols - curr_cols) == 1:
                column_scores.append(0.5)  # Minor change
            else:
                column_scores.append(0.0)  # Major change
        
        if column_scores:
            consistency_scores.append(statistics.mean(column_scores))
        
        # Compare text density
        density_scores = []
        densities = [p.text_density for p in page_layouts if p.text_density > 0]
        if len(densities) >= 2:
            mean_density = statistics.mean(densities)
            std_density = statistics.stdev(densities) if len(densities) > 2 else 0
            
            if mean_density > 0:
                # Lower std = more consistent
                cv = std_density / mean_density  # Coefficient of variation
                density_consistency = 1.0 - min(cv, 1.0)  # Cap at 1.0
                consistency_scores.append(density_consistency)
        
        if consistency_scores:
            return statistics.mean(consistency_scores)
        else:
            return 0.5  # Default consistency
    
    def _create_document_hierarchy(self, page_layouts: List[PageLayout]) -> List[LayoutElement]:
        """Create document hierarchy from page layouts"""
        # For now, create a simple hierarchy
        # In production, this would be more sophisticated
        
        if not page_layouts:
            return []
        
        # Create root document element
        root_element = LayoutElement(
            element_id="document_root",
            element_type=LayoutElementType.PAGE,
            bbox=BoundingBox(x0=0, y0=0, x1=page_layouts[0].width, y1=page_layouts[0].height, page_num=0),
            text=None,
            metadata={'element_count': len(page_layouts), 'type': 'document_root'},
        )
        
        # Add pages as children
        for page in page_layouts:
            page_element = LayoutElement(
                element_id=f"page_{page.page_num}",
                element_type=LayoutElementType.PAGE,
                bbox=BoundingBox(x0=0, y0=0, x1=page.width, y1=page.height, page_num=page.page_num),
                text=None,
                metadata={'page_number': page.page_num, 'element_count': len(page.elements)},
            )
            
            # Add page elements as children of page
            for elem in page.elements:
                page_element.add_child(elem)
            
            root_element.add_child(page_element)
        
        return [root_element]
    
    def _create_empty_page_layout(self, page: Union[PDFPage, Dict]) -> PageLayout:
        """Create empty page layout for error handling"""
        page_num = page.page_number if hasattr(page, 'page_number') else page.get('page_number', 0)
        width = page.width if hasattr(page, 'width') else page.get('width', 612)
        height = page.height if hasattr(page, 'height') else page.get('height', 792)
        
        return PageLayout(
            page_num=page_num,
            width=width,
            height=height,
            elements=[],
            metadata={
                'source_page': page_num,
                'error': 'layout_extraction_failed',
                'extraction_method': 'fallback',
            }
        )
    
    def _create_error_layout(self, document_path: Optional[Union[str, Path]], 
                            error_message: str) -> DocumentLayout:
        """Create error layout when extraction fails"""
        doc_path = str(document_path) if document_path else 'unknown'
        doc_hash = hashlib.md5(doc_path.encode()).hexdigest()[:16]
        
        return DocumentLayout(
            document_path=doc_path,
            document_hash=doc_hash,
            pages=[],
            metadata={
                'error': error_message,
                'extraction_timestamp': datetime.now().isoformat(),
                'status': 'failed',
            }
        )
    
    def _update_statistics(self, document_layout: DocumentLayout, processing_time: float):
        """Update extractor statistics"""
        self.stats['documents_processed'] += 1
        self.stats['total_pages_processed'] += len(document_layout.pages)
        self.stats['processing_time_total'] += processing_time
        
        # Count elements
        total_elements = 0
        for page in document_layout.pages:
            total_elements += len(page.elements)
            
            # Count by type
            for elem in page.elements:
                elem_type = elem.element_type.value
                if elem_type in self.stats['elements_detected']:
                    self.stats['elements_detected'][elem_type] += 1
        
        self.stats['elements_detected']['total'] += total_elements
        
        # Update layout quality
        consistency = document_layout.layout_consistency
        if consistency >= 0.8:
            self.stats['layout_quality']['excellent'] += 1
        elif consistency >= 0.6:
            self.stats['layout_quality']['good'] += 1
        elif consistency >= 0.4:
            self.stats['layout_quality']['fair'] += 1
        else:
            self.stats['layout_quality']['poor'] += 1
        
        # Check for KPK documents
        for page in document_layout.pages:
            if 'kpk_patterns' in page.metadata:
                self.stats['kpk_documents'] += 1
                break
        
        # Check for legal documents
        if any('legal_sections' in page.metadata.get('kpk_patterns', {}) 
               for page in document_layout.pages):
            self.stats['legal_documents'] += 1
        
        # Check for multi-column documents
        if any(len(page.columns) > 1 for page in document_layout.pages):
            self.stats['multi_column_documents'] += 1
        
        # Update performance metrics
        perf = self.stats['performance']
        perf['extraction_times'].append(processing_time)
        perf['fastest_extraction'] = min(perf['fastest_extraction'], processing_time)
        perf['slowest_extraction'] = max(perf['slowest_extraction'], processing_time)
        
        # Calculate averages
        total_docs = self.stats['documents_processed']
        if total_docs > 0:
            self.stats['avg_processing_time'] = self.stats['processing_time_total'] / total_docs
    
    def _log_layout_abstention(self, document_layout: DocumentLayout, 
                              document_path: Optional[Union[str, Path]]):
        """Log abstention for poor layout quality"""
        if self.enable_abstention_logging and self.abstention_logger:
            try:
                context = create_abstention_context(
                    stage=PipelineStage.LAYOUT_EXTRACTION,
                    component="LayoutExtractor",
                    document_path=str(document_path) if document_path else 'unknown',
                    reason="poor_layout_quality",
                    details={
                        'layout_consistency': document_layout.layout_consistency,
                        'total_pages': len(document_layout.pages),
                        'total_elements': sum(len(p.elements) for p in document_layout.pages),
                        'is_kpk_document': any('kpk_patterns' in p.metadata for p in document_layout.pages),
                    }
                )
                
                self.abstention_logger.log_abstention(
                    abstention_type=AbstentionType.LAYOUT_ISSUE,
                    severity=AbstentionSeverity.MEDIUM,
                    context=context,
                    suggested_action="Manual layout review or improve source document quality",
                    confidence=1.0 - document_layout.layout_consistency,
                    component_state=document_layout.to_dict(),
                )
                
                self.logger.info(f"Logged layout abstention for {document_path or 'document'}")
                
            except Exception as e:
                self.logger.warning(f"Failed to log layout abstention: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get current extractor statistics"""
        stats = self.stats.copy()
        
        # Calculate derived statistics
        total_processed = stats['documents_processed']
        if total_processed > 0:
            stats['avg_processing_time'] = stats['processing_time_total'] / total_processed
            
            # Calculate percentages
            total_quality = sum(stats['layout_quality'].values())
            for quality in stats['layout_quality']:
                count = stats['layout_quality'][quality]
                stats['layout_quality'][f"{quality}_pct"] = (
                    count / total_quality * 100 if total_quality > 0 else 0
                )
        
        # Add performance summary
        perf = stats['performance']
        if perf['extraction_times']:
            perf['avg_extraction_time'] = sum(perf['extraction_times']) / len(perf['extraction_times'])
        else:
            perf['avg_extraction_time'] = 0.0
            perf['fastest_extraction'] = 0.0
        
        return stats

# ============================================================================
# VISUALIZATION (Optional)
# ============================================================================

class LayoutVisualizer:
    """Visualize extracted layout"""
    
    @staticmethod
    def visualize_page_layout(page_layout: PageLayout, output_path: Optional[Path] = None):
        """Create visualization of page layout"""
        # This would create an image showing layout elements
        # For now, just return a simple representation
        
        visualization = {
            'page_number': page_layout.page_num,
            'dimensions': {'width': page_layout.width, 'height': page_layout.height},
            'margins': page_layout.margins,
            'columns': len(page_layout.columns),
            'elements': {
                'total': len(page_layout.elements),
                'by_type': {},
            },
        }
        
        # Count elements by type
        for elem in page_layout.elements:
            elem_type = elem.element_type.value
            visualization['elements']['by_type'][elem_type] = \
                visualization['elements']['by_type'].get(elem_type, 0) + 1
        
        return visualization

# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    """Main function for standalone testing"""
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description="Document Layout Extractor")
    parser.add_argument("--input", required=True, help="Input JSON from PDF parser")
    parser.add_argument("--output", help="Output JSON file for layout")
    parser.add_argument("--config", help="Configuration file (JSON)")
    parser.add_argument("--visualize", action="store_true", help="Generate visualization")
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
    
    # Load parsed PDF
    with open(args.input, 'r', encoding='utf-8') as f:
        parsed_pdf = json.load(f)
    
    # Extract layout
    extractor = LayoutExtractor(config=config)
    document_layout = extractor.extract_layout(parsed_pdf, args.input)
    
    # Save or display results
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(document_layout.to_dict(), f, indent=2, ensure_ascii=False)
        print(f"Layout saved to {args.output}")
    else:
        print(json.dumps(document_layout.to_dict(), indent=2))
    
    # Print summary
    print(f"\nLayout Extraction Summary:")
    print(f"  Pages processed: {len(document_layout.pages)}")
    print(f"  Sections found: {len(document_layout.sections)}")
    print(f"  Layout consistency: {document_layout.layout_consistency:.2%}")
    print(f"  Text density (avg): {document_layout.avg_text_density:.2%}")
    
    # Count element types
    element_counts = {}
    for page in document_layout.pages:
        for elem in page.elements:
            elem_type = elem.element_type.value
            element_counts[elem_type] = element_counts.get(elem_type, 0) + 1
    
    print(f"\nElement Counts:")
    for elem_type, count in sorted(element_counts.items()):
        print(f"  {elem_type}: {count}")
    
    # Generate visualization if requested
    if args.visualize and document_layout.pages:
        visualizer = LayoutVisualizer()
        visualization = visualizer.visualize_page_layout(document_layout.pages[0])
        viz_file = Path(args.output or 'layout_visualization.json').with_suffix('.viz.json')
        with open(viz_file, 'w') as f:
            json.dump(visualization, f, indent=2)
        print(f"\nVisualization saved to {viz_file}")
    
    # Print statistics
    stats = extractor.get_statistics()
    print(f"\nExtractor Statistics:")
    print(f"  Documents Processed: {stats['documents_processed']}")
    print(f"  Average Processing Time: {stats['avg_processing_time']:.2f}s")
    print(f"  KPK Documents: {stats['kpk_documents']}")
    print(f"  Multi-column Documents: {stats['multi_column_documents']}")

if __name__ == "__main__":
    main()
