"""
7.1_BATCH_PROCESSOR.PY - Phase 7: Enhanced Pipeline Orchestration
Complete controller for KPK forestry document processing with full phase integration.
Handles alphanumeric module names via dynamic imports.
"""

import os
import sys
import logging
import asyncio
import importlib
import json
import traceback
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass
import dataclasses
from pathlib import Path

# Add data_pipeline to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

# Import Common Modules (Standard names, so standard import works)
from preprocessing_pipeline.common.config import PipelineConfig, load_config
from preprocessing_pipeline.common.llm_client import LLMClient
from preprocessing_pipeline.common.constants import DocumentType, ProcessingStatus, QualityThresholds
# from phase_7_orchestration.quality_gates import KPKQualityGateManager (Invalid syntax)



# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pipeline.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def dynamic_import(module_name: str, class_name: str, package: str = None):
    """Import class from module with alphanumeric name (handles dots in filenames)."""
    try:
        # Resolve path
        if package:
            # Assume package is relative to current sys.path additions
            # e.g. "preprocessing_pipeline.phase_1_extraction"
            package_path = package.replace(".", "/")
            # Root directory (e:/GL_AI/src) + package_path
            # Use relative path from this file's location
            # This file is in src/preprocessing_pipeline/phase_7_orchestration
            # We need src/
            src_root = Path(__file__).parent.parent.parent
            base_dir = src_root
            file_path = base_dir / package_path / f"{module_name}.py"
        else:
            file_path = Path(f"{module_name}.py")

        if not file_path.exists():
            logger.error(f"File not found for dynamic import: {file_path}")
            return None

        import importlib.util
        # Use full dotted name for better package resolution during dynamic loading
        full_module_name = f"{package}.{module_name.replace('.', '_')}" if package else module_name.replace(".", "_")
        spec = importlib.util.spec_from_file_location(full_module_name, str(file_path))
        mod = importlib.util.module_from_spec(spec)
        if package:
            mod.__package__ = package
        spec.loader.exec_module(mod)
        return getattr(mod, class_name)
    except Exception as e:
        logger.error(f"Failed to import {class_name} from {module_name} ({package}): {e}")
        return None


@dataclass
class PhaseResult:
    """Standardized result from each phase"""
    status: ProcessingStatus
    data: Dict[str, Any]
    metrics: Dict[str, float]
    warnings: List[str]
    errors: List[str]
    duration_seconds: float
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary"""
        import dataclasses
        from enum import Enum
        from pathlib import Path
        
        def _serialize(obj):
            if dataclasses.is_dataclass(obj):
                return _serialize(dataclasses.asdict(obj))
            if isinstance(obj, dict):
                return {str(k): _serialize(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple, set)):
                return [_serialize(i) for i in obj]
            if isinstance(obj, Enum):
                return obj.value
            if isinstance(obj, datetime):
                return obj.isoformat()
            if isinstance(obj, Path):
                return str(obj)
            return obj

        return {
            'status': _serialize(self.status),
            'data': _serialize(self.data),
            'metrics': self.metrics,
            'warnings': self.warnings,
            'errors': self.errors,
            'duration_seconds': self.duration_seconds,
            'timestamp': self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp
        }

@dataclass 
class PipelineContext:
    """Complete pipeline execution context"""
    document_id: str
    file_path: Path
    config: PipelineConfig
    current_phase: int = 0
    status: ProcessingStatus = ProcessingStatus.PENDING
    results: Dict[int, PhaseResult] = None
    quality_scores: Dict[str, float] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        self.results = {}
        self.quality_scores = {}
        self.metadata = {
            "processing_start": datetime.now(),
            "document_type": None,
            "kpk_region": None
        }

class KPKPipelineOrchestrator:
    """
    Complete orchestrator for the 7-phase KPK forestry document pipeline.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        try:
            self.config = load_config(config_path) if 'load_config' in globals() else None
        except:
            self.config = None
            
        # Try to load quality manager dynamically
        gate_cls = dynamic_import("7.2_quality_gates", "KPKQualityGateManager", "preprocessing_pipeline.phase_7_orchestration")
        self.quality_manager = gate_cls(self.config) if gate_cls else None

            
        try:
            self.llm_client = LLMClient(self.config.llm_settings) if 'LLMClient' in globals() and self.config else None
        except:
            self.llm_client = None
        
        # Initialize all modules dynamically
        self.modules = self._initialize_modules()
        
        logger.info(f"Pipeline initialized.")
        
    def _initialize_modules(self) -> Dict[str, Any]:
        """Initialize all pipeline modules using dynamic imports matching file structure."""
        modules = {}
        
        # Helper to simplify calls
        # Note: Package paths map to the alphanumeric directory structure
        
        # Phase 0: Foundation
        pkg0 = "preprocessing_pipeline.phase_0_foundation"
        modules["doc_profiler"] = self._init_component("0.1_doc_profiler", "KPKDocumentProfiler", pkg0)
        modules["metadata_enricher"] = self._init_component("0.2_kpk_metadata_enricher", "KPKMetadataEnricher", pkg0)
        modules["abstention_logger"] = self._init_component("0.3_abstention_log", "AbstentionLogger", pkg0)
        modules["quality_assessor"] = self._init_component("0.4_doc_quality_assessor", "DocQualityAssessor", pkg0)

        # Phase 1: Extraction
        pkg1 = "preprocessing_pipeline.phase_1_extraction"
        modules["pdf_parser"] = self._init_component("1.1_pdf_parser", "KPKPDFParser", pkg1)
        modules["layout_extractor"] = self._init_component("1.2_extract_layout", "LayoutExtractor", pkg1)
        modules["table_extractor"] = self._init_component("1.3_table_extractor", "TableExtractor", pkg1)
        modules["image_processor"] = self._init_component("1.4_image_processor", "ImageProcessor", pkg1)
        modules["ocr_engine"] = self._init_component("1.5_ocr_engine", "KPKOCREngine", pkg1)
        
        # Phase 2: Restoration
        pkg2 = "preprocessing_pipeline.phase_2_restoration"
        modules["text_sanitizer"] = self._init_component("2.1_llm_text_sanitizer", "LLMTextSanitizer", pkg2, self.llm_client)
        modules["multilingual_segmenter"] = self._init_component("2.2_multilingual_segmenter", "MultilingualSegmenter", pkg2)

        # Phase 3: Linguistic Alignment
        pkg3 = "preprocessing_pipeline.phase_3_linguistic_alignment"
        modules["multilingual_handler"] = self._init_component("3.1_multilingual_handler", "MultilingualHandler", pkg3)
        modules["section_detector"] = self._init_component("3.4_section_detector", "KPKSectionDetector", pkg3)

        # Phase 4: Legal Extraction
        pkg4 = "preprocessing_pipeline.phase_4_legal_extraction"
        modules["rule_extractor"] = self._init_component("4.1_rule_extractor", "KPKRuleExtractor", pkg4)
        modules["ner_extractor"] = self._init_component("4.2_ner_extractor", "LLMNERExtractor", pkg4, self.llm_client)
        modules["amendment_tracker"] = self._init_component("4.3_amendment_tracker", "KPAmendmentTracker", pkg4)
        modules["citation_resolver"] = self._init_component("4.4_citation_resolver", "KPKCitationResolver", pkg4)

        # Phase 5: Authority Reasoning
        pkg5 = "preprocessing_pipeline.phase_5_authority_reasoning"
        modules["authority_resolver"] = self._init_component("5.1_authority_hierarchy", "AuthorityHierarchyResolver", pkg5)
        modules["penalty_engine"] = self._init_component("5.2_penalty_logic_engine", "PenaltyLogicEngine", pkg5)
        modules["ambiguity_resolver"] = self._init_component("5.3_llm_ambiguity_resolver", "LLMAmbiguityResolver", pkg5, self.llm_client)
        modules["temporal_validator"] = self._init_component("5.4_temporal_validator", "TemporalValidator", pkg5)

        # Phase 6: Graph Construction
        pkg6 = "preprocessing_pipeline.phase_6_graph_construction"
        modules["graph_schema"] = self._init_component("6.1_graph_schema_kpk", "KPKGraphSchema", pkg6)
        modules["graph_mapper"] = self._init_component("6.2_graph_mapper", "KPKGraphMapper", pkg6)
        # Graph Builder acts as orchestrator for 6.4-6.8
        modules["graph_builder"] = self._init_component("6.3_graph_builder", "KPKGraphBuilder", pkg6)

        
        return modules

    def _init_component(self, module_name, class_name, package, *args):
        """Instantiate a component if class is found."""
        cls = dynamic_import(module_name, class_name, package)
        if cls:
            # Filter None args
            valid_args = [arg for arg in args if arg is not None]
            
            # Try initializing with config first (Standardized: config is ALWAYS first if accepted)
            if self.config:
                try:
                    # New Standard: config is ALWAYS the first argument
                    return cls(self.config, *valid_args)
                except TypeError:
                    # If TypeError, it might be an old style or no-config component
                    try:
                        if valid_args:
                            return cls(*valid_args)
                        return cls()
                    except Exception as e:
                        logger.warning(f"Failed to instantiate {class_name}: {e}")
                        return None
            
            # Fallback for no config available
            try:
                if valid_args:
                    return cls(*valid_args)
                return cls()
            except Exception as e:
                logger.warning(f"Failed to instantiate {class_name}: {e}")
                return None
        return None


    async def process_document(self, file_path: str, use_dag: bool = True) -> PipelineContext:
        """Process document through pipeline."""
        file_path_obj = Path(file_path)
        doc_id = f"{file_path_obj.stem}"
        context = PipelineContext(
            document_id=doc_id,
            file_path=file_path_obj,
            config=self.config
        )
        
        try:
            logger.info(f"Processing {doc_id}...")
            
            if use_dag:
                # Use the resilient DAG-based orchestration
                from preprocessing_pipeline.phase_7_orchestration.pipeline_dag_wrapper import ResilientOrchestrator
                dag_runner = ResilientOrchestrator(self)
                dag_result = await dag_runner.process_with_dag(str(file_path), context)
                logger.info(f"DAG Execution Result: {dag_result}")
                
                # CRITICAL: Save results from DAG run to disk
                for phase_num in [0, 1, 2, 3, 4, 5, 6, 7]:
                    if phase_num in context.results:
                        await self._save_phase_output(context, phase_num)
            else:
                # Original linear flow
                # === Phase 1: Extraction ===
                await self._execute_phase_1(context)
                await self._save_phase_output(context, 1)
                
                # === Phase 2: Restoration ===
                await self._execute_phase_2(context)
                await self._save_phase_output(context, 2)
                
                # === Phase 3: Linguistic Alignment ===
                await self._execute_phase_3(context)
                await self._save_phase_output(context, 3)
                
                # === Phase 4: Legal Extraction ===
                await self._execute_phase_4(context)
                await self._save_phase_output(context, 4)
                
                # === Phase 6: Graph Construction ===
                await self._execute_phase_6(context)
                await self._save_phase_output(context, 6)
            
            context.status = ProcessingStatus.COMPLETED
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            logger.error(traceback.format_exc())
            context.status = ProcessingStatus.FAILED
            context.metadata["error"] = str(e)
            context.metadata["traceback"] = traceback.format_exc()
            
        return context

    async def _execute_phase_0(self, context: PipelineContext):
        """Execute Phase 0: Foundation (Profiling & Metadata)"""
        start_time = datetime.now()
        logger.info(f"Phase 0: Foundation for {context.document_id}")
        
        foundation_data = {
            "profile": {},
            "metadata": {},
            "quality": {}
        }
        
        # 1. Document Profiling
        if self.modules.get("doc_profiler"):
            try:
                foundation_data["profile"] = self.modules["doc_profiler"].profile_document(str(context.file_path))
            except Exception as e:
                logger.error(f"Profiling failed: {e}")

        # 2. Metadata Enrichment
        if self.modules.get("metadata_enricher"):
            try:
                foundation_data["metadata"] = self.modules["metadata_enricher"].enrich_metadata(str(context.file_path))
            except Exception as e:
                logger.error(f"Metadata enrichment failed: {e}")

        # 3. Quality Assessment
        if self.modules.get("quality_assessor"):
            try:
                foundation_data["quality"] = self.modules["quality_assessor"].assess_quality(str(context.file_path))
            except Exception as e:
                logger.error(f"Quality assessment failed: {e}")

        res = PhaseResult(
            status=ProcessingStatus.COMPLETED,
            data=foundation_data,
            metrics={},
            warnings=[],
            errors=[],
            duration_seconds=(datetime.now() - start_time).total_seconds(),
            timestamp=datetime.now()
        )
        context.results[0] = res
        return res

    def _extract_with_ocr(self, file_path: Path) -> Dict[str, Any]:
        """OCR fallback for scanned PDFs and non-PDF binaries."""
        data = {"raw_text": "", "metadata": {}}
        if not self.modules.get("ocr_engine"):
            logger.error("OCR Engine module not loaded.")
            return data
        logger.info(f"Using OCR engine on: {file_path}")
        res = self.modules["ocr_engine"].process_document(str(file_path))
        raw_text = getattr(res, "full_text", "") or ""
        if not raw_text.strip():
            logger.warning(f"OCR returned empty text for {file_path}")
        data["raw_text"] = raw_text
        meta = getattr(res, "preprocessing_summary", None)
        data["metadata"] = dict(meta) if isinstance(meta, dict) else {}
        data["metadata"]["extraction_method"] = "ocr_engine"
        if hasattr(res, "pages"):
            data["metadata"]["total_pages"] = len(res.pages)
        return data

    def _extract_pdf_with_parser(self, file_path: Path, ocr_fallback_threshold: int = 100) -> Dict[str, Any]:
        """Native PDF text extraction via KPKPDFParser; OCR only if text is insufficient."""
        data = {"raw_text": "", "metadata": {}}
        pdf_parser = self.modules.get("pdf_parser")
        if not pdf_parser:
            logger.warning("PDF parser not loaded; falling back to OCR")
            return self._extract_with_ocr(file_path)

        logger.info(f"Using PDF parser on: {file_path}")
        parse_result = pdf_parser.parse_pdf(str(file_path))
        raw_text = ""
        if hasattr(parse_result, "get_all_text"):
            raw_text = parse_result.get_all_text() or ""
        data["raw_text"] = raw_text
        data["metadata"] = {
            "total_pages": getattr(parse_result, "total_pages", 0),
            "extraction_method": getattr(parse_result, "parsing_method", "pdf_parser"),
            "total_characters": getattr(parse_result, "total_characters", len(raw_text)),
            "total_words": getattr(parse_result, "total_words", 0),
            "parsing_success_rate": getattr(parse_result, "success_rate", None),
        }

        if len(raw_text.strip()) < ocr_fallback_threshold and self.modules.get("ocr_engine"):
            logger.warning(
                f"PDF parser returned only {len(raw_text.strip())} chars for {file_path.name}; "
                "trying OCR fallback"
            )
            ocr_data = self._extract_with_ocr(file_path)
            if len(ocr_data.get("raw_text", "").strip()) > len(raw_text.strip()):
                return ocr_data
        return data

    async def _execute_phase_1(self, context: PipelineContext):
        """Execute Phase 1: Extraction"""
        start_time = datetime.now()
        data = {"raw_text": "", "metadata": {}}
        
        ext = context.file_path.suffix.lower()
        if ext in ['.json', '.csv', '.xlsx', '.xls', '.txt']:
            logger.info(f"Directly reading structured file: {context.file_path}")
            try:
                import pandas as pd
                if ext == '.json':
                    with open(context.file_path, 'r', encoding='utf-8-sig') as f:
                        json_data = json.load(f)
                        data["raw_text"] = json.dumps(json_data, indent=2)
                        data["metadata"]["source_type"] = "json"
                elif ext == '.csv':
                    df = pd.read_csv(context.file_path)
                    data["raw_text"] = df.to_string()
                    data["metadata"]["source_type"] = "csv"
                    data["metadata"]["row_count"] = len(df)
                elif ext == '.txt':
                    with open(context.file_path, 'r', encoding='utf-8-sig') as f:
                        data["raw_text"] = f.read()
                        data["metadata"]["source_type"] = "text"
                elif ext in ['.xlsx', '.xls']:
                    df = pd.read_excel(context.file_path)
                    data["raw_text"] = df.to_string()
                    data["metadata"]["source_type"] = "xlsx"
            except ImportError:
                data["raw_text"] = "[Pandas not installed, cannot read structured file]"
            except Exception as e:
                logger.error(f"Direct read failed for {context.file_path}: {e}")
                data["raw_text"] = f"[Error reading {ext} file: {e}]"

        elif ext == '.pdf':
            try:
                data = self._extract_pdf_with_parser(context.file_path)
            except Exception as ex:
                logger.error(f"PDF parser failed for {context.file_path}: {ex}")
                logger.error(traceback.format_exc())
                try:
                    data = self._extract_with_ocr(context.file_path)
                except Exception as ocr_ex:
                    logger.error(f"OCR fallback also failed: {ocr_ex}")
                    data = {"raw_text": "", "metadata": {}, "error": str(ex)}

        elif self.modules.get("ocr_engine"):
            try:
                data = self._extract_with_ocr(context.file_path)
            except Exception as ex:
                logger.error(f"Extraction failed: {ex}")
                logger.error(traceback.format_exc())
                data = {"raw_text": "", "metadata": {}, "error": str(ex)}
        else:
            logger.error("No extraction module available for %s", context.file_path)

        result = PhaseResult(
            status=ProcessingStatus.COMPLETED,
            data=data,
            metrics={"text_len": len(data.get("raw_text", ""))},
            warnings=[],
            errors=[],
            duration_seconds=(datetime.now() - start_time).total_seconds(),
            timestamp=datetime.now()
        )
        context.results[1] = result
        return result

    async def _execute_phase_2(self, context: PipelineContext):
        """Execute Phase 2: Restoration"""
        start_time = datetime.now()
        p1_res = context.results.get(1)
        if p1_res:
            if hasattr(p1_res, 'data'):
                raw_text = p1_res.data.get("raw_text", "")
            elif isinstance(p1_res, dict):
                raw_text = p1_res.get("data", {}).get("raw_text", "")
            else:
                raw_text = ""
        else:
            raw_text = ""
        
        logger.info(f"Phase 2 raw text length: {len(raw_text)}")
        
        if self.modules.get("text_sanitizer"):
            # Skip slow LLM sanitization on tiny extractions (unsupported formats, OCR failures)
            use_llm_sanitize = len(raw_text.strip()) >= 500
            result = self.modules["text_sanitizer"].sanitize_text(raw_text, use_llm=use_llm_sanitize)
            data = result.to_dict() if hasattr(result, 'to_dict') else result
        else:
            data = {"sanitized_text": raw_text, "skipped": True}
            
        res = PhaseResult(
            status=ProcessingStatus.COMPLETED,
            data=data,
            metrics={},
            warnings=[],
            errors=[],
            duration_seconds=(datetime.now() - start_time).total_seconds(),
            timestamp=datetime.now()
        )
        context.results[2] = res
        return res

    async def _execute_phase_3(self, context: PipelineContext):
        """Execute Phase 3: Linguistic Alignment & Section Detection"""
        start_time = datetime.now()
        p2_res = context.results.get(2)
        sanitized_text = p2_res.data.get("sanitized_text", "") if p2_res else ""
        
        if self.modules.get("section_detector"):
            sections = self.modules["section_detector"].detect_sections(sanitized_text)
            data = {"sections": sections, "text": sanitized_text}
        else:
            data = {"text": sanitized_text, "skipped": True}
            
        res = PhaseResult(
            status=ProcessingStatus.COMPLETED,
            data=data,
            metrics={},
            warnings=[],
            errors=[],
            duration_seconds=(datetime.now() - start_time).total_seconds(),
            timestamp=datetime.now()
        )
        context.results[3] = res
        return res

    async def _execute_phase_4(self, context: PipelineContext):
        """Execute Phase 4: Legal Extraction (Rules + LLM NER)"""
        start_time = datetime.now()
        p3_data = context.results.get(3, {}).data
        p1_res = context.results.get(1)
        if p1_res:
            if hasattr(p1_res, 'data'):
                raw_text = p1_res.data.get("raw_text", "")
            elif isinstance(p1_res, dict):
                raw_text = p1_res.get("data", {}).get("raw_text", "")
            else:
                raw_text = ""
        else:
            raw_text = ""
        # Get sanitized text from Phase 2
        sanitized_text = context.results.get(2, {}).data.get("sanitized_text", "") or p3_data.get("text", "")
        
        entities_data = {
            "rule_extracted_entities": {},
            "llm_suggested_entities": [],
            "relationships": [],
            "metadata": {"raw_text": raw_text, "doc_id": context.document_id}
        }
        
        extraction_input = {
            "normalized_text": sanitized_text,
            "metadata": {"raw_text": raw_text, "doc_id": context.document_id}
        }

        # 1. Deterministic Rule Extraction
        if self.modules.get("rule_extractor"):
            rule_results = self.modules["rule_extractor"].process_normalized_document(extraction_input)
            entities_data["rule_extracted_entities"] = rule_results.get("rule_extracted_entities", {})
            entities_data["relationships"].extend(rule_results.get("relationships", []))
            
        # 2. LLM-Assisted NER (skip tiny text; cap huge manuals to keep batch moving)
        _MAX_LLM_NER_CHARS = 80_000
        _ner_text = sanitized_text.strip()
        if self.modules.get("ner_extractor") and len(_ner_text) >= 100:
            if len(_ner_text) > _MAX_LLM_NER_CHARS:
                logger.info(
                    "Skipping LLM NER for %s: %s chars exceeds cap %s (rule extraction kept)",
                    context.document_id, len(_ner_text), _MAX_LLM_NER_CHARS,
                )
            else:
                try:
                    if hasattr(self.modules["ner_extractor"], "extract_with_assistance"):
                        llm_results = self.modules["ner_extractor"].extract_with_assistance(
                            sanitized_text, {"doc_id": context.document_id}
                        )
                        entities_data["llm_suggested_entities"] = llm_results.get("validated_entities", [])
                        entities_data["ambiguity_cases"] = llm_results.get("ambiguity_cases", [])
                except Exception as e:
                    logger.error(f"LLM NER extraction failed for {context.document_id}: {e}")
            
        res = PhaseResult(
            status=ProcessingStatus.COMPLETED,
            data=entities_data,
            metrics={"entity_count": len(entities_data.get("llm_suggested_entities", []))},
            warnings=[],
            errors=[],
            duration_seconds=(datetime.now() - start_time).total_seconds(),
            timestamp=datetime.now()
        )
        context.results[4] = res
        return res

    async def _execute_phase_5(self, context: PipelineContext):
        """Execute Phase 5: Authority Reasoning"""
        start_time = datetime.now()
        logger.info(f"Phase 5: Authority Reasoning for {context.document_id}")
        
        # Get data from Phase 4
        p4_res = context.results.get(4)
        if hasattr(p4_res, 'data'):
            p4_data = p4_res.data
        elif isinstance(p4_res, dict):
            p4_data = p4_res.get("data", {})
        else:
            p4_data = {}

        reasoning_data = {
            "authority_hierarchy": [],
            "penalties": [],
            "ambiguities": [],
            "temporal_validation": {}
        }
        
        # 1. Authority Hierarchy
        if self.modules.get("authority_resolver"):
            try:
                # AuthorityHierarchyResolver (5.1) main method is resolve_conflict or adapter
                if hasattr(self.modules["authority_resolver"], "resolve_conflict"):
                    # We pass the entities and relationships from Phase 4
                    entities = p4_data.get("rule_extracted_entities", {})
                    # This is a simplification; a real call would iterate or pass whole set
                    res = self.modules["authority_resolver"].resolve_conflict(
                        entity=context.document_id,
                        conflicting_sources=list(entities.keys()),
                    )
                    reasoning_data["authority_hierarchy"] = res
            except Exception as e:
                logger.error(f"Authority resolution failed: {e}")
             
        # 2. Penalty Logic
        if self.modules.get("penalty_engine"):
            try:
                if hasattr(self.modules["penalty_engine"], "calculate_penalty"):
                    # We evaluate penalties for extracted entities
                    entities = p4_data.get("rule_extracted_entities", {})
                    penalties = []
                    for entity_name, details in entities.items():
                        if "penalty" in str(details).lower() or "violation" in str(details).lower():
                            res = self.modules["penalty_engine"].calculate_penalty(
                                violation_type=entity_name,
                                quantity=1
                            )
                            penalties.append(res.to_dict() if hasattr(res, 'to_dict') else res)
                    reasoning_data["penalties"] = penalties
            except Exception as e:
                logger.error(f"Penalty evaluation failed: {e}")
             
        # 3. Ambiguity Resolution
        if self.modules.get("ambiguity_resolver"):
            try:
                if hasattr(self.modules["ambiguity_resolver"], "resolve_ambiguity"):
                    ambiguity_cases = p4_data.get("ambiguity_cases", [])
                    resolved = []
                    for case in ambiguity_cases:
                        res = self.modules["ambiguity_resolver"].resolve_ambiguity(case)
                        resolved.append(res.to_dict() if hasattr(res, 'to_dict') else res)
                    reasoning_data["ambiguities"] = resolved
            except Exception as e:
                logger.error(f"Ambiguity resolution failed: {e}")
             
        # 4. Temporal Validation
        if self.modules.get("temporal_validator"):
            try:
                if hasattr(self.modules["temporal_validator"], "validate"):
                    res = self.modules["temporal_validator"].validate(
                        entity_id=context.document_id,
                        entity_title=context.document_id,
                        context=p4_data
                    )
                    reasoning_data["temporal_validation"] = res.to_dict() if hasattr(res, 'to_dict') else res
            except Exception as e:
                logger.error(f"Temporal validation failed: {e}")

        res = PhaseResult(
            status=ProcessingStatus.COMPLETED,
            data=reasoning_data,
            metrics={"conflict_count": len(reasoning_data.get("authority_hierarchy", []))},
            warnings=[],
            errors=[],
            duration_seconds=(datetime.now() - start_time).total_seconds(),
            timestamp=datetime.now()
        )
        context.results[5] = res
        return res

    async def _execute_phase_6(self, context: PipelineContext):
        """Execute Phase 6: Graph Construction"""
        start_time = datetime.now()
        
        # Get extracted data from previous phases
        p4_res = context.results.get(4)
        if p4_res:
            if hasattr(p4_res, 'data'):
                p4_data = p4_res.data
            elif isinstance(p4_res, dict):
                p4_data = p4_res.get("data", {})
            else:
                p4_data = {}
        else:
            p4_data = {}

        p1_res = context.results.get(1)
        if p1_res:
            if hasattr(p1_res, 'data'):
                raw_text = p1_res.data.get("raw_text", "")
            elif isinstance(p1_res, dict):
                raw_text = p1_res.get("data", {}).get("raw_text", "")
            else:
                raw_text = ""
        else:
            raw_text = ""
        
        # Get Phase 5 data if available
        p5_res = context.results.get(5)
        if p5_res:
            if hasattr(p5_res, 'data'):
                p5_data = p5_res.data
            elif isinstance(p5_res, dict):
                p5_data = p5_res.get("data", {})
            else:
                p5_data = {}
        else:
            p5_data = {}

        # Prepare data for mapping (KPK Graph Schema)
        pipeline_output = {
            "document_id": context.document_id,
            "phase_4": {
                "4.1_rules": p4_data,
                "4.2_entities": p4_data.get("validated_entities", []),
                "4.3_amendments": p4_data.get("amendments", []),
                "4.4_citations": p4_data.get("citations", [])
            },
            "phase_5": p5_data,
            "metadata": {"raw_text": raw_text, "document_id": context.document_id}
        }
        
        # Step 1: Map to Graph Schema
        if self.modules.get("graph_mapper"):
            logger.info("Mapping pipeline output to graph schema...")
            mapped_data = self.modules["graph_mapper"].map_pipeline_output(pipeline_output)
        else:
            logger.warning("Graph mapper not found. Using raw data.")
            mapped_data = {
                "nodes": [], 
                "relationships": [], 
                "metadata": {"raw_text": raw_text, "document_id": context.document_id}
            }

        # Step 2: Build Graph & Run RAG (Chunking/Embedding/Indexing)
        if self.modules.get("graph_builder"):
            build_result = self.modules["graph_builder"].build_graph_from_mapped_data(mapped_data)
            data = build_result
        else:
            data = {"status": "skipped"}
            
        res = PhaseResult(
            status=ProcessingStatus.COMPLETED,
            data=data,
            metrics=data.get("statistics", {}) if isinstance(data, dict) else {},
            warnings=[],
            errors=[],
            duration_seconds=(datetime.now() - start_time).total_seconds(),
            timestamp=datetime.now()
        )
        context.results[6] = res
        return res

    async def _save_phase_output(self, context: PipelineContext, phase_num: int):
        """Save individual phase output to disk."""
        try:
            # Use relative path from project root
            # This file is in src/preprocessing_pipeline/phase_7_orchestration
            # Resolve project root (E:\GL_AI)
            project_root = Path(__file__).parent.parent.parent.parent.parent
            
            # REDIRECTED PATH FOR NEW DOCUMENTS: e:\GL_AI\data_processed\new_documents\{DOC_ID}\phase_{N}\
            doc_dir = project_root / "data_processed" / "new_documents" / context.document_id
            
            # Create phase folder e.g. phase_1
            phase_folder_name = f"phase_{phase_num}"
            phase_dir = doc_dir / phase_folder_name
            phase_dir.mkdir(parents=True, exist_ok=True)
            
            print(f"DEBUG: Saving to {phase_dir}")
            
            phase_names = {
                0: "foundation",
                1: "extraction",
                2: "restoration",
                3: "linguistic_alignment", 
                4: "legal_extraction",
                5: "authority_reasoning",
                6: "graph_construction",
                7: "orchestration"
            }
            phase_name = phase_names.get(phase_num, "unknown")
            # Standardized filename: phase_{N}_{N}_{name}.json
            filename = f"phase_{phase_num}_{phase_num}_{phase_name}.json"
            file_path = phase_dir / filename
            
            result = context.results.get(phase_num)
            if not result:
                return

            def json_serial(obj):
                if isinstance(obj, (datetime, Path)):
                    return str(obj)
                if dataclasses.is_dataclass(obj):
                    return dataclasses.asdict(obj)
                try:
                    return str(obj)
                except:
                    return "<unserializable>"

            output_data = {
                "document_id": context.document_id,
                "phase": phase_num,
                "timestamp": str(result.timestamp),
                "data": result.data
            }
            
            import json
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, default=json_serial, indent=2, ensure_ascii=False)
                
            logger.info(f"Saved Phase {phase_num} output to {file_path}")
            
        except Exception as e:
            logger.error(f"Failed to save phase {phase_num} output: {e}")

if __name__ == "__main__":
    import argparse
    import asyncio
    
    async def main_cli():
        parser = argparse.ArgumentParser(description="GreenLawAI Batch Processor CLI")
        parser.add_argument("--input-dir", help="Directory containing documents to process")
        parser.add_argument("--input-file", help="Single document file to process")
        parser.add_argument("--debug", action="store_true", help="Enable debug logging")
        parser.add_argument("--start-phase", type=int, default=1, help="Phase to start from")
        parser.add_argument("--end-phase", type=int, default=7, help="Phase to end at")
        parser.add_argument("--skip-existing", action="store_true", help="Skip documents that already have processed output")
        parser.add_argument("--phases", type=str, help="Comma-separated list of phases to run (e.g. 0,1,2,3,4,5,6,7)")
        parser.add_argument("--run-all", action="store_true", help="Run full pipeline (Phase 0-7) on default raw data directory")
        
        args = parser.parse_args()

        if args.debug:
            logging.getLogger().setLevel(logging.DEBUG)

        input_dir = args.input_dir
        input_file = args.input_file
        start_phase = args.start_phase
        end_phase = args.end_phase
        
        if args.run_all:
            input_dir = "E:\\GL_AI\\data_raw"
            start_phase = 0
            end_phase = 7
            print(f"Running full pipeline on {input_dir} (Phases {start_phase}-{end_phase})")
        
        if not input_dir and not input_file:
            parser.error("--input-dir or --input-file is required unless --run-all is specified.")
            
        # Load config
        from preprocessing_pipeline.common.config import load_config
        config = load_config()
        
        # Initialize orchestrator
        orchestrator = KPKPipelineOrchestrator(config)

        files = []
        if input_file:
            single = Path(input_file)
            if not single.exists():
                print(f"Error: Input file {input_file} does not exist.")
                return
            files = [single]
            print(f"Processing single file: {single}")
        else:
            input_path = Path(input_dir)
            if not input_path.exists():
                print(f"Error: Input directory {input_dir} does not exist.")
                return
            for ext in [".pdf", ".json", ".csv", ".xlsx", ".txt", ".doc", ".docx"]:
                files.extend(list(input_path.rglob(f"*{ext}")))
            print(f"Found {len(files)} files in {input_dir}")
        
        # Optional: filter by phases if requested
        # (This would need more complex DAG logic, but for now we rely on DAG skipping)
        
        for i, file in enumerate(files):
            print(f"[{i+1}/{len(files)}] Processing: {file.name}")
            try:
                # Use DAG by default for resilience
                await orchestrator.process_document(file, use_dag=True)
            except Exception as e:
                print(f"Failed to process {file.name}: {e}")

    try:
        asyncio.run(main_cli())
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
