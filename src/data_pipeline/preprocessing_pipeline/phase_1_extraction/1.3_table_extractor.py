"""
TABLE_EXTRACTOR.PY - Phase 1.3: KPK Forestry Document Table & Form Extraction
Specialized for KPK forestry forms: FIR forms, permit applications, auction sheets, etc.
Author: Hina Ali, Eman Irfan
Date: January 29, 2026
"""

import re
import json
import logging
import numpy as np
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union, Set, Generator
from dataclasses import dataclass, asdict, field
from datetime import datetime
from collections import defaultdict, OrderedDict
from enum import Enum
import statistics
import hashlib

# Third-party imports
import pdfplumber
import pymupdf  # PyMuPDF
from PIL import Image
import cv2
import pandas as pd
from sklearn.cluster import KMeans

# Import from common modules
try:
    from preprocessing_pipeline.common.config import PipelineConfig, TableExtractionConfig
    from preprocessing_pipeline.common.constants import *
    USE_COMMON_CONFIG = True
except ImportError:
    USE_COMMON_CONFIG = False
    print("Warning: common.config not found. Using default configuration.")

# Import shared types to avoid circularity
from .types import (
    PDFParseResult, PDFPage, DocumentLayout, PageLayout, LayoutElement, 
    LayoutElementType, TableCell, ExtractedTable, ExtractedForm, 
    TableExtractionResult, TableType, FormField
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
    print("Warning: Phase 1 modules not available. Running in standalone mode.")

# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class TableExtractionConfig:
    """Configuration for table and form extraction"""
    
    # Extraction methods
    EXTRACT_TABLES: bool = True
    EXTRACT_FORMS: bool = True
    EXTRACT_SCHEDULES: bool = True
    
    # Table detection parameters
    MIN_TABLE_ROWS: int = 2
    MIN_TABLE_COLUMNS: int = 2
    MAX_TABLE_COLUMNS: int = 10
    TABLE_DETECTION_CONFIDENCE: float = 0.7
    
    # Form detection
    FORM_DETECTION_ENABLED: bool = True
    FORM_CONFIDENCE_THRESHOLD: float = 0.6
    
    # KPK-specific patterns
    KPK_PATTERN_DETECTION: bool = True
    EXTRACT_KPK_ENTITIES: bool = True
    
    # Extraction strategies
    USE_PDFPLUMBER_TABLES: bool = True
    USE_MANUAL_EXTRACTION: bool = True
    USE_OCR_FALLBACK: bool = True
    OCR_RESOLUTION: int = 300  # DPI
    
    # Output formatting
    PRESERVE_TABLE_STRUCTURE: bool = True
    GENERATE_PANDAS_DF: bool = False
    GENERATE_HTML_TABLE: bool = False
    NORMALIZE_CELL_VALUES: bool = True
    
    # Performance
    PARALLEL_PROCESSING: bool = False
    MAX_WORKERS: int = 4
    CACHE_RESULTS: bool = True
    
    # Error handling
    CONTINUE_ON_ERROR: bool = True
    LOG_DETAILED_ERRORS: bool = True
    
    # Quality control
    MIN_CELL_CONFIDENCE: float = 0.5
    VALIDATE_TABLE_STRUCTURE: bool = True
    MERGE_SPLIT_CELLS: bool = True

# ============================================================================
# DATA CLASSES
# ============================================================================

class TableType(Enum):
    """Types of tables/forms"""
    REGULAR_TABLE = "regular_table"
    FORM = "form"
    SCHEDULE = "schedule"
    MATRIX = "matrix"
    TIMETABLE = "timetable"
    INVENTORY = "inventory"
    REGISTER = "register"
    UNKNOWN = "unknown"

@dataclass
class TableCell:
    """Represents a single table cell"""
    row_index: int
    col_index: int
    text: str
    bbox: Tuple[float, float, float, float]  # x0, y0, x1, y1
    confidence: float = 1.0
    is_header: bool = False
    rowspan: int = 1
    colspan: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'row': self.row_index,
            'column': self.col_index,
            'text': self.text,
            'bbox': self.bbox,
            'is_header': self.is_header,
            'rowspan': self.rowspan,
            'colspan': self.colspan,
            'confidence': self.confidence,
        }

@dataclass
class ExtractedTable:
    """Represents an extracted table"""
    table_id: str
    table_type: TableType
    page_num: int
    bbox: Tuple[float, float, float, float]  # x0, y0, x1, y1
    
    # Table data
    rows: List[List[TableCell]]
    header_rows: List[int] = field(default_factory=list)
    
    # Metadata
    extraction_method: str = "unknown"
    confidence: float = 1.0
    row_count: int = 0
    column_count: int = 0
    has_merged_cells: bool = False
    
    # KPK-specific
    is_kpk_form: bool = False
    kpk_form_type: Optional[str] = None
    detected_entities: Dict[str, List[str]] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate derived fields"""
        self.row_count = len(self.rows)
        if self.rows:
            self.column_count = max(len(row) for row in self.rows)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['table_type'] = self.table_type.value
        data['rows'] = [[cell.to_dict() for cell in row] for row in self.rows]
        return data
    
    def to_dataframe(self) -> Optional[pd.DataFrame]:
        """Convert to pandas DataFrame"""
        if not self.rows:
            return None
        
        # Create 2D array of cell texts
        data = []
        for row in self.rows:
            row_data = []
            for cell in row:
                row_data.append(cell.text)
            data.append(row_data)
        
        # Create DataFrame
        df = pd.DataFrame(data)
        
        # Set headers if available
        if self.header_rows and self.header_rows[0] < len(data):
            df.columns = data[self.header_rows[0]]
            df = df.drop(self.header_rows)
        
        return df
    
    def get_cell(self, row: int, col: int) -> Optional[TableCell]:
        """Get cell at position"""
        if 0 <= row < len(self.rows):
            row_cells = self.rows[row]
            for cell in row_cells:
                if cell.col_index <= col < cell.col_index + cell.colspan:
                    return cell
        return None
    
    def get_column(self, col_index: int) -> List[TableCell]:
        """Get all cells in a column"""
        column_cells = []
        for row in self.rows:
            for cell in row:
                if cell.col_index <= col_index < cell.col_index + cell.colspan:
                    column_cells.append(cell)
                    break
        return column_cells
    
    def extract_structured_data(self) -> Dict[str, Any]:
        """Extract structured data from table"""
        structured = {
            'table_type': self.table_type.value,
            'dimensions': {'rows': self.row_count, 'columns': self.column_count},
            'data': [],
            'entities': self.detected_entities,
        }
        
        for row in self.rows:
            row_data = {}
            for cell in row:
                if cell.text:
                    key = f"col_{cell.col_index}" if not cell.is_header else cell.text
                    row_data[key] = cell.text
            if row_data:
                structured['data'].append(row_data)
        
        return structured

@dataclass
class FormField:
    """Represents a form field"""
    field_name: str
    field_value: str
    field_type: str  # 'text', 'number', 'date', 'select', 'checkbox'
    bbox: Optional[Tuple[float, float, float, float]] = None
    confidence: float = 1.0
    validation_rules: List[str] = field(default_factory=list)
    is_required: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

@dataclass
class ExtractedForm:
    """Represents an extracted form"""
    form_id: str
    form_type: str
    page_num: int
    bbox: Tuple[float, float, float, float]
    
    # Form data
    fields: List[FormField]
    tables: List[ExtractedTable] = field(default_factory=list)
    
    # Metadata
    extraction_method: str = "unknown"
    confidence: float = 1.0
    is_kpk_form: bool = True
    kpk_form_subtype: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['fields'] = [field.to_dict() for field in self.fields]
        data['tables'] = [table.to_dict() for table in self.tables]
        return data
    
    def get_field(self, field_name: str) -> Optional[FormField]:
        """Get field by name"""
        for field in self.fields:
            if field.field_name == field_name:
                return field
        return None
    
    def to_structured_dict(self) -> Dict[str, Any]:
        """Convert form to structured dictionary"""
        structured = {
            'form_type': self.form_type,
            'kpk_subtype': self.kpk_form_subtype,
            'fields': {},
            'tables': [],
        }
        
        for field in self.fields:
            structured['fields'][field.field_name] = field.field_value
        
        for table in self.tables:
            structured['tables'].append(table.extract_structured_data())
        
        return structured

@dataclass
class TableExtractionResult:
    """Result of table extraction"""
    document_path: str
    document_hash: str
    extraction_timestamp: datetime
    
    # Extracted content
    tables: List[ExtractedTable]
    forms: List[ExtractedForm]
    
    # Statistics
    total_tables: int = 0
    total_forms: int = 0
    kpk_tables: int = 0
    kpk_forms: int = 0
    
    # Metadata
    extraction_methods: List[str] = field(default_factory=list)
    confidence_score: float = 0.0
    
    # Errors and warnings
    extraction_errors: List[str] = field(default_factory=list)
    extraction_warnings: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Calculate derived fields"""
        self.total_tables = len(self.tables)
        self.total_forms = len(self.forms)
        self.kpk_tables = sum(1 for t in self.tables if t.is_kpk_form)
        self.kpk_forms = sum(1 for f in self.forms if f.is_kpk_form)
        
        if self.tables or self.forms:
            confidences = []
            if self.tables:
                confidences.extend([t.confidence for t in self.tables])
            if self.forms:
                confidences.extend([f.confidence for f in self.forms])
            self.confidence_score = statistics.mean(confidences) if confidences else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['tables'] = [table.to_dict() for table in self.tables]
        data['forms'] = [form.to_dict() for form in self.forms]
        data['extraction_timestamp'] = self.extraction_timestamp.isoformat()
        return data
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get extraction statistics"""
        return {
            'total_tables': self.total_tables,
            'total_forms': self.total_forms,
            'kpk_tables': self.kpk_tables,
            'kpk_forms': self.kpk_forms,
            'confidence_score': self.confidence_score,
            'extraction_methods': list(set(self.extraction_methods)),
        }

# ============================================================================
# KPK FORM TEMPLATES
# ============================================================================

class KPKFormTemplates:
    """KPK forestry form templates and patterns"""
    
    FORM_TEMPLATES = {
        # FIR (First Information Report) Form
        'fir_form': {
            'indicators': ['FIR NO', 'FIR FORM', 'FOREST OFFENCE REPORT', 'ACCUSED', 'SEIZURE'],
            'fields': [
                'FIR No', 'Date', 'Police Station', 'Beat',
                'Accused Name', 'Father Name', 'CNIC', 'Address',
                'Offence Description', 'Section Violated',
                'Timber Species', 'Quantity', 'Vehicle No',
                'Seized By', 'Designation', 'Remarks'
            ],
            'structure': 'form',
            'kpk_specific': True,
            'category': 'legal',
        },
        
        # Timber Transit Permit
        'transit_permit': {
            'indicators': ['TIMBER TRANSPORT PERMIT', 'TRANSIT PERMIT', 'PERMIT NO'],
            'fields': [
                'Permit No', 'Date of Issue', 'Valid Upto',
                'Name of Contractor/Purchaser', 'CNIC',
                'Species', 'Quantity', 'Rate per Unit',
                'Total Amount', 'Mark of Timber',
                'From (Forest Division)', 'To (Destination)',
                'Vehicle No', 'Driver Name', 'License No'
            ],
            'structure': 'form_with_table',
            'kpk_specific': True,
            'category': 'administrative',
        },
        
        # Auction Bid Sheet
        'auction_sheet': {
            'indicators': ['AUCTION SHEET', 'BID SHEET', 'SALE NOTICE', 'LOT NO'],
            'fields': [
                'Lot No', 'Species', 'Quantity', 'Unit',
                'Reserve Price', 'Bid Amount', 'Bidder Name',
                'Bidder CNIC', 'Bid Security', 'Remarks'
            ],
            'structure': 'table',
            'kpk_specific': True,
            'category': 'financial',
        },
        
        # Tree Marking Register
        'marking_register': {
            'indicators': ['TREE MARKING REGISTER', 'MARKING SHEET', 'COMPARTMENT'],
            'fields': [
                'Compartment No', 'Tree No', 'Species',
                'DBH (cm)', 'Height (m)', 'Volume',
                'Mark', 'Date Marked', 'Marked By',
                'Remarks'
            ],
            'structure': 'table',
            'kpk_specific': True,
            'category': 'operational',
        },
        
        # Forest Produce Stock Register
        'stock_register': {
            'indicators': ['STOCK REGISTER', 'INVENTORY', 'STOCK POSITION'],
            'fields': [
                'S No', 'Date', 'Species', 'Quantity',
                'Unit', 'Rate', 'Amount', 'Receipt No',
                'Issued To', 'Balance'
            ],
            'structure': 'table',
            'kpk_specific': True,
            'category': 'inventory',
        },
        
        # Working Plan Prescription Table
        'working_plan_table': {
            'indicators': ['WORKING PLAN', 'PRESCRIPTION', 'COMPARTMENT', 'TREATMENT'],
            'fields': [
                'Compartment', 'Area (ha)', 'Species Composition',
                'Age Class', 'Treatment', 'Rotation Period',
                'Annual Allowable Cut', 'Remarks'
            ],
            'structure': 'table',
            'kpk_specific': True,
            'category': 'planning',
        },
        
        # Fee/Penalty Schedule
        'fee_schedule': {
            'indicators': ['FEE SCHEDULE', 'RATE SCHEDULE', 'PENALTY', 'FINE'],
            'fields': [
                'S No', 'Description', 'Unit', 'Rate (Rs)',
                'Remarks'
            ],
            'structure': 'table',
            'kpk_specific': True,
            'category': 'financial',
        },
        
        # Daily Progress Report
        'progress_report': {
            'indicators': ['DAILY PROGRESS REPORT', 'WORK PROGRESS', 'LABOUR'],
            'fields': [
                'Date', 'Work Description', 'Quantity',
                'Unit', 'Labour Employed', 'Supervisor',
                'Remarks'
            ],
            'structure': 'table',
            'kpk_specific': True,
            'category': 'operational',
        },
    }
    
    # KPK forestry-specific patterns
    FORESTRY_PATTERNS = {
        'species': re.compile(r'(?i)\b(deodar|chir\s+pine|blue\s+pine|kail|fir|spruce|poplar|willow|sheesham|mango|neem|oak|walnut)\b'),
        'quantity_units': re.compile(r'(?i)\b(cubic\s+foot|cf|cubic\s+meter|m³|ton|kg|piece|number|dozen)\b'),
        'money': re.compile(r'Rs\.?\s*(\d+(?:,\d+)*(?:\.\d+)?)'),
        'dates': re.compile(r'\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2})\b'),
        'cnic': re.compile(r'\b\d{5}-\d{7}-\d{1}\b'),
        'vehicle': re.compile(r'\b([A-Z]{2,3}-\d{1,4}|[A-Z]{3}\s*\d{4})\b'),
        'compartment': re.compile(r'(?i)comp(?:artment)?\.?\s*([A-Z]?\d+(?:-[A-Z\d]+)?)\b'),
        'beat_range': re.compile(r'(?i)(?:beat|range)\s*([A-Za-z\s]+)\b'),
        'designation': re.compile(r'(?i)\b(DFO|SDFO|Range\s+Officer|Beat\s+Guard|Forest\s+Guard|Forester|Conservator)\b'),
        'timber_mark': re.compile(r'(?i)\b(mark\s*[A-Z0-9]+|hammer\s*mark)\b'),
        'legal_section': re.compile(r'(?i)\b(section|sec\.?)\s*(\d+[A-Z]?)\b'),
    }
    
    @classmethod
    def detect_form_type(cls, text: str) -> Tuple[Optional[str], float]:
        """Detect form type based on text content"""
        text_upper = text.upper()
        matches = []
        
        for form_type, template in cls.FORM_TEMPLATES.items():
            score = 0.0
            indicators = template['indicators']
            
            # Check for indicator keywords
            for indicator in indicators:
                if indicator.upper() in text_upper:
                    score += 0.3
            
            # Check for field keywords
            fields_found = 0
            for field in template['fields']:
                field_upper = field.upper()
                if field_upper in text_upper:
                    fields_found += 1
            
            if fields_found > 0:
                score += min(0.5, fields_found * 0.1)
            
            if score > 0:
                matches.append((form_type, score))
        
        if not matches:
            return None, 0.0
        
        # Return best match
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[0]
    
    @classmethod
    def extract_kpk_entities(cls, text: str) -> Dict[str, List[str]]:
        """Extract KPK-specific entities from text"""
        entities = {}
        
        for entity_type, pattern in cls.FORESTRY_PATTERNS.items():
            matches = pattern.findall(text)
            if matches:
                if entity_type == 'legal_section':
                    # Format section matches nicely
                    formatted = [f"Section {match[1]}" if isinstance(match, tuple) else match for match in matches]
                    entities[entity_type] = list(set(formatted))
                else:
                    entities[entity_type] = list(set(matches))
        
        return entities

# ============================================================================
# TABLE EXTRACTOR
# ============================================================================

class TableExtractor:
    """
    Phase 1.3: KPK Forestry Document Table & Form Extraction
    Extracts tables and forms from KPK forestry documents.
    """
    
    def __init__(self, 
                 config: Optional[Union[TableExtractionConfig, Dict]] = None,
                 enable_abstention_logging: bool = True,
                 logger: Optional[logging.Logger] = None):
        """
        Initialize table extractor.
        
        Args:
            config: Configuration object or dictionary
            enable_abstention_logging: Whether to log abstentions
            logger: Optional logger instance
        """
        
        # Configuration
        if isinstance(config, dict):
            self.config = TableExtractionConfig()
            # Update config from dict
            for key, value in config.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
        else:
            self.config = config or TableExtractionConfig()
        
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
        
        # Form templates
        self.form_templates = KPKFormTemplates()
        
        # Statistics
        self.stats = self._init_statistics()
        
        # Cache
        self._extraction_cache = {}
        
        self.logger.info("TableExtractor initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging"""
        logger = logging.getLogger('TableExtractor')
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
            'extraction_time_total': 0.0,
            'avg_extraction_time': 0.0,
            
            'tables_extracted': {
                'total': 0,
                'kpk_tables': 0,
                'regular_tables': 0,
                'forms': 0,
            },
            
            'extraction_methods': {
                'pdfplumber': 0,
                'manual': 0,
                'ocr': 0,
                'layout_based': 0,
            },
            
            'quality_metrics': {
                'high_confidence': 0,
                'medium_confidence': 0,
                'low_confidence': 0,
            },
            
            'kpk_entities_found': defaultdict(int),
            
            'performance': {
                'fastest_extraction': float('inf'),
                'slowest_extraction': 0.0,
                'extraction_times': [],
            },
            
            'issues': {
                'extraction_errors': 0,
                'low_confidence_tables': 0,
                'failed_extractions': 0,
            },
        }
    
    def extract_tables(self, 
                      input_data: Union[PDFParseResult, DocumentLayout, Dict, Path],
                      document_path: Optional[Union[str, Path]] = None) -> TableExtractionResult:
        """
        Extract tables and forms from input data.
        
        Args:
            input_data: PDFParseResult, DocumentLayout, dictionary, or PDF path
            document_path: Optional document path for identification
            
        Returns:
            TableExtractionResult with extracted content
        """
        import time
        start_time = time.time()
        
        try:
            # Generate cache key
            cache_key = self._generate_cache_key(input_data, document_path)
            
            # Check cache
            if self.config.CACHE_RESULTS and cache_key in self._extraction_cache:
                self.logger.info(f"Returning cached extraction for {document_path or 'document'}")
                return self._extraction_cache[cache_key]
            
            self.logger.info(f"Extracting tables from {document_path or 'document'}")
            
            # Process based on input type
            if isinstance(input_data, PDFParseResult):
                result = self._extract_from_pdf_parse(input_data, document_path)
            elif isinstance(input_data, DocumentLayout):
                result = self._extract_from_document_layout(input_data, document_path)
            elif isinstance(input_data, dict):
                result = self._extract_from_dict(input_data, document_path)
            elif isinstance(input_data, Path) or isinstance(input_data, str):
                result = self._extract_from_pdf_file(Path(input_data))
            else:
                raise ValueError(f"Unsupported input type: {type(input_data)}")
            
            # Cache result
            if self.config.CACHE_RESULTS:
                self._extraction_cache[cache_key] = result
            
            # Update statistics
            extraction_time = time.time() - start_time
            self._update_statistics(result, extraction_time)
            
            # Log abstention if extraction quality is poor
            if (self.enable_abstention_logging and self.abstention_logger and 
                result.confidence_score < 0.5):
                
                self._log_extraction_abstention(result, document_path)
            
            self.logger.info(
                f"Table extraction complete: {document_path or 'document'} - "
                f"Tables: {len(result.tables)}, "
                f"Forms: {len(result.forms)}, "
                f"Confidence: {result.confidence_score:.2%}, "
                f"Time: {extraction_time:.2f}s"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Table extraction failed: {e}")
            
            # Create minimal result with error
            return self._create_error_result(document_path, str(e))
    
    def _generate_cache_key(self, input_data: Any, document_path: Optional[Union[str, Path]]) -> str:
        """Generate cache key for extraction"""
        try:
            if isinstance(input_data, PDFParseResult):
                doc_hash = input_data.document_hash
            elif isinstance(input_data, DocumentLayout):
                doc_hash = input_data.document_hash
            elif document_path:
                doc_hash = hashlib.md5(str(document_path).encode()).hexdigest()[:16]
            else:
                doc_hash = hashlib.md5(str(input_data).encode()).hexdigest()[:16]
            
            return f"tables_{doc_hash}"
        except:
            return "tables_unknown"
    
    def _extract_from_pdf_parse(self, pdf_result: PDFParseResult, 
                               document_path: Optional[Union[str, Path]]) -> TableExtractionResult:
        """Extract tables from PDFParseResult"""
        tables = []
        forms = []
        extraction_methods = set()
        
        for page in pdf_result.pages:
            try:
                page_tables, page_forms, methods = self._extract_from_page(
                    page, pdf_result, page.page_number
                )
                tables.extend(page_tables)
                forms.extend(page_forms)
                extraction_methods.update(methods)
                
            except Exception as e:
                self.logger.warning(f"Failed to extract from page {page.page_number}: {e}")
                if not self.config.CONTINUE_ON_ERROR:
                    raise
        
        # Create result
        result = TableExtractionResult(
            document_path=pdf_result.document_path,
            document_hash=pdf_result.document_hash,
            extraction_timestamp=datetime.now(),
            tables=tables,
            forms=forms,
            extraction_methods=list(extraction_methods),
        )
        
        return result
    
    def _extract_from_document_layout(self, layout: DocumentLayout,
                                     document_path: Optional[Union[str, Path]]) -> TableExtractionResult:
        """Extract tables from DocumentLayout"""
        tables = []
        forms = []
        extraction_methods = set()
        
        for page_layout in layout.pages:
            try:
                page_tables, page_forms, methods = self._extract_from_page_layout(
                    page_layout, document_path
                )
                tables.extend(page_tables)
                forms.extend(page_forms)
                extraction_methods.update(methods)
                
            except Exception as e:
                self.logger.warning(f"Failed to extract from page {page_layout.page_num}: {e}")
                if not self.config.CONTINUE_ON_ERROR:
                    raise
        
        # Create result
        result = TableExtractionResult(
            document_path=layout.document_path,
            document_hash=layout.document_hash,
            extraction_timestamp=datetime.now(),
            tables=tables,
            forms=forms,
            extraction_methods=list(extraction_methods),
        )
        
        return result
    
    def _extract_from_dict(self, data_dict: Dict, 
                          document_path: Optional[Union[str, Path]]) -> TableExtractionResult:
        """Extract tables from dictionary"""
        # This is a simplified implementation
        # In production, you'd properly parse the dictionary
        
        tables = []
        forms = []
        
        # Try to extract from text content
        if 'text' in data_dict or 'content' in data_dict:
            text = data_dict.get('text', data_dict.get('content', ''))
            
            # Extract tables from text
            text_tables = self._extract_tables_from_text(text)
            for table_data in text_tables:
                table = self._create_table_from_data(table_data, 0)
                if table:
                    tables.append(table)
            
            # Detect forms
            if self.config.EXTRACT_FORMS:
                form_type, confidence = self.form_templates.detect_form_type(text)
                if form_type and confidence >= self.config.FORM_CONFIDENCE_THRESHOLD:
                    form = self._extract_form_from_text(text, form_type, 0)
                    if form:
                        forms.append(form)
        
        # Create result
        result = TableExtractionResult(
            document_path=str(document_path) if document_path else 'unknown',
            document_hash=hashlib.md5(str(data_dict).encode()).hexdigest()[:16],
            extraction_timestamp=datetime.now(),
            tables=tables,
            forms=forms,
            extraction_methods=['text_analysis'],
        )
        
        return result
    
    def _extract_from_pdf_file(self, pdf_path: Path) -> TableExtractionResult:
        """Extract tables directly from PDF file"""
        tables = []
        forms = []
        extraction_methods = set()
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    try:
                        page_tables, page_forms, methods = self._extract_from_pdfplumber_page(
                            page, page_num, pdf_path
                        )
                        tables.extend(page_tables)
                        forms.extend(page_forms)
                        extraction_methods.update(methods)
                        
                    except Exception as e:
                        self.logger.warning(f"Failed to extract from page {page_num}: {e}")
                        if not self.config.CONTINUE_ON_ERROR:
                            raise
        
        except Exception as e:
            self.logger.error(f"Failed to open PDF {pdf_path}: {e}")
            return self._create_error_result(pdf_path, str(e))
        
        # Create result
        result = TableExtractionResult(
            document_path=str(pdf_path),
            document_hash=hashlib.md5(str(pdf_path).encode()).hexdigest()[:16],
            extraction_timestamp=datetime.now(),
            tables=tables,
            forms=forms,
            extraction_methods=list(extraction_methods),
        )
        
        return result
    
    def _extract_from_page(self, page: PDFPage, pdf_result: PDFParseResult,
                          page_num: int) -> Tuple[List[ExtractedTable], List[ExtractedForm], Set[str]]:
        """Extract tables and forms from PDFPage"""
        tables = []
        forms = []
        methods = set()
        
        # Extract text for form detection
        page_text = page.cleaned_text if hasattr(page, 'cleaned_text') else ''
        
        # Method 1: Use pdfplumber if available
        if self.config.USE_PDFPLUMBER_TABLES:
            try:
                pg_tables, pg_forms, pg_methods = self._extract_from_pdfplumber_page(page, page_num)
                tables.extend(pg_tables)
                forms.extend(pg_forms)
                methods.update(pg_methods)
            except Exception as e:
                self.logger.debug(f"pdfplumber extraction failed for page {page_num}: {e}")
        
        # Method 2: Manual extraction
        if self.config.USE_MANUAL_EXTRACTION and (not tables or len(tables) == 0):
            try:
                manual_tables = self._extract_manually(page, page_num)
                tables.extend(manual_tables)
                methods.add('manual')
            except Exception as e:
                self.logger.debug(f"Manual extraction failed for page {page_num}: {e}")
        
        # Method 3: OCR fallback
        if self.config.USE_OCR_FALLBACK and self._is_scanned_page(page_text):
            try:
                ocr_tables = self._extract_with_ocr(page, page_num)
                tables.extend(ocr_tables)
                methods.add('ocr')
            except Exception as e:
                self.logger.debug(f"OCR extraction failed for page {page_num}: {e}")
        
        # Detect forms
        if self.config.EXTRACT_FORMS and page_text:
            form_type, confidence = self.form_templates.detect_form_type(page_text)
            if form_type and confidence >= self.config.FORM_CONFIDENCE_THRESHOLD:
                form = self._extract_form_from_text(page_text, form_type, page_num)
                if form:
                    forms.append(form)
                    methods.add('form_detection')
        
        # Enhance tables with KPK context
        enhanced_tables = []
        for table in tables:
            enhanced = self._enhance_table_with_kpk_context(table, page_text)
            enhanced_tables.append(enhanced)
        
        return enhanced_tables, forms, methods

    def _extract_from_page_layout(self, page_layout: PageLayout,
                                 document_path: Optional[Union[str, Path]]) -> Tuple[List[ExtractedTable], List[ExtractedForm], Set[str]]:
        """Extract tables from PageLayout"""
        tables = []
        forms = []
        methods = set()
        
        # Extract text from layout elements
        page_text = ' '.join([elem.text for elem in page_layout.elements if elem.text])
        
        # Look for table elements in layout
        table_elements = [elem for elem in page_layout.elements 
                         if elem.element_type == LayoutElementType.TABLE]
        
        for table_elem in table_elements:
            try:
                table = self._extract_table_from_layout_element(table_elem, page_layout.page_num)
                if table:
                    tables.append(table)
                    methods.add('layout_based')
            except Exception as e:
                self.logger.debug(f"Failed to extract table from layout element: {e}")
        
        # Detect forms from text
        if self.config.EXTRACT_FORMS and page_text:
            form_type, confidence = self.form_templates.detect_form_type(page_text)
            if form_type and confidence >= self.config.FORM_CONFIDENCE_THRESHOLD:
                form = self._extract_form_from_text(page_text, form_type, page_layout.page_num)
                if form:
                    forms.append(form)
                    methods.add('form_detection')
        
        return tables, forms, methods

    def _extract_from_pdfplumber_page(self, page, page_num: int, pdf_path: Optional[Path] = None) -> Tuple[List[ExtractedTable], List[ExtractedForm], Set[str]]:
        """Extract tables using pdfplumber"""
        tables = []
        forms = []
        methods = set(['pdfplumber'])
        
        try:
            # Native pdfplumber table extraction
            if hasattr(page, 'extract_tables'):
                plumber_tables = page.extract_tables()
                for i, table_data in enumerate(plumber_tables):
                    table = self._create_table_from_data(table_data, page_num)
                    if table:
                        tables.append(table)
        except Exception as e:
            self.logger.debug(f"pdfplumber extraction failed: {e}")
            
        return tables, forms, methods

    def _create_table_from_data(self, table_data: List[List[Any]], page_num: int) -> Optional[ExtractedTable]:
        """Create ExtractedTable from raw data grid"""
        if not table_data or len(table_data) < self.config.MIN_TABLE_ROWS:
            return None
            
        rows = []
        for r_idx, row_data in enumerate(table_data):
            row = []
            for c_idx, cell_text in enumerate(row_data):
                cell = TableCell(
                    row_index=r_idx,
                    col_index=c_idx,
                    text=str(cell_text) if cell_text else "",
                    bbox=(0, 0, 0, 0)
                )
                row.append(cell)
            rows.append(row)
            
        return ExtractedTable(
            table_id=f"table_{page_num}_{hashlib.md5(str(table_data).encode()).hexdigest()[:8]}",
            table_type=TableType.REGULAR_TABLE,
            page_num=page_num,
            bbox=(0, 0, 0, 0),
            rows=rows
        )
        """Manual table extraction using text positions"""
        tables = []
        
        # Get text blocks with positions
        text_blocks = page.text_blocks if hasattr(page, 'text_blocks') else []
        
        if not text_blocks:
            return tables
        
        # Group text blocks into potential table rows
        rows = self._group_into_rows(text_blocks)
        
        # Detect columns in rows
        if len(rows) >= self.config.MIN_TABLE_ROWS:
            column_boundaries = self._detect_column_boundaries(rows)
            
            if len(column_boundaries) >= self.config.MIN_TABLE_COLUMNS:
                # Create table from rows and columns
                table = self._create_table_from_rows(rows, column_boundaries, page_num)
                if table:
                    tables.append(table)
        
        return tables
    
    def _group_into_rows(self, text_blocks: List[Any]) -> List[List[Dict[str, Any]]]:
        """Group text blocks into rows based on y-position"""
        if not text_blocks:
            return []
        
        # Sort blocks by y-position
        sorted_blocks = sorted(
            [(self._get_block_bbox(block), self._get_block_text(block)) 
             for block in text_blocks],
            key=lambda x: x[0][1]  # Sort by y0
        )
        
        # Group into rows with tolerance
        rows = []
        current_row = []
        current_y = None
        y_tolerance = 5
        
        for bbox, text in sorted_blocks:
            y0 = bbox[1]
            
            if current_y is None:
                current_y = y0
                current_row.append({'bbox': bbox, 'text': text})
            elif abs(y0 - current_y) <= y_tolerance:
                current_row.append({'bbox': bbox, 'text': text})
            else:
                if current_row:
                    rows.append(current_row)
                current_row = [{'bbox': bbox, 'text': text}]
                current_y = y0
        
        # Add last row
        if current_row:
            rows.append(current_row)
        
        return rows
    
    def _get_block_bbox(self, block: Any) -> Tuple[float, float, float, float]:
        """Get bounding box from text block"""
        if hasattr(block, 'bbox'):
            return block.bbox
        elif isinstance(block, dict) and 'bbox' in block:
            return block['bbox']
        else:
            return (0, 0, 100, 100)  # Default
    
    def _get_block_text(self, block: Any) -> str:
        """Get text from text block"""
        if hasattr(block, 'text'):
            return block.text
        elif isinstance(block, dict) and 'text' in block:
            return block['text']
        else:
            return ''
    
    def _detect_column_boundaries(self, rows: List[List[Dict[str, Any]]]) -> List[float]:
        """Detect column boundaries from rows"""
        # Collect all x-positions
        x_positions = []
        for row in rows:
            for item in row:
                bbox = item['bbox']
                x_positions.append(bbox[0])  # x0
                x_positions.append(bbox[2])  # x1
        
        if not x_positions:
            return []
        
        # Use K-means clustering to find column centers
        try:
            x_array = np.array(x_positions).reshape(-1, 1)
            n_samples = len(x_array)
            n_clusters = min(self.config.MAX_TABLE_COLUMNS, max(2, n_samples // 20))
            
            kmeans = KMeans(n_clusters=n_clusters, random_state=42)
            kmeans.fit(x_array)
            
            # Get cluster centers and sort them
            centers = sorted(kmeans.cluster_centers_.flatten())
            
            # Create boundaries between centers
            boundaries = []
            for i in range(len(centers) - 1):
                boundary = (centers[i] + centers[i + 1]) / 2
                boundaries.append(boundary)
            
            return boundaries
            
        except Exception:
            # Fallback to simple gap detection
            return self._simple_column_detection(x_positions)
    
    def _simple_column_detection(self, x_positions: List[float]) -> List[float]:
        """Simple column detection using gap analysis"""
        if len(x_positions) < 10:
            return []
        
        # Sort and find significant gaps
        x_positions.sort()
        gaps = []
        
        for i in range(1, len(x_positions)):
            gap = x_positions[i] - x_positions[i-1]
            if gap > 20:  # Significant gap threshold
                gaps.append((i, gap, x_positions[i-1], x_positions[i]))
        
        # Sort gaps by size
        gaps.sort(key=lambda x: x[1], reverse=True)
        
        # Take top gaps as column separators
        separators = []
        for gap in gaps[:self.config.MAX_TABLE_COLUMNS - 1]:
            separator = (gap[2] + gap[3]) / 2
            separators.append(separator)
        
        return sorted(separators)
    
    def _create_table_from_rows(self, rows: List[List[Dict[str, Any]]], 
                               column_boundaries: List[float], 
                               page_num: int) -> Optional[ExtractedTable]:
        """Create table from rows and column boundaries"""
        if not rows or not column_boundaries:
            return None
        
        # Create cells
        table_rows = []
        bbox_list = []
        
        for row_idx, row_items in enumerate(rows):
            row_cells = []
            
            for item in row_items:
                bbox = item['bbox']
                text = item['text']
                bbox_list.append(bbox)
                
                # Find which column this item belongs to
                x_center = (bbox[0] + bbox[2]) / 2
                col_idx = 0
                
                for boundary in column_boundaries:
                    if x_center > boundary:
                        col_idx += 1
                    else:
                        break
                
                # Create cell
                cell = TableCell(
                    row_index=row_idx,
                    col_index=col_idx,
                    text=text,
                    bbox=bbox,
                    confidence=1.0,
                    is_header=(row_idx == 0),  # First row as header
                )
                row_cells.append(cell)
            
            if row_cells:
                table_rows.append(row_cells)
        
        # Calculate overall table bounding box
        if bbox_list:
            x0 = min(b[0] for b in bbox_list)
            y0 = min(b[1] for b in bbox_list)
            x1 = max(b[2] for b in bbox_list)
            y1 = max(b[3] for b in bbox_list)
            table_bbox = (x0, y0, x1, y1)
        else:
            table_bbox = (0, 0, 0, 0)
        
        # Create table
        table = ExtractedTable(
            table_id=f"table_page_{page_num}_{hashlib.md5(str(table_rows).encode()).hexdigest()[:8]}",
            table_type=TableType.REGULAR_TABLE,
            page_num=page_num,
            bbox=table_bbox,
            rows=table_rows,
            header_rows=[0] if table_rows else [],
            extraction_method="manual",
            confidence=0.8,
        )
        
        return table
    
    def _is_scanned_page(self, text: str) -> bool:
        """Check if page is scanned (needs OCR)"""
        return len(text.strip()) < 100  # Very little text = likely scanned
    
    def _extract_with_ocr(self, page: PDFPage, page_num: int) -> List[ExtractedTable]:
        """Extract tables using OCR"""
        # This is a simplified implementation
        # In production, you'd implement proper OCR-based table extraction
        
        return []
    
    def _extract_table_from_layout_element(self, table_elem: LayoutElement,
                                          page_num: int) -> Optional[ExtractedTable]:
        """Extract table from layout element"""
        # This is a simplified implementation
        # In production, you'd parse the layout element structure
        
        return None
    
    def _extract_form_from_text(self, text: str, form_type: str, 
                               page_num: int) -> Optional[ExtractedForm]:
        """Extract form from text"""
        template = self.form_templates.FORM_TEMPLATES.get(form_type)
        if not template:
            return None
        
        # Extract fields
        fields = []
        for field_name in template['fields']:
            # Simple pattern matching for field extraction
            pattern = rf'{field_name}\s*[:.]?\s*(.+)'
            match = re.search(pattern, text, re.IGNORECASE)
            
            if match:
                value = match.group(1).strip()
                # Clean up
                value = re.sub(r'^[:.]\s*', '', value)
                
                # Determine field type
                field_type = self._determine_field_type(field_name, value)
                
                field_obj = FormField(
                    field_name=field_name,
                    field_value=value,
                    field_type=field_type,
                    confidence=0.9,
                )
                fields.append(field_obj)
        
        if not fields:
            return None
        
        # Create form
        form = ExtractedForm(
            form_id=f"form_{form_type}_{page_num}_{hashlib.md5(text.encode()).hexdigest()[:8]}",
            form_type=form_type,
            page_num=page_num,
            bbox=(0, 0, 0, 0),  # Unknown bbox
            fields=fields,
            extraction_method="text_analysis",
            confidence=0.7,
            is_kpk_form=True,
            kpk_form_subtype=form_type,
        )
        
        return form
    
    def _determine_field_type(self, field_name: str, value: str) -> str:
        """Determine field type based on name and value"""
        field_lower = field_name.lower()
        value_lower = value.lower()
        
        if any(keyword in field_lower for keyword in ['date', 'issued', 'valid']):
            return 'date'
        elif any(keyword in field_lower for keyword in ['amount', 'price', 'rate', 'fee']):
            return 'number'
        elif any(keyword in field_lower for keyword in ['quantity', 'number', 'no', '#']):
            return 'number'
        elif any(keyword in value_lower for keyword in ['yes', 'no', 'true', 'false']):
            return 'checkbox'
        elif re.search(r'\d{5}-\d{7}-\d{1}', value):  # CNIC pattern
            return 'cnic'
        elif re.search(r'[A-Z]{2,3}-\d{1,4}', value):  # Vehicle pattern
            return 'vehicle'
        else:
            return 'text'
    
    def _extract_tables_from_text(self, text: str) -> List[Dict[str, Any]]:
        """Extract table-like structures from plain text"""
        tables = []
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        # Find table regions
        table_regions = []
        current_region = []
        
        for line in lines:
            if self._looks_like_table_row(line):
                current_region.append(line)
            elif current_region:
                if len(current_region) >= 2:
                    table_regions.append(current_region)
                current_region = []
        
        # Process last region
        if current_region and len(current_region) >= 2:
            table_regions.append(current_region)
        
        # Parse regions
        for region in table_regions:
            table_data = self._parse_text_table_region(region)
            if table_data:
                tables.append(table_data)
        
        return tables
    
    def _looks_like_table_row(self, line: str) -> bool:
        """Check if line looks like a table row"""
        # Check for separator patterns
        if '|' in line and line.count('|') >= 2:
            return True
        
        # Check for aligned columns (multiple spaces)
        if '  ' in line and line.count('  ') >= 2:
            return True
        
        # Check for tab-separated
        if '\t' in line and line.count('\t') >= 2:
            return True
        
        return False
    
    def _parse_text_table_region(self, region: List[str]) -> Optional[Dict[str, Any]]:
        """Parse text region into table data"""
        if not region:
            return None
        
        # Try different parsing strategies
        table_data = None
        
        # Strategy 1: Pipe-separated
        if '|' in region[0]:
            rows = []
            for line in region:
                cells = [cell.strip() for cell in line.split('|')]
                # Remove empty first/last cells
                if cells and not cells[0]:
                    cells = cells[1:]
                if cells and not cells[-1]:
                    cells = cells[:-1]
                if cells:
                    rows.append(cells)
            
            if rows and len(rows) >= 2:
                table_data = {
                    'rows': rows,
                    'separator': 'pipe',
                }
        
        # Strategy 2: Tab-separated
        elif '\t' in region[0] and not table_data:
            rows = []
            for line in region:
                cells = [cell.strip() for cell in line.split('\t')]
                if cells:
                    rows.append(cells)
            
            if rows and len(rows) >= 2:
                table_data = {
                    'rows': rows,
                    'separator': 'tab',
                }
        
        # Strategy 3: Space-aligned
        elif not table_data:
            # Find column boundaries
            boundaries = self._find_text_column_boundaries(region[:min(5, len(region))])
            
            if boundaries:
                rows = []
                for line in region:
                    row = []
                    for start, end in boundaries:
                        if start < len(line):
                            cell = line[start:end].strip()
                        else:
                            cell = ""
                        row.append(cell)
                    rows.append(row)
                
                if rows and len(rows) >= 2:
                    table_data = {
                        'rows': rows,
                        'separator': 'fixed_width',
                    }
        
        return table_data
    
    def _find_text_column_boundaries(self, sample_rows: List[str]) -> List[Tuple[int, int]]:
        """Find column boundaries in text rows"""
        if not sample_rows:
            return []
        
        # Find positions where spaces align
        space_positions = []
        for line in sample_rows:
            for i, char in enumerate(line):
                if char == ' ':
                    if i > 0 and line[i-1] != ' ':
                        space_positions.append(i)
        
        if not space_positions:
            return []
        
        space_positions.sort()
        
        # Find clusters (column boundaries)
        boundaries = []
        current_cluster = [space_positions[0]]
        
        for pos in space_positions[1:]:
            if pos - current_cluster[-1] <= 2:
                current_cluster.append(pos)
            else:
                if len(current_cluster) >= 2:
                    avg_pos = sum(current_cluster) // len(current_cluster)
                    boundaries.append(avg_pos)
                current_cluster = [pos]
        
        # Last cluster
        if len(current_cluster) >= 2:
            avg_pos = sum(current_cluster) // len(current_cluster)
            boundaries.append(avg_pos)
        
        # Create column ranges
        column_ranges = []
        if boundaries:
            column_ranges.append((0, boundaries[0]))
            for i in range(len(boundaries) - 1):
                column_ranges.append((boundaries[i], boundaries[i + 1]))
            column_ranges.append((boundaries[-1], 1000))
        
        return column_ranges
    
    def _create_table_from_data(self, table_data: Dict[str, Any], 
                               page_num: int) -> Optional[ExtractedTable]:
        """Create ExtractedTable from parsed data"""
        if 'rows' not in table_data or not table_data['rows']:
            return None
        
        rows = table_data['rows']
        
        # Create cells
        table_rows = []
        for row_idx, row_data in enumerate(rows):
            row_cells = []
            for col_idx, cell_text in enumerate(row_data):
                cell = TableCell(
                    row_index=row_idx,
                    col_index=col_idx,
                    text=cell_text,
                    bbox=(0, 0, 0, 0),  # Unknown bbox
                    confidence=1.0,
                    is_header=(row_idx == 0),
                )
                row_cells.append(cell)
            table_rows.append(row_cells)
        
        # Create table
        table = ExtractedTable(
            table_id=f"text_table_{page_num}_{hashlib.md5(str(rows).encode()).hexdigest()[:8]}",
            table_type=TableType.REGULAR_TABLE,
            page_num=page_num,
            bbox=(0, 0, 0, 0),
            rows=table_rows,
            header_rows=[0] if table_rows else [],
            extraction_method="text_analysis",
            confidence=0.7,
        )
        
        return table
    
    def _enhance_table_with_kpk_context(self, table: ExtractedTable, 
                                       page_text: str) -> ExtractedTable:
        """Enhance table with KPK-specific context"""
        if not self.config.KPK_PATTERN_DETECTION:
            return table
        
        # Extract entities from table text
        all_text = ''
        for row in table.rows:
            for cell in row:
                all_text += cell.text + ' '
        
        entities = self.form_templates.extract_kpk_entities(all_text + ' ' + page_text)
        
        # Check if this is a KPK form
        is_kpk_form = False
        kpk_form_type = None
        
        if entities:
            form_type, confidence = self.form_templates.detect_form_type(all_text)
            if form_type and confidence >= self.config.FORM_CONFIDENCE_THRESHOLD:
                is_kpk_form = True
                kpk_form_type = form_type
                table.table_type = TableType.FORM
        
        # Update table
        table.is_kpk_form = is_kpk_form
        table.kpk_form_type = kpk_form_type
        table.detected_entities = entities
        
        return table
    
    def _update_statistics(self, result: TableExtractionResult, extraction_time: float):
        """Update extractor statistics"""
        self.stats['documents_processed'] += 1
        self.stats['extraction_time_total'] += extraction_time
        
        # Update table counts
        self.stats['tables_extracted']['total'] += result.total_tables
        self.stats['tables_extracted']['kpk_tables'] += result.kpk_tables
        self.stats['tables_extracted']['forms'] += result.total_forms
        
        # Update extraction methods
        for method in result.extraction_methods:
            if method in self.stats['extraction_methods']:
                self.stats['extraction_methods'][method] += 1
        
        # Update quality metrics
        confidence = result.confidence_score
        if confidence >= 0.8:
            self.stats['quality_metrics']['high_confidence'] += 1
        elif confidence >= 0.5:
            self.stats['quality_metrics']['medium_confidence'] += 1
        else:
            self.stats['quality_metrics']['low_confidence'] += 1
        
        # Count KPK entities
        for table in result.tables:
            for entity_type, entities in table.detected_entities.items():
                self.stats['kpk_entities_found'][entity_type] += len(entities)
        
        # Update performance metrics
        perf = self.stats['performance']
        perf['extraction_times'].append(extraction_time)
        perf['fastest_extraction'] = min(perf['fastest_extraction'], extraction_time)
        perf['slowest_extraction'] = max(perf['slowest_extraction'], extraction_time)
        
        # Calculate averages
        total_docs = self.stats['documents_processed']
        if total_docs > 0:
            self.stats['avg_extraction_time'] = self.stats['extraction_time_total'] / total_docs
    
    def _log_extraction_abstention(self, result: TableExtractionResult, 
                                 document_path: Optional[Union[str, Path]]):
        """Log abstention for poor extraction quality"""
        if self.enable_abstention_logging and self.abstention_logger:
            try:
                context = create_abstention_context(
                    pipeline_state=PipelineStage.TABLE_EXTRACTION.value,
                    processing_step="table_extraction",
                    module_state={},
                    stage=PipelineStage.TABLE_EXTRACTION,
                    component="TableExtractor",
                    document_path=str(document_path) if document_path else 'unknown',
                    reason="poor_extraction_quality",
                    details={
                        'confidence_score': result.confidence_score,
                        'tables_found': result.total_tables,
                        'forms_found': result.total_forms,
                        'kpk_tables': result.kpk_tables,
                        'extraction_methods': result.extraction_methods,
                    }
                )
                
                self.abstention_logger.log_abstention(
                    abstention_type=AbstentionType.EXTRACTION_ISSUE,
                    severity=AbstentionSeverity.MEDIUM,
                    context=context,
                    suggested_action="Manual review of extracted tables or improve source quality",
                    confidence=1.0 - result.confidence_score,
                    component_state=result.to_dict(),
                )
                
                self.logger.info(f"Logged extraction abstention for {document_path or 'document'}")
                
            except Exception as e:
                self.logger.warning(f"Failed to log extraction abstention: {e}")
    
    def _create_error_result(self, document_path: Optional[Union[str, Path]], 
                           error_message: str) -> TableExtractionResult:
        """Create error result when extraction fails"""
        return TableExtractionResult(
            document_path=str(document_path) if document_path else 'unknown',
            document_hash=hashlib.md5(str(document_path or '').encode()).hexdigest()[:16],
            extraction_timestamp=datetime.now(),
            tables=[],
            forms=[],
            extraction_errors=[error_message],
            confidence_score=0.0,
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get current extractor statistics"""
        stats = self.stats.copy()
        
        # Calculate derived statistics
        total_processed = stats['documents_processed']
        if total_processed > 0:
            stats['avg_extraction_time'] = stats['extraction_time_total'] / total_processed
            
            # Calculate percentages
            total_tables = stats['tables_extracted']['total']
            if total_tables > 0:
                for key in ['kpk_tables', 'forms']:
                    count = stats['tables_extracted'][key]
                    stats['tables_extracted'][f'{key}_pct'] = count / total_tables * 100
        
        # Add performance summary
        perf = stats['performance']
        if perf['extraction_times']:
            perf['avg_extraction_time'] = sum(perf['extraction_times']) / len(perf['extraction_times'])
        else:
            perf['avg_extraction_time'] = 0.0
            perf['fastest_extraction'] = 0.0
        
        return stats

# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    """Main function for standalone testing"""
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description="KPK Table Extractor")
    parser.add_argument("--input", required=True, help="Input PDF, JSON, or layout file")
    parser.add_argument("--output", help="Output JSON file")
    parser.add_argument("--config", help="Configuration file (JSON)")
    parser.add_argument("--mode", choices=['pdf', 'layout', 'text'], default='pdf',
                       help="Input mode: pdf, layout, or text")
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
    
    # Initialize extractor
    extractor = TableExtractor(config=config)
    
    input_path = Path(args.input)
    
    if args.mode == 'pdf':
        # Process PDF directly
        result = extractor.extract_tables(input_path)
    
    elif args.mode == 'layout':
        # Process layout JSON
        with open(input_path, 'r', encoding='utf-8') as f:
            layout_data = json.load(f)
        result = extractor.extract_tables(layout_data, input_path)
    
    elif args.mode == 'text':
        # Process text file
        with open(input_path, 'r', encoding='utf-8') as f:
            text = f.read()
        result = extractor.extract_tables({'text': text}, input_path)
    
    # Save or display results
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
        print(f"Results saved to {args.output}")
    else:
        print(json.dumps(result.to_dict(), indent=2))
    
    # Print summary
    print(f"\nTable Extraction Summary:")
    print(f"  Tables Found: {result.total_tables}")
    print(f"  Forms Found: {result.total_forms}")
    print(f"  KPK Tables: {result.kpk_tables}")
    print(f"  Confidence Score: {result.confidence_score:.2%}")
    print(f"  Extraction Methods: {', '.join(result.extraction_methods)}")
    
    if result.tables:
        print(f"\nTable Details:")
        for i, table in enumerate(result.tables[:3]):  # Show first 3 tables
            print(f"  Table {i+1}: {table.table_type.value} ({table.row_count}x{table.column_count})")
            if table.is_kpk_form:
                print(f"    KPK Form: {table.kpk_form_type}")
    
    # Print statistics
    stats = extractor.get_statistics()
    print(f"\nExtractor Statistics:")
    print(f"  Documents Processed: {stats['documents_processed']}")
    print(f"  Total Tables Extracted: {stats['tables_extracted']['total']}")
    print(f"  KPK Tables: {stats['tables_extracted']['kpk_tables']}")
    print(f"  Average Extraction Time: {stats['avg_extraction_time']:.2f}s")

if __name__ == "__main__":
    main()
