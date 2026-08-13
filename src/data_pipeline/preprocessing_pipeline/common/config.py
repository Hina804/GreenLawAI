"""
CONFIG.PY - Global Configuration
"""
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from preprocessing_pipeline.common.forestry_data import (
    KPK_FOREST_DIVISIONS, 
    KPK_OFFICER_HIERARCHY, 
    KPK_DOCUMENT_TYPES,
    KPK_SPECIES_STATUS,
    KPK_KEYWORDS,
    KPK_PENALTY_STRUCTURES,
    LEGAL_SECTION_PATTERNS
)


BASE_DIR = Path(__file__).parent.parent.parent

# Database Config
DB_PATH = os.getenv("DB_PATH", "sqlite:///kpk_forestry.db")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# LLM Config
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_MODEL = "llama3.2"

# Paths
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"

# Thresholds
QUALITY_THRESHOLD = 0.7
ABSTENTION_THRESHOLD = 0.5
QUALITY_THRESHOLDS = {
    'text_quality_threshold': 0.7,
    'legal_structure_threshold': 0.6,
    'entity_consistency_threshold': 0.5,
    'authority_validation_threshold': 0.7,
    'temporal_consistency_threshold': 0.8,
    'graph_integrity_threshold': 0.6,
    'multilingual_coherence_threshold': 0.5
}

ABSTENTION_REASONS = {
    'POOR_TEXT_QUALITY': 'Text extraction quality below threshold',
    'INCOMPLETE_STRUCTURE': 'Document structure missing critical elements',
    'AUTHORITY_CONFLICT': 'Conflicting legal authorities detected',
    'TEMPORAL_CONFLICT': 'Conflicting amendment timelines',
    'MULTILINGUAL_AMBIGUITY': 'Ambiguous translation or script'
}

DOCUMENT_TYPES = ['ACT', 'ORDINANCE', 'RULE', 'CIRCULAR', 'NOTIFICATION', 'WORKING_PLAN', 'REPORT', 'UNKNOWN']

LANGUAGES = ['ENGLISH', 'URDU', 'PASHTO', 'MIXED']



@dataclass
class DocumentProcessingConfig:
    """Configuration for document processing"""
    ocr_enabled: bool = True
    ocr_lang: str = "eng+urd"
    quality_threshold: float = 0.7
    max_pages: int = 200

@dataclass
class AbstentionSystemConfig:
    """Internal configuration for the abstention system, allowing flexible initialization."""
    enabled: bool = True
    log_dir: str = "./abstention_logs"
    severity_threshold: str = "medium"
    
    # Storage settings for 0.3 compatibility
    STORAGE: Dict[str, Any] = field(default_factory=lambda: {
        'log_dir': './abstention_logs',
        'db_path': './abstention_logs/abstention_db.sqlite',
        'enable_sqlite': True,
        'enable_json': True,
        'enable_csv': True,
        'enable_compression': True,
        'archive_after_days': 30,
        'cleanup_after_days': 180,
    })
    
    # Performance settings for 0.3 compatibility
    PERFORMANCE: Dict[str, Any] = field(default_factory=lambda: {
        'batch_size': 50,
        'flush_interval_seconds': 5,
        'max_queue_size': 1000,
        'worker_threads': 2,
        'enable_async_logging': True,
    })

    def __post_init__(self):
        # Ensure log_dir is a Path object if it's a string
        if isinstance(self.log_dir, str):
            self.log_dir = Path(self.log_dir)

@dataclass
class AbstentionConfig:
    """Configuration for abstention logging"""
    config: AbstentionSystemConfig = field(default_factory=AbstentionSystemConfig)

    def __init__(self, config: Optional[Any] = None):
        if isinstance(config, dict):
            self.config = AbstentionSystemConfig()
            # Update config from dict
            for key, value in config.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
        elif isinstance(config, AbstentionSystemConfig):
            self.config = config
        elif config and hasattr(config, 'STORAGE'): # This part seems specific, keeping it as per instruction
            self.config = config
        else:
            # Fallback to default or extract if possible
            self.config = AbstentionSystemConfig()
            if config and hasattr(config, 'abstention_settings'):
                # Potential future integration
                pass
    # The fields below are now managed by AbstentionSystemConfig
    # enabled: bool = True
    # log_dir: str = "./abstention_logs"
    # severity_threshold: str = "medium"

@dataclass
class LLMSettings:
    provider: str = "ollama"
    model: str = LLM_MODEL
    base_url: str = OLLAMA_BASE_URL
    temperature: float = 0.0

@dataclass
class PipelineConfig:
    pipeline_mode: str = "standard"
    enable_ocr_training: bool = False
    llm_settings: LLMSettings = field(default_factory=LLMSettings)
    neo4j_auth: tuple = (NEO4J_USER, NEO4J_PASSWORD)
    
    # Storage Paths
    TEMP_DIR: str = str(DATA_DIR / "temp")
    OUTPUT_DIR: str = str(BASE_DIR / "data_preprocessed")
    CACHE_DIR: str = str(DATA_DIR / "cache")
    LOG_DIR_PATH: str = str(LOG_DIR)
    
    # Hardening
    PRODUCTION_HARDENED: bool = True
    PROJECT_NAMESPACE: str = "greenlaw_kpk"
    
    # Flags
    CONTINUE_ON_ERROR: bool = True
    CACHE_RESULTS: bool = True
    USE_LLM_FOR_CLEANING: bool = True
    FALLBACK_TO_RULES: bool = True
    
    # LLM Settings
    LLM_MODEL: str = "llama3.2"
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 4096
    LLM_TIMEOUT: int = 120
    LLM_API_BASE: Optional[str] = "http://localhost:11434"
    LLM_API_KEY: Optional[str] = "ollama"
    
    # OCR & Image Processing
    TESSERACT_CMD: Optional[str] = None
    DEFAULT_DPI: int = 300
    USE_KPK_TRAINED_DATA: bool = True
    PARALLEL_PROCESSING: bool = True
    RETRY_FAILED_PAGES: bool = True
    MAX_RETRIES: int = 2
    COLUMN_DETECTION_ENABLED: bool = True
    MARGIN_DETECTION_ENABLED: bool = True
    HEADER_FOOTER_ENABLED: bool = True
    KPK_PATTERN_DETECTION: bool = True
    MAX_COLUMNS: int = 3
    COLUMN_SEPARATION_THRESHOLD: float = 0.05
    DEFAULT_MARGINS: Dict = field(default_factory=lambda: {'left': 50, 'right': 50, 'top': 50, 'bottom': 50})
    
    # Forestry Data
    KPK_FOREST_DIVISIONS: Dict = field(default_factory=lambda: KPK_FOREST_DIVISIONS)
    KPK_OFFICER_HIERARCHY: Dict = field(default_factory=lambda: KPK_OFFICER_HIERARCHY)
    KPK_DOCUMENT_TYPES: Dict = field(default_factory=lambda: KPK_DOCUMENT_TYPES)
    KPK_SPECIES_STATUS: Dict = field(default_factory=lambda: KPK_SPECIES_STATUS)
    KPK_KEYWORDS: Dict = field(default_factory=lambda: KPK_KEYWORDS)
    KPK_PENALTY_STRUCTURES: Dict = field(default_factory=lambda: KPK_PENALTY_STRUCTURES)
    LEGAL_SECTION_PATTERNS: List = field(default_factory=lambda: LEGAL_SECTION_PATTERNS)
    
    # Entity Extraction
    ENTITY_EXTRACTION: Dict = field(default_factory=lambda: {
        'use_spacy': True,
        'spacy_model': 'en_core_web_sm',
        'max_entities': 50,
        'min_entity_length': 2,
    })
    
    # Priority calculation weights
    PRIORITY_WEIGHTS: Dict = field(default_factory=lambda: {
        'is_kpk': 2,
        'is_law_type': 2,
        'is_circular': 1,
        'poor_quality': 2,
        'unreadable': 3,
        'has_amendments': 1,
        'needs_ocr': 1,
        'needs_language_sep': 1,
    })

    # Confidence Thresholds
    CONFIDENCE_THRESHOLDS: Dict = field(default_factory=lambda: {
        'low_confidence': 0.3,
        'abstention_threshold': 0.2,
    })

    # File Parameters
    FILE_PARAMS: Dict = field(default_factory=lambda: {
        'max_file_size_mb': 100,
        'supported_formats': ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt'],
        'supported_image_formats': ['.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp'],
    })

    # Processing decisions
    PROCESSING_DECISIONS: Dict = field(default_factory=lambda: {
        'auto_process': 0.70,
        'auto_clean_then_process': 0.50,
        'manual_review_needed': 0.30,
        'reject': 0.10,
    })

    # Phase 2 sanitization
    SANITIZATION_MODE: str = "hybrid"

    # Quality Thresholds (0-1 scale)
    QUALITY_THRESHOLDS: Dict = field(default_factory=lambda: {
        'excellent': 0.85,
        'good': 0.70,
        'fair': 0.50,
        'poor': 0.30,
        'unacceptable': 0.0,
    })

    # KPK-specific quality factors (sum to 1.0 ideally)
    KPK_QUALITY_FACTORS: Dict = field(default_factory=lambda: {
        'division_specificity': 0.3,
        'jurisdiction_clarity': 0.25,
        'legal_references': 0.20,
        'language_appropriateness': 0.15,
        'geographic_specificity': 0.10,
    })
    
    # Quality factor weights (sum to 1.0)
    QUALITY_WEIGHTS: Dict = field(default_factory=lambda: {
        'readability': 0.25,       # Text clarity and structure
        'completeness': 0.20,      # Missing pages/sections
        'technical_quality': 0.20,  # Scan quality, OCR errors
        'kpk_specificity': 0.15,   # KPK relevance and completeness
        'legal_validity': 0.10,    # Document validity and currency
        'metadata_quality': 0.10,   # Metadata completeness
    })

    # Issue severity scoring
    ISSUE_SEVERITY: Dict = field(default_factory=lambda: {
        'critical': {'weight': 1.0, 'description': 'Prevents processing'},
        'high': {'weight': 0.7, 'description': 'Significant impact on quality'},
        'medium': {'weight': 0.4, 'description': 'Moderate impact on quality'},
        'low': {'weight': 0.1, 'description': 'Minor quality issue'},
        'info': {'weight': 0.0, 'description': 'Informational only'},
    })

    # Subsystem Configurations
    ocr_config: DocumentProcessingConfig = field(default_factory=DocumentProcessingConfig)
    abstention_config: AbstentionSystemConfig = field(default_factory=AbstentionSystemConfig)

    
    
    def get(self, key: str, default: Any = None) -> Any:
        """Provide dictionary-like access for backward compatibility."""
        return getattr(self, key, default)

def load_config(config_path: str = None) -> PipelineConfig:
    """Load configuration from path or env."""
    return PipelineConfig()
