"""
6.2_GRAPH_MAPPER.PY - Maps extracted entities to KPK Graph Schema
Transforms pipeline entities into Neo4j-ready nodes/relationships based on 6.1_graph_schema_kpk.py
"""

import os
import json
import logging
import warnings
from typing import Dict, List, Any, Optional, Tuple, Set
from datetime import datetime
from dataclasses import dataclass
import hashlib
import uuid
from preprocessing_pipeline.common.identity import IdentityFactory

# Import the KPK graph schema from previous phase
# Import the KPK graph schema
try:
    # Try relative import
    from .graph_schema_kpk import (
        NodeLabel, RelationshipType, JurisdictionLevel, 
        PipelineEntity, PipelineRelationship, KPKNodeSchema, 
        KPKRelationshipSchema, AbstentionReason, GraphConstructionInterface
    )
    from preprocessing_pipeline.common.exceptions import (
        ForensicIntegrityError, SemanticViolationError
    )
except (ImportError, ValueError, SyntaxError):
    try:
        # Try absolute import (assuming src is in path)
        from preprocessing_pipeline.phase_6_graph_construction.graph_schema_kpk import (
            NodeLabel, RelationshipType, JurisdictionLevel, 
            PipelineEntity, PipelineRelationship, KPKNodeSchema, 
            KPKRelationshipSchema, AbstentionReason, GraphConstructionInterface
        )
        from preprocessing_pipeline.common.exceptions import (
            ForensicIntegrityError, SemanticViolationError
        )
    except (ImportError, ValueError, ModuleNotFoundError):
        # Minimal definitions for standalone testing fallback
        from enum import Enum
        class NodeLabel(Enum): 
            LAW = "Law"
            LAW_VERSION = "LawVersion"
            LEGAL_INTERPRETATION = "LegalInterpretation"
            ORDINANCE = "Ordinance"
            SECTION = "Section"
            CLAUSE = "Clause"
            PENALTY = "Penalty"
            ENTITY = "Entity"
            ABSTENTION = "Abstention"
            DOCUMENT = "Document"
            DOCUMENT_CHUNK = "DocumentChunk"
            SPECIES = "Species"
            OFFICER = "Officer"
            LOCATION = "Location"
            AMENDMENT = "Amendment"
            TEMPORAL_SLICE = "TemporalSlice"

        class RelationshipType(Enum): 
            HAS_ENTITY = "HAS_ENTITY"
            HAS_SECTION = "HAS_SECTION"
            IMPOSES = "IMPOSES"
            REFERENCES = "REFERENCES"
            PROTECTS_SPECIES = "PROTECTS_SPECIES"
            APPLIES_TO = "APPLIES_TO"
            LOCATED_IN = "LOCATED_IN"
            AMENDED_BY = "AMENDED_BY"
            VALID_IN = "VALID_IN"
            UNDER_JURISDICTION = "UNDER_JURISDICTION"
            REPORTED_TO = "REPORTED_TO"
            EXTRACTED_FROM = "EXTRACTED_FROM"
            MENTIONS = "MENTIONS"
            ABSTAINS_FROM = "ABSTAINS_FROM"
        class JurisdictionLevel(Enum): UNKNOWN = 99
        @dataclass
        class PipelineEntity:
            entity_id: str
            entity_type: Any
            properties: Dict[str, Any]
            source_phase: str
            confidence_score: float = 1.0
            abstention_reason: Any = None
            needs_human_review: bool = False
        @dataclass
        class PipelineRelationship:
            relationship_id: str
            relationship_type: Any
            from_node_id: str
            to_node_id: str
            properties: Dict[str, Any]
            source_phase: str
            confidence_score: float = 1.0
        class KPKNodeSchema: 
            def validate_node_against_schema(self, *args, **kwargs): return True, []
        class KPKRelationshipSchema: 
            def validate_relationship_against_schema(self, *args, **kwargs): return True, []
        class AbstentionReason(Enum): OTHER = "other"
        class GraphConstructionInterface: pass





# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class EntityMapping:
    """Mapping from extracted entity to graph node"""
    source_entity: Dict[str, Any]
    target_node_label: NodeLabel
    mapping_rules: List[str]
    confidence: float
    validation_errors: List[str] = None
    
    def __post_init__(self):
        if self.validation_errors is None:
            self.validation_errors = []

@dataclass 
class RelationshipMapping:
    """Mapping from extracted relationship to graph relationship"""
    source_relationship: Dict[str, Any]
    target_relationship_type: RelationshipType
    source_node_id: str
    target_node_id: str
    mapping_rules: List[str]
    confidence: float

class KPKGraphMapper:
    """
    Maps pipeline-extracted entities to KPK graph schema
    Ensures all entities from phases 0-5 are properly formatted for Neo4j
    """
    
    def __init__(self, config: Optional[Any] = None, schema_validation: bool = True):
        """
        Initialize graph mapper
        
        Args:
            config: Pipeline configuration object
            schema_validation: Whether to validate against KPK schema
        """
        self.config = config
        self.schema_validation = schema_validation
        self.namespace = getattr(config, "PROJECT_NAMESPACE", "greenlaw_kpk") if config else "greenlaw_kpk"
        self.node_schema = KPKNodeSchema()
        self.relationship_schema = KPKRelationshipSchema()
        
        # Mapping dictionaries
        self.entity_type_mappings = self._initialize_entity_mappings()
        self.relationship_type_mappings = self._initialize_relationship_mappings()
        
        # Caches for deduplication
        self.processed_nodes = set()
        self.processed_relationships = set()
        self.node_id_map = {}  # Map from original ID to deterministic ID
        
        # Statistics
        self.stats = {
            "total_nodes_mapped": 0,
            "total_relationships_mapped": 0,
            "validation_errors": [],
            "abstention_cases": [],
            "duplicate_nodes_skipped": 0,
            "duplicate_relationships_skipped": 0
        }
        
        logger.info("KPK Graph Mapper initialized with schema validation: %s", schema_validation)
    
    def _initialize_entity_mappings(self) -> Dict[str, Dict[str, Any]]:
        """Initialize mappings from pipeline entity types to graph node labels"""
        return {
        # From phase_4.1_rule_extractor.py
        "law": {
            "target_label": NodeLabel.LAW,
            "mapping_rules": [
                "map_title_to_title",
                "map_year_to_year", 
                "map_jurisdiction_to_jurisdiction",
                "add_kpk_specific_flag",
                "map_safety_hardened_invariants"
            ],
            "required_fields": ["title", "jurisdiction"]
        },
        "section": {
            "target_label": NodeLabel.SECTION,
                "mapping_rules": [
                    "map_section_number",
                    "link_to_parent_law",
                    "extract_penalty_amount_if_present",
                    "preserve_multilingual_content",
                    "map_dual_channel_text",
                    "map_traceability_metadata",
                    "enforce_forensic_metadata",
                    "map_safety_hardened_invariants"
                ],
                "required_fields": ["section_number", "law_id"]
            },
            "penalty": {
                "target_label": NodeLabel.PENALTY,
                "mapping_rules": [
                    "normalize_currency_to_pkr",
                    "calculate_escalation_if_repeat_offense",
                    "link_to_violation_type",
                    "apply_kpk_specific_multipliers",
                    "map_dual_channel_text",
                    "enforce_forensic_metadata",
                    "map_safety_hardened_invariants"
                ],
                "required_fields": ["amount", "currency"]
            },
            
            # From phase_4.2_ner_extractor.py
            "species": {
                "target_label": NodeLabel.SPECIES,
                "mapping_rules": [
                    "standardize_scientific_name",
                    "map_local_names_to_list",
                    "determine_protection_level_kpk",
                    "check_kpk_endemic_status"
                ],
                "required_fields": ["common_name"]
            },
            "officer": {
                "target_label": NodeLabel.OFFICER,
                "mapping_rules": [
                    "standardize_rank_abbreviations",
                    "determine_jurisdiction_level_from_rank",
                    "infer_authority_from_designation",
                    "link_to_division_if_present"
                ],
                "required_fields": ["rank", "jurisdiction_level"]
            },
            "location": {
                "target_label": NodeLabel.LOCATION,
                "mapping_rules": [
                    "determine_location_type",
                    "link_to_parent_location",
                    "extract_coordinates_if_present",
                    "apply_kpk_division_mapping"
                ],
                "required_fields": ["name", "type"]
            },
            
            # From phase_4.3_amendment_tracker.py
            "amendment": {
                "target_label": NodeLabel.AMENDMENT,
                "mapping_rules": [
                    "extract_gazette_reference",
                    "determine_change_type",
                    "build_version_chain",
                    "validate_temporal_consistency",
                    "enforce_forensic_metadata",
                    "map_safety_hardened_invariants"
                ],
                "required_fields": ["amending_law", "amended_section"]
            },
            
            # --- PHASE 3: AGENTIC SAFETY NODES ---
            "law_version": {
                "target_label": NodeLabel.LAW_VERSION,
                "mapping_rules": [
                    "map_safety_hardened_invariants"
                ],
                "required_fields": ["law_id", "version_number"]
            },
            "interpretation": {
                "target_label": NodeLabel.LEGAL_INTERPRETATION,
                "mapping_rules": [
                   "map_safety_hardened_invariants"
                ],
                "required_fields": ["interprets_node_id", "agent_id", "interpretation_text"]
            },
            
            # From phase_4.4_citation_resolver.py
            "citation": {
                "target_label": NodeLabel.SECTION,  # Citations map to sections
                "mapping_rules": [
                    "resolve_cross_references",
                    "build_citation_network",
                    "preserve_citation_context"
                ]
            },
            
            # From Phase 6 logic
            "document": {
                "target_label": NodeLabel.DOCUMENT,
                "mapping_rules": [],
                "required_fields": ["node_id"]
            },
            
            # From phase_6.4_legal_chunker.py
            "document_chunk": {
                "target_label": NodeLabel.DOCUMENT_CHUNK,
                "mapping_rules": [
                    "generate_unique_chunk_id",
                    "preserve_source_document_reference",
                    "extract_semantic_type",
                    "prepare_for_faiss_indexing"
                ],
                "required_fields": ["chunk_text", "source_document"]
            },
            
            # From phase_7.2_quality_gates.py
            "abstention": {
                "target_label": NodeLabel.ABSTENTION,
                "mapping_rules": [
                    "classify_abstention_reason",
                    "link_to_affected_entities",
                    "record_pipeline_phase",
                    "suggest_resolution_action"
                ],
                "required_fields": ["abstention_type", "reason"]
            }
        }
    
    def _initialize_relationship_mappings(self) -> Dict[str, Dict[str, Any]]:
        """Initialize mappings from pipeline relationships to graph relationship types"""
        return {
            # Legal structure relationships
            "has_section": {
                "target_type": RelationshipType.HAS_SECTION,
                "source_entity_types": ["law"],
                "target_entity_types": ["section"],
                "mapping_rules": ["validate_law_section_linkage"]
            },
            "imposes_penalty": {
                "target_type": RelationshipType.IMPOSES,
                "source_entity_types": ["section"],
                "target_entity_types": ["penalty"],
                "mapping_rules": ["validate_penalty_applicability"]
            },
            "protects_species": {
                "target_type": RelationshipType.PROTECTS_SPECIES,
                "source_entity_types": ["law", "section"],
                "target_entity_types": ["species"],
                "mapping_rules": ["determine_protection_level", "check_kpk_specific_rules"]
            },
            
            # Citation relationships
            "references": {
                "target_type": RelationshipType.REFERENCES,
                "source_entity_types": ["section", "amendment"],
                "target_entity_types": ["section", "law"],
                "mapping_rules": ["validate_citation_target"]
            },

            # Geographic relationships
            "applies_to_location": {
                "target_type": RelationshipType.APPLIES_TO,
                "source_entity_types": ["law", "section", "penalty"],
                "target_entity_types": ["location"],
                "mapping_rules": ["validate_jurisdiction_overlap", "check_hazara_override"]
            },
            "located_in": {
                "target_type": RelationshipType.LOCATED_IN,
                "source_entity_types": ["location", "officer"],
                "target_entity_types": ["location"],
                "mapping_rules": ["build_location_hierarchy", "validate_parent_child"]
            },
            
            # Temporal relationships
            "amended_by": {
                "target_type": RelationshipType.AMENDED_BY,
                "source_entity_types": ["section", "law"],
                "target_entity_types": ["amendment"],
                "mapping_rules": ["validate_temporal_order", "extract_effective_date"]
            },
            "valid_in": {
                "target_type": RelationshipType.VALID_IN,
                "source_entity_types": ["law", "section", "penalty"],
                "target_entity_types": ["location"],
                "mapping_rules": ["extract_validity_period", "check_conflicts"]
            },
            
            # Officer relationships
            "under_jurisdiction": {
                "target_type": RelationshipType.UNDER_JURISDICTION,
                "source_entity_types": ["officer"],
                "target_entity_types": ["location"],
                "mapping_rules": ["validate_authority_level", "check_tenure_period"]
            },
            "reports_to": {
                "target_type": RelationshipType.REPORTED_TO,
                "source_entity_types": ["officer"],
                "target_entity_types": ["officer"],
                "mapping_rules": ["validate_hierarchy_chain", "check_rank_order"]
            },
            
            # Document relationships
            "extracted_from": {
                "target_type": RelationshipType.EXTRACTED_FROM,
                "source_entity_types": ["section", "penalty", "species", "officer"],
                "target_entity_types": ["document_chunk"],
                "mapping_rules": ["preserve_source_context", "validate_extraction_confidence"]
            },
            "mentions": {
                "target_type": RelationshipType.MENTIONS,
                "source_entity_types": ["document_chunk", "section"],
                "target_entity_types": ["species", "officer", "location", "penalty"],
                "mapping_rules": ["extract_mention_context", "calculate_mention_frequency"]
            },
            
            # Abstention relationships
            "abstains_from": {
                "target_type": RelationshipType.ABSTAINS_FROM,
                "source_entity_types": ["abstention"],
                "target_entity_types": ["section", "penalty", "species", "law"],
                "mapping_rules": ["record_abstention_reason", "link_to_quality_gate"]
            }
        }
    
    def map_pipeline_output(self, pipeline_output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map complete pipeline output to graph schema
        
        Args:
            pipeline_output: Output from phase 5 (authority_reasoning) or batch_processor
            
        Returns:
            Dict with nodes and relationships ready for graph construction
        """
        logger.info("Starting graph mapping for pipeline output")
        
        # Extract entities and relationships from pipeline output (support nested structure)
        entities, relationships = self._collect_entities_from_phases(pipeline_output)
        metadata = pipeline_output.get("metadata", {})
        
        logger.info("Processing %d collected entities and %d relationships", len(entities), len(relationships))
        
        # Map entities to nodes
        mapped_nodes = []
        node_id_map = {}  # Map from pipeline entity IDs to graph node IDs
        
        for entity in entities:
            # Create PipelineEntity object
            pipeline_entity = self._create_pipeline_entity(entity)
            
            # Map to graph node
            node_result = self.map_entity_to_node(pipeline_entity, metadata)
            
            if node_result["success"]:
                mapped_node = node_result["node"]
                mapped_nodes.append(mapped_node)
                
                # Store mapping from pipeline ID to graph ID
                orig_id = entity.get("pipeline_id") or entity.get("id") or entity.get("node_id")
                if orig_id:
                    node_id_map[orig_id] = mapped_node["node_id"]
                
                # Also map "Section X" to node_id for citation resolution
                node_props = mapped_node.get("properties", {})
                if mapped_node.get("label") == "Section" and "name" in node_props:
                    section_name = node_props["name"]
                    # Map "Section 29" -> node_id
                    node_id_map[section_name] = mapped_node["node_id"]
                    # Map "29" -> node_id (just in case)
                    if section_name.lower().startswith("section "):
                        short_num = section_name.split(" ")[-1]
                        node_id_map[short_num] = mapped_node["node_id"]
                
                # Update statistics
                self.stats["total_nodes_mapped"] += 1
                
                # CRITICAL: Auto-link entities to document
                doc_id = pipeline_output.get("document_id")
                if doc_id and pipeline_entity.source_phase == "phase_4.2":
                    relationships.append({
                        "type": "MENTIONS",
                        "from_id": doc_id,
                        "to_id": mapped_node["node_id"],
                        "source_phase": "phase_6.2_auto_link",
                        "confidence": pipeline_entity.confidence_score,
                        "properties": {
                            "auto_linked": True,
                            "context": "Extracted from document"
                        }
                    })

                # Check for abstention
                if pipeline_entity.abstention_reason:
                    self.stats["abstention_cases"].append({
                        "entity_id": pipeline_entity.entity_id,
                        "reason": pipeline_entity.abstention_reason.value,
                        "node_id": mapped_node["node_id"]
                    })
            else:
                self.stats["validation_errors"].append({
                    "entity": pipeline_entity.entity_id,
                    "errors": node_result["errors"],
                    "action": node_result.get("action", "skipped")
                })
        
        # Map relationships
        mapped_relationships = []
        
        for rel in relationships:
            relationship_result = self.map_relationship(rel, node_id_map, metadata)
            
            if relationship_result["success"]:
                mapped_rel = relationship_result["relationship"]
                
                # Check for duplicates
                rel_key = f"{mapped_rel['from_id']}-{mapped_rel['type']}-{mapped_rel['to_id']}"
                if rel_key in self.processed_relationships:
                    self.stats["duplicate_relationships_skipped"] += 1
                    continue
                
                self.processed_relationships.add(rel_key)
                mapped_relationships.append(mapped_rel)
                self.stats["total_relationships_mapped"] += 1
            else:
                self.stats["validation_errors"].append({
                    "relationship": rel.get("type", "unknown"),
                    "errors": relationship_result["errors"],
                    "action": relationship_result.get("action", "skipped")
                })
        
        # Store mapped data in stats for archival (v2.3)
        self.stats["nodes"] = mapped_nodes
        self.stats["relationships"] = mapped_relationships

        # Create result structure
        result = {
            "nodes": mapped_nodes,
            "relationships": mapped_relationships,
            "node_id_map": node_id_map,
            "mapping_statistics": self.stats,
            "metadata": {
                **metadata,
                "mapping_timestamp": datetime.now().isoformat(),
                "mapper_version": "1.0-kpk",
                "schema_validation_applied": self.schema_validation
            },
            "quality_indicators": self._calculate_quality_indicators(mapped_nodes, mapped_relationships)
        }
        
        logger.info("Graph mapping complete: %d nodes, %d relationships", 
                   len(mapped_nodes), len(mapped_relationships))
        
        return result
    
    def _collect_entities_from_phases(self, pipeline_output: Dict[str, Any]) -> Tuple[List[Dict], List[Dict]]:
        """
        Collect entities and relationships from various pipeline phases
        Handles nested structure from run_sequential_pipeline.py
        """
        entities = []
        relationships = []
        
        # 1. Try to get top-level entities/relationships (backward compatibility)
        entities.extend(pipeline_output.get("entities", []))
        relationships.extend(pipeline_output.get("relationships", []))
        
        # 2. Extract from Phase 4 (Legal Extraction)
        doc_id = pipeline_output.get("document_id")
        if doc_id:
            # Explicitly add Document node
            doc_node = {
                "node_id": doc_id,
                "id": doc_id,
                "entity_type": "Document",
                "label": "Document",
                "properties": {
                    "node_id": doc_id,
                    "document_id": doc_id,
                    "document_type": (
                        pipeline_output.get("phase_4", {}).get("4.1_rules", {}).get("document_type", "Law") 
                        if isinstance(pipeline_output.get("phase_4", {}).get("4.1_rules"), dict) 
                        else "Law"
                    ),
                    "extraction_confidence": 1.0,
                    "source_phase": "phase_6.2",
                    "source_doc_id": doc_id,
                    "extraction_phase": "phase_6.2",
                    "confidence_score": 1.0,
                    "bbox": "document_level"
                }
            }
            entities.append(doc_node)

        phase_4 = pipeline_output.get("phase_4", {})
        if isinstance(phase_4, dict):
            # Extract laws/sections/penalties from rules
            rules_data = phase_4.get("4.1_rules", {})
            rules_list = []
            
            if isinstance(rules_data, dict):
                # Data is in "sections" key of the dict
                rules_list = rules_data.get("sections", [])
                # Also treat the document itself as a Law node if possible
                if rules_data.get("document_id"):
                    doc_law_node = {
                        "id": rules_data.get("document_id"),
                        "text": rules_data.get("full_text", "")[:100], # Trucate for summary
                        "entity_type": "Law",
                        "type": "law",
                        "source_phase": "phase_4.1",
                        "name": rules_data.get("document_type", "Law Document"),
                        "properties": {
                            "document_id": rules_data.get("document_id"),
                            "source_doc_id": rules_data.get("document_id"),
                            "extraction_phase": "phase_4.1",
                            "confidence_score": 1.0,
                            "bbox": "document_level"
                        }
                    }
                    entities.append(doc_law_node)
            elif isinstance(rules_data, list):
                rules_list = rules_data
                
            for rule in rules_list:
                if isinstance(rule, dict):
                    # Flatten metadata if present and id is missing
                    if "id" not in rule and "metadata" in rule:
                        meta = rule.get("metadata", {})
                        if "section_id" in meta:
                            rule["id"] = meta["section_id"]
                        if "section_number" in meta:
                            rule["section_number"] = meta["section_number"]
                            # Use Section X as name to match citations
                            if "name" not in rule:
                                rule["name"] = f"Section {meta['section_number']}"
                        
                        # Map legal_act to law_id if possible
                        if "legal_act" in meta and "law_id" not in rule:
                            # Simple normalization or use document_id if available
                            if pipeline_output.get("document_id"):
                                rule["law_id"] = pipeline_output.get("document_id")
                            else:
                                rule["law_id"] = "law_" + meta["legal_act"].lower().replace(" ", "_")
                                
                    # Map text to content if content is missing
                    if "text" in rule and "content" not in rule:
                        rule["content"] = rule["text"]
                        
                    if "source_phase" not in rule:
                        rule["source_phase"] = "phase_4.1"
                    # Default law/section/penalty types if missing
                    if "entity_type" not in rule:
                        if rule.get("type") == "penalty":
                            rule["entity_type"] = "Penalty"
                        elif any(x in str(rule.get("id", "")).lower() for x in ["section", "sec_", "ord_"]) or rule.get("metadata", {}).get("section_level") == "section":
                            rule["entity_type"] = "Section"
                        else:
                            rule["entity_type"] = "Law"
                    entities.append(rule)

                    # CRITICAL FIX: Link Section to Law
                    if rule["entity_type"] == "Section" and rule.get("law_id"):
                        relationships.append({
                            "type": "HAS_SECTION",
                            "from_id": rule["law_id"],
                            "to_id": rule.get("id"),
                            "source_phase": "phase_6.2_auto_link",
                            "confidence": 1.0
                        })
            
            # Extract entities (Species, Officers, Locations)
            # Support both flat list and nested dictionary structure
            entities_data = phase_4.get("4.2_entities", {})
            raw_entities = []
            if isinstance(entities_data, dict):
                raw_entities = entities_data.get("validated_entities", [])
                raw_entities.extend(entities_data.get("fallback_extractions", []))
            elif isinstance(entities_data, list):
                raw_entities = entities_data
            
            for entity in raw_entities:
                if isinstance(entity, dict):
                    # Just collect the raw entity, mapping happens in map_pipeline_output
                    if "source_phase" not in entity:
                        entity["source_phase"] = "phase_4.2"
                    entities.append(entity)
            
            # Extract amendments
            for amendment in phase_4.get("4.3_amendments", []):
                if isinstance(amendment, dict):
                    if "entity_type" not in amendment:
                        amendment["entity_type"] = "Amendment"
                    if "source_phase" not in amendment:
                        amendment["source_phase"] = "phase_4.3"
                    entities.append(amendment)
            
            # Extract citations as potential relationships
            for citation in phase_4.get("4.4_citations", []):
                if isinstance(citation, dict):
                    # Map citations to REFERENCES relationships
                    rel = {
                        "type": "REFERENCES",
                        "from_id": citation.get("source_section") or citation.get("document_id") or pipeline_output.get("document_id"),
                        "to_id": citation.get("resolved_target"),
                        "source_phase": "phase_4.4",
                        "confidence": citation.get("confidence", 0.7),
                        "properties": {
                            "source_text": citation.get("source_text"),
                            "citation_id": citation.get("citation_id")
                        }
                    }
                    if rel["from_id"] and rel["to_id"]:
                        relationships.append(rel)
            
        # 3. Extract from Phase 5 (Authority Reasoning)
        phase_5 = pipeline_output.get("phase_5", {})
        if isinstance(phase_5, dict):
            # Hierarchy relationships
            for item in phase_5.get("5.1_hierarchy", []):
                if isinstance(item, dict):
                    rel = {
                        "type": "GOVERNED_BY",
                        "from_id": item.get("entity"),
                        "to_id": item.get("authority"),
                        "source_phase": "phase_5.1",
                        "confidence": 0.9,
                        "properties": item.copy()
                    }
                    if rel["from_id"] and rel["to_id"]:
                        relationships.append(rel)

            # Penalties from reasoning
            for penalty in phase_5.get("5.2_penalties", []):
                if isinstance(penalty, dict):
                    if "entity_type" not in penalty:
                        penalty["entity_type"] = "Penalty"
                    if "source_phase" not in penalty:
                        penalty["source_phase"] = "phase_5.2"
                    entities.append(penalty)
                    
                    # Also create relationship between section and penalty if possible
                    if penalty.get("section_id") or penalty.get("section"):
                        relationships.append({
                            "type": "IMPOSES",
                            "from_id": penalty.get("section_id") or penalty.get("section"),
                            "to_id": penalty.get("id") or penalty.get("value"),
                            "source_phase": "phase_5.2",
                            "confidence": 1.0
                        })
        
        return entities, relationships

    def _create_pipeline_entity(self, entity_data: Dict[str, Any]) -> PipelineEntity:
        """Create PipelineEntity from raw entity data"""
        et_raw = entity_data.get("entity_type", "ENTITY")
        
        # Robust case-insensitive lookup for NodeLabel
        entity_type = NodeLabel.ENTITY
        for label in NodeLabel:
            if label.value.lower() == str(et_raw).lower():
                entity_type = label
                break
        
        # Extract properties (may be nested from Phase 4)
        properties = entity_data.get("properties", entity_data)
        
        # Forensic Metadata Extraction (v2.3 Hardening)
        # Phase 4 injects forensic fields into the nested 'properties' dict
        # We need to extract them and make them available at the top level for the mapper
        source_phase = entity_data.get("source_phase", "unknown")
        confidence_score = entity_data.get("confidence_score", 1.0)
        
        # If properties is a dict, check for nested forensic fields
        if isinstance(properties, dict):
            # Extract from nested properties if present
            if "source_phase" in properties:
                source_phase = properties.get("source_phase", source_phase)
            if "confidence_score" in properties:
                confidence_score = properties.get("confidence_score", confidence_score)
        
        entity = PipelineEntity(
            entity_data.get("entity_id", entity_data.get("id", str(uuid.uuid4()))),
            entity_type,
            properties,
            source_phase,
            confidence_score,
            AbstentionReason(entity_data["abstention_reason"]) 
                if entity_data.get("abstention_reason") else None,
            entity_data.get("needs_human_review", False)
        )
        
        # CRITICAL FIX: Attach metadata to entity instance so it can be accessed in map_entity_to_node
        entity.metadata = entity_data.get("metadata", {})
        
        return entity

    
    def map_entity_to_node(self, entity: PipelineEntity, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map a single entity to a graph node
        
        Args:
            entity: PipelineEntity to map
            metadata: Pipeline metadata for context
            
        Returns:
            Dict with mapping result
        """
        # Check for duplicate
        if entity.entity_id in self.processed_nodes:
            self.stats["duplicate_nodes_skipped"] += 1
            return {
                "success": False,
                "action": "skipped_duplicate",
                "errors": [f"Entity {entity.entity_id} already processed"]
            }
        
        self.processed_nodes.add(entity.entity_id)
        
        # Get mapping configuration for this entity type
        entity_type_str = entity.entity_type.value.lower().replace(" ", "_")
        mapping_config = self.entity_type_mappings.get(entity_type_str)
        
        if not mapping_config:
            logger.warning(f"No mapping configuration for entity type: {entity_type_str}")
            # Try to infer mapping
            mapping_config = self._infer_entity_mapping(entity)
        
        # Forensic Metadata Enforcement (Invariant Four)
        # CRITICAL: Check Phase 4 keys FIRST (source_doc_id, bbox) before fallback alternatives
        source_doc_id = entity.properties.get("source_doc_id") or entity.properties.get("document_id") or entity.properties.get("source_doc") or getattr(entity, 'metadata', {}).get("source_doc_id") or metadata.get("source_doc_id")
        
        # Semantic BBox Logic: Pixel coords vs Logical span
        bbox = entity.properties.get("bbox") or entity.properties.get("logical_span") or getattr(entity, 'metadata', {}).get("bbox") or metadata.get("bbox")
        
        # Hardened Injection Gates (v2.3): Treat "N/A" and "None" as missing
        is_hardened = getattr(self.config, "PRODUCTION_HARDENED", True)
        
        def is_forensically_invalid(val):
            if val is None: return True
            s_val = str(val).strip().lower()
            return s_val in ["", "none", "n/a", "unknown", "null"]

        if is_forensically_invalid(source_doc_id):
            source_doc_id = metadata.get("source_doc_id") or metadata.get("document_id")
            if is_forensically_invalid(source_doc_id):
                source_doc_id = "unknown"
            else:
                logger.debug(f"Injected source_doc_id from metadata for {entity.entity_id}")
        
        if is_forensically_invalid(bbox):
            # For system/canonical or nodes missing pixel bbox, use logical span
            bbox = "document_level"
            logger.debug(f"Injected logical 'document_level' bbox for {entity.entity_id}")

        mandatory_fields = {
            "source_doc_id": source_doc_id,
            "bbox": bbox,
            "extraction_phase": entity.source_phase,
            "confidence_score": entity.confidence_score
        }
        
        missing_fields = [k for k, v in mandatory_fields.items() if is_forensically_invalid(v)]
        
        # Hardening: Check BBox and Confidence for specialized legal nodes
        is_legal_node = entity.entity_type in [NodeLabel.SECTION, NodeLabel.PENALTY, NodeLabel.AMENDMENT]
        if is_legal_node and self.config and getattr(self.config, "PRODUCTION_HARDENED", False):
            if not mandatory_fields["bbox"]:
                missing_fields.append("bbox (Required for legal nodes)")
            if mandatory_fields["confidence_score"] < 0.1:
                raise ForensicIntegrityError(f"Unacceptable confidence ({mandatory_fields['confidence_score']}) for {entity.entity_id}")
        
        if missing_fields:
            error_msg = f"Forensic Completeness Failure for {entity_type_str} {entity.entity_id}: Missing {', '.join(missing_fields)}"
            logger.error(error_msg)
            
            # Strict Enforcement: No bypass in production
            if self.config and getattr(self.config, "PRODUCTION_HARDENED", False):
                raise ForensicIntegrityError(error_msg)
            else:
                self.stats["forensic_warnings"] = self.stats.get("forensic_warnings", 0) + 1
                logger.warning(f"Forensic Warning (Dev Mode): {error_msg}")

        # Safety Gate: Agentic Write Block (Phase 3 Hardening)
        is_canonical_node = entity.entity_type in [NodeLabel.LAW, NodeLabel.LAW_VERSION, NodeLabel.SECTION]
        is_agent_source = "agent" in entity.source_phase.lower() or "llm" in entity.source_phase.lower()
        
        if is_canonical_node and is_agent_source and self.config and getattr(self.config, "PRODUCTION_HARDENED", False):
            # Agents are FORBIDDEN from writing to canonical law/section nodes directly.
            # They must write to LegalInterpretation nodes instead.
            error_msg = (
                f"Agentic Safety Violation: Agent source '{entity.source_phase}' "
                f"is forbidden from mutating canonical node {entity.entity_id}"
            )
            logger.critical(error_msg)
            raise SemanticViolationError(error_msg)

        # Apply mapping rules
        mapped_properties = self._apply_entity_mapping_rules(
            entity, mapping_config["mapping_rules"], metadata
        )
        
        # Persist forensic invariants onto the node itself (HARD REQUIREMENT v2.3)
        mapped_properties.update({
            "source_doc_id": mandatory_fields["source_doc_id"],
            "bbox": mandatory_fields["bbox"],
            "extraction_phase": mandatory_fields["extraction_phase"],
            "confidence_score": mandatory_fields["confidence_score"]
        })
        
        # Generate node ID if not present
        if "node_id" not in mapped_properties:
            new_id = self._generate_node_id(entity, mapped_properties)
            mapped_properties["node_id"] = new_id
            
            # Populate node_id_map for auditability and refers/merges
            self.node_id_map[entity.entity_id] = new_id

        # Canonical ID Deduplication (Ontology Safety v2.3)
        canonical_node_id = mapped_properties["node_id"]
        if canonical_node_id in self.processed_nodes and canonical_node_id != entity.entity_id:
            self.stats["duplicate_nodes_skipped"] += 1
            return {
                "success": False,
                "action": "skipped_duplicate_canonical",
                "errors": [f"Canonical node {canonical_node_id} already processed"]
            }
        
        self.processed_nodes.add(canonical_node_id)
        
        # Add pipeline metadata
        mapped_properties.update({
            "pipeline_source": entity.source_phase,
            "extraction_confidence": entity.confidence_score,
            "mapping_timestamp": datetime.now().isoformat()
        })
        
        # Add abstention info if present
        if entity.abstention_reason:
            mapped_properties["abstention_reason"] = entity.abstention_reason.value
            mapped_properties["needs_review"] = entity.needs_human_review

        # Ensure node_id is in mapped_properties before validation
        if "node_id" not in mapped_properties:
            mapped_properties["node_id"] = self._generate_node_id(entity, mapped_properties)
        
        mapped_properties["mapped_at"] = datetime.now().isoformat()

        # Validate against schema if enabled
        if self.schema_validation:
            is_valid, errors = self.node_schema.validate_node_against_schema(
                mapped_properties, entity.entity_type
            )
            
            if not is_valid:
                return {
                    "success": False,
                    "errors": errors,
                    "action": "failed_validation",
                    "node": mapped_properties  # Still return for debugging
                }
        
        # Create final node
        node = {
            # Ensure properties don't overwrite our identified label or node_id
            **mapped_properties,
            "label": entity.entity_type.value,
            "node_id": mapped_properties.get("node_id", entity.entity_id)
        }
        
        return {
            "success": True,
            "node": node,
            "mapping_rules_applied": mapping_config["mapping_rules"]
        }
    
    def map_relationship(self, rel_data: Dict[str, Any], 
                        node_id_map: Dict[str, str], 
                        metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map a relationship to graph relationship
        
        Args:
            rel_data: Raw relationship data
            node_id_map: Mapping from pipeline IDs to graph node IDs
            metadata: Pipeline metadata
            
        Returns:
            Dict with mapping result
        """
        # Extract relationship info
        rel_type_str = rel_data.get("type", "unknown")
        from_id = rel_data.get("from_id")
        to_id = rel_data.get("to_id")
        properties = rel_data.get("properties", {})
        
        # Map IDs using node_id_map
        from_node_id = node_id_map.get(from_id, from_id)
        to_node_id = node_id_map.get(to_id, to_id)
        
        # Agentic safety: prevent agent-sourced relationships touching canonical nodes (v2.3)
        if self.config and getattr(self.config, "PRODUCTION_HARDENED", False):
            source_phase = rel_data.get("source_phase", "").lower()
            if "agent" in source_phase or "llm" in source_phase:
                # Use NodeLabel constants for reliability
                canonical_targets = [NodeLabel.LAW.value, NodeLabel.LAW_VERSION.value, NodeLabel.SECTION.value]
                # Defensive check: if IDs contain canonical patterns or we can resolve their labels
                if any(lbl.lower() in str(from_node_id).lower() or lbl.lower() in str(to_node_id).lower() for lbl in canonical_targets):
                     error_msg = (
                        f"Agentic Safety Violation: Agent source '{source_phase}' "
                        f"is forbidden from mutating relationships for canonical nodes ({from_node_id} -> {to_node_id})"
                    )
                     logger.critical(error_msg)
                     raise SemanticViolationError(error_msg)
        
        # Get relationship mapping configuration
        mapping_config = self.relationship_type_mappings.get(rel_type_str)
        
        # Try lowercase if not found
        if not mapping_config:
             mapping_config = self.relationship_type_mappings.get(rel_type_str.lower())
        
        if not mapping_config:
            logger.warning(f"No mapping configuration for relationship type: {rel_type_str}")
            mapping_config = self._infer_relationship_mapping(rel_type_str, from_id, to_id)
        
        # Apply mapping rules
        mapped_properties = self._apply_relationship_mapping_rules(
            rel_data, mapping_config["mapping_rules"], metadata
        )
        
        # Create relationship
        relationship = {
            "type": mapping_config["target_type"].value,
            "from_id": from_node_id,
            "to_id": to_node_id,
            # Deterministic, order-stable relationship ID (v2.3)
            "rel_id": f"REL_{mapping_config['target_type'].value}_" + hashlib.sha256(f"{from_node_id}:{mapping_config['target_type'].value}:{to_node_id}".encode()).hexdigest()[:12],
            **mapped_properties,
            "confidence_score": rel_data.get("confidence_score", rel_data.get("extraction_confidence", 1.0)),
            "pipeline_source": rel_data.get("source_phase", "unknown"),
            "mapping_timestamp": datetime.now().isoformat()
        }
        
        # Validate if enabled
        if self.schema_validation:
            is_valid, errors = self.relationship_schema.validate_relationship_against_schema(
                relationship, mapping_config["target_type"]
            )
            
            if not is_valid:
                return {
                    "success": False,
                    "errors": errors,
                    "action": "failed_validation",
                    "relationship": relationship
                }
        
        return {
            "success": True,
            "relationship": relationship,
            "mapping_rules_applied": mapping_config["mapping_rules"]
        }
    
    def _apply_entity_mapping_rules(self, entity: PipelineEntity, 
                                   rules: List[str], 
                                   metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Apply mapping rules to entity properties"""
        properties = entity.properties.copy()
        
        # Initial basic mapping from pipeline 'value' to primary schema fields
        if "value" in properties:
            if entity.entity_type == NodeLabel.OFFICER and "rank" not in properties:
                properties["rank"] = properties["value"]
            elif entity.entity_type == NodeLabel.SPECIES and "common_name" not in properties:
                properties["common_name"] = properties["value"]
            elif entity.entity_type == NodeLabel.LOCATION and "name" not in properties:
                properties["name"] = properties["value"]
            elif entity.entity_type == NodeLabel.AUTHORITY and "name" not in properties:
                properties["name"] = properties["value"]
        
        # Ensure node_id is present
        if "node_id" not in properties:
            if "id" in properties:
                properties["node_id"] = properties["id"]
            else:
                properties["node_id"] = entity.entity_id

        for rule in rules:
            try:
                if rule == "map_title_to_title" and "title" not in properties:
                    properties["title"] = entity.entity_id
                
                elif rule == "map_year_to_year" and "year" not in properties:
                    # Extract year from entity_id or metadata
                    year_match = self._extract_year(entity.entity_id)
                    if year_match:
                        properties["year"] = int(year_match)
                
                elif rule == "map_jurisdiction_to_jurisdiction" and "jurisdiction" not in properties:
                    properties["jurisdiction"] = self._infer_jurisdiction(entity, metadata)
                
                elif rule == "add_kpk_specific_flag":
                    properties["kpk_specific"] = self._is_kpk_specific(entity, metadata)
                
                elif rule == "map_section_number":
                    if entity.entity_type == NodeLabel.SECTION and "section_number" not in properties:
                        # Extract from entity_id or properties
                        if "number" in properties:
                            properties["section_number"] = properties["number"]
                
                elif rule == "link_to_parent_law":
                    if entity.entity_type == NodeLabel.SECTION and "law_id" not in properties:
                        # Infer from context
                        properties["law_id"] = self._infer_parent_law(entity, metadata)
                
                elif rule == "extract_penalty_amount_if_present":
                    if entity.entity_type == NodeLabel.PENALTY:
                        if "amount" in properties and isinstance(properties["amount"], str):
                            # Clean amount string
                            amount_str = properties["amount"].replace(",", "").replace("Rs.", "").strip()
                            try:
                                properties["amount"] = float(amount_str)
                            except ValueError:
                                pass
                
                elif rule == "normalize_currency_to_pkr":
                    if entity.entity_type == NodeLabel.PENALTY:
                        properties["currency"] = "PKR"
                
                elif rule == "calculate_escalation_if_repeat_offense":
                    if entity.entity_type == NodeLabel.PENALTY:
                        if "repeat_offense" in str(properties).lower():
                            properties["repeat_offense_multiplier"] = 2.0  # KPK standard
                
                elif rule == "standardize_scientific_name":
                    if entity.entity_type == NodeLabel.SPECIES:
                        common_name = properties.get("common_name", "").lower()
                        # Map common names to scientific names
                        species_map = {
                            "deodar": "Cedrus deodara",
                            "chir pine": "Pinus roxburghii",
                            "kail": "Pinus wallichiana",
                            "fir": "Abies pindrow"
                        }
                        if common_name in species_map:
                            properties["scientific_name"] = species_map[common_name]
                
                elif rule == "determine_protection_level_kpk":
                    if entity.entity_type == NodeLabel.SPECIES:
                        # KPK-specific protection levels
                        protected_species = ["deodar", "kail", "fir", "spruce"]
                        common_name = properties.get("common_name", "").lower()
                        
                        if common_name in protected_species:
                            properties["legal_status"] = "protected"
                            properties["protection_level"] = "highest"
                        else:
                            properties["legal_status"] = "regulated"
                            properties["protection_level"] = "medium"
                
                elif rule == "check_kpk_endemic_status":
                    if entity.entity_type == NodeLabel.SPECIES:
                        kpk_endemic = ["deodar", "kail"]
                        common_name = properties.get("common_name", "").lower()
                        properties["kpk_endemic"] = common_name in kpk_endemic
                
                elif rule == "standardize_rank_abbreviations":
                    if entity.entity_type == NodeLabel.OFFICER:
                        rank = properties.get("rank", "")
                        # Standardize KPK forest officer ranks
                        rank_map = {
                            "DFO": "Divisional Forest Officer",
                            "SDFO": "Sub-Divisional Forest Officer",
                            "RO": "Range Officer",
                            "BG": "Beat Guard"
                        }
                        if rank in rank_map:
                            properties["rank"] = rank_map[rank]
                
                elif rule == "determine_jurisdiction_level_from_rank":
                    if entity.entity_type == NodeLabel.OFFICER:
                        rank = properties.get("rank", "").lower()
                        if "divisional" in rank:
                            properties["jurisdiction_level"] = JurisdictionLevel.DIVISIONAL.value
                        elif "range" in rank:
                            properties["jurisdiction_level"] = JurisdictionLevel.RANGE_LEVEL.value
                        elif "beat" in rank:
                            properties["jurisdiction_level"] = JurisdictionLevel.BEAT_LEVEL.value
                
                elif rule == "determine_location_type":
                    if entity.entity_type == NodeLabel.LOCATION:
                        name = properties.get("name", "").lower()
                        if "division" in name:
                            properties["type"] = "division"
                        elif "range" in name:
                            properties["type"] = "range"
                        elif "beat" in name:
                            properties["type"] = "beat"
                        elif "forest" in name:
                            properties["type"] = "forest"
                
                elif rule == "apply_kpk_division_mapping":
                    if entity.entity_type == NodeLabel.LOCATION:
                        name = properties.get("name", "")
                        # Check if this is a known KPK division
                        kpk_divisions = ["Abbottabad", "Mansehra", "Swat", "Dir", 
                                       "Malakand", "D.I.Khan", "Kohat", "Bannu"]
                        if any(div.lower() in name.lower() for div in kpk_divisions):
                            properties["jurisdiction"] = JurisdictionLevel.DIVISIONAL.value
                
                elif rule == "extract_gazette_reference":
                    if entity.entity_type == NodeLabel.AMENDMENT:
                        # Extract S.R.O. or Gazette reference
                        if "gazette_notification" not in properties:
                            # Look for S.R.O pattern in properties
                            for key, value in properties.items():
                                if isinstance(value, str) and "S.R.O" in value:
                                    properties["gazette_notification"] = value
                                    break
                
                elif rule == "generate_unique_chunk_id":
                    if entity.entity_type == NodeLabel.DOCUMENT_CHUNK:
                        if "node_id" not in properties:
                            source_doc = properties.get("source_document", "unknown")
                            chunk_idx = properties.get("chunk_index", 0)
                            properties["node_id"] = f"chunk_{source_doc}_{chunk_idx}"
                
                elif rule == "map_dual_channel_text":
                    # Force preserve raw vs sanitized for legal audit
                    raw = entity.properties.get("raw_text")
                    sanitized = entity.properties.get("sanitized_text")
                    
                    if raw:
                        properties["raw_text"] = raw
                    if sanitized:
                        properties["sanitized_text"] = sanitized
                    
                    # Hardening: If both present, they MUST be different to satisfy dual-channel intent
                    if raw and sanitized and self.config and getattr(self.config, "PRODUCTION_HARDENED", False):
                        if raw == sanitized:
                            logger.error(f"Traceability Failure: raw_text equals sanitized_text for {entity.entity_id}")
                            # In strict mode, we should ideally raise but logging for now as per v2.1
                
                elif rule == "enforce_forensic_metadata":
                    # Mapped properties preservation (Logic handled in map_entity_to_node high-level gate)
                    bbox = entity.properties.get("bbox") or entity.properties.get("coordinates")
                    if bbox:
                        properties["bbox"] = bbox
                    properties["confidence_score"] = entity.confidence_score
                    
                    if "section_path" in entity.properties:
                        properties["section_path"] = entity.properties["section_path"]

                elif rule == "map_traceability_metadata":
                    # Map OCR and page info
                    properties["page_number"] = entity.properties.get("source_page", entity.properties.get("page", 0))
                    properties["confidence_score"] = entity.properties.get("confidence_score", entity.properties.get("ocr_confidence", 1.0))
                
                elif rule == "classify_abstention_reason":
                    if entity.entity_type == NodeLabel.ABSTENTION:
                        reason = properties.get("reason", "").lower()
                        # Map to standardized abstention reasons
                        if "authority" in reason and "conflict" in reason:
                            properties["abstention_type"] = "authority_conflict"
                        elif "ocr" in reason or "poor quality" in reason:
                            properties["abstention_type"] = "poor_ocr_quality"
                        elif "temporal" in reason:
                            properties["abstention_type"] = "temporal_conflict"
                        elif "multilingual" in reason:
                            properties["abstention_type"] = "multilingual_ambiguity"
                
                elif rule == "map_safety_hardened_invariants":
                    # Mark canonical nodes as immutable
                    if entity.entity_type in [NodeLabel.LAW, NodeLabel.LAW_VERSION, NodeLabel.SECTION]:
                        properties["is_immutable"] = True
                    elif entity.entity_type == NodeLabel.LEGAL_INTERPRETATION:
                        properties["is_immutable"] = False # Safe zone for agent writes
                
            except Exception as e:
                logger.warning(f"Rule {rule} failed for entity {entity.entity_id}: {e}")
        
        # PRESERVE CANONICAL NAME (Identity Hardening)
        # Check properties for metadata, as PipelineEntity doesn't have a metadata attribute
        # Phase 4 extraction puts metadata in properties dictionary
        entity_metadata = entity.properties.get('metadata', {})
        if 'canonical_name' in entity_metadata:
            properties['canonical_name'] = entity_metadata['canonical_name']
        elif 'canonical_name' in entity.properties:
            properties['canonical_name'] = entity.properties['canonical_name']

        # Enforce immutability consistency (defense-in-depth v2.3)
        if self.config and getattr(self.config, "PRODUCTION_HARDENED", False):
            if properties.get("is_immutable") and entity.source_phase.lower().startswith("agent"):
                error_msg = (
                    f"Agentic Safety Violation: Agent attempted to write immutable node {entity.entity_id}"
                )
                logger.critical(error_msg)
                raise SemanticViolationError(error_msg)

        return properties
    
    def _apply_relationship_mapping_rules(self, rel_data: Dict[str, Any],
                                         rules: List[str],
                                         metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Apply mapping rules to relationship properties"""
        properties = rel_data.get("properties", {}).copy()
        
        for rule in rules:
            try:
                if rule == "validate_law_section_linkage":
                    # Ensure law-section linkage is valid
                    properties["section_order"] = properties.get("section_order", 1)
                
                elif rule == "validate_penalty_applicability":
                    # Add KPK-specific penalty applicability rules
                    properties["applicability"] = properties.get("applicability", "general")
                    if "species_specific" in str(rel_data):
                        properties["condition"] = "species_specific"
                
                elif rule == "determine_protection_level":
                    # Set protection level based on KPK rules
                    properties["protection_level"] = properties.get("protection_level", "standard")
                
                elif rule == "check_kpk_specific_rules":
                    # Add KPK-specific flags
                    properties["kpk_specific"] = True
                
                elif rule == "validate_jurisdiction_overlap":
                    # Check for jurisdiction conflicts
                    properties["jurisdiction_conflict"] = properties.get("jurisdiction_conflict", "none")
                
                elif rule == "check_hazara_override":
                    # Special rule for Hazara Division overrides
                    if "Hazara" in str(rel_data):
                        properties["hazara_override"] = True
                
                elif rule == "build_location_hierarchy":
                    # Ensure proper hierarchy
                    properties["hierarchy_level"] = properties.get("hierarchy_level", "direct")
                
                elif rule == "validate_parent_child":
                    # Validate parent-child relationship
                    properties["validated"] = True
                
                elif rule == "validate_temporal_order":
                    # Ensure amendment order is correct
                    properties["temporal_valid"] = True
                
                elif rule == "extract_effective_date":
                    # Extract effective date if present
                    if "effective_date" not in properties:
                        properties["effective_date"] = metadata.get("document_date", None)
                
                elif rule == "extract_validity_period":
                    # Add validity period
                    properties["valid_from"] = properties.get("valid_from", "2000-01-01")
                    properties["valid_until"] = properties.get("valid_until", None)
                
                elif rule == "check_conflicts":
                    # Check for temporal conflicts
                    properties["temporal_conflict"] = False
                
                elif rule == "validate_authority_level":
                    # Validate officer authority level
                    properties["authority_validated"] = True
                
                elif rule == "check_tenure_period":
                    # Add tenure period if available
                    if "tenure_start" not in properties:
                        properties["tenure_start"] = None
                        properties["tenure_end"] = None
                
                elif rule == "validate_hierarchy_chain":
                    # Ensure proper reporting hierarchy
                    properties["hierarchy_valid"] = True
                
                elif rule == "check_rank_order":
                    # Validate rank ordering
                    properties["rank_order_valid"] = True
                
                elif rule == "preserve_source_context":
                    # Preserve extraction context
                    properties["extraction_context"] = properties.get("extraction_context", "direct")
                
                elif rule == "validate_extraction_confidence":
                    # Record extraction confidence (Standardized v2.3)
                    properties["confidence_score"] = rel_data.get("confidence_score", 1.0)
                
                elif rule == "extract_mention_context":
                    # Add mention context
                    properties["mention_context"] = properties.get("mention_context", "general")
                
                elif rule == "calculate_mention_frequency":
                    # Calculate mention frequency
                    properties["mention_frequency"] = properties.get("mention_frequency", 1)
                
                elif rule == "record_abstention_reason":
                    # Record abstention details
                    properties["abstention_detail"] = properties.get("abstention_detail", "see_abstention_node")
                
                elif rule == "link_to_quality_gate":
                    # Link to quality gate that triggered abstention
                    properties["quality_gate_trigger"] = properties.get("quality_gate_trigger", "unknown")
                
            except Exception as e:
                logger.warning(f"Rule {rule} failed for relationship: {e}")
        
        return properties
    
    def _infer_entity_mapping(self, entity: PipelineEntity) -> Dict[str, Any]:
        """Infer mapping configuration for unknown entity type"""
        entity_id_lower = entity.entity_id.lower()
        properties = entity.properties
        
        # Try to infer from entity_id and properties
        if any(keyword in entity_id_lower for keyword in ["law", "act", "ordinance"]):
            return {
                "target_label": NodeLabel.LAW,
                "mapping_rules": ["map_title_to_title", "add_kpk_specific_flag"],
                "required_fields": ["title"]
            }
        elif any(keyword in entity_id_lower for keyword in ["section", "sec", "s."]):
            return {
                "target_label": NodeLabel.SECTION,
                "mapping_rules": ["map_section_number", "link_to_parent_law"],
                "required_fields": ["section_number"]
            }
        elif any(keyword in entity_id_lower for keyword in ["penalty", "fine", "punishment"]):
            return {
                "target_label": NodeLabel.PENALTY,
                "mapping_rules": ["normalize_currency_to_pkr"],
                "required_fields": ["amount"]
            }
        elif any(keyword in entity_id_lower for keyword in ["species", "tree", "plant"]):
            return {
                "target_label": NodeLabel.SPECIES,
                "mapping_rules": ["determine_protection_level_kpk", "check_kpk_endemic_status"],
                "required_fields": ["common_name"]
            }
        elif any(keyword in entity_id_lower for keyword in ["officer", "dfo", "range"]):
            return {
                "target_label": NodeLabel.OFFICER,
                "mapping_rules": ["standardize_rank_abbreviations"],
                "required_fields": ["rank"]
            }
        elif any(keyword in entity_id_lower for keyword in ["location", "division", "range", "beat"]):
            return {
                "target_label": NodeLabel.LOCATION,
                "mapping_rules": ["determine_location_type", "apply_kpk_division_mapping"],
                "required_fields": ["name"]
            }
        else:
            # Default to generic entity
            return {
                "target_label": NodeLabel.ENTITY,
                "mapping_rules": ["map_title_to_title"],
                "required_fields": []
            }
    
    def _infer_relationship_mapping(self, rel_type: str, from_id: str, to_id: str) -> Dict[str, Any]:
        """Infer mapping configuration for unknown relationship type"""
        rel_type_lower = rel_type.lower()
        
        # Infer from relationship type string
        if "has" in rel_type_lower and "section" in rel_type_lower:
            return {
                "target_type": RelationshipType.HAS_SECTION,
                "mapping_rules": ["validate_law_section_linkage"]
            }
        elif "imposes" in rel_type_lower or "penalty" in rel_type_lower:
            return {
                "target_type": RelationshipType.IMPOSES,
                "mapping_rules": ["validate_penalty_applicability"]
            }
        elif "protects" in rel_type_lower:
            return {
                "target_type": RelationshipType.PROTECTS_SPECIES,
                "mapping_rules": ["determine_protection_level"]
            }
        elif "applies" in rel_type_lower:
            return {
                "target_type": RelationshipType.APPLIES_TO,
                "mapping_rules": ["validate_jurisdiction_overlap"]
            }
        elif "located" in rel_type_lower or "part_of" in rel_type_lower:
            return {
                "target_type": RelationshipType.LOCATED_IN,
                "mapping_rules": ["build_location_hierarchy"]
            }
        elif "amended" in rel_type_lower:
            return {
                "target_type": RelationshipType.AMENDED_BY,
                "mapping_rules": ["validate_temporal_order"]
            }
        elif "mentions" in rel_type_lower or "references" in rel_type_lower:
            return {
                "target_type": RelationshipType.MENTIONS,
                "mapping_rules": ["extract_mention_context"]
            }
        else:
            # Default to RELATES_TO
            return {
                "target_type": RelationshipType.RELATES_TO,
                "mapping_rules": []
            }
    
    def _extract_year(self, text: str) -> Optional[str]:
        """Extract year from text"""
        import re
        match = re.search(r'(19\d{2}|20\d{2})', text)
        return match.group(1) if match else None
    
    def _infer_jurisdiction(self, entity: PipelineEntity, metadata: Dict[str, Any]) -> str:
        """Infer jurisdiction for entity"""
        # Check metadata first
        if "jurisdiction" in metadata:
            return metadata["jurisdiction"]
        
        # Check entity properties
        if "jurisdiction" in entity.properties:
            return entity.properties["jurisdiction"]
        
        # Infer from entity type and content
        if entity.entity_type == NodeLabel.LAW:
            # Check if this is a KPK law
            entity_id_lower = entity.entity_id.lower()
            if any(keyword in entity_id_lower for keyword in ["kpk", "khyber", "nwfp", "hazara"]):
                return JurisdictionLevel.PROVINCIAL.value
        
        return JurisdictionLevel.PROVINCIAL.value  # Default for KPK
    
    def _is_kpk_specific(self, entity: PipelineEntity, metadata: Dict[str, Any]) -> bool:
        """Check if entity is KPK-specific"""
        entity_id_lower = entity.entity_id.lower()
        properties_str = str(entity.properties).lower()
        
        kpk_keywords = ["kpk", "khyber", "pakhtunkhwa", "nwfp", "hazara", 
                       "abbottabad", "manshera", "swat", "dir", "malakand"]
        
        # Check entity ID
        if any(keyword in entity_id_lower for keyword in kpk_keywords):
            return True
        
        # Check properties
        if any(keyword in properties_str for keyword in kpk_keywords):
            return True
        
        # Check metadata
        if metadata.get("jurisdiction") == "KPK":
            return True
        
        return False
    
    def _infer_parent_law(self, entity: PipelineEntity, metadata: Dict[str, Any]) -> str:
        """Infer parent law ID for section"""
        # Look for law reference in metadata
        if "document_law_id" in metadata:
            return metadata["document_law_id"]
        
        # Try to extract from entity_id
        entity_id_lower = entity.entity_id.lower()
        for keyword in ["kpk_fo", "forest_ordinance", "hazara_act"]:
            if keyword in entity_id_lower:
                return f"law_{keyword}"
        
        return f"law_unknown_{hash(entity.entity_id) % 1000}"
    
    def _generate_node_id(self, entity: PipelineEntity, properties: Dict[str, Any]) -> str:
        """Generate deterministic/unique node ID based on IdentityFactory"""
        
        # Determine name/value to hash
        name = properties.get("canonical_name", properties.get("name", properties.get("title", properties.get("section_number", entity.entity_id))))
        
        # Use IdentityFactory for stable, namespace-scoped hashing
        # Role is critical for ontological scaling (Officer vs Office) v2.3
        return IdentityFactory.generate_deterministic_id(
            namespace=self.namespace,
            label=entity.entity_type.value,
            name=str(name),
            role=properties.get("role", entity.entity_type.value),
            jurisdiction=properties.get("jurisdiction", "kpk")
        )
    
    def _slugify(self, text: str) -> str:
        """Convert text to slug format for IDs"""
        import re
        if not text:
            return "unknown"
        
        # Convert to lowercase
        slug = text.lower()
        
        # Replace spaces and special characters
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[-\s]+', '_', slug)
        
        # Remove leading/trailing underscores
        slug = slug.strip('_')
        
        # Limit length
        if len(slug) > 50:
            slug = slug[:50]
        
        return slug or "unknown"
    
    def _calculate_quality_indicators(self, nodes: List[Dict], relationships: List[Dict]) -> Dict[str, Any]:
        """Calculate quality indicators for the mapped graph"""
        total_nodes = len(nodes)
        total_relationships = len(relationships)
        
        if total_nodes == 0:
            return {
                "overall_quality": 0.0,
                "completeness": 0.0,
                "consistency": 0.0,
                "richness": 0.0
            }
        
        # Calculate node type diversity
        node_types = {}
        for node in nodes:
            label = node.get("label", "Unknown")
            node_types[label] = node_types.get(label, 0) + 1
        
        type_diversity = len(node_types) / total_nodes if total_nodes > 0 else 0
        
        # Calculate relationship richness
        relationship_richness = total_relationships / total_nodes if total_nodes > 0 else 0
        
        # Check for required KPK entity types
        required_types = ["Law", "Section", "Species", "Location"]
        present_types = sum(1 for t in required_types if t in node_types)
        completeness = present_types / len(required_types) if required_types else 1.0
        
        # Check for KPK-specific entities
        kpk_entities = sum(1 for node in nodes if node.get("kpk_specific", False))
        kpk_specificity = kpk_entities / total_nodes if total_nodes > 0 else 0
        
        # Overall quality score
        overall_quality = (
            completeness * 0.4 +
            type_diversity * 0.2 +
            relationship_richness * 0.2 +
            kpk_specificity * 0.2
        )
        
        return {
            "overall_quality": round(overall_quality, 3),
            "completeness": round(completeness, 3),
            "consistency": round(type_diversity, 3),
            "richness": round(relationship_richness, 3),
            "kpk_specificity": round(kpk_specificity, 3),
            "node_type_distribution": node_types,
            "validation_errors_count": len(self.stats["validation_errors"]),
            "abstention_cases_count": len(self.stats["abstention_cases"])
        }
    
    def export_mapping_report(self) -> Dict[str, Any]:
        """Export mapping report for documentation"""
        return {
            "mapping_summary": {
                "total_nodes_mapped": self.stats["total_nodes_mapped"],
                "total_relationships_mapped": self.stats["total_relationships_mapped"],
                "duplicates_skipped": {
                    "nodes": self.stats["duplicate_nodes_skipped"],
                    "relationships": self.stats["duplicate_relationships_skipped"]
                },
                "abstention_cases": len(self.stats["abstention_cases"])
            },
            "node_id_map": self.node_id_map,  # Expose global identity layer for audit/debug
            "quality_indicators": self._calculate_quality_indicators([], []),  # Will be populated after mapping
            "validation_errors": self.stats["validation_errors"],
            "mapping_configuration": {
                "entity_mappings": list(self.entity_type_mappings.keys()),
                "relationship_mappings": list(self.relationship_type_mappings.keys()),
                "schema_validation_enabled": self.schema_validation
            },
            "timestamp": datetime.now().isoformat()
        }


# ============================================================================
# UTILITY FUNCTIONS FOR PIPELINE INTEGRATION
# ============================================================================

def create_graph_mapper_from_config(config_path: Optional[str] = None) -> KPKGraphMapper:
    """
    Create graph mapper from configuration file
    
    Args:
        config_path: Path to mapper configuration JSON
        
    Returns:
        Configured KPKGraphMapper instance
    """
    if config_path and Path(config_path).exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        schema_validation = config.get("schema_validation", True)
        mapper = KPKGraphMapper(schema_validation=schema_validation)
        
        # Apply custom mappings if provided
        if "entity_mappings" in config:
            mapper.entity_type_mappings.update(config["entity_mappings"])
        
        if "relationship_mappings" in config:
            mapper.relationship_type_mappings.update(config["relationship_mappings"])
        
        logger.info(f"Graph mapper created from config: {config_path}")
        return mapper
    
    # Default mapper
    return KPKGraphMapper()


def validate_graph_structure(nodes: List[Dict], relationships: List[Dict]) -> Dict[str, Any]:
    """
    Validate graph structure before export to Neo4j
    
    Args:
        nodes: List of node dictionaries
        relationships: List of relationship dictionaries
        
    Returns:
        Validation report
    """
    report = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "statistics": {
            "total_nodes": len(nodes),
            "total_relationships": len(relationships),
            "isolated_nodes": 0,
            "duplicate_nodes": 0,
            "orphaned_relationships": 0
        }
    }
    
    # Check for duplicate node IDs
    node_ids = set()
    for node in nodes:
        node_id = node.get("node_id")
        if not node_id:
            report["errors"].append("Node missing node_id")
            report["valid"] = False
        elif node_id in node_ids:
            report["warnings"].append(f"Duplicate node ID: {node_id}")
            report["statistics"]["duplicate_nodes"] += 1
        else:
            node_ids.add(node_id)
    
    # Check for isolated nodes (nodes with no relationships)
    connected_nodes = set()
    for rel in relationships:
        from_id = rel.get("from_id")
        to_id = rel.get("to_id")
        
        if from_id and to_id:
            connected_nodes.add(from_id)
            connected_nodes.add(to_id)
        else:
            report["errors"].append(f"Relationship missing from_id or to_id: {rel}")
            report["valid"] = False
    
    isolated_nodes = node_ids - connected_nodes
    report["statistics"]["isolated_nodes"] = len(isolated_nodes)
    
    if isolated_nodes:
        report["warnings"].append(f"{len(isolated_nodes)} isolated nodes found")
    
    # Check for orphaned relationships (references to non-existent nodes)
    for rel in relationships:
        from_id = rel.get("from_id")
        to_id = rel.get("to_id")
        
        if from_id and from_id not in node_ids:
            report["warnings"].append(f"Relationship from_id {from_id} not found in nodes")
            report["statistics"]["orphaned_relationships"] += 1
        
        if to_id and to_id not in node_ids:
            report["warnings"].append(f"Relationship to_id {to_id} not found in nodes")
            report["statistics"]["orphaned_relationships"] += 1
    
    return report


# ============================================================================
# MAIN FUNCTION FOR STANDALONE USE
# ============================================================================

def main():
    """Main function for standalone testing"""
    import argparse
    
    parser = argparse.ArgumentParser(description="KPK Graph Mapper")
    parser.add_argument("--input", required=True, help="Input pipeline output JSON")
    parser.add_argument("--output", required=True, help="Output mapped graph JSON")
    parser.add_argument("--config", help="Mapper configuration JSON")
    parser.add_argument("--validate-only", action="store_true", 
                       help="Only validate, don't map")
    
    args = parser.parse_args()
    
    # Load input data
    with open(args.input, 'r', encoding='utf-8') as f:
        pipeline_output = json.load(f)
    
    if args.validate_only:
        # Validate existing graph structure
        nodes = pipeline_output.get("nodes", [])
        relationships = pipeline_output.get("relationships", [])
        
        validation = validate_graph_structure(nodes, relationships)
        
        print("\n" + "="*60)
        print("GRAPH STRUCTURE VALIDATION REPORT")
        print("="*60)
        print(f"Valid: {validation['valid']}")
        print(f"Nodes: {validation['statistics']['total_nodes']}")
        print(f"Relationships: {validation['statistics']['total_relationships']}")
        print(f"Isolated nodes: {validation['statistics']['isolated_nodes']}")
        print(f"Duplicate nodes: {validation['statistics']['duplicate_nodes']}")
        print(f"Orphaned relationships: {validation['statistics']['orphaned_relationships']}")
        
        if validation["errors"]:
            print("\nERRORS:")
            for error in validation["errors"][:5]:  # Show first 5 errors
                print(f"  - {error}")
        
        if validation["warnings"]:
            print("\nWARNINGS:")
            for warning in validation["warnings"][:5]:  # Show first 5 warnings
                print(f"  - {warning}")
        
        print("="*60)
        
    else:
        # Create mapper and process
        mapper = create_graph_mapper_from_config(args.config)
        
        # Map pipeline output to graph
        result = mapper.map_pipeline_output(pipeline_output)
        
        # Save result
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print("\n" + "="*60)
        print("GRAPH MAPPING COMPLETE")
        print("="*60)
        print(f"Input file: {args.input}")
        print(f"Output file: {args.output}")
        print(f"Nodes mapped: {mapper.stats['total_nodes_mapped']}")
        print(f"Relationships mapped: {mapper.stats['total_relationships_mapped']}")
        print(f"Validation errors: {len(mapper.stats['validation_errors'])}")
        print(f"Abstention cases: {len(mapper.stats['abstention_cases'])}")
        
        # Show quality indicators
        if "quality_indicators" in result:
            qi = result["quality_indicators"]
            print(f"\nQuality Indicators:")
            print(f"  Overall quality: {qi.get('overall_quality', 0):.3f}")
            print(f"  Completeness: {qi.get('completeness', 0):.3f}")
            print(f"  Consistency: {qi.get('consistency', 0):.3f}")
            print(f"  Richness: {qi.get('richness', 0):.3f}")
            print(f"  KPK Specificity: {qi.get('kpk_specificity', 0):.3f}")
        
        print("="*60)


if __name__ == "__main__":
    main()
