"""
GreenLawAI-KPK: Abstention Logging System
Version: 2.1 (Enhanced with KPK integration, configuration, and performance improvements)
Author: Hina Ali, Eman Irfan
Date: January 29, 2026

This module implements a comprehensive abstention logging system for tracking
all instances where the system cannot make a confident decision. This is critical
for academic integrity, system transparency, and continuous improvement.

Key Features:
1. Tracks all "I don't know" decisions with detailed reasons
2. KPK-specific abstention types and severity assessment
3. Enables human-in-the-loop review with KPK expert workflow
4. Provides analytics for system improvement
5. Integrates with KPK graph schema and metadata
6. Configuration-driven with performance optimizations
"""

import json
import csv
import sqlite3
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Dict, List, Any, Optional, Tuple, Set, Union
from dataclasses import dataclass, asdict, field
import hashlib
from pathlib import Path
import logging
import threading
import queue
import time
from collections import defaultdict, Counter
import zlib
import pickle
import zlib
import pickle
from concurrent.futures import ThreadPoolExecutor

print("DEBUG: 0.3 Imports starting...", flush=True)
# Import from common modules
try:
    from preprocessing_pipeline.common.config import PipelineConfig, AbstentionConfig
    print("DEBUG: 0.3 Imported Config", flush=True)
    from preprocessing_pipeline.common.constants import *
    print("DEBUG: 0.3 Imported Constants", flush=True)
    from preprocessing_pipeline.common.llm_client import LLMClient
    print("DEBUG: 0.3 Imported LLMClient", flush=True)
    USE_COMMON_CONFIG = True
except ImportError as e:
    USE_COMMON_CONFIG = False
    print(f"Warning: preprocessing_pipeline.common.config not found: {e}. Using default configuration.")
    print(f"DEBUG: 0.3 Import Error: {e}", flush=True)

print("DEBUG: 0.3 Configuration class definition...", flush=True)
# ============================================================================

# ============================================================================
# CONFIGURATION
# ============================================================================

class AbstentionSystemConfig:
    """Configuration for abstention logging system"""
    
    # Storage settings
    STORAGE = {
        'log_dir': './abstention_logs',
        'db_path': './abstention_logs/abstention_db.sqlite',
        'enable_sqlite': True,
        'enable_json': True,
        'enable_csv': True,
        'enable_compression': True,
        'archive_after_days': 30,
        'cleanup_after_days': 180,
    }
    
    # Performance settings
    PERFORMANCE = {
        'batch_size': 50,
        'flush_interval_seconds': 5,
        'max_queue_size': 1000,
        'worker_threads': 2,
        'enable_async_logging': True,
    }
    
    # KPK-specific settings
    KPK_SETTINGS = {
        'enable_kpk_severity_weights': True,
        'kpk_division_weights': {
            'hazara': 1.2,  # Higher weight for Hazara-specific issues
            'malakand': 1.1,
            'swat': 1.1,
            'other': 1.0,
        },
        'critical_kpk_issues': [
            'authority_conflict',
            'jurisdiction_overlap', 
            'amendment_chain_break',
            'kpk_federal_conflict',
        ],
    }
    
    # Thresholds and scoring
    THRESHOLDS = {
        'confidence_threshold_default': 0.7,
        'high_severity_threshold': 0.4,
        'medium_severity_threshold': 0.2,
        'auto_resolve_threshold': 0.1,
        'retrain_threshold_count': 10,
    }
    
    # Integration settings
    INTEGRATION = {
        'link_to_document_profile': True,
        'link_to_kpk_metadata': True,
        'enable_cross_module_tracking': True,
        'generate_pipeline_metrics': True,
    }

# ============================================================================
# ENUMERATIONS (ENHANCED)
# ============================================================================

class AbstentionType(Enum):
    """Types of abstentions the system can make (KPK-enhanced)"""
    # Document Processing
    POOR_OCR_QUALITY = "poor_ocr_quality"
    SCANNED_DOCUMENT_ISSUE = "scanned_document_issue"
    MULTILINGUAL_CONFUSION = "multilingual_confusion"
    FORMAT_PARSING_ERROR = "format_parsing_error"
    TABLE_EXTRACTION_FAILURE = "table_extraction_failure"
    IMAGE_PROCESSING_FAILURE = "image_processing_failure"
    EXTRACTION_ISSUE = "extraction_issue"
    
    # Legal Processing
    AUTHORITY_CONFLICT = "authority_conflict"
    KPK_FEDERAL_CONFLICT = "kpk_federal_conflict"  # KPK-specific
    JURISDICTION_OVERLAP = "jurisdiction_overlap"
    LEGAL_INTERPRETATION = "legal_interpretation"
    AMBIGUOUS_REFERENCE = "ambiguous_reference"
    CONTRADICTORY_SOURCES = "contradictory_sources"
    
    # Temporal and Amendment
    TEMPORAL_UNCERTAINTY = "temporal_uncertainty"
    AMENDMENT_CHAIN_BREAK = "amendment_chain_break"
    DATE_RESOLUTION_FAILURE = "date_resolution_failure"
    
    # Entity Extraction
    SPECIES_IDENTIFICATION = "species_identification"
    OFFICER_RANK_UNCERTAINTY = "officer_rank_uncertainty"
    LOCATION_RESOLUTION = "location_resolution"
    PENALTY_CALCULATION = "penalty_calculation"
    PERMIT_REQUIREMENT = "permit_requirement"
    
    # KPK-specific
    HAZARA_SPECIFIC_ISSUE = "hazara_specific_issue"
    MALAKAND_SPECIFIC_ISSUE = "malakand_specific_issue"
    KPK_DIVISION_CONFLICT = "kpk_division_conflict"
    FOREST_TYPE_CLASSIFICATION = "forest_type_classification"
    
    # Graph and Indexing
    GRAPH_RELATIONSHIP_UNCERTAIN = "graph_relationship_uncertain"
    INDEXING_INCONSISTENCY = "indexing_inconsistency"
    ENTITY_LINKING_FAILURE = "entity_linking_failure"
    
    # Query and Response
    QUERY_AMBIGUITY = "query_ambiguity"
    CLIMATE_IMPACT_ESTIMATION = "climate_impact_estimation"
    RESPONSE_CONFIDENCE_LOW = "response_confidence_low"
    
    # System and Performance
    LOW_CONFIDENCE_EXTRACTION = "low_confidence_extraction"
    INCOMPLETE_CONTEXT = "incomplete_context"
    SYSTEM_LIMITATION = "system_limitation"
    PERFORMANCE_DEGRADATION = "performance_degradation"
    
    OTHER = "other"

class AbstentionSeverity(Enum):
    """Severity levels for abstentions (enhanced)"""
    INFO = "info"           # Informational only, no impact
    LOW = "low"            # Minor uncertainty, can be auto-resolved
    MEDIUM = "medium"      # Needs human review, moderate impact
    HIGH = "high"          # Significant impact on accuracy
    CRITICAL = "critical"  # Fundamental system limitation or legal risk
    BLOCKER = "blocker"    # Prevents further processing

class ReviewStatus(Enum):
    """Status of abstention review (enhanced)"""
    PENDING = "pending"
    IN_REVIEW = "in_review"
    AUTO_RESOLVED = "auto_resolved"
    MANUAL_RESOLVED = "manual_resolved"
    DEFERRED = "deferred"
    IGNORED = "ignored"           # Valid abstention, no action needed
    SYSTEM_FIXED = "system_fixed" # System learned and fixed
    ESCALATED = "escalated"       # Sent to KPK expert
    INVALID = "invalid"           # Not a valid abstention

class PipelineStage(Enum):
    """Pipeline stages where abstentions can occur (enhanced)"""
    # Phase 0: Foundation
    DOCUMENT_PROFILING = "document_profiling"
    KPK_METADATA_ENRICHMENT = "kpk_metadata_enrichment"
    QUALITY_ASSESSMENT = "quality_assessment"
    
    # Phase 1: Extraction
    PDF_PARSING = "pdf_parsing"
    LAYOUT_EXTRACTION = "layout_extraction"
    TABLE_EXTRACTION = "table_extraction"
    IMAGE_PROCESSING = "image_processing"
    OCR_ENGINE = "ocr_engine"
    OCR_TRAINING = "ocr_training"
    
    # Phase 2: Restoration
    TEXT_SANITIZATION = "text_sanitization"
    MULTILINGUAL_SEGMENTATION = "multilingual_segmentation"
    
    # Phase 3: Linguistic Alignment
    MULTILINGUAL_HANDLING = "multilingual_handling"
    CIRCULAR_PARSING = "circular_parsing"
    WORKING_PLAN_PARSING = "working_plan_parsing"
    SECTION_DETECTION = "section_detection"
    
    # Phase 4: Legal Extraction
    RULE_EXTRACTION = "rule_extraction"
    NER_EXTRACTION = "ner_extraction"
    AMENDMENT_TRACKING = "amendment_tracking"
    CITATION_RESOLUTION = "citation_resolution"
    
    # Phase 5: Authority Reasoning
    AUTHORITY_HIERARCHY = "authority_hierarchy"
    PENALTY_LOGIC = "penalty_logic"
    AMBIGUITY_RESOLUTION = "ambiguity_resolution"
    TEMPORAL_VALIDATION = "temporal_validation"
    
    # Phase 6: Graph Construction
    GRAPH_SCHEMA = "graph_schema"
    GRAPH_MAPPING = "graph_mapping"
    GRAPH_BUILDING = "graph_building"
    LEGAL_CHUNKING = "legal_chunking"
    EMBEDDING_GENERATION = "embedding_generation"
    FAISS_INDEXING = "faiss_indexing"
    HYBRID_LINKING = "hybrid_linking"
    NEO4J_EXPORT = "neo4j_export"
    
    # Phase 7: Orchestration
    BATCH_PROCESSING = "batch_processing"
    QUALITY_GATES = "quality_gates"
    
    # System-wide
    SYSTEM_INITIALIZATION = "system_initialization"
    CONFIGURATION = "configuration"
    MONITORING = "monitoring"
    
    OTHER = "other"

class KPKDivision(Enum):
    """KPK Forest Divisions for context"""
    HAZARA = "hazara"
    MALAKAND = "malakand"
    SWAT = "swat"
    DIR = "dir"
    PESHAWAR = "peshawar"
    MARDAN = "mardan"
    KOHAT = "kohat"
    BANNU = "bannu"
    DERA_ISMAIL_KHAN = "dera_ismail_khan"
    UNKNOWN = "unknown"

# ============================================================================
# DATA CLASSES (ENHANCED)
# ============================================================================

@dataclass
class AbstentionContext:
    """Context information for abstention (enhanced)"""
    # Basic context
    pipeline_state: str
    processing_step: str
    module_state: Dict[str, Any]
    
    # KPK-specific context
    kpk_division: Optional[KPKDivision] = None
    kpk_district: Optional[str] = None
    is_hazara: bool = False
    is_malakand: bool = False
    
    # Document context
    document_type: Optional[str] = None
    document_year: Optional[int] = None
    document_quality: Optional[str] = None
    language_mix: Optional[str] = None
    
    # Processing context
    input_summary: Optional[str] = None
    text_preview: Optional[str] = None
    entity_count: Optional[int] = None
    confidence_scores: Optional[Dict[str, float]] = None
    
    # Technical context
    model_used: Optional[str] = None
    parameters_hash: Optional[str] = None
    system_version: str = "GreenLawAI-KPK v2.1"
    
    # Timestamps
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        
        # Convert enums to strings
        if self.kpk_division:
            data['kpk_division'] = self.kpk_division.value
        
        # Convert datetime to string
        data['timestamp'] = self.timestamp.isoformat()
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AbstentionContext':
        """Create from dictionary"""
        # Convert string to datetime
        if 'timestamp' in data and isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        
        # Convert string to enum
        if 'kpk_division' in data and data['kpk_division']:
            data['kpk_division'] = KPKDivision(data['kpk_division'])
        
        return cls(**data)


@dataclass
class AbstentionRecord:
    """Complete abstention record (enhanced)"""
    # Identification (Required)
    abstention_id: str
    abstention_type: AbstentionType
    severity: AbstentionSeverity
    timestamp: datetime
    pipeline_stage: PipelineStage
    module_name: str
    reason: str
    context: AbstentionContext
    affected_entities: List[str]
    confidence_before: float
    confidence_threshold: float
    system_version: str
    
    # Optional / With Defaults
    function_name: Optional[str] = None
    source_document: Optional[str] = None
    page_number: Optional[int] = None
    line_number: Optional[int] = None
    confidence_after: Optional[float] = None
    kpk_relevance_score: float = 0.0
    kpk_expert_needed: bool = False
    kpk_division_context: Optional[str] = None
    model_used: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    git_commit: Optional[str] = None
    review_status: ReviewStatus = ReviewStatus.PENDING
    reviewed_by: Optional[str] = None
    review_date: Optional[datetime] = None
    resolution: Optional[str] = None
    resolution_action: Optional[str] = None
    resolution_confidence: Optional[float] = None
    learning_feedback: Optional[str] = None
    should_retrain: bool = False
    retrain_priority: int = 0
    training_data_suggestion: Optional[str] = None

    
    # Technical details
    error_traceback: Optional[str] = None
    input_hash: Optional[str] = None
    output_hash: Optional[str] = None
    execution_time_ms: Optional[float] = None
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    notes: Optional[str] = None
    linked_abstentions: List[str] = field(default_factory=list)
    
    # Performance metrics
    memory_usage_mb: Optional[float] = None
    cpu_usage_percent: Optional[float] = None
    
    def __post_init__(self):
        """Calculate derived fields"""
        self.confidence_gap = self.confidence_threshold - self.confidence_before
        
        # Auto-calculate KPK relevance
        if self.kpk_relevance_score == 0.0:
            self.kpk_relevance_score = self._calculate_kpk_relevance()
        
        # Auto-determine if KPK expert needed
        if not self.kpk_expert_needed:
            self.kpk_expert_needed = self._needs_kpk_expert()
    
    def _calculate_kpk_relevance(self) -> float:
        """Calculate KPK relevance score"""
        score = 0.0
        
        # Base score based on type
        kpk_specific_types = {
            AbstentionType.KPK_FEDERAL_CONFLICT: 0.9,
            AbstentionType.HAZARA_SPECIFIC_ISSUE: 0.8,
            AbstentionType.MALAKAND_SPECIFIC_ISSUE: 0.8,
            AbstentionType.KPK_DIVISION_CONFLICT: 0.7,
        }
        
        score += kpk_specific_types.get(self.abstention_type, 0.0)
        
        # Score based on context
        if self.context.kpk_division:
            score += 0.2
        
        if self.context.is_hazara:
            score += 0.3
        
        if self.context.is_malakand:
            score += 0.2
        
        # Score based on document
        if self.source_document and any(kpk_term in self.source_document.lower() for kpk_term in ['kpk', 'khyber', 'hazara', 'malakand']):
            score += 0.2
        
        return min(score, 1.0)
    
    def _needs_kpk_expert(self) -> bool:
        """Determine if KPK forestry expert is needed"""
        # Critical KPK issues always need expert
        critical_issues = {
            AbstentionType.KPK_FEDERAL_CONFLICT,
            AbstentionType.HAZARA_SPECIFIC_ISSUE,
            AbstentionType.MALAKAND_SPECIFIC_ISSUE,
            AbstentionType.AUTHORITY_CONFLICT,
        }
        
        if self.abstention_type in critical_issues:
            return True
        
        # High severity with KPK relevance
        if self.severity in [AbstentionSeverity.HIGH, AbstentionSeverity.CRITICAL, AbstentionSeverity.BLOCKER]:
            if self.kpk_relevance_score > 0.5:
                return True
        
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        
        # Convert enums to strings
        data['abstention_type'] = self.abstention_type.value
        data['severity'] = self.severity.value
        data['pipeline_stage'] = self.pipeline_stage.value
        data['review_status'] = self.review_status.value
        
        # Convert context
        data['context'] = self.context.to_dict()
        
        # Convert datetime to string
        data['timestamp'] = self.timestamp.isoformat()
        if self.review_date:
            data['review_date'] = self.review_date.isoformat()
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AbstentionRecord':
        """Create from dictionary"""
        # Convert strings back to enums
        data['abstention_type'] = AbstentionType(data['abstention_type'])
        data['severity'] = AbstentionSeverity(data['severity'])
        data['pipeline_stage'] = PipelineStage(data['pipeline_stage'])
        data['review_status'] = ReviewStatus(data['review_status'])
        
        # Convert context
        if 'context' in data:
            data['context'] = AbstentionContext.from_dict(data['context'])
        
        # Convert string to datetime
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        if data.get('review_date'):
            data['review_date'] = datetime.fromisoformat(data['review_date'])
        
        return cls(**data)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of abstention for quick review"""
        return {
            'abstention_id': self.abstention_id,
            'type': self.abstention_type.value,
            'severity': self.severity.value,
            'stage': self.pipeline_stage.value,
            'reason': self.reason[:100] + '...' if len(self.reason) > 100 else self.reason,
            'confidence_gap': round(self.confidence_gap, 3),
            'kpk_relevance': round(self.kpk_relevance_score, 3),
            'kpk_expert_needed': self.kpk_expert_needed,
            'status': self.review_status.value,
            'timestamp': self.timestamp.isoformat(),
        }

# ============================================================================
# ASYNCHRONOUS LOGGING QUEUE
# ============================================================================

class AsyncAbstentionLogger:
    """Asynchronous abstention logger for performance"""
    
    def __init__(self, logger_instance, batch_size: int = 50, flush_interval: int = 5):
        self.logger = logger_instance
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        
        # Thread-safe queue
        self.queue = queue.Queue(maxsize=1000)
        self.batch_buffer = []
        
        # Control flags
        self.running = False
        self.worker_thread = None
        
        # Statistics
        self.stats = {
            'queued': 0,
            'processed': 0,
            'batched': 0,
            'dropped': 0,
            'avg_batch_size': 0,
            'max_queue_size': 0,
        }
    
    def start(self):
        """Start the async logger worker"""
        if self.running:
            return
        
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        
        logging.info("Async abstention logger started")
    
    def stop(self):
        """Stop the async logger worker"""
        self.running = False
        
        # Flush remaining records
        if self.worker_thread:
            self.worker_thread.join(timeout=10)
        
        # Process any remaining records
        self._process_batch()
        
        logging.info("Async abstention logger stopped")
    
    def log_async(self, record_data: Dict[str, Any]) -> Optional[str]:
        """Log abstention asynchronously"""
        if not self.running:
            logging.warning("Async logger not running, logging synchronously")
            return self.logger._log_record_sync(record_data)
        
        try:
            # Put record in queue with timeout
            self.queue.put(record_data, timeout=1)
            self.stats['queued'] += 1
            
            # Update max queue size
            current_size = self.queue.qsize()
            if current_size > self.stats['max_queue_size']:
                self.stats['max_queue_size'] = current_size
            
            # Return a temporary ID (actual ID will be generated during processing)
            return f"async_{hash(str(record_data))}"
            
        except queue.Full:
            self.stats['dropped'] += 1
            logging.warning("Abstention queue full, record dropped")
            return None
    
    def _worker_loop(self):
        """Worker loop for processing async logs"""
        last_flush = time.time()
        
        while self.running:
            try:
                # Try to get record with timeout
                try:
                    record_data = self.queue.get(timeout=1)
                    self.batch_buffer.append(record_data)
                    self.queue.task_done()
                    
                except queue.Empty:
                    # Check if we should flush based on time
                    if time.time() - last_flush >= self.flush_interval:
                        self._process_batch()
                        last_flush = time.time()
                    continue
                
                # Check if we should flush based on batch size
                if len(self.batch_buffer) >= self.batch_size:
                    self._process_batch()
                    last_flush = time.time()
                
            except Exception as e:
                logging.error(f"Error in async logger worker: {e}")
                time.sleep(0.1)  # Prevent tight loop on error
        
        # Final flush when stopping
        self._process_batch()
    
    def _process_batch(self):
        """Process a batch of records"""
        if not self.batch_buffer:
            return
        
        try:
            # Log all records in batch
            for record_data in self.batch_buffer:
                self.logger._log_record_sync(record_data)
                self.stats['processed'] += 1
            
            self.stats['batched'] += 1
            self.stats['avg_batch_size'] = (
                (self.stats['avg_batch_size'] * (self.stats['batched'] - 1) + len(self.batch_buffer))
                / self.stats['batched']
            )
            
            logging.debug(f"Processed batch of {len(self.batch_buffer)} abstentions")
            
        except Exception as e:
            logging.error(f"Error processing batch: {e}")
        
        finally:
            # Clear buffer
            self.batch_buffer.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get async logger statistics"""
        stats = self.stats.copy()
        stats['queue_size'] = self.queue.qsize()
        stats['buffer_size'] = len(self.batch_buffer)
        stats['is_running'] = self.running
        return stats

# ============================================================================
# ENHANCED ABSTENTION LOGGER
# ============================================================================
print("DEBUG: 0.3 Defining AbstentionLogger...", flush=True)

class AbstentionLogger:
    """Main abstention logging system with enhanced features"""
    
    def __init__(self, 
                 config: Optional[Union[AbstentionSystemConfig, Dict]] = None,
                 log_dir: Optional[str] = None,
                 enable_async: bool = True,
                 logger: Optional[logging.Logger] = None):
        """
        Initialize abstention logger with configuration.
        
        Args:
            config: Configuration object or dictionary
            log_dir: Override log directory
            enable_async: Enable asynchronous logging for performance
            logger: Custom logger instance
        """
        
        # Configuration
        if isinstance(config, dict):
            self.config = AbstentionSystemConfig()
            # Update config from dict
            for key, value in config.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
        elif config and hasattr(config, 'abstention_config'):
             # Handle PipelineConfig which has an abstention_config attribute
             self.config = config.abstention_config
        elif config and hasattr(config, 'STORAGE'):
            self.config = config
        else:
            # Fallback to default
            self.config = AbstentionSystemConfig()
        
        # Override log directory if provided
        if log_dir:
            if hasattr(self.config, 'STORAGE') and isinstance(self.config.STORAGE, dict):
                self.config.STORAGE['log_dir'] = log_dir
            else:
                setattr(self.config, 'log_dir', log_dir)
        
        # Setup directories
        if hasattr(self.config, 'STORAGE') and isinstance(self.config.STORAGE, dict):
            self.log_dir = Path(self.config.STORAGE.get('log_dir', './abstention_logs'))
        else:
            self.log_dir = Path(getattr(self.config, 'log_dir', './abstention_logs'))
            
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup logging
        self.logger = logger or self._setup_logging()
        
        # Statistics (enhanced)
        self.stats = self._init_statistics()
        
        # Initialize databases
        self._init_storage()
        
        # Async logging
        self.enable_async = enable_async and self.config.PERFORMANCE['enable_async_logging']
        self.async_logger = None
        
        if self.enable_async:
            self.async_logger = AsyncAbstentionLogger(
                self,
                batch_size=self.config.PERFORMANCE['batch_size'],
                flush_interval=self.config.PERFORMANCE['flush_interval_seconds']
            )
            self.async_logger.start()
        
        # Cache for frequent queries
        self._cache = {
            'recent_abstentions': [],
            'stats_cache': None,
            'stats_cache_time': None,
        }
        
        self.logger.info(f"AbstentionLogger initialized with {self.config.STORAGE}")
    
    def _setup_logging(self) -> logging.Logger:
        """Setup file logging for abstentions"""
        log_file = self.log_dir / "abstention_system.log"
        
        logger = logging.getLogger('AbstentionLogger')
        logger.setLevel(logging.INFO)
        
        # Clear existing handlers
        logger.handlers.clear()
        
        # File handler
        fh = logging.FileHandler(log_file, encoding='utf-8')
        fh.setLevel(logging.INFO)
        
        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.WARNING)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(module)s - %(message)s'
        )
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        
        logger.addHandler(fh)
        logger.addHandler(ch)
        
        return logger
    
    def _init_statistics(self) -> Dict[str, Any]:
        """Initialize statistics structure"""
        return {
            # Counts
            'total_abstentions': 0,
            'today_count': 0,
            'this_week_count': 0,
            'this_month_count': 0,
            
            # By type
            'by_type': {atype.value: 0 for atype in AbstentionType},
            'by_severity': {sev.value: 0 for sev in AbstentionSeverity},
            'by_stage': {stage.value: 0 for stage in PipelineStage},
            'by_status': {status.value: 0 for status in ReviewStatus},
            'by_kpk_division': {div.value: 0 for div in KPKDivision},
            
            # KPK-specific
            'kpk_related_count': 0,
            'hazara_related_count': 0,
            'malakand_related_count': 0,
            'kpk_expert_needed_count': 0,
            
            # Performance
            'avg_confidence_gap': 0.0,
            'avg_processing_time_ms': 0.0,
            'max_confidence_gap': 0.0,
            'min_confidence_gap': 1.0,
            
            # Resolution
            'resolved_count': 0,
            'pending_count': 0,
            'auto_resolved_count': 0,
            'manual_resolved_count': 0,
            'escalated_count': 0,
            
            # Documents
            'unique_documents': set(),
            'documents_with_abstentions': {},
            
            # Timeline
            'hourly_distribution': {str(i).zfill(2): 0 for i in range(24)},
            'daily_distribution': {},
            
            # Load existing stats
            'last_updated': datetime.now().isoformat(),
        }
    
    def _init_storage(self):
        """Initialize storage backends"""
        # SQLite database
        if self.config.STORAGE['enable_sqlite']:
            self._init_sqlite_db()
        
        # Create necessary directories
        (self.log_dir / 'archive').mkdir(exist_ok=True)
        (self.log_dir / 'reports').mkdir(exist_ok=True)
        (self.log_dir / 'exports').mkdir(exist_ok=True)
        
        # Load existing statistics
        self._load_statistics()
    
    def _init_sqlite_db(self):
        """Initialize SQLite database with enhanced schema"""
        db_path = Path(self.config.STORAGE['db_path'])
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            self.conn = sqlite3.connect(db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
            
            # Enable WAL for better concurrency
            self.cursor.execute("PRAGMA journal_mode=WAL")
            self.cursor.execute("PRAGMA synchronous=NORMAL")
            self.cursor.execute("PRAGMA cache_size=-2000")  # 2MB cache
            
            # Create main abstention table (enhanced)
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS abstentions (
                    abstention_id TEXT PRIMARY KEY,
                    abstention_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    pipeline_stage TEXT NOT NULL,
                    module_name TEXT NOT NULL,
                    function_name TEXT,
                    
                    -- Context (stored as compressed JSON)
                    context_data BLOB,
                    
                    reason TEXT NOT NULL,
                    affected_entities TEXT,
                    source_document TEXT,
                    page_number INTEGER,
                    line_number INTEGER,
                    
                    confidence_before REAL,
                    confidence_threshold REAL,
                    confidence_after REAL,
                    confidence_gap REAL,
                    
                    -- KPK-specific fields
                    kpk_relevance_score REAL DEFAULT 0.0,
                    kpk_expert_needed BOOLEAN DEFAULT 0,
                    kpk_division_context TEXT,
                    
                    system_version TEXT,
                    model_used TEXT,
                    parameters TEXT,
                    git_commit TEXT,
                    
                    review_status TEXT DEFAULT 'pending',
                    reviewed_by TEXT,
                    review_date DATETIME,
                    resolution TEXT,
                    resolution_action TEXT,
                    resolution_confidence REAL,
                    
                    learning_feedback TEXT,
                    should_retrain BOOLEAN DEFAULT 0,
                    retrain_priority INTEGER DEFAULT 0,
                    training_data_suggestion TEXT,
                    
                    error_traceback TEXT,
                    input_hash TEXT,
                    output_hash TEXT,
                    execution_time_ms REAL,
                    
                    tags TEXT,
                    notes TEXT,
                    linked_abstentions TEXT,
                    
                    memory_usage_mb REAL,
                    cpu_usage_percent REAL,
                    
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes for faster queries (enhanced)
            indexes = [
                ('idx_type', 'abstention_type'),
                ('idx_severity', 'severity'),
                ('idx_stage', 'pipeline_stage'),
                ('idx_status', 'review_status'),
                ('idx_timestamp', 'timestamp'),
                ('idx_document', 'source_document'),
                ('idx_kpk_relevance', 'kpk_relevance_score'),
                ('idx_confidence_gap', 'confidence_gap'),
                ('idx_module', 'module_name'),
                ('idx_kpk_expert', 'kpk_expert_needed'),
            ]
            
            for idx_name, column in indexes:
                self.cursor.execute(f'''
                    CREATE INDEX IF NOT EXISTS {idx_name} ON abstentions({column})
                ''')
            
            # Create views for common queries
            self._create_sql_views()
            
            self.conn.commit()
            self.logger.info(f"SQLite database initialized at {db_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize SQLite database: {e}")
            self.config.STORAGE['enable_sqlite'] = False
    
    def _create_sql_views(self):
        """Create SQL views for common queries"""
        views = {
            'vw_daily_summary': '''
                SELECT 
                    DATE(timestamp) as date,
                    COUNT(*) as total,
                    SUM(CASE WHEN severity = 'critical' THEN 1 ELSE 0 END) as critical,
                    SUM(CASE WHEN severity = 'high' THEN 1 ELSE 0 END) as high,
                    SUM(CASE WHEN kpk_expert_needed = 1 THEN 1 ELSE 0 END) as kpk_expert_needed,
                    AVG(confidence_gap) as avg_confidence_gap
                FROM abstentions
                GROUP BY DATE(timestamp)
                ORDER BY date DESC
            ''',
            
            'vw_module_performance': '''
                SELECT 
                    module_name,
                    COUNT(*) as total_abstentions,
                    AVG(confidence_gap) as avg_confidence_gap,
                    SUM(CASE WHEN severity IN ('critical', 'high') THEN 1 ELSE 0 END) as severe_count,
                    AVG(kpk_relevance_score) as avg_kpk_relevance
                FROM abstentions
                GROUP BY module_name
                ORDER BY total_abstentions DESC
            ''',
            
            'vw_kpk_issues': '''
                SELECT 
                    kpk_division_context,
                    COUNT(*) as total,
                    GROUP_CONCAT(DISTINCT abstention_type) as issue_types,
                    AVG(kpk_relevance_score) as avg_relevance
                FROM abstentions
                WHERE kpk_relevance_score > 0.3
                GROUP BY kpk_division_context
                ORDER BY total DESC
            ''',
            
            'vw_pending_review': '''
                SELECT 
                    abstention_id,
                    abstention_type,
                    severity,
                    timestamp,
                    module_name,
                    reason,
                    confidence_gap,
                    kpk_expert_needed
                FROM abstentions
                WHERE review_status = 'pending'
                ORDER BY 
                    CASE severity 
                        WHEN 'critical' THEN 1
                        WHEN 'high' THEN 2
                        WHEN 'medium' THEN 3
                        WHEN 'low' THEN 4
                        ELSE 5
                    END,
                    confidence_gap DESC
            ''',
        }
        
        for view_name, view_sql in views.items():
            try:
                self.cursor.execute(f'DROP VIEW IF EXISTS {view_name}')
                self.cursor.execute(f'CREATE VIEW {view_name} AS {view_sql}')
            except Exception as e:
                self.logger.warning(f"Could not create view {view_name}: {e}")
    
    def _load_statistics(self):
        """Load statistics from database"""
        stats_file = self.log_dir / "abstention_statistics.json"
        if stats_file.exists():
            try:
                with open(stats_file, 'r', encoding='utf-8') as f:
                    loaded_stats = json.load(f)
                
                # Update our stats with loaded data
                for key, value in loaded_stats.items():
                    if key in self.stats:
                        if isinstance(self.stats[key], set) and isinstance(value, list):
                            self.stats[key] = set(value)
                        else:
                            self.stats[key] = value
                
                self.logger.info("Statistics loaded from file")
                
            except Exception as e:
                self.logger.error(f"Failed to load statistics: {e}")
        
        # Also load from database if available
        if self.config.STORAGE['enable_sqlite']:
            self._load_stats_from_db()
    
    def _load_stats_from_db(self):
        """Load statistics from database"""
        try:
            # Get total count
            self.cursor.execute("SELECT COUNT(*) FROM abstentions")
            self.stats['total_abstentions'] = self.cursor.fetchone()[0]
            
            # Get today's count
            today = datetime.now().date()
            self.cursor.execute(
                "SELECT COUNT(*) FROM abstentions WHERE DATE(timestamp) = ?",
                (today.isoformat(),)
            )
            self.stats['today_count'] = self.cursor.fetchone()[0]
            
            # Get pending count
            self.cursor.execute(
                "SELECT COUNT(*) FROM abstentions WHERE review_status = 'pending'"
            )
            self.stats['pending_count'] = self.cursor.fetchone()[0]
            
            # Get unique documents
            self.cursor.execute(
                "SELECT DISTINCT source_document FROM abstentions WHERE source_document IS NOT NULL"
            )
            docs = [row[0] for row in self.cursor.fetchall()]
            self.stats['unique_documents'] = set(docs)
            
        except Exception as e:
            self.logger.warning(f"Could not load stats from DB: {e}")
    
    def _save_statistics(self):
        """Save statistics to file"""
        stats_file = self.log_dir / "abstention_statistics.json"
        
        # Convert sets to lists for JSON serialization
        stats_to_save = self.stats.copy()
        if 'unique_documents' in stats_to_save:
            stats_to_save['unique_documents'] = list(stats_to_save['unique_documents'])
        
        try:
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(stats_to_save, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save statistics: {e}")
    
    def _compress_data(self, data: Any) -> bytes:
        """Compress data for storage"""
        if not self.config.STORAGE['enable_compression']:
            return pickle.dumps(data)
        
        try:
            serialized = pickle.dumps(data)
            compressed = zlib.compress(serialized, level=zlib.Z_BEST_COMPRESSION)
            return compressed
        except Exception:
            return pickle.dumps(data)
    
    def _decompress_data(self, data: bytes) -> Any:
        """Decompress data from storage"""
        if not self.config.STORAGE['enable_compression']:
            return pickle.loads(data)
        
        try:
            decompressed = zlib.decompress(data)
            return pickle.loads(decompressed)
        except Exception:
            return pickle.loads(data)
    
    def generate_abstention_id(self, 
                               context: AbstentionContext,
                               reason: str,
                               module_name: str) -> str:
        """Generate unique abstention ID from context"""
        # Create hash from key components
        hash_input = f"{context.pipeline_state}:{reason}:{module_name}:{context.timestamp.isoformat()}"
        hash_obj = hashlib.sha256(hash_input.encode())
        hash_hex = hash_obj.hexdigest()[:16]
        
        # Add timestamp and type prefix
        timestamp = context.timestamp.strftime("%Y%m%d%H%M%S")
        type_prefix = "kpk" if context.kpk_division else "gen"
        
        return f"abst_{type_prefix}_{timestamp}_{hash_hex}"
    
    def log_abstention(self,
                       abstention_type: AbstentionType,
                       reason: str,
                       context: AbstentionContext,
                       affected_entities: List[str],
                       pipeline_stage: PipelineStage,
                       module_name: str,
                       confidence_before: float,
                       confidence_threshold: Optional[float] = None,
                       severity: Optional[AbstentionSeverity] = None,
                       function_name: Optional[str] = None,
                       source_document: Optional[str] = None,
                       page_number: Optional[int] = None,
                       line_number: Optional[int] = None,
                       model_used: Optional[str] = None,
                       parameters: Optional[Dict[str, Any]] = None,
                       error_traceback: Optional[str] = None,
                       tags: Optional[List[str]] = None,
                       notes: Optional[str] = None,
                       execution_time_ms: Optional[float] = None,
                       memory_usage_mb: Optional[float] = None,
                       cpu_usage_percent: Optional[float] = None,
                       use_async: bool = True) -> str:
        """
        Log a new abstention with enhanced features
        
        Returns:
            abstention_id: Unique ID of the logged abstention
        """
        
        # Use default threshold if not provided
        if confidence_threshold is None:
            confidence_threshold = self.config.THRESHOLDS['confidence_threshold_default']
        
        # Auto-determine severity if not provided
        if severity is None:
            severity = self._auto_determine_severity(
                abstention_type, confidence_before, confidence_threshold, context
            )
        
        # Generate abstention ID
        abstention_id = self.generate_abstention_id(context, reason, module_name)
        
        # Create abstention record
        record = AbstentionRecord(
            abstention_id=abstention_id,
            abstention_type=abstention_type,
            severity=severity,
            timestamp=context.timestamp,
            pipeline_stage=pipeline_stage,
            module_name=module_name,
            function_name=function_name,
            
            reason=reason,
            context=context,
            affected_entities=affected_entities,
            source_document=source_document,
            page_number=page_number,
            line_number=line_number,
            
            confidence_before=confidence_before,
            confidence_threshold=confidence_threshold,
            
            system_version=context.system_version,
            model_used=model_used or context.model_used,
            parameters=parameters,
            
            error_traceback=error_traceback,
            tags=tags or [],
            notes=notes,
            
            execution_time_ms=execution_time_ms,
            memory_usage_mb=memory_usage_mb,
            cpu_usage_percent=cpu_usage_percent,
        )
        
        # Prepare record data for logging
        record_data = {
            'record': record,
            'timestamp': datetime.now(),
        }
        
        # Log asynchronously or synchronously
        if use_async and self.enable_async and self.async_logger:
            # Return async ID immediately
            async_id = self.async_logger.log_async(record_data)
            if async_id:
                return async_id
            # Fall back to sync if async fails
            self.logger.warning("Async logging failed, falling back to sync")
        
        # Synchronous logging
        return self._log_record_sync(record_data)
    
    def _log_record_sync(self, record_data: Dict[str, Any]) -> str:
        """Log record synchronously (internal use)"""
        record = record_data['record']
        
        try:
            # Log to all enabled outputs
            self._log_to_sqlite(record)
            self._log_to_json(record)
            self._log_to_csv(record)
            
            # Update statistics
            self._update_statistics(record)
            
            # Update cache
            self._update_cache(record)
            
            # Log success
            self.logger.info(
                f"Abstention logged: {record.abstention_id} - "
                f"{record.abstention_type.value} - {record.severity.value} - "
                f"Gap: {record.confidence_gap:.2f}"
            )
            
            return record.abstention_id
            
        except Exception as e:
            self.logger.error(f"Failed to log abstention: {e}", exc_info=True)
            
            # Return error ID
            return f"error_{hash(str(record_data))}"
    
    def _auto_determine_severity(self,
                                 abstention_type: AbstentionType,
                                 confidence_before: float,
                                 confidence_threshold: float,
                                 context: AbstentionContext) -> AbstentionSeverity:
        """Automatically determine severity with KPK considerations"""
        
        # Calculate confidence gap
        confidence_gap = confidence_threshold - confidence_before
        
        # Critical KPK issues
        critical_kpk_issues = set(self.config.KPK_SETTINGS['critical_kpk_issues'])
        if abstention_type.value in critical_kpk_issues:
            return AbstentionSeverity.CRITICAL
        
        # KPK division-specific severity adjustment
        severity_adjustment = 1.0
        if context.kpk_division and self.config.KPK_SETTINGS['enable_kpk_severity_weights']:
            division_val = context.kpk_division.value if hasattr(context.kpk_division, 'value') else str(context.kpk_division)
            division_weight = self.config.KPK_SETTINGS['kpk_division_weights'].get(
                division_val, 1.0
            )
            severity_adjustment *= division_weight
        
        # Adjust confidence gap for KPK
        adjusted_gap = confidence_gap * severity_adjustment
        
        # Determine severity based on adjusted gap
        if adjusted_gap > 0.5:
            return AbstentionSeverity.CRITICAL
        elif adjusted_gap > 0.3:
            return AbstentionSeverity.HIGH
        elif adjusted_gap > 0.15:
            return AbstentionSeverity.MEDIUM
        elif adjusted_gap > 0.05:
            return AbstentionSeverity.LOW
        else:
            return AbstentionSeverity.INFO
    
    def _log_to_sqlite(self, record: AbstentionRecord):
        """Log abstention to SQLite database with compression"""
        if not self.config.STORAGE['enable_sqlite']:
            return
        
        try:
            # Compress context data
            context_blob = self._compress_data(record.context.to_dict())
            
            # Prepare parameters
            params = (
                record.abstention_id,
                record.abstention_type.value,
                record.severity.value,
                record.timestamp.isoformat(),
                record.pipeline_stage.value,
                record.module_name,
                record.function_name,
                
                context_blob,
                
                record.reason,
                json.dumps(record.affected_entities, ensure_ascii=False),
                record.source_document,
                record.page_number,
                record.line_number,
                
                record.confidence_before,
                record.confidence_threshold,
                record.confidence_after,
                record.confidence_gap,
                
                record.kpk_relevance_score,
                1 if record.kpk_expert_needed else 0,
                record.kpk_division_context,
                
                record.system_version,
                record.model_used,
                json.dumps(record.parameters, ensure_ascii=False) if record.parameters else None,
                record.git_commit,
                
                record.review_status.value,
                record.reviewed_by,
                record.review_date.isoformat() if record.review_date else None,
                record.resolution,
                record.resolution_action,
                record.resolution_confidence,
                
                record.learning_feedback,
                1 if record.should_retrain else 0,
                record.retrain_priority,
                record.training_data_suggestion,
                
                record.error_traceback,
                record.input_hash,
                record.output_hash,
                record.execution_time_ms,
                
                json.dumps(record.tags, ensure_ascii=False),
                record.notes,
                json.dumps(record.linked_abstentions, ensure_ascii=False),
                
                record.memory_usage_mb,
                record.cpu_usage_percent,
            )
            
            self.cursor.execute('''
                INSERT OR REPLACE INTO abstentions (
                    abstention_id, abstention_type, severity, timestamp,
                    pipeline_stage, module_name, function_name,
                    context_data,
                    reason, affected_entities, source_document, page_number, line_number,
                    confidence_before, confidence_threshold, confidence_after, confidence_gap,
                    kpk_relevance_score, kpk_expert_needed, kpk_division_context,
                    system_version, model_used, parameters, git_commit,
                    review_status, reviewed_by, review_date, resolution, resolution_action, resolution_confidence,
                    learning_feedback, should_retrain, retrain_priority, training_data_suggestion,
                    error_traceback, input_hash, output_hash, execution_time_ms,
                    tags, notes, linked_abstentions,
                    memory_usage_mb, cpu_usage_percent
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', params)
            
            self.conn.commit()
            
        except Exception as e:
            self.logger.error(f"Failed to log to SQLite: {e}", exc_info=True)
            # Try to reconnect
            self._reconnect_sqlite()
    
    def _reconnect_sqlite(self):
        """Reconnect to SQLite database"""
        try:
            if hasattr(self, 'conn'):
                self.conn.close()
            
            db_path = Path(self.config.STORAGE['db_path'])
            self.conn = sqlite3.connect(db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
            
            self.logger.info("Reconnected to SQLite database")
            
        except Exception as e:
            self.logger.error(f"Failed to reconnect to SQLite: {e}")
            self.config.STORAGE['enable_sqlite'] = False
    
    def _log_to_json(self, record: AbstentionRecord):
        """Log abstention to JSON file with daily rotation"""
        if not self.config.STORAGE['enable_json']:
            return
        
        try:
            # Daily JSON files
            date_str = record.timestamp.strftime("%Y%m%d")
            json_file = self.log_dir / f"abstentions_{date_str}.json"
            
            # Load existing data or create new
            data = self._load_json_file(json_file)
            
            # Add new record
            if 'abstentions' not in data:
                data['abstentions'] = []
            
            # Limit record size for JSON
            record_dict = record.to_dict()
            # Truncate long fields
            if 'reason' in record_dict and len(record_dict['reason']) > 500:
                record_dict['reason'] = record_dict['reason'][:500] + "..."
            
            data['abstentions'].append(record_dict)
            
            # Keep only last 1000 records per file
            if len(data['abstentions']) > 1000:
                data['abstentions'] = data['abstentions'][-1000:]
                data['metadata']['truncated'] = True
            
            # Save back
            self._save_json_file(json_file, data)
            
        except Exception as e:
            self.logger.error(f"Failed to log to JSON: {e}")
    
    def _load_json_file(self, json_file: Path) -> Dict[str, Any]:
        """Load JSON file or create new structure"""
        if json_file.exists():
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                # File corrupted, create new
                pass
        
        # Create new structure
        return {
            "metadata": {
                "created": datetime.now().isoformat(),
                "system_version": "GreenLawAI-KPK v2.1",
                "file_type": "abstention_log"
            },
            "abstentions": []
        }
    
    def _save_json_file(self, json_file: Path, data: Dict[str, Any]):
        """Save JSON file with atomic write"""
        # Write to temporary file first
        temp_file = json_file.with_suffix('.tmp')
        
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Atomic rename
            temp_file.replace(json_file)
            
        except Exception as e:
            self.logger.error(f"Failed to save JSON file: {e}")
            # Clean up temp file
            if temp_file.exists():
                temp_file.unlink()
    
    def _log_to_csv(self, record: AbstentionRecord):
        """Log abstention to CSV file with daily rotation"""
        if not self.config.STORAGE['enable_csv']:
            return
        
        try:
            # Daily CSV files
            date_str = record.timestamp.strftime("%Y%m%d")
            csv_file = self.log_dir / f"abstentions_{date_str}.csv"
            
            # Prepare CSV record
            csv_record = {
                'abstention_id': record.abstention_id,
                'timestamp': record.timestamp.isoformat(),
                'abstention_type': record.abstention_type.value,
                'severity': record.severity.value,
                'pipeline_stage': record.pipeline_stage.value,
                'module_name': record.module_name,
                'function_name': record.function_name or '',
                'reason': record.reason[:100].replace('\n', ' ').replace('\r', ' '),
                'source_document': record.source_document or '',
                'page_number': record.page_number or '',
                'confidence_before': round(record.confidence_before, 3),
                'confidence_threshold': round(record.confidence_threshold, 3),
                'confidence_gap': round(record.confidence_gap, 3),
                'kpk_relevance_score': round(record.kpk_relevance_score, 3),
                'kpk_expert_needed': 'Yes' if record.kpk_expert_needed else 'No',
                'review_status': record.review_status.value,
                'affected_entities_count': len(record.affected_entities),
                'tags': ';'.join(record.tags[:5]) if record.tags else '',
            }
            
            # Write header if file doesn't exist
            write_header = not csv_file.exists()
            
            with open(csv_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=csv_record.keys())
                if write_header:
                    writer.writeheader()
                writer.writerow(csv_record)
            
            # Rotate file if too large (>10MB)
            if csv_file.exists() and csv_file.stat().st_size > 10 * 1024 * 1024:
                # Create new file with timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                new_name = csv_file.stem + f"_{timestamp}" + csv_file.suffix
                csv_file.rename(csv_file.parent / new_name)
                
        except Exception as e:
            self.logger.error(f"Failed to log to CSV: {e}")
    
    def _update_statistics(self, record: AbstentionRecord):
        """Update statistics with enhanced metrics"""
        # Basic counts
        self.stats['total_abstentions'] += 1
        
        # Type, severity, stage, status counts
        self.stats['by_type'][record.abstention_type.value] += 1
        self.stats['by_severity'][record.severity.value] += 1
        self.stats['by_stage'][record.pipeline_stage.value] += 1
        self.stats['by_status'][record.review_status.value] += 1
        
        # KPK-specific counts
        if record.context.kpk_division:
            self.stats['by_kpk_division'][record.context.kpk_division.value] += 1
        
        if record.kpk_relevance_score > 0.3:
            self.stats['kpk_related_count'] += 1
        
        if record.context.is_hazara:
            self.stats['hazara_related_count'] += 1
        
        if record.context.is_malakand:
            self.stats['malakand_related_count'] += 1
        
        if record.kpk_expert_needed:
            self.stats['kpk_expert_needed_count'] += 1
        
        # Resolution counts
        if record.review_status == ReviewStatus.MANUAL_RESOLVED:
            self.stats['resolved_count'] += 1
        elif record.review_status == ReviewStatus.PENDING:
            self.stats['pending_count'] += 1
        elif record.review_status == ReviewStatus.AUTO_RESOLVED:
            self.stats['auto_resolved_count'] += 1
        elif record.review_status == ReviewStatus.MANUAL_RESOLVED:
            self.stats['manual_resolved_count'] += 1
        elif record.review_status == ReviewStatus.ESCALATED:
            self.stats['escalated_count'] += 1
        
        # Confidence statistics
        gap = record.confidence_gap
        self.stats['avg_confidence_gap'] = (
            (self.stats['avg_confidence_gap'] * (self.stats['total_abstentions'] - 1) + gap)
            / self.stats['total_abstentions']
        )
        
        if gap > self.stats['max_confidence_gap']:
            self.stats['max_confidence_gap'] = gap
        
        if gap < self.stats['min_confidence_gap']:
            self.stats['min_confidence_gap'] = gap
        
        # Document statistics
        if record.source_document:
            self.stats['unique_documents'].add(record.source_document)
            
            # Count abstentions per document
            if record.source_document not in self.stats['documents_with_abstentions']:
                self.stats['documents_with_abstentions'][record.source_document] = 0
            self.stats['documents_with_abstentions'][record.source_document] += 1
        
        # Timeline statistics
        hour_str = record.timestamp.strftime("%H")
        self.stats['hourly_distribution'][hour_str] += 1
        
        date_str = record.timestamp.strftime("%Y-%m-%d")
        if date_str not in self.stats['daily_distribution']:
            self.stats['daily_distribution'][date_str] = 0
        self.stats['daily_distribution'][date_str] += 1
        
        # Update time-based counts
        now = datetime.now()
        record_date = record.timestamp.date()
        
        if record_date == now.date():
            self.stats['today_count'] += 1
        
        # Weekly count (last 7 days)
        week_ago = now - timedelta(days=7)
        if record.timestamp >= week_ago:
            self.stats['this_week_count'] += 1
        
        # Monthly count (last 30 days)
        month_ago = now - timedelta(days=30)
        if record.timestamp >= month_ago:
            self.stats['this_month_count'] += 1
        
        # Update last updated timestamp
        self.stats['last_updated'] = now.isoformat()
        
        # Save statistics periodically
        if self.stats['total_abstentions'] % 100 == 0:
            self._save_statistics()
    
    def _update_cache(self, record: AbstentionRecord):
        """Update in-memory cache"""
        # Add to recent abstentions cache
        self._cache['recent_abstentions'].append(record)
        
        # Keep only last 100 records in cache
        if len(self._cache['recent_abstentions']) > 100:
            self._cache['recent_abstentions'] = self._cache['recent_abstentions'][-100:]
        
        # Invalidate stats cache
        self._cache['stats_cache'] = None
        self._cache['stats_cache_time'] = None
    
    def get_abstention(self, abstention_id: str) -> Optional[AbstentionRecord]:
        """Retrieve an abstention by ID with caching"""
        # Check cache first
        for record in self._cache['recent_abstentions']:
            if record.abstention_id == abstention_id:
                return record
        
        # Query database
        if not self.config.STORAGE['enable_sqlite']:
            return None
        
        try:
            self.cursor.execute('''
                SELECT * FROM abstentions WHERE abstention_id = ?
            ''', (abstention_id,))
            
            row = self.cursor.fetchone()
            if not row:
                return None
            
            # Convert row to record
            record = self._row_to_record(row)
            
            # Add to cache
            self._cache['recent_abstentions'].append(record)
            if len(self._cache['recent_abstentions']) > 100:
                self._cache['recent_abstentions'] = self._cache['recent_abstentions'][-100:]
            
            return record
            
        except Exception as e:
            self.logger.error(f"Failed to get abstention: {e}")
            return None
    
    def _row_to_record(self, row) -> AbstentionRecord:
        """Convert SQLite row to AbstentionRecord"""
        # Extract context data
        context_data = None
        if row['context_data']:
            try:
                context_data = self._decompress_data(row['context_data'])
                if isinstance(context_data, dict):
                    context_data = AbstentionContext.from_dict(context_data)
            except Exception as e:
                self.logger.warning(f"Failed to decompress context: {e}")
                context_data = AbstentionContext(
                    pipeline_state='unknown',
                    processing_step='unknown',
                    module_state={}
                )
        
        # Parse affected entities
        affected_entities = []
        if row['affected_entities']:
            try:
                affected_entities = json.loads(row['affected_entities'])
            except Exception:
                affected_entities = []
        
        # Parse parameters
        parameters = None
        if row['parameters']:
            try:
                parameters = json.loads(row['parameters'])
            except Exception:
                parameters = None
        
        # Parse tags
        tags = []
        if row['tags']:
            try:
                tags = json.loads(row['tags'])
            except Exception:
                tags = []
        
        # Parse linked abstentions
        linked_abstentions = []
        if row['linked_abstentions']:
            try:
                linked_abstentions = json.loads(row['linked_abstentions'])
            except Exception:
                linked_abstentions = []
        
        # Create record
        record = AbstentionRecord(
            abstention_id=row['abstention_id'],
            abstention_type=AbstentionType(row['abstention_type']),
            severity=AbstentionSeverity(row['severity']),
            timestamp=datetime.fromisoformat(row['timestamp']),
            pipeline_stage=PipelineStage(row['pipeline_stage']),
            module_name=row['module_name'],
            function_name=row['function_name'],
            
            reason=row['reason'],
            context=context_data or AbstentionContext(
                pipeline_state='unknown',
                processing_step='unknown',
                module_state={}
            ),
            affected_entities=affected_entities,
            source_document=row['source_document'],
            page_number=row['page_number'],
            line_number=row['line_number'],
            
            confidence_before=row['confidence_before'],
            confidence_threshold=row['confidence_threshold'],
            confidence_after=row['confidence_after'],
            
            kpk_relevance_score=row['kpk_relevance_score'] or 0.0,
            kpk_expert_needed=bool(row['kpk_expert_needed']),
            kpk_division_context=row['kpk_division_context'],
            
            system_version=row['system_version'],
            model_used=row['model_used'],
            parameters=parameters,
            git_commit=row['git_commit'],
            
            review_status=ReviewStatus(row['review_status']),
            reviewed_by=row['reviewed_by'],
            review_date=datetime.fromisoformat(row['review_date']) if row['review_date'] else None,
            resolution=row['resolution'],
            resolution_action=row['resolution_action'],
            resolution_confidence=row['resolution_confidence'],
            
            learning_feedback=row['learning_feedback'],
            should_retrain=bool(row['should_retrain']),
            retrain_priority=row['retrain_priority'] or 0,
            training_data_suggestion=row['training_data_suggestion'],
            
            error_traceback=row['error_traceback'],
            input_hash=row['input_hash'],
            output_hash=row['output_hash'],
            execution_time_ms=row['execution_time_ms'],
            
            tags=tags,
            notes=row['notes'],
            linked_abstentions=linked_abstentions,
            
            memory_usage_mb=row['memory_usage_mb'],
            cpu_usage_percent=row['cpu_usage_percent'],
        )
        
        return record
    
    def update_review_status(self, 
                            abstention_id: str,
                            review_status: ReviewStatus,
                            reviewed_by: Optional[str] = None,
                            resolution: Optional[str] = None,
                            resolution_action: Optional[str] = None,
                            resolution_confidence: Optional[float] = None,
                            learning_feedback: Optional[str] = None,
                            should_retrain: bool = False,
                            retrain_priority: int = 0,
                            training_data_suggestion: Optional[str] = None):
        """Update the review status of an abstention with enhanced tracking"""
        
        # Get the record first
        record = self.get_abstention(abstention_id)
        if not record:
            self.logger.warning(f"Abstention {abstention_id} not found")
            return False
        
        old_status = record.review_status
        
        # Update record
        record.review_status = review_status
        record.reviewed_by = reviewed_by
        record.review_date = datetime.now()
        record.resolution = resolution
        record.resolution_action = resolution_action
        record.resolution_confidence = resolution_confidence
        record.learning_feedback = learning_feedback
        record.should_retrain = should_retrain
        record.retrain_priority = retrain_priority
        record.training_data_suggestion = training_data_suggestion
        
        # Update in SQLite
        if self.config.STORAGE['enable_sqlite']:
            try:
                self.cursor.execute('''
                    UPDATE abstentions SET
                        review_status = ?,
                        reviewed_by = ?,
                        review_date = ?,
                        resolution = ?,
                        resolution_action = ?,
                        resolution_confidence = ?,
                        learning_feedback = ?,
                        should_retrain = ?,
                        retrain_priority = ?,
                        training_data_suggestion = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE abstention_id = ?
                ''', (
                    review_status.value,
                    reviewed_by,
                    record.review_date.isoformat(),
                    resolution,
                    resolution_action,
                    resolution_confidence,
                    learning_feedback,
                    1 if should_retrain else 0,
                    retrain_priority,
                    training_data_suggestion,
                    abstention_id
                ))
                
                self.conn.commit()
                
                # Update statistics
                self._update_review_statistics(old_status, review_status, record)
                
                # Update cache
                self._update_cache(record)
                
                self.logger.info(f"Updated abstention {abstention_id} from {old_status.value} to {review_status.value}")
                return True
                
            except Exception as e:
                self.logger.error(f"Failed to update abstention: {e}")
                return False
        
        return False
    
    def _update_review_statistics(self, 
                                  old_status: ReviewStatus, 
                                  new_status: ReviewStatus,
                                  record: AbstentionRecord):
        """Update statistics after review status change"""
        # Update status counts
        self.stats['by_status'][old_status.value] = max(0, self.stats['by_status'][old_status.value] - 1)
        self.stats['by_status'][new_status.value] += 1
        
        # Update resolution counts
        if old_status == ReviewStatus.PENDING and new_status != ReviewStatus.PENDING:
            self.stats['pending_count'] = max(0, self.stats['pending_count'] - 1)
        
        if new_status == ReviewStatus.RESOLVED:
            self.stats['resolved_count'] += 1
        elif new_status == ReviewStatus.AUTO_RESOLVED:
            self.stats['auto_resolved_count'] += 1
        elif new_status == ReviewStatus.MANUAL_RESOLVED:
            self.stats['manual_resolved_count'] += 1
        elif new_status == ReviewStatus.ESCALATED:
            self.stats['escalated_count'] += 1
        
        # Update KPK expert needed count
        if record.kpk_expert_needed and new_status in [ReviewStatus.RESOLVED, ReviewStatus.MANUAL_RESOLVED]:
            self.stats['kpk_expert_needed_count'] = max(0, self.stats['kpk_expert_needed_count'] - 1)
        
        # Save statistics
        self._save_statistics()
    
    def query_abstentions(self,
                         abstention_type: Optional[AbstentionType] = None,
                         severity: Optional[AbstentionSeverity] = None,
                         pipeline_stage: Optional[PipelineStage] = None,
                         review_status: Optional[ReviewStatus] = None,
                         module_name: Optional[str] = None,
                         source_document: Optional[str] = None,
                         kpk_expert_needed: Optional[bool] = None,
                         min_kpk_relevance: Optional[float] = None,
                         min_confidence_gap: Optional[float] = None,
                         max_confidence_gap: Optional[float] = None,
                         start_date: Optional[datetime] = None,
                         end_date: Optional[datetime] = None,
                         tags: Optional[List[str]] = None,
                         limit: int = 100,
                         offset: int = 0,
                         order_by: str = "timestamp",
                         order_desc: bool = True) -> List[AbstentionRecord]:
        """Query abstentions with enhanced filters"""
        
        if not self.config.STORAGE['enable_sqlite']:
            return []
        
        try:
            query = "SELECT * FROM abstentions WHERE 1=1"
            params = []
            
            # Build WHERE clause
            if abstention_type:
                query += " AND abstention_type = ?"
                params.append(abstention_type.value)
            
            if severity:
                query += " AND severity = ?"
                params.append(severity.value)
            
            if pipeline_stage:
                query += " AND pipeline_stage = ?"
                params.append(pipeline_stage.value)
            
            if review_status:
                query += " AND review_status = ?"
                params.append(review_status.value)
            
            if module_name:
                query += " AND module_name = ?"
                params.append(module_name)
            
            if source_document:
                query += " AND source_document = ?"
                params.append(source_document)
            
            if kpk_expert_needed is not None:
                query += " AND kpk_expert_needed = ?"
                params.append(1 if kpk_expert_needed else 0)
            
            if min_kpk_relevance is not None:
                query += " AND kpk_relevance_score >= ?"
                params.append(min_kpk_relevance)
            
            if min_confidence_gap is not None:
                query += " AND confidence_gap >= ?"
                params.append(min_confidence_gap)
            
            if max_confidence_gap is not None:
                query += " AND confidence_gap <= ?"
                params.append(max_confidence_gap)
            
            if start_date:
                query += " AND timestamp >= ?"
                params.append(start_date.isoformat())
            
            if end_date:
                query += " AND timestamp <= ?"
                params.append(end_date.isoformat())
            
            if tags:
                for tag in tags:
                    query += " AND tags LIKE ?"
                    params.append(f'%"{tag}"%')
            
            # Order by
            order_by_map = {
                'timestamp': 'timestamp',
                'confidence_gap': 'confidence_gap',
                'severity': 'severity',
                'kpk_relevance': 'kpk_relevance_score',
            }
            
            order_field = order_by_map.get(order_by, 'timestamp')
            order_dir = 'DESC' if order_desc else 'ASC'
            query += f" ORDER BY {order_field} {order_dir}"
            
            # Limit and offset
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            self.cursor.execute(query, params)
            rows = self.cursor.fetchall()
            
            records = []
            for row in rows:
                record = self._row_to_record(row)
                records.append(record)
            
            return records
            
        except Exception as e:
            self.logger.error(f"Failed to query abstentions: {e}")
            return []
    
    def get_statistics(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get comprehensive statistics with caching"""
        # Check cache
        if (not force_refresh and 
            self._cache['stats_cache'] is not None and 
            self._cache['stats_cache_time'] is not None):
            
            cache_age = datetime.now() - self._cache['stats_cache_time']
            if cache_age.total_seconds() < 60:  # 1 minute cache
                return self._cache['stats_cache']
        
        # Calculate enhanced statistics
        stats = self.stats.copy()
        
        # Add calculated metrics
        total = stats['total_abstentions']
        if total > 0:
            stats['resolution_rate'] = stats['resolved_count'] / total
            stats['pending_rate'] = stats['pending_count'] / total
            stats['kpk_issue_rate'] = stats['kpk_related_count'] / total
            stats['expert_needed_rate'] = stats['kpk_expert_needed_count'] / total
            
            # Calculate severity distribution
            severity_total = sum(stats['by_severity'].values())
            if severity_total > 0:
                stats['severity_distribution'] = {
                    sev: count / severity_total
                    for sev, count in stats['by_severity'].items()
                }
        
        # Top issues with percentages
        type_items = [(k, v) for k, v in stats['by_type'].items() if v > 0]
        type_items.sort(key=lambda x: x[1], reverse=True)
        stats['top_abstention_types'] = [
            {'type': k, 'count': v, 'percentage': v/total if total > 0 else 0}
            for k, v in type_items[:10]
        ]
        
        # Top modules with issues
        if self.config.STORAGE['enable_sqlite']:
            try:
                self.cursor.execute('''
                    SELECT module_name, COUNT(*) as count, AVG(confidence_gap) as avg_gap
                    FROM abstentions
                    GROUP BY module_name
                    ORDER BY count DESC
                    LIMIT 10
                ''')
                module_stats = []
                for row in self.cursor.fetchall():
                    module_stats.append({
                        'module': row['module_name'],
                        'count': row['count'],
                        'avg_confidence_gap': row['avg_gap']
                    })
                stats['top_modules'] = module_stats
            except Exception as e:
                self.logger.warning(f"Could not get module stats: {e}")
        
        # KPK division analysis
        division_items = [(k, v) for k, v in stats['by_kpk_division'].items() if v > 0]
        division_items.sort(key=lambda x: x[1], reverse=True)
        stats['kpk_division_analysis'] = division_items[:5]
        
        # Document analysis
        doc_items = list(stats['documents_with_abstentions'].items())
        doc_items.sort(key=lambda x: x[1], reverse=True)
        stats['top_problem_documents'] = [
            {'document': k, 'count': v}
            for k, v in doc_items[:5]
        ]
        
        # Performance metrics
        stats['performance_metrics'] = {
            'avg_confidence_gap': round(stats['avg_confidence_gap'], 3),
            'max_confidence_gap': round(stats['max_confidence_gap'], 3),
            'min_confidence_gap': round(stats['min_confidence_gap'], 3),
            'total_processing_time_ms': stats.get('total_processing_time_ms', 0),
        }
        
        # Async logger stats if enabled
        if self.async_logger:
            async_stats = self.async_logger.get_stats()
            stats['async_logger_stats'] = async_stats
        
        # Cache the results
        self._cache['stats_cache'] = stats
        self._cache['stats_cache_time'] = datetime.now()
        
        return stats
    
    def generate_report(self, 
                       report_type: str = "daily",
                       output_format: str = "json",
                       include_details: bool = True) -> Optional[Dict[str, Any]]:
        """Generate abstention report with KPK focus"""
        
        today = datetime.now()
        
        # Determine time period
        if report_type == "daily":
            start_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = today.replace(hour=23, minute=59, second=59, microsecond=999999)
            period = "daily"
        elif report_type == "weekly":
            start_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
            start_date = start_date.replace(day=start_date.day - start_date.weekday())
            end_date = start_date.replace(day=start_date.day + 6, hour=23, minute=59, second=59, microsecond=999999)
            period = "weekly"
        elif report_type == "monthly":
            start_date = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end_date = today.replace(hour=23, minute=59, second=59, microsecond=999999)
            period = "monthly"
        elif report_type == "kpk_focus":
            # Last 30 days with KPK focus
            start_date = today - timedelta(days=30)
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = today.replace(hour=23, minute=59, second=59, microsecond=999999)
            period = "kpk_focus_30d"
        else:
            start_date = datetime.min
            end_date = datetime.max
            period = "all_time"
        
        # Get abstentions for period
        abstentions = self.query_abstentions(
            start_date=start_date, 
            end_date=end_date, 
            limit=1000,
            order_by="severity" if report_type == "kpk_focus" else "timestamp",
            order_desc=True
        )
        
        # Calculate KPK-specific metrics
        kpk_abstentions = [r for r in abstentions if r.kpk_relevance_score > 0.3]
        hazara_abstentions = [r for r in abstentions if r.context.is_hazara]
        malakand_abstentions = [r for r in abstentions if r.context.is_malakand]
        expert_needed = [r for r in abstentions if r.kpk_expert_needed]
        
        # Calculate period statistics
        period_stats = {
            'total': len(abstentions),
            'kpk_related': len(kpk_abstentions),
            'hazara_related': len(hazara_abstentions),
            'malakand_related': len(malakand_abstentions),
            'expert_needed': len(expert_needed),
            'by_type': Counter(r.abstention_type.value for r in abstentions),
            'by_severity': Counter(r.severity.value for r in abstentions),
            'by_stage': Counter(r.pipeline_stage.value for r in abstentions),
            'by_status': Counter(r.review_status.value for r in abstentions),
            'avg_confidence_gap': sum(r.confidence_gap for r in abstentions) / len(abstentions) if abstentions else 0,
            'max_confidence_gap': max((r.confidence_gap for r in abstentions), default=0),
            'unique_documents': len(set(r.source_document for r in abstentions if r.source_document)),
        }
        
        # Create report
        report = {
            'report_id': f"abstention_report_{period}_{today.strftime('%Y%m%d_%H%M%S')}",
            'generated_at': today.isoformat(),
            'period': period,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            
            'executive_summary': {
                'total_abstentions': period_stats['total'],
                'kpk_related_percentage': period_stats['kpk_related'] / period_stats['total'] * 100 if period_stats['total'] > 0 else 0,
                'expert_needed_percentage': period_stats['expert_needed'] / period_stats['total'] * 100 if period_stats['total'] > 0 else 0,
                'resolution_rate': period_stats['by_status'].get('resolved', 0) / period_stats['total'] * 100 if period_stats['total'] > 0 else 0,
                'avg_confidence_gap': round(period_stats['avg_confidence_gap'], 3),
                'key_issue': max(period_stats['by_type'].items(), key=lambda x: x[1])[0] if period_stats['by_type'] else 'none',
            },
            
            'kpk_focus': {
                'hazara_issues': period_stats['hazara_related'],
                'malakand_issues': period_stats['malakand_related'],
                'expert_backlog': len([r for r in expert_needed if r.review_status == ReviewStatus.PENDING]),
                'top_kpk_issues': sorted(
                    [(k, v) for k, v in period_stats['by_type'].items() if any(kpk_term in k for kpk_term in ['kpk', 'hazara', 'malakand'])],
                    key=lambda x: x[1],
                    reverse=True
                )[:5],
            },
            
            'detailed_statistics': period_stats,
            
            'recommendations': self._generate_recommendations(period_stats, abstentions, report_type),
            
            'action_items': self._generate_action_items(abstentions),
        }
        
        # Include details if requested
        if include_details:
            report['sample_abstentions'] = [r.get_summary() for r in abstentions[:10]]
            
            # Critical issues requiring immediate attention
            critical_issues = [
                r.get_summary() for r in abstentions 
                if r.severity in [AbstentionSeverity.CRITICAL, AbstentionSeverity.BLOCKER]
                and r.review_status == ReviewStatus.PENDING
            ][:5]
            
            if critical_issues:
                report['critical_issues'] = critical_issues
        
        # Save report
        report_file = self.log_dir / f"reports/{period}_report_{today.strftime('%Y%m%d')}.{output_format}"
        report_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            if output_format == "json":
                with open(report_file, 'w', encoding='utf-8') as f:
                    json.dump(report, f, indent=2, ensure_ascii=False)
            elif output_format == "html":
                html_report = self._generate_html_report(report)
                with open(report_file, 'w', encoding='utf-8') as f:
                    f.write(html_report)
            elif output_format == "csv":
                # Flatten for CSV
                csv_data = []
                for rec in abstentions:
                    csv_data.append({
                        'id': rec.abstention_id,
                        'timestamp': rec.timestamp.isoformat(),
                        'type': rec.abstention_type.value,
                        'severity': rec.severity.value,
                        'stage': rec.pipeline_stage.value,
                        'module': rec.module_name,
                        'reason': rec.reason[:50],
                        'document': rec.source_document or '',
                        'kpk_relevance': round(rec.kpk_relevance_score, 3),
                        'expert_needed': 'Yes' if rec.kpk_expert_needed else 'No',
                        'status': rec.review_status.value,
                        'confidence_gap': round(rec.confidence_gap, 3),
                    })
                
                with open(report_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=csv_data[0].keys())
                    writer.writeheader()
                    writer.writerows(csv_data)
            
            self.logger.info(f"Generated {period} report: {report_file}")
            return report
            
        except Exception as e:
            self.logger.error(f"Failed to generate report: {e}")
            return None
    
    def _generate_recommendations(self, 
                                 period_stats: Dict[str, Any],
                                 abstentions: List[AbstentionRecord],
                                 report_type: str) -> List[Dict[str, str]]:
        """Generate recommendations based on abstention patterns"""
        recommendations = []
        
        # KPK-specific recommendations
        if report_type == "kpk_focus" or period_stats['kpk_related'] > period_stats['total'] * 0.3:
            if period_stats['expert_needed'] > 5:
                recommendations.append({
                    'area': 'KPK Expertise',
                    'recommendation': 'Allocate KPK forestry expert time for review',
                    'priority': 'high',
                    'impact': 'High accuracy improvement for KPK documents',
                })
            
            if period_stats['hazara_related'] > period_stats['malakand_related'] * 2:
                recommendations.append({
                    'area': 'Hazara Focus',
                    'recommendation': 'Prioritize improvements for Hazara-specific processing',
                    'priority': 'medium',
                    'impact': 'Better handling of Hazara Forest Act and related documents',
                })
        
        # System improvement recommendations
        for atype, count in period_stats['by_type'].items():
            if count > 20:  # High frequency threshold
                recommendations.append({
                    'area': f'System Improvement - {atype}',
                    'recommendation': f'Investigate root cause of frequent {atype} abstentions',
                    'priority': 'high' if count > 50 else 'medium',
                    'impact': f'Reduce {count} instances of {atype}',
                })
        
        # Confidence gap recommendations
        high_gap_count = len([r for r in abstentions if r.confidence_gap > 0.4])
        if high_gap_count > 10:
            recommendations.append({
                'area': 'Confidence Thresholds',
                'recommendation': 'Review and adjust confidence thresholds for high-gap cases',
                'priority': 'medium',
                'impact': f'Address {high_gap_count} cases with confidence gap > 0.4',
            })
        
        # Module-specific recommendations
        module_counts = Counter(r.module_name for r in abstentions)
        for module, count in module_counts.most_common(3):
            if count > 10:
                recommendations.append({
                    'area': f'Module Improvement - {module}',
                    'recommendation': f'Review and optimize {module} for better accuracy',
                    'priority': 'medium',
                    'impact': f'Reduce {count} abstentions from {module}',
                })
        
        return recommendations
    
    def _generate_action_items(self, abstentions: List[AbstentionRecord]) -> List[Dict[str, Any]]:
        """Generate actionable items from abstentions"""
        action_items = []
        
        # Critical pending issues
        critical_pending = [
            r for r in abstentions 
            if r.severity in [AbstentionSeverity.CRITICAL, AbstentionSeverity.BLOCKER]
            and r.review_status == ReviewStatus.PENDING
        ]
        
        if critical_pending:
            action_items.append({
                'type': 'critical_review',
                'description': f'Review {len(critical_pending)} critical/high severity pending abstentions',
                'deadline': 'ASAP',
                'assigned_to': 'KPK Expert',
                'priority': 1,
            })
        
        # KPK expert needed
        expert_needed = [r for r in abstentions if r.kpk_expert_needed and r.review_status == ReviewStatus.PENDING]
        if expert_needed:
            action_items.append({
                'type': 'kpk_expert_review',
                'description': f'Review {len(expert_needed)} KPK-specific abstentions requiring expert input',
                'deadline': 'Within 3 days',
                'assigned_to': 'KPK Forestry Expert',
                'priority': 2,
            })
        
        # High frequency modules
        module_counts = Counter(r.module_name for r in abstentions if r.review_status == ReviewStatus.PENDING)
        for module, count in module_counts.most_common(3):
            if count > 5:
                action_items.append({
                    'type': 'module_optimization',
                    'description': f'Optimize {module} module (causing {count} pending abstentions)',
                    'deadline': 'Next sprint',
                    'assigned_to': 'Development Team',
                    'priority': 3,
                })
        
        return action_items
    
    def _generate_html_report(self, report: Dict[str, Any]) -> str:
        """Generate HTML version of report"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Abstention Report - {report['period']}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ color: #2c3e50; }}
                h2 {{ color: #34495e; border-bottom: 2px solid #3498db; padding-bottom: 5px; }}
                .summary {{ background: #ecf0f1; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
                .metric {{ display: inline-block; margin-right: 20px; padding: 10px; background: white; border-radius: 5px; }}
                .metric-value {{ font-size: 24px; font-weight: bold; color: #2980b9; }}
                .metric-label {{ font-size: 12px; color: #7f8c8d; }}
                table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
                th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background-color: #3498db; color: white; }}
                .critical {{ background-color: #e74c3c; color: white; }}
                .high {{ background-color: #e67e22; color: white; }}
                .medium {{ background-color: #f39c12; color: white; }}
                .low {{ background-color: #f1c40f; }}
                .info {{ background-color: #3498db; color: white; }}
            </style>
        </head>
        <body>
            <h1>Abstention Report - {report['period']}</h1>
            <p>Generated: {report['generated_at']}</p>
            
            <div class="summary">
                <h2>Executive Summary</h2>
                <div class="metric">
                    <div class="metric-value">{report['executive_summary']['total_abstentions']}</div>
                    <div class="metric-label">Total Abstentions</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{report['executive_summary']['kpk_related_percentage']:.1f}%</div>
                    <div class="metric-label">KPK Related</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{report['executive_summary']['resolution_rate']:.1f}%</div>
                    <div class="metric-label">Resolution Rate</div>
                </div>
            </div>
            
            <h2>KPK Focus</h2>
            <table>
                <tr>
                    <th>Metric</th>
                    <th>Value</th>
                </tr>
                <tr>
                    <td>Hazara-related Issues</td>
                    <td>{report['kpk_focus']['hazara_issues']}</td>
                </tr>
                <tr>
                    <td>Malakand-related Issues</td>
                    <td>{report['kpk_focus']['malakand_issues']}</td>
                </tr>
                <tr>
                    <td>Expert Backlog</td>
                    <td>{report['kpk_focus']['expert_backlog']}</td>
                </tr>
            </table>
            
            <h2>Top Issues</h2>
            <table>
                <tr>
                    <th>Issue Type</th>
                    <th>Count</th>
                    <th>Percentage</th>
                </tr>
        """
        
        for issue in report.get('top_issues', []):
            html += f"""
                <tr>
                    <td>{issue['type']}</td>
                    <td>{issue['count']}</td>
                    <td>{issue['percentage']:.1%}</td>
                </tr>
            """
        
        html += """
            </table>
            
            <h2>Recommendations</h2>
            <table>
                <tr>
                    <th>Area</th>
                    <th>Recommendation</th>
                    <th>Priority</th>
                    <th>Impact</th>
                </tr>
        """
        
        for rec in report.get('recommendations', []):
            priority_class = rec['priority']
            html += f"""
                <tr class="{priority_class}">
                    <td>{rec['area']}</td>
                    <td>{rec['recommendation']}</td>
                    <td>{rec['priority'].upper()}</td>
                    <td>{rec.get('impact', '')}</td>
                </tr>
            """
        
        html += """
            </table>
        </body>
        </html>
        """
        
        return html
    
    def cleanup_old_records(self, days_to_keep: int = None):
        """Cleanup old abstention records with archive"""
        if days_to_keep is None:
            days_to_keep = self.config.STORAGE['archive_after_days']
        
        cutoff_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff_date = cutoff_date.replace(day=cutoff_date.day - days_to_keep)
        
        if not self.config.STORAGE['enable_sqlite']:
            return
        
        try:
            # Archive old records first
            self.cursor.execute('''
                SELECT * FROM abstentions 
                WHERE timestamp < ? 
                AND review_status != 'pending'
                AND review_status != 'in_review'
            ''', (cutoff_date.isoformat(),))
            
            old_records = self.cursor.fetchall()
            
            # Archive to compressed JSON
            if old_records:
                archive_date = cutoff_date.strftime('%Y%m%d')
                archive_file = self.log_dir / f"archive/abstentions_archive_{archive_date}.json.gz"
                archive_file.parent.mkdir(parents=True, exist_ok=True)
                
                archive_data = {
                    'archived_at': datetime.now().isoformat(),
                    'cutoff_date': cutoff_date.isoformat(),
                    'total_records': len(old_records),
                    'records': []
                }
                
                # Sample records for archive (limit to 1000)
                sample_size = min(1000, len(old_records))
                for i, row in enumerate(old_records[:sample_size]):
                    if i % 10 == 0:  # Sample every 10th record
                        record = self._row_to_record(row)
                        archive_data['records'].append(record.get_summary())
                
                # Compress and save
                import gzip
                with gzip.open(archive_file, 'wt', encoding='utf-8') as f:
                    json.dump(archive_data, f, ensure_ascii=False)
                
                # Delete from database
                self.cursor.execute('''
                    DELETE FROM abstentions 
                    WHERE timestamp < ? 
                    AND review_status != 'pending'
                    AND review_status != 'in_review'
                ''', (cutoff_date.isoformat(),))
                
                deleted_count = self.cursor.rowcount
                self.conn.commit()
                
                # Vacuum database to reclaim space
                self.cursor.execute('VACUUM')
                
                self.logger.info(f"Archived {deleted_count} old abstention records to {archive_file}")
            
            # Also cleanup old JSON and CSV files
            self._cleanup_old_files(days_to_keep)
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup old records: {e}")
    
    def _cleanup_old_files(self, days_to_keep: int):
        """Cleanup old log files"""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        try:
            # Cleanup old JSON files
            for json_file in self.log_dir.glob("abstentions_*.json"):
                try:
                    file_date_str = json_file.stem.replace("abstentions_", "")
                    file_date = datetime.strptime(file_date_str, "%Y%m%d")
                    if file_date < cutoff_date:
                        json_file.unlink()
                        self.logger.debug(f"Deleted old JSON file: {json_file}")
                except (ValueError, Exception):
                    continue
            
            # Cleanup old CSV files
            for csv_file in self.log_dir.glob("abstentions_*.csv"):
                try:
                    file_date_str = csv_file.stem.replace("abstentions_", "")
                    file_date = datetime.strptime(file_date_str, "%Y%m%d")
                    if file_date < cutoff_date:
                        csv_file.unlink()
                        self.logger.debug(f"Deleted old CSV file: {csv_file}")
                except (ValueError, Exception):
                    continue
                    
        except Exception as e:
            self.logger.warning(f"Failed to cleanup old files: {e}")
    
    def export_data(self, 
                   format: str = "json",
                   output_file: Optional[Path] = None,
                   filters: Optional[Dict[str, Any]] = None) -> Optional[Path]:
        """Export abstention data in various formats"""
        if filters is None:
            filters = {}
        
        # Apply filters to query
        abstentions = self.query_abstentions(
            abstention_type=filters.get('abstention_type'),
            severity=filters.get('severity'),
            pipeline_stage=filters.get('pipeline_stage'),
            review_status=filters.get('review_status'),
            start_date=filters.get('start_date'),
            end_date=filters.get('end_date'),
            limit=filters.get('limit', 1000),
            order_by=filters.get('order_by', 'timestamp'),
            order_desc=filters.get('order_desc', True)
        )
        
        if not abstentions:
            self.logger.warning("No abstentions to export")
            return None
        
        # Determine output file
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self.log_dir / f"exports/abstentions_export_{timestamp}.{format}"
        
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            if format == "json":
                export_data = {
                    'metadata': {
                        'export_date': datetime.now().isoformat(),
                        'total_records': len(abstentions),
                        'filters': filters,
                        'system_version': 'GreenLawAI-KPK v2.1',
                    },
                    'records': [r.to_dict() for r in abstentions]
                }
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            elif format == "csv":
                # Prepare CSV data
                csv_data = []
                for record in abstentions:
                    csv_data.append({
                        'id': record.abstention_id,
                        'timestamp': record.timestamp.isoformat(),
                        'type': record.abstention_type.value,
                        'severity': record.severity.value,
                        'stage': record.pipeline_stage.value,
                        'module': record.module_name,
                        'reason': record.reason[:200],
                        'document': record.source_document or '',
                        'confidence_gap': round(record.confidence_gap, 3),
                        'kpk_relevance': round(record.kpk_relevance_score, 3),
                        'expert_needed': 'Yes' if record.kpk_expert_needed else 'No',
                        'status': record.review_status.value,
                        'resolution': record.resolution or '',
                        'tags': ';'.join(record.tags),
                    })
                
                with open(output_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=csv_data[0].keys())
                    writer.writeheader()
                    writer.writerows(csv_data)
            
            elif format == "sql":
                # Export as SQL insert statements
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write("-- Abstention Data Export\n")
                    f.write(f"-- Generated: {datetime.now().isoformat()}\n")
                    f.write(f"-- Total Records: {len(abstentions)}\n\n")
                    
                    for record in abstentions:
                        # Simplified SQL export
                        f.write(f"INSERT INTO abstentions (abstention_id, abstention_type, reason) VALUES (")
                        f.write(f"'{record.abstention_id}', ")
                        f.write(f"'{record.abstention_type.value}', ")
                        reason_clean = record.reason[:100].replace("'", "''")
                        f.write(f"'{reason_clean}');\n")

            
            self.logger.info(f"Exported {len(abstentions)} abstentions to {output_file}")
            return output_file
            
        except Exception as e:
            self.logger.error(f"Failed to export data: {e}")
            return None
    
    def close(self):
        """Close database connections and cleanup"""
        # Stop async logger
        if self.async_logger:
            self.async_logger.stop()
        
        # Close database connections
        if hasattr(self, 'conn'):
            self.conn.close()
        
        # Save statistics
        self._save_statistics()
        
        self.logger.info("Abstention logger closed")


# ============================================================================
# HELPER FUNCTIONS (ENHANCED)
# ============================================================================

def create_abstention_context(
    pipeline_state: str,
    processing_step: str,
    module_state: Dict[str, Any],
    kpk_metadata: Optional[Dict[str, Any]] = None,
    document_profile: Optional[Dict[str, Any]] = None,
    **kwargs
) -> AbstentionContext:
    """Create standardized context data for abstention logging"""
    
    context = AbstentionContext(
        pipeline_state=pipeline_state,
        processing_step=processing_step,
        module_state=module_state,
    )
    
    # Add KPK metadata if available
    if kpk_metadata:
        context.kpk_division = KPKDivision(kpk_metadata.get('division', 'unknown'))
        context.kpk_district = kpk_metadata.get('district')
        context.is_hazara = kpk_metadata.get('is_hazara', False)
        context.is_malakand = kpk_metadata.get('is_malakand', False)
    
    # Add document profile information
    if document_profile:
        context.document_type = document_profile.get('document_type')
        context.document_year = document_profile.get('year')
        context.document_quality = document_profile.get('quality')
        context.language_mix = document_profile.get('language_mix')
    
    # Add processing context
    if 'input_summary' in kwargs:
        context.input_summary = kwargs['input_summary']
    
    if 'text_preview' in kwargs:
        context.text_preview = kwargs['text_preview']
    
    if 'entity_count' in kwargs:
        context.entity_count = kwargs['entity_count']
    
    if 'confidence_scores' in kwargs:
        context.confidence_scores = kwargs['confidence_scores']
    
    if 'model_used' in kwargs:
        context.model_used = kwargs['model_used']
    
    # Add parameters hash for reproducibility
    if 'parameters' in kwargs:
        import json
        params_str = json.dumps(kwargs['parameters'], sort_keys=True)
        context.parameters_hash = hashlib.md5(params_str.encode()).hexdigest()[:8]
    
    return context


# ============================================================================
# QUICK LOGGING FUNCTIONS (For easy integration)
# ============================================================================

# Global logger instance with lazy initialization
_global_logger = None
_logger_lock = threading.Lock()

def get_global_logger(config: Optional[Dict] = None) -> AbstentionLogger:
    """Get or create global abstention logger with thread safety"""
    global _global_logger
    
    with _logger_lock:
        if _global_logger is None:
            _global_logger = AbstentionLogger(config=config)
        
        return _global_logger

def set_global_logger(logger: AbstentionLogger):
    """Set global abstention logger instance"""
    global _global_logger
    
    with _logger_lock:
        # Close existing logger if any
        if _global_logger:
            _global_logger.close()
        
        _global_logger = logger

def log_quick_abstention(
    abstention_type: Union[str, AbstentionType],
    reason: str,
    module_name: str,
    confidence: float,
    threshold: float = None,
    pipeline_stage: Union[str, PipelineStage] = None,
    severity: Union[str, AbstentionSeverity] = None,
    kpk_metadata: Optional[Dict] = None,
    document_profile: Optional[Dict] = None,
    **kwargs
) -> str:
    """
    Quick abstention logging for common cases with enhanced features
    
    Example:
        abstention_id = log_quick_abstention(
            "poor_ocr_quality",
            "OCR confidence below threshold for Hazara document",
            "extract_layout.py",
            0.45,
            threshold=0.7,
            pipeline_stage="document_extraction",
            kpk_metadata={'division': 'hazara', 'is_hazara': True},
            document_profile={'document_type': 'ordinance', 'year': 2002},
            source_document="hazara_forest_act.pdf",
            page_number=15,
            tags=["ocr", "hazara", "scanned"]
        )
    """
    logger = get_global_logger()
    
    # Convert string to enum if needed
    if isinstance(abstention_type, str):
        try:
            abstention_type = AbstentionType(abstention_type)
        except ValueError:
            abstention_type = AbstentionType.OTHER
    
    # Convert pipeline stage if string
    if isinstance(pipeline_stage, str):
        try:
            pipeline_stage = PipelineStage(pipeline_stage)
        except ValueError:
            # Try to infer from module name
            if "extract" in module_name.lower():
                pipeline_stage = PipelineStage.DOCUMENT_EXTRACTION
            elif "clean" in module_name.lower() or "sanitize" in module_name.lower():
                pipeline_stage = PipelineStage.TEXT_SANITIZATION
            elif "entity" in module_name.lower():
                pipeline_stage = PipelineStage.ENTITY_EXTRACTION
            elif "graph" in module_name.lower():
                pipeline_stage = PipelineStage.GRAPH_CONSTRUCTION
            elif "amendment" in module_name.lower():
                pipeline_stage = PipelineStage.AMENDMENT_TRACKING
            elif "authority" in module_name.lower():
                pipeline_stage = PipelineStage.AUTHORITY_HIERARCHY
            else:
                pipeline_stage = PipelineStage.OTHER
    
    # Convert severity if string
    if isinstance(severity, str):
        try:
            severity = AbstentionSeverity(severity)
        except ValueError:
            severity = None  # Let auto-determination handle it
    
    # Create context
    context = create_abstention_context(
        pipeline_state=kwargs.get('pipeline_state', 'unknown'),
        processing_step=kwargs.get('processing_step', 'unknown'),
        module_state=kwargs.get('module_state', {}),
        kpk_metadata=kpk_metadata,
        document_profile=document_profile,
        input_summary=kwargs.get('input_summary'),
        text_preview=kwargs.get('text_preview'),
        entity_count=kwargs.get('entity_count'),
        confidence_scores=kwargs.get('confidence_scores'),
        model_used=kwargs.get('model_used'),
        parameters=kwargs.get('parameters'),
    )
    
    # Extract affected entities
    affected_entities = kwargs.get('affected_entities', [])
    if not affected_entities and 'affected_entity' in kwargs:
        affected_entities = [kwargs['affected_entity']]
    
    # Use default threshold if not provided
    if threshold is None:
        threshold = logger.config.THRESHOLDS['confidence_threshold_default']
    
    # Log abstention
    abstention_id = logger.log_abstention(
        abstention_type=abstention_type,
        reason=reason,
        context=context,
        affected_entities=affected_entities,
        pipeline_stage=pipeline_stage or PipelineStage.OTHER,
        module_name=module_name,
        confidence_before=confidence,
        confidence_threshold=threshold,
        severity=severity,
        function_name=kwargs.get('function_name'),
        source_document=kwargs.get('document') or kwargs.get('source_document'),
        page_number=kwargs.get('page_number'),
        line_number=kwargs.get('line_number'),
        model_used=kwargs.get('model_used'),
        parameters=kwargs.get('parameters'),
        error_traceback=kwargs.get('error_traceback'),
        tags=kwargs.get('tags', []),
        notes=kwargs.get('notes'),
        execution_time_ms=kwargs.get('execution_time_ms'),
        memory_usage_mb=kwargs.get('memory_usage_mb'),
        cpu_usage_percent=kwargs.get('cpu_usage_percent'),
        use_async=kwargs.get('use_async', True)
    )
    
    return abstention_id


# ============================================================================
# PIPELINE INTEGRATION DECORATORS
# ============================================================================

def with_abstention_logging(
    abstention_type: Union[str, AbstentionType] = AbstentionType.OTHER,
    threshold: float = 0.7,
    module_name: str = None,
    pipeline_stage: Union[str, PipelineStage] = None,
):
    """
    Decorator for automatic abstention logging in pipeline functions
    
    Example:
        @with_abstention_logging(
            abstention_type="poor_ocr_quality",
            threshold=0.7,
            module_name="ocr_engine.py",
            pipeline_stage="document_extraction"
        )
        def process_document(document_path, confidence_threshold=0.7):
            # Function implementation
            # If confidence < threshold, abstention will be auto-logged
            pass
    """
    
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Get module name from function if not provided
            nonlocal module_name
            if module_name is None:
                module_name = func.__module__ or "unknown"
            
            try:
                # Execute function
                result = func(*args, **kwargs)
                
                # Check if result has confidence score
                if isinstance(result, dict) and 'confidence' in result:
                    confidence = result['confidence']
                    
                    if confidence < threshold:
                        # Auto-log abstention
                        reason = f"Function {func.__name__} returned confidence {confidence} below threshold {threshold}"
                        
                        log_quick_abstention(
                            abstention_type=abstention_type,
                            reason=reason,
                            module_name=module_name,
                            confidence=confidence,
                            threshold=threshold,
                            pipeline_stage=pipeline_stage,
                            function_name=func.__name__,
                            kwargs=kwargs
                        )
                
                return result
                
            except Exception as e:
                # Log abstention for exceptions
                reason = f"Exception in {func.__name__}: {str(e)}"
                
                log_quick_abstention(
                    abstention_type=AbstentionType.SYSTEM_LIMITATION,
                    reason=reason,
                    module_name=module_name,
                    confidence=0.0,
                    threshold=threshold,
                    pipeline_stage=pipeline_stage,
                    function_name=func.__name__,
                    error_traceback=str(e),
                    kwargs=kwargs
                )
                
                # Re-raise the exception
                raise
        
        return wrapper
    
    return decorator


# ============================================================================
# EXAMPLE USAGE
# ============================================================================


if __name__ == "__main__":
    pass
