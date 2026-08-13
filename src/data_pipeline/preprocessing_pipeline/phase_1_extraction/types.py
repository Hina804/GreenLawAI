"""
TYPES.PY - Phase 1: Shared Data Structures for Extraction
Contains shared classes to avoid circular imports.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime
from enum import Enum

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
class OCREngineResult:
    """Result of OCR processing"""
    raw_text: str
    cleaned_text: str
    confidence: float
    page_count: int
    language_stats: Dict[str, float] = field(default_factory=dict)
    blocks: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    ocr_version: str = "2.1"
    processed_at: datetime = field(default_factory=datetime.now)

@dataclass
class PDFPage:
    """Represents a single page in a PDF"""
    page_number: int
    text: str
    width: float
    height: float
    images: List[Dict[str, Any]] = field(default_factory=list)
    tables: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    text_blocks: List[Any] = field(default_factory=list)  # List of TextBlock

@dataclass
class PDFParseResult:
    """Result of PDF parsing"""
    filename: str
    page_count: int
    pages: List[PDFPage]
    full_text: str
    metadata: Dict[str, Any]
    parse_time: float
    document_hash: str = ""
    document_path: str = ""
    is_searchable: bool = True

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
        return {"x0": self.x0, "y0": self.y0, "x1": self.x1, "y1": self.y1, "page_num": self.page_num}

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
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "element_id": self.element_id,
            "element_type": self.element_type.value,
            "bbox": self.bbox.to_dict(),
            "text": self.text,
            "confidence": self.confidence,
            "metadata": self.metadata,
            "children": [child.to_dict() for child in self.children]
        }

@dataclass
class PageLayout:
    """Complete layout for a single page"""
    page_num: int
    width: float
    height: float
    elements: List[LayoutElement]
    metadata: Dict[str, Any] = field(default_factory=dict)
    columns: List[Dict[str, Any]] = field(default_factory=list)
    margins: Dict[str, float] = field(default_factory=dict)
    headers: List[LayoutElement] = field(default_factory=list)
    footers: List[LayoutElement] = field(default_factory=list)
    tables: List[LayoutElement] = field(default_factory=list)
    lists: List[LayoutElement] = field(default_factory=list)
    text_density: float = 0.0
    layout_consistency_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
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

@dataclass
class DocumentLayout:
    """Complete layout for entire document"""
    document_path: str
    document_hash: str
    pages: List[PageLayout]
    metadata: Dict[str, Any] = field(default_factory=dict)
    sections: List[Dict[str, Any]] = field(default_factory=list)
    toc: List[Dict[str, Any]] = field(default_factory=list)
    document_hierarchy: List[LayoutElement] = field(default_factory=list)
    total_pages: int = 0
    avg_text_density: float = 0.0
    layout_consistency: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
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

@dataclass
class TableCell:
    """Represents a single table cell"""
    row_index: int
    col_index: int
    text: str
    bbox: Tuple[float, float, float, float]
    confidence: float = 1.0
    is_header: bool = False
    rowspan: int = 1
    colspan: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'row': self.row_index, 'column': self.col_index, 'text': self.text,
            'bbox': self.bbox, 'is_header': self.is_header, 'rowspan': self.rowspan,
            'colspan': self.colspan, 'confidence': self.confidence
        }

@dataclass
class ExtractedTable:
    """Represents an extracted table"""
    table_id: str
    table_type: TableType
    page_num: int
    bbox: Tuple[float, float, float, float]
    rows: List[List[TableCell]]
    header_rows: List[int] = field(default_factory=list)
    extraction_method: str = "unknown"
    confidence: float = 1.0
    row_count: int = 0
    column_count: int = 0
    is_kpk_form: bool = False
    kpk_form_type: Optional[str] = None
    detected_entities: Dict[str, List[str]] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'table_id': self.table_id, 'table_type': self.table_type.value,
            'page_num': self.page_num, 'bbox': self.bbox,
            'rows': [[c.to_dict() for c in r] for r in self.rows],
            'confidence': self.confidence, 'row_count': self.row_count,
            'column_count': self.column_count, 'is_kpk_form': self.is_kpk_form
        }

@dataclass
class FormField:
    """Represents a form field"""
    field_name: str
    field_value: str
    field_type: str
    bbox: Optional[Tuple[float, float, float, float]] = None
    confidence: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {"field_name": self.field_name, "field_value": self.field_value, "field_type": self.field_type}

@dataclass
class ExtractedForm:
    """Represents an extracted form"""
    form_id: str
    form_type: str
    page_num: int
    bbox: Tuple[float, float, float, float]
    fields: List[FormField]
    tables: List[ExtractedTable] = field(default_factory=list)
    extraction_method: str = "unknown"
    confidence: float = 1.0
    is_kpk_form: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'form_id': self.form_id, 'form_type': self.form_type,
            'fields': [f.to_dict() for f in self.fields],
            'tables': [t.to_dict() for t in self.tables],
            'confidence': self.confidence
        }

@dataclass
class TableExtractionResult:
    """Result of table extraction"""
    document_path: str
    document_hash: str
    extraction_timestamp: datetime
    tables: List[ExtractedTable]
    forms: List[ExtractedForm]
    total_tables: int = 0
    total_forms: int = 0
    confidence_score: float = 0.0
    extraction_errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'document_path': self.document_path,
            'tables': [t.to_dict() for t in self.tables],
            'forms': [f.to_dict() for f in self.forms],
            'confidence_score': self.confidence_score,
            'timestamp': self.extraction_timestamp.isoformat()
        }

@dataclass
class TextBlock:
    """Represents a block of text in a PDF"""
    text: str
    bbox: Tuple[float, float, float, float]
    font_name: str = ""
    font_size: float = 0.0
    page_num: int = 0
