"""
ENHANCED WORKING_PLAN_PARSER.PY - KPK Forestry Working Plan Parser
WITH PIPELINE INTEGRATION, GRAPH-RAG OPTIMIZATION, AND SPATIAL AWARENESS

Key Enhancements:
1. PipelineState integration for flow tracking
2. Graph schema mapping for Neo4j integration (Compartment → Prescription → Yield)
3. RAG-optimized chunking for spatial-temporal planning data
4. KPK-specific compartment classification and spatial relationships
5. Enhanced OCR handling for plan-specific patterns
6. Abstention framework for incomplete/ambiguous plans
7. Temporal planning with version control
8. Authority compliance tracking
9. Integration with phase 3.1 (multilingual) and phase 3.2 (circulars)
10. Output structured for phase 4-6 processing
"""

import re
import json
import logging
import math
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set, Union
from datetime import datetime
from dataclasses import dataclass, asdict, field
import sys
from enum import Enum
import hashlib
from collections import defaultdict

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add common module path for pipeline integration
sys.path.append(str(Path(__file__).parent.parent / "common"))
try:
    from config import PipelineConfig
    from constants import ABSTENTION_REASONS, KPK_ENTITIES, KPK_CONFIG
except ImportError:
    # Fallback if common modules not available
    class PipelineConfig:
        MIN_PLAN_CONFIDENCE = 0.65
        MAX_COMPARTMENTS = 200
        MAX_PRESCRIPTIONS = 500
    
    ABSTENTION_REASONS = {
        'insufficient_compartments': 'Too few compartments identified',
        'missing_temporal_data': 'Plan period not identifiable',
        'poor_ocr_quality': 'OCR errors affect compartment detection',
        'format_violation': 'Document not recognized as working plan',
        'spatial_inconsistency': 'Spatial data inconsistencies detected'
    }
    
    KPK_ENTITIES = {
        "DIVISIONS": ["Abbottabad", "Mansehra", "Swat", "Dir", "Malakand", "D.I.Khan"],
        "TREE_SPECIES": {
            "deodar": {"scientific": "Cedrus deodara", "legal_status": "protected", "rotation": 120},
            "chir_pine": {"scientific": "Pinus roxburghii", "legal_status": "regulated", "rotation": 60},
            "kail": {"scientific": "Pinus wallichiana", "legal_status": "protected", "rotation": 100},
            "walnut": {"scientific": "Juglans regia", "legal_status": "protected", "rotation": 80},
            "oak": {"scientific": "Quercus spp.", "legal_status": "protected", "rotation": 90}
        },
        "SOIL_TYPES": ["Clay", "Loam", "Sandy", "Rocky", "Alluvial"],
        "ASPECTS": ["North", "South", "East", "West", "Northeast", "Northwest", "Southeast", "Southwest"],
        "SLOPE_CLASSES": ["Flat (0-10%)", "Gentle (10-30%)", "Moderate (30-60%)", "Steep (60-100%)", "Very steep (>100%)"]
    }


@dataclass
class PipelineState:
    """Enhanced pipeline state tracking for working plans"""
    doc_id: str
    phase: int = 3
    subphase: str = "3.3_working_plan"
    status: str = "processing"
    metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    abstention_reasons: List[str] = field(default_factory=list)
    confidence: float = 1.0
    dependencies: List[str] = field(default_factory=list)
    spatial_references: Dict[str, Any] = field(default_factory=dict)
    
    def add_abstention(self, reason: str, context: str = ""):
        self.abstention_reasons.append(f"{reason}: {context}")
        self.status = "abstained"
        self.confidence = 0.0
    
    def add_warning(self, warning: str):
        self.warnings.append(f"{datetime.now().isoformat()}: {warning}")
    
    def add_spatial_reference(self, ref_type: str, data: Any):
        self.spatial_references[ref_type] = data
    
    def to_dict(self):
        return asdict(self)


class CompartmentStatus(Enum):
    """Compartment status based on prescriptions"""
    ACTIVE = "active"
    COMPLETED = "completed"
    PENDING = "pending"
    PROTECTED = "protected"
    RESTRICTED = "restricted"
    COMMUNITY = "community"
    
    @property
    def allows_extraction(self) -> bool:
        return self in [CompartmentStatus.ACTIVE, CompartmentStatus.PENDING]
    
    @property
    def graph_node_color(self) -> str:
        colors = {
            "active": "#4CAF50",
            "completed": "#2196F3",
            "pending": "#FF9800",
            "protected": "#F44336",
            "restricted": "#9C27B0",
            "community": "#795548"
        }
        return colors.get(self.value, "#607D8B")


class PrescriptionPriority(Enum):
    """Priority levels for prescriptions"""
    IMMEDIATE = {"level": 1, "timeline_days": 30}
    HIGH = {"level": 2, "timeline_days": 90}
    MEDIUM = {"level": 3, "timeline_days": 180}
    LOW = {"level": 4, "timeline_days": 365}
    MONITORING = {"level": 5, "timeline_days": None}
    
    @property
    def is_time_critical(self) -> bool:
        return self in [PrescriptionPriority.IMMEDIATE, PrescriptionPriority.HIGH]


@dataclass
class SpatialLocation:
    """Enhanced spatial location with KPK-specific mapping"""
    division: str
    compartment: str
    range: Optional[str] = None
    beat: Optional[str] = None
    coordinates: Optional[Tuple[float, float]] = None
    elevation_min: Optional[float] = None
    elevation_max: Optional[float] = None
    aspect: Optional[str] = None
    slope_class: Optional[str] = None
    soil_type: Optional[str] = None
    distance_to_road_km: Optional[float] = None
    distance_to_settlement_km: Optional[float] = None
    
    def to_dict(self):
        result = asdict(self)
        if self.coordinates:
            result['coordinates'] = list(self.coordinates)
        return result


@dataclass
class Compartment:
    """Enhanced compartment with spatial and temporal attributes"""
    number: str
    spatial: SpatialLocation
    name: Optional[str] = None
    area_ha: Optional[float] = None
    working_circle: Optional[str] = None
    compartment_type: str = "productive"
    compartment_status: CompartmentStatus = CompartmentStatus.PENDING
    establishment_year: Optional[int] = None
    revision_year: Optional[int] = None
    compartment_class: Optional[str] = None  # Class I, II, III based on productivity
    legal_status: Optional[str] = None  # Reserved, Protected, Guzara, etc.
    community_involvement: Optional[bool] = None
    conservation_value: float = 0.5  # 0-1 scale
    extraction_potential: float = 0.5  # 0-1 scale
    biodiversity_index: float = 0.5  # 0-1 scale
    fragmentation_level: str = "low"  # low, medium, high
    
    def to_dict(self):
        result = asdict(self)
        result['spatial'] = self.spatial.to_dict()
        if self.compartment_status:
            result['compartment_status'] = self.compartment_status.value
        return result


@dataclass
class SilviculturalPrescription:
    """Enhanced prescription with legal and compliance tracking"""
    id: str
    compartment_id: str
    prescription_type: str
    description: str
    prescription_subtype: Optional[str] = None
    priority: PrescriptionPriority = PrescriptionPriority.MEDIUM
    treatment_area_ha: Optional[float] = None
    treatment_year: Optional[int] = None
    start_month: Optional[str] = None
    duration_months: Optional[int] = None
    rotation_period: Optional[int] = None
    species_mix: Optional[Dict[str, float]] = None
    expected_yield_m3: Optional[float] = None
    yield_confidence: float = 0.7
    labor_requirements: Optional[int] = None  # Person-days
    equipment_needed: Optional[List[str]] = None
    budget_estimate_pkr: Optional[float] = None
    funding_source: Optional[str] = None
    legal_requirements: Optional[List[str]] = None
    compliance_deadline: Optional[str] = None
    authority_approval_required: bool = True
    monitoring_requirements: Optional[List[str]] = None
    success_indicators: Optional[Dict[str, Any]] = None
    risk_factors: Optional[List[str]] = None
    environmental_impact: str = "moderate"  # low, moderate, high
    community_benefits: Optional[List[str]] = None
    temporal_dependencies: Optional[List[str]] = None  # Other prescriptions this depends on
    
    def __post_init__(self):
        if self.equipment_needed is None:
            self.equipment_needed = []
        if self.legal_requirements is None:
            self.legal_requirements = []
        if self.monitoring_requirements is None:
            self.monitoring_requirements = []
        if self.risk_factors is None:
            self.risk_factors = []
        if self.community_benefits is None:
            self.community_benefits = []
        if self.temporal_dependencies is None:
            self.temporal_dependencies = []
        if self.success_indicators is None:
            self.success_indicators = {}
    
    def to_dict(self):
        result = asdict(self)
        if self.priority:
            result['priority'] = self.priority.value
        return result


@dataclass
class YieldCalculation:
    """Enhanced yield calculation with uncertainty modeling"""
    id: str
    compartment_id: str
    species: str
    yield_m3: float
    prescription_id: Optional[str] = None
    calculation_method: str = "volume_table"
    standing_volume_m3: Optional[float] = None
    standing_volume_confidence: float = 0.8
    annual_allowable_cut_m3: Optional[float] = None
    aac_confidence: float = 0.7
    actual_harvest_m3: Optional[float] = None
    harvest_year: Optional[int] = None
    growth_rate_percent: Optional[float] = None
    mortality_rate_percent: Optional[float] = None
    sustainable_yield_index: Optional[float] = None  # 0-1 scale
    carbon_storage_tonnes: Optional[float] = None
    carbon_sequestration_annual: Optional[float] = None
    economic_value_pkr: Optional[float] = None
    calculation_assumptions: Optional[List[str]] = None
    data_sources: Optional[List[str]] = None
    validation_status: str = "unvalidated"  # unvalidated, validated, verified
    
    def __post_init__(self):
        if self.calculation_assumptions is None:
            self.calculation_assumptions = []
        if self.data_sources is None:
            self.data_sources = []
    
    def to_dict(self):
        return asdict(self)


@dataclass
class ManagementDirective:
    """Enhanced management directive with implementation tracking"""
    id: str
    directive_type: str  # objective, strategy, action, regulation
    directive_level: str  # strategic, operational, tactical
    text: str
    responsible_authority: Optional[str] = None
    implementation_timeline: Optional[str] = None
    budget_allocation_pkr: Optional[float] = None
    performance_indicators: Optional[List[str]] = None
    monitoring_frequency: Optional[str] = None
    reporting_requirements: Optional[List[str]] = None
    compliance_deadline: Optional[str] = None
    legal_basis: Optional[str] = None
    authority_hierarchy_level: int = 3  # 1=provincial, 2=divisional, 3=range, 4=beat
    applies_to_compartments: Optional[List[str]] = None
    cross_references: Optional[List[str]] = None  # References to other directives/circulars
    
    def __post_init__(self):
        if self.performance_indicators is None:
            self.performance_indicators = []
        if self.reporting_requirements is None:
            self.reporting_requirements = []
        if self.applies_to_compartments is None:
            self.applies_to_compartments = []
        if self.cross_references is None:
            self.cross_references = []
    
    def to_dict(self):
        return asdict(self)


@dataclass
class RAGChunk:
    """RAG-optimized chunk for working plan spatial-temporal data"""
    chunk_id: str
    text: str
    chunk_type: str  # compartment_detail, prescription, yield_calc, directive, summary
    spatial_context: Dict[str, Any]
    temporal_context: Dict[str, Any]
    compartment_ids: List[str]
    prescription_ids: List[str]
    directive_ids: List[str]
    legal_significance: float
    spatial_importance: float  # How spatially specific is this chunk
    temporal_importance: float  # How time-sensitive is this chunk
    implementation_priority: float
    
    def to_dict(self):
        return asdict(self)


@dataclass
class GraphSchemaMapping:
    """Graph schema mapping for Neo4j"""
    nodes: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    
    def to_dict(self):
        return asdict(self)


class EnhancedKPKWorkingPlanParser:
    """
    Enhanced parser with pipeline integration and Graph-RAG optimization.
    """
    
    def __init__(self, pipeline_state: Optional[PipelineState] = None):
        self.pipeline_state = pipeline_state or PipelineState(
            doc_id="unknown",
            phase=3,
            subphase="3.3_working_plan"
        )
        
        # Enhanced patterns with OCR awareness
        self.ocr_error_patterns = {
            'Compartment': 'Compartment',
            'Cmpartment': 'Compartment',
            'Compartm3nt': 'Compartment',
            'Prescripiton': 'Prescription',
            'Prescripton': 'Prescription',
            'Silvicltural': 'Silvicultural',
            'annua1': 'annual',
            'vo1ume': 'volume',
            'hectares': 'hectares',
            'hactares': 'hectares',
        }
        
        # Enhanced compartment patterns
        self.compartment_patterns = [
            r'Compartment\s+(?:No\.?|N0\.?)?\s*(\d+[A-Z]?(?:\/\d+)?(?:-\d+)?)',  # Compartment 15A, 15/1, 15-1
            r'Cmp\.?\s*(\d+[A-Z]?(?:\/\d+)?)',  # Cmp. 15A
            r'Comp\.?\s*(\d+[A-Z]?)',  # Comp. 15
            r'^(\d+[A-Z]?(?:\/\d+)?)\s+(?:Compartment|Cmp\.?)',  # 15A Compartment
            r'Comp\.?\s+(\d+)\s+[A-Z]',  # Comp. 15 Range
        ]
        
        # KPK-specific spatial patterns
        self.kpk_spatial_patterns = {
            "division": [(r'Division\s+([A-Za-z\s\-]+?)(?:\.|$)', "division")],
            "range": [(r'Range\s+([A-Za-z\s\-]+?)(?:\.|$)', "range"),
                     (r'R\.\s+([A-Za-z\s\-]+?)(?:\.|$)', "range")],
            "beat": [(r'Beat\s+([A-Za-z\s\-]+?)(?:\.|$)', "beat"),
                    (r'B\.\s+([A-Za-z\s\-]+?)(?:\.|$)', "beat")],
            "block": [(r'Block\s+([A-Za-z\s\-]+?)(?:\.|$)', "block")],
        }
        
        # Enhanced prescription patterns with legal context
        self.prescription_type_patterns = {
            "clear_felling": {
                "patterns": [r'clear\s+(?:felling|cutting|harvesting)', r'final\s+felling'],
                "legal_requirements": ["Section 27 Forest Ordinance", "DFO Approval"],
                "authority_level": 2,  # Divisional level
                "environmental_impact": "high"
            },
            "thinning": {
                "patterns": [r'thinning', r'improvement\s+felling', r'selective\s+removal'],
                "legal_requirements": ["Section 26 Forest Ordinance", "RFO Approval"],
                "authority_level": 3,  # Range level
                "environmental_impact": "moderate"
            },
            "enrichment_planting": {
                "patterns": [r'enrichment\s+planting', r'afforestation', r'planting'],
                "legal_requirements": ["Section 29 Forest Ordinance", "Soil Conservation Guidelines"],
                "authority_level": 3,
                "environmental_impact": "low"
            },
            "protection": {
                "patterns": [r'protection', r'conservation', r'preservation'],
                "legal_requirements": ["Section 21 Forest Ordinance", "Wildlife Protection Act"],
                "authority_level": 2,
                "environmental_impact": "low"
            },
            "regeneration": {
                "patterns": [r'natural\s+regeneration', r'regeneration\s+felling'],
                "legal_requirements": ["Section 28 Forest Ordinance", "Natural Regeneration Guidelines"],
                "authority_level": 3,
                "environmental_impact": "moderate"
            },
            "community_based": {
                "patterns": [r'community', r'joint\s+forest', r'participatory'],
                "legal_requirements": ["Community Forestry Rules", "Village Committee Approval"],
                "authority_level": 4,  # Beat/Community level
                "environmental_impact": "low"
            }
        }
        
        # KPK-specific species rotation periods
        self.kpk_species_rotations = {
            "deodar": {"rotation": 120, "maturity": 80, "aac_percent": 0.8},
            "chir_pine": {"rotation": 60, "maturity": 40, "aac_percent": 1.0},
            "kail": {"rotation": 100, "maturity": 70, "aac_percent": 0.9},
            "walnut": {"rotation": 80, "maturity": 60, "aac_percent": 0.7},
            "oak": {"rotation": 90, "maturity": 65, "aac_percent": 0.75},
        }
        
        # Yield calculation methods with confidence scores
        self.yield_methods = {
            "volume_table": {"confidence": 0.9, "data_requirements": ["DBH", "Height", "Species"]},
            "taper_function": {"confidence": 0.85, "data_requirements": ["DBH", "Height", "Taper"]},
            "sample_plot": {"confidence": 0.8, "data_requirements": ["Plot Data", "Extrapolation"]},
            "remote_sensing": {"confidence": 0.75, "data_requirements": ["Satellite Imagery", "Ground Truth"]},
            "local_yield_table": {"confidence": 0.7, "data_requirements": ["Local Tables"]},
        }
        
        # Spatial relationship patterns
        self.spatial_relationship_patterns = [
            (r'adjacent\s+to\s+Compartment\s+(\d+)', 'ADJACENT_TO'),
            (r'bordering\s+Compartment\s+(\d+)', 'BORDERS'),
            (r'connected\s+to\s+Compartment\s+(\d+)', 'CONNECTED_TO'),
            (r'upstream\s+of\s+Compartment\s+(\d+)', 'UPSTREAM_OF'),
            (r'downstream\s+of\s+Compartment\s+(\d+)', 'DOWNSTREAM_OF'),
        ]
        
        # Temporal planning patterns
        self.temporal_patterns = [
            (r'Year\s+(\d+)\s+of\s+Plan', 'plan_year'),
            (r'Phase\s+([IVXLCDM]+)', 'plan_phase'),
            (r'(\d{4})\s*[-–]\s*(\d{4})', 'plan_period'),
            (r'quarter\s+([1-4])', 'plan_quarter'),
            (r'within\s+(\d+)\s+(?:months|years)', 'timeline'),
        ]
        
        logger.info("Enhanced KPK Working Plan Parser initialized")
    
    def parse_working_plan(self, text: str, doc_type: str = "working_plan") -> Dict[str, Any]:
        """
        Enhanced main parsing function with pipeline integration.
        
        Args:
            text: Normalized text from working plan document
            doc_type: Document type from previous phase
            
        Returns:
            Comprehensive parsing results with pipeline integration
        """
        self.pipeline_state.metadata['doc_type'] = doc_type
        self.pipeline_state.metadata['input_length'] = len(text)
        
        logger.info(f"Starting enhanced working plan parsing for {doc_type}")
        
        # Step 0: Pre-process with OCR correction and structure detection
        cleaned_text, preprocessing_metrics = self._preprocess_working_plan_text(text)
        
        # Step 1: Extract enhanced metadata with spatial context
        metadata = self.extract_enhanced_metadata(cleaned_text)
        
        # Step 2: Detect plan structure and identify sections
        plan_structure = self.analyze_plan_structure(cleaned_text)
        
        # Step 3: Extract compartments with spatial relationships
        compartments = self.extract_enhanced_compartments(cleaned_text, metadata)
        
        # Step 4: Extract enhanced prescriptions with legal context
        prescriptions = self.extract_enhanced_prescriptions(cleaned_text, compartments)
        
        # Step 5: Extract yield calculations with uncertainty modeling
        yield_calculations = self.extract_enhanced_yield_calculations(cleaned_text, compartments, prescriptions)
        
        # Step 6: Extract management directives with implementation tracking
        management_directives = self.extract_enhanced_management_directives(cleaned_text)
        
        # Step 7: Analyze spatial relationships between compartments
        spatial_relationships = self.analyze_spatial_relationships(cleaned_text, compartments)
        
        # Step 8: Analyze temporal planning and dependencies
        temporal_analysis = self.analyze_temporal_structure(cleaned_text, prescriptions)
        
        # Step 9: Create RAG-optimized chunks
        rag_chunks = self.create_rag_optimized_chunks(
            cleaned_text, compartments, prescriptions, 
            yield_calculations, management_directives,
            spatial_relationships, temporal_analysis
        )
        
        # Step 10: Create graph schema mapping
        graph_mapping = self.create_graph_schema_mapping(
            compartments, prescriptions, yield_calculations, 
            management_directives, spatial_relationships
        )
        
        # Step 11: Calculate processing metrics
        processing_metrics = self.calculate_enhanced_processing_metrics(
            cleaned_text, compartments, prescriptions, 
            yield_calculations, management_directives,
            preprocessing_metrics
        )
        
        # Step 12: Analyze plan quality and completeness
        plan_quality = self.analyze_plan_quality(
            compartments, prescriptions, yield_calculations, management_directives
        )
        
        # Step 13: Apply quality gates
        self.apply_working_plan_quality_gates(
            compartments, prescriptions, yield_calculations, plan_quality
        )
        
        # Step 14: Update pipeline state
        self.update_pipeline_state(
            metadata, compartments, prescriptions, 
            yield_calculations, management_directives,
            processing_metrics, plan_quality
        )
        
        # Build comprehensive result
        result = {
            "pipeline_state": self.pipeline_state.to_dict(),
            "metadata": metadata,
            "plan_structure": plan_structure,
            "compartments": [c.to_dict() for c in compartments],
            "prescriptions": [p.to_dict() for p in prescriptions],
            "yield_calculations": [y.to_dict() for y in yield_calculations],
            "management_directives": [m.to_dict() for m in management_directives],
            "spatial_analysis": {
                "relationships": spatial_relationships,
                "clusters": self.identify_spatial_clusters(compartments),
                "connectivity": self.calculate_spatial_connectivity(compartments, spatial_relationships)
            },
            "temporal_analysis": temporal_analysis,
            "rag_chunks": [chunk.to_dict() for chunk in rag_chunks],
            "graph_schema": graph_mapping.to_dict() if graph_mapping else None,
            "processing_metrics": processing_metrics,
            "plan_quality": plan_quality,
            "downstream_recommendations": self.generate_downstream_recommendations(
                compartments, prescriptions, yield_calculations, plan_quality
            )
        }
        
        logger.info(f"Enhanced working plan parsing complete: {len(compartments)} compartments, {len(prescriptions)} prescriptions")
        return result
    
    def _preprocess_working_plan_text(self, text: str) -> Tuple[str, Dict]:
        """Enhanced preprocessing for working plans"""
        # Apply OCR corrections
        corrected_text = text
        corrections_applied = 0
        
        for error, correction in self.ocr_error_patterns.items():
            if error in corrected_text:
                corrected_text = corrected_text.replace(error, correction)
                corrections_applied += 1
        
        # Fix common working plan OCR issues
        common_fixes = {
            'm3': 'm³',
            'm^3': 'm³',
            'hec': 'hectares',
            'hect': 'hectares',
            'compart': 'compartment',
            'silvi': 'silvicultural',
        }
        
        for error, correction in common_fixes.items():
            corrected_text = corrected_text.replace(error, correction)
        
        # Standardize section headers
        section_patterns = [
            (r'CHAPTER\s+(\d+)', 'CHAPTER'),
            (r'SECTION\s+(\d+)', 'SECTION'),
            (r'PART\s+([IVXLCDM]+)', 'PART'),
        ]
        
        for pattern, replacement in section_patterns:
            corrected_text = re.sub(pattern, rf'{replacement} \1', corrected_text)
        
        # Calculate preprocessing metrics
        preprocessing_metrics = {
            'original_length': len(text),
            'processed_length': len(corrected_text),
            'ocr_corrections': corrections_applied,
            'ocr_confidence': max(0.0, 1.0 - (corrections_applied / max(1, len(text.split())))),
            'section_headers_normalized': len(re.findall(r'CHAPTER|SECTION|PART', corrected_text))
        }
        
        return corrected_text, preprocessing_metrics
    
    def extract_enhanced_metadata(self, text: str) -> Dict[str, Any]:
        """Extract enhanced metadata with spatial context"""
        metadata = {
            "document_type": "working_plan",
            "parser_version": "enhanced_3.3",
            "extraction_timestamp": datetime.now().isoformat(),
            "spatial_context": {},
            "temporal_context": {},
            "authority_context": {}
        }
        
        # Extract division
        division = None
        for div in KPK_ENTITIES.get("DIVISIONS", []):
            if re.search(rf'\b{div}\b', text, re.IGNORECASE):
                division = div
                break
        
        if division:
            metadata["spatial_context"]["division"] = division
            metadata["authority_context"]["jurisdiction"] = f"KPK-{division}"
        
        # Extract range and beat
        range_match = re.search(r'Range\s+([A-Za-z\s\-]+?)(?:\.|$)', text, re.IGNORECASE)
        if range_match:
            metadata["spatial_context"]["range"] = range_match.group(1).strip()
        
        beat_match = re.search(r'Beat\s+([A-Za-z\s\-]+?)(?:\.|$)', text, re.IGNORECASE)
        if beat_match:
            metadata["spatial_context"]["beat"] = beat_match.group(1).strip()
        
        # Extract plan period with enhanced patterns
        period_patterns = [
            r'Working\s+Plan\s+(?:for\s+)?(\d{4})\s*[-–]\s*(\d{4})',
            r'Plan\s+Period\s*[:=]?\s*(\d{4})\s*[-–]\s*(\d{4})',
            r'(\d{4})\s*[-–]\s*(\d{4})\s+(?:Year\s+)?Plan',
            r'Planning\s+Period\s*[:=]?\s*(\d{4})\s*[-–]\s*(\d{4})',
        ]
        
        for pattern in period_patterns:
            period_match = re.search(pattern, text, re.IGNORECASE)
            if period_match:
                metadata["temporal_context"]["plan_start"] = int(period_match.group(1))
                metadata["temporal_context"]["plan_end"] = int(period_match.group(2))
                metadata["temporal_context"]["plan_duration"] = int(period_match.group(2)) - int(period_match.group(1)) + 1
                break
        
        # Extract plan number
        plan_no_match = re.search(r'Plan\s+(?:No\.?|Number)\s*[:=]?\s*([A-Z0-9\-/]+)', text, re.IGNORECASE)
        if plan_no_match:
            metadata["plan_number"] = plan_no_match.group(1)
        
        # Extract approval information
        approval_patterns = [
            r'Approved\s+(?:on|date)\s*[:=]?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
            r'Approval\s+Date\s*[:=]?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
            r'Date\s+of\s+Approval\s*[:=]?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
        ]
        
        for pattern in approval_patterns:
            approval_match = re.search(pattern, text, re.IGNORECASE)
            if approval_match:
                metadata["approval_date"] = approval_match.group(1)
                break
        
        # Extract authorities
        authority_patterns = [
            (r'Prepared\s+by\s*[:=]?\s*([A-Z][a-zA-Z\s\.]+?)(?:\.|$)', 'preparing_officer'),
            (r'Approved\s+by\s*[:=]?\s*([A-Z][a-zA-Z\s\.]+?)(?:\.|$)', 'approving_authority'),
            (r'Reviewed\s+by\s*[:=]?\s*([A-Z][a-zA-Z\s\.]+?)(?:\.|$)', 'reviewing_authority'),
            (r'DFO\s*[:=]?\s*([A-Z][a-zA-Z\s\.]+?)(?:\.|$)', 'divisional_officer'),
        ]
        
        for pattern, field in authority_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                metadata["authority_context"][field] = match.group(1).strip()
        
        # Extract total area
        area_match = re.search(r'Total\s+(?:forest\s+)?area\s*[:=]?\s*([\d,]+\.?\d*)\s*(?:ha|hectares)', text, re.IGNORECASE)
        if area_match:
            metadata["total_area_ha"] = float(area_match.group(1).replace(',', ''))
        
        # Extract revision information
        revision_match = re.search(r'(?:Revised|Revision)\s+(?:in\s+)?(\d{4})', text, re.IGNORECASE)
        if revision_match:
            metadata["revision_year"] = int(revision_match.group(1))
        
        # Extract plan objectives summary
        objectives = self._extract_plan_objectives(text)
        if objectives:
            metadata["plan_objectives"] = objectives
        
        return metadata
    
    def analyze_plan_structure(self, text: str) -> Dict[str, Any]:
        """Analyze working plan structure"""
        structure = {
            "sections": [],
            "tables": [],
            "figures": [],
            "annexures": [],
            "coverage_analysis": {}
        }
        
        # Extract sections
        section_patterns = [
            (r'(CHAPTER|Chapter)\s+(\d+)[\.:]?\s*(.+?)(?=\n(?:CHAPTER|Chapter|\d+\.|$))', 'chapter'),
            (r'(SECTION|Section)\s+(\d+)[\.:]?\s*(.+?)(?=\n(?:SECTION|Section|\d+\.|$))', 'section'),
            (r'(\d+)\.\s+(.+?)(?=\n\d+\.|\n[A-Z][A-Z\s]{10,})', 'numbered_section'),
        ]
        
        for pattern, section_type in section_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
            for match in matches:
                if len(match) >= 3:
                    section_text = match[2] if isinstance(match, tuple) else match
                    structure["sections"].append({
                        "type": section_type,
                        "number": match[1] if isinstance(match, tuple) else "unknown",
                        "title": section_text.strip()[:100],
                        "length": len(section_text)
                    })
        
        # Extract tables
        table_matches = re.findall(r'TABLE\s+([IVXLCDM\d]+)[\.:]?\s*(.+?)(?=\n(?:TABLE|FIGURE|ANNEX|$))', 
                                  text, re.IGNORECASE | re.DOTALL)
        for match in table_matches:
            structure["tables"].append({
                "number": match[0],
                "title": match[1].strip()[:100],
                "type": self._classify_table_content(match[1])
            })
        
        # Calculate coverage metrics
        if structure["sections"]:
            total_length = sum(s["length"] for s in structure["sections"])
            structure["coverage_analysis"] = {
                "total_sections": len(structure["sections"]),
                "total_tables": len(structure["tables"]),
                "avg_section_length": total_length / len(structure["sections"]),
                "has_compartments_section": any('compartment' in s["title"].lower() for s in structure["sections"]),
                "has_prescriptions_section": any('prescription' in s["title"].lower() or 
                                                'treatment' in s["title"].lower() for s in structure["sections"]),
                "has_yield_section": any('yield' in s["title"].lower() or 
                                        'volume' in s["title"].lower() for s in structure["sections"])
            }
        
        return structure
    
    def extract_enhanced_compartments(self, text: str, metadata: Dict) -> List[Compartment]:
        """Extract enhanced compartments with spatial attributes"""
        compartments = []
        compartment_data = {}
        
        # First pass: Identify all compartment references
        for pattern in self.compartment_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                comp_number = match.group(1)
                if comp_number not in compartment_data:
                    compartment_data[comp_number] = {
                        "number": comp_number,
                        "context": self._get_context(text, match.start(), match.end(), 10),
                        "position": match.start()
                    }
        
        # Process each compartment
        for comp_number, data in compartment_data.items():
            context = data["context"]
            
            # Create spatial location
            spatial = SpatialLocation(
                division=metadata.get("spatial_context", {}).get("division", "Unknown"),
                range=metadata.get("spatial_context", {}).get("range"),
                beat=metadata.get("spatial_context", {}).get("beat"),
                compartment=comp_number
            )
            
            # Extract area
            area = None
            area_patterns = [
                r'Area\s*[:=]?\s*([\d,]+\.?\d*)\s*(?:ha|hectares)',
                r'([\d,]+\.?\d*)\s*(?:ha|hectares)\s+area',
                r'Extent\s*[:=]?\s*([\d,]+\.?\d*)\s*(?:ha|hectares)',
            ]
            
            for pattern in area_patterns:
                area_match = re.search(pattern, context, re.IGNORECASE)
                if area_match:
                    try:
                        area = float(area_match.group(1).replace(',', ''))
                        break
                    except ValueError:
                        pass
            
            # Extract elevation
            elevation_min = None
            elevation_max = None
            elev_pattern = r'Elevation\s*[:=]?\s*(\d+)\s*[-–]\s*(\d+)\s*(?:m|meters)'
            elev_match = re.search(elev_pattern, context, re.IGNORECASE)
            if elev_match:
                try:
                    elevation_min = float(elev_match.group(1))
                    elevation_max = float(elev_match.group(2))
                    spatial.elevation_min = elevation_min
                    spatial.elevation_max = elevation_max
                except ValueError:
                    pass
            
            # Extract aspect
            for aspect in KPK_ENTITIES.get("ASPECTS", []):
                if re.search(rf'\b{aspect}\b', context, re.IGNORECASE):
                    spatial.aspect = aspect
                    break
            
            # Extract slope class
            for slope_class in KPK_ENTITIES.get("SLOPE_CLASSES", []):
                if slope_class.split()[0].lower() in context.lower():
                    spatial.slope_class = slope_class
                    break
            
            # Extract soil type
            for soil_type in KPK_ENTITIES.get("SOIL_TYPES", []):
                if soil_type.lower() in context.lower():
                    spatial.soil_type = soil_type
                    break
            
            # Determine compartment type
            comp_type = "productive"
            type_patterns = {
                "protection": r'protection|conservation|preserved',
                "research": r'research|experimental|demo',
                "community": r'community|guzara|village',
                "recreation": r'recreation|tourist|picnic',
                "grazing": r'grazing|pasture|livestock',
            }
            
            for type_name, pattern in type_patterns.items():
                if re.search(pattern, context, re.IGNORECASE):
                    comp_type = type_name
                    break
            
            # Determine compartment status
            status = CompartmentStatus.PENDING
            status_patterns = {
                CompartmentStatus.ACTIVE: r'active|current|ongoing',
                CompartmentStatus.COMPLETED: r'completed|finished|done',
                CompartmentStatus.PROTECTED: r'protected|reserved|sanctuary',
                CompartmentStatus.RESTRICTED: r'restricted|closed|banned',
                CompartmentStatus.COMMUNITY: r'community|joint|participatory',
            }
            
            for status_enum, pattern in status_patterns.items():
                if re.search(pattern, context, re.IGNORECASE):
                    status = status_enum
                    break
            
            # Extract compartment class (I, II, III)
            comp_class = None
            class_match = re.search(r'Class\s+([IVXLCDM\d])', context, re.IGNORECASE)
            if class_match:
                comp_class = class_match.group(1)
            
            # Extract legal status
            legal_status = None
            legal_patterns = [
                r'Reserved\s+Forest',
                r'Protected\s+Forest',
                r'Guzara\s+Forest',
                r'Riverine\s+Forest',
            ]
            
            for pattern in legal_patterns:
                if re.search(pattern, context, re.IGNORECASE):
                    legal_status = pattern.split()[0]
                    break
            
            # Calculate conservation value (simple heuristic)
            conservation_value = 0.5
            if comp_type == "protection":
                conservation_value = 0.9
            elif comp_type == "community":
                conservation_value = 0.7
            elif "biodiversity" in context.lower():
                conservation_value = 0.8
            
            # Calculate extraction potential
            extraction_potential = 0.5
            if comp_type == "productive" and status.allows_extraction:
                extraction_potential = 0.8
            elif comp_type == "protection":
                extraction_potential = 0.1
            
            # Create compartment object
            compartment = Compartment(
                number=comp_number,
                spatial=spatial,
                area_ha=area,
                compartment_type=comp_type,
                compartment_status=status,
                compartment_class=comp_class,
                legal_status=legal_status,
                conservation_value=conservation_value,
                extraction_potential=extraction_potential,
                biodiversity_index=conservation_value,  # Simplified
                fragmentation_level=self._assess_fragmentation(context)
            )
            
            compartments.append(compartment)
        
        # Sort compartments by number
        compartments.sort(key=lambda x: self._parse_compartment_number(x.number))
        
        return compartments
    
    def extract_enhanced_prescriptions(self, text: str, compartments: List[Compartment]) -> List[SilviculturalPrescription]:
        """Extract enhanced prescriptions with legal and compliance context"""
        prescriptions = []
        prescription_counter = 1
        
        # Extract prescription sections
        prescription_sections = self._extract_prescription_sections(text)
        
        for section_idx, section_text in enumerate(prescription_sections):
            # Identify target compartments
            target_compartments = []
            for compartment in compartments:
                if compartment.number in section_text:
                    target_compartments.append(compartment.number)
            
            if not target_compartments:
                continue
            
            # For each compartment mentioned, create a prescription
            for compartment_id in target_compartments[:3]:  # Limit to 3 compartments per section
                # Determine prescription type
                pres_type = "unknown"
                pres_subtype = None
                for type_name, type_data in self.prescription_type_patterns.items():
                    for pattern in type_data["patterns"]:
                        if re.search(pattern, section_text, re.IGNORECASE):
                            pres_type = type_name
                            # Check for subtype
                            subtype_match = re.search(rf'{type_name}\s+\((.+?)\)', section_text, re.IGNORECASE)
                            if subtype_match:
                                pres_subtype = subtype_match.group(1)
                            break
                    if pres_type != "unknown":
                        break
                
                # Generate prescription ID
                pres_id = f"PRES-{compartment_id}-{prescription_counter:03d}"
                prescription_counter += 1
                
                # Determine priority
                priority = PrescriptionPriority.MEDIUM
                priority_patterns = {
                    PrescriptionPriority.IMMEDIATE: r'immediate|urgent|priority|ASAP',
                    PrescriptionPriority.HIGH: r'high\s+priority|important|critical',
                    PrescriptionPriority.LOW: r'low\s+priority|optional|when\s+possible',
                    PrescriptionPriority.MONITORING: r'monitoring|observation|surveillance',
                }
                
                for prio_enum, pattern in priority_patterns.items():
                    if re.search(pattern, section_text, re.IGNORECASE):
                        priority = prio_enum
                        break
                
                # Extract treatment area
                treatment_area = None
                area_pattern = r'Area\s*[:=]?\s*([\d,]+\.?\d*)\s*(?:ha|hectares)'
                area_match = re.search(area_pattern, section_text, re.IGNORECASE)
                if area_match:
                    try:
                        treatment_area = float(area_match.group(1).replace(',', ''))
                    except ValueError:
                        pass
                
                # Extract treatment year
                treatment_year = None
                year_match = re.search(r'Year\s+(\d{4})', section_text, re.IGNORECASE)
                if year_match:
                    try:
                        treatment_year = int(year_match.group(1))
                    except ValueError:
                        pass
                
                # Extract duration
                duration_months = None
                duration_match = re.search(r'duration\s+of\s+(\d+)\s+months', section_text, re.IGNORECASE)
                if duration_match:
                    try:
                        duration_months = int(duration_match.group(1))
                    except ValueError:
                        pass
                
                # Extract species mix
                species_mix = {}
                species_patterns = [
                    r'(\w+)\s*[:=]?\s*(\d+)\s*%',
                    r'(\d+)\s*%\s*(\w+)',
                ]
                
                for pattern in species_patterns:
                    matches = re.findall(pattern, section_text, re.IGNORECASE)
                    for match in matches:
                        if len(match) == 2:
                            species, percentage = match
                            try:
                                species_norm = self._normalize_species_name(species)
                                species_mix[species_norm] = float(percentage)
                            except ValueError:
                                pass
                
                # Extract expected yield
                expected_yield = None
                yield_pattern = r'yield\s*[:=]?\s*([\d,]+\.?\d*)\s*(?:m³|m3|cubic)'
                yield_match = re.search(yield_pattern, section_text, re.IGNORECASE)
                if yield_match:
                    try:
                        expected_yield = float(yield_match.group(1).replace(',', ''))
                    except ValueError:
                        pass
                
                # Determine legal requirements based on prescription type
                legal_requirements = []
                if pres_type in self.prescription_type_patterns:
                    legal_requirements = self.prescription_type_patterns[pres_type].get("legal_requirements", [])
                
                # Determine environmental impact
                environmental_impact = "moderate"
                if pres_type in self.prescription_type_patterns:
                    environmental_impact = self.prescription_type_patterns[pres_type].get("environmental_impact", "moderate")
                
                # Estimate budget (simplified)
                budget_estimate = None
                if treatment_area and expected_yield:
                    # Rough estimate: PKR 5000 per hectare for treatment
                    budget_estimate = treatment_area * 5000
                
                # Create prescription object
                prescription = SilviculturalPrescription(
                    id=pres_id,
                    compartment_id=compartment_id,
                    prescription_type=pres_type,
                    prescription_subtype=pres_subtype,
                    description=self._clean_prescription_description(section_text),
                    priority=priority,
                    treatment_area_ha=treatment_area,
                    treatment_year=treatment_year,
                    duration_months=duration_months,
                    species_mix=species_mix if species_mix else None,
                    expected_yield_m3=expected_yield,
                    yield_confidence=0.7,
                    budget_estimate_pkr=budget_estimate,
                    legal_requirements=legal_requirements,
                    authority_approval_required=True,
                    environmental_impact=environmental_impact,
                    community_benefits=self._extract_community_benefits(section_text),
                    risk_factors=self._extract_risk_factors(section_text)
                )
                
                prescriptions.append(prescription)
        
        return prescriptions
    
    def extract_enhanced_yield_calculations(self, text: str, 
                                          compartments: List[Compartment],
                                          prescriptions: List[SilviculturalPrescription]) -> List[YieldCalculation]:
        """Extract enhanced yield calculations with uncertainty modeling"""
        yield_calcs = []
        yield_counter = 1
        
        # Extract yield sections
        yield_sections = self._extract_yield_sections(text)
        
        for section_text in yield_sections:
            # Identify compartments mentioned
            mentioned_compartments = []
            for compartment in compartments:
                if compartment.number in section_text:
                    mentioned_compartments.append(compartment.number)
            
            if not mentioned_compartments:
                continue
            
            # Extract species mentioned
            species_mentioned = []
            for species_id in KPK_ENTITIES.get("TREE_SPECIES", {}):
                common_name = species_id.replace('_', ' ')
                if common_name in section_text.lower():
                    species_mentioned.append(species_id)
            
            if not species_mentioned:
                species_mentioned = ["mixed"]
            
            # For each compartment and species combination
            for compartment_id in mentioned_compartments[:2]:  # Limit combinations
                for species in species_mentioned[:2]:
                    # Generate yield calculation ID
                    yield_id = f"YIELD-{compartment_id}-{species[:3].upper()}-{yield_counter:03d}"
                    yield_counter += 1
                    
                    # Extract standing volume
                    standing_volume = None
                    volume_patterns = [
                        r'standing\s+(?:volume|stock)\s*[:=]?\s*([\d,]+\.?\d*)',
                        r'volume\s*[:=]?\s*([\d,]+\.?\d*)\s*(?:m³|m3)',
                    ]
                    
                    for pattern in volume_patterns:
                        volume_match = re.search(pattern, section_text, re.IGNORECASE)
                        if volume_match:
                            try:
                                standing_volume = float(volume_match.group(1).replace(',', ''))
                                break
                            except ValueError:
                                pass
                    
                    # Extract annual allowable cut
                    aac = None
                    aac_patterns = [
                        r'annual\s+allowable\s+cut\s*[:=]?\s*([\d,]+\.?\d*)',
                        r'A\.?A\.?C\.?\s*[:=]?\s*([\d,]+\.?\d*)',
                    ]
                    
                    for pattern in aac_patterns:
                        aac_match = re.search(pattern, section_text, re.IGNORECASE)
                        if aac_match:
                            try:
                                aac = float(aac_match.group(1).replace(',', ''))
                                break
                            except ValueError:
                                pass
                    
                    # Determine calculation method
                    calculation_method = "volume_table"
                    for method, method_data in self.yield_methods.items():
                        if method in section_text.lower():
                            calculation_method = method
                            break
                    
                    # Calculate confidence based on method
                    confidence = self.yield_methods.get(calculation_method, {}).get("confidence", 0.7)
                    
                    # Estimate sustainable yield index
                    sustainable_yield_index = None
                    if standing_volume and aac:
                        sustainable_yield_index = min(1.0, aac / standing_volume * 10) if standing_volume > 0 else 0
                    
                    # Estimate carbon storage (rough: 1 m³ wood ≈ 0.25 tonnes carbon)
                    carbon_storage = None
                    if standing_volume:
                        carbon_storage = standing_volume * 0.25
                    
                    # Create yield calculation object
                    yield_calc = YieldCalculation(
                        id=yield_id,
                        compartment_id=compartment_id,
                        species=species,
                        calculation_method=calculation_method,
                        standing_volume_m3=standing_volume,
                        standing_volume_confidence=confidence,
                        annual_allowable_cut_m3=aac,
                        aac_confidence=confidence * 0.9,  # AAC typically less certain
                        sustainable_yield_index=sustainable_yield_index,
                        carbon_storage_tonnes=carbon_storage,
                        calculation_assumptions=self._extract_calculation_assumptions(section_text),
                        data_sources=self._extract_data_sources(section_text)
                    )
                    
                    yield_calcs.append(yield_calc)
        
        return yield_calcs
    
    def extract_enhanced_management_directives(self, text: str) -> List[ManagementDirective]:
        """Extract enhanced management directives"""
        directives = []
        directive_counter = 1
        
        # Directive patterns
        directive_patterns = [
            (r'Management\s+Objective\s*[:=]?\s*(.+?)(?=\n\n|\n[A-Z]{3,}|$)', "objective", "strategic"),
            (r'Goal\s*[:=]?\s*(.+?)(?=\n\n|\n[A-Z]{3,}|$)', "goal", "strategic"),
            (r'Strategy\s*[:=]?\s*(.+?)(?=\n\n|\n[A-Z]{3,}|$)', "strategy", "tactical"),
            (r'Action\s+Plan\s*[:=]?\s*(.+?)(?=\n\n|\n[A-Z]{3,}|$)', "action", "operational"),
            (r'Directive\s*[:=]?\s*(.+?)(?=\n\n|\n[A-Z]{3,}|$)', "directive", "operational"),
            (r'Regulation\s*[:=]?\s*(.+?)(?=\n\n|\n[A-Z]{3,}|$)', "regulation", "strategic"),
        ]
        
        for pattern, d_type, d_level in directive_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
            for match in matches:
                if isinstance(match, str):
                    directive_text = match.strip()
                elif isinstance(match, tuple):
                    directive_text = match[0].strip()
                else:
                    continue
                
                if directive_text:
                    # Generate directive ID
                    dir_id = f"DIR-{d_type[:3].upper()}-{directive_counter:03d}"
                    directive_counter += 1
                    
                    # Extract responsible authority
                    responsible_authority = None
                    authority_patterns = [
                        r'DFO',
                        r'Range\s+Officer',
                        r'Beat\s+Officer',
                        r'Forest\s+Guard',
                    ]
                    
                    for auth_pattern in authority_patterns:
                        if re.search(auth_pattern, directive_text, re.IGNORECASE):
                            responsible_authority = auth_pattern
                            break
                    
                    # Determine authority hierarchy level
                    authority_level = 3  # Default: range level
                    if responsible_authority:
                        if 'DFO' in responsible_authority:
                            authority_level = 2
                        elif 'Beat' in responsible_authority:
                            authority_level = 4
                        elif 'Guard' in responsible_authority:
                            authority_level = 5
                    
                    # Extract timeline
                    timeline = None
                    timeline_match = re.search(r'within\s+(\d+)\s+(?:months|years)', directive_text, re.IGNORECASE)
                    if timeline_match:
                        timeline = f"{timeline_match.group(1)} {timeline_match.group(2)}"
                    
                    # Extract performance indicators
                    performance_indicators = []
                    indicator_matches = re.findall(r'(\w+)\s+(?:rate|percentage|level)\s+(?:of|:)\s+\d', 
                                                  directive_text, re.IGNORECASE)
                    performance_indicators.extend(indicator_matches)
                    
                    # Create directive object
                    directive = ManagementDirective(
                        id=dir_id,
                        directive_type=d_type,
                        directive_level=d_level,
                        text=directive_text,
                        responsible_authority=responsible_authority,
                        implementation_timeline=timeline,
                        authority_hierarchy_level=authority_level,
                        performance_indicators=performance_indicators if performance_indicators else None
                    )
                    
                    directives.append(directive)
        
        return directives
    
    def analyze_spatial_relationships(self, text: str, compartments: List[Compartment]) -> List[Dict[str, Any]]:
        """Analyze spatial relationships between compartments"""
        relationships = []
        
        for pattern, rel_type in self.spatial_relationship_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                source_comp = None
                target_comp = match.group(1)
                
                # Find source compartment (look back in text)
                context_start = max(0, match.start() - 100)
                context = text[context_start:match.start()]
                
                for compartment in compartments:
                    if compartment.number in context:
                        source_comp = compartment.number
                        break
                
                if source_comp and target_comp:
                    relationships.append({
                        "source": source_comp,
                        "target": target_comp,
                        "relationship": rel_type,
                        "confidence": 0.8,
                        "context": match.group(0)
                    })
        
        return relationships
    
    def analyze_temporal_structure(self, text: str, prescriptions: List[SilviculturalPrescription]) -> Dict[str, Any]:
        """Analyze temporal structure of the plan"""
        temporal = {
            "phases": [],
            "timeline": {},
            "dependencies": [],
            "critical_path": []
        }
        
        # Extract plan phases
        phase_matches = re.findall(r'Phase\s+([IVXLCDM]+)[\.:]?\s*(.+?)(?=\nPhase|\n\d+\.|$)', 
                                  text, re.IGNORECASE | re.DOTALL)
        for match in phase_matches:
            temporal["phases"].append({
                "phase": match[0],
                "description": match[1].strip()[:200],
                "duration": self._estimate_phase_duration(match[1])
            })
        
        # Analyze prescription timeline
        prescription_years = [p.treatment_year for p in prescriptions if p.treatment_year]
        if prescription_years:
            temporal["timeline"] = {
                "start_year": min(prescription_years),
                "end_year": max(prescription_years),
                "duration_years": max(prescription_years) - min(prescription_years) + 1,
                "prescriptions_per_year": len(prescriptions) / (max(prescription_years) - min(prescription_years) + 1)
            }
        
        # Identify temporal dependencies
        for prescription in prescriptions:
            if prescription.temporal_dependencies:
                for dep in prescription.temporal_dependencies:
                    temporal["dependencies"].append({
                        "dependent": prescription.id,
                        "depends_on": dep,
                        "type": "temporal"
                    })
        
        return temporal
    
    def create_rag_optimized_chunks(self, text: str, compartments: List[Compartment],
                                  prescriptions: List[SilviculturalPrescription],
                                  yield_calcs: List[YieldCalculation],
                                  directives: List[ManagementDirective],
                                  spatial_relationships: List[Dict],
                                  temporal_analysis: Dict) -> List[RAGChunk]:
        """Create RAG-optimized chunks for working plan data"""
        chunks = []
        chunk_counter = 1
        
        # Chunk 1: Plan overview and metadata
        overview_chunk = RAGChunk(
            chunk_id=f"CHUNK-OVERVIEW-{chunk_counter:03d}",
            text=self._create_overview_text(compartments, prescriptions, yield_calcs, directives),
            chunk_type="plan_overview",
            spatial_context={"type": "regional", "scale": "division"},
            temporal_context={"type": "plan_period", "scale": "years"},
            compartment_ids=[c.number for c in compartments[:10]],  # Limit
            prescription_ids=[p.id for p in prescriptions[:5]],
            directive_ids=[d.id for d in directives[:5]],
            legal_significance=0.7,
            spatial_importance=0.3,
            temporal_importance=0.8,
            implementation_priority=0.9
        )
        chunks.append(overview_chunk)
        chunk_counter += 1
        
        # Chunk 2: Compartment details (grouped by type)
        compartments_by_type = {}
        for comp in compartments:
            comp_type = comp.compartment_type
            if comp_type not in compartments_by_type:
                compartments_by_type[comp_type] = []
            compartments_by_type[comp_type].append(comp)
        
        for comp_type, type_compartments in compartments_by_type.items():
            if type_compartments:
                # Limit to 5 compartments per type
                sample_comps = type_compartments[:5]
                chunk_text = f"{comp_type.upper()} COMPARTMENTS:\n"
                for comp in sample_comps:
                    chunk_text += f"- {comp.number}: {comp.area_ha} ha, {comp.compartment_status.value}, "
                    chunk_text += f"Elevation: {comp.spatial.elevation_min}-{comp.spatial.elevation_max}m\n"
                
                chunk = RAGChunk(
                    chunk_id=f"CHUNK-COMP-{comp_type.upper()}-{chunk_counter:03d}",
                    text=chunk_text,
                    chunk_type="compartment_group",
                    spatial_context={"type": "compartment_group", "compartment_type": comp_type},
                    temporal_context={"type": "ongoing"},
                    compartment_ids=[c.number for c in sample_comps],
                    prescription_ids=[],
                    directive_ids=[],
                    legal_significance=0.6,
                    spatial_importance=0.8,
                    temporal_importance=0.4,
                    implementation_priority=0.7 if comp_type == "productive" else 0.5
                )
                chunks.append(chunk)
                chunk_counter += 1
        
        # Chunk 3: Prescription highlights (grouped by priority)
        prescriptions_by_priority = {}
        for pres in prescriptions:
            priority = pres.priority.name if pres.priority else "MEDIUM"
            if priority not in prescriptions_by_priority:
                prescriptions_by_priority[priority] = []
            prescriptions_by_priority[priority].append(pres)
        
        for priority, priority_prescriptions in prescriptions_by_priority.items():
            if priority_prescriptions:
                # Limit to 3 prescriptions per priority
                sample_pres = priority_prescriptions[:3]
                chunk_text = f"{priority} PRIORITY PRESCRIPTIONS:\n"
                for pres in sample_pres:
                    chunk_text += f"- {pres.id} for {pres.compartment_id}: {pres.prescription_type}, "
                    chunk_text += f"Area: {pres.treatment_area_ha} ha, "
                    if pres.expected_yield_m3:
                        chunk_text += f"Yield: {pres.expected_yield_m3} m³\n"
                    else:
                        chunk_text += "\n"
                
                chunk = RAGChunk(
                    chunk_id=f"CHUNK-PRES-{priority}-{chunk_counter:03d}",
                    text=chunk_text,
                    chunk_type="prescription_group",
                    spatial_context={"type": "prescription_group", "priority": priority},
                    temporal_context={"type": "prescription_timeline"},
                    compartment_ids=list(set([p.compartment_id for p in sample_pres])),
                    prescription_ids=[p.id for p in sample_pres],
                    directive_ids=[],
                    legal_significance=0.8 if priority in ["IMMEDIATE", "HIGH"] else 0.6,
                    spatial_importance=0.7,
                    temporal_importance=0.9 if priority in ["IMMEDIATE", "HIGH"] else 0.6,
                    implementation_priority=1.0 if priority == "IMMEDIATE" else 0.8
                )
                chunks.append(chunk)
                chunk_counter += 1
        
        # Chunk 4: Yield calculation summary
        if yield_calcs:
            chunk_text = "YIELD CALCULATION SUMMARY:\n"
            # Group by compartment
            yields_by_comp = {}
            for yc in yield_calcs:
                if yc.compartment_id not in yields_by_comp:
                    yields_by_comp[yc.compartment_id] = []
                yields_by_comp[yc.compartment_id].append(yc)
            
            for comp_id, comp_yields in list(yields_by_comp.items())[:5]:  # Limit to 5 compartments
                chunk_text += f"\nCompartment {comp_id}:\n"
                for yc in comp_yields[:3]:  # Limit to 3 yields per compartment
                    chunk_text += f"  - {yc.species}: Standing: {yc.standing_volume_m3} m³, "
                    chunk_text += f"AAC: {yc.annual_allowable_cut_m3} m³\n"
            
            chunk = RAGChunk(
                chunk_id=f"CHUNK-YIELD-SUMMARY-{chunk_counter:03d}",
                text=chunk_text,
                chunk_type="yield_summary",
                spatial_context={"type": "yield_analysis"},
                temporal_context={"type": "annual"},
                compartment_ids=list(yields_by_comp.keys())[:5],
                prescription_ids=[],
                directive_ids=[],
                legal_significance=0.9,
                spatial_importance=0.6,
                temporal_importance=0.7,
                implementation_priority=0.8
            )
            chunks.append(chunk)
            chunk_counter += 1
        
        # Chunk 5: Management directives summary
        if directives:
            chunk_text = "MANAGEMENT DIRECTIVES:\n"
            # Group by type
            directives_by_type = {}
            for directive in directives:
                if directive.directive_type not in directives_by_type:
                    directives_by_type[directive.directive_type] = []
                directives_by_type[directive.directive_type].append(directive)
            
            for dir_type, type_directives in directives_by_type.items():
                chunk_text += f"\n{dir_type.upper()}:\n"
                for directive in type_directives[:3]:  # Limit to 3 per type
                    chunk_text += f"  - {directive.text[:100]}...\n"
            
            chunk = RAGChunk(
                chunk_id=f"CHUNK-DIRECTIVES-{chunk_counter:03d}",
                text=chunk_text,
                chunk_type="directives_summary",
                spatial_context={"type": "management"},
                temporal_context={"type": "directive_timeline"},
                compartment_ids=[],
                prescription_ids=[],
                directive_ids=[d.id for d in directives[:10]],
                legal_significance=0.8,
                spatial_importance=0.4,
                temporal_importance=0.6,
                implementation_priority=0.7
            )
            chunks.append(chunk)
            chunk_counter += 1
        
        return chunks
    
    def create_graph_schema_mapping(self, compartments: List[Compartment],
                                  prescriptions: List[SilviculturalPrescription],
                                  yield_calcs: List[YieldCalculation],
                                  directives: List[ManagementDirective],
                                  spatial_relationships: List[Dict]) -> Optional[GraphSchemaMapping]:
        """Create Neo4j graph schema mapping"""
        if self.pipeline_state.status == "abstained":
            return None
        
        nodes = []
        relationships = []
        
        # Add compartment nodes
        for comp in compartments[:50]:  # Limit to 50 compartments
            nodes.append({
                "id": f"COMPARTMENT_{comp.number}",
                "type": "Compartment",
                "properties": {
                    "number": comp.number,
                    "area_ha": comp.area_ha,
                    "type": comp.compartment_type,
                    "status": comp.compartment_status.value,
                    "conservation_value": comp.conservation_value,
                    "extraction_potential": comp.extraction_potential
                }
            })
        
        # Add prescription nodes
        for pres in prescriptions[:100]:  # Limit to 100 prescriptions
            nodes.append({
                "id": pres.id,
                "type": "Prescription",
                "properties": {
                    "type": pres.prescription_type,
                    "priority": pres.priority.name if pres.priority else "MEDIUM",
                    "area_ha": pres.treatment_area_ha,
                    "expected_yield_m3": pres.expected_yield_m3,
                    "environmental_impact": pres.environmental_impact
                }
            })
            
            # Add relationship: Prescription → Compartment
            relationships.append({
                "source": pres.id,
                "target": f"COMPARTMENT_{pres.compartment_id}",
                "type": "APPLIES_TO",
                "properties": {"relationship": "treatment_assignment"}
            })
        
        # Add spatial relationships
        for rel in spatial_relationships[:50]:  # Limit to 50 relationships
            relationships.append({
                "source": f"COMPARTMENT_{rel['source']}",
                "target": f"COMPARTMENT_{rel['target']}",
                "type": rel['relationship'],
                "properties": {"confidence": rel['confidence']}
            })
        
        # Add directive nodes
        for directive in directives[:20]:  # Limit to 20 directives
            nodes.append({
                "id": directive.id,
                "type": "ManagementDirective",
                "properties": {
                    "type": directive.directive_type,
                    "level": directive.directive_level,
                    "authority_level": directive.authority_hierarchy_level
                }
            })
        
        return GraphSchemaMapping(nodes=nodes, relationships=relationships)
    
    def calculate_enhanced_processing_metrics(self, text: str, compartments: List[Compartment],
                                            prescriptions: List[SilviculturalPrescription],
                                            yield_calcs: List[YieldCalculation],
                                            directives: List[ManagementDirective],
                                            preprocessing_metrics: Dict) -> Dict[str, Any]:
        """Calculate enhanced processing metrics"""
        total_compartments = len(compartments)
        total_prescriptions = len(prescriptions)
        
        # Calculate data completeness
        compartments_with_area = sum(1 for c in compartments if c.area_ha)
        compartments_with_spatial = sum(1 for c in compartments if c.spatial.elevation_min)
        
        prescriptions_with_area = sum(1 for p in prescriptions if p.treatment_area_ha)
        prescriptions_with_yield = sum(1 for p in prescriptions if p.expected_yield_m3)
        
        yield_calcs_with_data = sum(1 for y in yield_calcs if y.standing_volume_m3 or y.annual_allowable_cut_m3)
        
        # Calculate spatial coverage
        spatial_coverage = 0.0
        if compartments_with_spatial > 0:
            spatial_coverage = compartments_with_spatial / total_compartments
        
        # Calculate temporal coverage
        temporal_coverage = 0.0
        prescriptions_with_year = sum(1 for p in prescriptions if p.treatment_year)
        if prescriptions_with_year > 0:
            temporal_coverage = prescriptions_with_year / total_prescriptions
        
        # Calculate plan complexity
        plan_complexity = min(1.0, (total_compartments * 0.01 + total_prescriptions * 0.005))
        
        # Calculate overall confidence
        overall_confidence = (
            preprocessing_metrics.get('ocr_confidence', 0.5) * 0.2 +
            (compartments_with_area / max(1, total_compartments)) * 0.3 +
            (prescriptions_with_area / max(1, total_prescriptions)) * 0.3 +
            spatial_coverage * 0.1 +
            temporal_coverage * 0.1
        )
        
        return {
            "basic_counts": {
                "compartments": total_compartments,
                "prescriptions": total_prescriptions,
                "yield_calculations": len(yield_calcs),
                "directives": len(directives)
            },
            "data_completeness": {
                "compartments_with_area": compartments_with_area,
                "compartments_with_spatial_data": compartments_with_spatial,
                "prescriptions_with_area": prescriptions_with_area,
                "prescriptions_with_yield": prescriptions_with_yield,
                "yield_calcs_with_data": yield_calcs_with_data,
                "spatial_coverage": spatial_coverage,
                "temporal_coverage": temporal_coverage
            },
            "plan_characteristics": {
                "plan_complexity": plan_complexity,
                "avg_prescriptions_per_compartment": total_prescriptions / max(1, total_compartments),
                "compartment_size_diversity": self._calculate_size_diversity(compartments),
                "prescription_type_diversity": len(set(p.prescription_type for p in prescriptions)) / max(1, total_prescriptions)
            },
            "quality_indicators": {
                "ocr_confidence": preprocessing_metrics.get('ocr_confidence', 0.0),
                "parsing_consistency": self._check_parsing_consistency(compartments, prescriptions),
                "spatial_consistency": self._check_spatial_consistency(compartments),
                "temporal_consistency": self._check_temporal_consistency(prescriptions)
            },
            "overall_confidence": overall_confidence,
            "recommended_actions": self._generate_quality_actions(compartments, prescriptions, overall_confidence)
        }
    
    def analyze_plan_quality(self, compartments: List[Compartment],
                           prescriptions: List[SilviculturalPrescription],
                           yield_calcs: List[YieldCalculation],
                           directives: List[ManagementDirective]) -> Dict[str, Any]:
        """Analyze overall plan quality"""
        quality_indicators = {}
        
        # Spatial quality
        spatial_quality = self._assess_spatial_quality(compartments)
        
        # Temporal quality
        temporal_quality = self._assess_temporal_quality(prescriptions)
        
        # Economic viability
        economic_quality = self._assess_economic_quality(prescriptions, yield_calcs)
        
        # Environmental sustainability
        environmental_quality = self._assess_environmental_quality(compartments, prescriptions)
        
        # Implementation feasibility
        implementation_quality = self._assess_implementation_quality(prescriptions, directives)
        
        # Legal compliance
        legal_quality = self._assess_legal_quality(prescriptions, directives)
        
        # Calculate overall quality score
        weights = {
            "spatial": 0.15,
            "temporal": 0.15,
            "economic": 0.20,
            "environmental": 0.20,
            "implementation": 0.15,
            "legal": 0.15
        }
        
        overall_quality = (
            spatial_quality * weights["spatial"] +
            temporal_quality * weights["temporal"] +
            economic_quality * weights["economic"] +
            environmental_quality * weights["environmental"] +
            implementation_quality * weights["implementation"] +
            legal_quality * weights["legal"]
        )
        
        quality_indicators = {
            "spatial_quality": spatial_quality,
            "temporal_quality": temporal_quality,
            "economic_quality": economic_quality,
            "environmental_quality": environmental_quality,
            "implementation_quality": implementation_quality,
            "legal_quality": legal_quality,
            "overall_quality": overall_quality,
            "quality_level": self._get_quality_level(overall_quality)
        }
        
        return quality_indicators
    
    def apply_working_plan_quality_gates(self, compartments: List[Compartment],
                                       prescriptions: List[SilviculturalPrescription],
                                       yield_calcs: List[YieldCalculation],
                                       plan_quality: Dict[str, Any]):
        """Apply quality gates for working plan parsing"""
        # Gate 1: Minimum compartments
        if len(compartments) < 3:
            self.pipeline_state.add_abstention(
                "insufficient_compartments",
                f"Only {len(compartments)} compartments found"
            )
        
        # Gate 2: Plan quality too low
        if plan_quality.get("overall_quality", 0) < 0.4:
            self.pipeline_state.add_warning(
                f"Low plan quality score: {plan_quality.get('overall_quality', 0):.2f}"
            )
        
        # Gate 3: Missing critical data
        compartments_with_area = sum(1 for c in compartments if c.area_ha)
        if compartments_with_area / max(1, len(compartments)) < 0.5:
            self.pipeline_state.add_warning(
                f"Less than 50% of compartments have area data: {compartments_with_area}/{len(compartments)}"
            )
        
        # Gate 4: Temporal inconsistencies
        prescriptions_with_year = sum(1 for p in prescriptions if p.treatment_year)
        if 0 < prescriptions_with_year < len(prescriptions) * 0.3:
            self.pipeline_state.add_warning(
                f"Limited temporal data: only {prescriptions_with_year}/{len(prescriptions)} prescriptions have year"
            )
    
    def update_pipeline_state(self, metadata: Dict, compartments: List[Compartment],
                            prescriptions: List[SilviculturalPrescription],
                            yield_calcs: List[YieldCalculation],
                            directives: List[ManagementDirective],
                            processing_metrics: Dict[str, Any],
                            plan_quality: Dict[str, Any]):
        """Update pipeline state with parsing results"""
        self.pipeline_state.confidence = processing_metrics.get("overall_confidence", 0.0)
        
        self.pipeline_state.metadata.update({
            "parsing_completed": datetime.now().isoformat(),
            "total_compartments": len(compartments),
            "total_prescriptions": len(prescriptions),
            "total_yield_calculations": len(yield_calcs),
            "total_directives": len(directives),
            "plan_quality_score": plan_quality.get("overall_quality", 0.0),
            "plan_quality_level": plan_quality.get("quality_level", "unknown"),
            "division": metadata.get("spatial_context", {}).get("division", "unknown"),
            "plan_period": f"{metadata.get('temporal_context', {}).get('plan_start', '?')}-"
                          f"{metadata.get('temporal_context', {}).get('plan_end', '?')}"
        })
        
        # Add spatial references
        if compartments:
            self.pipeline_state.add_spatial_reference(
                "compartments_extracted",
                [c.number for c in compartments[:10]]
            )
    
    def generate_downstream_recommendations(self, compartments: List[Compartment],
                                          prescriptions: List[SilviculturalPrescription],
                                          yield_calcs: List[YieldCalculation],
                                          plan_quality: Dict[str, Any]) -> Dict[str, Any]:
        """Generate recommendations for downstream phases"""
        recommendations = {
            "phase_4_legal_extraction": {},
            "phase_5_authority_reasoning": {},
            "phase_6_graph_construction": {},
            "phase_7_orchestration": {}
        }
        
        # Recommendations for phase 4
        legal_focus = []
        if any(p.legal_requirements for p in prescriptions if p.legal_requirements):
            legal_focus.append("prescription_legal_requirements")
        if any(c.legal_status for c in compartments if c.legal_status):
            legal_focus.append("compartment_legal_status")
        
        if legal_focus:
            recommendations["phase_4_legal_extraction"] = {
                "focus_areas": legal_focus,
                "priority": "high" if len(legal_focus) > 1 else "medium",
                "extraction_method": "rule_based_with_context"
            }
        
        # Recommendations for phase 5
        if any(p.authority_approval_required for p in prescriptions):
            recommendations["phase_5_authority_reasoning"] = {
                "needs_authority_analysis": True,
                "authority_levels_present": list(set(
                    self.prescription_type_patterns.get(p.prescription_type, {}).get("authority_level", 3)
                    for p in prescriptions
                )),
                "recommended_approach": "hierarchical_authority_model"
            }
        
        # Recommendations for phase 6
        if len(compartments) > 0 and len(prescriptions) > 0:
            recommendations["phase_6_graph_construction"] = {
                "node_types_needed": ["Compartment", "Prescription", "YieldCalculation"],
                "relationship_types_needed": ["APPLIES_TO", "LOCATED_IN", "PRODUCES"],
                "spatial_modeling_recommended": len(compartments) > 10,
                "temporal_modeling_recommended": any(p.treatment_year for p in prescriptions)
            }
        
        # Recommendations for phase 7
        if plan_quality.get("quality_level") == "low":
            recommendations["phase_7_orchestration"] = {
                "quality_concerns": plan_quality,
                "recommended_action": "human_review",
                "review_focus": self._identify_review_focus(plan_quality)
            }
        
        return recommendations
    
    # ========== Helper Methods ==========
    
    def _get_context(self, text: str, start: int, end: int, lines: int = 10) -> str:
        """Get context around a position in text"""
        lines_before = text[:start].split('\n')[-lines:]
        lines_after = text[end:].split('\n')[:lines]
        return '\n'.join(lines_before + lines_after)
    
    def _parse_compartment_number(self, number_str: str) -> Tuple[int, str]:
        """Parse compartment number for sorting"""
        # Extract numeric part
        num_match = re.search(r'(\d+)', number_str)
        if num_match:
            numeric = int(num_match.group(1))
        else:
            numeric = 0
        
        # Extract alphabetic suffix
        alpha_match = re.search(r'[A-Za-z]+', number_str)
        alpha = alpha_match.group(0) if alpha_match else ""
        
        return numeric, alpha
    
    def _extract_prescription_sections(self, text: str) -> List[str]:
        """Extract prescription sections"""
        sections = []
        
        # Look for prescription headers
        prescription_headers = [
            r'PRESCRIPTION',
            r'TREATMENT\s+RECOMMENDED',
            r'SILVICULTURAL\s+TREATMENT',
            r'MANAGEMENT\s+ACTION',
            r'OPERATION\s+PLAN'
        ]
        
        lines = text.split('\n')
        current_section = []
        in_section = False
        
        for line in lines:
            line_upper = line.strip().upper()
            
            # Check if line starts a new section
            is_header = any(re.search(pattern, line_upper) for pattern in prescription_headers)
            
            if is_header:
                if current_section and in_section:
                    sections.append('\n'.join(current_section))
                    current_section = []
                in_section = True
            
            if in_section:
                current_section.append(line)
            
            # Check for end of section
            if in_section and (len(line_upper) < 5 or line_upper.startswith(('TABLE', 'FIGURE', 'CHAPTER'))):
                if current_section:
                    sections.append('\n'.join(current_section))
                    current_section = []
                    in_section = False
        
        if current_section and in_section:
            sections.append('\n'.join(current_section))
        
        return sections
    
    def _extract_yield_sections(self, text: str) -> List[str]:
        """Extract yield calculation sections"""
        sections = []
        
        yield_headers = [
            r'YIELD\s+CALCULATION',
            r'VOLUME\s+ESTIMATE',
            r'STANDING\s+VOLUME',
            r'ANNUAL\s+ALLOWABLE\s+CUT',
            r'GROWTH\s+AND\s+YIELD'
        ]
        
        lines = text.split('\n')
        current_section = []
        in_section = False
        
        for line in lines:
            line_upper = line.strip().upper()
            
            is_header = any(re.search(pattern, line_upper) for pattern in yield_headers)
            
            if is_header:
                if current_section and in_section:
                    sections.append('\n'.join(current_section))
                    current_section = []
                in_section = True
            
            if in_section:
                current_section.append(line)
            
            if in_section and (len(line_upper) < 5 or line_upper.startswith(('PRESCRIPTION', 'COMPARTMENT'))):
                if current_section:
                    sections.append('\n'.join(current_section))
                    current_section = []
                    in_section = False
        
        if current_section and in_section:
            sections.append('\n'.join(current_section))
        
        return sections
    
    def _clean_prescription_description(self, text: str) -> str:
        """Clean prescription description"""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Remove headers
        headers = ['PRESCRIPTION', 'TREATMENT', 'RECOMMENDATION', 'ACTION']
        for header in headers:
            text = re.sub(rf'^{header}[:.]?\s*', '', text, flags=re.IGNORECASE)
        
        # Limit length
        if len(text) > 300:
            text = text[:297] + "..."
        
        return text
    
    def _normalize_species_name(self, species_name: str) -> str:
        """Normalize species name"""
        species_name = species_name.lower().strip()
        
        # Common variations
        variations = {
            'deodar': 'deodar',
            'diar': 'deodar',
            'chir': 'chir_pine',
            'chil': 'chir_pine',
            'kail': 'kail',
            'khael': 'kail',
            'walnut': 'walnut',
            'oak': 'oak',
            'baloot': 'oak',
        }
        
        for variant, normalized in variations.items():
            if variant in species_name:
                return normalized
        
        # Default: use first word
        return species_name.split()[0] if species_name.split() else "unknown"
    
    def _extract_community_benefits(self, text: str) -> List[str]:
        """Extract community benefits from prescription"""
        benefits = []
        benefit_keywords = [
            'employment', 'income', 'fuelwood', 'fodder', 'water',
            'medicinal', 'recreation', 'education', 'training'
        ]
        
        for keyword in benefit_keywords:
            if keyword in text.lower():
                benefits.append(keyword)
        
        return benefits if benefits else None
    
    def _extract_risk_factors(self, text: str) -> List[str]:
        """Extract risk factors from prescription"""
        risks = []
        risk_keywords = [
            'fire', 'disease', 'pest', 'erosion', 'landslide',
            'flood', 'drought', 'illegal', 'conflict', 'funding'
        ]
        
        for keyword in risk_keywords:
            if keyword in text.lower():
                risks.append(keyword)
        
        return risks if risks else None
    
    def _extract_calculation_assumptions(self, text: str) -> List[str]:
        """Extract calculation assumptions"""
        assumptions = []
        
        # Look for assumption indicators
        assumption_patterns = [
            r'assuming\s+(.+?)(?:\.|$)',
            r'assumption\s*[:=]?\s*(.+?)(?:\.|$)',
            r'based\s+on\s+(.+?)(?:\.|$)',
        ]
        
        for pattern in assumption_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            assumptions.extend(matches)
        
        return assumptions if assumptions else None
    
    def _extract_data_sources(self, text: str) -> List[str]:
        """Extract data sources"""
        sources = []
        
        source_keywords = [
            'inventory', 'survey', 'measurement', 'plot', 'sample',
            'remote sensing', 'satellite', 'field data', 'records'
        ]
        
        for keyword in source_keywords:
            if keyword in text.lower():
                sources.append(keyword)
        
        return sources if sources else None
    
    def _extract_plan_objectives(self, text: str) -> List[str]:
        """Extract plan objectives"""
        objectives = []
        
        objective_patterns = [
            r'objective\s*[:=]?\s*(.+?)(?=\n\n|\n[A-Z]{3,}|$)',
            r'purpose\s*[:=]?\s*(.+?)(?=\n\n|\n[A-Z]{3,}|$)',
            r'aim\s*[:=]?\s*(.+?)(?=\n\n|\n[A-Z]{3,}|$)',
        ]
        
        for pattern in objective_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
            for match in matches:
                if isinstance(match, str):
                    objectives.append(match.strip())
        
        return objectives[:5] if objectives else None  # Limit to 5
    
    def _classify_table_content(self, table_text: str) -> str:
        """Classify table content type"""
        table_lower = table_text.lower()
        
        if any(word in table_lower for word in ['compartment', 'area', 'elevation']):
            return "compartment_data"
        elif any(word in table_lower for word in ['prescription', 'treatment', 'silvicultural']):
            return "prescription_data"
        elif any(word in table_lower for word in ['yield', 'volume', 'aac']):
            return "yield_data"
        elif any(word in table_lower for word in ['species', 'composition', 'mix']):
            return "species_data"
        else:
            return "general_data"
    
    def _estimate_phase_duration(self, phase_text: str) -> str:
        """Estimate phase duration"""
        if 'year' in phase_text.lower():
            return "1 year"
        elif 'month' in phase_text.lower():
            months_match = re.search(r'(\d+)\s+months', phase_text.lower())
            if months_match:
                return f"{months_match.group(1)} months"
        return "unknown"
    
    def _assess_fragmentation(self, context: str) -> str:
        """Assess fragmentation level from context"""
        if 'fragmented' in context.lower() or 'patchy' in context.lower():
            return "high"
        elif 'isolated' in context.lower() or 'scattered' in context.lower():
            return "medium"
        else:
            return "low"
    
    def _create_overview_text(self, compartments: List[Compartment],
                            prescriptions: List[SilviculturalPrescription],
                            yield_calcs: List[YieldCalculation],
                            directives: List[ManagementDirective]) -> str:
        """Create overview text for RAG chunk"""
        overview = "WORKING PLAN OVERVIEW\n\n"
        
        # Compartment summary
        overview += f"COMPARTMENTS: {len(compartments)} total\n"
        if compartments:
            area_sum = sum(c.area_ha for c in compartments if c.area_ha)
            overview += f"Total area: {area_sum:.1f} ha\n"
            
            # Count by type
            types_count = {}
            for comp in compartments:
                types_count[comp.compartment_type] = types_count.get(comp.compartment_type, 0) + 1
            
            for comp_type, count in types_count.items():
                overview += f"  - {comp_type}: {count} compartments\n"
        
        # Prescription summary
        overview += f"\nPRESCRIPTIONS: {len(prescriptions)} total\n"
        if prescriptions:
            # Count by type
            pres_types = {}
            for pres in prescriptions:
                pres_types[pres.prescription_type] = pres_types.get(pres.prescription_type, 0) + 1
            
            for pres_type, count in pres_types.items():
                overview += f"  - {pres_type}: {count} prescriptions\n"
        
        # Yield summary
        overview += f"\nYIELD CALCULATIONS: {len(yield_calcs)} total\n"
        
        # Directives summary
        overview += f"\nMANAGEMENT DIRECTIVES: {len(directives)} total\n"
        
        return overview
    
    def _calculate_size_diversity(self, compartments: List[Compartment]) -> float:
        """Calculate diversity of compartment sizes"""
        areas = [c.area_ha for c in compartments if c.area_ha]
        if len(areas) < 2:
            return 0.0
        
        # Coefficient of variation
        mean = sum(areas) / len(areas)
        variance = sum((x - mean) ** 2 for x in areas) / len(areas)
        std_dev = math.sqrt(variance)
        
        return std_dev / mean if mean > 0 else 0.0
    
    def _check_parsing_consistency(self, compartments: List[Compartment],
                                 prescriptions: List[SilviculturalPrescription]) -> float:
        """Check parsing consistency"""
        # Check if compartments mentioned in prescriptions exist
        mentioned_compartments = set(p.compartment_id for p in prescriptions)
        existing_compartments = set(c.number for c in compartments)
        
        matches = mentioned_compartments.intersection(existing_compartments)
        if mentioned_compartments:
            return len(matches) / len(mentioned_compartments)
        
        return 1.0  # No prescriptions to check against
    
    def _check_spatial_consistency(self, compartments: List[Compartment]) -> float:
        """Check spatial consistency"""
        # Check elevation consistency
        elevations_valid = 0
        for comp in compartments:
            if comp.spatial.elevation_min and comp.spatial.elevation_max:
                if 0 < comp.spatial.elevation_min <= comp.spatial.elevation_max <= 5000:
                    elevations_valid += 1
        
        return elevations_valid / len(compartments) if compartments else 1.0
    
    def _check_temporal_consistency(self, prescriptions: List[SilviculturalPrescription]) -> float:
        """Check temporal consistency"""
        years = [p.treatment_year for p in prescriptions if p.treatment_year]
        if len(years) < 2:
            return 1.0  # Not enough data to assess
        
        # Check if years are in reasonable range (1900-2100)
        valid_years = sum(1900 <= year <= 2100 for year in years)
        return valid_years / len(years)
    
    def _generate_quality_actions(self, compartments: List[Compartment],
                                prescriptions: List[SilviculturalPrescription],
                                confidence: float) -> List[str]:
        """Generate quality improvement actions"""
        actions = []
        
        if len(compartments) < 5:
            actions.append("Consider manual review: Few compartments detected")
        
        if confidence < 0.7:
            actions.append("Consider OCR quality improvement")
        
        compartments_without_area = sum(1 for c in compartments if not c.area_ha)
        if compartments_without_area > len(compartments) * 0.3:
            actions.append(f"Missing area data for {compartments_without_area} compartments")
        
        return actions
    
    def _assess_spatial_quality(self, compartments: List[Compartment]) -> float:
        """Assess spatial data quality"""
        if not compartments:
            return 0.0
        
        scores = []
        for comp in compartments:
            comp_score = 0.0
            
            # Area data
            if comp.area_ha:
                comp_score += 0.3
            
            # Elevation data
            if comp.spatial.elevation_min and comp.spatial.elevation_max:
                comp_score += 0.3
            
            # Aspect data
            if comp.spatial.aspect:
                comp_score += 0.2
            
            # Soil data
            if comp.spatial.soil_type:
                comp_score += 0.2
            
            scores.append(comp_score)
        
        return sum(scores) / len(scores) if scores else 0.0
    
    def _assess_temporal_quality(self, prescriptions: List[SilviculturalPrescription]) -> float:
        """Assess temporal data quality"""
        if not prescriptions:
            return 0.0
        
        scores = []
        for pres in prescriptions:
            pres_score = 0.0
            
            # Treatment year
            if pres.treatment_year:
                pres_score += 0.4
            
            # Duration
            if pres.duration_months:
                pres_score += 0.3
            
            # Timeline references
            if pres.priority and pres.priority.is_time_critical:
                pres_score += 0.3
            
            scores.append(pres_score)
        
        return sum(scores) / len(scores) if scores else 0.0
    
    def _assess_economic_quality(self, prescriptions: List[SilviculturalPrescription],
                               yield_calcs: List[YieldCalculation]) -> float:
        """Assess economic data quality"""
        score = 0.0
        
        # Budget estimates
        prescriptions_with_budget = sum(1 for p in prescriptions if p.budget_estimate_pkr)
        if prescriptions:
            score += (prescriptions_with_budget / len(prescriptions)) * 0.4
        
        # Yield data
        yield_calcs_with_data = sum(1 for y in yield_calcs if y.standing_volume_m3 or y.annual_allowable_cut_m3)
        if yield_calcs:
            score += (yield_calcs_with_data / len(yield_calcs)) * 0.4
        
        # Economic value estimates
        yield_calcs_with_value = sum(1 for y in yield_calcs if y.economic_value_pkr)
        if yield_calcs:
            score += (yield_calcs_with_value / len(yield_calcs)) * 0.2
        
        return score
    
    def _assess_environmental_quality(self, compartments: List[Compartment],
                                    prescriptions: List[SilviculturalPrescription]) -> float:
        """Assess environmental data quality"""
        score = 0.0
        
        # Conservation value data
        compartments_with_conservation = sum(1 for c in c.conservation_value > 0 for c in compartments)
        if compartments:
            score += (compartments_with_conservation / len(compartments)) * 0.3
        
        # Biodiversity data
        compartments_with_biodiversity = sum(1 for c in c.biodiversity_index > 0 for c in compartments)
        if compartments:
            score += (compartments_with_biodiversity / len(compartments)) * 0.3
        
        # Environmental impact assessments
        prescriptions_with_impact = sum(1 for p in p.environmental_impact != "moderate" for p in prescriptions)
        if prescriptions:
            score += (prescriptions_with_impact / len(prescriptions)) * 0.4
        
        return score
    
    def _assess_implementation_quality(self, prescriptions: List[SilviculturalPrescription],
                                     directives: List[ManagementDirective]) -> float:
        """Assess implementation data quality"""
        score = 0.0
        
        # Prescription feasibility
        prescriptions_with_resources = sum(1 for p in p.labor_requirements or p.equipment_needed for p in prescriptions)
        if prescriptions:
            score += (prescriptions_with_resources / len(prescriptions)) * 0.4
        
        # Authority requirements
        prescriptions_with_authority = sum(1 for p in p.authority_approval_required for p in prescriptions)
        if prescriptions:
            score += (prescriptions_with_authority / len(prescriptions)) * 0.3
        
        # Monitoring requirements
        prescriptions_with_monitoring = sum(1 for p in p.monitoring_requirements for p in prescriptions)
        if prescriptions:
            score += (prescriptions_with_monitoring / len(prescriptions)) * 0.3
        
        return score
    
    def _assess_legal_quality(self, prescriptions: List[SilviculturalPrescription],
                            directives: List[ManagementDirective]) -> float:
        """Assess legal data quality"""
        score = 0.0
        
        # Prescription legal requirements
        prescriptions_with_legal = sum(1 for p in p.legal_requirements for p in prescriptions)
        if prescriptions:
            score += (prescriptions_with_legal / len(prescriptions)) * 0.6
        
        # Directive legal basis
        directives_with_legal = sum(1 for d in d.legal_basis for d in directives)
        if directives:
            score += (directives_with_legal / len(directives)) * 0.4
        
        return score
    
    def _get_quality_level(self, quality_score: float) -> str:
        """Convert quality score to level"""
        if quality_score >= 0.8:
            return "high"
        elif quality_score >= 0.6:
            return "good"
        elif quality_score >= 0.4:
            return "fair"
        else:
            return "low"
    
    def _identify_review_focus(self, plan_quality: Dict[str, Any]) -> List[str]:
        """Identify focus areas for human review"""
        focus = []
        
        if plan_quality.get("spatial_quality", 0) < 0.5:
            focus.append("spatial_data")
        
        if plan_quality.get("temporal_quality", 0) < 0.5:
            focus.append("temporal_data")
        
        if plan_quality.get("legal_quality", 0) < 0.5:
            focus.append("legal_references")
        
        return focus if focus else ["general_review"]
    
    def identify_spatial_clusters(self, compartments: List[Compartment]) -> List[Dict]:
        """Identify spatial clusters of compartments"""
        # Simplified clustering based on compartment numbers
        clusters = []
        
        # Group by numeric prefix
        compartments_by_prefix = defaultdict(list)
        for comp in compartments:
            # Extract numeric prefix (e.g., "15" from "15A")
            prefix_match = re.match(r'(\d+)', comp.number)
            if prefix_match:
                prefix = prefix_match.group(1)
                compartments_by_prefix[prefix].append(comp.number)
        
        for prefix, comp_numbers in compartments_by_prefix.items():
            if len(comp_numbers) >= 3:  # Minimum cluster size
                clusters.append({
                    "cluster_id": f"CLUSTER-{prefix}",
                    "compartments": comp_numbers,
                    "size": len(comp_numbers),
                    "type": "numeric_group"
                })
        
        return clusters
    
    def calculate_spatial_connectivity(self, compartments: List[Compartment], 
                                     relationships: List[Dict]) -> Dict[str, float]:
        """Calculate spatial connectivity metrics"""
        if not compartments or not relationships:
            return {"connectivity_index": 0.0}
        
        # Create adjacency list
        adjacency = defaultdict(set)
        for rel in relationships:
            adjacency[rel["source"]].add(rel["target"])
            adjacency[rel["target"]].add(rel["source"])
        
        # Calculate connectivity metrics
        total_possible = len(compartments) * (len(compartments) - 1) / 2
        actual_connections = sum(len(neighbors) for neighbors in adjacency.values()) / 2
        
        connectivity_index = actual_connections / total_possible if total_possible > 0 else 0
        
        return {
            "connectivity_index": connectivity_index,
            "total_compartments": len(compartments),
            "total_connections": int(actual_connections),
            "avg_connections_per_compartment": actual_connections / len(compartments) if compartments else 0
        }


# ========== ENHANCED INTEGRATION FUNCTION ==========

def integrate_enhanced_working_plan_with_pipeline(phase_2_output: Dict,
                                                phase_3_1_output: Dict,
                                                phase_3_2_output: Dict,
                                                working_plan_data: Dict) -> Dict:
    """
    Enhanced integration with pipeline phases for working plans.
    
    Args:
        phase_2_output: Output from phase 2 (restoration)
        phase_3_1_output: Output from phase 3.1 (multilingual)
        phase_3_2_output: Output from phase 3.2 (circulars)
        working_plan_data: Enhanced parsed working plan
        
    Returns:
        Integrated data for downstream phases
    """
    integrated_data = {
        "pipeline_progress": {
            "phase_2_completed": bool(phase_2_output),
            "phase_3_1_completed": bool(phase_3_1_output),
            "phase_3_2_completed": bool(phase_3_2_output),
            "phase_3_3_completed": True,
            "current_phase": 3,
            "ready_for_phase_4": working_plan_data["pipeline_state"]["status"] != "abstained"
        },
        "document_analysis": {
            "type": "working_plan",
            "subtype": "forest_management_plan",
            "processing_confidence": working_plan_data["pipeline_state"]["confidence"],
            "abstention_reasons": working_plan_data["pipeline_state"]["abstention_reasons"],
            "warnings": working_plan_data["pipeline_state"]["warnings"],
            "spatial_scope": working_plan_data.get("metadata", {}).get("spatial_context", {}).get("division", "unknown")
        },
        "working_plan_analysis": working_plan_data,
        "multilingual_context": phase_3_1_output.get("language_analysis", {}) if phase_3_1_output else {},
        "circular_context": phase_3_2_output.get("circular_analysis", {}) if phase_3_2_output else {},
        "phase_2_context": phase_2_output.get("processing_metrics", {}) if phase_2_output else {},
        "recommendations_for_downstream": working_plan_data.get("downstream_recommendations", {}),
        "integration_notes": {
            "has_spatial_data": bool(working_plan_data.get("spatial_analysis", {}).get("relationships")),
            "has_temporal_data": bool(working_plan_data.get("temporal_analysis", {}).get("timeline")),
            "has_legal_references": any(
                p.get("legal_requirements") 
                for p in working_plan_data.get("prescriptions", [])
            ),
            "rag_chunks_ready": len(working_plan_data.get("rag_chunks", [])) > 0,
            "graph_schema_ready": working_plan_data.get("graph_schema") is not None
        }
    }
    
    # Add cross-references if available
    if phase_3_2_output and "circular_analysis" in phase_3_2_output:
        circular_refs = phase_3_2_output["circular_analysis"].get("metadata", {})
        if circular_refs.get("circular_number"):
            integrated_data["cross_references"] = {
                "related_circulars": [circular_refs.get("circular_number")],
                "reference_type": "implementation_guidance"
            }
    
    # Prepare data for phase 4
    integrated_data["phase_4_input"] = {
        "compartments_for_legal_extraction": [
            {
                "id": comp["number"],
                "legal_status": comp.get("legal_status"),
                "requires_extraction": comp.get("compartment_type") == "productive"
            }
            for comp in working_plan_data.get("compartments", [])[:20]  # Limit
        ],
        "prescriptions_for_legal_analysis": [
            {
                "id": pres["id"],
                "type": pres["prescription_type"],
                "legal_requirements": pres.get("legal_requirements", []),
                "priority": pres.get("priority", {}).get("level", 3)
            }
            for pres in working_plan_data.get("prescriptions", [])[:20]  # Limit
        ],
        "directives_for_authority_mapping": [
            {
                "id": dir["id"],
                "type": dir["directive_type"],
                "authority_level": dir.get("authority_hierarchy_level", 3)
            }
            for dir in working_plan_data.get("management_directives", [])[:10]  # Limit
        ]
    }
    
    # Prepare data for phase 6 (graph construction)
    if working_plan_data.get("graph_schema"):
        integrated_data["phase_6_input"] = {
            "nodes": working_plan_data["graph_schema"]["nodes"],
            "relationships": working_plan_data["graph_schema"]["relationships"],
            "spatial_context": working_plan_data.get("spatial_analysis", {}),
            "temporal_context": working_plan_data.get("temporal_analysis", {})
        }
    
    # Prepare RAG chunks for phase 6
    if working_plan_data.get("rag_chunks"):
        integrated_data["phase_6_rag_chunks"] = working_plan_data["rag_chunks"]
    
    return integrated_data


# ========== COMMAND LINE INTERFACE ==========

def main():
    """Enhanced command line interface for working plan parser"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Enhanced KPK Working Plan Parser')
    parser.add_argument('--input', required=True, help='Input text file or JSON')
    parser.add_argument('--output', help='Output JSON path')
    parser.add_argument('--doc-type', default='working_plan', help='Document type')
    parser.add_argument('--integrate-phase2', help='Phase 2 output JSON')
    parser.add_argument('--integrate-phase3-1', help='Phase 3.1 output JSON')
    parser.add_argument('--integrate-phase3-2', help='Phase 3.2 output JSON')
    parser.add_argument('--verbose', action='store_true', help='Verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Load input
    input_path = Path(args.input)
    if input_path.suffix == '.json':
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        text = data.get('normalized_text', '') if 'normalized_text' in data else str(data)
    else:
        with open(input_path, 'r', encoding='utf-8') as f:
            text = f.read()
    
    # Load pipeline outputs if provided
    phase2_output = None
    if args.integrate_phase2:
        with open(args.integrate_phase2, 'r', encoding='utf-8') as f:
            phase2_output = json.load(f)
    
    phase31_output = None
    if args.integrate_phase3_1:
        with open(args.integrate_phase3_1, 'r', encoding='utf-8') as f:
            phase31_output = json.load(f)
    
    phase32_output = None
    if args.integrate_phase3_2:
        with open(args.integrate_phase3_2, 'r', encoding='utf-8') as f:
            phase32_output = json.load(f)
    
    # Parse working plan
    parser = EnhancedKPKWorkingPlanParser()
    working_plan_data = parser.parse_working_plan(text, args.doc_type)
    
    # Integrate with pipeline
    integrated_result = integrate_enhanced_working_plan_with_pipeline(
        phase2_output, phase31_output, phase32_output, working_plan_data
    )
    
    # Save or output result
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(integrated_result, f, indent=2, ensure_ascii=False)
        print(f"Enhanced working plan analysis saved to {args.output}")
    else:
        print(json.dumps(integrated_result, indent=2))
    
    # Print enhanced summary
    print(f"\n{'='*60}")
    print("ENHANCED WORKING PLAN PARSING SUMMARY")
    print(f"{'='*60}")
    
    wp_data = working_plan_data
    compartments = wp_data.get("compartments", [])
    prescriptions = wp_data.get("prescriptions", [])
    
    print(f"Compartments found: {len(compartments)}")
    print(f"Prescriptions found: {len(prescriptions)}")
    print(f"Yield calculations: {len(wp_data.get('yield_calculations', []))}")
    print(f"Management directives: {len(wp_data.get('management_directives', []))}")
    
    metadata = wp_data.get("metadata", {})
    division = metadata.get("spatial_context", {}).get("division", "Unknown")
    period = f"{metadata.get('temporal_context', {}).get('plan_start', '?')}-" \
            f"{metadata.get('temporal_context', {}).get('plan_end', '?')}"
    print(f"Division: {division}, Plan Period: {period}")
    
    pipeline_state = wp_data.get("pipeline_state", {})
    print(f"Pipeline Status: {pipeline_state.get('status', 'unknown')}")
    print(f"Processing Confidence: {pipeline_state.get('confidence', 0):.2%}")
    
    plan_quality = wp_data.get("plan_quality", {})
    print(f"Plan Quality: {plan_quality.get('quality_level', 'unknown')} "
          f"({plan_quality.get('overall_quality', 0):.2%})")
    
    print(f"{'='*60}")
    
    # Show recommendations
    print("\nDOWNSTREAM RECOMMENDATIONS:")
    recs = wp_data.get("downstream_recommendations", {})
    for phase, phase_recs in recs.items():
        if phase_recs:
            print(f"\n{phase}:")
            for key, value in phase_recs.items():
                if isinstance(value, list):
                    print(f"  {key}: {', '.join(str(v) for v in value)}")
                else:
                    print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
