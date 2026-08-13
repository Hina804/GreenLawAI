"""
GreenLawAI-KPK: Document Profiler and Classifier
Version: 2.1 (Enhanced with configuration, better entity extraction, and error handling)
Author: Hina Ali, Eman Irfan
Date: January 29, 2026

This module analyzes and classifies KPK forestry documents to determine their
type, jurisdiction, quality, and processing requirements.

Key Features:
1. KPK-specific document type classification with confidence scoring
2. Document quality assessment with configurable thresholds
3. Jurisdiction detection with KPK-specific hierarchy
4. Amendment chain identification
5. Integration with graph schema and abstention logging
6. Configuration-driven processing parameters
"""

import re
import json
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Set, Union
from pathlib import Path
import hashlib
import logging
from enum import Enum
# import spacy
# from spacy.language import Language
class Language: 
    pass
import tempfile
import sys
import time

print("DEBUG: 0.1 Start...", flush=True)

# Third-party imports
try:
    import pdfplumber
    print("DEBUG: 0.1 Imported pdfplumber", flush=True)
    import pymupdf  # PyMuPDF
    print("DEBUG: 0.1 Imported pymupdf", flush=True)
    import pytesseract
    print("DEBUG: 0.1 Imported pytesseract", flush=True)
    from PIL import Image
    import numpy as np
except ImportError as e:
    print(f"Warning: PDF processing libraries missing: {e}")

print("DEBUG: 0.1 Imports Done...", flush=True)

# Import common modules
try:
    from preprocessing_pipeline.common.config import PipelineConfig, DocumentProcessingConfig
    from preprocessing_pipeline.common.constants import *
    USE_COMMON_CONFIG = True
except ImportError:
    USE_COMMON_CONFIG = False
    print("Warning: common.config not found. Using default configuration.")

# Import schema and abstention modules with graceful fallback
# Avoid circular dependency with phase 6
GRAPH_SCHEMA_AVAILABLE = False
class DocumentType(Enum):
    LAW = "Law"
    ORDINANCE = "Ordinance"
    RULE = "Rule"
    CIRCULAR = "Circular"
    GAZETTE = "Gazette Notification"
    WORKING_PLAN = "Working Plan"
    FIR = "FIR (First Information Report)"
    PERMIT = "Permit"
    LICENSE = "License"
    REPORT = "Report"
    POLICY = "Policy"
    GUIDELINE = "Guideline"
    FORM = "Form"
    REGISTER = "Register"
    MEMORANDUM = "Memorandum"
    ORDER = "Order"
    NOTIFICATION = "Notification"
    AGREEMENT = "Agreement"
    CONTRACT = "Contract"
    OTHER = "Other"

try:
    from ..phase_0_foundation.abstention_log import AbstentionLogger, AbstentionType, PipelineStage, log_quick_abstention
    ABSTENTION_AVAILABLE = True
except ImportError:
    ABSTENTION_AVAILABLE = False
    class AbstentionLogger:
        pass
    class AbstentionType(Enum):
        OTHER = "other"
    class PipelineStage(Enum):
        PROFILING = "profiling"
    def log_quick_abstention(**kwargs):
        return "abstention_fallback_id"

# ============================================================================
# CONFIGURATION
# ============================================================================

class DocProfilerConfig:
    """Configuration for document profiler"""
    
    # Quality thresholds (configurable)
    QUALITY_THRESHOLDS = {
        'excellent': 0.8,
        'good': 0.6,
        'fair': 0.4,
        'poor': 0.2,
    }
    
    # Confidence thresholds
    CONFIDENCE_THRESHOLDS = {
        'high_confidence': 0.7,
        'medium_confidence': 0.5,
        'low_confidence': 0.3,
        'abstention_threshold': 0.4,
    }
    
    # Language detection thresholds
    LANGUAGE_THRESHOLDS = {
        'dominant_language': 0.9,
        'mixed_language': 0.6,
        'bilingual': 0.3,
    }
    
    # Priority calculation weights
    PRIORITY_WEIGHTS = {
        'is_kpk': 2,
        'is_law_type': 2,
        'is_circular': 1,
        'poor_quality': 2,
        'unreadable': 3,
        'has_amendments': 1,
        'needs_ocr': 1,
        'needs_language_sep': 1,
    }
    
    # Entity extraction settings
    ENTITY_EXTRACTION = {
        'use_spacy': True,
        'spacy_model': 'en_core_web_sm',
        'max_entities': 50,
        'min_entity_length': 2,
    }

# ============================================================================
# ENUMERATIONS
# ============================================================================

class DocumentQuality(Enum):
    """Document quality assessment levels"""
    EXCELLENT = "excellent"       # Clean, searchable, well-structured
    GOOD = "good"                 # Minor issues, mostly readable
    FAIR = "fair"                 # Some issues, requires cleaning
    POOR = "poor"                 # Major issues, hard to parse
    UNREADABLE = "unreadable"     # Cannot be processed

class JurisdictionType(Enum):
    """Jurisdiction types in KPK"""
    FEDERAL = "federal"
    PROVINCIAL = "provincial"
    DIVISIONAL = "divisional"
    DISTRICT = "district"
    LOCAL = "local"
    MULTIPLE = "multiple"
    UNKNOWN = "unknown"

class LanguageMix(Enum):
    """Language mixing patterns"""
    ENGLISH_ONLY = "english_only"
    URDU_ONLY = "urdu_only"
    PASHTO_ONLY = "pashto_only"
    ENGLISH_URDU = "english_urdu"
    ENGLISH_PASHTO = "english_pashto"
    URDU_PASHTO = "urdu_pashto"
    TRILINGUAL = "trilingual"
    MIXED = "mixed"
    UNKNOWN = "unknown"

class ProcessingPriority(Enum):
    """Processing priority levels"""
    CRITICAL = 1    # Laws, amendments, poor quality
    HIGH = 2        # Circulars, important documents
    MEDIUM = 3      # Reports, working plans
    LOW = 4         # Forms, registers, other documents

# ============================================================================
# KPK-SPECIFIC PATTERNS (ENHANCED)
# ============================================================================

class KPKDocumentPatterns:
    """KPK-specific patterns for document identification with enhanced patterns"""
    
    # Document type indicators (enhanced with more patterns)
    LAW_PATTERNS = [
        r"(?i)(?:act|ordinance|regulation|rule)\s+(?:no\.?)?\s*\d+",
        r"(?i)the\s+.+?\s+(?:act|ordinance),\s*\d{4}",
        r"(?i)کے\s+.+?\s+(?:ایکٹ|آرڈیننس|قانون),\s*\d{4}",
        r"(?i)آئین\s+\d{4}",  # Constitution year
        r"(?i)قانون\s+شماریاتی\s+\d+",  # Law number
    ]
    
    CIRCULAR_PATTERNS = [
        r"(?i)circular\s+(?:no\.?)?\s*\d+",
        r"(?i)ڈی\s*پارٹمنٹل\s*سرکلر",
        r"(?i)سرکلر\s*نمبر",
        r"(?i)subject:\s*.+",
        r"(?i)distribution:\s*.+",
        r"(?i)مشق\s*برائے\s*اطلاع",  # For information
        r"(?i)حوالہ\s*خط\s*نمبر",  # Reference letter number
    ]
    
    WORKING_PLAN_PATTERNS = [
        r"(?i)working\s+plan",
        r"(?i)forest\s+working\s+plan",
        r"(?i)ورکنگ\s*پلان",
        r"(?i)جنگلات\s*کا\s*ورکنگ\s*پلان",
        r"(?i)compartment\s+no\.?\s*\d+",
        r"(?i)سیلویکلچرل\s*سسٹم",
        r"(?i)منصوبہ\s*بندی",  # Planning
        r"(?i)آپریشنل\s*پلان",  # Operational plan
    ]
    
    FIR_PATTERNS = [
        r"(?i)first\s+information\s+report",
        r"(?i)F\.I\.R",
        r"(?i)ایف\s*آئی\s*آر",
        r"(?i)پہلی\s*اطلاعاتی\s*رپورٹ",
        r"(?i)police\s+station",
        r"(?i)تھانہ",
        r"(?i)مقدمہ\s*نمبر",  # Case number
        r"(?i)شکایت\s*درج",  # Complaint registered
    ]
    
    GAZETTE_PATTERNS = [
        r"(?i)S\.R\.O\.?\s*No\.?\s*\d+",
        r"(?i)Gazette\s+of\s+Pakistan",
        r"(?i)گزیٹ\s*آف\s*پاکستان",
        r"(?i)اضافی\s*سرکاری\s*گزیٹ",
        r"(?i)سرکاری\s*گزیٹ",  # Official gazette
        r"(?i)ایس\s*آر\s*او",  # SRO in Urdu
    ]
    
    PERMIT_PATTERNS = [
        r"(?i)permit\s+no\.?\s*\d+",
        r"(?i)اجازت\s*نامہ",
        r"(?i)ٹرانسپورٹ\s*پرمٹ",  # Transport permit
        r"(?i)ٹمبر\s*ٹرانسٹ\s*پرمٹ",  # Timber transit permit
    ]
    
    REPORT_PATTERNS = [
        r"(?i)report\s+on\s+.+",
        r"(?i)رپورٹ\s*برائے",
        r"(?i)تفصیلی\s*رپورٹ",  # Detailed report
        r"(?i)آڈٹ\s*رپورٹ",  # Audit report
        r"(?i)نگرانی\s*رپورٹ",  # Monitoring report
    ]
    
    # KPK jurisdiction indicators (enhanced)
    KPK_JURISDICTION_PATTERNS = [
        r"(?i)Khyber\s+Pakhtunkhwa",
        r"(?i)KPK",
        r"(?i)خیبر\s*پختونخوا",
        r"(?i)صوبہ\s*خیبر\s*پختونخوا",
        r"(?i)مالاکنڈ|سوات|ہزارہ|پشاور|کوہستان|بنوں|ڈیرہ\s*اسماعیل\s*خان",  # KPK divisions
    ]
    
    HAZARA_SPECIFIC_PATTERNS = [
        r"(?i)Hazara\s+Forest\s+Act",
        r"(?i)ہزارہ\s*جنگلات\s*ایکٹ",
        r"(?i)ایبٹ آباد|مانسہرہ|ہری پور|باتگرام|ٹور غر|کالا ڈھاکا",  # Hazara districts
    ]
    
    MALAKAND_SPECIFIC_PATTERNS = [
        r"(?i)Malakand\s+Division",
        r"(?i)مالاکنڈ\s*ڈویژن",
        r"(?i)سوات|دیر|چارسدہ|شنگلہ|بونیر",  # Malakand districts
    ]
    
    # Amendment indicators (enhanced)
    AMENDMENT_PATTERNS = [
        r"(?i)amended\s+by",
        r"(?i)substituted\s+by",
        r"(?i)متبادل",
        r"(?i)ترمیم شدہ",
        r"(?i)ضمنی\s*ترمیم",  # Supplementary amendment
        r"(?i)نظر ثانی شدہ",  # Revised
        r"(?i)S\.R\.O\.",  # Gazette notification
        r"(?i)نوٹیفیکیشن",
    ]
    
    # Date patterns (enhanced for KPK documents)
    DATE_PATTERNS = [
        r"\d{1,2}[-/]\d{1,2}[-/]\d{2,4}",  # DD-MM-YYYY
        r"\d{4}[-/]\d{1,2}[-/]\d{1,2}",  # YYYY-MM-DD
        r"(?i)(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},?\s+\d{4}",
        r"\d{1,2}\s+(?:جنوری|فروری|مارچ|اپریل|مئی|جون|جولائی|اگست|ستمبر|اکتوبر|نومبر|دسمبر)\s+\d{4}",
        r"\d{4}",  # Just year
        r"(?i)dated\s+\d{1,2}[-\s]\w+[-\s]\d{4}",
    ]
    
    # Document number patterns (enhanced)
    DOCUMENT_NUMBER_PATTERNS = [
        r"(?i)(?:no\.?|number|نمبر)\s*[:=]?\s*([A-Z0-9/\-()]+)",
        r"(?i)(?:ref\.?|reference|حوالہ)\s*[:=]?\s*([A-Z0-9/\-()]+)",
        r"(?i)(?:letter|خط)\s*no\.?\s*([A-Z0-9/\-()]+)",
    ]
    
    # Language detection patterns (enhanced)
    URDU_PATTERNS = [
        r"[\u0600-\u06FF]",  # Arabic script (includes Urdu)
        r"[\u0750-\u077F]",  # Arabic supplement
        r"[\u08A0-\u08FF]",  # Arabic extended-A
        r"[\uFB50-\uFDFF]",  # Arabic presentation forms
    ]
    
    PASHTO_PATTERNS = [
        r"[\u0671\u067E\u0686\u0693\u069A\u06AB\u06AF\u06CC]",  # Pashto-specific letters
        r"(?i)پښتو|پشتو",  # Pashto language name
        r"(?i)خېر|ښه|مننه",  # Common Pashto words
    ]
    
    # Quality indicators (enhanced)
    SCAN_QUALITY_INDICATORS = [
        r"(?i)scanned",
        r"(?i)image",
        r"(?i)photo copy",
        r"(?i)فٹو\s*کاپی",
        r"(?i)اسکین\s*شدہ",
        r"\.(?:jpg|jpeg|png|tiff?|bmp|gif)",  # Image file extensions
    ]
    
    OCR_ERROR_INDICATORS = [
        r"[l1I|]",  # Common OCR confusions
        r"[o0O]",   # Zero vs O
        r"[5S]",    # Five vs S
        r"[8B]",    # Eight vs B
        r"[nm]",    # n vs m
        r"[UV]",    # U vs V
    ]
    
    # Structure patterns (for quality assessment)
    STRUCTURE_PATTERNS = [
        r"(?i)^\s*section\s+\d+",  # Section headings
        r"(?i)^\s*article\s+\d+",  # Article headings
        r"(?i)^\s*فصل\s+\d+",  # Urdu section headings
        r"(?i)^\s*\d+\.\s+\w+",  # Numbered list
        r"(?i)^\s*[\u2022\-\*]\s+\w+",  # Bulleted list
        r"(?i)table\s+\d+:",  # Table references
        r"(?i)figure\s+\d+:",  # Figure references
    ]

# ============================================================================
# DOCUMENT PROFILE CLASS (ENHANCED)
# ============================================================================

class DocumentProfile:
    """Complete profile of a KPK forestry document with enhanced capabilities"""
    
    def __init__(self, 
                 document_path: Optional[Union[str, Path]] = None,
                 config: Optional[DocProfilerConfig] = None):
        
        self.document_path = str(document_path) if document_path else None
        self.filename = Path(document_path).name if document_path else "unknown"
        self.profile_id = self._generate_profile_id()
        
        # Configuration
        self.config = config or DocProfilerConfig()
        
        # Basic information
        self.document_type: Optional[DocumentType] = None
        self.jurisdiction: Optional[JurisdictionType] = None
        self.language_mix: Optional[LanguageMix] = None
        self.quality: Optional[DocumentQuality] = None
        
        # KPK-specific information (enhanced)
        self.is_kpk: bool = False
        self.kpk_division: Optional[str] = None
        self.kpk_district: Optional[str] = None
        self.is_hazara: bool = False
        self.is_malakand: bool = False
        self.is_merged_area: bool = False  # For formerly FATA areas
        
        # Content analysis (enhanced)
        self.contains_amendments: bool = False
        self.amendment_count: int = 0
        self.amendment_references: List[str] = []
        self.has_tables: bool = False
        self.has_figures: bool = False
        self.has_forms: bool = False
        self.has_signatures: bool = False
        self.has_stamps: bool = False
        self.has_attachments: bool = False
        
        # Dates (enhanced)
        self.creation_date: Optional[datetime] = None
        self.effective_date: Optional[datetime] = None
        self.expiry_date: Optional[datetime] = None
        self.amendment_dates: List[datetime] = []
        self.all_dates: List[datetime] = []
        
        # Document numbers (enhanced)
        self.document_number: Optional[str] = None
        self.circular_number: Optional[str] = None
        self.fir_number: Optional[str] = None
        self.gazette_number: Optional[str] = None
        self.permit_number: Optional[str] = None
        self.license_number: Optional[str] = None
        self.report_number: Optional[str] = None
        
        # Text statistics (enhanced)
        self.total_pages: int = 0
        self.total_words: int = 0
        self.total_characters: int = 0
        self.english_word_count: int = 0
        self.urdu_word_count: int = 0
        self.pashto_word_count: int = 0
        self.unique_entities: Set[str] = set()
        self.entities_by_type: Dict[str, List[str]] = {}
        
        # Quality metrics (enhanced)
        self.ocr_confidence: float = 0.0
        self.structure_score: float = 0.0
        self.completeness_score: float = 0.0
        self.readability_score: float = 0.0
        self.overall_quality_score: float = 0.0
        self.quality_indicators: Dict[str, float] = {}
        
        # Processing flags (enhanced)
        self.needs_ocr_correction: bool = False
        self.needs_language_separation: bool = False
        self.needs_table_extraction: bool = False
        self.needs_figure_extraction: bool = False
        self.needs_form_extraction: bool = False
        self.needs_manual_review: bool = False
        self.priority: int = ProcessingPriority.MEDIUM.value
        
        # Extraction confidence
        self.extraction_confidence: float = 0.0
        self.classification_confidence: float = 0.0
        self.jurisdiction_confidence: float = 0.0
        self.language_confidence: float = 0.0
        
        # Metadata (enhanced)
        self.source_department: Optional[str] = None
        self.issuing_authority: Optional[str] = None
        self.author_name: Optional[str] = None
        self.recipients: List[str] = []
        self.tags: List[str] = []
        self.categories: List[str] = []
        self.keywords: List[str] = []
        
        # Processing history
        self.profiled_at: datetime = datetime.now()
        self.profiled_by: str = "GreenLawAI-KPK Document Profiler v2.1"
        self.processing_notes: List[str] = []
        self.processing_warnings: List[str] = []
        self.processing_errors: List[str] = []
        
        # Abstention tracking
        self.abstention_ids: List[str] = []
        self.abstention_reasons: List[str] = []
        
        # NLP components (lazy-loaded)
        self._nlp = None
        
        # Add initial processing note
        self.add_processing_note(f"Profile created for: {self.filename}")
    
    def _generate_profile_id(self) -> str:
        """Generate unique profile ID with timestamp and hash"""
        base_str = f"{self.document_path}_{datetime.now().isoformat()}"
        hash_digest = hashlib.md5(base_str.encode()).hexdigest()[:12]
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"docprof_{timestamp}_{hash_digest}"
    
    @property
    def nlp(self) -> Optional[Language]:
        """Lazy-load spaCy NLP model"""
        if self._nlp is None and self.config.ENTITY_EXTRACTION['use_spacy']:
            try:
                self._nlp = spacy.load(self.config.ENTITY_EXTRACTION['spacy_model'])
            except Exception as e:
                self.add_processing_warning(f"Failed to load spaCy model: {e}")
                self._nlp = None
        return self._nlp
    
    def add_processing_note(self, note: str):
        """Add a processing note with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.processing_notes.append(f"[{timestamp}] {note}")
    
    def add_processing_warning(self, warning: str):
        """Add a processing warning"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.processing_warnings.append(f"[{timestamp}] WARNING: {warning}")
    
    def add_processing_error(self, error: str):
        """Add a processing error"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.processing_errors.append(f"[{timestamp}] ERROR: {error}")
    
    def add_abstention(self, abstention_id: str, reason: str):
        """Record an abstention related to this document"""
        self.abstention_ids.append(abstention_id)
        self.abstention_reasons.append(reason)
        self.add_processing_note(f"Abstention logged: {abstention_id} - {reason}")
    
    def add_quality_indicator(self, indicator: str, score: float):
        """Add a quality indicator score"""
        self.quality_indicators[indicator] = score
    
    def calculate_priority(self) -> int:
        """Calculate processing priority based on profile"""
        priority_score = 0
        
        # Use configured weights
        weights = self.config.PRIORITY_WEIGHTS
        
        # Higher priority for KPK documents
        if self.is_kpk:
            priority_score += weights['is_kpk']
        
        # Higher priority for laws and ordinances
        if self.document_type in [DocumentType.LAW, DocumentType.ORDINANCE, DocumentType.RULE]:
            priority_score += weights['is_law_type']
        elif self.document_type == DocumentType.CIRCULAR:
            priority_score += weights['is_circular']
        
        # Higher priority for poor quality (needs more attention)
        if self.quality == DocumentQuality.POOR:
            priority_score += weights['poor_quality']
            self.needs_manual_review = True
        elif self.quality == DocumentQuality.UNREADABLE:
            priority_score += weights['unreadable']
            self.needs_manual_review = True
        
        # Higher priority if amendments present
        if self.contains_amendments:
            priority_score += weights['has_amendments']
        
        # Higher priority if needs OCR correction
        if self.needs_ocr_correction:
            priority_score += weights['needs_ocr']
        
        # Higher priority if needs language separation
        if self.needs_language_separation:
            priority_score += weights['needs_language_sep']
        
        # Convert score to priority level
        if priority_score >= 8:
            return ProcessingPriority.CRITICAL.value
        elif priority_score >= 5:
            return ProcessingPriority.HIGH.value
        elif priority_score >= 3:
            return ProcessingPriority.MEDIUM.value
        else:
            return ProcessingPriority.LOW.value
    
    def get_processing_requirements(self) -> Dict[str, bool]:
        """Get processing requirements based on profile"""
        return {
            'ocr_correction': self.needs_ocr_correction,
            'language_separation': self.needs_language_separation,
            'table_extraction': self.needs_table_extraction,
            'figure_extraction': self.needs_figure_extraction,
            'form_extraction': self.needs_form_extraction,
            'amendment_tracking': self.contains_amendments,
            'authority_resolution': self.is_kpk and self.jurisdiction == JurisdictionType.MULTIPLE,
            'manual_review': self.needs_manual_review,
            'entity_extraction': len(self.unique_entities) < 10 and self.total_words > 100,
        }
    
    def get_recommended_phases(self) -> List[str]:
        """Get recommended processing phases based on profile"""
        phases = ['phase_0_foundation']  # Always include foundation
        
        requirements = self.get_processing_requirements()
        
        if requirements['ocr_correction'] or requirements['language_separation']:
            phases.append('phase_1_extraction')
            phases.append('phase_2_restoration')
        
        if requirements['table_extraction'] or requirements['figure_extraction']:
            phases.append('phase_1_extraction')
        
        if self.language_mix in [LanguageMix.ENGLISH_URDU, LanguageMix.ENGLISH_PASHTO, 
                                LanguageMix.URDU_PASHTO, LanguageMix.TRILINGUAL, LanguageMix.MIXED]:
            phases.append('phase_3_linguistic_alignment')
        
        if self.document_type in [DocumentType.LAW, DocumentType.ORDINANCE, DocumentType.RULE,
                                 DocumentType.CIRCULAR, DocumentType.GAZETTE]:
            phases.append('phase_4_legal_extraction')
        
        if requirements['amendment_tracking'] or requirements['authority_resolution']:
            phases.append('phase_5_authority_reasoning')
        
        # Always include graph construction and orchestration
        phases.append('phase_6_graph_construction')
        phases.append('phase_7_orchestration')
        
        return list(dict.fromkeys(phases))  # Remove duplicates while preserving order
    
    def is_processable(self) -> Tuple[bool, str, float]:
        """Check if document can be processed with confidence score"""
        
        if self.quality == DocumentQuality.UNREADABLE:
            return False, "Document is unreadable", 0.0
        
        if not self.document_type:
            return False, "Could not determine document type", 0.0
        
        if self.overall_quality_score < self.config.CONFIDENCE_THRESHOLDS['abstention_threshold']:
            reason = f"Quality score too low: {self.overall_quality_score:.2f}"
            return False, reason, self.overall_quality_score
        
        # Calculate processability confidence
        confidence_factors = [
            self.extraction_confidence,
            self.overall_quality_score,
            self.classification_confidence,
            1.0 if self.total_words > 50 else 0.5,  # Content factor
        ]
        
        processability_confidence = sum(confidence_factors) / len(confidence_factors)
        
        if processability_confidence >= 0.5:
            return True, "Document can be processed", processability_confidence
        else:
            return False, f"Low processability confidence: {processability_confidence:.2f}", processability_confidence
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert profile to dictionary"""
        data = {
            'profile_id': self.profile_id,
            'document_path': self.document_path,
            'filename': self.filename,
            
            # Basic information
            'document_type': self.document_type.value if self.document_type else None,
            'jurisdiction': self.jurisdiction.value if self.jurisdiction else None,
            'language_mix': self.language_mix.value if self.language_mix else None,
            'quality': self.quality.value if self.quality else None,
            
            # KPK-specific information
            'is_kpk': self.is_kpk,
            'kpk_division': self.kpk_division,
            'kpk_district': self.kpk_district,
            'is_hazara': self.is_hazara,
            'is_malakand': self.is_malakand,
            'is_merged_area': self.is_merged_area,
            
            # Content analysis
            'contains_amendments': self.contains_amendments,
            'amendment_count': self.amendment_count,
            'amendment_references': self.amendment_references,
            'has_tables': self.has_tables,
            'has_figures': self.has_figures,
            'has_forms': self.has_forms,
            'has_signatures': self.has_signatures,
            'has_stamps': self.has_stamps,
            'has_attachments': self.has_attachments,
            
            # Dates
            'creation_date': self.creation_date.isoformat() if self.creation_date else None,
            'effective_date': self.effective_date.isoformat() if self.effective_date else None,
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'amendment_dates': [d.isoformat() for d in self.amendment_dates],
            'all_dates': [d.isoformat() for d in self.all_dates],
            
            # Document numbers
            'document_number': self.document_number,
            'circular_number': self.circular_number,
            'fir_number': self.fir_number,
            'gazette_number': self.gazette_number,
            'permit_number': self.permit_number,
            'license_number': self.license_number,
            'report_number': self.report_number,
            
            # Text statistics
            'total_pages': self.total_pages,
            'total_words': self.total_words,
            'total_characters': self.total_characters,
            'english_word_count': self.english_word_count,
            'urdu_word_count': self.urdu_word_count,
            'pashto_word_count': self.pashto_word_count,
            'unique_entities': list(self.unique_entities),
            'entities_by_type': self.entities_by_type,
            
            # Quality metrics
            'ocr_confidence': self.ocr_confidence,
            'structure_score': self.structure_score,
            'completeness_score': self.completeness_score,
            'readability_score': self.readability_score,
            'overall_quality_score': self.overall_quality_score,
            'quality_indicators': self.quality_indicators,
            
            # Processing flags
            'needs_ocr_correction': self.needs_ocr_correction,
            'needs_language_separation': self.needs_language_separation,
            'needs_table_extraction': self.needs_table_extraction,
            'needs_figure_extraction': self.needs_figure_extraction,
            'needs_form_extraction': self.needs_form_extraction,
            'needs_manual_review': self.needs_manual_review,
            'priority': self.priority,
            'priority_label': ProcessingPriority(self.priority).name if hasattr(ProcessingPriority, '_value2member_map_') else str(self.priority),
            
            # Extraction confidence
            'extraction_confidence': self.extraction_confidence,
            'classification_confidence': self.classification_confidence,
            'jurisdiction_confidence': self.jurisdiction_confidence,
            'language_confidence': self.language_confidence,
            
            # Metadata
            'source_department': self.source_department,
            'issuing_authority': self.issuing_authority,
            'author_name': self.author_name,
            'recipients': self.recipients,
            'tags': self.tags,
            'categories': self.categories,
            'keywords': self.keywords,
            
            # Processing history
            'profiled_at': self.profiled_at.isoformat(),
            'profiled_by': self.profiled_by,
            'processing_notes': self.processing_notes,
            'processing_warnings': self.processing_warnings,
            'processing_errors': self.processing_errors,
            
            # Abstention tracking
            'abstention_ids': self.abstention_ids,
            'abstention_reasons': self.abstention_reasons,
            
            # Processing recommendations
            'processing_requirements': self.get_processing_requirements(),
            'recommended_phases': self.get_recommended_phases(),
            
            # Processability
            'is_processable': self.is_processable()[0],
            'processability_reason': self.is_processable()[1],
            'processability_confidence': self.is_processable()[2],
        }
        
        return data
    
    def to_json(self, indent: int = 2) -> str:
        """Convert profile to JSON string"""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, default=str)
    
    def to_summary(self) -> str:
        """Generate a human-readable summary"""
        processable, reason, confidence = self.is_processable()
        
        summary = f"""
        ========================================
        DOCUMENT PROFILE SUMMARY
        ========================================
        Document: {self.filename}
        Profile ID: {self.profile_id}
        
        BASIC INFORMATION:
        - Type: {self.document_type.value if self.document_type else 'Unknown'}
        - Jurisdiction: {self.jurisdiction.value if self.jurisdiction else 'Unknown'}
        - Quality: {self.quality.value if self.quality else 'Unknown'}
        - Language Mix: {self.language_mix.value if self.language_mix else 'Unknown'}
        
        KPK INFORMATION:
        - Is KPK: {'Yes' if self.is_kpk else 'No'}
        - Division: {self.kpk_division or 'Not specified'}
        - District: {self.kpk_district or 'Not specified'}
        - Hazara Region: {'Yes' if self.is_hazara else 'No'}
        - Malakand Region: {'Yes' if self.is_malakand else 'No'}
        
        CONTENT ANALYSIS:
        - Total Pages: {self.total_pages}
        - Total Words: {self.total_words}
        - Amendments: {self.amendment_count} found
        - Tables: {'Yes' if self.has_tables else 'No'}
        - Forms: {'Yes' if self.has_forms else 'No'}
        - Signatures: {'Yes' if self.has_signatures else 'No'}
        
        QUALITY METRICS:
        - Overall Quality Score: {self.overall_quality_score:.2f}
        - Extraction Confidence: {self.extraction_confidence:.2f}
        - Structure Score: {self.structure_score:.2f}
        
        PROCESSING REQUIREMENTS:
        - OCR Correction: {'Required' if self.needs_ocr_correction else 'Not required'}
        - Language Separation: {'Required' if self.needs_language_separation else 'Not required'}
        - Table Extraction: {'Required' if self.needs_table_extraction else 'Not required'}
        - Manual Review: {'Required' if self.needs_manual_review else 'Not required'}
        - Priority: {self.priority} ({'High' if self.priority <= 2 else 'Medium' if self.priority == 3 else 'Low'})
        
        PROCESSABILITY:
        - Can be processed: {'Yes' if processable else 'No'}
        - Reason: {reason}
        - Confidence: {confidence:.2f}
        
        RECOMMENDED PHASES: {', '.join(self.get_recommended_phases())}
        
        TAGS: {', '.join(self.tags[:10])}{'...' if len(self.tags) > 10 else ''}
        ========================================
        """
        
        return summary

# ============================================================================
# ENHANCED DOCUMENT PROFILER
# ============================================================================

class KPKDocumentProfiler:
    """Main document profiler for KPK forestry documents with enhanced capabilities"""
    
    def __init__(self, 
                 config: Optional[Union[DocProfilerConfig, Dict]] = None,
                 abstention_logger: Optional[AbstentionLogger] = None,
                 enable_abstention_logging: bool = True,
                 enable_spacy: bool = True,
                 logger: Optional[logging.Logger] = None):
        
        # Configuration
        if isinstance(config, dict):
            self.config = DocProfilerConfig()
            # Update config from dict
            for key, value in config.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
        else:
            self.config = config or DocProfilerConfig()
        
        # NLP setup
        if enable_spacy and self.config.ENTITY_EXTRACTION['use_spacy']:
            try:
                self.nlp = spacy.load(self.config.ENTITY_EXTRACTION['spacy_model'])
                self.use_spacy = True
            except Exception as e:
                print(f"Warning: Could not load spaCy model: {e}")
                self.nlp = None
                self.use_spacy = False
        else:
            self.nlp = None
            self.use_spacy = False
        
        # Abstention logging
        self.abstention_logger = abstention_logger
        self.enable_abstention_logging = enable_abstention_logging and ABSTENTION_AVAILABLE
        
        # Logger
        self.logger = logger or logging.getLogger(__name__)
        
        # Patterns
        self.patterns = KPKDocumentPatterns()
        
        # Statistics
        self.stats = {
            'documents_processed': 0,
            'kpk_documents': 0,
            'hazara_documents': 0,
            'malakand_documents': 0,
            'processable_documents': 0,
            'unprocessable_documents': 0,
            'by_type': {},
            'by_quality': {},
            'by_jurisdiction': {},
            'abstentions_logged': 0,
            'processing_time_total': 0.0,
            'average_processing_time': 0.0,
        }
        
        # Cache for document type patterns
        self._document_type_patterns = None
        
        self.logger.info("KPKDocumentProfiler initialized with enhanced capabilities")
    
    def _get_document_type_patterns(self) -> Dict[DocumentType, List[str]]:
        """Cache document type patterns for efficiency"""
        if self._document_type_patterns is None:
            self._document_type_patterns = {
                DocumentType.LAW: self.patterns.LAW_PATTERNS,
                DocumentType.ORDINANCE: self.patterns.LAW_PATTERNS,  # Same as laws
                DocumentType.RULE: self.patterns.LAW_PATTERNS,  # Same as laws
                DocumentType.CIRCULAR: self.patterns.CIRCULAR_PATTERNS,
                DocumentType.WORKING_PLAN: self.patterns.WORKING_PLAN_PATTERNS,
                DocumentType.FIR: self.patterns.FIR_PATTERNS,
                DocumentType.GAZETTE: self.patterns.GAZETTE_PATTERNS,
                DocumentType.PERMIT: self.patterns.PERMIT_PATTERNS,
                DocumentType.REPORT: self.patterns.REPORT_PATTERNS,
            }
        return self._document_type_patterns
    
    def profile_document(self, 
                        document_path: Optional[Union[str, Path]] = None,
                        extracted_text: Optional[str] = None,
                        metadata: Optional[Dict[str, Any]] = None,
                        extract_entities: bool = True) -> DocumentProfile:
        """
        Create a comprehensive profile for a document
        
        Args:
            document_path: Path to the document file
            extracted_text: Pre-extracted text (if available)
            metadata: Additional metadata about the document
            extract_entities: Whether to perform entity extraction
            
        Returns:
            DocumentProfile object
        """
        
        import time
        start_time = time.time()
        
        profile = DocumentProfile(document_path, self.config)
        
        try:
            # Update statistics
            self.stats['documents_processed'] += 1
            
            # Analyze text if provided
            if extracted_text:
                self._analyze_text(profile, extracted_text, extract_entities)
            
            # Analyze metadata if provided
            if metadata:
                self._analyze_metadata(profile, metadata)
            
            # Analyze filename for clues
            if document_path:
                self._analyze_filename(profile)
                self._probe_pdf_structure(profile, document_path)
            
            # Determine document type
            self._determine_document_type(profile, extracted_text)
            
            # Determine jurisdiction
            self._determine_jurisdiction(profile, extracted_text)
            
            # Determine language mix
            self._determine_language_mix(profile, extracted_text)
            
            # Assess quality
            self._assess_quality(profile, extracted_text)
            
            # Extract dates and numbers
            self._extract_dates_and_numbers(profile, extracted_text)
            
            # Analyze content features
            self._analyze_content_features(profile, extracted_text)
            
            # Extract additional information
            self._extract_additional_info(profile, extracted_text)
            
            # Calculate scores and flags
            self._calculate_scores_and_flags(profile)
            
            # Update KPK statistics
            if profile.is_kpk:
                self.stats['kpk_documents'] += 1
            if profile.is_hazara:
                self.stats['hazara_documents'] += 1
            if profile.is_malakand:
                self.stats['malakand_documents'] += 1
            
            # Update type statistics
            doc_type = profile.document_type.value if profile.document_type else 'unknown'
            self.stats['by_type'][doc_type] = self.stats['by_type'].get(doc_type, 0) + 1
            
            # Update quality statistics
            quality = profile.quality.value if profile.quality else 'unknown'
            self.stats['by_quality'][quality] = self.stats['by_quality'].get(quality, 0) + 1
            
            # Update jurisdiction statistics
            jurisdiction = profile.jurisdiction.value if profile.jurisdiction else 'unknown'
            self.stats['by_jurisdiction'][jurisdiction] = self.stats['by_jurisdiction'].get(jurisdiction, 0) + 1
            
            # Update processability statistics
            processable, _, _ = profile.is_processable()
            if processable:
                self.stats['processable_documents'] += 1
            else:
                self.stats['unprocessable_documents'] += 1
            
            # Add processing note
            profile.add_processing_note("Profiling completed by Enhanced KPKDocumentProfiler")
            
            # Log success
            self.logger.info(f"Successfully profiled document: {profile.filename}")
            
        except Exception as e:
            error_msg = f"Error profiling document {document_path}: {str(e)}"
            profile.add_processing_error(error_msg)
            profile.document_type = DocumentType.OTHER
            profile.quality = DocumentQuality.UNREADABLE
            profile.needs_manual_review = True
            self.logger.error(error_msg, exc_info=True)
        
        # Calculate processing time
        processing_time = time.time() - start_time
        self.stats['processing_time_total'] += processing_time
        self.stats['average_processing_time'] = (
            self.stats['processing_time_total'] / self.stats['documents_processed']
        )
        
        profile.add_processing_note(f"Profiling completed in {processing_time:.2f} seconds")
        
        return profile
    
    def _analyze_text(self, profile: DocumentProfile, text: str, extract_entities: bool = True):
        """Analyze text content with enhanced capabilities"""
        if not text:
            profile.add_processing_warning("No text provided for analysis")
            return
        
        # Basic text statistics
        profile.total_characters = len(text)
        words = re.findall(r'\b\w+\b', text)  # Better word splitting
        profile.total_words = len(words)
        
        # Character distribution for language detection
        profile.english_word_count = self._count_english_words(words)
        profile.urdu_word_count = self._count_urdu_words(text)
        profile.pashto_word_count = self._count_pashto_words(text)
        
        # Entity extraction (enhanced)
        if extract_entities:
            profile.unique_entities = self._extract_enhanced_entities(text)
            profile.entities_by_type = self._categorize_entities(profile.unique_entities)
        
        # Extract keywords (simple TF-based)
        if len(words) > 10:
            profile.keywords = self._extract_keywords(words)
    
    def _count_english_words(self, words: List[str]) -> int:
        """Count English words (enhanced detection)"""
        english_pattern = re.compile(r'^[a-zA-Z][a-zA-Z\s\-]*[a-zA-Z]$')
        count = 0
        for word in words:
            if 2 <= len(word) <= 50 and english_pattern.match(word):
                count += 1
        return count
    
    def _count_urdu_words(self, text: str) -> int:
        """Count Urdu words (enhanced)"""
        # Urdu word pattern (sequence of Urdu characters)
        urdu_pattern = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF]{2,}')
        matches = urdu_pattern.findall(text)
        return len(matches)
    
    def _count_pashto_words(self, text: str) -> int:
        """Count Pashto words (enhanced)"""
        # Pashto word pattern (sequence with Pashto-specific characters)
        pashto_pattern = re.compile(
            r'(?:[\u0671\u067E\u0686\u0693\u069A\u06AB\u06AF\u06CC][\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]*)+|'  # Words with Pashto letters
            r'(?:پښتو|پشتو|خېر|ښه|مننه|ستاسې|مهرباني)'  # Common Pashto words
        )
        matches = pashto_pattern.findall(text)
        return len(matches)
    
    def _extract_enhanced_entities(self, text: str) -> Set[str]:
        """Extract enhanced entities from text using multiple methods"""
        entities = set()
        
        # Method 1: Pattern-based extraction
        entities.update(self._extract_entities_by_pattern(text))
        
        # Method 2: spaCy-based extraction (if available)
        if self.use_spacy and self.nlp and len(text) < 1000000:  # Limit for performance
            try:
                doc = self.nlp(text[:50000])  # Process first 50k chars for performance
                for ent in doc.ents:
                    if ent.label_ in ['LAW', 'ORG', 'GPE', 'LOC', 'DATE', 'MONEY']:
                        entities.add(f"{ent.label_.lower()}:{ent.text}")
            except Exception as e:
                self.logger.warning(f"spaCy entity extraction failed: {e}")
        
        # Method 3: KPK-specific entity extraction
        entities.update(self._extract_kpk_specific_entities(text))
        
        # Limit number of entities
        max_entities = self.config.ENTITY_EXTRACTION['max_entities']
        if len(entities) > max_entities:
            entities = set(list(entities)[:max_entities])
        
        return entities
    
    def _extract_entities_by_pattern(self, text: str) -> Set[str]:
        """Extract entities using regex patterns"""
        entities = set()
        
        # Extract section numbers (enhanced)
        section_patterns = [
            r'(?:Section|Sec\.|Sec|فصل|دفعہ)\s+(\d+[A-Za-z]*(?:\s*\(\d+\))?)',
            r'(\d+[A-Z]?)\s*(?:of\s+this\s+Act|کا\s+دفعہ)',
        ]
        
        for pattern in section_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                entities.add(f"section:{match}")
        
        # Extract penalties (enhanced)
        penalty_patterns = [
            r'Rs\.?\s*([\d,]+(?:\s*lakhs?|\s*millions?|\s*crores?)?)',
            r'روپے\s*([\d,]+(?:\s*لاکھ|\s*ملین|\s*کروڑ)?)',
            r'fine\s+of\s+Rs\.?\s*([\d,]+)',
            r'جرمانہ\s*:?\s*روپے\s*([\d,]+)',
        ]
        
        for pattern in penalty_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                entities.add(f"penalty:{match}")
        
        # Extract years (for laws)
        year_pattern = r'\b(1[0-9]{3}|20[0-9]{2})\b'
        years = re.findall(year_pattern, text)
        for year in years:
            if 1800 <= int(year) <= 2100:
                entities.add(f"year:{year}")
        
        # Extract KPK districts
        kpk_districts = [
            'Abbottabad', 'Mansehra', 'Haripur', 'Battagram', 'Torghar', 'Kohistan',
            'Swat', 'Malakand', 'Dir', 'Chitral', 'Shangla', 'Buner',
            'Peshawar', 'Charsadda', 'Nowshera', 'Mardan', 'Swabi',
            'Kohat', 'Hangu', 'Karak', 'Bannu', 'Lakki Marwat', 'Tank',
            'Dera Ismail Khan', 'South Waziristan', 'North Waziristan',
        ]
        
        for district in kpk_districts:
            if re.search(rf'\b{district}\b', text, re.IGNORECASE):
                entities.add(f"district:{district.lower()}")
        
        return entities
    
    def _extract_kpk_specific_entities(self, text: str) -> Set[str]:
        """Extract KPK-specific entities"""
        entities = set()
        
        # KPK Forest Acts and Ordinances
        kpk_laws = [
            'KPK Forest Ordinance 2002',
            'Hazara Forest Act 1912',
            'Malakand Forest Regulation',
            'KP Wildlife Act',
            'KP Environmental Act',
        ]
        
        for law in kpk_laws:
            if re.search(re.escape(law), text, re.IGNORECASE):
                entities.add(f"law:{law}")
        
        # Forest types in KPK
        forest_types = [
            'Chir Pine', 'Deodar', 'Fir', 'Spruce', 'Oak',
            'چلغوزہ', 'دیودار', 'صنوبر', 'شاہ بلوط',
        ]
        
        for forest in forest_types:
            if forest in text:
                entities.add(f"forest_type:{forest}")
        
        return entities
    
    def _categorize_entities(self, entities: Set[str]) -> Dict[str, List[str]]:
        """Categorize entities by type"""
        categories = {
            'section': [],
            'penalty': [],
            'year': [],
            'law': [],
            'district': [],
            'division': [],
            'forest_type': [],
            'other': [],
        }
        
        for entity in entities:
            if ':' in entity:
                category, value = entity.split(':', 1)
                if category in categories:
                    categories[category].append(value)
                else:
                    categories['other'].append(entity)
            else:
                categories['other'].append(entity)
        
        # Remove empty categories
        return {k: v for k, v in categories.items() if v}
    
    def _extract_keywords(self, words: List[str], top_n: int = 10) -> List[str]:
        """Extract top keywords using simple TF"""
        from collections import Counter
        
        # Filter stopwords and short words
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        filtered_words = [w.lower() for w in words if w.lower() not in stopwords and len(w) > 2]
        
        # Count frequencies
        word_counts = Counter(filtered_words)
        
        # Get top N words
        top_words = [word for word, count in word_counts.most_common(top_n)]
        
        return top_words
    
    def _probe_pdf_structure(self, profile: DocumentProfile, document_path: Union[str, Path]) -> None:
        """Set page count and basic readability from the PDF file when text is not pre-extracted."""
        path = Path(document_path)
        if path.suffix.lower() != '.pdf' or not path.exists():
            return
        if profile.total_pages > 0 and profile.quality != DocumentQuality.UNREADABLE:
            return
        try:
            doc = pymupdf.open(str(path))
            profile.total_pages = len(doc)
            if len(doc) > 0:
                sample = (doc[0].get_text() or "").strip()
                if len(sample) >= 50 and profile.quality == DocumentQuality.UNREADABLE:
                    profile.quality = DocumentQuality.GOOD
                profile.total_characters = max(profile.total_characters, len(sample))
            doc.close()
            profile.add_quality_indicator("pdf_probe", True)
        except Exception as e:
            profile.add_processing_note(f"PDF structure probe failed: {e}")

    def _analyze_metadata(self, profile: DocumentProfile, metadata: Dict[str, Any]):
        """Analyze document metadata (enhanced)"""
        # Extract page count
        page_keys = ['pages', 'page_count', 'numpages', 'total_pages']
        for key in page_keys:
            if key in metadata:
                try:
                    profile.total_pages = int(metadata[key])
                    break
                except (ValueError, TypeError):
                    continue
        
        # Extract dates
        date_keys = ['creation_date', 'create_date', 'date_created', 'modified_date', 'last_modified']
        for key in date_keys:
            if key in metadata:
                try:
                    date_str = str(metadata[key])
                    # Try multiple date formats
                    for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%d-%m-%Y', '%d/%m/%Y', '%Y%m%d']:
                        try:
                            profile.creation_date = datetime.strptime(date_str[:10], fmt)
                            break
                        except ValueError:
                            continue
                    if profile.creation_date:
                        break
                except Exception:
                    continue
        
        # Extract OCR confidence
        if 'ocr_confidence' in metadata:
            try:
                profile.ocr_confidence = float(metadata['ocr_confidence'])
                profile.add_quality_indicator('ocr_confidence', profile.ocr_confidence)
            except (ValueError, TypeError):
                pass
        
        # Extract source information
        source_keys = ['source', 'author', 'creator', 'producer', 'company']
        for key in source_keys:
            if key in metadata and metadata[key]:
                profile.source_department = str(metadata[key])
                if key == 'author':
                    profile.author_name = str(metadata[key])
                break
        
        # Check for scan indicators
        scan_indicators = ['is_scanned', 'scanned', 'image_count', 'has_images']
        for indicator in scan_indicators:
            if indicator in metadata and metadata[indicator]:
                profile.tags.append('scanned')
                profile.needs_ocr_correction = True
                break
        
        # Extract file format information
        if 'format' in metadata:
            profile.tags.append(f"format:{metadata['format'].lower()}")
        
        # Extract security information
        if 'encrypted' in metadata and metadata['encrypted']:
            profile.tags.append('encrypted')
            profile.add_processing_warning("Document is encrypted")
    
    def _analyze_filename(self, profile: DocumentProfile):
        """Analyze filename for clues (enhanced)"""
        filename = profile.filename.lower()
        stem = Path(profile.filename).stem.lower()
        
        # Check for KPK indicators in filename
        kpk_indicators = ['kpk', 'khyber', 'pakhtunkhwa', 'خیبر', 'پختونخوا', 'kp_']
        for indicator in kpk_indicators:
            if indicator in filename:
                profile.is_kpk = True
                profile.tags.append('kpk_document')
                break
        
        # Check for Hazara indicators
        hazara_indicators = ['hazara', 'ہزارہ', 'abbottabad', 'mansehra', 'haripur', 'battagram']
        for indicator in hazara_indicators:
            if indicator in filename:
                profile.is_hazara = True
                profile.kpk_division = "Hazara Division"
                profile.tags.append('hazara_region')
                break
        
        # Check for Malakand indicators
        malakand_indicators = ['malakand', 'مالاکنڈ', 'swat', 'سوات', 'dir', 'دیر']
        for indicator in malakand_indicators:
            if indicator in filename:
                profile.is_malakand = True
                profile.kpk_division = "Malakand Division"
                profile.tags.append('malakand_region')
                break
        
        # Check for document type indicators in filename
        type_patterns = [
            (r'.*ordinance.*', DocumentType.ORDINANCE, 'ordinance'),
            (r'.*act.*', DocumentType.LAW, 'act'),
            (r'.*circular.*', DocumentType.CIRCULAR, 'circular'),
            (r'.*fir.*', DocumentType.FIR, 'fir'),
            (r'.*working.*plan.*', DocumentType.WORKING_PLAN, 'working_plan'),
            (r'.*gazette.*', DocumentType.GAZETTE, 'gazette'),
            (r'.*permit.*', DocumentType.PERMIT, 'permit'),
            (r'.*license.*', DocumentType.LICENSE, 'license'),
            (r'.*report.*', DocumentType.REPORT, 'report'),
            (r'.*policy.*', DocumentType.POLICY, 'policy'),
        ]
        
        for pattern, doc_type, tag in type_patterns:
            if re.search(pattern, filename, re.IGNORECASE):
                if not profile.document_type:  # Only set if not already determined
                    profile.document_type = doc_type
                profile.tags.append(tag)
                break
        
        # Check for quality indicators in filename
        quality_indicators = [
            ('scan', 'scanned', True),  # (pattern, tag, needs_ocr)
            ('scanned', 'scanned', True),
            ('ocr', 'needs_ocr', True),
            ('draft', 'draft', False),
            ('final', 'final', False),
            ('copy', 'copy', False),
            ('unsigned', 'unsigned', True),
        ]
        
        for pattern, tag, needs_ocr in quality_indicators:
            if pattern in filename:
                profile.tags.append(tag)
                if needs_ocr:
                    profile.needs_ocr_correction = True
        
        # Extract year from filename
        year_match = re.search(r'(?:19|20)\d{2}', filename)
        if year_match:
            try:
                year = int(year_match.group())
                if 1800 <= year <= 2100:
                    profile.tags.append(f"year_{year}")
            except ValueError:
                pass
        
        # Extract document number from filename
        number_match = re.search(r'(?:no|num|number)[_.\-]?(\d+)', filename, re.IGNORECASE)
        if number_match and not profile.document_number:
            profile.document_number = number_match.group(1)
    
    def _determine_document_type(self, profile: DocumentProfile, text: Optional[str]):
        """Determine the document type based on content patterns with confidence scoring"""
        if not text and not profile.document_type:
            profile.document_type = DocumentType.OTHER
            profile.classification_confidence = 0.1
            return
        
        type_patterns = self._get_document_type_patterns()
        type_scores = {doc_type: 0.0 for doc_type in DocumentType}
        
        if text:
            text_lower = text.lower()
            text_length = len(text)
            
            # Score based on patterns with weighting
            for doc_type, patterns in type_patterns.items():
                for pattern in patterns:
                    matches = re.findall(pattern, text, re.IGNORECASE)
                    if matches:
                        # Weight by number of matches and pattern specificity
                        weight = 2.0 if '\\d' in pattern else 1.0  # Higher weight for patterns with numbers
                        type_scores[doc_type] += len(matches) * weight
            
            # Additional heuristics with context awareness
            heuristic_patterns = [
                (r'(?i)permit\s+(?:no\.?)?\s*\d+', DocumentType.PERMIT, 2.0),
                (r'(?i)اجازت\s*نامہ', DocumentType.PERMIT, 2.0),
                (r'(?i)license\s+(?:no\.?)?\s*\d+', DocumentType.LICENSE, 2.0),
                (r'(?i)لائسنس', DocumentType.LICENSE, 2.0),
                (r'(?i)report\s+on\s+.+', DocumentType.REPORT, 1.5),
                (r'(?i)رپورٹ\s*برائے', DocumentType.REPORT, 1.5),
                (r'(?i)policy\s+(?:on|for)\s+.+', DocumentType.POLICY, 1.5),
                (r'(?i)پالیسی', DocumentType.POLICY, 1.5),
                (r'(?i)guideline', DocumentType.GUIDELINE, 1.0),
                (r'(?i)ہدایات', DocumentType.GUIDELINE, 1.0),
                (r'(?i)form\s+[A-Z0-9]+', DocumentType.FORM, 1.5),
                (r'فارم', DocumentType.FORM, 1.5),
                (r'(?i)register', DocumentType.REGISTER, 1.0),
                (r'رجسٹر', DocumentType.REGISTER, 1.0),
            ]
            
            for pattern, doc_type, weight in heuristic_patterns:
                if re.search(pattern, text):
                    type_scores[doc_type] += weight
            
            # Context-based scoring
            if 'memorandum' in text_lower or 'یاد داشت' in text:
                type_scores[DocumentType.MEMORANDUM] += 2.0
            
            if 'order' in text_lower and ('court' in text_lower or 'عدالت' in text):
                type_scores[DocumentType.ORDER] += 3.0
            
            if 'agreement' in text_lower or 'معاہدہ' in text:
                type_scores[DocumentType.AGREEMENT] += 2.0
        
        # Consider filename-based type if already set
        if profile.document_type:
            type_scores[profile.document_type] += 1.5
        
        # Normalize scores and calculate confidence
        max_score = max(type_scores.values()) if type_scores else 0
        
        if max_score > 0:
            # Get all types with max score (or close to max)
            threshold = max_score * 0.8  # 80% of max score
            top_types = [t for t, s in type_scores.items() if s >= threshold]
            
            if len(top_types) == 1:
                profile.document_type = top_types[0]
                # Confidence based on score strength and uniqueness
                profile.classification_confidence = min(max_score / 10.0, 1.0)  # Normalize
                
                # Boost confidence if score is significantly higher than others
                second_max = sorted(type_scores.values())[-2] if len(type_scores) > 1 else 0
                if max_score > second_max * 2:  # Twice as high as next best
                    profile.classification_confidence = min(profile.classification_confidence * 1.2, 1.0)
                    
            else:
                # Multiple types with similar scores - ambiguous
                profile.document_type = DocumentType.OTHER
                profile.classification_confidence = 0.4
                
                # Try to choose based on hierarchy
                law_types = [DocumentType.LAW, DocumentType.ORDINANCE, DocumentType.RULE]
                for law_type in law_types:
                    if law_type in top_types:
                        profile.document_type = law_type
                        profile.classification_confidence = 0.5
                        break
                
                reason = f"Ambiguous document type: {', '.join([t.value for t in top_types[:3]])}"
                self._log_abstention_if_enabled(
                    profile, 
                    "ambiguous_document_type", 
                    reason,
                    confidence=profile.classification_confidence
                )
                profile.add_processing_note(f"Ambiguous type detection: {reason}")
        else:
            profile.document_type = DocumentType.OTHER
            profile.classification_confidence = 0.3
        
        # Add tag for determined type
        if profile.document_type:
            type_tag = profile.document_type.value.lower().replace(' ', '_').replace('(', '').replace(')', '')
            profile.tags.append(f"type_{type_tag}")
            profile.categories.append(type_tag)
    
    def _determine_jurisdiction(self, profile: DocumentProfile, text: Optional[str]):
        """Determine the jurisdiction of the document with confidence scoring"""
        if not text and not profile.is_kpk:
            profile.jurisdiction = JurisdictionType.UNKNOWN
            profile.jurisdiction_confidence = 0.1
            return
        
        jurisdiction_scores = {juris: 0.0 for juris in JurisdictionType}
        
        if text:
            # Check for KPK patterns with weighting
            for pattern in self.patterns.KPK_JURISDICTION_PATTERNS:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    profile.is_kpk = True
                    jurisdiction_scores[JurisdictionType.PROVINCIAL] += len(matches) * 2.0
                    jurisdiction_scores[JurisdictionType.DIVISIONAL] += len(matches) * 1.0
            
            # Check for Hazara specific patterns
            for pattern in self.patterns.HAZARA_SPECIFIC_PATTERNS:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    profile.is_hazara = True
                    jurisdiction_scores[JurisdictionType.DIVISIONAL] += len(matches) * 2.0
                    profile.kpk_division = "Hazara Division"
                    profile.tags.append('hazara_jurisdiction')
            
            # Check for Malakand specific patterns
            for pattern in self.patterns.MALAKAND_SPECIFIC_PATTERNS:
                if re.search(pattern, text, re.IGNORECASE):
                    profile.is_malakand = True
                    jurisdiction_scores[JurisdictionType.DIVISIONAL] += 2.0
                    profile.kpk_division = "Malakand Division"
                    profile.tags.append('malakand_jurisdiction')
            
            # Check for federal indicators with context
            federal_indicators = [
                (r"(?i)government\s+of\s+pakistan", 3.0),
                (r"(?i)federal\s+government", 3.0),
                (r"(?i)حکومتِ\s+پاکستان", 3.0),
                (r"(?i)وفاقی\s+حکومت", 3.0),
                (r"(?i)islamabad", 1.0),
                (r"(?i)اسلام آباد", 1.0),
            ]
            
            for pattern, weight in federal_indicators:
                if re.search(pattern, text):
                    jurisdiction_scores[JurisdictionType.FEDERAL] += weight
            
            # Check for divisional indicators
            divisional_indicators = [
                (r"(?i)division(?:al)?\s+(?:forest|office|commissioner)", 2.0),
                (r"(?i)ڈویژن(?:ل)?\s+(?:جنگلات|دفتر|کمشنر)", 2.0),
            ]
            
            for pattern, weight in divisional_indicators:
                if re.search(pattern, text):
                    jurisdiction_scores[JurisdictionType.DIVISIONAL] += weight
            
            # Check for district indicators
            district_indicators = [
                (r"(?i)district\s+(?:forest|office|administration)", 2.0),
                (r"(?i)ضلع\s+(?:جنگلات|دفتر|انتظامیہ)", 2.0),
                (r"(?i)DC\s+office", 1.0),  # Deputy Commissioner
                (r"(?i)ڈی\s*سی\s*دفتر", 1.0),
            ]
            
            for pattern, weight in district_indicators:
                if re.search(pattern, text):
                    jurisdiction_scores[JurisdictionType.DISTRICT] += weight
            
            # Check for local indicators
            local_indicators = [
                (r"(?i)tehsil|تحصیل", 1.0),
                (r"(?i)union\s+council|یونین\s*کونسل", 1.0),
                (r"(?i)village|گاؤں", 0.5),
            ]
            
            for pattern, weight in local_indicators:
                if re.search(pattern, text):
                    jurisdiction_scores[JurisdictionType.LOCAL] += weight
        
        # Determine jurisdiction with confidence
        max_score = max(jurisdiction_scores.values()) if any(v > 0 for v in jurisdiction_scores.values()) else 0
        
        if max_score > 0:
            top_jurisdictions = [j for j, s in jurisdiction_scores.items() if s == max_score]
            
            if len(top_jurisdictions) == 1:
                profile.jurisdiction = top_jurisdictions[0]
                profile.jurisdiction_confidence = min(max_score / 10.0, 1.0)
            else:
                profile.jurisdiction = JurisdictionType.MULTIPLE
                profile.jurisdiction_confidence = 0.5
                profile.tags.append('multiple_jurisdictions')
                profile.add_processing_note(f"Multiple jurisdictions detected: {', '.join([j.value for j in top_jurisdictions])}")
        else:
            profile.jurisdiction = JurisdictionType.UNKNOWN
            profile.jurisdiction_confidence = 0.1
        
        # Set KPK flag if provincial or divisional jurisdiction
        if profile.jurisdiction in [JurisdictionType.PROVINCIAL, JurisdictionType.DIVISIONAL, JurisdictionType.DISTRICT]:
            profile.is_kpk = True
        
        # Extract specific division/district if possible
        if text and profile.is_kpk:
            self._extract_kpk_location(profile, text)
    
    def _extract_kpk_location(self, profile: DocumentProfile, text: str):
        """Extract specific KPK location information"""
        # KPK divisions
        divisions = {
            'Hazara Division': ['abbottabad', 'mansehra', 'haripur', 'battagram', 'torghar', 'kohistan'],
            'Malakand Division': ['swat', 'malakand', 'dir', 'chitral', 'shangla', 'buner'],
            'Peshawar Division': ['peshawar', 'charsadda', 'nowshera'],
            'Mardan Division': ['mardan', 'swabi'],
            'Kohat Division': ['kohat', 'hangu', 'karak'],
            'Bannu Division': ['bannu', 'lakki marwat'],
            'Dera Ismail Khan Division': ['dera ismail khan', 'tank', 'south waziristan', 'north waziristan'],
        }
        
        text_lower = text.lower()
        
        for division, districts in divisions.items():
            for district in districts:
                if district in text_lower:
                    profile.kpk_division = division
                    profile.kpk_district = district.title()
                    profile.tags.append(f"division_{division.lower().replace(' ', '_')}")
                    profile.tags.append(f"district_{district.replace(' ', '_')}")
                    return
        
        # Check for division names directly
        for division in divisions.keys():
            if division.lower() in text_lower:
                profile.kpk_division = division
                profile.tags.append(f"division_{division.lower().replace(' ', '_')}")
                break
    
    def _determine_language_mix(self, profile: DocumentProfile, text: Optional[str]):
        """Determine the language mixing pattern with confidence scoring"""
        if not text:
            profile.language_mix = LanguageMix.UNKNOWN
            profile.language_confidence = 0.1
            return
        
        # Count characters by script with enhanced detection
        english_chars = len(re.findall(r'[a-zA-Z]', text))
        urdu_chars = len(re.findall(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF]', text))
        pashto_specific = len(re.findall(r'[\u0671\u067E\u0686\u0693\u069A\u06AB\u06AF\u06CC]', text))
        pashto_chars = urdu_chars  # Pashto uses Arabic script, so count overlaps
        other_chars = len(re.findall(r'[^a-zA-Z\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF]', text))
        
        total_chars = len(text)
        if total_chars == 0:
            profile.language_mix = LanguageMix.UNKNOWN
            profile.language_confidence = 0.1
            return
        
        # Calculate percentages
        english_pct = english_chars / total_chars
        urdu_pct = urdu_chars / total_chars
        pashto_pct = pashto_specific / total_chars  # Use specific characters for Pashto detection
        other_pct = other_chars / total_chars
        
        # Determine language mix with thresholds
        thresholds = self.config.LANGUAGE_THRESHOLDS
        
        profile.language_confidence = 0.7  # Base confidence
        
        if english_pct > thresholds['dominant_language']:
            profile.language_mix = LanguageMix.ENGLISH_ONLY
            profile.language_confidence = 0.9
        elif urdu_pct > thresholds['dominant_language'] and pashto_pct < 0.05:
            profile.language_mix = LanguageMix.URDU_ONLY
            profile.language_confidence = 0.9
        elif pashto_pct > thresholds['dominant_language']:
            profile.language_mix = LanguageMix.PASHTO_ONLY
            profile.language_confidence = 0.8
        elif english_pct > thresholds['mixed_language'] and urdu_pct > thresholds['bilingual']:
            profile.language_mix = LanguageMix.ENGLISH_URDU
            profile.needs_language_separation = True
            profile.language_confidence = 0.7
        elif english_pct > thresholds['mixed_language'] and pashto_pct > thresholds['bilingual']:
            profile.language_mix = LanguageMix.ENGLISH_PASHTO
            profile.needs_language_separation = True
            profile.language_confidence = 0.6
        elif urdu_pct > thresholds['mixed_language'] and pashto_pct > thresholds['bilingual']:
            profile.language_mix = LanguageMix.URDU_PASHTO
            profile.needs_language_separation = True
            profile.language_confidence = 0.6
        elif english_pct > thresholds['bilingual'] and urdu_pct > thresholds['bilingual'] and pashto_pct > thresholds['bilingual']:
            profile.language_mix = LanguageMix.TRILINGUAL
            profile.needs_language_separation = True
            profile.language_confidence = 0.5
        else:
            profile.language_mix = LanguageMix.MIXED
            profile.needs_language_separation = True
            profile.language_confidence = 0.4
        
        # Add language tags
        profile.tags.append(f"lang_{profile.language_mix.value}")
        
        # Add detailed language percentages
        profile.add_quality_indicator('english_percentage', english_pct)
        profile.add_quality_indicator('urdu_percentage', urdu_pct)
        profile.add_quality_indicator('pashto_percentage', pashto_pct)
        profile.add_quality_indicator('other_percentage', other_pct)
    
    def _assess_quality(self, profile: DocumentProfile, text: Optional[str]):
        """Assess the quality of the document with enhanced metrics"""
        quality_score = 0.0
        max_score = 12.0  # Increased for more factors
        
        if not text:
            profile.quality = DocumentQuality.UNREADABLE
            profile.overall_quality_score = 0.0
            profile.add_processing_warning("No text available for quality assessment")
            return
        
        # 1. Text length and density (max 2 points)
        if len(text) > 2000:
            quality_score += 2
            profile.add_quality_indicator('text_length', 1.0)
        elif len(text) > 1000:
            quality_score += 1.5
            profile.add_quality_indicator('text_length', 0.75)
        elif len(text) > 500:
            quality_score += 1
            profile.add_quality_indicator('text_length', 0.5)
        elif len(text) > 100:
            quality_score += 0.5
            profile.add_quality_indicator('text_length', 0.25)
        
        # Word density (words per character)
        word_density = profile.total_words / len(text) if len(text) > 0 else 0
        if 0.15 < word_density < 0.25:  # Good density range
            quality_score += 0.5
        profile.add_quality_indicator('word_density', word_density)
        
        # 2. OCR confidence from metadata (max 2 points)
        if profile.ocr_confidence > 0.9:
            quality_score += 2
        elif profile.ocr_confidence > 0.7:
            quality_score += 1.5
        elif profile.ocr_confidence > 0.5:
            quality_score += 1
        elif profile.ocr_confidence > 0:
            quality_score += 0.5
        
        # 3. Structure detection (max 2 points)
        structure_count = 0
        for pattern in self.patterns.STRUCTURE_PATTERNS:
            if re.search(pattern, text, re.MULTILINE):
                structure_count += 1
        
        structure_score = min(structure_count / 5.0, 1.0)  # Normalize to 0-1
        profile.structure_score = structure_score
        
        if structure_score > 0.8:
            quality_score += 2
        elif structure_score > 0.6:
            quality_score += 1.5
        elif structure_score > 0.4:
            quality_score += 1
        elif structure_score > 0.2:
            quality_score += 0.5
        
        # 4. Language clarity and consistency (max 2 points)
        if profile.language_mix in [LanguageMix.ENGLISH_ONLY, LanguageMix.URDU_ONLY, LanguageMix.PASHTO_ONLY]:
            quality_score += 2
            profile.add_quality_indicator('language_consistency', 1.0)
        elif profile.language_mix in [LanguageMix.ENGLISH_URDU, LanguageMix.ENGLISH_PASHTO]:
            quality_score += 1
            profile.needs_language_separation = True
            profile.add_quality_indicator('language_consistency', 0.5)
        else:
            profile.needs_language_separation = True
            profile.add_quality_indicator('language_consistency', 0.2)
        
        # 5. Error detection (max 2 points)
        error_count = 0
        for pattern in self.patterns.OCR_ERROR_INDICATORS:
            error_count += len(re.findall(pattern, text))
        
        error_rate = error_count / len(text) if len(text) > 0 else 0
        profile.add_quality_indicator('error_rate', error_rate)
        
        if error_rate < 0.005:  # 0.5%
            quality_score += 2
        elif error_rate < 0.01:  # 1%
            quality_score += 1.5
        elif error_rate < 0.02:  # 2%
            quality_score += 1
        elif error_rate < 0.05:  # 5%
            quality_score += 0.5
        else:
            profile.needs_ocr_correction = True
        
        # 6. Readability metrics (max 2 points)
        readability_score = self._calculate_readability(text)
        profile.readability_score = readability_score
        profile.add_quality_indicator('readability', readability_score)
        
        if readability_score > 0.7:
            quality_score += 2
        elif readability_score > 0.5:
            quality_score += 1.5
        elif readability_score > 0.3:
            quality_score += 1
        elif readability_score > 0.1:
            quality_score += 0.5
        
        # Calculate overall quality score (0-1)
        profile.overall_quality_score = quality_score / max_score
        
        # Determine quality level based on configurable thresholds
        thresholds = self.config.QUALITY_THRESHOLDS
        
        if profile.overall_quality_score >= thresholds['excellent']:
            profile.quality = DocumentQuality.EXCELLENT
        elif profile.overall_quality_score >= thresholds['good']:
            profile.quality = DocumentQuality.GOOD
        elif profile.overall_quality_score >= thresholds['fair']:
            profile.quality = DocumentQuality.FAIR
            profile.needs_manual_review = True
        elif profile.overall_quality_score >= thresholds['poor']:
            profile.quality = DocumentQuality.POOR
            profile.needs_manual_review = True
        else:
            profile.quality = DocumentQuality.UNREADABLE
            profile.needs_manual_review = True
        
        # Log abstention if quality is poor
        if profile.quality in [DocumentQuality.POOR, DocumentQuality.UNREADABLE]:
            reason = f"Document quality too low: {profile.quality.value} (score: {profile.overall_quality_score:.2f})"
            self._log_abstention_if_enabled(
                profile,
                "poor_ocr_quality",
                reason,
                confidence=profile.overall_quality_score
            )
        
        profile.add_processing_note(f"Quality assessed as {profile.quality.value} (score: {profile.overall_quality_score:.2f})")
    
    def _calculate_readability(self, text: str) -> float:
        """Calculate readability score (simplified)"""
        if not text or len(text) < 100:
            return 0.5
        
        try:
            # Simple readability metrics
            sentences = re.split(r'[.!?۔؟]+', text)
            sentences = [s.strip() for s in sentences if s.strip()]
            
            words = re.findall(r'\b\w+\b', text)
            
            if len(sentences) == 0 or len(words) == 0:
                return 0.5
            
            avg_sentence_length = len(words) / len(sentences)
            
            # Calculate word length complexity
            long_words = sum(1 for word in words if len(word) > 6)
            long_word_ratio = long_words / len(words) if len(words) > 0 else 0
            
            # Normalize to 0-1 (lower is better for legal documents)
            # Legal documents tend to have longer sentences and words
            sentence_score = 1.0 - min(avg_sentence_length / 50.0, 1.0)  # Cap at 50 words/sentence
            word_score = 1.0 - min(long_word_ratio / 0.5, 1.0)  # Cap at 50% long words
            
            readability = (sentence_score + word_score) / 2.0
            
            return max(0.1, min(1.0, readability))
            
        except Exception:
            return 0.5
    
    def _extract_dates_and_numbers(self, profile: DocumentProfile, text: Optional[str]):
        """Extract dates and document numbers with enhanced parsing"""
        if not text:
            return
        
        # Extract all dates with context
        dates_found = []
        for pattern in self.patterns.DATE_PATTERNS:
            matches = re.findall(pattern, text)
            dates_found.extend(matches)
        
        # Try to parse dates with context analysis
        parsed_dates = []
        for date_str in dates_found[:10]:  # Limit to first 10 dates
            try:
                date_obj = self._parse_date(date_str)
                if date_obj:
                    parsed_dates.append(date_obj)
            except Exception:
                continue
        
        profile.all_dates = parsed_dates
        
        # Try to determine specific dates based on context
        if parsed_dates:
            # Sort dates chronologically
            parsed_dates.sort()
            
            # First date might be creation date
            profile.creation_date = parsed_dates[0]
            
            # Look for effective date indicators
            effective_indicators = [
                r'(?i)effective\s+(?:date|from|since)[:\s]*([\d/\\-]+)',
                r'(?i)نافذ\s+(?:ہونے\s+کی\s+تاریخ|تاریخ)[:\s]*([\d/\\-]+)',
                r'(?i)dated[:\s]*([\d/\\-]+)',
            ]
            
            for indicator in effective_indicators:
                matches = re.search(indicator, text)
                if matches:
                    date_str = matches.group(1)
                    date_obj = self._parse_date(date_str)
                    if date_obj:
                        profile.effective_date = date_obj
                        break
            
            # If no effective date found, use the most recent date
            if not profile.effective_date and len(parsed_dates) > 1:
                profile.effective_date = parsed_dates[-1]
            
            # Look for amendment dates
            amendment_contexts = [
                r'(?i)amended\s+on[:\s]*([\d/\\-]+)',
                r'(?i)ترمیم\s+تاریخ[:\s]*([\d/\\-]+)',
                r'(?i)S\.R\.O\.\s+.*?([\d/\\-]+)',
            ]
            
            for context in amendment_contexts:
                for match in re.finditer(context, text):
                    date_str = match.group(1)
                    date_obj = self._parse_date(date_str)
                    if date_obj and date_obj not in profile.amendment_dates:
                        profile.amendment_dates.append(date_obj)
        
        # Extract document numbers with enhanced patterns
        for pattern in self.patterns.DOCUMENT_NUMBER_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                number = match.group(1)
                if number and len(number) <= 50:  # Sanity check
                    if not profile.document_number:
                        profile.document_number = number
                    
                    # Try to categorize the number
                    if re.search(r'(?i)circular', pattern) or 'سرکلر' in pattern:
                        profile.circular_number = number
                    elif re.search(r'(?i)f\.?i\.?r', pattern):
                        profile.fir_number = number
                    elif re.search(r'(?i)s\.?r\.?o', pattern, re.IGNORECASE):
                        profile.gazette_number = number
                    elif re.search(r'(?i)permit', pattern):
                        profile.permit_number = number
                    elif re.search(r'(?i)license', pattern):
                        profile.license_number = number
                    elif re.search(r'(?i)report', pattern):
                        profile.report_number = number
        
        # Count amendment references
        if text:
            amendment_refs = re.findall(r'(?i)amendment\s+(?:no\.?)?\s*(\w+)', text)
            amendment_refs += re.findall(r'(?i)ترمیم\s+(?:نمبر)?\s*(\w+)', text)
            profile.amendment_references = list(set(amendment_refs))
            profile.amendment_count = len(profile.amendment_references)
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string with multiple format attempts"""
        date_formats = [
            '%d-%m-%Y', '%d/%m/%Y', '%d.%m.%Y',
            '%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d',
            '%d-%b-%Y', '%d/%b/%Y', '%d %b %Y',
            '%d-%B-%Y', '%d/%B/%Y', '%d %B %Y',
            '%Y',  # Just year
        ]
        
        # Clean the date string
        date_str = date_str.strip()
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        # Try Urdu month names
        urdu_months = {
            'جنوری': 'Jan', 'فروری': 'Feb', 'مارچ': 'Mar',
            'اپریل': 'Apr', 'مئی': 'May', 'جون': 'Jun',
            'جولائی': 'Jul', 'اگست': 'Aug', 'ستمبر': 'Sep',
            'اکتوبر': 'Oct', 'نومبر': 'Nov', 'دسمبر': 'Dec',
        }
        
        for urdu_month, eng_month in urdu_months.items():
            if urdu_month in date_str:
                date_str = date_str.replace(urdu_month, eng_month)
                for fmt in ['%d %b %Y', '%d-%b-%Y', '%d/%b/%Y']:
                    try:
                        return datetime.strptime(date_str, fmt)
                    except ValueError:
                        continue
        
        return None
    
    def _analyze_content_features(self, profile: DocumentProfile, text: Optional[str]):
        """Analyze specific content features with enhanced detection"""
        if not text:
            return
        
        # Check for amendments with context
        amendment_count = 0
        amendment_contexts = []
        
        for pattern in self.patterns.AMENDMENT_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            amendment_count += len(matches)
            for match in matches:
                if isinstance(match, str) and len(match) > 5:
                    amendment_contexts.append(match[:100])  # Store context
        
        if amendment_count > 0:
            profile.contains_amendments = True
            profile.amendment_count = amendment_count
            profile.tags.append('has_amendments')
            profile.add_processing_note(f"Found {amendment_count} amendment references")
        
        # Check for tables (enhanced detection)
        table_indicators = [
            (r'\|\s*[\w\s]+\s*\|', 2.0),  # Pipe tables
            (r'\+[-]+\+', 1.5),  # ASCII tables
            (r'(?i)table\s+\d+[:.]', 3.0),  # Table references with punctuation
            (r'جدول\s+\d+', 3.0),  # Urdu table references
            (r'(?i)\s{5,}[\w\s]{10,}\s{5,}[\w\s]{10,}', 1.0),  # Tabular alignment
        ]
        
        table_score = 0
        for pattern, weight in table_indicators:
            if re.search(pattern, text):
                table_score += weight
        
        if table_score >= 2.0:
            profile.has_tables = True
            profile.needs_table_extraction = True
            profile.tags.append('has_tables')
            profile.add_quality_indicator('table_score', min(table_score / 5.0, 1.0))
        
        # Check for figures
        figure_indicators = [
            r'(?i)figure\s+\d+[:.]',
            r'شکل\s+\d+',
            r'(?i)graph\s+\d+',
            r'گراف',
        ]
        
        for indicator in figure_indicators:
            if re.search(indicator, text):
                profile.has_figures = True
                profile.needs_figure_extraction = True
                profile.tags.append('has_figures')
                break
        
        # Check for forms
        form_indicators = [
            (r'(?i)form\s+[A-Z0-9]+', 2.0),
            (r'فارم\s+[A-Z0-9]+', 2.0),
            (r'(?i)application\s+form', 1.5),
            (r'درخواست\s+فارم', 1.5),
            (r'نام:\s*\n.*?\n', 1.0),  # Form-like structure
            (r'تاریخ:\s*\n.*?\n', 1.0),
        ]
        
        form_score = 0
        for pattern, weight in form_indicators:
            if re.search(pattern, text):
                form_score += weight
        
        if form_score >= 2.0:
            profile.has_forms = True
            profile.needs_form_extraction = True
            profile.tags.append('has_forms')
        
        # Check for signatures and stamps
        signature_indicators = [
            r'(?i)signature\s*:',
            r'(?i)signed\s+by',
            r'دستخط',
            r'مہر\s*:',
            r'(?i)stamp',
            r'(?i)seal',
        ]
        
        for indicator in signature_indicators:
            if re.search(indicator, text):
                profile.has_signatures = True
                profile.tags.append('has_signatures')
                break
        
        # Check for attachments
        attachment_indicators = [
            r'(?i)attachment\s+\d+',
            r'(?i)annex\s+\w+',
            r'منسلکہ',
            r'ضمیمہ',
        ]
        
        for indicator in attachment_indicators:
            if re.search(indicator, text):
                profile.has_attachments = True
                profile.tags.append('has_attachments')
                break
    
    def _extract_additional_info(self, profile: DocumentProfile, text: Optional[str]):
        """Extract additional information from document"""
        if not text:
            return
        
        # Extract issuing authority
        authority_patterns = [
            r'(?i)issued\s+by\s+([A-Z][\w\s&,]+?(?:Department|Division|Office|Section))',
            r'(?i)جاری\s+شدہ\s+بذریعہ\s+([\u0600-\u06FF\s]+)',
            r'(?i)Director\s+General\s+[^,\n]+',
            r'(?i)ڈائریکٹر\s+جنرل\s+[^,\n]+',
        ]
        
        for pattern in authority_patterns:
            match = re.search(pattern, text)
            if match:
                profile.issuing_authority = match.group(1).strip()
                break
        
        # Extract source department if not already set
        if not profile.source_department:
            dept_patterns = [
                r'(?i)Forest\s+Department',
                r'جنگلات\s+محکمہ',
                r'(?i)Wildlife\s+Department',
                r'وحشِیات\s+محکمہ',
            ]
            
            for pattern in dept_patterns:
                if re.search(pattern, text):
                    profile.source_department = pattern.replace('(?i)', '').replace('\\', '').strip()
                    break
        
        # Extract recipients
        recipient_patterns = [
            r'(?i)to\s*:\s*([^.\n]+)',
            r'بذریعہ\s*:\s*([^.\n]+)',
            r'(?i)copy\s+to\s*:\s*([^.\n]+)',
        ]
        
        for pattern in recipient_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if isinstance(match, str):
                    recipients = [r.strip() for r in match.split(',')]
                    profile.recipients.extend(recipients)
        
        # Remove duplicates
        profile.recipients = list(set(profile.recipients))
    
    def _calculate_scores_and_flags(self, profile: DocumentProfile):
        """Calculate final scores and set processing flags with enhanced logic"""
        # Calculate completeness score
        completeness_factors = []
        weights = [1.0, 0.8, 0.6, 0.4]  # Weight factors by importance
        
        if profile.document_type:
            completeness_factors.append(weights[0])
        
        if profile.jurisdiction and profile.jurisdiction != JurisdictionType.UNKNOWN:
            completeness_factors.append(weights[1])
        
        if profile.quality:
            completeness_factors.append(weights[2])
        
        if profile.total_words > 100:
            completeness_factors.append(weights[3])
        elif profile.total_words > 50:
            completeness_factors.append(weights[3] * 0.5)
        
        if completeness_factors:
            profile.completeness_score = sum(completeness_factors) / sum(weights)
        else:
            profile.completeness_score = 0.0
        
        # Calculate overall extraction confidence
        confidence_factors = [
            (profile.classification_confidence, 0.3),
            (profile.overall_quality_score, 0.3),
            (profile.completeness_score, 0.2),
            (profile.jurisdiction_confidence, 0.1),
            (profile.language_confidence, 0.1),
        ]
        
        weighted_sum = sum(score * weight for score, weight in confidence_factors)
        total_weight = sum(weight for _, weight in confidence_factors)
        
        profile.extraction_confidence = weighted_sum / total_weight if total_weight > 0 else 0.0
        
        # Set processing priority
        profile.priority = profile.calculate_priority()
        
        # Set manual review flag based on multiple factors
        review_factors = []
        
        if profile.extraction_confidence < self.config.CONFIDENCE_THRESHOLDS['low_confidence']:
            review_factors.append(("Low extraction confidence", 3.0))
        
        if profile.quality in [DocumentQuality.POOR, DocumentQuality.UNREADABLE]:
            review_factors.append(("Poor quality", 3.0))
        
        if profile.needs_ocr_correction and profile.ocr_confidence < 0.3:
            review_factors.append(("Low OCR confidence", 2.0))
        
        if profile.language_mix in [LanguageMix.MIXED, LanguageMix.TRILINGUAL]:
            review_factors.append(("Complex language mix", 1.5))
        
        if profile.contains_amendments and profile.amendment_count > 5:
            review_factors.append(("Many amendments", 1.0))
        
        # Calculate review need score
        review_score = sum(weight for _, weight in review_factors)
        profile.needs_manual_review = review_score >= 3.0
        
        if profile.needs_manual_review and review_factors:
            reasons = [reason for reason, _ in review_factors]
            profile.add_processing_note(f"Manual review needed due to: {', '.join(reasons[:3])}")
        
        # Log abstention if extraction confidence is low
        abstention_threshold = self.config.CONFIDENCE_THRESHOLDS['abstention_threshold']
        if profile.extraction_confidence < abstention_threshold:
            reason = f"Low extraction confidence: {profile.extraction_confidence:.2f} (threshold: {abstention_threshold})"
            self._log_abstention_if_enabled(
                profile,
                "low_confidence_extraction",
                reason,
                confidence=profile.extraction_confidence
            )
    
    def _log_abstention_if_enabled(self, 
                                  profile: DocumentProfile,
                                  abstention_type_str: str,
                                  reason: str,
                                  confidence: float,
                                  threshold: Optional[float] = None):
        """Log an abstention if logging is enabled with enhanced error handling"""
        if not self.enable_abstention_logging or not ABSTENTION_AVAILABLE:
            profile.add_processing_note(f"Abstention would be logged: {abstention_type_str} - {reason}")
            return
        
        try:
            abstention_type = getattr(AbstentionType, abstention_type_str.upper(), AbstentionType.OTHER)
            
            abstention_id = log_quick_abstention(
                abstention_type=abstention_type_str,
                reason=reason,
                module_name="doc_profiler.py",
                confidence=confidence,
                threshold=threshold or self.config.CONFIDENCE_THRESHOLDS['abstention_threshold'],
                document=profile.document_path,
                affected_entities=list(profile.unique_entities),
                tags=profile.tags,
                profile_data=profile.to_dict()
            )
            
            if abstention_id:
                profile.add_abstention(abstention_id, reason)
                self.stats['abstentions_logged'] += 1
                profile.add_processing_note(f"Logged abstention: {abstention_id} - {reason}")
                
        except Exception as e:
            profile.add_processing_warning(f"Failed to log abstention: {str(e)}")
            self.logger.warning(f"Failed to log abstention: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get profiling statistics with enhanced metrics"""
        stats = self.stats.copy()
        
        # Calculate percentages and rates
        if stats['documents_processed'] > 0:
            stats['kpk_percentage'] = (stats['kpk_documents'] / stats['documents_processed']) * 100
            stats['hazara_percentage'] = (stats['hazara_documents'] / stats['documents_processed']) * 100
            stats['malakand_percentage'] = (stats['malakand_documents'] / stats['documents_processed']) * 100
            stats['processable_percentage'] = (stats['processable_documents'] / stats['documents_processed']) * 100
            stats['abstention_rate'] = (stats['abstentions_logged'] / stats['documents_processed']) * 100
            
            # Average processing time in milliseconds
            stats['average_processing_time_ms'] = stats['average_processing_time'] * 1000
            
            # Success rate
            success_rate = (stats['documents_processed'] - len([v for v in self.stats.values() if isinstance(v, dict) and 'error' in str(v).lower()])) / stats['documents_processed'] * 100
            stats['success_rate'] = success_rate
        else:
            stats['kpk_percentage'] = 0
            stats['hazara_percentage'] = 0
            stats['malakand_percentage'] = 0
            stats['processable_percentage'] = 0
            stats['abstention_rate'] = 0
            stats['average_processing_time_ms'] = 0
            stats['success_rate'] = 0
        
        # Add histogram data for document types
        if stats['by_type']:
            stats['type_distribution'] = {
                'labels': list(stats['by_type'].keys()),
                'values': list(stats['by_type'].values())
            }
        
        # Add histogram data for quality levels
        if stats['by_quality']:
            stats['quality_distribution'] = {
                'labels': list(stats['by_quality'].keys()),
                'values': list(stats['by_quality'].values())
            }
        
        return stats
    
    def batch_profile(self, 
                     document_paths: List[Union[str, Path]],
                     progress_callback = None,
                     max_workers: int = 1) -> Dict[str, DocumentProfile]:
        """Profile multiple documents with optional parallel processing"""
        profiles = {}
        
        total_docs = len(document_paths)
        
        if max_workers > 1 and total_docs > 10:
            # Use parallel processing for large batches
            import concurrent.futures
            from concurrent.futures import ThreadPoolExecutor
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_path = {
                    executor.submit(self.profile_document, doc_path): doc_path 
                    for doc_path in document_paths
                }
                
                for i, future in enumerate(concurrent.futures.as_completed(future_to_path)):
                    doc_path = future_to_path[future]
                    try:
                        profile = future.result()
                        profiles[str(doc_path)] = profile
                        
                        if progress_callback:
                            progress = (i + 1) / total_docs * 100
                            progress_callback(progress, doc_path, profile)
                            
                    except Exception as e:
                        # Create minimal profile for failed documents
                        error_profile = DocumentProfile(doc_path, self.config)
                        error_profile.document_type = DocumentType.OTHER
                        error_profile.quality = DocumentQuality.UNREADABLE
                        error_profile.needs_manual_review = True
                        error_profile.add_processing_error(f"Profiling failed: {str(e)}")
                        profiles[str(doc_path)] = error_profile
                        
                        self.logger.error(f"Failed to profile {doc_path}: {e}")
                        
                        if progress_callback:
                            progress = (i + 1) / total_docs * 100
                            progress_callback(progress, doc_path, error_profile)
        else:
            # Sequential processing for small batches
            for i, doc_path in enumerate(document_paths):
                try:
                    profile = self.profile_document(document_path=doc_path)
                    profiles[str(doc_path)] = profile
                    
                    if progress_callback:
                        progress = (i + 1) / total_docs * 100
                        progress_callback(progress, doc_path, profile)
                        
                except Exception as e:
                    # Create minimal profile for failed documents
                    error_profile = DocumentProfile(doc_path, self.config)
                    error_profile.document_type = DocumentType.OTHER
                    error_profile.quality = DocumentQuality.UNREADABLE
                    error_profile.needs_manual_review = True
                    error_profile.add_processing_error(f"Profiling failed: {str(e)}")
                    profiles[str(doc_path)] = error_profile
                    
                    self.logger.error(f"Failed to profile {doc_path}: {e}")
                    
                    if progress_callback:
                        progress = (i + 1) / total_docs * 100
                        progress_callback(progress, doc_path, error_profile)
        
        return profiles
    
    def export_profiles(self, 
                       profiles: Dict[str, DocumentProfile],
                       output_dir: Union[str, Path],
                       format: str = "json",
                       include_summary: bool = True) -> Dict[str, List[str]]:
        """Export profiles to files with multiple formats"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        exported_files = {
            'profiles': [],
            'summary': [],
            'statistics': []
        }
        
        # Export individual profiles
        for doc_path, profile in profiles.items():
            try:
                filename = Path(doc_path).stem if doc_path else profile.profile_id
                safe_filename = re.sub(r'[^\w\-_]', '_', filename)
                
                if format == "json":
                    output_file = output_dir / f"{safe_filename}_profile.json"
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(profile.to_json())
                    exported_files['profiles'].append(str(output_file))
                
                elif format == "csv":
                    # Convert to CSV format
                    import csv
                    output_file = output_dir / f"{safe_filename}_profile.csv"
                    data = profile.to_dict()
                    
                    # Flatten nested structures
                    flat_data = {}
                    for key, value in data.items():
                        if isinstance(value, (list, dict)):
                            flat_data[key] = json.dumps(value, ensure_ascii=False)
                        else:
                            flat_data[key] = value
                    
                    with open(output_file, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.DictWriter(f, fieldnames=flat_data.keys())
                        writer.writeheader()
                        writer.writerow(flat_data)
                    
                    exported_files['profiles'].append(str(output_file))
                
                # Export summary if requested
                if include_summary:
                    summary_file = output_dir / f"{safe_filename}_summary.txt"
                    with open(summary_file, 'w', encoding='utf-8') as f:
                        f.write(profile.to_summary())
                    exported_files['summary'].append(str(summary_file))
                
            except Exception as e:
                self.logger.error(f"Failed to export profile for {doc_path}: {e}")
        
        # Export batch statistics
        if profiles:
            stats_file = output_dir / "batch_statistics.json"
            batch_stats = self._calculate_batch_statistics(profiles)
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(batch_stats, f, indent=2, ensure_ascii=False, default=str)
            exported_files['statistics'].append(str(stats_file))
        
        return exported_files
    
    def _calculate_batch_statistics(self, profiles: Dict[str, DocumentProfile]) -> Dict[str, Any]:
        """Calculate statistics for a batch of profiles"""
        batch_stats = {
            'total_documents': len(profiles),
            'processable_documents': 0,
            'average_confidence': 0.0,
            'document_types': {},
            'quality_distribution': {},
            'jurisdiction_distribution': {},
            'language_distribution': {},
            'priority_distribution': {},
        }
        
        confidence_sum = 0.0
        processable_count = 0
        
        for profile in profiles.values():
            # Processability
            processable, _, confidence = profile.is_processable()
            if processable:
                processable_count += 1
            
            confidence_sum += profile.extraction_confidence
            
            # Document types
            doc_type = profile.document_type.value if profile.document_type else 'unknown'
            batch_stats['document_types'][doc_type] = batch_stats['document_types'].get(doc_type, 0) + 1
            
            # Quality distribution
            quality = profile.quality.value if profile.quality else 'unknown'
            batch_stats['quality_distribution'][quality] = batch_stats['quality_distribution'].get(quality, 0) + 1
            
            # Jurisdiction distribution
            jurisdiction = profile.jurisdiction.value if profile.jurisdiction else 'unknown'
            batch_stats['jurisdiction_distribution'][jurisdiction] = batch_stats['jurisdiction_distribution'].get(jurisdiction, 0) + 1
            
            # Language distribution
            language = profile.language_mix.value if profile.language_mix else 'unknown'
            batch_stats['language_distribution'][language] = batch_stats['language_distribution'].get(language, 0) + 1
            
            # Priority distribution
            priority_label = 'critical' if profile.priority == 1 else 'high' if profile.priority == 2 else 'medium' if profile.priority == 3 else 'low'
            batch_stats['priority_distribution'][priority_label] = batch_stats['priority_distribution'].get(priority_label, 0) + 1
        
        # Calculate averages
        if profiles:
            batch_stats['processable_documents'] = processable_count
            batch_stats['processable_percentage'] = (processable_count / len(profiles)) * 100
            batch_stats['average_confidence'] = confidence_sum / len(profiles)
        
        return batch_stats


# ============================================================================
# QUICK PROFILING FUNCTIONS (ENHANCED)
# ============================================================================

def quick_profile_document(document_path: Union[str, Path], 
                          extracted_text: Optional[str] = None,
                          config: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Quick profiling function for single documents with enhanced output
    
    Returns:
        Dictionary with key profiling information
    """
    profiler_config = DocProfilerConfig()
    if config:
        for key, value in config.items():
            if hasattr(profiler_config, key):
                setattr(profiler_config, key, value)
    
    profiler = KPKDocumentProfiler(
        config=profiler_config,
        enable_abstention_logging=False,
        enable_spacy=False,
        logger=logging.getLogger(__name__)
    )
    
    profile = profiler.profile_document(
        document_path=document_path, 
        extracted_text=extracted_text,
        extract_entities=False  # Faster for quick profiling
    )
    
    # Return enhanced profile summary
    processable, reason, confidence = profile.is_processable()
    
    return {
        'profile_id': profile.profile_id,
        'filename': profile.filename,
        'document_type': profile.document_type.value if profile.document_type else 'unknown',
        'jurisdiction': profile.jurisdiction.value if profile.jurisdiction else 'unknown',
        'quality': profile.quality.value if profile.quality else 'unknown',
        'language_mix': profile.language_mix.value if profile.language_mix else 'unknown',
        'is_kpk': profile.is_kpk,
        'is_hazara': profile.is_hazara,
        'is_malakand': profile.is_malakand,
        'total_words': profile.total_words,
        'total_pages': profile.total_pages,
        'extraction_confidence': round(profile.extraction_confidence, 3),
        'overall_quality_score': round(profile.overall_quality_score, 3),
        'needs_manual_review': profile.needs_manual_review,
        'needs_ocr_correction': profile.needs_ocr_correction,
        'needs_language_separation': profile.needs_language_separation,
        'priority': profile.priority,
        'priority_label': 'critical' if profile.priority == 1 else 'high' if profile.priority == 2 else 'medium' if profile.priority == 3 else 'low',
        'is_processable': processable,
        'processability_reason': reason,
        'processability_confidence': round(confidence, 3),
        'tags': profile.tags[:10],  # First 10 tags
        'recommended_phases': profile.get_recommended_phases(),
        'processing_requirements': profile.get_processing_requirements(),
    }


def profile_document_from_text(text: str, 
                              filename: str = "unknown.txt",
                              config: Optional[Dict] = None) -> DocumentProfile:
    """
    Create a document profile directly from text
    
    Useful for testing or when documents are already extracted
    """
    profiler_config = DocProfilerConfig()
    if config:
        for key, value in config.items():
            if hasattr(profiler_config, key):
                setattr(profiler_config, key, value)
    
    profiler = KPKDocumentProfiler(
        config=profiler_config,
        enable_abstention_logging=False
    )
    
    return profiler.profile_document(
        document_path=filename,
        extracted_text=text,
        extract_entities=True
    )


# ============================================================================
# EXAMPLE USAGE AND TESTING
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("GREENLAWAI-KPK ENHANCED DOCUMENT PROFILER")
    print("=" * 80)
    
    # Configure logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Create profiler with enhanced configuration
    profiler_config = {
        'QUALITY_THRESHOLDS': {
            'excellent': 0.85,
            'good': 0.65,
            'fair': 0.45,
            'poor': 0.25,
        },
        'CONFIDENCE_THRESHOLDS': {
            'high_confidence': 0.75,
            'medium_confidence': 0.55,
            'low_confidence': 0.35,
            'abstention_threshold': 0.45,
        },
    }
    
    try:
        profiler = KPKDocumentProfiler(
            config=profiler_config,
            enable_abstention_logging=True,
            enable_spacy=True,
            logger=logging.getLogger(__name__)
        )
        print("Profiler initialized with enhanced configuration")
    except Exception as e:
        print(f"Warning: Could not initialize with enhanced config: {e}")
        profiler = KPKDocumentProfiler(enable_abstention_logging=False)
    
    # Example 1: Profile a KPK Forest Ordinance document (enhanced)
    print("\n" + "=" * 80)
    print("1. ENHANCED EXAMPLE: KPK Forest Ordinance Document")
    print("=" * 80)
    
    example_text = """
    THE KHYBER PAKHTUNKHWA FOREST ORDINANCE, 2002
    (KPK Ord. No. VII of 2002)
    
    Section 27: Penalties for unauthorized felling
    
    (1) Any person who fells any tree in a reserved forest without permission 
    shall be punishable with imprisonment which may extend to three years, 
    or with fine which may extend to fifty thousand rupees, or with both.
    
    (2) The provisions of this section shall apply to all forests in the 
    Malakand and Hazara Divisions.
    
    Amended by S.R.O. No. 123(I)/2015 dated 15th January, 2015.
    Further amended by Notification No. 456/Forest dated 2023-06-30.
    
    Table 1: Fine structure for different violations
    
    | Violation Type | Minimum Fine | Maximum Fine | Imprisonment |
    |----------------|--------------|--------------|--------------|
    | Unauthorized felling | Rs. 10,000 | Rs. 50,000 | 1-3 years |
    | Firewood collection | Rs. 5,000 | Rs. 20,000 | 6 months |
    | Grazing violation | Rs. 2,000 | Rs. 10,000 | 3 months |
    
    Form 7: Application for Timber Transit Permit
    
    Subject: Implementation of new penalty structure
    Distribution: All Divisional Forest Officers
    
    This document supersedes Circular No. 34/2001.
    
    Reference: Hazara Forest Act, 1912 and Malakand Forest Regulation, 1975.
    """
    
    profile1 = profiler.profile_document(
        document_path="/documents/KPK_Forest_Ordinance_2002_Amended.pdf",
        extracted_text=example_text
    )
    
    print(profile1.to_summary())
    
    # Example 2: Profile a Hazara-specific document (enhanced)
    print("\n" + "=" * 80)
    print("2. ENHANCED EXAMPLE: Hazara Forest Act Document")
    print("=" * 80)
    
    example_text2 = """
    HAZARA FOREST ACT, 1912
    (Act No. IV of 1912)
    
    فصل 15: تحفظ جنگلات ہزارہ
    
    کوئی شخص بغیر اجازت کے ہزارہ ڈویژن کے کسی بھی جنگل میں درخت نہیں کاٹ سکتا۔
    
    جرمانہ: تیس ہزار روپے یا تین ماہ قید یا دونوں۔
    
    یہ قانون ایبٹ آباد، مانسہرہ، ہری پور، اور باتگرام اضلاع پر لاگو ہوتا ہے۔
    
    ترمیم: نوٹیفیکیشن نمبر 89/2020 مورخہ 2020-08-15
    مزید ترمیم: حوالہ خط نمبر 123/فارنسٹ مورخہ 2023-03-10
    
    ایف آئی آر نمبر: 123/2024
    تھانہ: ایبٹ آباد
    تاریخ: 2024-01-15
    
    منسلکہ: ضلع وار جنگلات کا رقبہ
    """
    
    profile2 = profiler.profile_document(
        document_path="/documents/Hazara_Forest_Act_1912_Amended.pdf",
        extracted_text=example_text2
    )
    
    print(profile2.to_summary())
    
    # Example 3: Quick profiling with enhanced output
    print("\n" + "=" * 80)
    print("3. ENHANCED QUICK PROFILING EXAMPLE:")
    print("=" * 80)
    
    quick_profile = quick_profile_document(
        document_path="/documents/circular_2023.pdf",
        extracted_text="Departmental Circular No. 45/Forest dated 2023-06-15\nSubject: New guidelines for forest fire prevention\nDistribution: All Range Officers",
        config={'ENTITY_EXTRACTION': {'use_spacy': False}}
    )
    
    for key, value in quick_profile.items():
        if isinstance(value, list):
            print(f"   {key}: {', '.join(map(str, value[:5]))}{'...' if len(value) > 5 else ''}")
        else:
            print(f"   {key}: {value}")
    
    # Example 4: Profile from text only
    print("\n" + "=" * 80)
    print("4. PROFILE FROM TEXT ONLY:")
    print("=" * 80)
    
    text_profile = profile_document_from_text(
        text="Malakand Forest Working Plan 2023-2028\nCompartment No. 45: Chir Pine Forest\nArea: 125 hectares\n",
        filename="working_plan_2023.txt"
    )
    
    print(f"   Document Type: {text_profile.document_type.value if text_profile.document_type else 'Unknown'}")
    print(f"   Is Malakand: {text_profile.is_malakand}")
    print(f"   Has Tables: {text_profile.has_tables}")
    print(f"   Entities Found: {len(text_profile.unique_entities)}")
    
    # Show enhanced statistics
    print("\n" + "=" * 80)
    print("5. ENHANCED PROFILER STATISTICS:")
    print("=" * 80)
    
    stats = profiler.get_statistics()
    print(f"   Documents Processed: {stats['documents_processed']}")
    print(f"   KPK Documents: {stats['kpk_documents']} ({stats['kpk_percentage']:.1f}%)")
    print(f"   Hazara Documents: {stats['hazara_documents']} ({stats['hazara_percentage']:.1f}%)")
    print(f"   Malakand Documents: {stats['malakand_documents']} ({stats['malakand_percentage']:.1f}%)")
    print(f"   Processable Documents: {stats['processable_documents']} ({stats['processable_percentage']:.1f}%)")
    print(f"   Abstentions Logged: {stats['abstentions_logged']} ({stats['abstention_rate']:.1f}%)")
    print(f"   Average Processing Time: {stats['average_processing_time_ms']:.0f} ms")
    print(f"   Success Rate: {stats['success_rate']:.1f}%")
    
    # Document type distribution
    if stats.get('type_distribution'):
        print(f"\n   Document Type Distribution:")
        for doc_type, count in stats['by_type'].items():
            percentage = (count / stats['documents_processed']) * 100
            print(f"     - {doc_type}: {count} ({percentage:.1f}%)")
    
    print("\n" + "=" * 80)
    print("ENHANCED DOCUMENT PROFILER READY FOR KPK FORESTRY DOCUMENTS")
    print("=" * 80)
