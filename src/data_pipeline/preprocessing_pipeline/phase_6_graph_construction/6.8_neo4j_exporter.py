"""
6.8_NEO4J_EXPORTER.PY - Neo4j Graph Export for KPK Forestry Knowledge Graph
Exports processed data to Neo4j with KPK specialization, schema validation, and hybrid indexing.
Features: Cypher generation, CSV export, constraint management, and Neo4j integration.
"""

import json
import csv
import logging
import shutil
from typing import Dict, List, Tuple, Optional, Any, Union, Set
from pathlib import Path
from dataclasses import dataclass, asdict, field
from datetime import datetime
import hashlib
import re
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
try:
    import pandas as pd
except ImportError:
    pd = None
from preprocessing_pipeline.common.exceptions import ForensicIntegrityError

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class Neo4jConfig:
    """Configuration for Neo4j export."""
    uri: str = "bolt://localhost:7687"
    username: str = "neo4j"
    password: str = "password"
    database: str = "kpkforestry"
    batch_size: int = 1000
    use_apoc: bool = True
    create_constraints: bool = True
    create_indexes: bool = True
    export_format: str = "csv"  # "csv", "cypher", "both"
    csv_directory: Optional[str] = None
    
    def validate(self) -> bool:
        """Validate configuration parameters."""
        if not self.uri.startswith(("bolt://", "neo4j://")):
            logger.error(f"Invalid URI: {self.uri}. Must start with bolt:// or neo4j://")
            return False
        
        if self.export_format not in ["csv", "cypher", "both"]:
            logger.error(f"Invalid export_format: {self.export_format}")
            return False
        
        if self.batch_size <= 0 or self.batch_size > 10000:
            logger.error(f"Invalid batch_size: {self.batch_size}. Must be between 1 and 10000")
            return False
        
        return True

@dataclass
class ExportNode:
    """Node for Neo4j export."""
    node_id: str
    labels: List[str]
    properties: Dict[str, Any]
    source_file: str
    creation_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class ExportRelationship:
    """Relationship for Neo4j export."""
    relationship_id: str
    start_node_id: str
    end_node_id: str
    type: str
    properties: Dict[str, Any]
    source_file: str
    creation_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class ExportStatistics:
    """Statistics for export operation."""
    total_nodes: int = 0
    total_relationships: int = 0
    nodes_by_label: Dict[str, int] = field(default_factory=dict)
    relationships_by_type: Dict[str, int] = field(default_factory=dict)
    export_duration: float = 0.0
    file_sizes: Dict[str, int] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    forensic_validated: bool = False

@dataclass
class Neo4jConstraint:
    """Neo4j constraint definition."""
    name: str
    type: str  # "UNIQUE", "EXISTS", "NODE_KEY"
    label: str
    property: str
    description: str = ""

@dataclass
class Neo4jIndex:
    """Neo4j index definition."""
    name: str
    type: str  # "INDEX", "FULLTEXT", "LOOKUP"
    labels_or_types: List[str]
    properties: List[str]
    description: str = ""

class KPKNeo4jSchema:
    """KPK-specific Neo4j schema definitions."""
    
    def __init__(self):
        self.constraints = self._define_constraints()
        self.indexes = self._define_indexes()
        self.node_templates = self._define_node_templates()
        self.relationship_templates = self._define_relationship_templates()
        
        logger.info("KPKNeo4jSchema initialized")
    
    def _define_constraints(self) -> List[Neo4jConstraint]:
        """Define Neo4j constraints for KPK forestry graph."""
        return [
            # Node uniqueness constraints
            Neo4jConstraint(
                name="law_id_unique",
                type="UNIQUE",
                label="Law",
                property="node_id",
                description="Ensure unique law IDs"
            ),
            Neo4jConstraint(
                name="section_id_unique",
                type="UNIQUE",
                label="Section",
                property="node_id",
                description="Ensure unique section IDs"
            ),
            Neo4jConstraint(
                name="species_id_unique",
                type="UNIQUE",
                label="Species",
                property="node_id",
                description="Ensure unique species IDs"
            ),
            Neo4jConstraint(
                name="officer_id_unique",
                type="UNIQUE",
                label="Officer",
                property="node_id",
                description="Ensure unique officer IDs"
            ),
            Neo4jConstraint(
                name="location_id_unique",
                type="UNIQUE",
                label="Location",
                property="node_id",
                description="Ensure unique location IDs"
            ),
            Neo4jConstraint(
                name="penalty_id_unique",
                type="UNIQUE",
                label="Penalty",
                property="node_id",
                description="Ensure unique penalty IDs"
            ),
            Neo4jConstraint(
                name="abstention_id_unique",
                type="UNIQUE",
                label="Abstention",
                property="node_id",
                description="Ensure unique abstention IDs"
            ),
            
            # Property existence constraints
            Neo4jConstraint(
                name="law_title_exists",
                type="EXISTS",
                label="Law",
                property="title",
                description="Ensure law has title"
            ),
            Neo4jConstraint(
                name="section_number_exists",
                type="EXISTS",
                label="Section",
                property="section_number",
                description="Ensure section has number"
            ),
            Neo4jConstraint(
                name="species_name_exists",
                type="EXISTS",
                label="Species",
                property="common_name",
                description="Ensure species has common name"
            ),
            
            # Node key constraints (composite)
            Neo4jConstraint(
                name="law_jurisdiction_key",
                type="NODE_KEY",
                label="Law",
                property="title,jurisdiction,year",
                description="Unique combination of title, jurisdiction, and year"
            )
        ]
    
    def _define_indexes(self) -> List[Neo4jIndex]:
        """Define Neo4j indexes for KPK forestry graph."""
        return [
            # Single property indexes
            Neo4jIndex(
                name="law_year_index",
                type="INDEX",
                labels_or_types=["Law"],
                properties=["year"],
                description="Index for law years"
            ),
            Neo4jIndex(
                name="species_status_index",
                type="INDEX",
                labels_or_types=["Species"],
                properties=["legal_status"],
                description="Index for species legal status"
            ),
            Neo4jIndex(
                name="penalty_amount_index",
                type="INDEX",
                labels_or_types=["Penalty"],
                properties=["amount"],
                description="Index for penalty amounts"
            ),
            Neo4jIndex(
                name="location_type_index",
                type="INDEX",
                labels_or_types=["Location"],
                properties=["type"],
                description="Index for location types"
            ),
            Neo4jIndex(
                name="officer_rank_index",
                type="INDEX",
                labels_or_types=["Officer"],
                properties=["rank"],
                description="Index for officer ranks"
            ),
            Neo4jIndex(
                name="abstention_reason_index",
                type="INDEX",
                labels_or_types=["Abstention"],
                properties=["reason"],
                description="Index for abstention reasons"
            ),
            
            # Composite indexes
            Neo4jIndex(
                name="law_jurisdiction_year_index",
                type="INDEX",
                labels_or_types=["Law"],
                properties=["jurisdiction", "year"],
                description="Composite index for law jurisdiction and year"
            ),
            Neo4jIndex(
                name="section_law_index",
                type="INDEX",
                labels_or_types=["Section"],
                properties=["law_id", "section_number"],
                description="Composite index for sections by law"
            ),
            
            # Full-text indexes
            Neo4jIndex(
                name="law_content_fulltext",
                type="FULLTEXT",
                labels_or_types=["Law"],
                properties=["title", "description"],
                description="Full-text search on law content"
            ),
            Neo4jIndex(
                name="species_names_fulltext",
                type="FULLTEXT",
                labels_or_types=["Species"],
                properties=["common_name", "scientific_name", "local_names"],
                description="Full-text search on species names"
            ),
            Neo4jIndex(
                name="section_content_fulltext",
                type="FULLTEXT",
                labels_or_types=["Section"],
                properties=["title", "content"],
                description="Full-text search on section content"
            ),
            
            # Relationship indexes
            Neo4jIndex(
                name="relationship_type_index",
                type="INDEX",
                labels_or_types=["HAS_SECTION", "IMPOSES", "APPLIES_TO", "PROTECTS_SPECIES"],
                properties=["type"],
                description="Index on relationship types"
            )
        ]
    
    def _define_node_templates(self) -> Dict[str, Dict[str, Any]]:
        """Define node templates for KPK entities."""
        return {
            "Law": {
                "required_properties": ["node_id", "title", "jurisdiction"],
                "recommended_properties": ["year", "act_number", "gazette_notification", "effective_date"],
                "labels": ["Law", "LegalDocument", "KPK_Entity"],
                "description": "Legal document (Act, Ordinance, Rules)"
            },
            "Section": {
                "required_properties": ["node_id", "section_number", "law_id"],
                "recommended_properties": ["title", "content", "penalty_amount", "effective_date"],
                "labels": ["Section", "LegalClause", "KPK_Entity"],
                "description": "Section of a law"
            },
            "Species": {
                "required_properties": ["node_id", "common_name"],
                "recommended_properties": ["scientific_name", "legal_status", "protection_level", "kpk_endemic"],
                "labels": ["Species", "ForestEntity", "KPK_Entity"],
                "description": "Tree species in KPK forests"
            },
            "Officer": {
                "required_properties": ["node_id", "rank"],
                "recommended_properties": ["designation", "jurisdiction_level", "division", "authority_level"],
                "labels": ["Officer", "Authority", "KPK_Entity"],
                "description": "Forestry department officer"
            },
            "Location": {
                "required_properties": ["node_id", "name", "type"],
                "recommended_properties": ["division", "district", "area_ha", "protection_status"],
                "labels": ["Location", "GeographicEntity", "KPK_Entity"],
                "description": "Geographic location in KPK"
            },
            "Penalty": {
                "required_properties": ["node_id", "amount", "currency"],
                "recommended_properties": ["violation_type", "applicable_section", "repeat_offense_multiplier"],
                "labels": ["Penalty", "LegalConsequence", "KPK_Entity"],
                "description": "Fine or penalty for violation"
            },
            "Abstention": {
                "required_properties": ["node_id", "reason", "entity_type"],
                "recommended_properties": ["confidence", "requires_human_review", "pipeline_phase"],
                "labels": ["Abstention", "Uncertainty", "KPK_Entity"],
                "description": "Node representing uncertain data"
            },
            "DocumentChunk": {
                "required_properties": ["node_id", "chunk_text", "source_document"],
                "recommended_properties": ["faiss_index_id", "embedding_vector", "confidence_score"],
                "labels": ["DocumentChunk", "Content", "KPK_Entity"],
                "description": "Chunk of document text for RAG"
            }
        }
    
    def _define_relationship_templates(self) -> Dict[str, Dict[str, Any]]:
        """Define relationship templates for KPK graph."""
        return {
            "HAS_SECTION": {
                "from_labels": ["Law"],
                "to_labels": ["Section"],
                "recommended_properties": ["section_number", "order", "amendment_status"],
                "description": "Law contains sections"
            },
            "IMPOSES": {
                "from_labels": ["Section"],
                "to_labels": ["Penalty"],
                "recommended_properties": ["condition", "applicability", "severity"],
                "description": "Section imposes penalty"
            },
            "PROTECTS_SPECIES": {
                "from_labels": ["Law", "Section"],
                "to_labels": ["Species"],
                "recommended_properties": ["protection_level", "restrictions", "conservation_measures"],
                "description": "Law protects species"
            },
            "APPLIES_TO": {
                "from_labels": ["Law", "Section", "Penalty"],
                "to_labels": ["Location", "Species"],
                "recommended_properties": ["jurisdiction", "effective_date", "conditions"],
                "description": "Legal provision applies to entity"
            },
            "UNDER_JURISDICTION": {
                "from_labels": ["Officer"],
                "to_labels": ["Location"],
                "recommended_properties": ["jurisdiction_type", "authority_level", "tenure"],
                "description": "Officer has jurisdiction over location"
            },
            "AMENDED_BY": {
                "from_labels": ["Section", "Law"],
                "to_labels": ["Amendment"],
                "recommended_properties": ["amendment_date", "gazette_reference", "change_type"],
                "description": "Legal provision amended by amendment"
            },
            "ABSTAINS_FROM": {
                "from_labels": ["Abstention"],
                "to_labels": ["Section", "Penalty", "Species", "Law"],
                "recommended_properties": ["reason_detail", "confidence_score", "suggested_action"],
                "description": "System abstains from making decision"
            },
            "HAS_CHUNK": {
                "from_labels": ["Law", "Section", "Document"],
                "to_labels": ["DocumentChunk"],
                "recommended_properties": ["chunk_order", "page_number", "confidence"],
                "description": "Document contains text chunks"
            },
            "SIMILAR_TO": {
                "from_labels": ["DocumentChunk"],
                "to_labels": ["DocumentChunk"],
                "recommended_properties": ["similarity_score", "embedding_distance", "semantic_type"],
                "description": "Chunks are semantically similar"
            }
        }
    
    def validate_node(self, node: ExportNode) -> Tuple[bool, List[str]]:
        """Validate node against schema."""
        primary_label = node.labels[0] if node.labels else None
        
        if not primary_label or primary_label not in self.node_templates:
            return False, [f"Unknown node label: {primary_label}"]
        
        template = self.node_templates[primary_label]
        errors = []
        
        # Check required properties
        for prop in template["required_properties"]:
            if prop not in node.properties:
                errors.append(f"Missing required property: {prop}")
        
        # Check property types (basic validation)
        for prop, value in node.properties.items():
            if prop == "node_id" and not isinstance(value, str):
                errors.append(f"node_id must be string, got {type(value)}")
            elif prop == "year" and not isinstance(value, (int, str)):
                errors.append(f"year must be int or string, got {type(value)}")
        
        return len(errors) == 0, errors
    
    def validate_relationship(self, rel: ExportRelationship) -> Tuple[bool, List[str]]:
        """Validate relationship against schema."""
        if rel.type not in self.relationship_templates:
            return False, [f"Unknown relationship type: {rel.type}"]
        
        return True, []  # Relationship validation would check node labels

class Neo4jCSVExporter:
    """Exports data to Neo4j CSV format for LOAD CSV."""
    
    def __init__(self, output_dir: Union[str, Path] = "./data_processed/graph_exports", production_mode: bool = True):
        self.output_dir = Path(output_dir)
        self.production_mode = production_mode
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.nodes_file = self.output_dir / "nodes.csv"
        self.relationships_file = self.output_dir / "relationships.csv"
        self.constraints_file = self.output_dir / "constraints.cypher"
        self.indexes_file = self.output_dir / "indexes.cypher"
        
        self.node_writer = None
        self.relationship_writer = None
        self.node_fieldnames = None
        self.relationship_fieldnames = None
        
        # Internal components
        try:
            from preprocessing_pipeline.phase_6_graph_construction.graph_schema_kpk import KPKNodeSchema, NodeLabel
        except ImportError:
            pass # Use fallbacks if needed
            
        self.schema = KPKNeo4jSchema()
        self.stats = ExportStatistics()
        
        # Audit logic hashes
        self.logic_hashes = self._calculate_logic_hashes()
        
        # Initialize state and directories
        self.prepare_csv_dirs()
        
        logger.info(f"CSV exporter initialized with output directory: {self.output_dir}")
    
    def _generate_deterministic_rel_id(self, start_id: str, end_id: str, rel_type: str, rel_id: Optional[str] = None) -> str:
        """Generate a deterministic relationship ID based on its endpoints and type."""
        if not rel_id or rel_id.startswith("rel_"):
            hash_input = f"{start_id}_{rel_type}_{end_id}"
            hash_val = hashlib.sha256(hash_input.encode()).hexdigest()[:12]
            return f"{rel_type}_{hash_val}"
        return rel_id

    def _calculate_logic_hashes(self) -> Dict[str, str]:
        """Calculate hashes of critical pipeline logic for audit trail"""
        hashes = {}
        paths = {
            "identity": Path(__file__).parent.parent / "common" / "identity.py",
            "schema": Path(__file__).parent / "graph_schema_kpk.py",
            "exporter": Path(__file__)
        }
        
        for name, path in paths.items():
            try:
                if path.exists():
                    with open(path, "rb") as f:
                        hashes[name] = hashlib.sha256(f.read()).hexdigest()[:12].strip()
                else:
                    hashes[name] = "unknown"
            except Exception as e:
                logger.warning(f"Could not hash {name} logic: {e}")
                hashes[name] = "error"
        return hashes

    def _generate_audit_manifest(self) -> str:
        """Generate manifest.json with system metadata and logic hashes"""
        manifest = {
            "export_timestamp": datetime.now().isoformat(),
            "system_version": "2.3-hardened",
            "logic_hashes": self.logic_hashes,
            "export_statistics": {
                "nodes": self.stats.total_nodes,
                "relationships": self.stats.total_relationships
            },
            "environment": {
                "python_version": sys.version.split()[0],
                "platform": sys.platform
            }
        }
        
        manifest_path = self.output_dir / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
            
        logger.info(f"Audit manifest generated: {manifest_path}")
        return str(manifest_path)

    def export_to_neo4j(self, linked_graph: Dict[str, Any]) -> Dict[str, Any]:
        """Compatibility method for run_sequential_pipeline.py."""
        nodes_by_type = linked_graph.get("nodes_by_type", {})
        all_nodes = []
        for node_list in nodes_by_type.values():
            for n in node_list:
                # Handle flat vs nested structure logic
                labels = n.get("labels", [])
                if not labels and "label" in n:
                    labels = [n["label"]]
                elif isinstance(labels, str):
                    labels = [labels]
                
                props = n.get("properties", {})
                exclude = ["node_id", "label", "labels", "source_document", "source_file"]
                if not props:
                    # If empty, it's likely a flat structure from mapper
                    props = {k: v for k, v in n.items() if k not in exclude}
                else:
                    # Even if nested, filter out redundant IDs and labels
                    props = {k: v for k, v in props.items() if k not in exclude}
                
                all_nodes.append(ExportNode(
                    n.get("node_id"), 
                    labels, 
                    props, 
                    n.get("source_document", n.get("source_file", "unknown"))
                ))
        
        relationships_by_type = linked_graph.get("relationships_by_type", {})
        all_rels = []
        for rel_list in relationships_by_type.values():
            for r in rel_list:
                # Mapper uses from_id/to_id, Exporter expects start/end
                start_id = r.get("start_node_id", r.get("from_id"))
                end_id = r.get("end_node_id", r.get("to_id"))
                
                # Phase 6 Hardening: Use deterministic relationship IDs (v2.3)
                rel_id = r.get("relationship_id", r.get("rel_id"))
                if not rel_id or rel_id.startswith("rel_") or rel_id.startswith("REL_"):
                    rel_id = self._generate_deterministic_rel_id(start_id, end_id, r.get("type", "RELATES_TO"))
                
                rel_props = r.get("properties", {})
                exclude = ["rel_id", "relationship_id", "from_id", "to_id", "start_node_id", "end_node_id", "type", "source_document", "source_file"]
                if not rel_props:
                    rel_props = {k: v for k, v in r.items() if k not in exclude}
                else:
                    rel_props = {k: v for k, v in rel_props.items() if k not in exclude}

                all_rels.append(ExportRelationship(
                    rel_id, 
                    start_id, 
                    end_id, 
                    r.get("type", "RELATES_TO"), 
                    rel_props, 
                    r.get("source_document", r.get("source_file", "unknown"))
                ))
                
        # Prepare files (without headers yet, we'll write them in export methods)
        self.prepare_csv_dirs()
        
        node_count = self.export_nodes(all_nodes, overwrite=True)
        rel_count = self.export_relationships(all_rels, overwrite=True)
        
        # Update stats for manifest
        self.stats.total_nodes = node_count
        self.stats.total_relationships = rel_count
        
        # Phase 3 Hardening: Generate DB-level enforcement triggers
        self.generate_immutability_constraints()
        
        manifest_path = self._generate_audit_manifest()
        
        return {
            "status": "success",
            "nodes_exported": node_count,
            "relationships_exported": rel_count,
            "output_directory": str(self.output_dir),
            "manifest": manifest_path,
            "forensic_validation": {
                "validated_against_csv": getattr(self.stats, "forensic_validated", False),
                "validated_timestamp": datetime.now().isoformat(),
                "missing_fields": 0 if getattr(self.stats, "forensic_validated", False) else "unknown",
                "hard_enforcement_active": getattr(self, "production_mode", True)
            }
        }

    def export_batch(self, nodes_data: List[Dict], relationships_data: List[Dict]) -> Dict[str, int]:
        """Export a batch of raw dict data (from GraphBuilder)."""
        nodes = []
        for n in nodes_data:
            # Handle flat vs nested structure logic
            labels = n.get("labels", [])
            if not labels and "label" in n:
                labels = [n["label"]]
            elif isinstance(labels, str):
                labels = [labels]
                
            props = n.get("properties", {})
            exclude = ["node_id", "label", "labels", "source_document", "source_file"]
            if not props:
                props = {k: v for k, v in n.items() if k not in exclude}
            else:
                props = {k: v for k, v in props.items() if k not in exclude}

            nodes.append(ExportNode(
                node_id=n.get("node_id"),
                labels=labels,
                properties=props,
                source_file=n.get("source_document", n.get("source_file", "unknown"))
            ))
            
        relationships = []
        for r in relationships_data:
            # Handle flat vs nested structure logic
            # Mapper uses from_id/to_id, Exporter expects start/end
            start_id = r.get("start_node_id", r.get("from_id"))
            end_id = r.get("end_node_id", r.get("to_id"))
            
            # Phase 6 Hardening: Use deterministic relationship IDs (v2.3)
            rel_id = r.get("relationship_id", r.get("rel_id"))
            if not rel_id or rel_id.startswith("rel_"):
                rel_id = self._generate_deterministic_rel_id(start_id, end_id, r.get("type", "RELATES_TO"))
            
            
            rel_props = r.get("properties", {})
            exclude = ["rel_id", "relationship_id", "from_id", "to_id", "start_node_id", "end_node_id", "type", "source_document", "source_file"]
            if not rel_props:
                rel_props = {k: v for k, v in r.items() if k not in exclude}
            else:
                rel_props = {k: v for k, v in rel_props.items() if k not in exclude}

            relationships.append(ExportRelationship(
                relationship_id=rel_id,
                start_node_id=start_id,
                end_node_id=end_id,
                type=r.get("type", "RELATES_TO"),
                properties=rel_props,
                source_file=r.get("source_document", r.get("source_file", "unknown"))
            ))
            
        # For batching, we append without overwriting, but if it's the first batch we might need a header
        # However, for simplicity in current architecture, we'll assume export_nodes/export_relationships 
        # manages the header if it doesn't exist
        node_count = self.export_nodes(nodes, overwrite=False)
        rel_count = self.export_relationships(relationships, overwrite=False)
        
        return {"nodes": node_count, "relationships": rel_count}
    
    def prepare_csv_dirs(self):
        """Ensure output directory exists."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.node_fieldnames_base = [
            'node_id:ID',
            ':LABEL',
            'source_file',
            'creation_timestamp',
            'export_version',
            'logic_hash'
        ]
        self.relationship_fieldnames_base = [
            ':START_ID',
            ':END_ID',
            ':TYPE',
            'relationship_id',
            'source_file',
            'creation_timestamp',
            'export_version',
            'logic_hash'
        ]
    
    def export_nodes(self, nodes: List[ExportNode], overwrite: bool = True) -> int:
        """
        Export nodes to CSV.
        """
        if not nodes:
            return 0
        
        # 3. Frozen Header Union (Phase 3 Hardening)
        # Derive headers from the union of all node properties across the entire set
        all_properties = set()
        for node in nodes:
            all_properties.update(node.properties.keys())
        
        property_fieldnames = sorted(list(all_properties))
        fieldnames = self.node_fieldnames_base + property_fieldnames
        
        # Freeze headers for this file if write mode
        if overwrite:
            self.node_fieldnames = fieldnames
        
        mode = 'w' if overwrite else 'a'
        file_exists = self.nodes_file.exists()
        
        exported_count = 0
        with open(self.nodes_file, mode, newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if overwrite or not file_exists:
                writer.writeheader()
            
            # Forensic Invariant Enforcement Gate (Phase 3 Final Mile)
            REQUIRED_FORENSIC_FIELDS = ["source_doc_id", "extraction_phase", "confidence_score", "bbox"]
            
            # Production Hardening Switch
            PRODUCTION_MODE = getattr(self, "production_mode", True)
            
            for node in nodes:
                try:
                    # 1. Final Invariant Check
                    for field in REQUIRED_FORENSIC_FIELDS:
                        val = node.properties.get(field)
                        if not val or str(val).strip() == "" or str(val).lower() == "none":
                            error_msg = f"Forensic Persistence Violation: Node {node.node_id} missing {field}"
                            logger.error(error_msg)
                            if PRODUCTION_MODE:
                                raise ForensicIntegrityError(error_msg)

                    # Prepare CSV row
                    row = {
                        'node_id:ID': node.node_id,
                        ':LABEL': ';'.join(node.labels),
                        'source_file': node.source_file,
                        'creation_timestamp': node.creation_timestamp,
                        'export_version': '2.3-hardened',
                        'logic_hash': self.logic_hashes.get("exporter", "unknown")
                    }
                    
                    # Add properties
                    for prop, value in node.properties.items():
                        # 2. Strict Serialization: json.dumps for dicts, strings for literals
                        if prop == "bbox" and isinstance(value, dict):
                            row[prop] = json.dumps(value, ensure_ascii=False)
                        elif isinstance(value, (dict, list)):
                            row[prop] = json.dumps(value, ensure_ascii=False)
                        elif isinstance(value, bool):
                            row[prop] = 'true' if value else 'false'
                        elif value is None:
                            row[prop] = ''
                        else:
                            row[prop] = str(value)
                    
                    # Fill missing properties with empty strings
                    for field in fieldnames:
                        if field not in row:
                            row[field] = ''
                    
                    writer.writerow(row)
                    exported_count += 1
                    
                    # Structural Immutability Enforcement (Phase 3 Hardening)
                    self._enforce_structural_immutability(node)
                    
                except ForensicIntegrityError as e:
                    raise e # Propagate unrecoverable security violation
                except Exception as e:
                    logger.error(f"Failed to export node {node.node_id}: {e}")
        
        logger.info(f"Exported {exported_count} nodes to {self.nodes_file}")
        
        # 4. Post-Serialization Verification (Ruthless Audit)
        if exported_count > 0:
            self._verify_csv_forensics(self.nodes_file, REQUIRED_FORENSIC_FIELDS)
            
        return exported_count

    def _verify_csv_forensics(self, file_path: Path, required_fields: List[str]):
        """Ruthlessly verify CSV for forensic completeness using pandas."""
        if pd is None:
            logger.warning("Pandas not installed. Using basic CSV check for forensics.")
            self._verify_csv_basic(file_path, required_fields)
            return

        try:
            df = pd.read_csv(file_path, dtype=str)
            logger.info(f"Validator examining {file_path.name}: {len(df)} rows, columns: {list(df.columns)}")
            
            for field in required_fields:
                if field not in df.columns:
                    raise ForensicIntegrityError(f"Critical Column Missing in CSV: {field}")
                
                # Check for null, empty, whitespace, or "None"
                invalid_mask = (
                    df[field].isna() | 
                    (df[field].str.strip() == "") | 
                    (df[field].str.lower() == "none") |
                    (df[field].str.lower() == "n/a") # Stricter in production
                )
                
                if invalid_mask.any():
                    invalid_count = invalid_mask.sum()
                    invalid_ids = df[invalid_mask]["node_id:ID"].tolist()[:5]
                    error_msg = f"Forensic Corruption Detected in {file_path.name}: Field '{field}' is empty for {invalid_count} nodes {invalid_ids}"
                    
                    # Log sample values
                    sample_indices = df[invalid_mask].index[:3]
                    for idx in sample_indices:
                        logger.debug(f"Sample invalid row {idx}: {df.iloc[idx].to_dict()}")
                        
                    logger.critical(error_msg)
                    raise ForensicIntegrityError(error_msg)
            
            logger.info(f"Forensic Certification Passed for {file_path.name}")
            self.stats.forensic_validated = True
            
        except Exception as e:
            if isinstance(e, ForensicIntegrityError):
                raise e
            logger.error(f"Post-serialization validation check failed: {e}")

    def _verify_csv_basic(self, file_path: Path, required_fields: List[str]):
        """Fallback basic CSV check if pandas is missing."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    for field in required_fields:
                        val = row.get(field)
                        if not val or val.strip() == "" or val.lower() in ["none", "n/a"]:
                            raise ForensicIntegrityError(f"Forensic field {field} is invalid for node {row.get('node_id:ID')}")
        except Exception as e:
            if isinstance(e, ForensicIntegrityError): raise e
            logger.error(f"Basic validation failed: {e}")
    
    def export_relationships(self, relationships: List[ExportRelationship], overwrite: bool = True) -> int:
        """
        Export relationships to CSV.
        """
        if not relationships:
            return 0
        
        # Collect all property names for dynamic columns
        all_properties = set()
        for rel in relationships:
            all_properties.update(rel.properties.keys())
        
        property_fieldnames = sorted(list(all_properties))
        fieldnames = self.relationship_fieldnames_base + property_fieldnames
        
        mode = 'w' if overwrite else 'a'
        file_exists = self.relationships_file.exists()
        
        exported_count = 0
        with open(self.relationships_file, mode, newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if overwrite or not file_exists:
                writer.writeheader()
            
            for rel in relationships:
                try:
                    # Prepare CSV row
                    row = {
                        ':START_ID': rel.start_node_id,
                        ':END_ID': rel.end_node_id,
                        ':TYPE': rel.type,
                        'relationship_id': rel.relationship_id,
                        'source_file': rel.source_file,
                        'creation_timestamp': rel.creation_timestamp,
                        'export_version': '2.3-hardened',
                        'logic_hash': self.logic_hashes.get("exporter", "unknown")
                    }
                    
                    # Add properties
                    for prop, value in rel.properties.items():
                        # Convert complex types to JSON strings
                        if isinstance(value, (dict, list)):
                            row[prop] = json.dumps(value, ensure_ascii=False)
                        elif isinstance(value, bool):
                            row[prop] = 'true' if value else 'false'
                        elif value is None:
                            row[prop] = ''
                        else:
                            row[prop] = str(value)
                    
                    # Fill missing properties with empty strings
                    for field in fieldnames:
                        if field not in row:
                            row[field] = ''
                    
                    writer.writerow(row)
                    exported_count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to export relationship {rel.relationship_id}: {e}")
        
        logger.info(f"Exported {exported_count} relationships to {self.relationships_file}")
        return exported_count
    
    def _enforce_structural_immutability(self, node: ExportNode):
        """
        Structural Immutability Gate (Hardened): 
        Prevents exporting any mutation to canonical nodes if the source is agentic.
        """
        is_immutable = node.properties.get("is_immutable", False)
        # Handle string booleans from flat dictionaries if needed
        if isinstance(is_immutable, str):
            is_immutable = is_immutable.lower() == "true"
            
        source_phase = node.source_file.lower()
        is_agent_source = "agent" in source_phase or "llm" in source_phase
        
        if is_immutable and is_agent_source:
            error_msg = f"Structural Immutability Violation: Attempt to export immutable node {node.node_id} from agentic source {source_phase}"
            logger.critical(error_msg)
            raise ForensicIntegrityError(error_msg)

    def generate_immutability_constraints(self) -> List[str]:
        """
        Generate Cypher for Neo4j triggers/constraints to enforce immutability at DB level.
        Requires APOC or Enterprise Edition for triggers.
        """
        statements = [
            "-- STRUCTURAL IMMUTABILITY CONSTRAINTS (HARDENED)",
            "-- Generated to prevent agentic mutation of canonical laws",
            "CALL apoc.trigger.add('block-immutable-mutation', ",
            "  'UNWIND $updatedNodes AS n MATCH (n) WHERE n.is_immutable = true RETURN fail(\"Mutation forbidden on immutable canonical nodes\")', ",
            "  {phase:'before'});"
        ]
        
        trigger_file = self.output_dir / "immutability_triggers.cypher"
        with open(trigger_file, 'w', encoding='utf-8') as f:
            f.write("\n".join(statements))
            
        return statements
    
    def generate_constraints_cypher(self, schema: KPKNeo4jSchema) -> List[str]:
        """Generate Cypher constraints."""
        constraints = [
            "-- NEO4J CONSTRAINTS FOR KPK FORESTRY KNOWLEDGE GRAPH",
            f"-- Generated: {datetime.now().isoformat()}",
            "--",
            ""
        ]
        
        for constraint in schema.constraints:
            if constraint.type == "UNIQUE":
                cypher = f"CREATE CONSTRAINT {constraint.name} IF NOT EXISTS FOR (n:{constraint.label}) REQUIRE n.{constraint.property} IS UNIQUE;"
            elif constraint.type == "EXISTS":
                cypher = f"CREATE CONSTRAINT {constraint.name} IF NOT EXISTS FOR (n:{constraint.label}) REQUIRE n.{constraint.property} IS NOT NULL;"
            elif constraint.type == "NODE_KEY":
                # Handle composite node key
                properties = constraint.property.split(',')
                props_str = ', '.join([f'n.{p}' for p in properties])
                cypher = f"CREATE CONSTRAINT {constraint.name} IF NOT EXISTS FOR (n:{constraint.label}) REQUIRE ({props_str}) IS NODE KEY;"
            else:
                continue
            
            constraints.append(cypher)
        
        # Write to file
        with open(self.constraints_file, 'w', encoding='utf-8') as f:
            f.write("\n".join(constraints))
        
        logger.info(f"Generated {len(constraints)} constraint statements to {self.constraints_file}")
        return constraints
    
    def generate_indexes_cypher(self, schema: KPKNeo4jSchema) -> List[str]:
        """Generate Cypher indexes."""
        indexes = [
            "-- NEO4J INDEXES FOR KPK FORESTRY KNOWLEDGE GRAPH",
            f"-- Generated: {datetime.now().isoformat()}",
            "--",
            ""
        ]
        
        for index in schema.indexes:
            if index.type == "INDEX":
                # Single or composite index
                if len(index.properties) == 1:
                    cypher = f"CREATE INDEX {index.name} IF NOT EXISTS FOR (n:{index.labels_or_types[0]}) ON (n.{index.properties[0]});"
                else:
                    props_str = ', '.join([f'n.{p}' for p in index.properties])
                    cypher = f"CREATE INDEX {index.name} IF NOT EXISTS FOR (n:{index.labels_or_types[0]}) ON ({props_str});"
            
            elif index.type == "FULLTEXT":
                # Full-text index
                labels_str = ', '.join([f'n:{label}' for label in index.labels_or_types])
                props_str = ', '.join([f'n.{p}' for p in index.properties])
                cypher = f"CREATE FULLTEXT INDEX {index.name} IF NOT EXISTS FOR ({labels_str}) ON EACH [{props_str}];"
            
            elif index.type == "LOOKUP":
                # Lookup index (for relationship types)
                cypher = f"CREATE LOOKUP INDEX {index.name} IF NOT EXISTS FOR ()-[r]-() ON (r.type);"
            
            else:
                continue
            
            indexes.append(cypher)
        
        # Write to file
        with open(self.indexes_file, 'w', encoding='utf-8') as f:
            f.write("\n".join(indexes))
        
        logger.info(f"Generated {len(indexes)} index statements to {self.indexes_file}")
        return indexes
    
    def generate_import_cypher(self) -> List[str]:
        """Generate Cypher for importing CSV files."""
        import_statements = [
            "-- NEO4J IMPORT SCRIPT FOR KPK FORESTRY KNOWLEDGE GRAPH",
            f"-- Generated: {datetime.now().isoformat()}",
            "--",
            "-- Step 1: Load nodes",
            f"LOAD CSV WITH HEADERS FROM 'file:///{self.nodes_file.name}' AS row",
            "CALL {{",
            "  WITH row",
            "  MERGE (n:Node {node_id: row.`node_id:ID`})",
            "  SET n += properties(row)",
            "  SET n:Loaded",
            "  WITH n, row",
            "  CALL apoc.create.addLabels(n, split(row.`:LABEL`, ';')) YIELD node",
            "  RETURN count(*)",
            "}} IN TRANSACTIONS OF 1000 ROWS;",
            "",
            "-- Step 2: Load relationships",
            f"LOAD CSV WITH HEADERS FROM 'file:///{self.relationships_file.name}' AS row",
            "CALL {{",
            "  WITH row",
            "  MATCH (a {{node_id: row.`:START_ID`}})",
            "  MATCH (b {{node_id: row.`:END_ID`}})",
            "  MERGE (a)-[r:RELATIONSHIP {{type: row.`:TYPE`}}]->(b)",
            "  SET r += properties(row)",
            "  WITH r, row",
            "  CALL apoc.refactor.setType(r, row.`:TYPE`) YIELD output",
            "  RETURN count(*)",
            "}} IN TRANSACTIONS OF 1000 ROWS;",
            "",
            "-- Step 3: Remove temporary labels",
            "MATCH (n:Loaded) REMOVE n:Loaded;"
        ]
        
        return import_statements

class Neo4jCypherGenerator:
    """Generates Cypher statements for direct Neo4j import."""
    
    def __init__(self):
        self.statements = []
        self.batch_size = 100
        
        logger.info("Cypher generator initialized")
    
    def generate_node_cypher(self, node: ExportNode) -> str:
        """Generate Cypher CREATE statement for a node."""
        # Prepare properties
        props = []
        for key, value in node.properties.items():
            if isinstance(value, str):
                # Escape single quotes
                escaped = value.replace("'", "\\'")
                props.append(f"{key}: '{escaped}'")
            elif isinstance(value, bool):
                props.append(f"{key}: {str(value).lower()}")
            elif value is None:
                props.append(f"{key}: null")
            elif isinstance(value, (dict, list)):
                # Convert to JSON string
                json_str = json.dumps(value, ensure_ascii=False).replace("'", "\\'")
                props.append(f"{key}: '{json_str}'")
            else:
                props.append(f"{key}: {value}")
        
        props_str = ', '.join(props)
        labels_str = ':'.join(node.labels)
        
        return f"CREATE (n:{labels_str} {{ {props_str} }});"
    
    def generate_relationship_cypher(self, rel: ExportRelationship) -> str:
        """Generate Cypher CREATE statement for a relationship."""
        # Prepare properties
        props = []
        for key, value in rel.properties.items():
            if isinstance(value, str):
                escaped = value.replace("'", "\\'")
                props.append(f"{key}: '{escaped}'")
            elif isinstance(value, bool):
                props.append(f"{key}: {str(value).lower()}")
            elif value is None:
                props.append(f"{key}: null")
            elif isinstance(value, (dict, list)):
                json_str = json.dumps(value, ensure_ascii=False).replace("'", "\\'")
                props.append(f"{key}: '{json_str}'")
            else:
                props.append(f"{key}: {value}")
        
        props_str = ', '.join(props) if props else ""
        
        return f"""
        MATCH (a {{node_id: '{rel.start_node_id}'}})
        MATCH (b {{node_id: '{rel.end_node_id}'}})
        CREATE (a)-[r:{rel.type} {{ {props_str} }}]->(b);
        """
    
    def generate_batch_cypher(self, nodes: List[ExportNode], 
                             relationships: List[ExportRelationship]) -> List[str]:
        """Generate batched Cypher statements."""
        statements = [
            "-- KPK FORESTRY KNOWLEDGE GRAPH IMPORT",
            f"-- Generated: {datetime.now().isoformat()}",
            f"-- Nodes: {len(nodes)}",
            f"-- Relationships: {len(relationships)}",
            "",
            "BEGIN"
        ]
        
        # Add nodes in batches
        for i in range(0, len(nodes), self.batch_size):
            batch = nodes[i:i + self.batch_size]
            batch_statements = []
            
            for node in batch:
                cypher = self.generate_node_cypher(node)
                batch_statements.append(cypher)
            
            statements.extend(batch_statements)
            
            if i + self.batch_size < len(nodes):
                statements.append("COMMIT")
                statements.append("BEGIN")
        
        # Add relationships in batches
        for i in range(0, len(relationships), self.batch_size):
            batch = relationships[i:i + self.batch_size]
            batch_statements = []
            
            for rel in batch:
                cypher = self.generate_relationship_cypher(rel)
                batch_statements.append(cypher)
            
            statements.extend(batch_statements)
            
            if i + self.batch_size < len(relationships):
                statements.append("COMMIT")
                statements.append("BEGIN")
        
        statements.append("COMMIT")
        
        return statements
    
    def save_cypher(self, statements: List[str], output_file: Path):
        """Save Cypher statements to file."""
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("\n".join(statements))
        
        logger.info(f"Saved {len(statements)} Cypher statements to {output_file}")

"""
NEO4J_EXPORTER.PY - Phase 6
Handles direct insertion of nodes and relationships into Neo4j.
"""
import logging
import os
from typing import List, Dict, Any

# Optional neo4j driver
try:
    from neo4j import GraphDatabase
    HAS_NEO4J = True
except ImportError:
    HAS_NEO4J = False

from preprocessing_pipeline.common.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

logger = logging.getLogger(__name__)

class Neo4jExporter:
    """
    Exports structured data to Neo4j Database.
    """
    
    def __init__(self):
        self.driver = None
        if HAS_NEO4J:
            try:
                self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
                logger.info("Connected to Neo4j.")
            except Exception as e:
                logger.error(f"Failed to connect to Neo4j: {e}")
        else:
            logger.warning("Neo4j driver not installed.")

    def close(self):
        if self.driver:
            self.driver.close()

    def export_batch(self, nodes: List[Dict], relationships: List[Dict]):
        """
        Export nodes and relationships in a batch transaction.
        """
        if not self.driver:
            logger.warning("No Neo4j connection. Skipping export.")
            return

        with self.driver.session() as session:
            # 1. atomic merge for nodes
            for node in nodes:
                session.execute_write(self._merge_node, node)
            
            # 2. atomic merge for relationships
            for rel in relationships:
                session.execute_write(self._merge_relationship, rel)
                
        logger.info(f"Exported {len(nodes)} nodes and {len(relationships)} relationships to Neo4j.")

    @staticmethod
    def _flatten_properties(props: Dict) -> Dict:
        """Flatten nested dictionaries and convert to Neo4j-compatible types."""
        flattened = {}
        for key, value in props.items():
            if isinstance(value, dict):
                # Flatten nested dict: convert to JSON string
                flattened[key] = json.dumps(value, ensure_ascii=False)
            elif isinstance(value, list):
                # Check if list contains primitives
                if all(isinstance(item, (str, int, float, bool, type(None))) for item in value):
                    flattened[key] = value
                else:
                    # Convert complex list to JSON string
                    flattened[key] = json.dumps(value, ensure_ascii=False)
            elif isinstance(value, (str, int, float, bool, type(None))):
                flattened[key] = value
            else:
                # Convert any other type to string
                flattened[key] = str(value)
        return flattened
    
    @staticmethod
    def _merge_node(tx, node: Dict):
        import json
        
        # Handle labels (could be list "labels" or string "label")
        labels = node.get("labels", [])
        if not labels and "label" in node:
            labels = [node["label"]]
        if not labels:
            labels = ["Entity"]
            
        # Primary label for MERGE
        primary_label = labels[0]
        
        # Prepare properties
        # 1. Start with base fields from GraphNode, excluding structural ones
        excluded_keys = ["labels", "label", "node_id", "properties", "type"]
        final_props = {k:v for k,v in node.items() if k not in excluded_keys}
        
        # 2. Merge with user properties (unpacking the nested dict)
        user_props = node.get("properties", {})
        if isinstance(user_props, dict):
            final_props.update(user_props)
        
        # 3. Flatten for Neo4j (convert nested dicts/lists to JSON strings)
        flat_props = Neo4jExporter._flatten_properties(final_props)
        
        # Build Query
        # MERGE on primary label and ID
        query = f"MERGE (n:`{primary_label}` {{node_id: $node_id}}) SET n += $props"
        
        # Add extra labels if any
        if len(labels) > 1:
            # sanitize labels just in case
            extra_labels = ":".join([f"`{l.replace('`', '')}`" for l in labels[1:]])
            query += f", n:{extra_labels}"
            
        tx.run(query, node_id=node.get("node_id"), props=flat_props)

    @staticmethod
    def _merge_relationship(tx, rel: Dict):
        import json
        
        # Determine relationship type
        r_type = rel.get("type", "RELATED_TO")
        
        # Determine start/end IDs (handle both GraphNode 'start_node_id' and mapped 'from_id' formats)
        start_id = rel.get("start_node_id") or rel.get("from_id")
        end_id = rel.get("end_node_id") or rel.get("to_id")
        
        if not start_id or not end_id:
            return # Skip invalid relationships
            
        # Prepare properties
        excluded_keys = ["relationship_id", "start_node_id", "end_node_id", "from_id", "to_id", "type", "properties", "rel_id"]
        final_props = {k:v for k,v in rel.items() if k not in excluded_keys}
        
        # Merge with user properties
        user_props = rel.get("properties", {})
        if isinstance(user_props, dict):
            final_props.update(user_props)
            
        # Flatten
        flat_props = Neo4jExporter._flatten_properties(final_props)
        
        query = f"""
        MATCH (a {{node_id: $start_id}})
        MATCH (b {{node_id: $end_id}})
        MERGE (a)-[r:`{r_type}`]->(b)
        SET r += $props
        """
        tx.run(query, start_id=start_id, end_id=end_id, props=flat_props)
    
class KPKNeo4jExporter:
    """Main class for exporting KPK forestry graph to Neo4j."""
    
    def __init__(self, config: Neo4jConfig, schema: Optional[KPKNeo4jSchema] = None):
        self.config = config
        if not self.config.validate():
            raise ValueError("Invalid Neo4j configuration")
        
        self.schema = schema or KPKNeo4jSchema()
        self.csv_exporter = None
        self.cypher_generator = Neo4jCypherGenerator()
        
        # Statistics
        self.statistics = ExportStatistics()
        self.export_timestamp = datetime.now().isoformat()
        
        logger.info(f"KPKNeo4jExporter initialized with config: {self.config.export_format}")
    
    def export_graph_data(self, graph_data: Dict[str, Any]) -> ExportStatistics:
        """
        Export graph data to Neo4j format.
        
        Args:
            graph_data: Graph data from previous phases
            
        Returns:
            Export statistics
        """
        start_time = datetime.now()
        
        try:
            # Extract nodes and relationships
            nodes = self._extract_nodes(graph_data)
            relationships = self._extract_relationships(graph_data)
            
            # Validate data
            validation_result = self._validate_export_data(nodes, relationships)
            if not validation_result["valid"]:
                logger.error(f"Validation failed: {validation_result['errors']}")
                self.statistics.errors.extend(validation_result["errors"])
                return self.statistics
            
            # Export based on format
            if self.config.export_format in ["csv", "both"]:
                self._export_to_csv(nodes, relationships)
            
            if self.config.export_format in ["cypher", "both"]:
                self._export_to_cypher(nodes, relationships)
            
            # Update statistics
            self._update_statistics(nodes, relationships, start_time)
            
            # Generate additional files
            self._generate_additional_files()
            
            logger.info(f"Export completed successfully: {self.statistics.total_nodes} nodes, "
                       f"{self.statistics.total_relationships} relationships")
            
        except Exception as e:
            logger.error(f"Export failed: {e}")
            self.statistics.errors.append(str(e))
        
        return self.statistics
    
    def _extract_nodes(self, graph_data: Dict[str, Any]) -> List[ExportNode]:
        """Extract nodes from graph data."""
        nodes = []
        
        # Handle different input formats
        if "nodes" in graph_data:
            # Direct nodes list
            for node_data in graph_data["nodes"]:
                node = self._create_export_node(node_data)
                if node:
                    nodes.append(node)
        
        elif "graph" in graph_data and "nodes" in graph_data["graph"]:
            # Nested structure
            for node_data in graph_data["graph"]["nodes"]:
                node = self._create_export_node(node_data)
                if node:
                    nodes.append(node)
        
        elif "entities" in graph_data:
            # Entity-based structure
            for entity_data in graph_data["entities"]:
                node = self._create_export_node_from_entity(entity_data)
                if node:
                    nodes.append(node)
        
        logger.info(f"Extracted {len(nodes)} nodes from graph data")
        return nodes
    
    def _create_export_node(self, node_data: Dict[str, Any]) -> Optional[ExportNode]:
        """Create ExportNode from node data."""
        try:
            node_id = node_data.get("node_id")
            if not node_id:
                node_id = self._generate_node_id(node_data)
            
            labels = node_data.get("labels", [])
            if not labels and "label" in node_data:
                labels = [node_data["label"]]
            
            # Ensure we have at least one label
            if not labels:
                labels = ["Entity"]
            
            # Extract properties (everything except special fields)
            properties = {}
            for key, value in node_data.items():
                if key not in ["node_id", "labels", "label", "source_file"]:
                    properties[key] = value
            
            # Add KPK-specific enhancements
            properties = self._enhance_node_properties(properties, labels)
            
            return ExportNode(
                node_id=node_id,
                labels=labels,
                properties=properties,
                source_file=node_data.get("source_file", "unknown"),
                creation_timestamp=node_data.get("creation_timestamp", self.export_timestamp)
            )
            
        except Exception as e:
            logger.error(f"Failed to create export node: {e}")
            return None
    
    def _create_export_node_from_entity(self, entity_data: Dict[str, Any]) -> Optional[ExportNode]:
        """Create ExportNode from entity data."""
        try:
            # Map entity type to Neo4j label
            entity_type = entity_data.get("entity_type", "Entity")
            labels = [entity_type]
            
            # Generate node ID
            entity_id = entity_data.get("entity_id")
            if not entity_id:
                entity_id = f"{entity_type}_{hashlib.md5(str(entity_data).encode()).hexdigest()[:8]}"
            
            # Extract properties
            properties = entity_data.get("properties", {})
            properties["entity_id"] = entity_id
            
            # Add confidence if available
            if "confidence" in entity_data:
                properties["confidence"] = entity_data["confidence"]
            
            # Add source phase if available
            if "source_phase" in entity_data:
                properties["pipeline_source"] = entity_data["source_phase"]
            
            return ExportNode(
                node_id=entity_id,
                labels=labels,
                properties=properties,
                source_file=entity_data.get("source_document", "unknown")
            )
            
        except Exception as e:
            logger.error(f"Failed to create export node from entity: {e}")
            return None
    
    def _generate_node_id(self, node_data: Dict[str, Any]) -> str:
        """Generate node ID from node data."""
        # Try to generate meaningful ID
        if "title" in node_data:
            title = node_data["title"]
            year = node_data.get("year", "")
            return f"{title}_{year}".replace(" ", "_").lower()[:50]
        
        if "common_name" in node_data:
            name = node_data["common_name"]
            return f"species_{name}".replace(" ", "_").lower()
        
        if "name" in node_data:
            name = node_data["name"]
            loc_type = node_data.get("type", "location")
            return f"{loc_type}_{name}".replace(" ", "_").lower()
        
        # Fallback to hash
        data_str = json.dumps(node_data, sort_keys=True)
        return f"node_{hashlib.md5(data_str.encode()).hexdigest()[:12]}"
    
    def _enhance_node_properties(self, properties: Dict[str, Any], labels: List[str]) -> Dict[str, Any]:
        """Enhance node properties with KPK-specific data."""
        enhanced = properties.copy()
        
        # Add export metadata
        enhanced["export_timestamp"] = self.export_timestamp
        enhanced["export_version"] = "1.0-kpk"
        
        # Add KPK-specific flags
        if any(label in ["Law", "Section", "Species", "Officer", "Location"] for label in labels):
            enhanced["kpk_entity"] = True
            
            # Check if this is specifically KPK
            if self._is_kpk_entity(enhanced, labels):
                enhanced["kpk_specific"] = True
                enhanced["jurisdiction"] = "KPK"
        
        # Add quality indicators
        if "confidence" in enhanced:
            conf = enhanced["confidence"]
            if conf < 0.7:
                enhanced["needs_review"] = True
        
        # Ensure required properties
        if "Law" in labels and "jurisdiction" not in enhanced:
            enhanced["jurisdiction"] = "unknown"
        
        if "Species" in labels and "legal_status" not in enhanced:
            enhanced["legal_status"] = "unknown"
        
        return enhanced
    
    def _is_kpk_entity(self, properties: Dict[str, Any], labels: List[str]) -> bool:
        """Check if entity is KPK-specific."""
        # Check properties for KPK indicators
        prop_str = str(properties).lower()
        kpk_indicators = ["kpk", "khyber", "pakhtunkhwa", "hazara", "nwfp",
                         "abbottabad", "swat", "mansehra", "malakand", "dir"]
        
        if any(indicator in prop_str for indicator in kpk_indicators):
            return True
        
        # Check specific properties
        if properties.get("jurisdiction") == "KPK":
            return True
        
        if properties.get("kpk_specific") is True:
            return True
        
        # Check labels
        if any("kpk" in label.lower() for label in labels):
            return True
        
        return False
    
    def _extract_relationships(self, graph_data: Dict[str, Any]) -> List[ExportRelationship]:
        """Extract relationships from graph data."""
        relationships = []
        
        # Handle different input formats
        if "relationships" in graph_data:
            # Direct relationships list
            for rel_data in graph_data["relationships"]:
                rel = self._create_export_relationship(rel_data)
                if rel:
                    relationships.append(rel)
        
        elif "graph" in graph_data and "relationships" in graph_data["graph"]:
            # Nested structure
            for rel_data in graph_data["graph"]["relationships"]:
                rel = self._create_export_relationship(rel_data)
                if rel:
                    relationships.append(rel)
        
        elif "relations" in graph_data:
            # Alternative naming
            for rel_data in graph_data["relations"]:
                rel = self._create_export_relationship(rel_data)
                if rel:
                    relationships.append(rel)
        
        logger.info(f"Extracted {len(relationships)} relationships from graph data")
        return relationships
    
    def _create_export_relationship(self, rel_data: Dict[str, Any]) -> Optional[ExportRelationship]:
        """Create ExportRelationship from relationship data."""
        try:
            rel_id = rel_data.get("relationship_id")
            if not rel_id:
                rel_id = f"rel_{hashlib.md5(str(rel_data).encode()).hexdigest()[:12]}"
            
            start_id = rel_data.get("start_node_id") or rel_data.get("from_id") or rel_data.get(":START_ID")
            end_id = rel_data.get("end_node_id") or rel_data.get("to_id") or rel_data.get(":END_ID")
            rel_type = rel_data.get("type") or rel_data.get(":TYPE") or "RELATES_TO"
            
            if not start_id or not end_id:
                logger.warning(f"Missing start or end ID for relationship: {rel_data}")
                return None
            
            # Extract properties
            properties = {}
            for key, value in rel_data.items():
                if key not in ["relationship_id", "start_node_id", "end_node_id", "from_id", 
                              "to_id", "type", ":START_ID", ":END_ID", ":TYPE", "source_file"]:
                    properties[key] = value
            
            # Enhance with KPK data
            properties = self._enhance_relationship_properties(properties, rel_type)
            
            return ExportRelationship(
                relationship_id=rel_id,
                start_node_id=start_id,
                end_node_id=end_id,
                type=rel_type,
                properties=properties,
                source_file=rel_data.get("source_file", "unknown")
            )
            
        except Exception as e:
            logger.error(f"Failed to create export relationship: {e}")
            return None
    
    def _enhance_relationship_properties(self, properties: Dict[str, Any], rel_type: str) -> Dict[str, Any]:
        """Enhance relationship properties with KPK-specific data."""
        enhanced = properties.copy()
        
        # Add export metadata
        enhanced["export_timestamp"] = self.export_timestamp
        enhanced["export_version"] = "1.0-kpk"
        
        # Add relationship-specific enhancements
        if rel_type == "IMPOSES":
            if "currency" not in enhanced:
                enhanced["currency"] = "PKR"
            enhanced["kpk_enforceable"] = True
        
        elif rel_type == "APPLIES_TO":
            enhanced["jurisdiction_verified"] = enhanced.get("jurisdiction_verified", False)
        
        elif rel_type == "PROTECTS_SPECIES":
            enhanced["protection_level"] = enhanced.get("protection_level", "standard")
        
        elif rel_type == "ABSTAINS_FROM":
            enhanced["requires_human_review"] = True
        
        return enhanced
    
    def _validate_export_data(self, nodes: List[ExportNode], 
                            relationships: List[ExportRelationship]) -> Dict[str, Any]:
        """Validate export data against schema."""
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "node_validation": {},
            "relationship_validation": {}
        }
        
        # Validate nodes
        node_ids = set()
        for node in nodes:
            # Check for duplicate node IDs
            if node.node_id in node_ids:
                validation_result["warnings"].append(f"Duplicate node ID: {node.node_id}")
            else:
                node_ids.add(node.node_id)
            
            # Validate against schema
            is_valid, errors = self.schema.validate_node(node)
            if not is_valid:
                validation_result["errors"].extend(errors)
                validation_result["valid"] = False
        
        # Validate relationships
        relationship_keys = set()
        for rel in relationships:
            # Check for missing nodes
            if rel.start_node_id not in node_ids:
                validation_result["errors"].append(f"Start node not found: {rel.start_node_id}")
                validation_result["valid"] = False
            
            if rel.end_node_id not in node_ids:
                validation_result["errors"].append(f"End node not found: {rel.end_node_id}")
                validation_result["valid"] = False
            
            # Check for duplicate relationships
            rel_key = f"{rel.start_node_id}-{rel.type}-{rel.end_node_id}"
            if rel_key in relationship_keys:
                validation_result["warnings"].append(f"Duplicate relationship: {rel_key}")
            else:
                relationship_keys.add(rel_key)
            
            # Validate against schema
            is_valid, errors = self.schema.validate_relationship(rel)
            if not is_valid:
                validation_result["errors"].extend(errors)
                validation_result["valid"] = False
        
        validation_result["node_validation"] = {
            "total_nodes": len(nodes),
            "unique_node_ids": len(node_ids),
            "duplicate_node_ids": len(nodes) - len(node_ids)
        }
        
        validation_result["relationship_validation"] = {
            "total_relationships": len(relationships),
            "unique_relationships": len(relationship_keys),
            "duplicate_relationships": len(relationships) - len(relationship_keys)
        }
        
        return validation_result
    
    def _export_to_csv(self, nodes: List[ExportNode], relationships: List[ExportRelationship]):
        """Export data to CSV format."""
        # Determine CSV directory
        if self.config.csv_directory:
            csv_dir = Path(self.config.csv_directory)
        else:
            csv_dir = Path("neo4j_export") / "csv"
        
        csv_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize CSV exporter
        self.csv_exporter = Neo4jCSVExporter(csv_dir)
        
        # Export nodes
        nodes_exported = self.csv_exporter.export_nodes(nodes)
        
        # Export relationships
        relationships_exported = self.csv_exporter.export_relationships(relationships)
        
        # Generate constraints and indexes
        if self.config.create_constraints:
            self.csv_exporter.generate_constraints_cypher(self.schema)
        
        if self.config.create_indexes:
            self.csv_exporter.generate_indexes_cypher(self.schema)
        
        # Generate import script
        import_cypher = self.csv_exporter.generate_import_cypher()
        import_file = csv_dir / "import.cypher"
        with open(import_file, 'w', encoding='utf-8') as f:
            f.write("\n".join(import_cypher))
        
        logger.info(f"CSV export completed: {nodes_exported} nodes, {relationships_exported} relationships")
    
    def _export_to_cypher(self, nodes: List[ExportNode], relationships: List[ExportRelationship]):
        """Export data to Cypher format."""
        # Determine output directory
        cypher_dir = Path("neo4j_export") / "cypher"
        cypher_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate Cypher statements
        cypher_statements = self.cypher_generator.generate_batch_cypher(nodes, relationships)
        
        # Save to file
        cypher_file = cypher_dir / "import.cypher"
        self.cypher_generator.save_cypher(cypher_statements, cypher_file)
        
        # Generate constraints and indexes
        if self.config.create_constraints:
            constraints_file = cypher_dir / "constraints.cypher"
            constraints = self.csv_exporter.generate_constraints_cypher(self.schema) if self.csv_exporter \
                         else self._generate_constraints_cypher()
            with open(constraints_file, 'w', encoding='utf-8') as f:
                f.write("\n".join(constraints))
        
        if self.config.create_indexes:
            indexes_file = cypher_dir / "indexes.cypher"
            indexes = self.csv_exporter.generate_indexes_cypher(self.schema) if self.csv_exporter \
                     else self._generate_indexes_cypher()
            with open(indexes_file, 'w', encoding='utf-8') as f:
                f.write("\n".join(indexes))
        
        logger.info(f"Cypher export completed: {len(cypher_statements)} statements")
    
    def _generate_constraints_cypher(self) -> List[str]:
        """Generate constraints Cypher without CSV exporter."""
        constraints = [
            "-- CONSTRAINTS FOR KPK FORESTRY GRAPH",
            f"-- Generated: {datetime.now().isoformat()}",
            ""
        ]
        
        for constraint in self.schema.constraints:
            if constraint.type == "UNIQUE":
                constraints.append(f"CREATE CONSTRAINT {constraint.name} IF NOT EXISTS FOR (n:{constraint.label}) REQUIRE n.{constraint.property} IS UNIQUE;")
        
        return constraints
    
    def _generate_indexes_cypher(self) -> List[str]:
        """Generate indexes Cypher without CSV exporter."""
        indexes = [
            "-- INDEXES FOR KPK FORESTRY GRAPH",
            f"-- Generated: {datetime.now().isoformat()}",
            ""
        ]
        
        for index in self.schema.indexes[:5]:  # First 5 indexes
            if index.type == "INDEX":
                indexes.append(f"CREATE INDEX {index.name} IF NOT EXISTS FOR (n:{index.labels_or_types[0]}) ON (n.{index.properties[0]});")
        
        return indexes
    
    def _update_statistics(self, nodes: List[ExportNode], 
                          relationships: List[ExportRelationship],
                          start_time: datetime):
        """Update export statistics."""
        end_time = datetime.now()
        
        self.statistics.total_nodes = len(nodes)
        self.statistics.total_relationships = len(relationships)
        self.statistics.export_duration = (end_time - start_time).total_seconds()
        
        # Count nodes by label
        for node in nodes:
            for label in node.labels:
                self.statistics.nodes_by_label[label] = self.statistics.nodes_by_label.get(label, 0) + 1
        
        # Count relationships by type
        for rel in relationships:
            self.statistics.relationships_by_type[rel.type] = \
                self.statistics.relationships_by_type.get(rel.type, 0) + 1
        
        # Calculate file sizes
        export_dir = Path("neo4j_export")
        if export_dir.exists():
            for file_path in export_dir.rglob("*"):
                if file_path.is_file():
                    self.statistics.file_sizes[file_path.name] = file_path.stat().st_size
    
    def _generate_additional_files(self):
        """Generate additional export files."""
        export_dir = Path("neo4j_export")
        export_dir.mkdir(exist_ok=True)
        
        # Generate metadata file
        metadata = {
            "export_summary": {
                "timestamp": self.export_timestamp,
                "total_nodes": self.statistics.total_nodes,
                "total_relationships": self.statistics.total_relationships,
                "export_duration": self.statistics.export_duration
            },
            "node_distribution": self.statistics.nodes_by_label,
            "relationship_distribution": self.statistics.relationships_by_type,
            "configuration": self.config.__dict__,
            "kpk_specifics": {
                "kpk_nodes": sum(1 for label in self.statistics.nodes_by_label.keys() 
                               if "kpk" in label.lower() or label in ["Law", "Section", "Species", "Officer", "Location"]),
                "abstention_nodes": self.statistics.nodes_by_label.get("Abstention", 0),
                "protected_species": self.statistics.nodes_by_label.get("Species", 0)
            },
            "quality_indicators": {
                "node_validation_errors": len([e for e in self.statistics.errors if "node" in e.lower()]),
                "relationship_validation_errors": len([e for e in self.statistics.errors if "relationship" in e.lower()]),
                "duplicate_nodes": self.statistics.total_nodes - len(set(self.statistics.nodes_by_label.keys())),
                "orphaned_relationships": 0  # Would need to calculate
            }
        }
        
        metadata_file = export_dir / "export_metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        # Generate README
        readme_content = self._generate_readme()
        readme_file = export_dir / "README.md"
        with open(readme_file, 'w', encoding='utf-8') as f:
            f.write(readme_content)
        
        logger.info("Additional files generated: export_metadata.json, README.md")
    
    def _generate_readme(self) -> str:
        """Generate README file for the export."""
        return f"""# KPK Forestry Knowledge Graph - Neo4j Export

## Overview
This export contains the KPK Forestry Knowledge Graph with {self.statistics.total_nodes} nodes and {self.statistics.total_relationships} relationships.

## Export Details
- **Export Timestamp**: {self.export_timestamp}
- **Export Format**: {self.config.export_format}
- **Export Duration**: {self.statistics.export_duration:.2f} seconds

- .csv: Node and relationship data
- .cypher: Import statements
- .json: Metadata and analysis reports

## Importing to Neo4j
Use the generated `import.cypher` or `neo4j-admin import` tool with the provided CSVs.
"""
