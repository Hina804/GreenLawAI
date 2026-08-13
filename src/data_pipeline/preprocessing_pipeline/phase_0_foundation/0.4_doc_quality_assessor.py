"""
DOC_QUALITY_ASSESSOR.PY - Phase 0.4: Document Quality Assessment
Assesses document quality before processing with KPK-specific intelligence.
This runs AFTER profiling and metadata enrichment, BEFORE Phase 1 extraction.
Author: Hina Ali, Eman Irfan
Date: January 29, 2026
"""

import re
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Set, Union
from dataclasses import dataclass, asdict, field
from enum import Enum
import hashlib
import mimetypes
from collections import defaultdict, Counter
import statistics

# Import from common modules
try:
    from preprocessing_pipeline.common.config import PipelineConfig, QualityAssessmentConfig
    from preprocessing_pipeline.common.constants import *
    USE_COMMON_CONFIG = True
except ImportError:
    USE_COMMON_CONFIG = False
    print("Warning: common.config not found. Using default configuration.")

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

class QualityAssessmentConfig:
    """Configuration for document quality assessment"""
    
    # Quality thresholds (0-1 scale)
    QUALITY_THRESHOLDS = {
        'excellent': 0.85,
        'good': 0.70,
        'fair': 0.50,
        'poor': 0.30,
        'unacceptable': 0.0,
    }
    
    # Processing decision thresholds
    PROCESSING_DECISIONS = {
        'auto_process': 0.70,      # Automatically process
        'auto_clean_then_process': 0.50,  # Auto-clean then process
        'manual_review_needed': 0.30,     # Requires human review
        'reject': 0.10,            # Cannot be processed
    }
    
    # Quality factor weights (sum to 1.0)
    QUALITY_WEIGHTS = {
        'readability': 0.25,       # Text clarity and structure
        'completeness': 0.20,      # Missing pages/sections
        'technical_quality': 0.20,  # Scan quality, OCR errors
        'kpk_specificity': 0.15,   # KPK relevance and completeness
        'legal_validity': 0.10,    # Document validity and currency
        'metadata_quality': 0.10,   # Metadata completeness
    }
    
    # KPK-specific quality factors
    KPK_QUALITY_FACTORS = {
        'division_specificity': 0.3,    # Clear KPK division mentioned
        'jurisdiction_clarity': 0.25,   # Clear jurisdictional boundaries
        'legal_references': 0.20,       # References KPK laws/ordinances
        'language_appropriateness': 0.15,  # Appropriate language for KPK
        'geographic_specificity': 0.10,  # Specific locations mentioned
    }
    
    # Readability assessment parameters
    READABILITY_PARAMS = {
        'min_words_per_sentence': 5,
        'max_words_per_sentence': 50,
        'ideal_words_per_sentence': 20,
        'min_sentence_length': 10,
        'max_sentence_length': 1000,
        'ideal_sentence_length': 150,
        'acceptable_ocr_error_rate': 0.05,  # 5% OCR errors acceptable
        'max_consecutive_errors': 3,
    }
    
    # Technical quality parameters
    TECHNICAL_PARAMS = {
        'min_dpi': 150,           # Minimum DPI for scanned documents
        'min_ocr_confidence': 0.70,
        'max_image_skew_angle': 5.0,  # Degrees
        'acceptable_noise_level': 0.10,  # Image noise threshold
        'min_text_density': 0.10,  # Minimum text vs whitespace ratio
    }
    
    # File-specific parameters
    FILE_PARAMS = {
        'max_file_size_mb': 100,
        'supported_formats': ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt'],
        'supported_image_formats': ['.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp'],
        'encrypted_file_penalty': 0.3,  # Penalty for encrypted files
        'corrupted_file_threshold': 0.1,  # Probability file is corrupted
    }
    
    # Issue severity scoring
    ISSUE_SEVERITY = {
        'critical': {'weight': 1.0, 'description': 'Prevents processing'},
        'high': {'weight': 0.7, 'description': 'Significant impact on quality'},
        'medium': {'weight': 0.4, 'description': 'Moderate impact on quality'},
        'low': {'weight': 0.1, 'description': 'Minor quality issue'},
        'info': {'weight': 0.0, 'description': 'Informational only'},
    }

# ============================================================================
# ENUMERATIONS
# ============================================================================

class QualityCategory(Enum):
    """Document quality categories"""
    EXCELLENT = "excellent"        # Perfect for processing
    GOOD = "good"                  # Minor issues, fully processable
    FAIR = "fair"                  # Issues present, requires cleaning
    POOR = "poor"                  # Significant issues, manual review needed
    UNACCEPTABLE = "unacceptable"  # Cannot be processed
    
    @classmethod
    def from_score(cls, score: float) -> 'QualityCategory':
        """Convert quality score to category"""
        if score >= 0.85:
            return cls.EXCELLENT
        elif score >= 0.70:
            return cls.GOOD
        elif score >= 0.50:
            return cls.FAIR
        elif score >= 0.30:
            return cls.POOR
        else:
            return cls.UNACCEPTABLE

class ProcessingDecision(Enum):
    """Processing decisions based on quality assessment"""
    AUTO_PROCESS = "auto_process"                 # Process automatically
    AUTO_CLEAN_THEN_PROCESS = "auto_clean_then_process"  # Clean then process
    MANUAL_REVIEW_NEEDED = "manual_review_needed" # Human review required
    EXPERT_REVIEW_NEEDED = "expert_review_needed" # KPK expert review needed
    REJECT = "reject"                            # Cannot be processed
    DEFER = "defer"                              # Defer for later processing

class IssueType(Enum):
    """Types of quality issues"""
    # Technical Issues
    LOW_OCR_CONFIDENCE = "low_ocr_confidence"
    POOR_SCAN_QUALITY = "poor_scan_quality"
    IMAGE_SKEW = "image_skew"
    HIGH_NOISE_LEVEL = "high_noise_level"
    CORRUPTED_FILE = "corrupted_file"
    ENCRYPTED_FILE = "encrypted_file"
    UNSUPPORTED_FORMAT = "unsupported_format"
    LARGE_FILE_SIZE = "large_file_size"
    
    # Text Issues
    HIGH_OCR_ERROR_RATE = "high_ocr_error_rate"
    LOW_TEXT_DENSITY = "low_text_density"
    POOR_READABILITY = "poor_readability"
    INCOMPLETE_TEXT = "incomplete_text"
    GARBLED_TEXT = "garbled_text"
    MISSING_PAGES = "missing_pages"
    DUPLICATE_CONTENT = "duplicate_content"
    
    # Structural Issues
    MISSING_SECTIONS = "missing_sections"
    POOR_DOCUMENT_STRUCTURE = "poor_document_structure"
    INCONSISTENT_FORMATTING = "inconsistent_formatting"
    BROKEN_TABLES = "broken_tables"
    MISSING_FIGURES = "missing_figures"
    
    # Language Issues
    MIXED_LANGUAGES = "mixed_languages"
    POOR_TRANSLATION = "poor_translation"
    UNKNOWN_SCRIPT = "unknown_script"
    LANGUAGE_CONFUSION = "language_confusion"
    
    # KPK-specific Issues
    UNCLEAR_JURISDICTION = "unclear_jurisdiction"
    MISSING_KPK_REFERENCES = "missing_kpk_references"
    VAGUE_GEOGRAPHIC_INFO = "vague_geographic_info"
    OUTDATED_KPK_LAW = "outdated_kpk_law"
    CONFLICTING_AUTHORITIES = "conflicting_authorities"
    HAZARA_SPECIFIC_ISSUE = "hazara_specific_issue"
    MALAKAND_SPECIFIC_ISSUE = "malakand_specific_issue"
    
    # Legal Issues
    EXPIRED_DOCUMENT = "expired_document"
    SUPERSEDED_DOCUMENT = "superseded_document"
    LEGAL_CONFLICT = "legal_conflict"
    AMBIGUOUS_LEGAL_TERMS = "ambiguous_legal_terms"
    
    # Metadata Issues
    INCOMPLETE_METADATA = "incomplete_metadata"
    INCONSISTENT_METADATA = "inconsistent_metadata"
    MISSING_DATES = "missing_dates"
    UNCLEAR_AUTHORSHIP = "unclear_authorship"
    
    # Other Issues
    LOW_CONFIDENCE_EXTRACTION = "low_confidence_extraction"
    INSUFFICIENT_CONTEXT = "insufficient_context"
    POTENTIAL_PII = "potential_pii"
    WATERMARK_INTERFERENCE = "watermark_interference"

class AssessmentStage(Enum):
    """Stages of quality assessment"""
    PRE_PROCESSING = "pre_processing"        # Before any processing
    POST_EXTRACTION = "post_extraction"      # After text extraction
    POST_CLEANING = "post_cleaning"          # After text cleaning
    POST_ANALYSIS = "post_analysis"          # After content analysis
    FINAL_VALIDATION = "final_validation"    # Final quality check

# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class QualityIssue:
    """Detailed quality issue"""
    issue_type: IssueType
    severity: str  # critical, high, medium, low, info
    description: str
    location: Optional[str] = None  # e.g., "page 15", "section 3.2"
    context: Optional[Dict[str, Any]] = None
    confidence: float = 1.0
    suggested_fix: Optional[str] = None
    fix_priority: int = 3  # 1=urgent, 2=high, 3=medium, 4=low
    detected_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['issue_type'] = self.issue_type.value
        data['detected_at'] = self.detected_at.isoformat()
        return data
    
    @property
    def severity_weight(self) -> float:
        """Get severity weight for scoring"""
        severity_weights = {
            'critical': 1.0,
            'high': 0.7,
            'medium': 0.4,
            'low': 0.1,
            'info': 0.0,
        }
        return severity_weights.get(self.severity, 0.0)

@dataclass
class QualityMetric:
    """Individual quality metric"""
    name: str
    score: float  # 0-1
    weight: float  # Contribution to overall score
    description: str
    details: Optional[Dict[str, Any]] = None
    threshold: Optional[float] = None
    passed: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        return data

@dataclass
class QualityAssessment:
    """Complete quality assessment"""
    # Identification
    assessment_id: str
    document_path: str
    assessment_stage: AssessmentStage
    assessed_at: datetime
    
    # Quality scores
    overall_quality_score: float  # 0-1
    quality_category: QualityCategory
    processing_decision: ProcessingDecision
    
    # Detailed metrics
    metrics: Dict[str, QualityMetric]  # metric_name -> QualityMetric
    issues: List[QualityIssue]
    
    # Breakdown scores
    readability_score: float
    completeness_score: float
    technical_score: float
    kpk_specificity_score: float
    legal_validity_score: float
    metadata_score: float
    
    # KPK-specific assessment
    kpk_relevance_score: float
    kpk_division_specificity: float
    kpk_jurisdiction_clarity: float
    kpk_legal_references_score: float
    
    # Recommendations
    recommended_actions: List[Dict[str, Any]]
    priority_actions: List[str]
    estimated_processing_time: Optional[float] = None  # minutes
    
    # Statistics
    total_issues: int = 0
    critical_issues: int = 0
    high_issues: int = 0
    medium_issues: int = 0
    low_issues: int = 0
    
    # Metadata
    assessor_version: str = "GreenLawAI-KPK Quality Assessor v2.1"
    notes: Optional[str] = None
    
    def __post_init__(self):
        """Calculate derived fields"""
        self.total_issues = len(self.issues)
        self.critical_issues = sum(1 for i in self.issues if i.severity == 'critical')
        self.high_issues = sum(1 for i in self.issues if i.severity == 'high')
        self.medium_issues = sum(1 for i in self.issues if i.severity == 'medium')
        self.low_issues = sum(1 for i in self.issues if i.severity == 'low')
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        
        # Convert enums to strings
        data['quality_category'] = self.quality_category.value
        data['processing_decision'] = self.processing_decision.value
        data['assessment_stage'] = self.assessment_stage.value
        
        # Convert metrics and issues
        data['metrics'] = {k: v.to_dict() for k, v in self.metrics.items()}
        data['issues'] = [i.to_dict() for i in self.issues]
        
        # Convert datetime
        data['assessed_at'] = self.assessed_at.isoformat()
        
        return data
    
    def to_summary(self) -> Dict[str, Any]:
        """Get summary of assessment"""
        return {
            'assessment_id': self.assessment_id,
            'document_path': self.document_path,
            'overall_quality_score': round(self.overall_quality_score, 3),
            'quality_category': self.quality_category.value,
            'processing_decision': self.processing_decision.value,
            'total_issues': self.total_issues,
            'critical_issues': self.critical_issues,
            'kpk_relevance_score': round(self.kpk_relevance_score, 3),
            'recommended_actions_count': len(self.recommended_actions),
            'priority_actions': self.priority_actions,
        }
    
    def get_quality_report(self) -> str:
        """Generate human-readable quality report"""
        report = f"""
        ========================================
        DOCUMENT QUALITY ASSESSMENT REPORT
        ========================================
        
        Document: {Path(self.document_path).name}
        Assessment ID: {self.assessment_id}
        Assessment Time: {self.assessed_at.strftime('%Y-%m-%d %H:%M:%S')}
        Assessor Version: {self.assessor_version}
        
        OVERALL ASSESSMENT:
        - Quality Score: {self.overall_quality_score:.2%}
        - Quality Category: {self.quality_category.value.upper()}
        - Processing Decision: {self.processing_decision.value.replace('_', ' ').upper()}
        - KPK Relevance: {self.kpk_relevance_score:.2%}
        
        DETAILED SCORES:
        - Readability: {self.readability_score:.2%}
        - Completeness: {self.completeness_score:.2%}
        - Technical Quality: {self.technical_score:.2%}
        - KPK Specificity: {self.kpk_specificity_score:.2%}
        - Legal Validity: {self.legal_validity_score:.2%}
        - Metadata Quality: {self.metadata_score:.2%}
        
        ISSUE SUMMARY:
        - Total Issues: {self.total_issues}
        - Critical: {self.critical_issues}
        - High: {self.high_issues}
        - Medium: {self.medium_issues}
        - Low: {self.low_issues}
        
        KPK-SPECIFIC ASSESSMENT:
        - Division Specificity: {self.kpk_division_specificity:.2%}
        - Jurisdiction Clarity: {self.kpk_jurisdiction_clarity:.2%}
        - Legal References: {self.kpk_legal_references_score:.2%}
        
        RECOMMENDATIONS:
        {chr(10).join(f'  - {action}' for action in self.priority_actions[:5])}
        
        ESTIMATED PROCESSING TIME: {self.estimated_processing_time or 'N/A'} minutes
        
        ========================================
        """
        return report

# ============================================================================
# QUALITY ASSESSOR
# ============================================================================

class DocQualityAssessor:
    """
    Phase 0.4: Document Quality Assessment
    Assesses document quality before processing with KPK-specific intelligence.
    """
    
    def __init__(self, 
                 config: Optional[Union[QualityAssessmentConfig, Dict]] = None,
                 enable_abstention_logging: bool = True,
                 logger: Optional[logging.Logger] = None):
        """
        Initialize document quality assessor.
        
        Args:
            config: Configuration object or dictionary
            enable_abstention_logging: Whether to log abstentions for low-quality docs
            logger: Optional logger instance
        """
        
        # Configuration (orchestrator may pass PipelineConfig — use phase-specific config)
        if isinstance(config, QualityAssessmentConfig):
            self.config = config
        elif isinstance(config, dict):
            self.config = QualityAssessmentConfig()
            for key, value in config.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
        else:
            self.config = QualityAssessmentConfig()
        
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
        
        # Statistics
        self.stats = self._init_statistics()
        
        # Compile patterns for efficiency
        self._compile_patterns()
        
        # Cache for document analysis
        self._cache = {}
        
        self.logger.info("DocQualityAssessor initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging"""
        logger = logging.getLogger('DocQualityAssessor')
        logger.setLevel(logging.INFO)
        
        # Clear existing handlers
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
            'documents_assessed': 0,
            'assessment_time_total': 0.0,
            'avg_assessment_time': 0.0,
            
            'by_quality_category': {
                cat.value: 0 for cat in QualityCategory
            },
            'by_processing_decision': {
                dec.value: 0 for dec in ProcessingDecision
            },
            
            'total_issues_found': 0,
            'issues_by_type': defaultdict(int),
            'issues_by_severity': defaultdict(int),
            
            'avg_quality_score': 0.0,
            'avg_kpk_relevance': 0.0,
            
            'kpk_documents': 0,
            'hazara_documents': 0,
            'malakand_documents': 0,
            
            'auto_processed': 0,
            'manual_review_needed': 0,
            'rejected': 0,
            
            'performance_metrics': {
                'fastest_assessment': float('inf'),
                'slowest_assessment': 0.0,
                'assessment_times': [],
            },
        }
    
    def _compile_patterns(self):
        """Compile regex patterns for efficiency"""
        # OCR error patterns
        self.ocr_error_patterns = [
            re.compile(r'[l1I|]'),      # Common OCR confusions
            re.compile(r'[o0O]'),       # Zero vs O
            re.compile(r'[5S]'),        # Five vs S
            re.compile(r'[8B]'),        # Eight vs B
            re.compile(r'[nm]{3,}'),    # Multiple n/m confusions
            re.compile(r'\b\w\b'),      # Single character words (often errors)
        ]
        
        # Legal reference patterns (KPK-specific)
        self.kpk_legal_patterns = [
            re.compile(r'(?i)kpk\s+forest', re.IGNORECASE),
            re.compile(r'(?i)khyber\s+pakhtunkhwa', re.IGNORECASE),
            re.compile(r'(?i)hazara\s+forest', re.IGNORECASE),
            re.compile(r'(?i)malakand\s+forest', re.IGNORECASE),
            re.compile(r'(?i)ordinance\s+(?:no\.?\s*)?\d{4}', re.IGNORECASE),
            re.compile(r'(?i)act\s+(?:no\.?\s*)?\d{4}', re.IGNORECASE),
            re.compile(r'(?i)s\.?r\.?o\.?\s+\d+', re.IGNORECASE),  # SRO references
        ]
        
        # KPK division patterns
        self.kpk_division_patterns = {
            'hazara': re.compile(r'(?i)\b(?:hazara|abbottabad|mansehra|haripur|battagram|torghar)\b', re.IGNORECASE),
            'malakand': re.compile(r'(?i)\b(?:malakand|swat|dir|chitral|buner|shangla)\b', re.IGNORECASE),
            'peshawar': re.compile(r'(?i)\b(?:peshawar|charsadda|nowshera)\b', re.IGNORECASE),
            'kohat': re.compile(r'(?i)\b(?:kohat|hangu|karak)\b', re.IGNORECASE),
            'bannu': re.compile(r'(?i)\b(?:bannu|lakki\s+marwat)\b', re.IGNORECASE),
            'dera': re.compile(r'(?i)\b(?:dera\s+ismail\s+khan|tank)\b', re.IGNORECASE),
        }
        
        # Date patterns for validity checking
        self.date_patterns = [
            re.compile(r'\b\d{1,2}[-/]\d{1,2}[-/]\d{4}\b'),
            re.compile(r'\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b'),
            re.compile(r'\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]* \d{1,2},? \d{4}\b', re.IGNORECASE),
            re.compile(r'\b\d{1,2} (?:جنوری|فروری|مارچ|اپریل|مئی|جون|جولائی|اگست|ستمبر|اکتوبر|نومبر|دسمبر) \d{4}\b'),
        ]
        
        # Structure patterns
        self.structure_patterns = [
            re.compile(r'^\s*(?:section|article|clause)\s+\d+', re.MULTILINE | re.IGNORECASE),
            re.compile(r'^\s*\d+\.\s+\w+', re.MULTILINE),  # Numbered list
            re.compile(r'^\s*[•\-*]\s+\w+', re.MULTILINE),  # Bulleted list
            re.compile(r'^\s*(?:table|figure)\s+\d+[:.]', re.MULTILINE | re.IGNORECASE),
        ]
    
    def assess_quality(self,
                        document_path: Union[str, Path],
                        profile: Optional[DocumentProfile] = None,
                        extracted_text: Optional[str] = None,
                        metadata: Optional[Dict[str, Any]] = None,
                        stage: AssessmentStage = AssessmentStage.PRE_PROCESSING,
                        detailed_analysis: bool = True) -> QualityAssessment:
        """
        Perform comprehensive quality assessment of a document.
        
        Args:
            document_path: Path to the document
            profile: Optional document profile from doc_profiler.py
            extracted_text: Optional extracted text for analysis
            metadata: Optional metadata from kpk_metadata_enricher.py
            stage: Assessment stage (pre/post processing)
            detailed_analysis: Whether to perform detailed analysis
            
        Returns:
            QualityAssessment object with complete assessment
        """
        import time
        start_time = time.time()
        
        try:
            self.logger.info(f"Assessing document: {document_path}")
            
            # Generate assessment ID
            assessment_id = self._generate_assessment_id(document_path, stage)
            
            # Basic file checks
            file_metrics, file_issues = self._assess_file_quality(document_path)
            
            # Text analysis if text is available
            text_metrics, text_issues = self._assess_text_quality(extracted_text) if extracted_text else ({}, [])
            
            # Profile analysis if profile is available
            profile_metrics, profile_issues = self._assess_profile_quality(profile) if profile else ({}, [])
            
            # KPK-specific assessment
            kpk_metrics, kpk_issues = self._assess_kpk_quality(
                extracted_text, profile, metadata
            )
            
            # Legal validity assessment
            legal_metrics, legal_issues = self._assess_legal_validity(
                extracted_text, profile, metadata
            )
            
            # Structural assessment
            structural_metrics, structural_issues = self._assess_structure_quality(
                extracted_text
            ) if extracted_text and detailed_analysis else ({}, [])
            
            # Combine all metrics and issues
            all_metrics = {}
            all_metrics.update(file_metrics)
            all_metrics.update(text_metrics)
            all_metrics.update(profile_metrics)
            all_metrics.update(kpk_metrics)
            all_metrics.update(legal_metrics)
            all_metrics.update(structural_metrics)
            
            all_issues = []
            all_issues.extend(file_issues)
            all_issues.extend(text_issues)
            all_issues.extend(profile_issues)
            all_issues.extend(kpk_issues)
            all_issues.extend(legal_issues)
            all_issues.extend(structural_issues)
            
            # Calculate overall scores
            overall_score = self._calculate_overall_score(all_metrics)
            quality_category = QualityCategory.from_score(overall_score)
            
            # Calculate component scores
            component_scores = self._calculate_component_scores(all_metrics)
            
            # Determine processing decision
            processing_decision = self._determine_processing_decision(
                overall_score, all_issues, component_scores
            )
            
            # Generate recommendations
            recommendations, priority_actions = self._generate_recommendations(
                all_issues, component_scores, processing_decision
            )
            
            # Estimate processing time
            estimated_time = self._estimate_processing_time(
                overall_score, len(all_issues), processing_decision
            )
            
            # Create assessment
            assessment = QualityAssessment(
                assessment_id=assessment_id,
                document_path=str(document_path),
                assessment_stage=stage,
                assessed_at=datetime.now(),
                
                overall_quality_score=overall_score,
                quality_category=quality_category,
                processing_decision=processing_decision,
                
                metrics=all_metrics,
                issues=all_issues,
                
                readability_score=component_scores.get('readability', 0),
                completeness_score=component_scores.get('completeness', 0),
                technical_score=component_scores.get('technical_quality', 0),
                kpk_specificity_score=component_scores.get('kpk_specificity', 0),
                legal_validity_score=component_scores.get('legal_validity', 0),
                metadata_score=component_scores.get('metadata_quality', 0),
                
                kpk_relevance_score=component_scores.get('kpk_relevance', 0),
                kpk_division_specificity=component_scores.get('kpk_division_specificity', 0),
                kpk_jurisdiction_clarity=component_scores.get('kpk_jurisdiction_clarity', 0),
                kpk_legal_references_score=component_scores.get('kpk_legal_references', 0),
                
                recommended_actions=recommendations,
                priority_actions=priority_actions,
                estimated_processing_time=estimated_time,
            )
            
            # Update statistics
            self._update_statistics(assessment, time.time() - start_time)
            
            # Log abstention if quality is poor
            if (self.enable_abstention_logging and self.abstention_logger and 
                overall_score < self.config.PROCESSING_DECISIONS['manual_review_needed']):
                
                self._log_quality_abstention(assessment, document_path)
            
            self.logger.info(
                f"Assessment complete for {document_path}: "
                f"Score={overall_score:.2%}, Category={quality_category.value}, "
                f"Decision={processing_decision.value}"
            )
            
            return assessment
            
        except Exception as e:
            self.logger.error(f"Error assessing document {document_path}: {e}", exc_info=True)
            
            # Return minimal assessment with error
            return self._create_error_assessment(document_path, str(e), stage)
    
    def _generate_assessment_id(self, document_path: Union[str, Path], stage: AssessmentStage) -> str:
        """Generate unique assessment ID"""
        doc_hash = hashlib.md5(str(document_path).encode()).hexdigest()[:8]
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        stage_code = stage.value[:3]
        
        return f"qa_{stage_code}_{timestamp}_{doc_hash}"
    
    def _assess_file_quality(self, document_path: Union[str, Path]) -> Tuple[Dict[str, QualityMetric], List[QualityIssue]]:
        """Assess file-level quality"""
        metrics = {}
        issues = []
        
        path = Path(document_path)
        
        # Check file existence
        if not path.exists():
            issue = QualityIssue(
                issue_type=IssueType.CORRUPTED_FILE,
                severity='critical',
                description=f"File does not exist: {document_path}",
                suggested_fix="Verify file path and permissions",
                fix_priority=1
            )
            issues.append(issue)
            
            metrics['file_existence'] = QualityMetric(
                name='file_existence',
                score=0.0,
                weight=0.05,
                description='File exists and is accessible',
                passed=False
            )
            return metrics, issues
        
        # Check file size
        try:
            file_size_mb = path.stat().st_size / (1024 * 1024)
            max_size = self.config.FILE_PARAMS['max_file_size_mb']
            
            if file_size_mb > max_size:
                issue = QualityIssue(
                    issue_type=IssueType.LARGE_FILE_SIZE,
                    severity='high',
                    description=f"File size ({file_size_mb:.1f} MB) exceeds maximum ({max_size} MB)",
                    suggested_fix="Consider splitting the document or compressing images",
                    fix_priority=2
                )
                issues.append(issue)
                size_score = max(0, 1 - (file_size_mb - max_size) / max_size)
            else:
                size_score = 1.0
            
            metrics['file_size'] = QualityMetric(
                name='file_size',
                score=size_score,
                weight=0.03,
                description='File size within acceptable limits',
                details={'size_mb': file_size_mb, 'max_mb': max_size},
                passed=size_score >= 0.8
            )
            
        except Exception as e:
            self.logger.warning(f"Could not check file size: {e}")
            metrics['file_size'] = QualityMetric(
                name='file_size',
                score=0.5,
                weight=0.03,
                description='File size check failed',
                passed=False
            )
        
        # Check file format
        file_ext = path.suffix.lower()
        supported = (self.config.FILE_PARAMS['supported_formats'] + 
                    self.config.FILE_PARAMS['supported_image_formats'])
        
        if file_ext in supported:
            format_score = 1.0
        elif file_ext in ['.pdf', '.doc', '.docx']:  # Preferred formats
            format_score = 0.9
        else:
            format_score = 0.3
            issue = QualityIssue(
                issue_type=IssueType.UNSUPPORTED_FORMAT,
                severity='high' if file_ext not in ['.txt', '.rtf'] else 'medium',
                description=f"File format '{file_ext}' may have limited support",
                suggested_fix="Convert to PDF or DOCX format for better processing",
                fix_priority=2
            )
            issues.append(issue)
        
        metrics['file_format'] = QualityMetric(
            name='file_format',
            score=format_score,
            weight=0.04,
            description='File format is supported',
            details={'extension': file_ext, 'supported': file_ext in supported},
            passed=format_score >= 0.7
        )
        
        # Check if file is encrypted (basic check)
        try:
            # Try to read first few bytes
            with open(path, 'rb') as f:
                header = f.read(100)
            
            # Simple encryption detection (not comprehensive)
            is_encrypted = False
            encrypted_indicators = [
                b'ENCRYPTED', b'%ANS', b'PK\x03\x04',  # Some encrypted indicators
            ]
            
            for indicator in encrypted_indicators:
                if indicator in header:
                    is_encrypted = True
                    break
            
            if is_encrypted:
                encryption_score = 0.3
                issue = QualityIssue(
                    issue_type=IssueType.ENCRYPTED_FILE,
                    severity='critical',
                    description="File appears to be encrypted",
                    suggested_fix="Decrypt the file before processing",
                    fix_priority=1
                )
                issues.append(issue)
            else:
                encryption_score = 1.0
            
            metrics['file_encryption'] = QualityMetric(
                name='file_encryption',
                score=encryption_score,
                weight=0.03,
                description='File is not encrypted',
                details={'is_encrypted': is_encrypted},
                passed=not is_encrypted
            )
            
        except Exception as e:
            self.logger.warning(f"Could not check file encryption: {e}")
            metrics['file_encryption'] = QualityMetric(
                name='file_encryption',
                score=0.5,
                weight=0.03,
                description='File encryption check failed',
                passed=False
            )
        
        return metrics, issues
    
    def _assess_text_quality(self, text: str) -> Tuple[Dict[str, QualityMetric], List[QualityIssue]]:
        """Assess text quality"""
        metrics = {}
        issues = []
        
        if not text or len(text.strip()) == 0:
            issue = QualityIssue(
                issue_type=IssueType.INCOMPLETE_TEXT,
                severity='critical',
                description="No text content found",
                suggested_fix="Check OCR settings or document format",
                fix_priority=1
            )
            issues.append(issue)
            
            metrics['text_presence'] = QualityMetric(
                name='text_presence',
                score=0.0,
                weight=0.10,
                description='Text content is present',
                passed=False
            )
            return metrics, issues
        
        text_length = len(text)
        
        # Text presence metric
        presence_score = 1.0 if text_length > 100 else text_length / 100
        metrics['text_presence'] = QualityMetric(
            name='text_presence',
            score=presence_score,
            weight=0.05,
            description='Adequate text content present',
            details={'text_length': text_length},
            passed=presence_score >= 0.5
        )
        
        # OCR error detection
        error_metrics = self._assess_ocr_errors(text)
        metrics.update(error_metrics['metrics'])
        issues.extend(error_metrics['issues'])
        
        # Readability assessment
        readability_metrics = self._assess_readability(text)
        metrics.update(readability_metrics['metrics'])
        issues.extend(readability_metrics['issues'])
        
        # Text density
        density_score = self._calculate_text_density(text)
        metrics['text_density'] = QualityMetric(
            name='text_density',
            score=density_score,
            weight=0.03,
            description='Text density is appropriate',
            details={'density_score': density_score},
            passed=density_score >= 0.7
        )
        
        if density_score < 0.5:
            issue = QualityIssue(
                issue_type=IssueType.LOW_TEXT_DENSITY,
                severity='medium',
                description=f"Low text density (score: {density_score:.2f})",
                suggested_fix="Check for excessive whitespace or formatting issues",
                fix_priority=3
            )
            issues.append(issue)
        
        # Language analysis
        language_metrics = self._assess_language_quality(text)
        metrics.update(language_metrics['metrics'])
        issues.extend(language_metrics['issues'])
        
        return metrics, issues
    
    def _assess_ocr_errors(self, text: str) -> Dict[str, Any]:
        """Assess OCR errors in text"""
        metrics = {}
        issues = []
        
        if not text:
            return {'metrics': metrics, 'issues': issues}
        
        # Count total characters
        total_chars = len(text)
        if total_chars == 0:
            return {'metrics': metrics, 'issues': issues}
        
        # Detect OCR errors
        error_count = 0
        error_details = {}
        
        for pattern in self.ocr_error_patterns:
            matches = pattern.findall(text)
            pattern_errors = len(matches)
            error_count += pattern_errors
            
            if pattern_errors > 0:
                pattern_name = pattern.pattern[:20]
                error_details[pattern_name] = pattern_errors
        
        # Calculate error rate
        error_rate = error_count / total_chars if total_chars > 0 else 0
        acceptable_rate = self.config.READABILITY_PARAMS['acceptable_ocr_error_rate']
        
        # Calculate score (1.0 = no errors, 0.0 = high error rate)
        if error_rate <= acceptable_rate:
            error_score = 1.0
        else:
            # Scale from acceptable_rate to 1.0 (worst case)
            error_score = max(0.0, 1.0 - (error_rate - acceptable_rate) / acceptable_rate)
        
        metrics['ocr_error_rate'] = QualityMetric(
            name='ocr_error_rate',
            score=error_score,
            weight=0.08,
            description='OCR error rate within acceptable limits',
            details={
                'error_count': error_count,
                'total_chars': total_chars,
                'error_rate': error_rate,
                'acceptable_rate': acceptable_rate,
                'error_details': error_details
            },
            passed=error_score >= 0.7
        )
        
        # Check for consecutive errors
        if error_count > 0:
            # Simple consecutive error detection
            lines = text.split('\n')
            consecutive_errors = 0
            max_consecutive = 0
            
            for line in lines:
                line_errors = sum(1 for _ in re.finditer(r'[l1I|o0O5S8B]', line))
                if line_errors > 0:
                    consecutive_errors += 1
                    max_consecutive = max(max_consecutive, consecutive_errors)
                else:
                    consecutive_errors = 0
            
            if max_consecutive > self.config.READABILITY_PARAMS['max_consecutive_errors']:
                issue = QualityIssue(
                    issue_type=IssueType.HIGH_OCR_ERROR_RATE,
                    severity='high',
                    description=f"High OCR error rate ({error_rate:.2%}) with consecutive errors",
                    suggested_fix="Apply OCR correction or use better quality scan",
                    fix_priority=2
                )
                issues.append(issue)
        
        # Check for garbled text (repeated patterns)
        garbled_score = self._detect_garbled_text(text)
        metrics['garbled_text'] = QualityMetric(
            name='garbled_text',
            score=garbled_score,
            weight=0.04,
            description='Text is not garbled or corrupted',
            details={'garbled_score': garbled_score},
            passed=garbled_score >= 0.8
        )
        
        if garbled_score < 0.6:
            issue = QualityIssue(
                issue_type=IssueType.GARBLED_TEXT,
                severity='high',
                description="Text appears garbled or corrupted",
                suggested_fix="Check OCR settings or scan quality",
                fix_priority=2
            )
            issues.append(issue)
        
        return {'metrics': metrics, 'issues': issues}
    
    def _detect_garbled_text(self, text: str) -> float:
        """Detect garbled or corrupted text"""
        if not text or len(text) < 100:
            return 1.0  # Not enough text to assess
        
        # Check for repeated nonsense patterns
        lines = text.split('\n')
        garbled_lines = 0
        
        for line in lines:
            if len(line) > 20:  # Only check longer lines
                # Check for excessive special characters
                special_chars = len(re.findall(r'[^a-zA-Z0-9\s\u0600-\u06FF]', line))
                special_ratio = special_chars / len(line) if len(line) > 0 else 0
                
                # Check for repeated character patterns
                repeated_patterns = len(re.findall(r'(.)\1{3,}', line))  # Same char 4+ times
                
                # Check for random capitalization
                words = line.split()
                if words:
                    random_caps = sum(1 for w in words if w.isupper() and len(w) > 3)
                    caps_ratio = random_caps / len(words)
                else:
                    caps_ratio = 0
                
                if (special_ratio > 0.3 or repeated_patterns > 2 or caps_ratio > 0.3):
                    garbled_lines += 1
        
        garbled_ratio = garbled_lines / len(lines) if lines else 0
        return max(0.0, 1.0 - garbled_ratio * 2)  # Penalize heavily for garbled text
    
    def _assess_readability(self, text: str) -> Dict[str, Any]:
        """Assess text readability"""
        metrics = {}
        issues = []
        
        if not text:
            metrics['readability'] = QualityMetric(
                name='readability',
                score=0.0,
                weight=self.config.QUALITY_WEIGHTS['readability'],
                description='Text readability score',
                passed=False
            )
            return {'metrics': metrics, 'issues': issues}
        
        # Split into sentences
        sentences = re.split(r'[.!?۔؟]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            readability_score = 0.3
            issue = QualityIssue(
                issue_type=IssueType.POOR_READABILITY,
                severity='medium',
                description="No proper sentences detected",
                suggested_fix="Check sentence boundaries or text structure",
                fix_priority=3
            )
            issues.append(issue)
        else:
            # Calculate sentence length statistics
            sentence_lengths = []
            word_counts = []
            
            for sentence in sentences:
                # Character length
                sentence_lengths.append(len(sentence))
                
                # Word count
                words = re.findall(r'\b\w+\b', sentence)
                word_counts.append(len(words))
            
            if sentence_lengths:
                avg_sentence_length = statistics.mean(sentence_lengths)
                avg_word_count = statistics.mean(word_counts) if word_counts else 0
                
                # Score based on ideal sentence length
                ideal_length = self.config.READABILITY_PARAMS['ideal_sentence_length']
                min_length = self.config.READABILITY_PARAMS['min_sentence_length']
                max_length = self.config.READABILITY_PARAMS['max_sentence_length']
                
                if avg_sentence_length < min_length:
                    length_score = avg_sentence_length / min_length
                elif avg_sentence_length > max_length:
                    length_score = max(0.0, 1.0 - (avg_sentence_length - max_length) / max_length)
                else:
                    # Bell curve around ideal length
                    deviation = abs(avg_sentence_length - ideal_length) / ideal_length
                    length_score = max(0.0, 1.0 - deviation)
                
                # Score based on word count per sentence
                ideal_words = self.config.READABILITY_PARAMS['ideal_words_per_sentence']
                min_words = self.config.READABILITY_PARAMS['min_words_per_sentence']
                max_words = self.config.READABILITY_PARAMS['max_words_per_sentence']
                
                if avg_word_count < min_words:
                    word_score = avg_word_count / min_words
                elif avg_word_count > max_words:
                    word_score = max(0.0, 1.0 - (avg_word_count - max_words) / max_words)
                else:
                    deviation = abs(avg_word_count - ideal_words) / ideal_words
                    word_score = max(0.0, 1.0 - deviation)
                
                # Combined readability score
                readability_score = (length_score + word_score) / 2
                
                # Check for issues
                if readability_score < 0.6:
                    issue = QualityIssue(
                        issue_type=IssueType.POOR_READABILITY,
                        severity='medium',
                        description=f"Poor readability (score: {readability_score:.2f})",
                        suggested_fix="Consider restructuring or simplifying text",
                        fix_priority=3
                    )
                    issues.append(issue)
            else:
                readability_score = 0.5
        
        metrics['readability'] = QualityMetric(
            name='readability',
            score=readability_score,
            weight=self.config.QUALITY_WEIGHTS['readability'],
            description='Text readability assessment',
            details={
                'sentence_count': len(sentences),
                'avg_sentence_length': avg_sentence_length if 'avg_sentence_length' in locals() else 0,
                'avg_word_count': avg_word_count if 'avg_word_count' in locals() else 0,
            },
            passed=readability_score >= 0.6
        )
        
        return {'metrics': metrics, 'issues': issues}
    
    def _calculate_text_density(self, text: str) -> float:
        """Calculate text density (text vs whitespace)"""
        if not text:
            return 0.0
        
        # Count non-whitespace characters
        non_whitespace = len(re.sub(r'\s', '', text))
        total_chars = len(text)
        
        if total_chars == 0:
            return 0.0
        
        density = non_whitespace / total_chars
        
        # Normalize to 0-1 score
        # Ideal density is around 0.7-0.8 for documents
        if density >= 0.7:
            return 1.0
        elif density >= 0.5:
            return 0.7 + (density - 0.5) * 1.5
        elif density >= 0.3:
            return 0.3 + (density - 0.3) * 2.0
        else:
            return density * 1.0
    
    def _assess_language_quality(self, text: str) -> Dict[str, Any]:
        """Assess language quality and issues"""
        metrics = {}
        issues = []
        
        if not text:
            return {'metrics': metrics, 'issues': issues}
        
        # Detect language mixing
        english_chars = len(re.findall(r'[a-zA-Z]', text))
        urdu_chars = len(re.findall(r'[\u0600-\u06FF]', text))
        other_chars = len(text) - english_chars - urdu_chars
        
        total_chars = len(text)
        if total_chars == 0:
            return {'metrics': metrics, 'issues': issues}
        
        english_ratio = english_chars / total_chars
        urdu_ratio = urdu_chars / total_chars
        
        # Language mixing score
        if english_ratio > 0.8:
            # Predominantly English
            mixing_score = 1.0
        elif urdu_ratio > 0.8:
            # Predominantly Urdu
            mixing_score = 0.9  # Slightly lower for Urdu-only (OCR may have issues)
        elif english_ratio > 0.3 and urdu_ratio > 0.3:
            # Mixed English-Urdu
            mixing_score = 0.7
        elif english_ratio > 0.1 or urdu_ratio > 0.1:
            # Some language content
            mixing_score = 0.5
        else:
            # Unknown script or mostly symbols
            mixing_score = 0.3
            issue = QualityIssue(
                issue_type=IssueType.UNKNOWN_SCRIPT,
                severity='high',
                description="Text contains mostly unknown script or symbols",
                suggested_fix="Check encoding or document format",
                fix_priority=2
            )
            issues.append(issue)
        
        metrics['language_mixing'] = QualityMetric(
            name='language_mixing',
            score=mixing_score,
            weight=0.05,
            description='Appropriate language mixing for KPK documents',
            details={
                'english_ratio': english_ratio,
                'urdu_ratio': urdu_ratio,
                'other_ratio': other_chars / total_chars,
            },
            passed=mixing_score >= 0.6
        )
        
        if mixing_score < 0.6:
            issue = QualityIssue(
                issue_type=IssueType.MIXED_LANGUAGES,
                severity='medium',
                description=f"Language mixing may cause confusion (score: {mixing_score:.2f})",
                suggested_fix="Consider separating language sections or improving OCR",
                fix_priority=3
            )
            issues.append(issue)
        
        # Check for language confusion (e.g., Urdu words in English text with wrong encoding)
        confusion_score = self._detect_language_confusion(text)
        metrics['language_confusion'] = QualityMetric(
            name='language_confusion',
            score=confusion_score,
            weight=0.03,
            description='No language encoding confusion',
            details={'confusion_score': confusion_score},
            passed=confusion_score >= 0.8
        )
        
        if confusion_score < 0.7:
            issue = QualityIssue(
                issue_type=IssueType.LANGUAGE_CONFUSION,
                severity='medium',
                description="Possible language encoding confusion detected",
                suggested_fix="Check text encoding and OCR language settings",
                fix_priority=3
            )
            issues.append(issue)
        
        return {'metrics': metrics, 'issues': issues}
    
    def _detect_language_confusion(self, text: str) -> float:
        """Detect language encoding confusion"""
        if not text or len(text) < 100:
            return 1.0
        
        # Check for common encoding issues
        # Urdu characters that might be mis-encoded as Latin
        urdu_latin_confusion = re.findall(r'[A-Za-z][\u0600-\u06FF]|[\u0600-\u06FF][A-Za-z]', text)
        
        # Check for garbled Urdu (common OCR issue)
        garbled_urdu = re.findall(r'[\u0600-\u06FF]{2,}[A-Za-z0-9]+[\u0600-\u06FF]{2,}', text)
        
        confusion_count = len(urdu_latin_confusion) + len(garbled_urdu)
        
        # Normalize by text length
        confusion_ratio = confusion_count / (len(text) / 100)  # per 100 characters
        
        if confusion_ratio == 0:
            return 1.0
        elif confusion_ratio < 1:
            return 0.9
        elif confusion_ratio < 3:
            return 0.7
        elif confusion_ratio < 5:
            return 0.5
        elif confusion_ratio < 10:
            return 0.3
        else:
            return 0.1
    
    def _assess_profile_quality(self, profile: DocumentProfile) -> Tuple[Dict[str, QualityMetric], List[QualityIssue]]:
        """Assess quality based on document profile"""
        metrics = {}
        issues = []
        
        if not profile:
            return metrics, issues
        
        try:
            # Extract scores from profile
            profile_dict = profile.to_dict() if hasattr(profile, 'to_dict') else {}
            
            # Overall quality from profiler
            profiler_quality = profile_dict.get('quality', 'unknown')
            profiler_score = profile_dict.get('overall_quality_score', 0.5)
            
            # Map profiler quality to our score
            quality_mapping = {
                'excellent': 0.9,
                'good': 0.7,
                'fair': 0.5,
                'poor': 0.3,
                'unreadable': 0.1,
            }
            
            if profiler_quality in quality_mapping:
                profile_score = quality_mapping[profiler_quality]
            else:
                profile_score = profiler_score
            
            metrics['profile_quality'] = QualityMetric(
                name='profile_quality',
                score=profile_score,
                weight=0.06,
                description='Document quality from profiler',
                details={'profiler_quality': profiler_quality, 'profiler_score': profiler_score},
                passed=profile_score >= 0.5
            )
            
            # Extraction confidence
            extraction_confidence = profile_dict.get('extraction_confidence', 0.5)
            metrics['extraction_confidence'] = QualityMetric(
                name='extraction_confidence',
                score=extraction_confidence,
                weight=0.04,
                description='Confidence in text extraction',
                details={'confidence': extraction_confidence},
                passed=extraction_confidence >= 0.6
            )
            
            if extraction_confidence < 0.4:
                issue = QualityIssue(
                    issue_type=IssueType.LOW_CONFIDENCE_EXTRACTION,
                    severity='medium',
                    description=f"Low extraction confidence ({extraction_confidence:.2%})",
                    suggested_fix="Review extraction parameters or document quality",
                    fix_priority=3
                )
                issues.append(issue)
            
            # Check if manual review is needed according to profiler
            needs_manual_review = profile_dict.get('needs_manual_review', False)
            if needs_manual_review:
                issue = QualityIssue(
                    issue_type=IssueType.POOR_READABILITY,
                    severity='high',
                    description="Document profiler flagged for manual review",
                    suggested_fix="Perform manual review before processing",
                    fix_priority=2
                )
                issues.append(issue)
            
            # Language mix from profile
            language_mix = profile_dict.get('language_mix', 'unknown')
            if language_mix in ['mixed', 'trilingual']:
                issue = QualityIssue(
                    issue_type=IssueType.MIXED_LANGUAGES,
                    severity='low',
                    description=f"Mixed language document ({language_mix})",
                    suggested_fix="Ensure proper language handling in pipeline",
                    fix_priority=4
                )
                issues.append(issue)
            
        except Exception as e:
            self.logger.warning(f"Error assessing profile quality: {e}")
        
        return metrics, issues
    
    def _assess_kpk_quality(self, 
                           text: Optional[str], 
                           profile: Optional[DocumentProfile],
                           metadata: Optional[Dict[str, Any]]) -> Tuple[Dict[str, QualityMetric], List[QualityIssue]]:
        """Assess KPK-specific quality factors"""
        metrics = {}
        issues = []
        
        # Initialize scores
        kpk_scores = {
            'division_specificity': 0.0,
            'jurisdiction_clarity': 0.0,
            'legal_references': 0.0,
            'language_appropriateness': 0.0,
            'geographic_specificity': 0.0,
        }
        
        # Check text for KPK references
        if text:
            # KPK legal references
            kpk_legal_count = 0
            for pattern in self.kpk_legal_patterns:
                matches = pattern.findall(text)
                kpk_legal_count += len(matches)
            
            if kpk_legal_count > 5:
                kpk_scores['legal_references'] = 1.0
            elif kpk_legal_count > 2:
                kpk_scores['legal_references'] = 0.7
            elif kpk_legal_count > 0:
                kpk_scores['legal_references'] = 0.4
            else:
                kpk_scores['legal_references'] = 0.1
                issue = QualityIssue(
                    issue_type=IssueType.MISSING_KPK_REFERENCES,
                    severity='medium',
                    description="No clear KPK legal references found",
                    suggested_fix="Verify document is KPK-related or add KPK context",
                    fix_priority=3
                )
                issues.append(issue)
            
            # KPK division specificity
            division_found = False
            for division_name, pattern in self.kpk_division_patterns.items():
                if pattern.search(text):
                    division_found = True
                    if division_name in ['hazara', 'malakand']:
                        # Higher score for specific divisions
                        kpk_scores['division_specificity'] = 0.9
                        kpk_scores['geographic_specificity'] = 0.8
                        
                        # Add division-specific issue if needed
                        if division_name == 'hazara':
                            issue = QualityIssue(
                                issue_type=IssueType.HAZARA_SPECIFIC_ISSUE,
                                severity='info',
                                description="Hazara-specific document detected",
                                suggested_fix="Apply Hazara-specific processing rules",
                                fix_priority=4
                            )
                        else:
                            issue = QualityIssue(
                                issue_type=IssueType.MALAKAND_SPECIFIC_ISSUE,
                                severity='info',
                                description="Malakand-specific document detected",
                                suggested_fix="Apply Malakand-specific processing rules",
                                fix_priority=4
                            )
                        issues.append(issue)
                    else:
                        kpk_scores['division_specificity'] = 0.7
                        kpk_scores['geographic_specificity'] = 0.6
                    break
            
            if not division_found:
                kpk_scores['division_specificity'] = 0.3
                kpk_scores['geographic_specificity'] = 0.2
                issue = QualityIssue(
                    issue_type=IssueType.VAGUE_GEOGRAPHIC_INFO,
                    severity='low',
                    description="No specific KPK division mentioned",
                    suggested_fix="Add geographic context if available",
                    fix_priority=4
                )
                issues.append(issue)
            
            # Jurisdiction clarity (look for jurisdiction terms)
            jurisdiction_terms = [
                r'jurisdiction', r'authority', r'competent',
                r'اختیار', r'دائرہ اختیار', r'صلاحیت',
            ]
            
            jurisdiction_count = 0
            for term in jurisdiction_terms:
                if re.search(term, text, re.IGNORECASE):
                    jurisdiction_count += 1
            
            if jurisdiction_count >= 3:
                kpk_scores['jurisdiction_clarity'] = 0.9
            elif jurisdiction_count >= 1:
                kpk_scores['jurisdiction_clarity'] = 0.6
            else:
                kpk_scores['jurisdiction_clarity'] = 0.3
                issue = QualityIssue(
                    issue_type=IssueType.UNCLEAR_JURISDICTION,
                    severity='medium',
                    description="Jurisdiction not clearly specified",
                    suggested_fix="Add jurisdiction information if available",
                    fix_priority=3
                )
                issues.append(issue)
        
        # Check metadata for KPK information
        if metadata:
            kpk_metadata = metadata.get('kpk_metadata', {})
            
            if kpk_metadata.get('is_kpk_jurisdiction', False):
                # Boost scores if KPK jurisdiction is confirmed
                for key in kpk_scores:
                    kpk_scores[key] = min(1.0, kpk_scores[key] + 0.2)
            
            if kpk_metadata.get('is_hazara', False):
                kpk_scores['division_specificity'] = max(kpk_scores['division_specificity'], 0.9)
                kpk_scores['geographic_specificity'] = max(kpk_scores['geographic_specificity'], 0.9)
            
            if kpk_metadata.get('is_malakand', False):
                kpk_scores['division_specificity'] = max(kpk_scores['division_specificity'], 0.9)
                kpk_scores['geographic_specificity'] = max(kpk_scores['geographic_specificity'], 0.9)
        
        # Create metrics
        for factor_name, score in kpk_scores.items():
            weight = self.config.KPK_QUALITY_FACTORS.get(factor_name, 0.1)
            
            metrics[f'kpk_{factor_name}'] = QualityMetric(
                name=f'kpk_{factor_name}',
                score=score,
                weight=weight,
                description=f'KPK {factor_name.replace("_", " ")}',
                details={'score': score},
                passed=score >= 0.5
            )
        
        # Calculate overall KPK relevance score
        kpk_relevance = sum(
            score * self.config.KPK_QUALITY_FACTORS.get(factor_name, 0.1)
            for factor_name, score in kpk_scores.items()
        )
        
        metrics['kpk_relevance'] = QualityMetric(
            name='kpk_relevance',
            score=kpk_relevance,
            weight=0.15,
            description='Overall KPK relevance and specificity',
            details={'relevance_score': kpk_relevance, 'component_scores': kpk_scores},
            passed=kpk_relevance >= 0.4
        )
        
        return metrics, issues
    
    def _assess_legal_validity(self, 
                              text: Optional[str],
                              profile: Optional[DocumentProfile],
                              metadata: Optional[Dict[str, Any]]) -> Tuple[Dict[str, QualityMetric], List[QualityIssue]]:
        """Assess legal validity of the document"""
        metrics = {}
        issues = []
        
        # Initialize scores
        validity_score = 0.7  # Default assumption
        currency_score = 0.7  # Default assumption
        
        # Check for dates in text
        if text:
            dates_found = []
            for pattern in self.date_patterns:
                matches = pattern.findall(text)
                dates_found.extend(matches)
            
            if dates_found:
                # Try to extract years
                years = []
                for date_str in dates_found[:10]:  # Check first 10 dates
                    year_match = re.search(r'\b(19\d{2}|20\d{2})\b', date_str)
                    if year_match:
                        years.append(int(year_match.group(1)))
                
                if years:
                    current_year = datetime.now().year
                    latest_year = max(years)
                    
                    # Calculate currency score based on age
                    age = current_year - latest_year
                    if age <= 2:
                        currency_score = 1.0
                    elif age <= 5:
                        currency_score = 0.8
                    elif age <= 10:
                        currency_score = 0.6
                    elif age <= 20:
                        currency_score = 0.4
                    elif age <= 50:
                        currency_score = 0.2
                    else:
                        currency_score = 0.1
                        
                        issue = QualityIssue(
                            issue_type=IssueType.OUTDATED_KPK_LAW,
                            severity='medium',
                            description=f"Document appears outdated (latest year: {latest_year})",
                            suggested_fix="Check if document is still valid or has been superseded",
                            fix_priority=3
                        )
                        issues.append(issue)
        
        # Check for legal conflict indicators
        if text:
            conflict_indicators = [
                r'notwithstanding',
                r'provided that',
                r'subject to',
                r'however',
                r'بشرطیکہ',
                r'تاہم',
                r'ماسوائے',
            ]
            
            conflict_count = 0
            for indicator in conflict_indicators:
                if re.search(indicator, text, re.IGNORECASE):
                    conflict_count += 1
            
            if conflict_count > 3:
                validity_score *= 0.8  # Reduce validity for potential conflicts
                issue = QualityIssue(
                    issue_type=IssueType.LEGAL_CONFLICT,
                    severity='medium',
                    description="Potential legal conflicts detected",
                    suggested_fix="Review document for conflicting provisions",
                    fix_priority=3
                )
                issues.append(issue)
        
        # Check for ambiguous legal terms
        if text:
            ambiguous_terms = [
                r'reasonable', r'appropriate', r'sufficient',
                r'مناسب', r'کافی', r'معقول',
            ]
            
            ambiguous_count = 0
            for term in ambiguous_terms:
                matches = re.findall(rf'\b{term}\b', text, re.IGNORECASE)
                ambiguous_count += len(matches)
            
            if ambiguous_count > 5:
                validity_score *= 0.9  # Slight reduction for ambiguity
                issue = QualityIssue(
                    issue_type=IssueType.AMBIGUOUS_LEGAL_TERMS,
                    severity='low',
                    description="Multiple ambiguous legal terms found",
                    suggested_fix="Clarify ambiguous terms for better interpretation",
                    fix_priority=4
                )
                issues.append(issue)
        
        # Create metrics
        metrics['legal_validity'] = QualityMetric(
            name='legal_validity',
            score=validity_score,
            weight=self.config.QUALITY_WEIGHTS['legal_validity'],
            description='Legal validity and clarity',
            details={'validity_score': validity_score, 'currency_score': currency_score},
            passed=validity_score >= 0.6
        )
        
        metrics['document_currency'] = QualityMetric(
            name='document_currency',
            score=currency_score,
            weight=0.05,
            description='Document currency and relevance',
            details={'currency_score': currency_score},
            passed=currency_score >= 0.5
        )
        
        return metrics, issues
    
    def _assess_structure_quality(self, text: str) -> Dict[str, Any]:
        """Assess document structure quality"""
        metrics = {}
        issues = []
        
        if not text:
            return {'metrics': metrics, 'issues': issues}
        
        # Check for document structure elements
        structure_elements = {
            'sections': 0,
            'lists': 0,
            'tables': 0,
            'headings': 0,
        }
        
        for pattern in self.structure_patterns:
            matches = pattern.findall(text)
            if 'section' in pattern.pattern.lower():
                structure_elements['sections'] += len(matches)
            elif 'table' in pattern.pattern.lower():
                structure_elements['tables'] += len(matches)
            elif 'figure' in pattern.pattern.lower():
                structure_elements['tables'] += len(matches)  # Count figures as structure
            elif re.search(r'\d+\.', pattern.pattern):
                structure_elements['lists'] += len(matches)
            else:
                structure_elements['headings'] += len(matches)
        
        # Calculate structure score
        total_elements = sum(structure_elements.values())
        text_length = len(text)
        
        if text_length > 5000:  # Long documents should have more structure
            expected_elements = text_length / 1000  # Rough heuristic
            if total_elements >= expected_elements:
                structure_score = 1.0
            elif total_elements >= expected_elements * 0.5:
                structure_score = 0.7
            elif total_elements >= expected_elements * 0.2:
                structure_score = 0.4
            else:
                structure_score = 0.2
        else:
            # For shorter documents, any structure is good
            structure_score = min(1.0, total_elements * 0.3)
        
        metrics['document_structure'] = QualityMetric(
            name='document_structure',
            score=structure_score,
            weight=0.06,
            description='Document structure and organization',
            details={'structure_elements': structure_elements, 'total_elements': total_elements},
            passed=structure_score >= 0.5
        )
        
        if structure_score < 0.4:
            issue = QualityIssue(
                issue_type=IssueType.POOR_DOCUMENT_STRUCTURE,
                severity='medium',
                description="Poor document structure detected",
                suggested_fix="Improve document formatting and structure",
                fix_priority=3
            )
            issues.append(issue)
        
        # Check for tables
        if structure_elements['tables'] == 0 and 'table' in text.lower():
            # Text mentions tables but none detected
            issue = QualityIssue(
                issue_type=IssueType.BROKEN_TABLES,
                severity='medium',
                description="Table references found but no table structure detected",
                suggested_fix="Check table extraction or formatting",
                fix_priority=3
            )
            issues.append(issue)
        
        return {'metrics': metrics, 'issues': issues}
    
    def _calculate_overall_score(self, metrics: Dict[str, QualityMetric]) -> float:
        """Calculate overall quality score from metrics"""
        if not metrics:
            return 0.5  # Default score if no metrics
        
        weighted_sum = 0.0
        total_weight = 0.0
        
        for metric_name, metric in metrics.items():
            weighted_sum += metric.score * metric.weight
            total_weight += metric.weight
        
        # Also consider component weights from config
        component_scores = self._calculate_component_scores(metrics)
        
        config_weighted_sum = 0.0
        for component, weight in self.config.QUALITY_WEIGHTS.items():
            score = component_scores.get(component, 0.5)
            config_weighted_sum += score * weight
        
        # Combine both calculations (weighted average)
        if total_weight > 0:
            metric_based_score = weighted_sum / total_weight
        else:
            metric_based_score = 0.5
        
        # Use 70% metric-based, 30% config-based
                # Use 70% metric-based, 30% config-based
        overall_score = (metric_based_score * 0.7) + (config_weighted_sum * 0.3)
        
        return min(1.0, max(0.0, overall_score))
    
    def _calculate_component_scores(self, metrics: Dict[str, QualityMetric]) -> Dict[str, float]:
        """Calculate component scores based on metric categories"""
        component_mapping = {
            'readability': ['readability', 'language_mixing', 'language_confusion', 'garbled_text'],
            'completeness': ['text_presence', 'incomplete_text', 'missing_sections'],
            'technical_quality': ['ocr_error_rate', 'file_size', 'file_format', 'file_encryption', 
                                  'text_density', 'extraction_confidence'],
            'kpk_specificity': ['kpk_relevance', 'kpk_division_specificity', 'kpk_jurisdiction_clarity',
                               'kpk_legal_references', 'kpk_language_appropriateness', 'kpk_geographic_specificity'],
            'legal_validity': ['legal_validity', 'document_currency'],
            'metadata_quality': ['profile_quality', 'extraction_confidence'],
        }
        
        component_scores = {}
        
        for component, metric_names in component_mapping.items():
            component_metrics = [metrics.get(name) for name in metric_names if name in metrics]
            
            if not component_metrics:
                component_scores[component] = 0.5  # Default
                continue
            
            # Calculate weighted average
            weighted_sum = 0.0
            total_weight = 0.0
            
            for metric in component_metrics:
                weighted_sum += metric.score * metric.weight
                total_weight += metric.weight
            
            if total_weight > 0:
                component_scores[component] = weighted_sum / total_weight
            else:
                component_scores[component] = 0.5
        
        return component_scores
    
    def _determine_processing_decision(self, 
                                     overall_score: float,
                                     issues: List[QualityIssue],
                                     component_scores: Dict[str, float]) -> ProcessingDecision:
        """Determine processing decision based on quality assessment"""
        
        # Check for critical issues that prevent processing
        critical_issues = [i for i in issues if i.severity == 'critical']
        if critical_issues:
            return ProcessingDecision.REJECT
        
        # Check for high-severity issues that require expert review
        high_issues = [i for i in issues if i.severity == 'high']
        kpk_legal_issues = [i for i in issues if i.issue_type in [
            IssueType.CONFLICTING_AUTHORITIES,
            IssueType.OUTDATED_KPK_LAW,
            IssueType.UNCLEAR_JURISDICTION,
        ]]
        
        if high_issues and kpk_legal_issues:
            return ProcessingDecision.EXPERT_REVIEW_NEEDED
        
        # Score-based decisions
        thresholds = self.config.PROCESSING_DECISIONS
        
        if overall_score >= thresholds['auto_process']:
            # High quality documents
            if component_scores.get('kpk_specificity', 0) >= 0.7:
                return ProcessingDecision.AUTO_PROCESS
            else:
                # Good quality but low KPK specificity
                return ProcessingDecision.AUTO_CLEAN_THEN_PROCESS
                
        elif overall_score >= thresholds['auto_clean_then_process']:
            # Medium quality, can be auto-cleaned
            return ProcessingDecision.AUTO_CLEAN_THEN_PROCESS
            
        elif overall_score >= thresholds['manual_review_needed']:
            # Low quality, needs human review
            if component_scores.get('kpk_specificity', 0) < 0.4:
                # KPK relevance unclear - expert needed
                return ProcessingDecision.EXPERT_REVIEW_NEEDED
            else:
                return ProcessingDecision.MANUAL_REVIEW_NEEDED
                
        elif overall_score >= thresholds['reject']:
            # Very low quality, but not zero
            if len(high_issues) > 2:
                return ProcessingDecision.REJECT
            else:
                return ProcessingDecision.DEFER  # Defer for later processing
        
        else:
            # Unacceptable quality
            return ProcessingDecision.REJECT
    
    def _generate_recommendations(self,
                                 issues: List[QualityIssue],
                                 component_scores: Dict[str, float],
                                 processing_decision: ProcessingDecision) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Generate recommendations based on assessment"""
        recommendations = []
        priority_actions = []
        
        # Sort issues by priority
        sorted_issues = sorted(issues, key=lambda x: (x.fix_priority, -x.confidence))
        
        # Generate specific recommendations for each high/medium priority issue
        for issue in sorted_issues:
            if issue.fix_priority <= 3:  # Only urgent, high, and medium priority
                rec = {
                    'issue_type': issue.issue_type.value,
                    'severity': issue.severity,
                    'description': issue.description,
                    'suggested_fix': issue.suggested_fix or "No specific fix suggested",
                    'priority': issue.fix_priority,
                }
                recommendations.append(rec)
                
                if issue.fix_priority <= 2:
                    priority_actions.append(f"{issue.severity.upper()}: {issue.description}")
        
        # Add component-based recommendations
        for component, score in component_scores.items():
            if score < 0.5:
                if component == 'kpk_specificity':
                    rec = {
                        'issue_type': 'low_kpk_specificity',
                        'severity': 'medium',
                        'description': f"Low {component.replace('_', ' ')} score: {score:.2%}",
                        'suggested_fix': "Add KPK-specific metadata or context",
                        'priority': 3,
                    }
                    recommendations.append(rec)
                    priority_actions.append(f"Improve KPK specificity (score: {score:.2%})")
                
                elif component == 'legal_validity':
                    rec = {
                        'issue_type': 'low_legal_validity',
                        'severity': 'medium',
                        'description': f"Low {component.replace('_', ' ')} score: {score:.2%}",
                        'suggested_fix': "Verify document validity and currency",
                        'priority': 3,
                    }
                    recommendations.append(rec)
        
        # Add processing decision specific recommendations
        if processing_decision == ProcessingDecision.AUTO_CLEAN_THEN_PROCESS:
            rec = {
                'issue_type': 'auto_clean_needed',
                'severity': 'info',
                'description': "Document requires automated cleaning before processing",
                'suggested_fix': "Run through LLM text sanitizer and multilingual handler",
                'priority': 3,
            }
            recommendations.append(rec)
            priority_actions.append("Perform automated text cleaning")
        
        elif processing_decision == ProcessingDecision.MANUAL_REVIEW_NEEDED:
            rec = {
                'issue_type': 'manual_review_needed',
                'severity': 'high',
                'description': "Document requires human review before processing",
                'suggested_fix': "Review document quality and KPK relevance manually",
                'priority': 2,
            }
            recommendations.append(rec)
            priority_actions.append("Schedule manual review by forestry expert")
        
        elif processing_decision == ProcessingDecision.EXPERT_REVIEW_NEEDED:
            rec = {
                'issue_type': 'expert_review_needed',
                'severity': 'high',
                'description': "Document requires KPK forestry expert review",
                'suggested_fix': "Consult with KPK forestry department experts",
                'priority': 1,
            }
            recommendations.append(rec)
            priority_actions.append("Urgent: Consult KPK forestry experts")
        
        elif processing_decision == ProcessingDecision.REJECT:
            rec = {
                'issue_type': 'document_rejected',
                'severity': 'critical',
                'description': "Document quality is too poor for processing",
                'suggested_fix': "Obtain better quality version or different source",
                'priority': 1,
            }
            recommendations.append(rec)
            priority_actions.append("Reject document - quality unacceptable")
        
        # Add general recommendations if none specific
        if not priority_actions:
            if component_scores.get('readability', 1) < 0.7:
                priority_actions.append("Improve document readability")
            if component_scores.get('technical_quality', 1) < 0.7:
                priority_actions.append("Enhance technical quality (OCR, formatting)")
        
        # Ensure at least one priority action
        if not priority_actions:
            priority_actions.append("Proceed with standard processing")
        
        return recommendations, priority_actions
    
    def _estimate_processing_time(self, 
                                 overall_score: float,
                                 issue_count: int,
                                 processing_decision: ProcessingDecision) -> Optional[float]:
        """Estimate processing time in minutes"""
        
        # Base time estimates (minutes)
        base_times = {
            ProcessingDecision.AUTO_PROCESS: 5,
            ProcessingDecision.AUTO_CLEAN_THEN_PROCESS: 15,
            ProcessingDecision.MANUAL_REVIEW_NEEDED: 45,
            ProcessingDecision.EXPERT_REVIEW_NEEDED: 120,
            ProcessingDecision.REJECT: 0,
            ProcessingDecision.DEFER: 5,  # Quick assessment only
        }
        
        base_time = base_times.get(processing_decision, 10)
        
        # Adjust based on quality score
        # Lower quality = more time needed
        if overall_score < 0.5:
            time_multiplier = 1.5
        elif overall_score < 0.7:
            time_multiplier = 1.2
        else:
            time_multiplier = 1.0
        
        # Adjust based on number of issues
        if issue_count > 10:
            issue_multiplier = 1.5
        elif issue_count > 5:
            issue_multiplier = 1.3
        elif issue_count > 2:
            issue_multiplier = 1.1
        else:
            issue_multiplier = 1.0
        
        estimated_time = base_time * time_multiplier * issue_multiplier
        
        # Round to nearest 5 minutes
        estimated_time = round(estimated_time / 5) * 5
        
        return estimated_time if estimated_time > 0 else None
    
    def _update_statistics(self, assessment: QualityAssessment, assessment_time: float):
        """Update assessment statistics"""
        self.stats['documents_assessed'] += 1
        self.stats['assessment_time_total'] += assessment_time
        
        # Update quality category stats
        category = assessment.quality_category.value
        self.stats['by_quality_category'][category] += 1
        
        # Update processing decision stats
        decision = assessment.processing_decision.value
        self.stats['by_processing_decision'][decision] += 1
        
        # Update issue statistics
        self.stats['total_issues_found'] += assessment.total_issues
        
        for issue in assessment.issues:
            self.stats['issues_by_type'][issue.issue_type.value] += 1
            self.stats['issues_by_severity'][issue.severity] += 1
        
        # Update KPK statistics
        if assessment.kpk_relevance_score > 0.7:
            self.stats['kpk_documents'] += 1
        
        # Check for specific KPK divisions
        if assessment.kpk_division_specificity > 0.8:
            # Check which division (would need more context)
            pass
        
        # Update processing statistics
        if assessment.processing_decision == ProcessingDecision.AUTO_PROCESS:
            self.stats['auto_processed'] += 1
        elif assessment.processing_decision in [
            ProcessingDecision.MANUAL_REVIEW_NEEDED,
            ProcessingDecision.EXPERT_REVIEW_NEEDED
        ]:
            self.stats['manual_review_needed'] += 1
        elif assessment.processing_decision == ProcessingDecision.REJECT:
            self.stats['rejected'] += 1
        
        # Update average scores
        total_assessments = self.stats['documents_assessed']
        old_avg_score = self.stats['avg_quality_score']
        old_avg_kpk = self.stats['avg_kpk_relevance']
        
        self.stats['avg_quality_score'] = (
            (old_avg_score * (total_assessments - 1) + assessment.overall_quality_score) 
            / total_assessments
        )
        
        self.stats['avg_kpk_relevance'] = (
            (old_avg_kpk * (total_assessments - 1) + assessment.kpk_relevance_score) 
            / total_assessments
        )
        
        # Update performance metrics
        perf = self.stats['performance_metrics']
        perf['assessment_times'].append(assessment_time)
        perf['fastest_assessment'] = min(perf['fastest_assessment'], assessment_time)
        perf['slowest_assessment'] = max(perf['slowest_assessment'], assessment_time)
    
    def _log_quality_abstention(self, assessment: QualityAssessment, document_path: str):
        """Log abstention for low-quality documents"""
        try:
            context = create_abstention_context(
                stage=PipelineStage.QUALITY_ASSESSMENT,
                component="DocQualityAssessor",
                document_path=str(document_path),
                reason="document_quality_too_low",
                details={
                    'quality_score': assessment.overall_quality_score,
                    'quality_category': assessment.quality_category.value,
                    'critical_issues': assessment.critical_issues,
                    'high_issues': assessment.high_issues,
                    'kpk_relevance': assessment.kpk_relevance_score,
                }
            )
            
            self.abstention_logger.log_abstention(
                abstention_type=AbstentionType.QUALITY_ISSUE,
                severity=AbstentionSeverity.HIGH,
                context=context,
                suggested_action="Obtain better quality document or perform manual review",
                confidence=1.0 - assessment.overall_quality_score,
                component_state=assessment.to_dict(),
            )
            
            self.logger.info(f"Logged quality abstention for {document_path}")
            
        except Exception as e:
            self.logger.warning(f"Failed to log quality abstention: {e}")
    
    def _create_error_assessment(self, 
                                document_path: str,
                                error_message: str,
                                stage: AssessmentStage) -> QualityAssessment:
        """Create minimal assessment when error occurs"""
        assessment_id = f"qa_error_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Create critical issue for the error
        error_issue = QualityIssue(
            issue_type=IssueType.CORRUPTED_FILE,
            severity='critical',
            description=f"Assessment error: {error_message}",
            suggested_fix="Check document and try again",
            fix_priority=1
        )
        
        return QualityAssessment(
            assessment_id=assessment_id,
            document_path=str(document_path),
            assessment_stage=stage,
            assessed_at=datetime.now(),
            
            overall_quality_score=0.1,
            quality_category=QualityCategory.UNACCEPTABLE,
            processing_decision=ProcessingDecision.REJECT,
            
            metrics={},
            issues=[error_issue],
            
            readability_score=0.0,
            completeness_score=0.0,
            technical_score=0.0,
            kpk_specificity_score=0.0,
            legal_validity_score=0.0,
            metadata_score=0.0,
            
            kpk_relevance_score=0.0,
            kpk_division_specificity=0.0,
            kpk_jurisdiction_clarity=0.0,
            kpk_legal_references_score=0.0,
            
            recommended_actions=[{
                'issue_type': 'assessment_error',
                'severity': 'critical',
                'description': f"Assessment failed: {error_message}",
                'suggested_fix': "Check document and assessment parameters",
                'priority': 1,
            }],
            priority_actions=["Fix assessment error before processing"],
            estimated_processing_time=None,
            notes=f"Assessment failed with error: {error_message}"
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get current assessment statistics"""
        stats = self.stats.copy()
        
        # Calculate derived statistics
        total_assessed = stats['documents_assessed']
        if total_assessed > 0:
            stats['avg_assessment_time'] = stats['assessment_time_total'] / total_assessed
            
            # Calculate percentages
            for category in QualityCategory:
                count = stats['by_quality_category'][category.value]
                stats['by_quality_category'][f"{category.value}_pct"] = (
                    count / total_assessed * 100 if total_assessed > 0 else 0
                )
            
            for decision in ProcessingDecision:
                count = stats['by_processing_decision'][decision.value]
                stats['by_processing_decision'][f"{decision.value}_pct"] = (
                    count / total_assessed * 100 if total_assessed > 0 else 0
                )
        
        # Add performance metrics summary
        perf = stats['performance_metrics']
        if perf['assessment_times']:
            perf['avg_assessment_time'] = sum(perf['assessment_times']) / len(perf['assessment_times'])
        else:
            perf['avg_assessment_time'] = 0.0
            perf['fastest_assessment'] = 0.0
        
        return stats
    
    def save_assessment(self, assessment: QualityAssessment, output_dir: Union[str, Path]):
        """Save assessment to file"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save as JSON
        json_path = output_dir / f"{assessment.assessment_id}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(assessment.to_dict(), f, indent=2, ensure_ascii=False)
        
        # Save report as text
        report_path = output_dir / f"{assessment.assessment_id}_report.txt"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(assessment.get_quality_report())
        
        self.logger.info(f"Saved assessment to {json_path}")
        return json_path, report_path
    
    def batch_assess(self, 
                     documents: List[Dict[str, Any]],
                     output_dir: Optional[Union[str, Path]] = None) -> List[QualityAssessment]:
        """
        Assess multiple documents in batch
        
        Args:
            documents: List of dicts with keys:
                - 'path': Document path
                - 'profile': Optional DocumentProfile
                - 'text': Optional extracted text
                - 'metadata': Optional metadata
            output_dir: Optional directory to save assessments
        
        Returns:
            List of QualityAssessment objects
        """
        assessments = []
        
        for i, doc_info in enumerate(documents, 1):
            try:
                self.logger.info(f"Processing document {i}/{len(documents)}: {doc_info.get('path', 'unknown')}")
                
                assessment = self.assess_document(
                    document_path=doc_info['path'],
                    profile=doc_info.get('profile'),
                    extracted_text=doc_info.get('text'),
                    metadata=doc_info.get('metadata'),
                    detailed_analysis=True
                )
                
                assessments.append(assessment)
                
                # Save if output directory specified
                if output_dir:
                    self.save_assessment(assessment, output_dir)
                
            except Exception as e:
                self.logger.error(f"Error processing document {i}: {e}")
                
                # Create error assessment
                error_assessment = self._create_error_assessment(
                    document_path=doc_info.get('path', 'unknown'),
                    error_message=str(e),
                    stage=AssessmentStage.PRE_PROCESSING
                )
                assessments.append(error_assessment)
        
        return assessments

# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    """Main function for standalone testing"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Document Quality Assessor")
    parser.add_argument("document_path", help="Path to document to assess")
    parser.add_argument("--output-dir", "-o", help="Output directory for assessment reports")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create assessor
    assessor = DocQualityAssessor()
    
    # Assess single document
    assessment = assessor.assess_document(args.document_path)
    
    # Print summary
    print("\n" + "="*60)
    print("QUALITY ASSESSMENT SUMMARY")
    print("="*60)
    print(f"Document: {Path(args.document_path).name}")
    print(f"Quality Score: {assessment.overall_quality_score:.2%}")
    print(f"Quality Category: {assessment.quality_category.value.upper()}")
    print(f"Processing Decision: {assessment.processing_decision.value.replace('_', ' ').upper()}")
    print(f"KPK Relevance: {assessment.kpk_relevance_score:.2%}")
    print(f"Issues Found: {assessment.total_issues} (Critical: {assessment.critical_issues})")
    print("\nPriority Actions:")
    for action in assessment.priority_actions[:3]:
        print(f"  • {action}")
    
    # Save if output directory specified
    if args.output_dir:
        json_path, report_path = assessor.save_assessment(assessment, args.output_dir)
        print(f"\nAssessment saved to:")
        print(f"  JSON: {json_path}")
        print(f"  Report: {report_path}")
    
    # Print statistics
    stats = assessor.get_statistics()
    print(f"\nStatistics:")
    print(f"  Documents Assessed: {stats['documents_assessed']}")
    print(f"  Average Quality Score: {stats['avg_quality_score']:.2%}")
    print(f"  Average KPK Relevance: {stats['avg_kpk_relevance']:.2%}")
    print(f"  Auto Processed: {stats['auto_processed']}")
    print(f"  Manual Review Needed: {stats['manual_review_needed']}")
    print(f"  Rejected: {stats['rejected']}")

if __name__ == "__main__":
    main()
