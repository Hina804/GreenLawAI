"""
GRAPH_SCHEMA_KPK.PY - KPK Forestry Knowledge Graph Schema
Core research contribution: Defines Neo4j nodes, relationships, and properties for KPK forestry domain.
ENHANCED VERSION: Added Climate/Agentic nodes, improved validation, and better integration with pipeline phases.
"""

from enum import Enum
from typing import Dict, List, Any, Optional, Set, Tuple
from datetime import datetime
from dataclasses import dataclass, field
import json

# ============================================================================
# ENUMERATIONS
# ============================================================================

class NodeLabel(Enum):
    """Node labels in KPK forestry knowledge graph"""
    LAW = "Law"
    ORDINANCE = "Ordinance"
    SECTION = "Section"
    CLAUSE = "Clause"
    PENALTY = "Penalty"
    FINE = "Fine"
    SPECIES = "Species"
    TREE_SPECIES = "TreeSpecies"
    OFFICER = "Officer"
    AUTHORITY = "Authority"
    LOCATION = "Location"
    DIVISION = "Division"
    RANGE = "Range"
    BEAT = "Beat"
    FOREST = "Forest"
    COMPARTMENT = "Compartment"
    PERMIT = "Permit"
    LICENSE = "License"
    CIRCULAR = "Circular"
    NOTIFICATION = "Notification"
    WORKING_PLAN = "WorkingPlan"
    DOCUMENT = "Document"
    DOCUMENT_CHUNK = "DocumentChunk"
    ENTITY = "Entity"
    RELATIONSHIP = "Relationship"
    AMENDMENT = "Amendment"
    VERSION = "Version"
    TEMPORAL_SLICE = "TemporalSlice"
    ABSTENTION = "Abstention"
    # NEW: Climate and Agentic AI nodes for future extensions
    CLIMATE_IMPACT = "ClimateImpact"
    CARBON_SEQUESTRATION = "CarbonSequestration"
    CONSERVATION_ACTION = "ConservationAction"
    AGENT = "Agent"  # For Agentic AI components
    AGENT_ACTION = "AgentAction"
    USER_QUERY = "UserQuery"
    SYSTEM_RESPONSE = "SystemResponse"
    UNCERTAINTY_REGION = "UncertaintyRegion"  # For fuzzy boundaries
    LAW_VERSION = "LawVersion"  # NEW: Temporal immutable law
    LEGAL_INTERPRETATION = "LegalInterpretation"  # NEW: Agent-writable layer
    AUTHORITY_GATE = "AuthorityGate"  # NEW: Mutation control node
    
    # Missing labels needed by DocProfiler
    FIR = "FIR"
    OTHER = "Other"
    RULE = "Rule"
    REGULATION = "Regulation"
    GAZETTE = "Gazette"
    REPORT = "Report"
    POLICY = "Policy"
    GUIDELINE = "Guideline"
    FORM = "Form"
    REGISTER = "Register"
    MEMORANDUM = "Memorandum"
    ORDER = "Order"
    AGREEMENT = "Agreement"
    CONTRACT = "Contract"
    DEPARTMENT = "Department"
    PROVINCE = "Province"

class RelationshipType(Enum):
    """Relationship types in KPK forestry knowledge graph"""
    # Legal Structure
    HAS_SECTION = "HAS_SECTION"
    HAS_CLAUSE = "HAS_CLAUSE"
    HAS_PENALTY = "HAS_PENALTY"
    IMPOSES = "IMPOSES"
    DEFINES = "DEFINES"
    REFERENCES = "REFERENCES"
    CITES = "CITES"
    
    # Hierarchy
    PART_OF = "PART_OF"
    CONTAINS = "CONTAINS"
    BELONGS_TO = "BELONGS_TO"
    GOVERNED_BY = "GOVERNED_BY"
    UNDER_JURISDICTION = "UNDER_JURISDICTION"
    
    # Authority
    ISSUED_BY = "ISSUED_BY"
    SIGNED_BY = "SIGNED_BY"
    APPROVED_BY = "APPROVED_BY"
    ENFORCED_BY = "ENFORCED_BY"
    REPORTED_TO = "REPORTED_TO"
    
    # Geographic
    LOCATED_IN = "LOCATED_IN"
    APPLIES_TO = "APPLIES_TO"
    VALID_IN = "VALID_IN"
    PROTECTS = "PROTECTS"
    COVERS = "COVERS"
    
    # Temporal
    AMENDED_BY = "AMENDED_BY"
    SUPERSEDES = "SUPERSEDES"
    REPLACES = "REPLACES"
    VERSION_OF = "VERSION_OF"
    VALID_FROM = "VALID_FROM"
    VALID_UNTIL = "VALID_UNTIL"
    
    # Species & Permits
    PROTECTS_SPECIES = "PROTECTS_SPECIES"
    REGULATES = "REGULATES"
    REQUIRES_PERMIT = "REQUIRES_PERMIT"
    ALLOWS = "ALLOWS"
    PROHIBITS = "PROHIBITS"
    
    # Financial
    HAS_FINE = "HAS_FINE"
    FINES_FOR = "FINES_FOR"
    PENALIZES = "PENALIZES"
    
    # Document
    EXTRACTED_FROM = "EXTRACTED_FROM"
    MENTIONS = "MENTIONS"
    RELATES_TO = "RELATES_TO"
    SIMILAR_TO = "SIMILAR_TO"
    
    # Abstention
    ABSTAINS_FROM = "ABSTAINS_FROM"
    UNCERTAIN_ABOUT = "UNCERTAIN_ABOUT"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    
    # NEW: For Climate and Agentic AI
    CONTRIBUTES_TO = "CONTRIBUTES_TO"  # Deforestation → Climate Impact
    MITIGATES = "MITIGATES"  # Conservation → Carbon Sequestration
    SUGGESTED_BY = "SUGGESTED_BY"  # Agent suggests action
    EXECUTED_BY = "EXECUTED_BY"  # Action executed by agent
    TRIGGERS = "TRIGGERS"  # Pattern triggers agent action
    ANSWERED_BY = "ANSWERED_BY"  # Query answered by response
    HAS_CONFIDENCE = "HAS_CONFIDENCE"  # Confidence score relationship
    HAS_INTERPRETATION = "HAS_INTERPRETATION" # NEW: Law/Section -> Interpretation
    INTERPRETED_BY = "INTERPRETED_BY" # NEW: Interpretation -> Agent

class JurisdictionLevel(Enum):
    """Jurisdiction hierarchy in KPK"""
    FEDERAL = "federal"
    PROVINCIAL = "provincial"
    DIVISIONAL = "divisional"
    DISTRICT = "district"
    RANGE_LEVEL = "range"
    BEAT_LEVEL = "beat"
    LOCAL = "local"

class AbstentionReason(Enum):
    """Reasons for system abstention - VIVA RESEARCH CONTRIBUTION"""
    AUTHORITY_CONFLICT = "authority_conflict"
    POOR_OCR_QUALITY = "poor_ocr_quality"
    MULTILINGUAL_AMBIGUITY = "multilingual_ambiguity"
    TEMPORAL_CONFLICT = "temporal_conflict"
    JURISDICTION_OVERLAP = "jurisdiction_overlap"
    PENALTY_CALCULATION_UNCERTAIN = "penalty_calculation_uncertain"
    SPECIES_IDENTIFICATION_LOW_CONFIDENCE = "species_identification_low_confidence"
    LEGAL_TERM_AMBIGUITY = "legal_term_ambiguity"
    CONTRADICTORY_REFERENCES = "contradictory_references"
    INCOMPLETE_AMENDMENT_CHAIN = "incomplete_amendment_chain"

# ============================================================================
# DATA CLASSES FOR PIPELINE INTEGRATION
# ============================================================================

@dataclass
class PipelineEntity:
    """Standardized entity format flowing through pipeline"""
    entity_id: str
    entity_type: NodeLabel
    properties: Dict[str, Any]
    source_phase: str  # Which phase extracted this (e.g., "phase_4.1")
    confidence_score: float = 1.0
    abstention_reason: Optional[AbstentionReason] = None
    needs_human_review: bool = False
    
    def to_node_dict(self) -> Dict[str, Any]:
        """Convert to Neo4j node format"""
        return {
            "label": self.entity_type.value,
            "node_id": self.entity_id,
            **self.properties,
            "extraction_phase": self.source_phase,
            "confidence_score": self.confidence_score,
            "abstention_reason": self.abstention_reason.value if self.abstention_reason else None,
            "needs_review": self.needs_human_review
        }

@dataclass
class PipelineRelationship:
    """Standardized relationship format flowing through pipeline"""
    relationship_id: str
    relationship_type: RelationshipType
    from_node_id: str
    to_node_id: str
    properties: Dict[str, Any]
    source_phase: str
    confidence_score: float = 1.0
    
    def to_relationship_dict(self) -> Dict[str, Any]:
        """Convert to Neo4j relationship format"""
        return {
            "type": self.relationship_type.value,
            "from_id": self.from_node_id,
            "to_id": self.to_node_id,
            **self.properties,
            "extraction_phase": self.source_phase,
            "confidence_score": self.confidence_score
        }

# ============================================================================
# NODE SCHEMAS (ENHANCED)
# ============================================================================

class KPKGraphQueries:
    """Standard Cypher queries for KPK forestry graph."""
    CREATE_NODE = "MERGE (n:{label} {{node_id: $node_id}}) SET n += $properties RETURN n"
    CREATE_RELATIONSHIP = "MATCH (a), (b) WHERE a.node_id = $src_id AND b.node_id = $dst_id MERGE (a)-[r:{rel_type}]->(b) SET r += $properties RETURN r"
    GET_CITATIONS = "MATCH (l:Law)-[:HAS_SECTION]->(s:Section)-[:CITES]->(target) RETURN l.name, s.number, target.name"
    GET_AMENDMENTS = "MATCH (a:Amendment)-[:AMENDED_BY]->(b) RETURN a, b"

class KPKGraphPatterns:
    """Common graph patterns in KPK forestry law."""
    ACT_AMENDMENT = "(law:Law)-[:AMENDED_BY]->(amendment:Amendment)"
    PENALTY_FOR_OFFENCE = "(penalty:Penalty)-[:PENALIZES]->(species:Species)"
    AUTHORITY_JURISDICTION = "(authority:Authority)-[:GOVERNED_BY]->(law:Law)"

class KPKNodeSchema:
    """Schema definitions for KPK forestry graph nodes"""
    
    @staticmethod
    def get_node_schemas() -> Dict[NodeLabel, Dict[str, Any]]:
        """Get all node schema definitions"""
        schemas = {
            NodeLabel.LAW: {
                "required": ["node_id", "title", "jurisdiction"],
                "optional": [
                    "year", "act_number", "gazette_notification",
                    "effective_date", "repealed_date", "status",
                    "source_document", "parsing_confidence",
                    "kpk_specific", "hazara_override", "version",
                    "pipeline_source", "chunk_ids",  # NEW: Integration with FAISS
                    "amendment_chain_complete",  # NEW: From amendment_tracker.py
                    "authority_conflicts",  # NEW: From authority_hierarchy.py
                    "name", "content", "full_text", "canonical_name" # NEW: Common pipeline fields
                ],
                "constraints": ["UNIQUE(node_id)", "INDEX(title)"],
                "example": {
                    "node_id": "law_kpk_forest_ordinance_2002",
                    "title": "Khyber Pakhtunkhwa Forest Ordinance, 2002",
                    "jurisdiction": JurisdictionLevel.PROVINCIAL.value,
                    "year": 2002,
                    "act_number": "VII of 2002",
                    "kpk_specific": True,
                    "hazara_override": False,
                    "version": "1.0",
                    "pipeline_source": "phase_4.1_rule_extractor",
                    "amendment_chain_complete": True,
                    "authority_conflicts": ["hazara_act_1912"],
                    "is_immutable": True # SAFETY HARDENING
                }
            },
            
            NodeLabel.LAW_VERSION: {
                "required": ["node_id", "law_id", "version_number"],
                "optional": ["effective_date", "gazette_reference", "is_current", "is_immutable"],
                "constraints": ["UNIQUE(node_id)"],
                "example": {
                    "node_id": "version_kpk_fo_2002_v1",
                    "law_id": "law_kpk_forest_ordinance_2002",
                    "version_number": "1.0",
                    "is_immutable": True
                }
            },
            
            NodeLabel.LEGAL_INTERPRETATION: {
                "required": ["node_id", "interprets_node_id", "agent_id", "interpretation_text"],
                "optional": ["confidence", "justification", "legal_references", "is_immutable"],
                "constraints": ["UNIQUE(node_id)"],
                "example": {
                    "node_id": "interp_agent_alpha_sec_27",
                    "interprets_node_id": "section_kpk_fo_2002_27",
                    "agent_id": "agent_legal_analyzer_v1",
                    "interpretation_text": "Section 27 applies even if tree is dead.",
                    "is_immutable": False # Agents can refine their own interpretations
                }
            },
            
            NodeLabel.SECTION: {
                "required": ["node_id", "section_number", "law_id"],
                "optional": [
                    "title", "content", "amendment_history",
                    "effective_date", "repealed_date", "penalty_amount",
                    "currency", "applicable_to", "jurisdiction_specific",
                    "parsing_confidence", "needs_review",
                    "multilingual_content",  # NEW: From multilingual_handler.py
                    "ocr_corrected",  # NEW: From llm_text_sanitizer.py
                    "ambiguity_resolved",  # NEW: From llm_ambiguity_resolver.py
                    "chunk_ids",  # NEW: Which document chunks contain this
                    "citation_references",  # NEW: From citation_resolver.py
                    "name",  # NEW: Useful for display and searching
                    "text", "bbox", "ocr_confidence", "canonical_name"
                ],
                "constraints": ["UNIQUE(node_id)", "INDEX(section_number)"],
                "example": {
                    "node_id": "section_kpk_fo_2002_27",
                    "section_number": "27",
                    "law_id": "law_kpk_forest_ordinance_2002",
                    "title": "Penalty for unauthorized felling",
                    "content": "Any person who fells any tree in a reserved forest...",
                    "penalty_amount": 50000,
                    "currency": "PKR",
                    "jurisdiction_specific": "KPK",
                    "ocr_corrected": True,
                    "ambiguity_resolved": "section_above_refers_to_26",
                    "chunk_ids": ["chunk_123", "chunk_124"]
                }
            },
            
            NodeLabel.PENALTY: {
                "required": ["node_id", "amount", "currency"],
                "optional": [
                    "violation_type", "applicable_section",
                    "minimum_amount", "maximum_amount",
                    "discretionary", "escalation_clause",
                    "repeat_offense_multiplier", "species_specific",
                    "location_specific", "officer_discretion",
                    "calculated_by",
                    "temporal_validity",
                    "authority_level",
                    "bbox",
                    "ocr_confidence"
                ],
                "constraints": ["UNIQUE(node_id)", "INDEX(amount)"],
                "example": {
                    "node_id": "penalty_50000_pkr_felling",
                    "amount": 50000,
                    "currency": "PKR",
                    "violation_type": "unauthorized_felling",
                    "species_specific": "deodar",
                    "repeat_offense_multiplier": 2.0,
                    "calculated_by": "penalty_logic_engine",
                    "temporal_validity": "2002-01-01_to_2015-01-14"
                }
            },
            
            NodeLabel.SPECIES: {
                "required": ["node_id", "common_name"],
                "optional": [
                    "scientific_name", "local_names",
                    "legal_status", "protection_level",
                    "cutting_permit_required", "permit_type",
                    "commercial_use_allowed", "traditional_use_allowed",
                    "conservation_status", "kpk_endemic",
                    "division_specific_rules",
                    "ner_confidence",  # NEW: From ner_extractor.py
                    "multilingual_terms",  # NEW: From multilingual_handler.py
                    "image_references",  # NEW: From image_processor.py
                    "working_plan_references", "canonical_name"  # NEW: From working_plan_parser.py
                ],
                "constraints": ["UNIQUE(node_id)", "INDEX(common_name)"],
                "example": {
                    "node_id": "species_deodar",
                    "common_name": "Deodar",
                    "scientific_name": "Cedrus deodara",
                    "local_names": ["دیار", "देवदार"],
                    "legal_status": "protected",
                    "protection_level": "highest",
                    "cutting_permit_required": "special_permit",
                    "kpk_endemic": True,
                    "ner_confidence": 0.95,
                    "multilingual_terms": {
                        "urdu": "دیار",
                        "pashto": "دیودار"
                    }
                }
            },
            
            NodeLabel.DOCUMENT_CHUNK: {
                "required": ["node_id", "chunk_text", "source_document"],
                "optional": [
                    "chunk_index", "embedding_vector",
                    "page_number", "section_reference",
                    "language", "confidence_score",
                    "entities_mentioned", "key_phrases",
                    "semantic_type", "faiss_index_id",
                    "pipeline_phase",  # NEW: Which phase created this
                    "ocr_quality",  # NEW: From doc_quality_assessor.py
                    "layout_type",  # NEW: From extract_layout.py
                    "table_data_extracted"  # NEW: From table_extractor.py
                ],
                "constraints": ["UNIQUE(node_id)", "INDEX(source_document)"],
                "example": {
                    "node_id": "chunk_kpk_fo_27_1",
                    "chunk_text": "Section 27: Any person who fells any tree...",
                    "source_document": "kpk_forest_ordinance_2002.pdf",
                    "page_number": 12,
                    "section_reference": "27",
                    "confidence_score": 0.95,
                    "faiss_index_id": 12345,
                    "pipeline_phase": "phase_6.4_legal_chunker",
                    "ocr_quality": 0.98,
                    "layout_type": "single_column"
                }
            },
            
            NodeLabel.ABSTENTION: {
                "required": ["node_id", "abstention_type", "reason"],
                "optional": [
                    "confidence_threshold", "affected_entities",
                    "module_name", "timestamp", "resolution_status",
                    "human_reviewed", "resolution_notes",
                    "tags", "document_context",
                    "pipeline_phase",  # NEW: Which phase abstained
                    "quality_gate_triggered",  # NEW: From quality_gates.py
                    "suggested_resolution"  # NEW: For human reviewer
                ],
                "constraints": ["UNIQUE(node_id)", "INDEX(abstention_type)"],
                "example": {
                    "node_id": "abstention_conflict_hazara_20240115",
                    "abstention_type": "authority_conflict",
                    "reason": "Conflict between KPK Ordinance and Hazara Forest Act",
                    "confidence_threshold": 0.7,
                    "affected_entities": ["species_deodar", "penalty_50000_pkr_felling"],
                    "module_name": "authority_hierarchy.py",
                    "timestamp": "2024-01-15T10:30:00Z",
                    "resolution_status": "pending",
                    "pipeline_phase": "phase_5.1",
                    "quality_gate_triggered": "authority_conflict_detected",
                    "suggested_resolution": "Check Gazette S.R.O. 456/2010"
                }
            },
            
            # NEW: Climate Impact Node for FYP extension
            NodeLabel.CLIMATE_IMPACT: {
                "required": ["node_id", "impact_type", "severity"],
                "optional": [
                    "description", "carbon_emissions_estimate",
                    "affected_species", "affected_locations",
                    "mitigation_measures", "temporal_trend",
                    "data_source", "confidence_level"
                ],
                "constraints": ["UNIQUE(node_id)", "INDEX(impact_type)"],
                "example": {
                    "node_id": "climate_deforestation_kpk",
                    "impact_type": "carbon_emissions",
                    "severity": "high",
                    "description": "Deforestation in KPK coniferous forests",
                    "carbon_emissions_estimate": "50000 tons CO2/year",
                    "affected_species": ["deodar", "chir_pine"],
                    "mitigation_measures": ["reforestation", "protected_areas"]
                }
            },
            
            # NEW: Agent Node for Agentic AI
            NodeLabel.AGENT: {
                "required": ["node_id", "agent_type", "capabilities"],
                "optional": [
                    "description", "trigger_conditions",
                    "authority_level", "knowledge_sources",
                    "execution_history", "success_rate",
                    "confidence_thresholds"
                ],
                "constraints": ["UNIQUE(node_id)", "INDEX(agent_type)"],
                "example": {
                    "node_id": "agent_illegal_pattern_detector",
                    "agent_type": "monitoring_agent",
                    "capabilities": ["pattern_detection", "anomaly_alert"],
                    "trigger_conditions": "multiple_offenses_same_location_30days",
                    "authority_level": "divisional",
                    "knowledge_sources": ["incident_reports", "permit_data"]
                }
            },
            
            # --- NEW SCHEMAS FOR BASE ENTITIES ---
            NodeLabel.LOCATION: {
                "required": ["node_id", "name"],
                "optional": [
                    "type", "jurisdiction_level", "parent_location_id",
                    "area_km2", "population_millions", "capital",
                    "forest_coverage_percent", "description",
                    "kpk_specific", "hazara_specific", "districts",
                    "special_status", "hazara_forest_act_applies",
                    "kpk_ordinance_overridden", "canonical_name"
                ],
                "constraints": ["UNIQUE(node_id)", "INDEX(name)"],
                "example": {
                    "node_id": "LOCATION_KPK_PROVINCE",
                    "name": "Khyber Pakhtunkhwa",
                    "type": "province",
                    "kpk_specific": True
                }
            },
            
            NodeLabel.AUTHORITY: {
                "required": ["node_id", "name"],
                "optional": [
                    "type", "jurisdiction_level", "headquarters",
                    "description", "kpk_specific", "established_year",
                    "responsibilities", "contact_info", "address", "website", "canonical_name"
                ],
                "constraints": ["UNIQUE(node_id)", "INDEX(name)"],
                "example": {
                    "node_id": "AUTHORITY_KPK_FOREST_DEPARTMENT",
                    "name": "KPK Forest Department",
                    "type": "department",
                    "kpk_specific": True
                }
            },
            
            NodeLabel.OFFICER: {
                "required": ["node_id", "rank"],
                "optional": [
                    "name", "designation", "jurisdiction_level",
                    "location_id", "authority_id", "tenure", "canonical_name"
                ],
                "constraints": ["UNIQUE(node_id)"],
                "example": {
                    "node_id": "OFFICER_DFO_ABBOTTABAD",
                    "rank": "Divisional Forest Officer",
                    "location_id": "LOCATION_ABBOTTABAD"
                }
            },
            
            NodeLabel.AMENDMENT: {
                "required": ["node_id", "amending_law", "amended_section"],
                "optional": [
                    "gazette_reference", "amendment_date",
                    "change_type", "effective_date",
                    "bbox", "ocr_confidence"
                ],
                "constraints": ["UNIQUE(node_id)"],
                "example": {
                    "node_id": "AMENDMENT_GAZETTE_2010_1",
                    "amending_law": "KPK Forest (Amendment) Act, 2010",
                    "amended_section": "section_kpk_fo_2002_27"
                }
            },
            
            # --- NEW SCHEMAS FOR BASE ENTITIES ---
            NodeLabel.DOCUMENT: {
                "required": ["node_id"],
                "optional": ["document_id", "document_type", "title", "name", "content", "full_text", "source_phase", "extraction_confidence", "metadata"],
                "constraints": ["UNIQUE(node_id)"]
            },
            
            # NEW: Document Chunk Node for RAG integration
            NodeLabel.DOCUMENT_CHUNK: {
                "required": ["node_id"],
                "optional": ["chunk_id", "content", "metadata", "tokens", "source_document", "order"],
                "constraints": ["UNIQUE(node_id)"]
            }
        }
        return schemas
    
    @staticmethod
    def validate_node_against_schema(node_data: Dict, node_type: NodeLabel) -> Tuple[bool, List[str]]:
        """Validate a node against its schema"""
        schemas = KPKNodeSchema.get_node_schemas()
        schema = schemas.get(node_type)
        
        if not schema:
            return False, [f"Unknown node type: {node_type}"]
        
        errors = []
        
        # Check required fields
        for field in schema["required"]:
            if field not in node_data:
                errors.append(f"Missing required field: {field}")
        
        # Check for unknown fields (typo detection)
        # Filter out common pipeline metadata fields that are always allowed
        internal_metadata = {
            "pipeline_source", "extraction_confidence", "mapping_timestamp",
            "source_phase", "source_document", "confidence", "method",
            "deterministic", "entity_id", "original_text", "context", "id",
            "entity_type", "type", "value", "label", "abstention_reason",
            "needs_review", "node_id", "label", "authority_level", "mapped_at",
            "jurisdiction", "chunk_ids", "law_id", "amendment_chain_complete",
            "authority_conflicts", "metadata", "child_sections", "relationships",
            "full_text", "document_id", "document_type", "species_mentioned",
            "section_number", "content", "name", "text", "is_immutable",
            "source_doc_id", "extraction_phase", "confidence_score",
            "bbox", "ocr_confidence", "canonical_name"
        }
        
        allowed_fields = set(schema["required"] + schema["optional"]) | internal_metadata
        for field in node_data.keys():
            if field not in allowed_fields:
                errors.append(f"Unknown field: {field}")
        
        # Special KPK validations
        if node_type == NodeLabel.LAW:
            if node_data.get("kpk_specific") and not node_data.get("jurisdiction") == JurisdictionLevel.PROVINCIAL.value:
                errors.append("KPK-specific law must have provincial jurisdiction")
        
        if node_type == NodeLabel.SPECIES:
            if node_data.get("kpk_endemic") and not node_data.get("legal_status") in ["protected", "regulated"]:
                errors.append("KPK endemic species should be protected or regulated")
        
        return len(errors) == 0, errors

# ============================================================================
# RELATIONSHIP SCHEMAS (ENHANCED)
# ============================================================================

class KPKRelationshipSchema:
    """Schema definitions for KPK forestry graph relationships"""
    
    @staticmethod
    def get_relationship_schemas() -> Dict[RelationshipType, Dict[str, Any]]:
        """Get all relationship schema definitions"""
        return {
            RelationshipType.HAS_SECTION: {
                "from": NodeLabel.LAW,
                "to": NodeLabel.SECTION,
                "properties": ["section_number", "order", "version"],
                "cardinality": "ONE_TO_MANY",
                "description": "Law contains multiple sections",
                "pipeline_source": "phase_4.1_rule_extractor"  # NEW
            },
            
            RelationshipType.IMPOSES: {
                "from": NodeLabel.SECTION,
                "to": NodeLabel.PENALTY,
                "properties": ["condition", "applicability", "severity"],
                "cardinality": "ONE_TO_ONE_OR_MANY",
                "description": "Section imposes penalty for violation",
                "pipeline_source": "phase_5.2_penalty_logic_engine"  # NEW
            },
            
            RelationshipType.PROTECTS_SPECIES: {
                "from": NodeLabel.LAW,
                "to": NodeLabel.SPECIES,
                "properties": ["protection_level", "exceptions", "permit_requirements"],
                "cardinality": "MANY_TO_MANY",
                "description": "Law provides protection to specific tree species",
                "pipeline_source": "phase_4.2_ner_extractor"  # NEW
            },
            
            RelationshipType.APPLIES_TO: {
                "from": NodeLabel.LAW,
                "to": NodeLabel.LOCATION,
                "properties": ["jurisdiction_level", "exceptions", "overrides"],
                "cardinality": "MANY_TO_MANY",
                "description": "Law applies to specific geographic locations",
                "pipeline_source": "phase_5.1_authority_hierarchy"  # NEW
            },
            
            RelationshipType.AMENDED_BY: {
                "from": NodeLabel.SECTION,
                "to": NodeLabel.AMENDMENT,
                "properties": ["amendment_date", "change_type", "gazette_reference"],
                "cardinality": "ONE_TO_MANY",
                "description": "Section amended by gazette notification",
                "pipeline_source": "phase_4.3_amendment_tracker"  # NEW
            },
            
            RelationshipType.REQUIRES_PERMIT: {
                "from": NodeLabel.SECTION,
                "to": NodeLabel.PERMIT,
                "properties": ["permit_condition", "exceptions", "application_process"],
                "cardinality": "ONE_TO_MANY",
                "description": "Activity requires specific permit as per law",
                "pipeline_source": "phase_3.2_circular_parser"  # NEW
            },
            
            RelationshipType.UNDER_JURISDICTION: {
                "from": NodeLabel.OFFICER,
                "to": NodeLabel.LOCATION,
                "properties": ["jurisdiction_type", "authority_level", "tenure"],
                "cardinality": "MANY_TO_MANY",
                "description": "Officer has jurisdiction over location",
                "pipeline_source": "phase_0.2_kpk_metadata_enricher"  # NEW
            },
            
            RelationshipType.ABSTAINS_FROM: {
                "from": NodeLabel.ABSTENTION,
                "to": [NodeLabel.SECTION, NodeLabel.PENALTY, NodeLabel.SPECIES],
                "properties": ["reason_detail", "confidence_score", "suggested_action"],
                "cardinality": "ONE_TO_MANY",
                "description": "System abstains from making decision about entity",
                "pipeline_source": "phase_7.2_quality_gates"  # NEW
            },
            
            RelationshipType.VALID_IN: {
                "from": NodeLabel.LAW,
                "to": NodeLabel.LOCATION,
                "properties": ["valid_from", "valid_until", "jurisdiction_conflict"],
                "cardinality": "MANY_TO_MANY",
                "description": "Law is valid in specific location during time period",
                "pipeline_source": "phase_5.4_temporal_validator"  # NEW
            },
            
            RelationshipType.GOVERNED_BY: {
                "from": [NodeLabel.LAW, NodeLabel.SECTION, NodeLabel.OFFICER],
                "to": NodeLabel.AUTHORITY,
                "properties": ["authority_type", "legal_basis"],
                "optional_properties": ["rank", "jurisdiction"],
                "cardinality": "MANY_TO_ONE",
                "description": "Entity is governed by or subject to an authority",
                "pipeline_source": "phase_5.1_authority_hierarchy"
            },
            
            RelationshipType.REFERENCES: {
                "from": [NodeLabel.SECTION, NodeLabel.AMENDMENT],
                "to": [NodeLabel.SECTION, NodeLabel.LAW],
                "properties": ["source_text"],
                "optional_properties": ["citation_id", "confidence"],
                "cardinality": "MANY_TO_MANY",
                "description": "One legal entity refers to another",
                "pipeline_source": "phase_4.4_citation_resolver"
            },
            
            RelationshipType.BELONGS_TO: {
                "from": NodeLabel.OFFICER,
                "to": NodeLabel.DEPARTMENT,
                "properties": [],
                "optional_properties": ["role", "since"],
                "cardinality": "MANY_TO_ONE",
                "description": "Officer belongs to a department",
                "pipeline_source": "phase_6.3_graph_builder"
            },
            
            RelationshipType.LOCATED_IN: {
                "from": [NodeLabel.SECTION, NodeLabel.OFFICER, NodeLabel.AUTHORITY],
                "to": NodeLabel.LOCATION,
                "properties": [],
                "optional_properties": ["context", "confidence"],
                "cardinality": "MANY_TO_MANY",
                "description": "Entity is associated with a geographic location",
                "pipeline_source": "phase_4.2_ner_extractor"
            },
            
            RelationshipType.CITES: {
                "from": NodeLabel.SECTION,
                "to": NodeLabel.SECTION,
                "properties": ["citation_type", "context", "interpretation"],
                "cardinality": "MANY_TO_MANY",
                "description": "Section cites another section for reference",
                "pipeline_source": "phase_4.4_citation_resolver"  # NEW
            },
            
            # NEW: For Climate and Agentic AI
            RelationshipType.CONTRIBUTES_TO: {
                "from": NodeLabel.PENALTY,  # Violation contributes to climate impact
                "to": NodeLabel.CLIMATE_IMPACT,
                "properties": ["contribution_factor", "evidence_source"],
                "cardinality": "MANY_TO_MANY",
                "description": "Violation contributes to climate impact",
                "pipeline_source": "phase_6.2_graph_mapper"  # Future extension
            },
            
            RelationshipType.TRIGGERS: {
                "from": NodeLabel.ABSTENTION,  # Uncertainty triggers agent
                "to": NodeLabel.AGENT,
                "properties": ["trigger_type", "priority", "conditions"],
                "cardinality": "MANY_TO_MANY",
                "description": "Abstention or uncertainty triggers agent action",
                "pipeline_source": "phase_7.2_quality_gates"  # Future extension
            },
            
            RelationshipType.MENTIONS: {
                "from": NodeLabel.DOCUMENT,
                "to": [NodeLabel.SPECIES, NodeLabel.OFFICER, NodeLabel.AUTHORITY, NodeLabel.LOCATION, NodeLabel.ENTITY],
                "properties": ["context", "confidence"],
                "cardinality": "MANY_TO_MANY",
                "description": "Document mentions a specific entity",
                "pipeline_source": "phase_6.2_graph_mapper"
            }
        }
    
    @staticmethod
    def validate_relationship_against_schema(rel_data: Dict, rel_type: RelationshipType) -> Tuple[bool, List[str]]:
        """Validate a relationship against its schema"""
        schemas = KPKRelationshipSchema.get_relationship_schemas()
        schema = schemas.get(rel_type)
        
        if not schema:
            return False, [f"Unknown relationship type: {rel_type}"]
        
        errors = []
        
        # Check required properties (only if they are explicitly marked as required in validation logic)
        # Note: In this implementation, we treat the 'properties' list in schema as 'recommended'
        # but only certain core fields are strictly required across all relationships.
        internal_metadata = {
            "pipeline_source", "confidence", "mapping_timestamp", 
            "source_phase", "rel_id", "link_type", "from_id", "to_id", "type",
            "confidence_score", "extraction_phase", "source_doc_id"
        }
        
        # For now, we only enforce that the relationship has from_id and to_id
        # if they are present in the rel_data (mapper uses this)
        # Builder passes properties only, so we skip if not present
        if "from_id" in rel_data or "to_id" in rel_data:
            if "from_id" not in rel_data:
                errors.append("Missing required property: from_id")
            if "to_id" not in rel_data:
                errors.append("Missing required property: to_id")
        
        # Check for mandatory properties from schema definition
        required_props = schema.get("properties", [])
        # In this implementation, we don't strictly enforce 'properties' as 'required' 
        # unless they are in a separate 'required' list (which isn't in the rel schema yet)
        
        # Check node types exist (would need Neo4j connection)
        # This is a placeholder for actual validation
        
        return len(errors) == 0, errors

# ============================================================================
# GRAPH CONSTRUCTION INTEGRATION
# ============================================================================

class GraphConstructionInterface:
    """Interface for pipeline phases to interact with graph construction"""
    
    @staticmethod
    def prepare_for_phase_6(entities: List[PipelineEntity], 
                          relationships: List[PipelineRelationship]) -> Dict[str, Any]:
        """Prepare data from earlier phases for graph construction"""
        
        # Group entities by type
        nodes_by_type = {}
        for entity in entities:
            node_type = entity.entity_type.value
            if node_type not in nodes_by_type:
                nodes_by_type[node_type] = []
            nodes_by_type[node_type].append(entity.to_node_dict())
        
        # Group relationships by type
        rels_by_type = {}
        for rel in relationships:
            rel_type = rel.relationship_type.value
            if rel_type not in rels_by_type:
                rels_by_type[rel_type] = []
            rels_by_type[rel_type].append(rel.to_relationship_dict())
        
        # Create mapping for FAISS indexing
        chunk_nodes = [e for e in entities if e.entity_type == NodeLabel.DOCUMENT_CHUNK]
        chunk_mapping = {}
        for chunk in chunk_nodes:
            chunk_mapping[chunk.entity_id] = {
                "faiss_index_id": chunk.properties.get("faiss_index_id"),
                "embedding_vector": chunk.properties.get("embedding_vector"),
                "source_document": chunk.properties.get("source_document")
            }
        
        return {
            "nodes_by_type": nodes_by_type,
            "relationships_by_type": rels_by_type,
            "chunk_mapping": chunk_mapping,
            "statistics": {
                "total_entities": len(entities),
                "total_relationships": len(relationships),
                "entity_types": list(nodes_by_type.keys()),
                "relationship_types": list(rels_by_type.keys())
            },
            "pipeline_metadata": {
                "phases_completed": list(set([e.source_phase for e in entities])),
                "abstentions_count": len([e for e in entities if e.abstention_reason]),
                "needs_review_count": len([e for e in entities if e.needs_human_review])
            }
        }

# ============================================================================
# QUALITY GATES INTEGRATION
# ============================================================================

class SchemaQualityGates:
    """Quality gates specific to graph schema validation"""
    
    @staticmethod
    def check_graph_quality(graph_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run quality checks on graph data before construction"""
        
        quality_report = {
            "passed": True,
            "checks": [],
            "warnings": [],
            "errors": [],
            "abstention_recommendations": []
        }
        
        nodes = graph_data.get("nodes", [])
        relationships = graph_data.get("relationships", [])
        
        # Check 1: All nodes have required fields
        for node in nodes:
            node_type = node.get("label")
            if node_type:
                try:
                    node_label = NodeLabel(node_type)
                    valid, errors = KPKNodeSchema.validate_node_against_schema(node, node_label)
                    if not valid:
                        quality_report["errors"].extend(errors)
                        quality_report["passed"] = False
                except ValueError:
                    quality_report["errors"].append(f"Unknown node label: {node_type}")
                    quality_report["passed"] = False
        
        # Check 2: All relationships have valid types
        for rel in relationships:
            rel_type = rel.get("type")
            if rel_type:
                try:
                    rel_enum = RelationshipType(rel_type)
                    valid, errors = KPKRelationshipSchema.validate_relationship_against_schema(rel, rel_enum)
                    if not valid:
                        quality_report["errors"].extend(errors)
                        quality_report["passed"] = False
                except ValueError:
                    quality_report["errors"].append(f"Unknown relationship type: {rel_type}")
                    quality_report["passed"] = False
        
        # Check 3: KPK-specific requirements
        provincial_laws = [n for n in nodes if n.get("label") == "Law" and n.get("jurisdiction") == "provincial"]
        if not provincial_laws:
            quality_report["warnings"].append("No provincial (KPK-specific) laws found")
        
        # Check 4: Abstention linkage
        abstentions = [n for n in nodes if n.get("label") == "Abstention"]
        for abstention in abstentions:
            affected_entities = abstention.get("affected_entities", [])
            if not affected_entities:
                quality_report["warnings"].append(f"Abstention {abstention.get('node_id')} has no affected entities")
        
        # Check 5: Temporal validity
        laws_with_dates = [n for n in nodes if n.get("label") == "Law" and n.get("effective_date")]
        laws_without_dates = [n for n in nodes if n.get("label") == "Law" and not n.get("effective_date")]
        if laws_without_dates:
            quality_report["warnings"].append(f"{len(laws_without_dates)} laws missing effective dates")
        
        return quality_report

# ============================================================================
# MAIN EXPORT (ENHANCED)
# ============================================================================

class KPKGraphSchema:
    """Main class exposing KPK forestry graph schema"""
    
    def __init__(self):
        self.node_schema = KPKNodeSchema()
        self.relationship_schema = KPKRelationshipSchema()
        self.queries = KPKGraphQueries()
        self.patterns = KPKGraphPatterns()
        self.construction_interface = GraphConstructionInterface()
        self.quality_gates = SchemaQualityGates()
    
    def export_schema(self) -> Dict[str, Any]:
        """Export complete schema for documentation"""
        return {
            "version": "2.1-kpk-enhanced",  # UPDATED
            "description": "KPK Forestry Knowledge Graph Schema with Pipeline Integration",
            "jurisdiction": "Khyber Pakhtunkhwa, Pakistan",
            "research_contribution": "Abstention Framework + Hybrid Storage",
            "nodes": self.node_schema.get_node_schemas(),
            "relationships": self.relationship_schema.get_relationship_schemas(),
            "pipeline_integration": {
                "data_classes": ["PipelineEntity", "PipelineRelationship"],
                "interface_methods": ["prepare_for_phase_6", "check_graph_quality"],
                "phase_mappings": self._get_phase_mappings()
            },
            "metadata": {
                "created": datetime.now().isoformat(),
                "fyp_alignment": {
                    "objective_1": "Structured knowledge base",
                    "objective_2": "RAG foundation",
                    "objective_3": "Agentic AI ready",
                    "objective_4": "Climate awareness extension"
                },
                "coverage": [
                    "Forest Laws", "Species Protection", "Officer Hierarchy", 
                    "Geographic Jurisdiction", "Temporal Amendments",
                    "Authority Conflicts", "Climate Impacts", "Agentic Actions"
                ]
            }
        }
    
    def get_schema_summary(self) -> Dict[str, Any]:
        """Compatibility method for legacy pipeline."""
        schema = self.export_schema()
        return {
            "version": schema["version"],
            "nodes": list(schema["nodes"].keys()),
            "relationships": list(schema["relationships"].keys()),
            "total_node_types": len(schema["nodes"]),
            "total_relationship_types": len(schema["relationships"])
        }
    
    def _get_phase_mappings(self) -> Dict[str, List[str]]:
        """Map pipeline phases to graph components"""
        return {
            "phase_0": ["metadata_enrichment", "quality_assessment"],
            "phase_1": ["text_extraction", "ocr_correction"],
            "phase_2": ["document_restoration", "multilingual_segmentation"],
            "phase_3": ["linguistic_alignment", "document_type_parsing"],
            "phase_4": ["entity_extraction", "amendment_tracking"],
            "phase_5": ["authority_reasoning", "temporal_validation"],
            "phase_6": ["graph_construction", "vector_indexing"],
            "phase_7": ["quality_gates", "abstention_handling"]
        }
    
    def generate_phase_6_input(self, pipeline_output: Dict[str, Any]) -> Dict[str, Any]:
        """Generate input for phase 6 graph construction"""
        # This would be called by phase 7.1_batch_processor.py
        entities = pipeline_output.get("entities", [])
        relationships = pipeline_output.get("relationships", [])
        
        return self.construction_interface.prepare_for_phase_6(entities, relationships)


# ============================================================================
# EXAMPLE USAGE WITH PIPELINE INTEGRATION
# ============================================================================

if __name__ == "__main__":
    # Initialize enhanced schema
    kpk_schema = KPKGraphSchema()
    
    # Export complete schema
    schema_doc = kpk_schema.export_schema()
    print(f"✅ Enhanced KPK Graph Schema v{schema_doc['version']}")
    print(f"   Nodes: {len(schema_doc['nodes'])} types")
    print(f"   Relationships: {len(schema_doc['relationships'])} types")
    print(f"   Pipeline Integration: {len(schema_doc['pipeline_integration']['phase_mappings'])} phases")
    
    # Example pipeline entity
    deodar_entity = PipelineEntity(
        entity_id="species_deodar",
        entity_type=NodeLabel.SPECIES,
        properties={
            "common_name": "Deodar",
            "scientific_name": "Cedrus deodara",
            "legal_status": "protected",
            "kpk_endemic": True,
            "ner_confidence": 0.95
        },
        source_phase="phase_4.2_ner_extractor",
        confidence_score=0.95
    )
    
    # Example pipeline relationship
    protection_rel = PipelineRelationship(
        relationship_id="protects_deodar_1",
        relationship_type=RelationshipType.PROTECTS_SPECIES,
        from_node_id="law_kpk_forest_ordinance_2002",
        to_node_id="species_deodar",
        properties={
            "protection_level": "highest",
            "permit_requirements": "special_permit"
        },
        source_phase="phase_4.1_rule_extractor",
        confidence_score=0.98
    )
    
    # Prepare for graph construction
    graph_input = kpk_schema.construction_interface.prepare_for_phase_6(
        [deodar_entity], 
        [protection_rel]
    )
    
    print(f"\n📊 Graph Construction Input Prepared:")
    print(f"   Entities: {graph_input['statistics']['total_entities']}")
    print(f"   Relationships: {graph_input['statistics']['total_relationships']}")
    print(f"   Entity Types: {graph_input['statistics']['entity_types']}")
    
    print("\n" + "="*80)
    print("KPK FORESTRY KNOWLEDGE GRAPH SCHEMA - READY FOR PHASE 6 CONSTRUCTION")
    print("="*80)
