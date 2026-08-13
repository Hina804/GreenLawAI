"""
LLM_AMBIGUITY_RESOLVER.PY - ENHANCED
===========================================================
PHASE 5.3: CONTROLLED LLM ASSISTANCE WITH PHASE 5.1-5.2 INTEGRATION

ENHANCEMENTS:
1. ✅ Direct integration with Phase 5.1 (AuthorityHierarchyResolver)
2. ✅ Integration with Phase 5.2 (PenaltyLogicEngine) 
3. ✅ Enhanced KPK-specific ambiguity handling
4. ✅ Gazette notification (SRO) validation
5. ✅ Research-grade abstention tracking for VIVA
6. ✅ Graph output for Phase 6 integration
7. ✅ Improved multilingual ambiguity resolution

KEY PHILOSOPHY ENFORCED:
- LLM ONLY suggests, RULES ALWAYS decide
- System knows when LLM should NOT be used
- Every LLM suggestion must pass rule verification
- Abstention is better than wrong resolution
"""

import logging
import json
import re
from typing import Dict, List, Any, Optional, Tuple, Union, Set
from dataclasses import dataclass, asdict, field
from datetime import datetime, date
from pathlib import Path
import hashlib
from enum import Enum
import statistics
from decimal import Decimal

# Import from Phase 5.1 and 5.2
try:
    from preprocessing_pipeline.phase_5_authority_reasoning.authority_hierarchy import (
        AuthorityHierarchyResolver, AuthorityLevel, LegalSource, ResolutionResult, KPKJurisdictionMapper
    )
    from preprocessing_pipeline.phase_5_authority_reasoning.penalty_logic_engine import (
        PenaltyLogicEngine, ViolationType, ForestType, PenaltyCalculation
    )
    from preprocessing_pipeline.phase_0_foundation import AbstentionLogger
    from preprocessing_pipeline.common.config import KPK_FORESTRY_CONFIG
    from preprocessing_pipeline.common.llm_client import LLMClient
except (ImportError, ValueError, ModuleNotFoundError):
    # Fallback for standalone testing
    class AuthorityHierarchyResolver: pass
    class AuthorityLevel(Enum): pass
    class LegalSource: pass
    class KPKJurisdictionMapper: pass
    class LLMClient:
        def __init__(self, *args, **kwargs): pass
        def generate(self, *args, **kwargs): return ""
    class PenaltyLogicEngine: pass
    class ViolationType(Enum): pass
    class ForestType(Enum): pass
    class PenaltyCalculation: pass
    class AbstentionLogger:
        def log_abstention(self, *args, **kwargs): pass
    KPK_FORESTRY_CONFIG = {}

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AmbiguityType(Enum):
    """Enhanced ambiguity types for KPK forestry context"""
    SECTION_REFERENCE = "section_reference"
    AUTHORITY_CONFLICT = "authority_conflict"
    TEMPORAL_AMBIGUITY = "temporal_ambiguity"
    SPECIES_IDENTIFICATION = "species_identification"
    PENALTY_CALCULATION = "penalty_calculation"
    JURISDICTION_CONFLICT = "jurisdiction_conflict"
    GAZETTE_REFERENCE = "gazette_reference"
    MULTILINGUAL_TERM = "multilingual_term"
    OCR_ERROR_RESOLUTION = "ocr_error_resolution"
    CITATION_CHAIN = "citation_chain"
    AMENDMENT_APPLICABILITY = "amendment_applicability"
    OFFICER_DISCRETION = "officer_discretion"
    
    # Research-specific ambiguity types
    HAZARA_ACT_APPLICABILITY = "hazara_act_applicability"
    SRO_VALIDITY = "sro_validity"
    COMMUNITY_FOREST_RULES = "community_forest_rules"
    CLIMATE_SURCHARGE = "climate_surcharge"


class LLMProvider(Enum):
    """Supported LLM providers"""
    OLLAMA = "ollama"
    OPENAI = "openai"
    HUGGINGFACE = "huggingface"
    ANTHROPIC = "anthropic"
    LOCAL = "local"


@dataclass
class AmbiguityContext:
    """Enhanced context for ambiguity resolution"""
    ambiguity_type: AmbiguityType
    source_text: str
    candidates: List[Any]
    ambiguity_id: str = field(default_factory=lambda: f"ambig_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hashlib.md5(str(datetime.now()).encode()).hexdigest()[:6]}")
    
    # Enhanced metadata
    document_id: Optional[str] = None
    document_type: Optional[str] = None
    document_quality: float = 1.0  # From Phase 0.4
    
    # Spatial-temporal context
    location: Optional[str] = None
    jurisdiction: Optional[str] = None
    effective_date: Optional[date] = None
    processing_date: date = field(default_factory=date.today)
    
    # Phase 5.1-5.2 integration
    authority_context: Optional[Dict] = None  # From authority_hierarchy
    penalty_context: Optional[Dict] = None  # From penalty_logic_engine
    
    # Rules context (what rules already determined)
    rules_context: Dict = field(default_factory=dict)
    rule_confidence: float = 0.0
    rule_constraints: List[Dict] = field(default_factory=list)
    
    # Confidence thresholds
    min_confidence_for_llm: float = 0.7
    llm_confidence_threshold: float = 0.8
    
    # Research tracking
    requires_kpk_context: bool = False
    involves_hazara_act: bool = False
    involves_sro: bool = False
    is_climate_related: bool = False
    
    # Abstention tracking
    abstention_reason: Optional[str] = None
    previous_attempts: List[Dict] = field(default_factory=list)
    
    def __post_init__(self):
        # Auto-detect KPK context
        text_lower = self.source_text.lower()
        self.requires_kpk_context = any(
            keyword in text_lower 
            for keyword in ["kpk", "khyber pakhtunkhwa", "خیبر پختونخوا", "provincial"]
        )
        self.involves_hazara_act = "hazara" in text_lower
        self.involves_sro = any(
            keyword in text_lower 
            for keyword in ["sro", "gazette", "notification", "ایس آر او", "گزیٹ"]
        )
        self.is_climate_related = any(
            keyword in text_lower 
            for keyword in ["climate", "carbon", "موسمیاتی", "کاربن"]
        )
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        
        # Convert dates
        if self.effective_date:
            data['effective_date'] = self.effective_date.isoformat()
        data['processing_date'] = self.processing_date.isoformat()
        
        # Convert Enum to value
        data['ambiguity_type'] = self.ambiguity_type.value
        
        return data


@dataclass
class LLMSuggestion:
    """Enhanced LLM suggestion with verification tracking"""
    # LLM response (non-default)
    original_response: str
    parsed_resolution: Any
    llm_confidence: float
    llm_explanation: str
    llm_model: str
    llm_provider: str
    
    suggestion_id: str = field(default_factory=lambda: f"sugg_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hashlib.md5(str(datetime.now()).encode()).hexdigest()[:6]}")
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Verification tracking
    
    # Evidence and citations
    cited_evidence: List[str] = field(default_factory=list)
    assumptions_made: List[str] = field(default_factory=list)
    alternatives_considered: List[Any] = field(default_factory=list)
    
    # Rule verification
    passed_rule_verification: bool = False
    verification_method: str = "not_verified"
    verification_constraints: List[Dict] = field(default_factory=list)
    constraint_violations: List[str] = field(default_factory=list)
    
    # KPK-specific verification
    kpk_context_applied: bool = False
    kpk_authority_check: Optional[Dict] = None
    gazette_validation: Optional[Dict] = None
    
    # Phase 5.1-5.2 integration
    authority_verification: Optional[Dict] = None
    penalty_verification: Optional[Dict] = None
    
    # Final result
    accepted_resolution: Optional[Any] = None
    final_confidence: float = 0.0
    abstention_reason: Optional[str] = None
    requires_human_review: bool = False
    
    # Research tracking
    complexity_score: float = 0.0
    research_significance: str = "standard"
    
    # Phase 6 graph integration
    graph_node_id: Optional[str] = None
    
    def __post_init__(self):
        # Generate graph node ID
        self.graph_node_id = f"LLMSuggestion_{self.suggestion_id}"
        
        # Calculate complexity
        self.complexity_score = self._calculate_complexity()
        
        # Determine research significance
        self.research_significance = self._determine_research_significance()
    
    def _calculate_complexity(self) -> float:
        """Calculate suggestion complexity."""
        complexity = 0.0
        
        # More evidence = more complex
        complexity += min(len(self.cited_evidence) * 0.1, 0.3)
        
        # More constraints = more complex
        complexity += min(len(self.verification_constraints) * 0.1, 0.3)
        
        # KPK-specific factors add complexity
        if self.kpk_context_applied:
            complexity += 0.2
        
        if self.involves_hazara_act():
            complexity += 0.1
        
        if self.involves_sro():
            complexity += 0.1
        
        return min(complexity, 1.0)
    
    def _determine_research_significance(self) -> str:
        """Determine research significance for VIVA."""
        if self.involves_hazara_act():
            return "hazara_special"
        elif self.involves_sro():
            return "sro_based"
        elif self.kpk_context_applied:
            return "kpk_specific"
        elif "climate" in self.llm_explanation.lower():
            return "climate_related"
        
        return "standard"
    
    def involves_hazara_act(self) -> bool:
        """Check if suggestion involves Hazara Act."""
        return any(
            "hazara" in str(item).lower() 
            for item in [self.parsed_resolution, self.llm_explanation] + self.cited_evidence
        )
    
    def involves_sro(self) -> bool:
        """Check if suggestion involves SRO."""
        return any(
            keyword in str(item).lower()
            for item in [self.parsed_resolution, self.llm_explanation] + self.cited_evidence
            for keyword in ["sro", "gazette", "notification"]
        )
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        data = asdict(self)
        
        # Convert datetime
        data['timestamp'] = self.timestamp.isoformat()
        
        return data


@dataclass
class ResolutionResult:
    """Enhanced resolution result with research metrics"""
    ambiguity_context: AmbiguityContext
    llm_suggestion: Optional[LLMSuggestion]
    final_resolution: Any
    resolution_method: str  # "llm_verified", "rules_only", "abstention"
    confidence: float
    explanation: str
    resolution_id: str = field(default_factory=lambda: f"res_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hashlib.md5(str(datetime.now()).encode()).hexdigest()[:6]}")
    
    # Verification details
    verification_steps: List[Dict] = field(default_factory=list)
    passed_verifications: List[str] = field(default_factory=list)
    failed_verifications: List[str] = field(default_factory=list)
    
    # Abstention details (if applicable)
    abstention_reason: Optional[str] = None
    abstention_category: Optional[str] = None  # "llm_low_confidence", "rule_violation", etc.
    
    # Research metrics
    processing_time_ms: int = 0
    llm_call_duration_ms: Optional[int] = None
    rule_verification_duration_ms: Optional[int] = None
    complexity_score: float = 0.0
    
    # Quality gates (Phase 7 integration)
    passed_quality_gates: List[str] = field(default_factory=list)
    failed_quality_gates: List[str] = field(default_factory=list)
    
    # Phase 6 graph integration
    graph_node_id: Optional[str] = None
    graph_relationships: List[Dict] = field(default_factory=list)
    
    def __post_init__(self):
        # Generate graph node ID
        self.graph_node_id = f"Resolution_{self.resolution_id}"
        
        # Calculate complexity
        self.complexity_score = self._calculate_complexity()
    
    def _calculate_complexity(self) -> float:
        """Calculate resolution complexity."""
        complexity = 0.0
        
        # LLM involvement adds complexity
        if self.llm_suggestion:
            complexity += 0.3
            complexity += self.llm_suggestion.complexity_score * 0.3
        
        # More verification steps = more complex
        complexity += min(len(self.verification_steps) * 0.1, 0.3)
        
        # More failed verifications = more complex
        complexity += min(len(self.failed_verifications) * 0.05, 0.2)
        
        # Abstention adds complexity (indicates difficult case)
        if self.abstention_reason:
            complexity += 0.1
        
        return min(complexity, 1.0)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        data = asdict(self)
        
        # Convert nested objects
        data['ambiguity_context'] = self.ambiguity_context.to_dict()
        if self.llm_suggestion:
            data['llm_suggestion'] = self.llm_suggestion.to_dict()
        
        return data


class LLMAmbiguityResolver:
    """
    Enhanced LLM ambiguity resolver with Phase 5.1-5.2 integration.
    Implements strict "LLM suggests, rules decide" philosophy.
    """
    def __init__(
        self,
        config: Optional[Any] = None,
        llm_client: Optional[Any] = None,
        authority_resolver: Optional[AuthorityHierarchyResolver] = None,
        penalty_engine: Optional[PenaltyLogicEngine] = None,
        abstention_logger: Optional[AbstentionLogger] = None,
        jurisdiction_mapper: Optional[KPKJurisdictionMapper] = None
    ):
        """
        Initialize enhanced ambiguity resolver.
        """
        self.config = config or self._default_config()
        self.authority_resolver = authority_resolver
        self.penalty_engine = penalty_engine
        self.abstention_logger = abstention_logger or AbstentionLogger()
        self.jurisdiction_mapper = jurisdiction_mapper
        
        # Initialize LLM client
        self.llm_client = self._initialize_llm()
        
        # Gazette registry for SRO validation
        self.gazette_registry = self._load_gazette_registry()
        
        # KPK-specific knowledge base
        self.kpk_knowledge_base = self._build_kpk_knowledge_base()
        
        # Research statistics
        self.research_stats = {
            "total_resolutions": 0,
            "llm_calls": 0,
            "llm_verified_resolutions": 0,
            "rules_only_resolutions": 0,
            "abstentions": 0,
            "hazara_act_resolutions": 0,
            "sro_resolutions": 0,
            "average_confidence": 0.0,
            "average_processing_time_ms": 0,
            "confidence_distribution": [],
        }
        
        # Resolution history
        self.resolution_history = []
        
        # LLM prompt templates (enhanced for KPK)
        self.prompt_templates = self._build_prompt_templates()
        
        logger.info("Enhanced LLM Ambiguity Resolver initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        """Default configuration with research-grade settings."""
        return {
            # LLM Settings
            "llm_provider": LLMProvider.OLLAMA.value,
            "llm_model": "llama3.2",  # or "mistral", "gemma", etc.
            "temperature": 0.1,  # Very low for deterministic legal work
            "max_tokens": 1000,
            "top_p": 0.9,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0,
            
            # Control Parameters (STRICT)
            "llm_usage_conditions": {
                "min_rule_confidence": 0.7,  # Use LLM only when rules uncertain
                "multiple_viable_candidates": True,
                "conflicting_rule_outputs": True,
                "requires_context_understanding": True,
                "requires_kpk_domain_knowledge": True,
                "temporal_complexity": True,
                "multilingual_ambiguity": True,
            },
            
            # Verification Parameters
            "min_llm_confidence": 0.8,
            "require_citation": True,
            "require_kpk_context_awareness": True,
            "validate_with_authority_hierarchy": True,
            "validate_with_penalty_logic": True,
            "gazette_validation_required": True,
            
            # Abstention Parameters
            "prefer_abstention_over_wrong": True,
            "abstention_categories": {
                "llm_low_confidence": 0.7,
                "rule_constraint_violation": 1.0,  # Always abstain
                "authority_hierarchy_conflict": 1.0,
                "gazette_validation_failed": 1.0,
                "temporal_impossibility": 1.0,
            },
            "human_review_threshold": 0.6,
            
            # KPK-Specific Parameters
            "kpk_context_weight": 0.2,  # Boost for KPK-relevant resolutions
            "hazara_act_special_handling": True,
            "sro_validation_required": True,
            "community_forest_special_rules": True,
            
            # Performance Parameters
            "timeout_seconds": 30,
            "max_retries": 2,
            "cache_responses": True,
            "cache_ttl_hours": 24,
            
            # Research Parameters
            "collect_research_metrics": True,
            "log_viva_examples": True,
            "export_graph_data": True,
        }
    
    def _initialize_llm(self):
        """Initialize LLM client with enhanced error handling."""
        provider = self.config.get("llm_provider", LLMProvider.OLLAMA.value)
        
        try:
            if provider == LLMProvider.OLLAMA.value:
                # Use our common LLMClient for Ollama
                client = LLMClient(
                    model=self.config.get("llm_model", "llama3.2")
                )
                # Test connection (generate empty prompt)
                resp = client.generate("test")
                if resp:
                    logger.info(f"Ollama connected via LLMClient with model: {client.model}")
                    return client
                else:
                    logger.warning("Ollama connection test returned empty response")
                    return None
                
            elif provider == LLMProvider.OPENAI.value:
                import openai
                api_key = self.config.get("openai_api_key")
                if not api_key:
                    logger.warning("OpenAI API key not provided")
                    return None
                openai.api_key = api_key
                return openai
            
            elif provider == LLMProvider.HUGGINGFACE.value:
                from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM
                
                model_name = self.config.get("hf_model", "microsoft/phi-2")
                tokenizer = AutoTokenizer.from_pretrained(model_name)
                model = AutoModelForCausalLM.from_pretrained(model_name)
                
                return pipeline(
                    "text-generation",
                    model=model,
                    tokenizer=tokenizer,
                    device=-1  # Use CPU, change to 0 for GPU
                )
            
            elif provider == LLMProvider.ANTHROPIC.value:
                import anthropic
                api_key = self.config.get("anthropic_api_key")
                if not api_key:
                    logger.warning("Anthropic API key not provided")
                    return None
                return anthropic.Anthropic(api_key=api_key)
            
            else:
                logger.warning(f"Unknown LLM provider: {provider}")
                return None
                
        except ImportError as e:
            logger.error(f"Failed to import LLM library: {e}")
            logger.info("LLM functionality will be disabled")
            return None
        except Exception as e:
            logger.error(f"LLM initialization failed: {e}")
            return None
    
    def _load_gazette_registry(self) -> Dict:
        """Load gazette registry for SRO validation."""
        # This would typically load from a database
        # For now, return sample data
        return {
            "SRO-123/2010": {
                "date": date(2010, 3, 15),
                "subject": "Protected Species List Enhancement",
                "effective_date": date(2010, 4, 1),
                "published_in": "KPK Gazette Extraordinary",
                "validity": "current"
            },
            "SRO-456/2015": {
                "date": date(2015, 7, 1),
                "subject": "General Penalty Enhancement",
                "effective_date": date(2015, 8, 1),
                "published_in": "KPK Gazette",
                "validity": "current"
            },
            "SRO-789/2018": {
                "date": date(2018, 6, 15),
                "subject": "Biodiversity Surcharge",
                "effective_date": date(2018, 7, 1),
                "published_in": "KPK Gazette",
                "validity": "current"
            },
            "SRO-101/2020": {
                "date": date(2020, 1, 1),
                "subject": "Climate Change Surcharge",
                "effective_date": date(2020, 2, 1),
                "published_in": "KPK Gazette Extraordinary",
                "validity": "current"
            }
        }
    
    def _build_kpk_knowledge_base(self) -> Dict:
        """Build KPK-specific knowledge base for context enhancement."""
        return {
            "authority_hierarchy": [
                "Constitution of Pakistan",
                "Federal Forest Act 1927",
                "KPK Forest Ordinance 2002 (Primary)",
                "Hazara Forest Act 1936 (Special Regional)",
                "KPK Forest Rules 2004",
                "Gazette Notifications (SROs)",
                "Department Circulars",
                "Working Plans",
                "Officer Orders"
            ],
            "key_sections": {
                "Section 27": "Penalty for unauthorized felling",
                "Section 28": "Penalty for illegal transport",
                "Section 29": "Protected forests declaration",
                "Section 32": "Encroachment penalties",
                "Section 33": "Forest fire penalties"
            },
            "protected_species": [
                "Deodar (Cedrus deodara)",
                "Kail (Pinus wallichiana)",
                "Chir Pine (Pinus roxburghii)",
                "Walnut (Juglans regia)",
                "Oak (Quercus spp.)"
            ],
            "jurisdiction_special_cases": {
                "Hazara Division": "Hazara Forest Act applies",
                "Malakand Division": "Special regulations may apply",
                "Tribal Districts": "Transitional legal status"
            },
            "common_ambiguities": {
                "section_above": "Usually refers to immediately preceding section",
                "said section": "Refers to previously mentioned section",
                "relevant authority": "Context determines federal/provincial",
                "as amended": "Check latest gazette notification"
            }
        }
    
    def _build_prompt_templates(self) -> Dict[str, str]:
        """Build enhanced prompt templates for KPK forestry context."""
        return {
            AmbiguityType.SECTION_REFERENCE.value: self._section_reference_prompt(),
            AmbiguityType.AUTHORITY_CONFLICT.value: self._authority_conflict_prompt(),
            AmbiguityType.TEMPORAL_AMBIGUITY.value: self._temporal_ambiguity_prompt(),
            AmbiguityType.SPECIES_IDENTIFICATION.value: self._species_identification_prompt(),
            AmbiguityType.PENALTY_CALCULATION.value: self._penalty_calculation_prompt(),
            AmbiguityType.JURISDICTION_CONFLICT.value: self._jurisdiction_conflict_prompt(),
            AmbiguityType.GAZETTE_REFERENCE.value: self._gazette_reference_prompt(),
            AmbiguityType.MULTILINGUAL_TERM.value: self._multilingual_term_prompt(),
            AmbiguityType.OCR_ERROR_RESOLUTION.value: self._ocr_error_resolution_prompt(),
            AmbiguityType.HAZARA_ACT_APPLICABILITY.value: self._hazara_act_applicability_prompt(),
            AmbiguityType.SRO_VALIDITY.value: self._sro_validity_prompt(),
        }
    
    def resolve_ambiguity(self, 
                         ambiguity_context: Union[AmbiguityContext, Dict],
                         viva_mode: bool = False) -> ResolutionResult:
        """
        Enhanced ambiguity resolution with strict control.
        Supports both AmbiguityContext objects and legacy dictionaries.
        
        Args:
            ambiguity_context: Complete ambiguity context or dictionary
            viva_mode: Enable detailed logging for VIVA demonstration
            
        Returns:
            ResolutionResult with complete tracking
        """
        start_time = datetime.now()
        
        # Handle legacy dictionary input
        if isinstance(ambiguity_context, dict):
            try:
                # Extract fields with defaults
                text = ambiguity_context.get("text") or ambiguity_context.get("source_text", "")
                candidates = ambiguity_context.get("candidates", [])
                
                # Parse ambiguity type
                type_str = ambiguity_context.get("type") or ambiguity_context.get("ambiguity_type", "section_reference")
                try:
                    amb_type = AmbiguityType(type_str)
                except ValueError:
                    # Try to map common legacy types
                    if "section" in type_str:
                        amb_type = AmbiguityType.SECTION_REFERENCE
                    elif "authority" in type_str:
                        amb_type = AmbiguityType.AUTHORITY_CONFLICT
                    else:
                        amb_type = AmbiguityType.SECTION_REFERENCE
                
                # Create proper context object
                ambiguity_context = AmbiguityContext(
                    ambiguity_type=amb_type,
                    source_text=text,
                    candidates=candidates,
                    document_id=ambiguity_context.get("document_id"),
                    location=ambiguity_context.get("location"),
                    jurisdiction=ambiguity_context.get("jurisdiction")
                )
            except Exception as e:
                logger.error(f"Failed to convert legacy dict to AmbiguityContext: {e}")
                # return a safe failure result if needed, or let it crash to be caught
                pass
        
        logger.info(f"Resolving ambiguity: {ambiguity_context.ambiguity_type.value}")
        
        # Step 1: Check if LLM should be used (STRICT conditions)
        should_use_llm = self._should_use_llm(ambiguity_context)
        
        if not should_use_llm:
            # Use rules-only resolution
            result = self._rules_only_resolution(ambiguity_context, start_time)
            self._update_research_stats(result, start_time)
            
            if viva_mode:
                self._log_viva_example(result, "rules_only")
            
            return result
        
        # Step 2: Prepare enhanced LLM prompt
        prompt = self._prepare_enhanced_prompt(ambiguity_context)
        
        # Step 3: Call LLM with controlled parameters
        llm_response = self._call_llm_with_control(prompt, ambiguity_context)
        self.research_stats["llm_calls"] += 1
        
        # Step 4: Parse and validate LLM response
        llm_suggestion = self._parse_llm_response(llm_response, ambiguity_context)
        
        # Step 5: Apply strict rule verification
        verification_result = self._verify_with_rules(llm_suggestion, ambiguity_context)
        
        # Step 6: Apply Phase 5.1-5.2 verification if available
        if verification_result.get("passed_basic_verification", False):
            verification_result = self._apply_phase_integration(
                verification_result, llm_suggestion, ambiguity_context
            )
        
        # Step 7: Make final decision
        final_result = self._make_final_decision(
            verification_result, llm_suggestion, ambiguity_context, start_time
        )
        
        # Step 8: Update research statistics
        self._update_research_stats(final_result, start_time)
        
        # Step 9: VIVA logging if enabled
        if viva_mode:
            self._log_viva_example(final_result, "llm_assisted")
        
        return final_result
    
    def _should_use_llm(self, context: AmbiguityContext) -> bool:
        """
        STRICT conditions for LLM usage.
        LLM should ONLY be used when rules cannot decide.
        """
        conditions = self.config.get("llm_usage_conditions", {})
        
        # Condition 1: Rules have low confidence
        if context.rule_confidence < conditions.get("min_rule_confidence", 0.7):
            logger.debug(f"Using LLM: Rule confidence ({context.rule_confidence:.2f}) below threshold")
            return True
        
        # Condition 2: Multiple viable candidates
        if (conditions.get("multiple_viable_candidates", True) and 
            len(context.candidates) > 1 and 
            self._has_multiple_viable_candidates(context)):
            logger.debug(f"Using LLM: Multiple viable candidates")
            return True
        
        # Condition 3: Conflicting rule outputs
        if (conditions.get("conflicting_rule_outputs", True) and 
            context.rules_context.get("conflicting_outputs", False)):
            logger.debug(f"Using LLM: Conflicting rule outputs")
            return True
        
        # Condition 4: Requires contextual understanding
        if (conditions.get("requires_context_understanding", True) and 
            self._requires_context_understanding(context)):
            logger.debug(f"Using LLM: Requires contextual understanding")
            return True
        
        # Condition 5: Requires KPK domain knowledge
        if (conditions.get("requires_kpk_domain_knowledge", True) and 
            context.requires_kpk_context):
            logger.debug(f"Using LLM: Requires KPK domain knowledge")
            return True
        
        # Condition 6: Temporal complexity
        if (conditions.get("temporal_complexity", True) and 
            context.ambiguity_type == AmbiguityType.TEMPORAL_AMBIGUITY):
            logger.debug(f"Using LLM: Temporal complexity requires analysis")
            return True
        
        # Condition 7: Multilingual ambiguity
        if (conditions.get("multilingual_ambiguity", True) and 
            context.ambiguity_type == AmbiguityType.MULTILINGUAL_TERM):
            logger.debug(f"Using LLM: Multilingual ambiguity")
            return True
        
        # Special case: Hazara Act applicability
        if context.ambiguity_type == AmbiguityType.HAZARA_ACT_APPLICABILITY:
            logger.debug(f"Using LLM: Hazara Act special case")
            return True
        
        # Special case: SRO validity
        if context.ambiguity_type == AmbiguityType.SRO_VALIDITY:
            logger.debug(f"Using LLM: SRO validation requires analysis")
            return True
        
        return False
    
    def _has_multiple_viable_candidates(self, context: AmbiguityContext) -> bool:
        """Check if multiple candidates are viable."""
        if len(context.candidates) <= 1:
            return False
        
        # Check if candidates have similar rule confidence
        if "candidate_confidences" in context.rules_context:
            confidences = context.rules_context["candidate_confidences"]
            if len(confidences) > 1:
                # Check if top candidates are close
                sorted_conf = sorted(confidences, reverse=True)
                if len(sorted_conf) >= 2 and (sorted_conf[0] - sorted_conf[1]) < 0.2:
                    return True
        
        return False
    
    def _requires_context_understanding(self, context: AmbiguityContext) -> bool:
        """Check if ambiguity requires deep contextual understanding."""
        text = context.source_text.lower()
        
        # Contextual phrases that require understanding
        contextual_phrases = [
            "as per the context",
            "in light of the circumstances",
            "considering the situation",
            "depending on the context",
            "given that",
            "whereas",
            "hereinafter referred to as",
        ]
        
        return any(phrase in text for phrase in contextual_phrases)
    
    def _prepare_enhanced_prompt(self, context: AmbiguityContext) -> str:
        """Prepare enhanced prompt with KPK-specific context."""
        template = self.prompt_templates.get(
            context.ambiguity_type.value,
            self._generic_ambiguity_prompt()
        )
        
        # Format base prompt
        base_prompt = template.format(
            source_text=context.source_text,
            candidates=json.dumps(context.candidates, indent=2, default=str),
            ambiguity_type=context.ambiguity_type.value,
            location=context.location or "Not specified",
            effective_date=context.effective_date or "Not specified",
        )
        
        # Add KPK context if required
        if context.requires_kpk_context:
            kpk_context = self._enhance_kpk_context(context)
            base_prompt += f"\n\nKPK-SPECIFIC CONTEXT:\n{kpk_context}"
        
        # Add rules context if available
        if context.rules_context:
            rules_summary = self._summarize_rules_context(context.rules_context)
            base_prompt += f"\n\nRULE-BASED ANALYSIS:\n{rules_summary}"
        
        # Add constraints if available
        if context.rule_constraints:
            constraints = json.dumps(context.rule_constraints, indent=2)
            base_prompt += f"\n\nRULE CONSTRAINTS:\n{constraints}"
        
        # Add strict response format instructions
        base_prompt += "\n\nSTRICT RESPONSE FORMAT (JSON):\n" + self._strict_response_format()
        
        # Add verification requirements
        base_prompt += "\n\nVERIFICATION REQUIREMENTS:\n" + self._verification_requirements()
        
        return base_prompt
    
    def _enhance_kpk_context(self, context: AmbiguityContext) -> str:
        """Enhance prompt with KPK-specific knowledge."""
        enhancements = []
        
        # Add authority hierarchy
        enhancements.append("KPK AUTHORITY HIERARCHY:")
        for i, authority in enumerate(self.kpk_knowledge_base["authority_hierarchy"], 1):
            enhancements.append(f"{i}. {authority}")
        
        # Add jurisdiction info if location specified
        if context.location and self.jurisdiction_mapper:
            try:
                jurisdiction_info = self.jurisdiction_mapper.map_location(context.location)
                enhancements.append(f"\nJURISDICTION ANALYSIS for {context.location}:")
                enhancements.append(f"- Division: {jurisdiction_info.get('division', 'Unknown')}")
                enhancements.append(f"- District: {jurisdiction_info.get('district', 'Unknown')}")
                enhancements.append(f"- Special Region: {jurisdiction_info.get('special_region', 'None')}")
            except Exception as e:
                logger.warning(f"Jurisdiction mapping failed: {e}")
        
        # Add relevant sections
        if context.ambiguity_type == AmbiguityType.SECTION_REFERENCE:
            enhancements.append("\nKEY FORESTRY SECTIONS:")
            for section, description in self.kpk_knowledge_base["key_sections"].items():
                enhancements.append(f"- {section}: {description}")
        
        # Add species info if relevant
        if context.ambiguity_type == AmbiguityType.SPECIES_IDENTIFICATION:
            enhancements.append("\nPROTECTED SPECIES IN KPK:")
            for species in self.kpk_knowledge_base["protected_species"]:
                enhancements.append(f"- {species}")
        
        return "\n".join(enhancements)
    
    def _summarize_rules_context(self, rules_context: Dict) -> str:
        """Summarize rule-based analysis for prompt."""
        summary = []
        
        if "extracted_entities" in rules_context:
            entities = rules_context["extracted_entities"]
            summary.append(f"Extracted Entities: {len(entities)}")
            for entity_type, entity_list in entities.items():
                summary.append(f"- {entity_type}: {len(entity_list)} items")
        
        if "confidence" in rules_context:
            summary.append(f"Rule Confidence: {rules_context['confidence']:.2f}")
        
        if "candidate_ranking" in rules_context:
            ranking = rules_context["candidate_ranking"]
            summary.append("Candidate Ranking by Rules:")
            for i, (candidate, score) in enumerate(ranking[:3], 1):  # Top 3 only
                summary.append(f"{i}. {candidate}: {score:.2f}")
        
        return "\n".join(summary)
    
    def _strict_response_format(self) -> str:
        """Strict response format instructions."""
        return """{
    "resolution": "The chosen resolution MUST BE ONE OF THE PROVIDED CANDIDATES, or 'ABSTAIN'",
    "confidence": 0.0-1.0,
    "explanation": "Detailed, evidence-based explanation",
    "cited_evidence": ["List SPECIFIC evidence from context"],
    "assumptions_made": ["List any assumptions"],
    "kpk_context_applied": true/false,
    "requires_human_review": true/false,
    "alternatives_considered": ["Other candidates considered"],
    "reasoning_chain": ["Step-by-step reasoning"]
}"""
    
    def _verification_requirements(self) -> str:
        """Verification requirements for LLM response."""
        return """VERIFICATION WILL CHECK:
1. Resolution must be in candidates list
2. Confidence must be justified by evidence
3. Must consider KPK legal hierarchy if applicable
4. Must consider temporal validity if dates involved
5. Must cite specific evidence from context
6. Must flag if human review is needed

FAILURE TO MEET THESE REQUIREMENTS WILL RESULT IN ABSTENTION."""
    
    def _call_llm_with_control(self, prompt: str, context: AmbiguityContext) -> str:
        """Call LLM with strict control parameters."""
        if not self.llm_client:
            logger.warning("LLM client not available, returning abstention")
            return self._default_abstention_response(context)
        
        provider = self.config.get("llm_provider", LLMProvider.OLLAMA.value)
        
        try:
            if provider == LLMProvider.OLLAMA.value:
                response = self.llm_client.generate(
                    model=self.config.get("llm_model", "llama3.2"),
                    prompt=prompt,
                    options={
                        "temperature": self.config.get("temperature", 0.1),
                        "num_predict": self.config.get("max_tokens", 1000),
                        "top_p": self.config.get("top_p", 0.9),
                    }
                )
                return response

            
            elif provider == LLMProvider.OPENAI.value:
                response = self.llm_client.ChatCompletion.create(
                    model=self.config.get("llm_model", "gpt-3.5-turbo"),
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self.config.get("temperature", 0.1),
                    max_tokens=self.config.get("max_tokens", 1000),
                    top_p=self.config.get("top_p", 0.9),
                )
                return response.choices[0].message.content
            
            elif provider == LLMProvider.HUGGINGFACE.value:
                response = self.llm_client(
                    prompt,
                    max_length=self.config.get("max_tokens", 1000),
                    temperature=self.config.get("temperature", 0.1),
                    top_p=self.config.get("top_p", 0.9),
                    do_sample=True,
                    num_return_sequences=1,
                )
                return response[0]["generated_text"]
            
            elif provider == LLMProvider.ANTHROPIC.value:
                response = self.llm_client.messages.create(
                    model=self.config.get("llm_model", "claude-3-haiku"),
                    max_tokens=self.config.get("max_tokens", 1000),
                    temperature=self.config.get("temperature", 0.1),
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.content[0].text
            
            else:
                return self._default_abstention_response(context)
                
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return self._default_abstention_response(context)
    
    def _default_abstention_response(self, context: AmbiguityContext) -> str:
        """Default response when LLM fails."""
        return json.dumps({
            "resolution": "ABSTAIN",
            "confidence": 0.0,
            "explanation": f"LLM service unavailable for {context.ambiguity_type.value}",
            "cited_evidence": [],
            "assumptions_made": ["LLM service failure"],
            "kpk_context_applied": False,
            "requires_human_review": True,
            "alternatives_considered": context.candidates,
            "reasoning_chain": ["LLM service unavailable, defaulting to abstention"]
        })
    
    def _parse_llm_response(self, response: str, context: AmbiguityContext) -> LLMSuggestion:
        """Parse and validate LLM response with enhanced checks."""
        try:
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if not json_match:
                return self._parse_text_response(response, context)
            
            parsed = json.loads(json_match.group())
            
            # Validate required fields
            parsed = self._validate_llm_response(parsed, context)
            
            # Create LLM suggestion object
            suggestion = LLMSuggestion(
                original_response=response,
                parsed_resolution=parsed.get("resolution"),
                llm_confidence=float(parsed.get("confidence", 0.0)),
                llm_explanation=parsed.get("explanation", ""),
                llm_model=self.config.get("llm_model", "unknown"),
                llm_provider=self.config.get("llm_provider", "unknown"),
                cited_evidence=parsed.get("cited_evidence", []),
                assumptions_made=parsed.get("assumptions_made", []),
                alternatives_considered=parsed.get("alternatives_considered", []),
                kpk_context_applied=parsed.get("kpk_context_applied", False),
                requires_human_review=parsed.get("requires_human_review", False),
            )
            
            return suggestion
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")
            return self._parse_text_response(response, context)
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            return self._create_error_suggestion(response, context, str(e))
    
    def _validate_llm_response(self, parsed: Dict, context: AmbiguityContext) -> Dict:
        """Validate LLM response against strict criteria."""
        # Ensure resolution is in candidates or is "ABSTAIN"
        resolution = parsed.get("resolution", "")
        if resolution != "ABSTAIN" and resolution not in context.candidates:
            # Try fuzzy matching
            fuzzy_match = self._fuzzy_match_resolution(resolution, context.candidates)
            if fuzzy_match:
                parsed["resolution"] = fuzzy_match
                parsed["fuzzy_matched"] = True
            else:
                parsed["resolution"] = "ABSTAIN"
                parsed["abstention_reason"] = f"Resolution '{resolution}' not in candidates"
        
        # Validate confidence
        confidence = float(parsed.get("confidence", 0.0))
        confidence = max(0.0, min(1.0, confidence))
        parsed["confidence"] = confidence
        
        # Validate required fields
        if "explanation" not in parsed:
            parsed["explanation"] = "No explanation provided"
        
        if "cited_evidence" not in parsed:
            parsed["cited_evidence"] = []
        
        # Add KPK context flag if not present
        if "kpk_context_applied" not in parsed and context.requires_kpk_context:
            # Check if explanation mentions KPK keywords
            explanation_lower = parsed["explanation"].lower()
            kpk_keywords = ["kpk", "khyber pakhtunkhwa", "provincial", "ordinance", "hazara"]
            parsed["kpk_context_applied"] = any(
                keyword in explanation_lower for keyword in kpk_keywords
            )
        
        return parsed
    
    def _fuzzy_match_resolution(self, suggestion: str, candidates: List[str]) -> Optional[str]:
        """Fuzzy match LLM suggestion to candidate list."""
        suggestion_lower = suggestion.lower()
        
        # Try exact match first
        for candidate in candidates:
            if candidate.lower() == suggestion_lower:
                return candidate
        
        # Try contains match
        for candidate in candidates:
            candidate_lower = candidate.lower()
            if candidate_lower in suggestion_lower or suggestion_lower in candidate_lower:
                return candidate
        
        # Try word overlap
        for candidate in candidates:
            candidate_lower = candidate.lower()
            suggestion_words = set(suggestion_lower.split())
            candidate_words = set(candidate_lower.split())
            
            overlap = suggestion_words & candidate_words
            if overlap:
                jaccard = len(overlap) / len(suggestion_words | candidate_words)
                if jaccard > 0.3:  # Lower threshold for legal text
                    return candidate
        
        # Try numeric matching for sections
        section_match = re.search(r'section\s*(\d+[a-z]?)', suggestion_lower, re.IGNORECASE)
        if section_match:
            section_num = section_match.group(1)
            for candidate in candidates:
                if section_num in candidate.lower():
                    return candidate
        
        return None
    
    def _parse_text_response(self, response: str, context: AmbiguityContext) -> LLMSuggestion:
        """Parse text-only LLM response."""
        # Extract resolution
        resolution = "ABSTAIN"
        for candidate in context.candidates:
            if candidate.lower() in response.lower():
                resolution = candidate
                break
        
        # Extract confidence
        confidence = 0.5
        confidence_patterns = [
            r'confidence["\']?\s*[:=]\s*(\d+(?:\.\d+)?)',
            r'(\d+(?:\.\d+)?)\s*% confidence',
            r'confidence level.*?(\d+(?:\.\d+)?)',
        ]
        
        for pattern in confidence_patterns:
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                try:
                    conf_value = float(match.group(1))
                    confidence = conf_value / 100 if conf_value > 1 else conf_value
                    break
                except ValueError:
                    pass
        
        # Check for KPK context
        kpk_context = any(
            keyword in response.lower()
            for keyword in ["kpk", "khyber pakhtunkhwa", "provincial", "ordinance"]
        )
        
        return LLMSuggestion(
            original_response=response[:1000],  # Store first 1000 chars
            parsed_resolution=resolution,
            llm_confidence=confidence,
            llm_explanation=response[:500],  # First 500 chars as explanation
            llm_model=self.config.get("llm_model", "unknown"),
            llm_provider=self.config.get("llm_provider", "unknown"),
            kpk_context_applied=kpk_context,
            requires_human_review=confidence < 0.7,
        )
    
    def _create_error_suggestion(self, response: str, context: AmbiguityContext, error: str) -> LLMSuggestion:
        """Create error suggestion when parsing fails."""
        return LLMSuggestion(
            original_response=response[:500],
            parsed_resolution="ABSTAIN",
            llm_confidence=0.0,
            llm_explanation=f"Error parsing LLM response: {error}",
            llm_model=self.config.get("llm_model", "unknown"),
            llm_provider=self.config.get("llm_provider", "unknown"),
            requires_human_review=True,
        )
    
    def _verify_with_rules(self, suggestion: LLMSuggestion, context: AmbiguityContext) -> Dict:
        """
        STRICT rule verification.
        LLM suggestions must pass ALL applicable rule checks.
        """
        verification_steps = []
        passed_verifications = []
        failed_verifications = []
        constraint_violations = []
        
        # Step 1: Basic candidate check
        if suggestion.parsed_resolution == "ABSTAIN":
            verification_steps.append({
                "step": "llm_abstention",
                "passed": True,
                "details": "LLM abstained from making suggestion"
            })
            passed_verifications.append("llm_abstention")
            
            return {
                "passed_basic_verification": False,
                "abstention_reason": "LLM abstained",
                "verification_steps": verification_steps,
                "passed_verifications": passed_verifications,
                "failed_verifications": failed_verifications,
                "constraint_violations": constraint_violations,
            }
        
        # Step 2: Candidate validity
        if suggestion.parsed_resolution not in context.candidates:
            verification_steps.append({
                "step": "candidate_validity",
                "passed": False,
                "details": f"LLM suggestion '{suggestion.parsed_resolution}' not in candidates"
            })
            failed_verifications.append("candidate_validity")
            constraint_violations.append("candidate_validity")
            
            return {
                "passed_basic_verification": False,
                "abstention_reason": "LLM suggestion not in candidates",
                "verification_steps": verification_steps,
                "passed_verifications": passed_verifications,
                "failed_verifications": failed_verifications,
                "constraint_violations": constraint_violations,
            }
        else:
            verification_steps.append({
                "step": "candidate_validity",
                "passed": True,
                "details": "LLM suggestion is in candidate list"
            })
            passed_verifications.append("candidate_validity")
        
        # Step 3: Confidence threshold
        min_confidence = context.llm_confidence_threshold
        if suggestion.llm_confidence < min_confidence:
            verification_steps.append({
                "step": "confidence_threshold",
                "passed": False,
                "details": f"LLM confidence {suggestion.llm_confidence:.2f} below threshold {min_confidence}"
            })
            failed_verifications.append("confidence_threshold")
            constraint_violations.append("confidence_threshold")
        else:
            verification_steps.append({
                "step": "confidence_threshold",
                "passed": True,
                "details": f"LLM confidence {suggestion.llm_confidence:.2f} meets threshold"
            })
            passed_verifications.append("confidence_threshold")
        
        # Step 4: Evidence requirement
        if self.config.get("require_citation", True) and not suggestion.cited_evidence:
            verification_steps.append({
                "step": "evidence_requirement",
                "passed": False,
                "details": "LLM did not cite specific evidence"
            })
            failed_verifications.append("evidence_requirement")
            constraint_violations.append("evidence_requirement")
        else:
            verification_steps.append({
                "step": "evidence_requirement",
                "passed": True,
                "details": f"LLM cited {len(suggestion.cited_evidence)} pieces of evidence"
            })
            passed_verifications.append("evidence_requirement")
        
        # Step 5: KPK context awareness (if required)
        if (context.requires_kpk_context and 
            self.config.get("require_kpk_context_awareness", True) and 
            not suggestion.kpk_context_applied):
            
            verification_steps.append({
                "step": "kpk_context_awareness",
                "passed": False,
                "details": "LLM did not demonstrate KPK context awareness"
            })
            failed_verifications.append("kpk_context_awareness")
            constraint_violations.append("kpk_context_awareness")
        elif context.requires_kpk_context:
            verification_steps.append({
                "step": "kpk_context_awareness",
                "passed": True,
                "details": "LLM demonstrated KPK context awareness"
            })
            passed_verifications.append("kpk_context_awareness")
        
        # Step 6: Check rule constraints
        for constraint in context.rule_constraints:
            constraint_check = self._check_constraint(
                suggestion.parsed_resolution, constraint, context
            )
            verification_steps.append(constraint_check)
            
            if constraint_check["passed"]:
                passed_verifications.append(f"constraint_{constraint.get('type', 'unknown')}")
            else:
                failed_verifications.append(f"constraint_{constraint.get('type', 'unknown')}")
                constraint_violations.append(constraint_check["details"])
        
        # Determine if passed basic verification
        passed_basic = (
            len(failed_verifications) == 0 or  # No failures
            (len(failed_verifications) == 1 and "confidence_threshold" in failed_verifications)
        )  # Allow confidence failure if everything else passes
        
        return {
            "passed_basic_verification": passed_basic,
            "verification_steps": verification_steps,
            "passed_verifications": passed_verifications,
            "failed_verifications": failed_verifications,
            "constraint_violations": constraint_violations,
            "suggestion": suggestion,
        }
    
    def _check_constraint(self, resolution: str, constraint: Dict, context: AmbiguityContext) -> Dict:
        """Check a specific rule constraint."""
        constraint_type = constraint.get("type", "unknown")
        
        try:
            if constraint_type == "temporal":
                return self._check_temporal_constraint(resolution, constraint, context)
            elif constraint_type == "authority":
                return self._check_authority_constraint(resolution, constraint, context)
            elif constraint_type == "jurisdiction":
                return self._check_jurisdiction_constraint(resolution, constraint, context)
            elif constraint_type == "gazette":
                return self._check_gazette_constraint(resolution, constraint, context)
            elif constraint_type == "species":
                return self._check_species_constraint(resolution, constraint, context)
            else:
                return {
                    "step": f"constraint_{constraint_type}",
                    "passed": True,
                    "details": f"Unknown constraint type '{constraint_type}', assuming passed"
                }
        except Exception as e:
            return {
                "step": f"constraint_{constraint_type}",
                "passed": False,
                "details": f"Error checking constraint: {str(e)}"
            }
    
    def _check_temporal_constraint(self, resolution: str, constraint: Dict, context: AmbiguityContext) -> Dict:
        """Check temporal constraint."""
        # Extract year from resolution
        year_match = re.search(r'\b(19\d{2}|20\d{2})\b', resolution)
        if not year_match:
            return {
                "step": "temporal_constraint",
                "passed": True,
                "details": "No year found in resolution, constraint not applicable"
            }
        
        year = int(year_match.group())
        
        # Check constraints
        if "valid_after" in constraint and year < constraint["valid_after"]:
            return {
                "step": "temporal_constraint",
                "passed": False,
                "details": f"Resolution year {year} before valid_after {constraint['valid_after']}"
            }
        
        if "valid_before" in constraint and year > constraint["valid_before"]:
            return {
                "step": "temporal_constraint",
                "passed": False,
                "details": f"Resolution year {year} after valid_before {constraint['valid_before']}"
            }
        
        return {
            "step": "temporal_constraint",
            "passed": True,
            "details": f"Resolution year {year} satisfies temporal constraints"
        }
    
    def _check_authority_constraint(self, resolution: str, constraint: Dict, context: AmbiguityContext) -> Dict:
        """Check authority hierarchy constraint."""
        resolution_lower = resolution.lower()
        
        # Check Hazara Act special case
        if constraint.get("hazara_override", False) and "hazara" in context.location.lower():
            if "hazara act" in resolution_lower and "kpk ordinance" in constraint.get("conflicting_with", ""):
                return {
                    "step": "authority_constraint",
                    "passed": True,
                    "details": "Hazara Act correctly overrides KPK Ordinance in Hazara region"
                }
        
        # Check federal vs provincial
        if constraint.get("federal_overrides_provincial", False):
            if "federal" in resolution_lower and "provincial" in constraint.get("current_context", "").lower():
                return {
                    "step": "authority_constraint",
                    "passed": True,
                    "details": "Federal law correctly overrides provincial law"
                }
        
        return {
            "step": "authority_constraint",
            "passed": True,
            "details": "Authority constraints satisfied"
        }
    
    def _check_jurisdiction_constraint(self, resolution: str, constraint: Dict, context: AmbiguityContext) -> Dict:
        """Check jurisdiction constraint."""
        if not context.location:
            return {
                "step": "jurisdiction_constraint",
                "passed": True,
                "details": "No location specified, constraint not applicable"
            }
        
        # Check if resolution mentions location
        resolution_lower = resolution.lower()
        location_lower = context.location.lower()
        
        # For location-specific resolutions
        if constraint.get("must_mention_location", False) and location_lower not in resolution_lower:
            return {
                "step": "jurisdiction_constraint",
                "passed": False,
                "details": f"Resolution does not mention location '{context.location}'"
            }
        
        return {
            "step": "jurisdiction_constraint",
            "passed": True,
            "details": "Jurisdiction constraints satisfied"
        }
    
    def _check_gazette_constraint(self, resolution: str, constraint: Dict, context: AmbiguityContext) -> Dict:
        """Check gazette notification constraint."""
        # Extract SRO reference
        sro_match = re.search(r'SRO[-\s]*(\d+/\d+)', resolution, re.IGNORECASE)
        if not sro_match:
            return {
                "step": "gazette_constraint",
                "passed": True,
                "details": "No SRO reference found, constraint not applicable"
            }
        
        sro_ref = sro_match.group(1)
        
        # Check if SRO exists in registry
        if sro_ref not in self.gazette_registry:
            return {
                "step": "gazette_constraint",
                "passed": False,
                "details": f"SRO {sro_ref} not found in gazette registry"
            }
        
        # Check temporal validity if date specified
        if context.effective_date:
            sro_info = self.gazette_registry[sro_ref]
            if context.effective_date < sro_info.get("effective_date", date(1900, 1, 1)):
                return {
                    "step": "gazette_constraint",
                    "passed": False,
                    "details": f"SRO {sro_ref} not yet effective on {context.effective_date}"
                }
        
        return {
            "step": "gazette_constraint",
            "passed": True,
            "details": f"SRO {sro_ref} validated against gazette registry"
        }
    
    def _check_species_constraint(self, resolution: str, constraint: Dict, context: AmbiguityContext) -> Dict:
        """Check species-related constraint."""
        resolution_lower = resolution.lower()
        
        # Check protected species
        if constraint.get("protected_species_only", False):
            protected_species = self.kpk_knowledge_base["protected_species"]
            if not any(species.lower() in resolution_lower for species in protected_species):
                return {
                    "step": "species_constraint",
                    "passed": False,
                    "details": "Resolution does not mention protected species as required"
                }
        
        return {
            "step": "species_constraint",
            "passed": True,
            "details": "Species constraints satisfied"
        }
    
    def _apply_phase_integration(self, verification_result: Dict, 
                                suggestion: LLMSuggestion,
                                context: AmbiguityContext) -> Dict:
        """
        Apply Phase 5.1-5.2 integration for enhanced verification.
        """
        enhanced_verification = verification_result.copy()
        
        # Phase 5.1: Authority hierarchy verification
        if (self.config.get("validate_with_authority_hierarchy", True) and 
            self.authority_resolver and
            context.ambiguity_type in [
                AmbiguityType.AUTHORITY_CONFLICT,
                AmbiguityType.SECTION_REFERENCE,
                AmbiguityType.HAZARA_ACT_APPLICABILITY
            ]):
            
            authority_check = self._verify_with_authority_hierarchy(suggestion, context)
            enhanced_verification["authority_verification"] = authority_check
            
            if not authority_check.get("passed", True):
                enhanced_verification["failed_verifications"].append("authority_hierarchy")
                enhanced_verification["constraint_violations"].append(
                    authority_check.get("reason", "Authority hierarchy violation")
                )
        
        # Phase 5.2: Penalty logic verification
        if (self.config.get("validate_with_penalty_logic", True) and 
            self.penalty_engine and
            context.ambiguity_type == AmbiguityType.PENALTY_CALCULATION):
            
            penalty_check = self._verify_with_penalty_logic(suggestion, context)
            enhanced_verification["penalty_verification"] = penalty_check
            
            if not penalty_check.get("valid", True):
                enhanced_verification["failed_verifications"].append("penalty_logic")
                enhanced_verification["constraint_violations"].append(
                    penalty_check.get("error", "Penalty logic violation")
                )
        
        # Gazette validation
        if (self.config.get("gazette_validation_required", True) and 
            context.involves_sro):
            
            gazette_check = self._validate_gazette_reference(suggestion, context)
            enhanced_verification["gazette_validation"] = gazette_check
            
            if not gazette_check.get("valid", True):
                enhanced_verification["failed_verifications"].append("gazette_validation")
                enhanced_verification["constraint_violations"].append(
                    gazette_check.get("error", "Gazette validation failed")
                )
        
        return enhanced_verification
    
    def _verify_with_authority_hierarchy(self, suggestion: LLMSuggestion, 
                                        context: AmbiguityContext) -> Dict:
        """Verify suggestion with authority hierarchy (Phase 5.1)."""
        try:
            # Build conflicting sources from suggestion
            conflicting_sources = []
            if suggestion.parsed_resolution and suggestion.parsed_resolution != "ABSTAIN":
                # Create a mock legal source from suggestion
                source_dict = {
                    "title": f"LLM Suggestion: {suggestion.parsed_resolution}",
                    "authority": self._infer_authority_level(suggestion.parsed_resolution),
                    "jurisdiction": context.jurisdiction or "unknown",
                    "confidence": suggestion.llm_confidence
                }
                conflicting_sources.append(source_dict)
            
            # Add context sources
            if context.authority_context and "conflicting_sources" in context.authority_context:
                conflicting_sources.extend(context.authority_context["conflicting_sources"])
            
            if len(conflicting_sources) >= 2:
                resolution = self.authority_resolver.resolve_conflict(
                    entity=f"LLM_Suggestion_{context.ambiguity_type.value}",
                    conflicting_sources=conflicting_sources,
                    location=context.location,
                    effective_date=context.effective_date,
                    context=context.authority_context
                )
                
                # Check if LLM suggestion matches authority resolver result
                if resolution and resolution.selected_source:
                    llm_title = f"LLM Suggestion: {suggestion.parsed_resolution}"
                    if llm_title in resolution.selected_source.title:
                        return {
                            "passed": True,
                            "reason": "LLM suggestion consistent with authority hierarchy",
                            "resolution": resolution.to_dict() if hasattr(resolution, 'to_dict') else str(resolution)
                        }
                    else:
                        return {
                            "passed": False,
                            "reason": f"LLM suggestion conflicts with authority hierarchy. "
                                    f"Authority resolver selected: {resolution.selected_source.title}",
                            "resolution": resolution.to_dict() if hasattr(resolution, 'to_dict') else str(resolution)
                        }
            
            return {
                "passed": True,
                "reason": "Insufficient data for authority hierarchy verification"
            }
            
        except Exception as e:
            return {
                "passed": False,
                "reason": f"Authority hierarchy verification failed: {str(e)}"
            }
    
    def _infer_authority_level(self, resolution: str) -> str:
        """Infer authority level from resolution text."""
        resolution_lower = resolution.lower()
        
        if "hazara act" in resolution_lower:
            return "hazara_act"
        elif "ordinance" in resolution_lower:
            return "kpk_ordinance"
        elif "sro" in resolution_lower or "gazette" in resolution_lower:
            return "gazette_notification"
        elif "circular" in resolution_lower:
            return "department_circular"
        elif "federal" in resolution_lower:
            return "federal_act"
        else:
            return "unknown"
    
    def _verify_with_penalty_logic(self, suggestion: LLMSuggestion, 
                                  context: AmbiguityContext) -> Dict:
        """Verify suggestion with penalty logic (Phase 5.2)."""
        try:
            if not context.penalty_context:
                return {
                    "valid": True,
                    "reason": "No penalty context provided"
                }
            
            # Extract penalty calculation from suggestion
            # This would need more sophisticated parsing in real implementation
            penalty_match = re.search(r'Rs\.?\s*([\d,]+)', suggestion.parsed_resolution or "")
            if not penalty_match:
                return {
                    "valid": False,
                    "error": "No penalty amount found in LLM suggestion"
                }
            
            penalty_amount = float(penalty_match.group(1).replace(',', ''))
            
            # Validate against penalty context
            if "expected_range" in context.penalty_context:
                min_val = context.penalty_context["expected_range"]["min"]
                max_val = context.penalty_context["expected_range"]["max"]
                
                if min_val <= penalty_amount <= max_val:
                    return {
                        "valid": True,
                        "reason": f"Penalty amount {penalty_amount} within expected range [{min_val}, {max_val}]"
                    }
                else:
                    return {
                        "valid": False,
                        "error": f"Penalty amount {penalty_amount} outside expected range [{min_val}, {max_val}]"
                    }
            
            return {
                "valid": True,
                "reason": "Penalty logic validation passed"
            }
            
        except Exception as e:
            return {
                "valid": False,
                "error": f"Penalty logic verification failed: {str(e)}"
            }
    
    def _validate_gazette_reference(self, suggestion: LLMSuggestion, 
                                   context: AmbiguityContext) -> Dict:
        """Validate gazette reference in suggestion."""
        try:
            # Extract SRO reference
            sro_match = re.search(r'SRO[-\s]*(\d+/\d+)', suggestion.parsed_resolution or "", re.IGNORECASE)
            if not sro_match:
                return {
                    "valid": True,
                    "reason": "No SRO reference found in suggestion"
                }
            
            sro_ref = sro_match.group(1)
            
            # Check registry
            if sro_ref not in self.gazette_registry:
                return {
                    "valid": False,
                    "error": f"SRO {sro_ref} not found in gazette registry"
                }
            
            sro_info = self.gazette_registry[sro_ref]
            
            # Check temporal validity
            if context.effective_date and context.effective_date < sro_info.get("effective_date", date.min):
                return {
                    "valid": False,
                    "error": f"SRO {sro_ref} not yet effective on {context.effective_date}"
                }
            
            return {
                "valid": True,
                "reason": f"SRO {sro_ref} validated: {sro_info.get('subject', 'Unknown subject')}"
            }
            
        except Exception as e:
            return {
                "valid": False,
                "error": f"Gazette validation failed: {str(e)}"
            }
    
    def _make_final_decision(self, verification_result: Dict,
                            suggestion: LLMSuggestion,
                            context: AmbiguityContext,
                            start_time: datetime) -> ResolutionResult:
        """Make final decision based on verification results."""
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        # Check if we should abstain
        should_abstain = self._should_abstain(verification_result, suggestion, context)
        
        if should_abstain:
            abstention_reason = self._determine_abstention_reason(verification_result, suggestion)
            
            # Log abstention
            if self.abstention_logger:
                self.abstention_logger.log_abstention(
                    module="llm_ambiguity_resolver",
                    entity=context.ambiguity_type.value,
                    reason=abstention_reason,
                    context={
                        "suggestion": suggestion.parsed_resolution,
                        "llm_confidence": suggestion.llm_confidence,
                        "failed_verifications": verification_result.get("failed_verifications", []),
                        "constraint_violations": verification_result.get("constraint_violations", [])
                    },
                    category="llm_verification_failed"
                )
            
            return ResolutionResult(
                ambiguity_context=context,
                llm_suggestion=suggestion,
                final_resolution="ABSTAIN",
                resolution_method="llm_abstention",
                confidence=suggestion.llm_confidence * 0.5,  # Penalize for failure
                explanation=f"Abstained: {abstention_reason}",
                verification_steps=verification_result.get("verification_steps", []),
                passed_verifications=verification_result.get("passed_verifications", []),
                failed_verifications=verification_result.get("failed_verifications", []),
                abstention_reason=abstention_reason,
                abstention_category="llm_verification_failed",
                processing_time_ms=processing_time,
                complexity_score=suggestion.complexity_score,
            )
        
        # Accept the suggestion
        final_confidence = self._calculate_final_confidence(suggestion, verification_result)
        
        # Check if human review is needed
        requires_human_review = (
            final_confidence < self.config.get("human_review_threshold", 0.6) or
            suggestion.requires_human_review or
            len(verification_result.get("constraint_violations", [])) > 0
        )
        
        # Apply KPK context boost if applicable
        if context.requires_kpk_context and suggestion.kpk_context_applied:
            final_confidence = min(1.0, final_confidence + 0.1)
        
        # Create resolution result
        result = ResolutionResult(
            ambiguity_context=context,
            llm_suggestion=suggestion,
            final_resolution=suggestion.parsed_resolution,
            resolution_method="llm_verified",
            confidence=final_confidence,
            explanation=f"LLM suggestion verified by rules: {suggestion.llm_explanation[:200]}...",
            verification_steps=verification_result.get("verification_steps", []),
            passed_verifications=verification_result.get("passed_verifications", []),
            failed_verifications=verification_result.get("failed_verifications", []),
            processing_time_ms=processing_time,
            llm_call_duration_ms=processing_time * 0.7,  # Estimate
            rule_verification_duration_ms=processing_time * 0.3,  # Estimate
            complexity_score=suggestion.complexity_score,
        )
        
        # Update suggestion with acceptance
        suggestion.accepted_resolution = suggestion.parsed_resolution
        suggestion.final_confidence = final_confidence
        suggestion.passed_rule_verification = True
        suggestion.verification_method = "rules_verified"
        
        return result
    
    def _should_abstain(self, verification_result: Dict, 
                       suggestion: LLMSuggestion,
                       context: AmbiguityContext) -> bool:
        """Determine if we should abstain based on verification results."""
        abstention_categories = self.config.get("abstention_categories", {})
        
        # Category 1: LLM abstained
        if suggestion.parsed_resolution == "ABSTAIN":
            return True
        
        # Category 2: LLM low confidence
        if (suggestion.llm_confidence < abstention_categories.get("llm_low_confidence", 0.7)):
            return True
        
        # Category 3: Rule constraint violation
        if (abstention_categories.get("rule_constraint_violation", 1.0) and 
            len(verification_result.get("constraint_violations", [])) > 0):
            return True
        
        # Category 4: Authority hierarchy conflict
        if (abstention_categories.get("authority_hierarchy_conflict", 1.0) and 
            "authority_hierarchy" in verification_result.get("failed_verifications", [])):
            return True
        
        # Category 5: Gazette validation failed
        if (abstention_categories.get("gazette_validation_failed", 1.0) and 
            "gazette_validation" in verification_result.get("failed_verifications", [])):
            return True
        
        # Category 6: Temporal impossibility
        if abstention_categories.get("temporal_impossibility", 1.0):
            # Check if suggestion violates temporal constraints
            for violation in verification_result.get("constraint_violations", []):
                if "before valid_after" in violation or "after valid_before" in violation:
                    return True
        
        # Default: Don't abstain if verification passed
        return not verification_result.get("passed_basic_verification", False)
    
    def _determine_abstention_reason(self, verification_result: Dict, 
                                    suggestion: LLMSuggestion) -> str:
        """Determine detailed abstention reason."""
        if suggestion.parsed_resolution == "ABSTAIN":
            return "LLM abstained from making a suggestion"
        
        if suggestion.llm_confidence < self.config.get("min_llm_confidence", 0.8):
            return f"LLM confidence ({suggestion.llm_confidence:.2f}) below threshold"
        
        if verification_result.get("constraint_violations"):
            return f"Rule constraints violated: {verification_result['constraint_violations'][0]}"
        
        if verification_result.get("failed_verifications"):
            return f"Verification failed: {verification_result['failed_verifications'][0]}"
        
        return "Unknown reason for abstention"
    
    def _calculate_final_confidence(self, suggestion: LLMSuggestion, 
                                   verification_result: Dict) -> float:
        """Calculate final confidence score."""
        base_confidence = suggestion.llm_confidence
        
        # Apply penalties for failed verifications
        penalty = len(verification_result.get("failed_verifications", [])) * 0.1
        final_confidence = base_confidence - penalty
        
        # Boost for passed verifications
        boost = len(verification_result.get("passed_verifications", [])) * 0.05
        final_confidence = min(1.0, final_confidence + boost)
        
        # Ensure minimum confidence
        return max(0.0, final_confidence)
    
    def _rules_only_resolution(self, context: AmbiguityContext, 
                              start_time: datetime) -> ResolutionResult:
        """Make resolution using only rules (no LLM)."""
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        if not context.candidates:
            return ResolutionResult(
                ambiguity_context=context,
                llm_suggestion=None,
                final_resolution="ABSTAIN",
                resolution_method="rules_only",
                confidence=0.0,
                explanation="No candidates available for rules-only resolution",
                processing_time_ms=processing_time,
            )
        
        # Use rule confidence to choose
        if context.rule_confidence >= 0.7 and len(context.candidates) == 1:
            return ResolutionResult(
                ambiguity_context=context,
                llm_suggestion=None,
                final_resolution=context.candidates[0],
                resolution_method="rules_only",
                confidence=context.rule_confidence,
                explanation=f"High rule confidence ({context.rule_confidence:.2f}) for single candidate",
                processing_time_ms=processing_time,
            )
        
        # Use rule context if available
        if "candidate_ranking" in context.rules_context:
            ranking = context.rules_context["candidate_ranking"]
            if ranking:
                best_candidate, best_score = ranking[0]
                return ResolutionResult(
                    ambiguity_context=context,
                    llm_suggestion=None,
                    final_resolution=best_candidate,
                    resolution_method="rules_only",
                    confidence=best_score,
                    explanation=f"Rules ranked candidate '{best_candidate}' highest with score {best_score:.2f}",
                    processing_time_ms=processing_time,
                )
        
        # Default: choose first candidate with low confidence
        return ResolutionResult(
            ambiguity_context=context,
            llm_suggestion=None,
            final_resolution=context.candidates[0],
            resolution_method="rules_only",
            confidence=0.4,
            explanation="Default choice from multiple candidates using rules only",
            processing_time_ms=processing_time,
            requires_human_review=True,
        )
    
    def _update_research_stats(self, result: ResolutionResult, start_time: datetime):
        """Update research statistics."""
        self.research_stats["total_resolutions"] += 1
        
        if result.resolution_method == "llm_verified":
            self.research_stats["llm_verified_resolutions"] += 1
        elif result.resolution_method == "rules_only":
            self.research_stats["rules_only_resolutions"] += 1
        elif result.abstention_reason:
            self.research_stats["abstentions"] += 1
        
        # Update special categories
        if result.ambiguity_context.involves_hazara_act:
            self.research_stats["hazara_act_resolutions"] += 1
        
        if result.ambiguity_context.involves_sro:
            self.research_stats["sro_resolutions"] += 1
        
        # Update confidence distribution
        self.research_stats["confidence_distribution"].append(result.confidence)
        
        # Update averages
        total_resolutions = self.research_stats["total_resolutions"]
        if total_resolutions > 0:
            self.research_stats["average_confidence"] = (
                (self.research_stats["average_confidence"] * (total_resolutions - 1) + 
                 result.confidence) / total_resolutions
            )
            
            processing_time = result.processing_time_ms or 0
            self.research_stats["average_processing_time_ms"] = (
                (self.research_stats["average_processing_time_ms"] * (total_resolutions - 1) + 
                 processing_time) / total_resolutions
            )
        
        # Add to history
        self.resolution_history.append(result)
    
    def _log_viva_example(self, result: ResolutionResult, example_type: str):
        """Log example for VIVA demonstration."""
        viva_log = {
            "timestamp": datetime.now().isoformat(),
            "example_type": example_type,
            "ambiguity_type": result.ambiguity_context.ambiguity_type.value,
            "resolution_method": result.resolution_method,
            "final_resolution": str(result.final_resolution),
            "confidence": result.confidence,
            "processing_time_ms": result.processing_time_ms,
            "complexity_score": result.complexity_score,
            "llm_used": result.llm_suggestion.llm_model if result.llm_suggestion else "none",
            "abstention_reason": result.abstention_reason,
            "requires_human_review": result.requires_human_review if hasattr(result, 'requires_human_review') else False,
        }
        
        logger.info(f"VIVA Example - {example_type}: {json.dumps(viva_log, indent=2, default=str)}")
    
    def get_research_statistics(self) -> Dict:
        """Get comprehensive research statistics."""
        stats = self.research_stats.copy()
        
        # Calculate derived statistics
        total_resolutions = stats["total_resolutions"]
        
        if total_resolutions > 0:
            stats["llm_usage_rate"] = stats["llm_calls"] / total_resolutions
            stats["llm_success_rate"] = stats["llm_verified_resolutions"] / total_resolutions
            stats["abstention_rate"] = stats["abstentions"] / total_resolutions
            stats["rules_only_rate"] = stats["rules_only_resolutions"] / total_resolutions
            
            # Confidence statistics
            if stats["confidence_distribution"]:
                stats["confidence_stats"] = {
                    "mean": statistics.mean(stats["confidence_distribution"]),
                    "median": statistics.median(stats["confidence_distribution"]),
                    "stdev": statistics.stdev(stats["confidence_distribution"]) if len(stats["confidence_distribution"]) > 1 else 0,
                    "min": min(stats["confidence_distribution"]),
                    "max": max(stats["confidence_distribution"])
                }
        
        # Add resolution history count
        stats["resolution_history_count"] = len(self.resolution_history)
        
        return stats
    
    def export_resolutions_for_graph(self) -> Dict:
        """Export resolutions for Phase 6 graph construction."""
        nodes = []
        edges = []
        
        for resolution in self.resolution_history:
            # Resolution node
            resolution_node = {
                "id": resolution.graph_node_id,
                "label": f"Resolution_{resolution.ambiguity_context.ambiguity_type.value}",
                "type": "AmbiguityResolution",
                "properties": {
                    "ambiguity_type": resolution.ambiguity_context.ambiguity_type.value,
                    "resolution_method": resolution.resolution_method,
                    "confidence": resolution.confidence,
                    "final_resolution": str(resolution.final_resolution)[:100],  # Truncate
                    "timestamp": resolution.processing_time_ms,
                }
            }
            nodes.append(resolution_node)
            
            # LLM suggestion relationship
            if resolution.llm_suggestion:
                llm_node_id = resolution.llm_suggestion.graph_node_id
                
                # LLM suggestion node
                llm_node = {
                    "id": llm_node_id,
                    "label": f"LLMSuggestion_{resolution.llm_suggestion.llm_model}",
                    "type": "LLMSuggestion",
                    "properties": {
                        "llm_model": resolution.llm_suggestion.llm_model,
                        "llm_confidence": resolution.llm_suggestion.llm_confidence,
                        "parsed_resolution": str(resolution.llm_suggestion.parsed_resolution)[:100],
                    }
                }
                nodes.append(llm_node)
                
                # Relationship
                edge = {
                    "id": f"sugg_{resolution.resolution_id}",
                    "source": resolution.graph_node_id,
                    "target": llm_node_id,
                    "type": "USES_LLM_SUGGESTION",
                    "properties": {
                        "verification_method": resolution.llm_suggestion.verification_method,
                        "passed_verification": resolution.llm_suggestion.passed_rule_verification
                    }
                }
                edges.append(edge)
        
        return {
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "total_resolutions": len(self.resolution_history),
                "generated_at": datetime.now().isoformat(),
                "graph_type": "ambiguity_resolution_network",
                "purpose": "Phase 6 graph construction"
            }
        }
    
    # ========== PROMPT TEMPLATES ==========
    
    def _section_reference_prompt(self) -> str:
        return """You are a legal document analysis assistant specializing in Khyber Pakhtunkhwa (KPK) forestry laws.

SOURCE TEXT:
{source_text}

CANDIDATE SECTION REFERENCES:
{candidates}

AMBIGUITY TYPE: {ambiguity_type}
LOCATION: {location}
EFFECTIVE DATE: {effective_date}

TASK: Determine which section is most likely being referenced.

KPK-SPECIFIC GUIDANCE:
1. KPK Forest Ordinance 2002 is the primary law (Sections 1-78)
2. Penalty sections: 27 (unauthorized felling), 28 (illegal transport), 32 (encroachment)
3. Hazara Forest Act sections apply only in Hazara Division
4. Gazette notifications (SROs) amend specific sections
5. "Section above" usually refers to immediately preceding section

REQUIREMENTS:
1. MUST choose ONE candidate or "ABSTAIN"
2. MUST cite specific evidence from source text
3. MUST consider KPK legal hierarchy
4. MUST consider temporal validity
5. MUST flag if human legal review is needed"""
    
    def _authority_conflict_prompt(self) -> str:
        return """You are resolving an authority conflict in KPK forestry jurisdiction.

SOURCE TEXT:
{source_text}

CONFLICTING AUTHORITIES:
{candidates}

LOCATION: {location}
EFFECTIVE DATE: {effective_date}

TASK: Determine which authority takes precedence.

KPK AUTHORITY HIERARCHY (Highest to Lowest):
1. Constitution of Pakistan
2. Federal Acts (Pakistan Forest Act 1927)
3. KPK Forest Ordinance 2002 (Primary provincial law)
4. Hazara Forest Act 1936 (Special regional law - Hazara Division only)
5. KPK Forest Rules 2004
6. Gazette Notifications (SROs)
7. Department Circulars
8. Working Plans
9. Officer Orders

SPECIAL RULES:
- In Hazara Division: Hazara Act may override KPK Ordinance for local matters
- Federal laws override provincial when in conflict
- Newer laws override older laws (lex posterior)
- Special laws override general laws (lex specialis)

REQUIREMENTS:
1. Apply KPK hierarchy strictly
2. Consider geographic applicability
3. Consider temporal factors
4. Cite specific legal principles used
5. Flag for human review if complex jurisdictional issue"""
    
    def _temporal_ambiguity_prompt(self) -> str:
        return """You are resolving temporal ambiguity in KPK legal documents.

SOURCE TEXT:
{source_text}

TEMPORAL CANDIDATES:
{candidates}

EFFECTIVE DATE: {effective_date}

TASK: Determine correct temporal interpretation.

KPK TEMPORAL RULES:
1. Laws become effective on gazette publication date
2. Amendments may have retrospective effect if specified
3. Working plans have 10-20 year validity periods
4. Circulars are effective from issue date
5. "As amended" refers to latest version at effective date
6. Gazette notifications often have 30-day implementation delay

COMMON PATTERNS:
- "From 2002 to 2010" = valid during that period
- "After 2015 amendment" = post-2015 versions apply
- "Under the old rules" = pre-amendment version
- "Currently" = as of document date or current date

REQUIREMENTS:
1. Identify all date references in text
2. Determine valid period for each candidate
3. Apply KPK gazette publication rules
4. Consider amendment chains
5. Flag if timeline is unclear"""
    
    def _species_identification_prompt(self) -> str:
        return """You are identifying tree species in KPK forestry documents.

SOURCE TEXT:
{source_text}

CANDIDATE SPECIES:
{candidates}

LOCATION: {location}

TASK: Identify the correct tree species.

KPK SPECIES KNOWLEDGE:
PROTECTED SPECIES (Higher penalties):
- Deodar (Cedrus deodara): دیار, highest protection
- Kail (Pinus wallichiana): کایل, blue pine
- Chir Pine (Pinus roxburghii): چیر, commercial but regulated
- Walnut (Juglans regia): اخروٹ, high economic value
- Oak (Quercus spp.): شاہ بلوط, biodiversity importance

COMMON SPECIES:
- Poplar (Populus spp.): پاپلر, fast-growing
- Eucalyptus (Eucalyptus spp.): یوکلپٹس, exotic

LOCAL NAMES (Urdu/Pashto):
- Deodar: دیار, دیودار
- Chir: چیر, چلغوزا
- Walnut: اخروٹ

REQUIREMENTS:
1. Match to KPK forestry terminology
2. Consider local names and spelling variations
3. Account for OCR errors
4. Consider context (location, usage, legal status)
5. Flag uncertain identifications"""
    
    def _penalty_calculation_prompt(self) -> str:
        return """You are resolving penalty calculation ambiguity in KPK forestry.

SOURCE TEXT:
{source_text}

CANDIDATE PENALTIES:
{candidates}

LOCATION: {location}
EFFECTIVE DATE: {effective_date}

TASK: Determine correct penalty amount.

KPK PENALTY STRUCTURE (Base amounts, pre-multipliers):
- Unauthorized felling: Rs. 50,000 per tree (Section 27)
- Illegal transport: Rs. 25,000 per vehicle (Section 28)
- Firewood collection: Rs. 5,000 + Rs. 100/kg (Rule 15)
- Grazing violation: Rs. 3,000 + Rs. 500/animal (Rule 18)

MULTIPLIERS:
- Deodar: 2.5x (Highly protected)
- Kail: 2.0x (Highly protected)
- Chir: 1.8x (Protected)
- Protected areas: 1.5-2.0x
- Repeat offenses: 1.5-3.0x

SURCHARGES (Post-2020):
- Climate change: 10%
- Biodiversity: 5% for protected species

REQUIREMENTS:
1. Identify violation type
2. Identify species if mentioned
3. Apply correct multipliers
4. Consider location-based adjustments
5. Calculate surcharges if applicable
6. Show step-by-step calculation"""
    
    def _jurisdiction_conflict_prompt(self) -> str:
        return """You are resolving jurisdiction conflict in KPK forestry.

SOURCE TEXT:
{source_text}

CANDIDATE JURISDICTIONS:
{candidates}

LOCATION: {location}

TASK: Determine applicable jurisdiction.

KPK JURISDICTION HIERARCHY:
1. Federal (entire Pakistan)
2. Provincial (Khyber Pakhtunkhwa)
3. Division (Malakand, Hazara, Peshawar, etc.)
4. District (Swat, Dir, Mansehra, etc.)
5. Tehsil/Sub-district
6. Forest Compartment

SPECIAL JURISDICTIONS:
- Hazara Division: Hazara Forest Act applies
- Malakand Division: Special regulations
- Tribal Districts: Transitional status
- Protected Areas: Federal/provincial overlap

COMMON CONFLICTS:
- Federal vs Provincial authority
- Hazara vs KPK provincial laws
- District vs Division level
- Community forest vs State forest

REQUIREMENTS:
1. Analyze location specificity
2. Apply KPK administrative hierarchy
3. Consider special regional laws
4. Determine which authority has primacy
5. Flag complex jurisdictional issues"""
    
    def _gazette_reference_prompt(self) -> str:
        return """You are resolving gazette reference ambiguity in KPK legal documents.

SOURCE TEXT:
{source_text}

CANDIDATE GAZETTE REFERENCES:
{candidates}

EFFECTIVE DATE: {effective_date}

TASK: Identify correct gazette notification.

KPK GAZETTE SYSTEM:
- SRO (Statutory Regulatory Order): Amends laws
- Gazette Extraordinary: Immediate effect
- Regular Gazette: Standard publication
- Notification numbers: SRO-XXX/YYYY

COMMON SROs IN FORESTRY:
- SRO-123/2010: Protected species enhancement
- SRO-456/2015: General penalty enhancement
- SRO-789/2018: Biodiversity surcharge
- SRO-101/2020: Climate change surcharge

VALIDATION RULES:
1. Check SRO exists in gazette registry
2. Verify effective date
3. Check if still current (not repealed)
4. Confirm subject matter matches context

REQUIREMENTS:
1. Extract SRO number from text
2. Match to candidate
3. Validate against known SROs
4. Check temporal validity
5. Flag if SRO cannot be validated"""
    
    def _multilingual_term_prompt(self) -> str:
        return """You are resolving multilingual term ambiguity in KPK documents.

SOURCE TEXT:
{source_text}

CANDIDATE TRANSLATIONS/MEANINGS:
{candidates}

LOCATION: {location}

TASK: Determine correct meaning of multilingual term.

KPK MULTILINGUAL CONTEXT:
- Urdu: Official language, legal terminology
- Pashto: Regional language, local terms
- English: Technical/scientific terms
- Local dialects: Varied terminology

COMMON MULTILINGUAL PATTERNS:
- Urdu/English mix in official documents
- Pashto terms for local species/places
- OCR errors in non-Latin scripts
- Spelling variations in transliteration

SPECIFIC TERMS:
- جنگل (jungle/forest)
- درخت (tree)
- قطعہ (compartment)
- گزارہ (guzara/community forest)
- محفوظ (protected)

REQUIREMENTS:
1. Identify language(s) in term
2. Consider document context
3. Account for OCR/spelling errors
4. Match to forestry terminology
5. Provide best translation/interpretation"""
    
    def _ocr_error_resolution_prompt(self) -> str:
        return """You are resolving OCR errors in scanned KPK forestry documents.

SOURCE TEXT (with OCR errors):
{source_text}

CANDIDATE CORRECTIONS:
{candidates}

TASK: Determine correct text from OCR output.

COMMON OCR ERRORS IN KPK DOCUMENTS:
1. Similar characters: O/0, l/1, r/n
2. Urdu script errors: ک/گ, د/ڈ
3. Pashto script errors: پ/ب
4. Damaged text gaps
5. Mixed font issues

FORESTRY-SPECIFIC PATTERNS:
- "f0rest" → "forest"
- "Secti0n" → "Section"
- "De0dar" → "Deodar"
- "penalty" → "penalty"
- "gazette" → "gazette"

CONTEXT CLUES:
- Legal section numbers (27, 28, 32)
- Species names (Deodar, Chir, Kail)
- Gazette references (SRO numbers)
- Penalty amounts (Rs. X,XXX)

REQUIREMENTS:
1. Identify probable OCR errors
2. Use context to correct
3. Match to forestry terminology
4. Consider KPK-specific terms
5. Provide most likely correct version"""
    
    def _hazara_act_applicability_prompt(self) -> str:
        return """You are determining Hazara Forest Act applicability.

SOURCE TEXT:
{source_text}

CANDIDATE APPLICABILITY:
{candidates}

LOCATION: {location}
EFFECTIVE DATE: {effective_date}

TASK: Determine if/when Hazara Forest Act applies.

HAZARA FOREST ACT 1936:
- Special regional law for Hazara Division
- Applies alongside KPK Forest Ordinance
- Specific provisions for Hazara region
- May override KPK Ordinance in certain matters

APPLICABILITY CONDITIONS:
1. LOCATION: Must be in Hazara Division
   - Districts: Mansehra, Abbottabad, Haripur, Batagram, Kohistan
2. TIME: Must be after 1936 enactment
3. SUBJECT: Forestry matters within Hazara
4. CONFLICT: When conflicts with KPK Ordinance

COMMON SITUATIONS:
- "In Hazara division" → Hazara Act applies
- "Throughout the province" → KPK Ordinance applies
- Unclear location → Need context analysis
- Both laws mentioned → Hierarchy analysis needed

REQUIREMENTS:
1. Check location specificity
2. Check temporal validity
3. Analyze conflict with KPK Ordinance
4. Determine applicability conditions
5. Flag for legal review if complex"""
    
    def _sro_validity_prompt(self) -> str:
        return """You are validating SRO (gazette notification) references.

SOURCE TEXT:
{source_text}

CANDIDATE VALIDITY ASSESSMENTS:
{candidates}

EFFECTIVE DATE: {effective_date}

TASK: Determine if SRO reference is valid.

SRO VALIDATION CRITERIA:
1. EXISTENCE: SRO must be published in gazette
2. TEMPORAL: Must be effective at reference date
3. SUBJECT: Must match forestry context
4. CURRENT: Not repealed or superseded
5. JURISDICTION: Must apply to KPK

KNOWN FORESTRY SROs:
- SRO-123/2010: Protected species (Valid from 2010-04-01)
- SRO-456/2015: Penalty enhancement (Valid from 2015-08-01)
- SRO-789/2018: Biodiversity surcharge (Valid from 2018-07-01)
- SRO-101/2020: Climate surcharge (Valid from 2020-02-01)

VALIDATION STEPS:
1. Extract SRO number from text
2. Check against known SRO registry
3. Verify effective date
4. Confirm subject relevance
5. Check if still current

REQUIREMENTS:
1. Identify SRO reference
2. Validate existence
3. Check temporal validity
4. Assess subject relevance
5. Provide validity determination"""
    
    def _generic_ambiguity_prompt(self) -> str:
        return """You are resolving ambiguity in KPK forestry document analysis.

SOURCE TEXT:
{source_text}

CANDIDATE RESOLUTIONS:
{candidates}

AMBIGUITY TYPE: {ambiguity_type}
LOCATION: {location}
EFFECTIVE DATE: {effective_date}

TASK: Choose the most appropriate resolution.

GENERAL GUIDELINES:
1. Prefer resolutions consistent with KPK forestry laws
2. Consider temporal validity
3. Consider geographic applicability
4. Apply rule-based constraints when known
5. When uncertain, prefer abstention over wrong resolution

KPK CONTEXT CONSIDERATIONS:
- KPK Forest Ordinance 2002 is primary law
- Hazara Forest Act applies only in Hazara Division
- Gazette notifications amend existing laws
- Department circulars provide implementation guidance
- Working plans have specific validity periods

REQUIREMENTS:
1. Analyze context thoroughly
2. Apply KPK-specific knowledge
3. Choose best-supported candidate
4. Provide evidence-based explanation
5. Flag for human review if uncertain"""
    
    # ========== INTEGRATION FUNCTIONS ==========
    
    def resolve_with_llm_if_needed(self, ambiguity_data: Dict, 
                                  rule_extractor_output: Dict) -> Dict[str, Any]:
        """
        Integration function for rule_extractor.py
        
        Usage in rule_extractor.py:
        
        from llm_ambiguity_resolver import resolve_with_llm_if_needed
        
        # When rule-based extraction has ambiguity
        resolution = resolve_with_llm_if_needed(ambiguity_data, rule_extractor_output)
        """
        # Create ambiguity context
        context = AmbiguityContext(
            ambiguity_type=AmbiguityType(ambiguity_data.get("type", "generic")),
            source_text=ambiguity_data.get("source_text", ""),
            candidates=ambiguity_data.get("candidates", []),
            document_id=ambiguity_data.get("document_id"),
            document_type=ambiguity_data.get("document_type"),
            location=ambiguity_data.get("location"),
            effective_date=ambiguity_data.get("effective_date"),
            rules_context=rule_extractor_output,
            rule_confidence=rule_extractor_output.get("confidence", 0.0),
            rule_constraints=rule_extractor_output.get("constraints", []),
        )
        
        # Resolve using enhanced resolver
        resolution = self.resolve_ambiguity(context, viva_mode=False)
        
        # Convert to dict and add statistics
        result = resolution.to_dict()
        result["resolver_statistics"] = self.get_research_statistics()
        
        return result


# ========== FACTORY FUNCTIONS ==========

def create_llm_resolver(
    config: Optional[Dict] = None,
    authority_resolver: Optional[AuthorityHierarchyResolver] = None,
    penalty_engine: Optional[PenaltyLogicEngine] = None,
    abstention_logger: Optional[AbstentionLogger] = None,
) -> LLMAmbiguityResolver:
    """Factory function to create enhanced LLM resolver."""
    return LLMAmbiguityResolver(
        config=config,
        authority_resolver=authority_resolver,
        penalty_engine=penalty_engine,
        abstention_logger=abstention_logger,
    )


# ========== COMMAND LINE INTERFACE ==========

def main():
    """Command line interface for testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Enhanced LLM Ambiguity Resolver')
    parser.add_argument('--test', action='store_true', help='Run test cases')
    parser.add_argument('--config', help='Configuration file (JSON)')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--viva', action='store_true', help='VIVA demonstration mode')
    
    args = parser.parse_args()
    
    # Load configuration
    config = {}
    if args.config:
        import json
        with open(args.config, 'r') as f:
            config = json.load(f)
    
    resolver = create_llm_resolver(config)
    
    if args.test:
        print("=" * 80)
        print("ENHANCED LLM AMBIGUITY RESOLVER - RESEARCH DEMONSTRATION")
        print("=" * 80)
        print("Phase 5.3: Controlled LLM Assistance with Phase 5.1-5.2 Integration")
        print()
        
        # Test Case 1: Hazara Act Applicability (RESEARCH FOCUS)
        print("TEST CASE 1: Hazara Act Applicability Ambiguity")
        print("-" * 80)
        
        context1 = AmbiguityContext(
            ambiguity_type=AmbiguityType.HAZARA_ACT_APPLICABILITY,
            source_text="In Hazara Division, cutting Deodar trees requires permission under the relevant Act.",
            candidates=["Hazara Forest Act 1936 applies", "KPK Forest Ordinance 2002 applies"],
            location="Mansehra, Hazara Division",
            effective_date=date(2023, 6, 15),
            requires_kpk_context=True,
            involves_hazara_act=True,
        )
        
        result1 = resolver.resolve_ambiguity(context1, viva_mode=args.viva)
        print(f"Final Resolution: {result1.final_resolution}")
        print(f"Confidence: {result1.confidence:.2f}")
        print(f"Method: {result1.resolution_method}")
        if result1.abstention_reason:
            print(f"Abstention Reason: {result1.abstention_reason}")
        
        print("\n" + "=" * 80)
        
        # Test Case 2: Section Reference with OCR Errors
        print("\nTEST CASE 2: Section Reference with OCR Errors")
        print("-" * 80)
        
        context2 = AmbiguityContext(
            ambiguity_type=AmbiguityType.SECTION_REFERENCE,
            source_text="Penalty for unauthorized felling is prescribed in Secti0n 27 of the Ordinance.",
            candidates=["Section 27", "Section 15", "Section 42"],
            document_type="Scanned KPK Ordinance",
            location="KPK",
            effective_date=date(2023, 6, 15),
        )
        
        result2 = resolver.resolve_ambiguity(context2, viva_mode=args.viva)
        print(f"Final Resolution: {result2.final_resolution}")
        print(f"Confidence: {result2.confidence:.2f}")
        print(f"LLM Used: {result2.llm_suggestion.llm_model if result2.llm_suggestion else 'None'}")
        
        print("\n" + "=" * 80)
        
        # Test Case 3: Authority Conflict Resolution
        print("\nTEST CASE 3: Authority Conflict Resolution")
        print("-" * 80)
        
        context3 = AmbiguityContext(
            ambiguity_type=AmbiguityType.AUTHORITY_CONFLICT,
            source_text="The notification states that in protected areas, federal laws take precedence.",
            candidates=["Federal Forest Act 1927 applies", "KPK Forest Ordinance 2002 applies"],
            location="Ayubia National Park, Hazara Division",
            effective_date=date(2023, 6, 15),
            requires_kpk_context=True,
        )
        
        result3 = resolver.resolve_ambiguity(context3, viva_mode=args.viva)
        print(f"Final Resolution: {result3.final_resolution}")
        print(f"Confidence: {result3.confidence:.2f}")
        print(f"Verification Steps: {len(result3.verification_steps)}")
        
        print("\n" + "=" * 80)
        
        # Test Case 4: Multilingual Species Identification
        print("\nTEST CASE 4: Multilingual Species Identification")
        print("-" * 80)
        
        context4 = AmbiguityContext(
            ambiguity_type=AmbiguityType.SPECIES_IDENTIFICATION,
            source_text="قطع دیار درخت کی سزا دس ہزار روپے ہے۔",
            candidates=["Deodar tree", "Chir pine tree", "Walnut tree"],
            location="Swat, Malakand Division",
            effective_date=date(2023, 6, 15),
            requires_kpk_context=True,
        )
        
        result4 = resolver.resolve_ambiguity(context4, viva_mode=args.viva)
        print(f"Final Resolution: {result4.final_resolution}")
        print(f"Confidence: {result4.confidence:.2f}")
        
        print("\n" + "=" * 80)
        
        # Display statistics
        stats = resolver.get_research_statistics()
        print("\nRESEARCH STATISTICS:")
        print("-" * 80)
        print(f"Total Resolutions: {stats['total_resolutions']}")
        print(f"LLM Calls: {stats['llm_calls']}")
        print(f"LLM Verified Resolutions: {stats['llm_verified_resolutions']}")
        print(f"Rules Only Resolutions: {stats['rules_only_resolutions']}")
        print(f"Abstentions: {stats['abstentions']}")
        print(f"Average Confidence: {stats['average_confidence']:.2f}")
        print(f"Average Processing Time: {stats['average_processing_time_ms']:.0f} ms")
        print(f"Hazara Act Resolutions: {stats['hazara_act_resolutions']}")
        print(f"SRO Resolutions: {stats['sro_resolutions']}")
        
        if 'confidence_stats' in stats:
            print(f"\nConfidence Statistics:")
            conf_stats = stats['confidence_stats']
            print(f"  Mean: {conf_stats['mean']:.2f}")
            print(f"  Median: {conf_stats['median']:.2f}")
            print(f"  Range: {conf_stats['min']:.2f} - {conf_stats['max']:.2f}")
        
        # Export graph data
        graph_data = resolver.export_resolutions_for_graph()
        print(f"\nGraph Data Prepared:")
        print(f"  Nodes: {len(graph_data['nodes'])}")
        print(f"  Edges: {len(graph_data['edges'])}")
        print(f"  Graph Type: {graph_data['metadata']['graph_type']}")
        
        print("\n" + "=" * 80)
        print("Enhanced LLM Ambiguity Resolver Test Complete ✓")
        print("Ready for Phase 6 Graph Construction")
        
    else:
        print("Enhanced LLM Ambiguity Resolver initialized.")
        print("Use --test to run test cases or --viva for demonstration mode.")


if __name__ == "__main__":
    main()
