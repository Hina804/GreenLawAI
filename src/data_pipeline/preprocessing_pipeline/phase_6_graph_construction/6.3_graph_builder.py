"""
6.3_GRAPH_BUILDER.PY - Builds Neo4j Knowledge Graph from Mapped Entities
Transforms mapped entities from 6.2_graph_mapper.py into Neo4j-compatible format.
Features KPK specialization, abstention framework integration, and pipeline tracking.
"""

import json
import csv
import logging
from typing import Dict, List, Any, Optional, Union, Tuple, Set
from pathlib import Path
from dataclasses import dataclass, asdict, field
from datetime import datetime
from collections import defaultdict, Counter
import hashlib
import re
import uuid
import warnings

# Global placeholders for RAG components
LegalChunker = None
EmbeddingGenerator = None
FAISSIndexer = None
HybridLinker = None
Neo4jExporter = None

# Import from Phase 6 package
try:
    from preprocessing_pipeline.phase_6_graph_construction.graph_schema_kpk import (
        NodeLabel, RelationshipType, JurisdictionLevel,
        PipelineEntity, PipelineRelationship, KPKNodeSchema,
        KPKRelationshipSchema, AbstentionReason, GraphConstructionInterface,
        KPKGraphSchema
    )
    # Import RAG components from package
    try:
        from preprocessing_pipeline.phase_6_graph_construction import (
            LegalChunker as Phase6LegalChunker, 
            EmbeddingGenerator as Phase6EmbeddingGenerator, 
            FAISSIndexer as Phase6FAISSIndexer,
            HybridLinker as Phase6HybridLinker, 
            Neo4jExporter as Phase6Neo4jExporter,
            ExportNode as Phase6ExportNode,
            ExportRelationship as Phase6ExportRelationship
        )
        LegalChunker = Phase6LegalChunker
        EmbeddingGenerator = Phase6EmbeddingGenerator
        FAISSIndexer = Phase6FAISSIndexer
        HybridLinker = Phase6HybridLinker
        Neo4jExporter = Phase6Neo4jExporter
        ExportNode = Phase6ExportNode
        ExportRelationship = Phase6ExportRelationship
    except (ImportError, ValueError, AttributeError):
        class ExportNode: pass
        class ExportRelationship: pass
except (ImportError, ValueError, ModuleNotFoundError):
    class KPKGraphSchema: pass
    class NodeLabel: pass
    class RelationshipType: pass
    class JurisdictionLevel: 
        PROVINCIAL = "Provincial"
        DIVISIONAL = "Divisional"
        RANGE_LEVEL = "Range"
        BEAT_LEVEL = "Beat"
        DISTRICT = "District"
        class AbstentionReason: pass
        class PipelineEntity: pass
        class PipelineRelationship: pass
        class KPKNodeSchema: pass
        class KPKRelationshipSchema: pass
        class GraphConstructionInterface: pass

    warnings.warn("Could not import from .graph_schema_kpk, falling back to absolute import. Ensure module structure is correct.")

# Note: components are now imported directly from the package, which uses load_numeric internally.

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class GraphNode:
    """Enhanced Neo4j node with KPK specialization."""
    node_id: str
    labels: List[str]
    properties: Dict[str, Any]
    source_document: str
    extraction_confidence: float
    pipeline_source: str = "graph_builder"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    version: str = "2.3"
    
    def to_csv_row(self) -> Dict[str, str]:
        """Convert to Neo4j CSV import format."""
        # Neo4j CSV format requires special handling
        row = {
            'node_id:ID': self.node_id,
            ':LABEL': ';'.join(self.labels),
            'source_document': self.source_document,
            'extraction_confidence': str(self.extraction_confidence),
            'pipeline_source': self.pipeline_source,
            'created_at': self.created_at,
            'version': self.version
        }
        
        # Add properties (JSON encoded for complex values)
        for key, value in self.properties.items():
            if isinstance(value, (dict, list)):
                row[key] = json.dumps(value, ensure_ascii=False)
            elif isinstance(value, bool):
                row[key] = 'true' if value else 'false'
            elif value is None:
                row[key] = ''
            else:
                row[key] = str(value)
        
        return row
    
    def to_cypher_create(self) -> str:
        """Generate Cypher CREATE statement."""
        labels_str = ':'.join(self.labels)
        props_str = ', '.join([f'{k}: ${k}' for k in self.properties.keys()])
        return f"CREATE (n:{labels_str} {{ {props_str} }})"

@dataclass  
class GraphRelationship:
    """Enhanced Neo4j relationship with KPK specialization."""
    relationship_id: str
    start_node_id: str
    end_node_id: str
    type: str
    properties: Dict[str, Any]
    source_document: str
    confidence: float
    pipeline_source: str = "graph_builder"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_csv_row(self) -> Dict[str, str]:
        """Convert to Neo4j CSV import format."""
        row = {
            ':START_ID': self.start_node_id,
            ':END_ID': self.end_node_id,
            ':TYPE': self.type,
            'relationship_id': self.relationship_id,
            'source_document': self.source_document,
            'confidence': str(self.confidence),
            'pipeline_source': self.pipeline_source,
            'created_at': self.created_at
        }
        
        # Add properties
        for key, value in self.properties.items():
            if isinstance(value, (dict, list)):
                row[key] = json.dumps(value, ensure_ascii=False)
            elif isinstance(value, bool):
                row[key] = 'true' if value else 'false'
            elif value is None:
                row[key] = ''
            else:
                row[key] = str(value)
        
        return row
    
    def to_cypher_create(self, start_label: str, end_label: str) -> str:
        """Generate Cypher CREATE relationship statement."""
        props_str = ', '.join([f'{k}: ${k}' for k in self.properties.keys()])
        return f"""
            MATCH (a:{start_label} {{node_id: $start_id}})
            MATCH (b:{end_label} {{node_id: $end_id}})
            CREATE (a)-[r:{self.type} {{ {props_str} }}]->(b)
        """

@dataclass
class KPKAbstentionNode:
    """KPK-specific abstention node for uncertain/incomplete data."""
    abstention_id: str
    reason: str
    entity_type: str
    context: Dict[str, Any]
    related_node_ids: List[str]
    confidence: float
    requires_human_review: bool
    pipeline_phase: str
    quality_gate_trigger: Optional[str] = None
    suggested_resolution: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_graph_node(self) -> GraphNode:
        """Convert to GraphNode for Neo4j."""
        return GraphNode(
            node_id=f"ABSTENTION_{self.abstention_id}",
            labels=['Abstention', self.entity_type, 'Uncertainty'],
            properties={
                'abstention_id': self.abstention_id,
                'reason': self.reason,
                'entity_type': self.entity_type,
                'context': self.context,
                'confidence': self.confidence,
                'requires_human_review': self.requires_human_review,
                'pipeline_phase': self.pipeline_phase,
                'quality_gate_trigger': self.quality_gate_trigger,
                'suggested_resolution': self.suggested_resolution,
                'created_at': self.created_at,
                'is_abstention': True,
                'kpk_specific': True
            },
            source_document='graph_builder',
            extraction_confidence=self.confidence,
            pipeline_source=self.pipeline_phase
        )

@dataclass
class GraphConstructionReport:
    """Report of graph construction process."""
    timestamp: str
    nodes_created: int
    relationships_created: int
    abstention_nodes: int
    validation_errors: List[str]
    quality_indicators: Dict[str, Any]
    file_paths: Dict[str, Path]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class KPKGraphBuilder:
    """
    Main graph builder for KPK forestry knowledge graph.
    Converts mapped entities into Neo4j-compatible format with KPK specialization.
    """
    
    def __init__(self, config: Optional[Any] = None, schema: Optional[KPKGraphSchema] = None):
        self.config = config
        self.schema = schema or KPKGraphSchema()
        self.nodes: List[GraphNode] = []
        self.relationships: List[GraphRelationship] = []
        self.abstention_nodes: List[KPKAbstentionNode] = []
        self.node_registry: Dict[str, GraphNode] = {}
        self.relationship_counter = 0
        
        # Statistics and tracking
        self.stats = defaultdict(int)
        self.validation_errors = []
        self.pipeline_tracking = []
        
        # KPK-specific configurations
        self.kpk_config = self._load_kpk_config()
        
        # Initialize GraphRAG Components
        self._init_rag_components()
        
        logger.info("KPK GraphBuilder initialized with enhanced schema and RAG capabilities")

    def _init_rag_components(self):
        """Initialize GraphRAG sub-components if available."""
        self.chunker = None
        self.embedder = None
        self.indexer = None
        self.linker = None
        self.exporter = None
        
        try:
            self.chunker = LegalChunker() if LegalChunker else None
            self.embedder = EmbeddingGenerator() if EmbeddingGenerator else None
            self.indexer = FAISSIndexer() if FAISSIndexer else None
            self.linker = HybridLinker() if HybridLinker else None
            
            # Phase 6 Hardening: Propagate PRODUCTION_HARDENED to exporter
            is_hardened = getattr(self.config, "PRODUCTION_HARDENED", True) if self.config else True
            if Neo4jExporter:
                # Both Neo4jExporter and Neo4jCSVExporter are compatible
                try:
                    self.exporter = Neo4jExporter(production_mode=is_hardened)
                except TypeError:
                    # Fallback if class doesn't support the param yet
                    self.exporter = Neo4jExporter()
            else:
                self.exporter = None
        except Exception as e:
            logger.error(f"Failed to initialize RAG components: {e}")


    def _load_kpk_config(self) -> Dict[str, Any]:
        """Load KPK-specific configuration."""
        return {
            "jurisdiction": "KPK",
            "default_currency": "PKR",
            "officer_hierarchy": ["CCF", "CF", "DFO", "SDFO", "RO", "BG"],
            "protected_species": ["deodar", "kail", "fir", "spruce"],
            "divisions": ["Abbottabad", "Mansehra", "Swat", "Dir", "Malakand", "D.I.Khan", "Kohat", "Bannu"],
            "hazara_override": True,
            "penalty_multipliers": {
                "repeat_offense": 2.0,
                "protected_species": 1.5,
                "reserved_forest": 1.3
            }
        }
    
    def build_graph(self, mapped_data: Dict[str, Any]) -> Dict[str, Any]:
        """Compatibility alias for run_sequential_pipeline.py."""
        return self.build_graph_from_mapped_data(mapped_data)
    
    def build_graph_from_mapped_data(self, mapped_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build graph from mapped data (output of 6.2_graph_mapper.py).
        Also performs RAG steps: Chunking -> Embedding -> Indexing -> Linking.
        """
        logger.info("Building graph from mapped data...")
        
        # Reset state for new build
        self._reset_state()
        
        # Track pipeline phase
        self.pipeline_tracking.append({
            "phase": "6.3_graph_builder",
            "timestamp": datetime.now().isoformat(),
            "input_data_keys": list(mapped_data.keys())
        })
        
        # Extract nodes and relationships from mapped data
        mapped_nodes = mapped_data.get("nodes", [])
        mapped_relationships = mapped_data.get("relationships", [])
        node_id_map = mapped_data.get("node_id_map", {})
        metadata = mapped_data.get("metadata", {})
        
        logger.info(f"Processing {len(mapped_nodes)} mapped nodes and {len(mapped_relationships)} mapped relationships")
        
        # 1. Build Standard Graph Nodes & Relationships
        self._build_nodes_from_mapped(mapped_nodes, metadata)
        self._build_relationships_from_mapped(mapped_relationships, node_id_map, metadata)
        
        if "abstention_cases" in mapped_data.get("mapping_statistics", {}):
            self._add_abstention_nodes_from_mapped(mapped_data)
        
        self._add_kpk_specific_entities()
        
        # 2. GraphRAG Steps (Chunking & Embedding)
        rag_stats = {}
        if self.chunker and self.embedder:
            rag_stats = self._process_rag_pipeline(mapped_data, metadata)
            
        # 3. Export to Neo4j (DISABLED: Use explicit export_to_csv for production hardening)
        # if self.exporter:
        #     try:
        #         # Convert GraphNodes to dicts for exporter
        #         export_nodes = [asdict(n) for n in self.nodes]
        #         export_rels = [asdict(r) for r in self.relationships]
        #         self.exporter.export_batch(export_nodes, export_rels)
        #     except Exception as e:
        #         logger.error(f"Neo4j Export failed: {e}")
        
        # Validate graph
        validation_result = self._validate_graph()
        
        # Generate statistics
        stats = self._generate_statistics()
        
        # Generate quality report
        quality_report = self._generate_quality_report()
        
        logger.info(f"Graph built: {len(self.nodes)} nodes, {len(self.relationships)} relationships")
        
        # Prepare nodes and relationships for return
        nodes_by_type = {}
        for node in self.nodes:
            # Use primary label for grouping, fall back to first label
            label = node.labels[0] if node.labels else "Unknown"
            # Ensure proper serialization
            node_dict = asdict(node)
            if label not in nodes_by_type:
                nodes_by_type[label] = []
            nodes_by_type[label].append(node_dict)
            
        relationships_by_type = {}
        for rel in self.relationships:
            # Group by relationship type
            rel_type = rel.type
            rel_dict = asdict(rel)
            if rel_type not in relationships_by_type:
                relationships_by_type[rel_type] = []
            relationships_by_type[rel_type].append(rel_dict)

        return {
            'nodes_by_type': nodes_by_type,
            'relationships_by_type': relationships_by_type,
            'nodes': [asdict(n) for n in self.nodes], # Flat list for convenience
            'relationships': [asdict(r) for r in self.relationships],
            'build_summary': {
                'nodes_count': len(self.nodes),
                'relationships_count': len(self.relationships),
                'abstention_nodes_count': len(self.abstention_nodes),
                'build_timestamp': datetime.now().isoformat()
            },
            'statistics': stats,
            'rag_statistics': rag_stats,
            'validation': validation_result,
            'quality_report': quality_report,
            'pipeline_tracking': self.pipeline_tracking,
            'kpk_entities_summary': self._get_kpk_entities_summary()
        }

    def _process_rag_pipeline(self, mapped_data: Dict, metadata: Dict) -> Dict:
        """Execute Phase 6 RAG pipeline: Chunk -> Embed -> Index -> Link."""
        stats = {"chunks_created": 0, "embeddings_generated": 0}
        
        # Get raw text
        raw_text = metadata.get("raw_text") or mapped_data.get("raw_text")
        if not raw_text:
            logger.warning("No raw text found for RAG processing.")
            return stats

        # A. Chunking
        chunks = self.chunker.chunk(raw_text, doc_metadata=metadata)
        stats["chunks_created"] = len(chunks)
        
        if not chunks:
            return stats

        # B. Embedding
        texts = [c["chunk_text"] for c in chunks]
        embeddings = self.embedder.generate(texts)
        stats["embeddings_generated"] = len(embeddings)

        # C. Indexing
        if self.indexer:
            import numpy as np
            # CRITICAL FIX: create_index() must be called before add_vectors()
            # The indexer raises ValueError if self.index is None
            if self.indexer.index is None:
                dim = embeddings.shape[1] if hasattr(embeddings, 'shape') and len(embeddings.shape) > 1 else (len(embeddings[0]) if len(embeddings) > 0 else 384)
                self.indexer.create_index(int(dim))
            self.indexer.add_vectors(embeddings, chunks)

        # D. Linking (Hybrid) & Graph Augmentation
        if self.linker and hasattr(self.linker, 'link_chunks_to_entities'):
            # Convert current graph nodes to dicts for linker
            graph_nodes_dicts = [asdict(n) for n in self.nodes]
            hybrid_links = self.linker.link_chunks_to_entities(chunks, graph_nodes_dicts)
            
            # Create Chunk Nodes in Graph
            for i, chunk in enumerate(chunks):
                chunk_node = self._create_chunk_node(chunk, embeddings[i] if i < len(embeddings) else [])
                self._add_node(chunk_node)
            
            # Add Hybrid Relationships
            for rel_dict in hybrid_links:
                rel = GraphRelationship(
                    relationship_id=f"REL_HYBRID_{uuid.uuid4().hex[:8]}",
                    start_node_id=rel_dict["from_id"],
                    end_node_id=rel_dict["to_id"],
                    type=rel_dict["type"],
                    properties=rel_dict.get("metadata", {}),
                    source_document=metadata.get("file_name", "unknown"),
                    confidence=1.0,
                    pipeline_source="phase_6.7_hybrid_linker"
                )
                self._add_relationship(rel)
                
        return stats

    def _create_chunk_node(self, chunk: Dict, embedding: List[float]) -> GraphNode:
        """Create a graph node representing a text chunk."""
        node_id = f"chunk_{chunk.get('chunk_index')}_{chunk.get('source')}"
        return GraphNode(
            node_id=node_id,
            labels=["DocumentChunk"],
            properties={
                "text": chunk.get("chunk_text", "")[:500], # Trucate for property
                "chunk_index": chunk.get("chunk_index"),
                "char_length": chunk.get("char_length"),
                # Store truncated embedding or reference ID? usually don't store full vec in property
                "embedding_dim": len(embedding)
            },
            source_document=chunk.get("source", "unknown"),
            extraction_confidence=1.0,
            pipeline_source="phase_6.4_legal_chunker"
        )
    
    def _reset_state(self):
        """Reset builder state for new build."""
        self.nodes.clear()
        self.relationships.clear()
        self.abstention_nodes.clear()
        self.node_registry.clear()
        self.stats.clear()
        self.validation_errors.clear()
        self.pipeline_tracking.clear()
        self.relationship_counter = 0
    
    def _build_nodes_from_mapped(self, mapped_nodes: List[Dict], metadata: Dict[str, Any]):
        """Build graph nodes from mapped node data."""
        for mapped_node in mapped_nodes:
            try:
                node = self._create_graph_node_from_mapped(mapped_node, metadata)
                self._add_node(node)
                
                # Track statistics
                self.stats['nodes_processed'] += 1
                
            except Exception as e:
                error_msg = f"Failed to create node from mapped data: {e}"
                logger.error(error_msg)
                self.validation_errors.append(error_msg)
                self.stats['node_errors'] += 1
        
        logger.info(f"Built {len(self.nodes)} nodes from mapped data")
    
    def _create_graph_node_from_mapped(self, mapped_node: Dict, metadata: Dict) -> GraphNode:
        """Create GraphNode from mapped node data with strict validation."""
        # Extract node information
        label = mapped_node.get("label", "Entity")
        node_id = mapped_node.get("node_id", self._generate_node_id(label))
        
        # CRITICAL FIX (v2.3 Hardened): Consolidate all properties. 
        # Mapper (6.2) often returns a flat dictionary where properties are at the top level.
        properties = {}
        if "properties" in mapped_node and isinstance(mapped_node["properties"], dict):
            properties.update(mapped_node["properties"])
        
        # Merge top-level keys that are actual properties (excluding structural Neo4j keys)
        exclude_keys = ["node_id", "label", "labels", "properties", "success", "errors", "action"]
        for k, v in mapped_node.items():
            if k not in exclude_keys:
                properties[k] = v
        
        # Phase 3 Hardening: Delegate to Neo4jExporter if available (6.8)
        # Hardening: Dual-Channel Immutability & Presence
        # Only mandatory for Section/Law/Penalty in production
        traceable_labels = ["Section", "Law", "Penalty", "Clause", "Amendment"]
        is_hardened = getattr(self.config, "PRODUCTION_HARDENED", False) if self.config else False
        
        if label in traceable_labels:
            raw = properties.get("raw_text")
            sanit = properties.get("sanitized_text")
            
            if is_hardened:
                # RELAXATION: Only enforce for Section/Penalty or nodes with expected text.
                # NER entities (phase_4.2) rarely have dual-channel text.
                source_phase = properties.get("extraction_phase", "")
                if "phase_4.2" in source_phase:
                    logger.debug(f"Bypassing traceability for NER entity: {label} {node_id}")
                elif not raw or not sanit:
                    error_msg = f"Traceability Error: Missing dual-channel text for {label} {node_id}"
                    logger.error(error_msg)
                    raise ValueError(error_msg)
                
                if raw == sanit:
                    error_msg = f"Traceability Regression: raw_text equals sanitized_text for {label} {node_id}. Integrity compromised."
                    logger.error(error_msg)
                    raise ValueError(error_msg)

        # Remove non-property fields (label is separate)
        if "label" in properties:
            del properties["label"]
        
        # Add KPK-specific properties
        properties = self._enhance_with_kpk_properties(label, properties, metadata)
        
        # Add pipeline tracking
        properties["pipeline_source"] = properties.get("pipeline_source", "phase_6.3")
        properties["mapped_at"] = datetime.now().isoformat()
        
        # Create GraphNode
        return GraphNode(
            node_id=node_id,
            labels=[label] + self._get_additional_labels(label, properties),
            properties=properties,
            source_document=properties.get("source_document", "unknown"),
            extraction_confidence=float(properties.get("confidence_score", 0.8)),
            pipeline_source=properties.get("pipeline_source", "graph_builder")
        )
    
    def _enhance_with_kpk_properties(self, label: str, properties: Dict, metadata: Dict) -> Dict:
        """Add KPK-specific properties to node."""
        enhanced = properties.copy()
        
        # Add KPK flag if applicable
        if self._is_kpk_entity(label, properties):
            enhanced["kpk_specific"] = True
            enhanced["jurisdiction"] = JurisdictionLevel.PROVINCIAL.value
        
        # Enhance based on entity type
        if label == "Law":
            enhanced = self._enhance_law_properties(enhanced)
        elif label == "Section":
            enhanced = self._enhance_section_properties(enhanced)
        elif label == "Species":
            enhanced = self._enhance_species_properties(enhanced)
        elif label == "Penalty":
            enhanced = self._enhance_penalty_properties(enhanced)
        elif label == "Location":
            enhanced = self._enhance_location_properties(enhanced)
        elif label == "Officer":
            enhanced = self._enhance_officer_properties(enhanced)
        
        return enhanced
    
    def _enhance_law_properties(self, properties: Dict) -> Dict:
        """Enhance law node properties."""
        enhanced = properties.copy()
        
        # Extract year from title
        title = str(enhanced.get("title", ""))
        year_match = re.search(r'\b(19\d{2}|20\d{2})\b', title)
        if year_match and "year" not in enhanced:
            enhanced["year"] = int(year_match.group(1))
        
        # Set KPK jurisdiction
        if "jurisdiction" not in enhanced:
            enhanced["jurisdiction"] = JurisdictionLevel.PROVINCIAL.value
        
        # Check for Hazara override
        if "hazara" in title.lower():
            enhanced["hazara_override"] = True
            enhanced["jurisdiction_specific"] = "Hazara Division"
        
        return enhanced
    
    def _enhance_section_properties(self, properties: Dict) -> Dict:
        """Enhance section node properties."""
        enhanced = properties.copy()
        
        # Extract penalty amount if present
        content = str(enhanced.get("content", ""))
        if content and "penalty_amount" not in enhanced:
            penalty_match = re.search(r'Rs\.?\s*([\d,]+)', content)
            if penalty_match:
                enhanced["penalty_amount"] = int(penalty_match.group(1).replace(',', ''))
                enhanced["penalty_currency"] = "PKR"
        
        # Check for species mentions
        species_mentions = []
        for species in self.kpk_config["protected_species"]:
            if species.lower() in content.lower():
                species_mentions.append(species)
        
        if species_mentions:
            enhanced["species_mentioned"] = species_mentions
        
        return enhanced
    
    def _enhance_species_properties(self, properties: Dict) -> Dict:
        """Enhance species node properties."""
        enhanced = properties.copy()
        
        # Set protection level based on KPK rules
        common_name = str(enhanced.get("common_name", "")).lower()
        
        if common_name in self.kpk_config["protected_species"]:
            enhanced["legal_status"] = "protected"
            enhanced["protection_level"] = "highest"
            enhanced["kpk_endemic"] = True
        else:
            enhanced["legal_status"] = enhanced.get("legal_status", "regulated")
            enhanced["protection_level"] = enhanced.get("protection_level", "medium")
        
        # Add local names if not present
        if "local_names" not in enhanced:
            enhanced["local_names"] = self._get_local_names(common_name)
        
        return enhanced
    
    def _enhance_penalty_properties(self, properties: Dict) -> Dict:
        """Enhance penalty node properties."""
        enhanced = properties.copy()
        
        # Ensure currency is PKR
        if "currency" not in enhanced:
            enhanced["currency"] = "PKR"
        
        # Apply KPK-specific multipliers
        amount = enhanced.get("amount")
        if amount:
            try:
                base_amount = float(amount)
                
                # Apply multipliers based on conditions
                if enhanced.get("violation_type") == "repeat_offense":
                    base_amount *= self.kpk_config["penalty_multipliers"]["repeat_offense"]
                if enhanced.get("species_specific") in self.kpk_config["protected_species"]:
                    base_amount *= self.kpk_config["penalty_multipliers"]["protected_species"]
                if enhanced.get("location_specific") == "reserved_forest":
                    base_amount *= self.kpk_config["penalty_multipliers"]["reserved_forest"]
                
                enhanced["amount"] = base_amount
                enhanced["calculated_amount"] = True
                
            except (ValueError, TypeError):
                pass
        
        return enhanced
    
    def _enhance_location_properties(self, properties: Dict) -> Dict:
        """Enhance location node properties."""
        enhanced = properties.copy()
        
        # Determine location type
        name = str(enhanced.get("name", "")).lower()
        
        if any(div.lower() in name for div in self.kpk_config["divisions"]):
            enhanced["type"] = "division"
            enhanced["jurisdiction_level"] = JurisdictionLevel.DIVISIONAL.value
        elif "range" in name:
            enhanced["type"] = "range"
            enhanced["jurisdiction_level"] = JurisdictionLevel.RANGE_LEVEL.value
        elif "beat" in name:
            enhanced["type"] = "beat"
            enhanced["jurisdiction_level"] = JurisdictionLevel.BEAT_LEVEL.value
        elif "forest" in name:
            enhanced["type"] = "forest"
            enhanced["jurisdiction_level"] = JurisdictionLevel.DISTRICT.value
        
        # Check for Hazara Division
        if "hazara" in name:
            enhanced["hazara_division"] = True
            enhanced["has_special_rules"] = True
        
        return enhanced
    
    def _enhance_officer_properties(self, properties: Dict) -> Dict:
        """Enhance officer node properties."""
        enhanced = properties.copy()
        
        # Standardize rank
        rank = str(enhanced.get("rank", "")).upper()
        rank_mapping = {
            "DFO": "Divisional Forest Officer",
            "SDFO": "Sub-Divisional Forest Officer",
            "RO": "Range Officer",
            "BG": "Beat Guard",
            "CF": "Conservator of Forests",
            "CCF": "Chief Conservator of Forests"
        }
        
        if rank in rank_mapping:
            enhanced["rank"] = rank_mapping[rank]
            enhanced["rank_code"] = rank
        
        # Determine authority level
        rank = enhanced.get("rank", "").lower()
        if "chief" in rank or "ccf" in rank:
            enhanced["authority_level"] = 5
        elif "conservator" in rank or "cf" in rank:
            enhanced["authority_level"] = 4
        elif "divisional" in rank or "dfo" in rank:
            enhanced["authority_level"] = 3
        elif "sub-divisional" in rank or "sdfo" in rank:
            enhanced["authority_level"] = 2
        elif "range" in rank or "ro" in rank:
            enhanced["authority_level"] = 1
        else:
            enhanced["authority_level"] = 0
        
        return enhanced
    
    def _get_local_names(self, species: str) -> List[str]:
        """Get local names for species."""
        local_names_map = {
            "deodar": ["دیار", "देवदार"],
            "kail": ["کیل", "कैल"],
            "fir": ["راڑ", "राज"],
            "spruce": ["اسپروس", "स्प्रूस"],
            "chir pine": ["چلغوزا", "चीड़"],
            "oak": ["بلوط", "ओक"]
        }
        return local_names_map.get(species, [])
    
    def _get_additional_labels(self, primary_label: str, properties: Dict) -> List[str]:
        """Get additional labels based on properties."""
        additional = []
        
        if primary_label == "Law":
            if properties.get("kpk_specific"):
                additional.append("KPK_Law")
            if properties.get("hazara_override"):
                additional.append("Hazara_Law")
        
        elif primary_label == "Species":
            if properties.get("kpk_endemic"):
                additional.append("KPK_Endemic")
            if properties.get("legal_status") == "protected":
                additional.append("Protected_Species")
        
        elif primary_label == "Location":
            if "hazara" in properties.get("name", "").lower():
                additional.append("Hazara_Location")
            if properties.get("type") == "division":
                additional.append("Forest_Division")
        
        return additional
    
    def _build_relationships_from_mapped(self, mapped_relationships: List[Dict], 
                                        node_id_map: Dict[str, str], 
                                        metadata: Dict[str, Any]):
        """Build graph relationships from mapped relationship data."""
        for mapped_rel in mapped_relationships:
            try:
                relationship = self._create_relationship_from_mapped(mapped_rel, node_id_map, metadata)
                if relationship:
                    self._add_relationship(relationship)
                    
                    # Track statistics
                    self.stats['relationships_processed'] += 1
                    
            except Exception as e:
                error_msg = f"Failed to create relationship from mapped data: {e}"
                logger.error(error_msg)
                self.validation_errors.append(error_msg)
                self.stats['relationship_errors'] += 1
        
        logger.info(f"Built {len(self.relationships)} relationships from mapped data")
    
    def _create_relationship_from_mapped(self, mapped_rel: Dict, 
                                        node_id_map: Dict[str, str],
                                        metadata: Dict) -> Optional[GraphRelationship]:
        """Create GraphRelationship from mapped relationship data."""
        # Extract relationship information
        rel_type = mapped_rel.get("type", "RELATES_TO")
        from_id = mapped_rel.get("from_id")
        to_id = mapped_rel.get("to_id")
        properties = mapped_rel.copy()
        
        # Map IDs if necessary
        if from_id in node_id_map:
            from_id = node_id_map[from_id]
        if to_id in node_id_map:
            to_id = node_id_map[to_id]
        
        # Remove non-property fields
        for field in ["type", "from_id", "to_id", "rel_id"]:
            if field in properties:
                del properties[field]
        
        # Validate nodes exist
        if from_id not in self.node_registry and not self._is_pending_node(from_id):
            logger.warning(f"Start node {from_id} not found for relationship")
            return None
        
        if to_id not in self.node_registry and not self._is_pending_node(to_id):
            logger.warning(f"End node {to_id} not found for relationship")
            return None
        
        # Enhance with KPK properties
        properties = self._enhance_relationship_properties(rel_type, properties, metadata)
        
        # Generate relationship ID
        rel_id = mapped_rel.get("rel_id", f"REL_{self.relationship_counter:08d}")
        
        # Create GraphRelationship
        return GraphRelationship(
            relationship_id=rel_id,
            start_node_id=from_id,
            end_node_id=to_id,
            type=rel_type,
            properties=properties,
            source_document=properties.get("source_document", "unknown"),
            confidence=float(properties.get("confidence", 0.8)),
            pipeline_source=properties.get("pipeline_source", "graph_builder")
        )
    
    def _enhance_relationship_properties(self, rel_type: str, properties: Dict, metadata: Dict) -> Dict:
        """Add KPK-specific properties to relationship."""
        enhanced = properties.copy()
        
        # Add KPK-specific metadata
        enhanced["kpk_validated"] = True
        enhanced["created_at"] = datetime.now().isoformat()
        
        # Enhance based on relationship type
        if rel_type == "IMPOSES":
            if "currency" not in enhanced:
                enhanced["currency"] = "PKR"
            enhanced["applicable_in_kpk"] = True
            
        elif rel_type == "APPLIES_TO":
            enhanced["jurisdiction_verified"] = True
            if "jurisdiction_conflict" not in enhanced:
                enhanced["jurisdiction_conflict"] = "none"
            
        elif rel_type == "PROTECTS_SPECIES":
            enhanced["protection_verified_kpk"] = True
            enhanced["enforcement_level"] = "high"
            
        elif rel_type == "ABSTAINS_FROM":
            enhanced["abstention_type"] = properties.get("abstention_type", "general")
            enhanced["requires_review"] = True
            
        elif rel_type == "AMENDED_BY":
            enhanced["gazette_verified"] = properties.get("gazette_verified", False)
            enhanced["temporal_validity"] = properties.get("temporal_validity", "unknown")
        
        return enhanced
    
    def _is_pending_node(self, node_id: str) -> bool:
        """Check if node is pending creation."""
        # This would check against a list of node IDs that should be created
        # For now, just check if it follows expected pattern
        return bool(re.match(r'^(LAW|SECTION|SPECIES|LOCATION|OFFICER|PENALTY)_', node_id.upper()))
    
    def _add_abstention_nodes_from_mapped(self, mapped_data: Dict):
        """Add abstention nodes from mapped data."""
        abstention_cases = mapped_data.get("mapping_statistics", {}).get("abstention_cases", [])
        
        for case in abstention_cases:
            try:
                abstention = KPKAbstentionNode(
                    abstention_id=case.get("entity_id", f"abst_{uuid.uuid4().hex[:8]}"),
                    reason=case.get("reason", "unknown"),
                    entity_type=case.get("entity_type", "unknown"),
                    context={"source": "mapped_data", "details": case},
                    related_node_ids=[case.get("node_id")] if case.get("node_id") else [],
                    confidence=float(case.get("confidence", 0.5)),
                    requires_human_review=True,
                    pipeline_phase="phase_6.2",
                    quality_gate_trigger=case.get("quality_gate", "unknown")
                )
                
                self.abstention_nodes.append(abstention)
                
                # Convert to GraphNode and add to graph
                abstention_node = abstention.to_graph_node()
                self._add_node(abstention_node)
                
            except Exception as e:
                logger.error(f"Failed to create abstention node: {e}")
    
    def _add_kpk_specific_entities(self):
        """Add KPK-specific entities to the graph."""
        logger.info("Adding KPK-specific entities...")
        
        # Add KPK Province node
        kpk_node = self._create_kpk_province_node()
        self._add_node(kpk_node)
        
        # Add KPK Forest Department node
        forest_dept_node = self._create_forest_department_node()
        self._add_node(forest_dept_node)
        
        # Add relationships between KPK entities and other nodes
        self._add_kpk_relationships(kpk_node, forest_dept_node)
        
        # Add special nodes for Hazara Division (Always included for KPK anchor)
        self._add_hazara_special_nodes()
    
    def _create_kpk_province_node(self) -> GraphNode:
        """Create KPK Province node."""
        return GraphNode(
            node_id="LOCATION_KPK_PROVINCE",
            labels=["Location", "Province", "KPK_Specific"],
            properties={
                "node_id": "LOCATION_KPK_PROVINCE",
                "name": "Khyber Pakhtunkhwa",
                "type": "province",
                "jurisdiction_level": JurisdictionLevel.PROVINCIAL.value,
                "area_km2": 74521,
                "population_millions": 35.5,
                "capital": "Peshawar",
                "forest_coverage_percent": 20.3,
                "kpk_specific": True,
                "description": "Khyber Pakhtunkhwa Province of Pakistan",
                # Forensic invariants (v2.3 hardening)
                "source_doc_id": "synthetic_seed",
                "extraction_phase": "phase_6.3_seed",
                "confidence_score": 1.0,
                "bbox": "document_level"
            },
            source_document="graph_builder",
            extraction_confidence=1.0,
            pipeline_source="phase_6.3"
        )
    
    def _create_forest_department_node(self) -> GraphNode:
        """Create KPK Forest Department node."""
        return GraphNode(
            node_id="AUTHORITY_KPK_FOREST_DEPARTMENT",
            labels=["Authority", "Department", "KPK_Specific"],
            properties={
                "node_id": "AUTHORITY_KPK_FOREST_DEPARTMENT",
                "name": "KPK Forest Department",
                "type": "department",
                "jurisdiction_level": JurisdictionLevel.PROVINCIAL.value,
                "headquarters": "Peshawar",
                "established_year": 1901,
                "responsibilities": ["Forest Management", "Wildlife Protection", "Forest Law Enforcement"],
                "kpk_specific": True,
                "contact_info": {"website": "www.kpkforest.gov.pk"},
                # Forensic invariants (v2.3 hardening)
                "source_doc_id": "synthetic_seed",
                "extraction_phase": "phase_6.3_seed",
                "confidence_score": 1.0,
                "bbox": "document_level"
            },
            source_document="graph_builder",
            extraction_confidence=1.0,
            pipeline_source="phase_6.3"
        )
    
    def _add_kpk_relationships(self, kpk_node: GraphNode, forest_dept_node: GraphNode):
        """Add relationships between KPK entities and other nodes."""
        
        # Connect laws to KPK province
        for node in self.nodes:
            if "Law" in node.labels and node.properties.get("jurisdiction") == JurisdictionLevel.PROVINCIAL.value:
                self._add_relationship(GraphRelationship(
                    relationship_id=f"REL_{self.relationship_counter:08d}",
                    start_node_id=node.node_id,
                    end_node_id=kpk_node.node_id,
                    type="APPLIES_TO",
                    properties={
                        "jurisdiction": "direct",
                        "applicability": "province_wide",
                        "kpk_validated": True
                    },
                    source_document="graph_builder",
                    confidence=1.0,
                    pipeline_source="phase_6.3"
                ))
                self.relationship_counter += 1
        
        # Connect officers to Forest Department
        for node in self.nodes:
            if "Officer" in node.labels:
                self._add_relationship(GraphRelationship(
                    relationship_id=f"REL_{self.relationship_counter:08d}",
                    start_node_id=node.node_id,
                    end_node_id=forest_dept_node.node_id,
                    type="BELONGS_TO",
                    properties={
                        "department": "KPK Forest Department",
                        "employment_status": "active",
                        "kpk_validated": True
                    },
                    source_document="graph_builder",
                    confidence=0.9,
                    pipeline_source="phase_6.3"
                ))
                self.relationship_counter += 1
    
    def _has_hazara_entities(self) -> bool:
        """Check if graph contains Hazara Division entities."""
        for node in self.nodes:
            if "hazara" in node.properties.get("name", "").lower():
                return True
            if node.properties.get("hazara_division"):
                return True
        return False
    
    def _add_hazara_special_nodes(self):
        """Add special nodes for Hazara Division."""
        hazara_node = GraphNode(
            node_id="LOCATION_HAZARA_DIVISION",
            labels=["Location", "Division", "Hazara_Specific", "KPK_Specific"],
            properties={
                "name": "Hazara Division",
                "type": "division",
                "jurisdiction_level": JurisdictionLevel.DIVISIONAL.value,
                "districts": ["Abbottabad", "Mansehra", "Haripur", "Batagram", "Kohistan", "Torghar"],
                "special_status": "Has separate forest act",
                "hazara_forest_act_applies": True,
                "kpk_ordinance_overridden": True,
                "kpk_specific": True,
                # Forensic invariants (v2.3 hardening)
                "source_doc_id": "synthetic_seed",
                "extraction_phase": "phase_6.3_seed",
                "confidence_score": 1.0,
                "bbox": "document_level"
            },
            source_document="graph_builder",
            extraction_confidence=1.0,
            pipeline_source="phase_6.3"
        )
        
        self._add_node(hazara_node)
    
    def _add_node(self, node: GraphNode):
        """Add node to graph with validation."""
        # Validate against schema
        if self.schema.node_schema:
            # Merge node attributes into validation data
            validation_data = {
                "node_id": node.node_id,
                "label": node.labels[0] if node.labels else "Entity",
                **node.properties
            }
            is_valid, errors = self.schema.node_schema.validate_node_against_schema(
                validation_data,
                NodeLabel(node.labels[0]) if node.labels else NodeLabel.ENTITY
            )
        else:
            # If no schema, assume valid for now
            is_valid = True
            errors = []
        
        if not is_valid:
            error_msg = f"Schema Violation for {node.node_id}: {'; '.join(errors)}"
            self.validation_errors.append(error_msg)
            
            if self.config and getattr(self.config, "PRODUCTION_HARDENED", False):
                logger.error(f"STRICT SCHEMA FAILURE: {error_msg}")
                raise ValueError(error_msg)
            else:
                logger.warning(f"Node validation failed (Soft): {node.node_id}")
        
        # Check for duplicates
        if node.node_id in self.node_registry:
            logger.warning(f"Duplicate node ID: {node.node_id}")
            # Generate new ID with suffix
            original_id = node.node_id
            suffix = 1
            while node.node_id in self.node_registry:
                node.node_id = f"{original_id}_{suffix}"
                suffix += 1
        
        # Add to collections
        self.nodes.append(node)
        self.node_registry[node.node_id] = node
        
        # Update statistics
        for label in node.labels:
            self.stats[f'node_label_{label}'] = self.stats.get(f'node_label_{label}', 0) + 1
        
        # Track KPK-specific nodes
        if node.properties.get("kpk_specific"):
            self.stats['kpk_specific_nodes'] = self.stats.get('kpk_specific_nodes', 0) + 1
    
    def _add_relationship(self, relationship: GraphRelationship):
        """Add relationship to graph with validation."""
        # Validate against schema
        try:
            rel_type = RelationshipType(relationship.type)
            is_valid, errors = self.schema.relationship_schema.validate_relationship_against_schema(
                relationship.properties, rel_type
            )
            
            if not is_valid:
                error_msg = f"Relationship Schema Violation for {relationship.type}: {'; '.join(errors)}"
                self.validation_errors.append(error_msg)
                
                if self.config and getattr(self.config, "PRODUCTION_HARDENED", False):
                    logger.error(f"STRICT SCHEMA FAILURE: {error_msg}")
                    raise ValueError(error_msg)
                else:
                    logger.warning(f"Relationship validation failed (Soft): {relationship.type}")
                    return
                
        except ValueError:
            logger.warning(f"Unknown relationship type: {relationship.type}")
        
        # Check for orphaned relationships
        if relationship.start_node_id not in self.node_registry:
            logger.warning(f"Orphaned relationship: start node {relationship.start_node_id} not found")
            self.stats['orphaned_relationships'] = self.stats.get('orphaned_relationships', 0) + 1
        
        if relationship.end_node_id not in self.node_registry:
            logger.warning(f"Orphaned relationship: end node {relationship.end_node_id} not found")
            self.stats['orphaned_relationships'] = self.stats.get('orphaned_relationships', 0) + 1
        
        # Check for duplicates
        rel_signature = f"{relationship.start_node_id}->{relationship.type}->{relationship.end_node_id}"
        if hasattr(self, '_relationship_signatures'):
            if rel_signature in self._relationship_signatures:
                logger.warning(f"Duplicate relationship: {rel_signature}")
                self.stats['duplicate_relationships'] = self.stats.get('duplicate_relationships', 0) + 1
                return
            self._relationship_signatures.add(rel_signature)
        else:
            self._relationship_signatures = {rel_signature}
        
        # Add to collections
        self.relationships.append(relationship)
        
        # Update statistics
        self.stats[f'relationship_type_{relationship.type}'] = self.stats.get(f'relationship_type_{relationship.type}', 0) + 1
        
        # Track KPK-specific relationships
        if relationship.properties.get("kpk_validated"):
            self.stats['kpk_validated_relationships'] = self.stats.get('kpk_validated_relationships', 0) + 1
    
    def _generate_node_id(self, label: str) -> str:
        """Generate unique node ID."""
        hash_str = hashlib.md5(str(uuid.uuid4()).encode()).hexdigest()[:8]
        return f"{label.upper()}_{hash_str}"
    
    def _is_kpk_entity(self, label: str, properties: Dict) -> bool:
        """Check if entity is KPK-specific."""
        if properties.get("kpk_specific"):
            return True
        
        # Check based on properties
        if label == "Law":
            title = properties.get("title", "").lower()
            if any(keyword in title for keyword in ["kpk", "khyber", "nwfp", "hazara"]):
                return True
        
        elif label == "Location":
            name = properties.get("name", "").lower()
            if any(div.lower() in name for div in self.kpk_config["divisions"]):
                return True
        
        return False
    
    def _validate_graph(self) -> Dict[str, Any]:
        """Validate the built graph."""
        validation_result = {
            'node_validation': {
                'total_nodes': len(self.nodes),
                'nodes_without_labels': sum(1 for n in self.nodes if not n.labels),
                'duplicate_node_ids': len(self.nodes) - len(set(n.node_id for n in self.nodes)),
                'kpk_specific_nodes': self.stats.get('kpk_specific_nodes', 0)
            },
            'relationship_validation': {
                'total_relationships': len(self.relationships),
                'relationships_without_type': sum(1 for r in self.relationships if not r.type),
                'orphaned_relationships': self.stats.get('orphaned_relationships', 0),
                'duplicate_relationships': self.stats.get('duplicate_relationships', 0),
                'kpk_validated_relationships': self.stats.get('kpk_validated_relationships', 0)
            },
            'schema_errors': len(self.validation_errors),
            'error_samples': self.validation_errors[:10] if self.validation_errors else []
        }
        
        return validation_result
    
    def _generate_statistics(self) -> Dict[str, Any]:
        """Generate graph statistics."""
        # Node statistics
        node_labels = Counter()
        for node in self.nodes:
            for label in node.labels:
                node_labels[label] += 1
        
        # Relationship statistics
        rel_types = Counter()
        for rel in self.relationships:
            rel_types[rel.type] += 1
        
        # Property statistics
        property_counts = Counter()
        for node in self.nodes:
            property_counts.update(node.properties.keys())
        
        # KPK-specific statistics
        kpk_nodes = sum(1 for n in self.nodes if n.properties.get("kpk_specific", False))
        hazara_nodes = sum(1 for n in self.nodes if n.properties.get("hazara_division", False))
        
        return {
            'nodes': {
                'total': len(self.nodes),
                'by_label': dict(node_labels),
                'with_abstentions': len(self.abstention_nodes),
                'kpk_specific': kpk_nodes,
                'hazara_specific': hazara_nodes
            },
            'relationships': {
                'total': len(self.relationships),
                'by_type': dict(rel_types),
                'average_per_node': len(self.relationships) / len(self.nodes) if self.nodes else 0
            },
            'properties': {
                'unique_properties': len(property_counts),
                'most_common_properties': property_counts.most_common(10)
            },
            'graph_density': self._calculate_graph_density(),
            'abstention_analysis': {
                'total_abstentions': len(self.abstention_nodes),
                'abstention_reasons': Counter([a.reason for a in self.abstention_nodes]),
                'requires_human_review': sum(1 for a in self.abstention_nodes if a.requires_human_review)
            },
            'kpk_analysis': {
                'kpk_nodes_percentage': (kpk_nodes / len(self.nodes) * 100) if self.nodes else 0,
                'protected_species_count': sum(1 for n in self.nodes if 'Protected_Species' in n.labels),
                'forest_officers_count': sum(1 for n in self.nodes if 'Officer' in n.labels),
                'hazara_coverage': 'Yes' if hazara_nodes > 0 else 'No'
            }
        }
    
    def _calculate_graph_density(self) -> float:
        """Calculate graph density (relationships per possible relationship)."""
        n = len(self.nodes)
        if n <= 1:
            return 0.0
        
        max_possible_edges = n * (n - 1)
        actual_edges = len(self.relationships)
        
        return actual_edges / max_possible_edges if max_possible_edges > 0 else 0.0
    
    def _generate_quality_report(self) -> Dict[str, Any]:
        """Generate quality report for the graph."""
        stats = self._generate_statistics()
        
        # Calculate quality scores
        completeness_score = self._calculate_completeness_score(stats)
        consistency_score = self._calculate_consistency_score()
        richness_score = self._calculate_richness_score(stats)
        
        # Overall quality score
        overall_quality = (
            completeness_score * 0.4 +
            consistency_score * 0.3 +
            richness_score * 0.3
        )
        
        return {
            'overall_quality': round(overall_quality, 3),
            'completeness': round(completeness_score, 3),
            'consistency': round(consistency_score, 3),
            'richness': round(richness_score, 3),
            'kpk_coverage': round(stats['kpk_analysis']['kpk_nodes_percentage'] / 100, 3),
            'validation_passed': len(self.validation_errors) == 0,
            'validation_errors_count': len(self.validation_errors),
            'recommendations': self._generate_quality_recommendations(stats)
        }
    
    def _calculate_completeness_score(self, stats: Dict) -> float:
        """Calculate completeness score (0-1)."""
        # Check for essential KPK entity types
        essential_types = ["Law", "Section", "Species", "Location", "Officer"]
        found_types = sum(1 for t in essential_types if stats['nodes']['by_label'].get(t, 0) > 0)
        
        completeness = found_types / len(essential_types) if essential_types else 1.0
        
        # Boost if we have KPK-specific entities
        if stats['kpk_analysis']['kpk_nodes_percentage'] > 50:
            completeness = min(completeness + 0.2, 1.0)
        
        return completeness
    
    def _calculate_consistency_score(self) -> float:
        """Calculate consistency score (0-1)."""
        # Check for consistent property naming
        total_nodes = len(self.nodes)
        if total_nodes == 0:
            return 0.0
        
        # Check for nodes with required properties
        nodes_with_confidence = sum(1 for n in self.nodes if "confidence_score" in n.properties)
        confidence_consistency = nodes_with_confidence / total_nodes
        
        # Check for nodes with source tracking
        nodes_with_source = sum(1 for n in self.nodes if "source_document" in n.properties)
        source_consistency = nodes_with_source / total_nodes
        
        return (confidence_consistency + source_consistency) / 2
    
    def _calculate_richness_score(self, stats: Dict) -> float:
        """Calculate richness score (0-1)."""
        total_nodes = len(self.nodes)
        total_relationships = len(self.relationships)
        
        if total_nodes == 0:
            return 0.0
        
        # Relationship richness
        relationship_richness = total_relationships / total_nodes
        
        # Property richness (average properties per node)
        total_properties = sum(len(n.properties) for n in self.nodes)
        property_richness = total_properties / total_nodes
        
        # Normalize
        normalized_relationship = min(relationship_richness / 5, 1.0)  # Max 5 relationships per node
        normalized_property = min(property_richness / 10, 1.0)  # Max 10 properties per node
        
        return (normalized_relationship + normalized_property) / 2
    
    def _generate_quality_recommendations(self, stats: Dict) -> List[str]:
        """Generate quality improvement recommendations."""
        recommendations = []
        
        # Check for low relationship density
        if stats['relationships']['average_per_node'] < 1.0:
            recommendations.append("Consider adding more relationships between entities")
        
        # Check for missing KPK entities
        if stats['kpk_analysis']['kpk_nodes_percentage'] < 30:
            recommendations.append("Add more KPK-specific entities for better domain coverage")
        
        # Check for validation errors
        if len(self.validation_errors) > 0:
            recommendations.append(f"Address {len(self.validation_errors)} validation errors")
        
        # Check for abstentions needing review
        if stats['abstention_analysis']['requires_human_review'] > 0:
            recommendations.append(f"Review {stats['abstention_analysis']['requires_human_review']} abstention cases")
        
        return recommendations
    
    def _get_kpk_entities_summary(self) -> Dict[str, Any]:
        """Get summary of KPK-specific entities."""
        kpk_laws = []
        protected_species = []
        forest_officers = []
        hazara_entities = []
        
        for node in self.nodes:
            if node.properties.get("kpk_specific"):
                if "Law" in node.labels:
                    kpk_laws.append(node.properties.get("title", node.node_id))
                if "Species" in node.labels and node.properties.get("legal_status") == "protected":
                    protected_species.append(node.properties.get("common_name", node.node_id))
                if "Officer" in node.labels:
                    forest_officers.append(node.properties.get("rank", node.node_id))
                if node.properties.get("hazara_division"):
                    hazara_entities.append(node.properties.get("name", node.node_id))
        
        return {
            "kpk_laws_count": len(kpk_laws),
            "kpk_laws_sample": kpk_laws[:5],
            "protected_species_count": len(protected_species),
            "protected_species_sample": protected_species[:5],
            "forest_officers_count": len(forest_officers),
            "hazara_entities_count": len(hazara_entities),
            "hazara_entities_sample": hazara_entities[:3]
        }
    
    def export_to_csv(self, output_dir: Union[str, Path]) -> Dict[str, Path]:
        """
        Export graph to CSV files for Neo4j import.
        
        Args:
            output_dir: Directory to save CSV files
            
        Returns:
            Dict mapping file type to file path
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        file_paths = {} # Correctly initialized for v2.3
        
        if Neo4jExporter:
            logger.info("Using hardened Neo4jExporter (6.8) for production-grade export.")
            # For 6.3 GraphBuilder, we need to pass a production_mode flag
            production_mode = True # Default to True for certification
            exporter = Neo4jExporter(output_dir=output_dir, production_mode=production_mode)
            
            # Prepare data dictionaries for the exporter
            nodes_data = []
            for node in self.nodes:
                n_dict = {
                    "node_id": node.node_id,
                    "labels": node.labels,
                    "properties": node.properties,
                    "source_document": node.source_document
                }
                nodes_data.append(n_dict)
                
            relationships_data = []
            for rel in self.relationships:
                r_dict = {
                    "relationship_id": rel.relationship_id,
                    "from_id": rel.start_node_id,
                    "to_id": rel.end_node_id,
                    "type": rel.type,
                    "properties": rel.properties,
                    "source_document": rel.source_document
                }
                relationships_data.append(r_dict)
            
            # Execute Hardened Export (this triggers pre-check, write, and post-verification)
            # We use overwrite=True for the initial call
            exporter.export_nodes([ExportNode(
                node_id=n["node_id"],
                labels=n["labels"],
                properties=n["properties"],
                source_file=n["source_document"]
            ) for n in nodes_data], overwrite=True)
            
            exporter.export_relationships([ExportRelationship(
                relationship_id=r["relationship_id"],
                start_node_id=r["from_id"],
                end_node_id=r["to_id"],
                type=r["type"],
                properties=r["properties"],
                source_file=r["source_document"]
            ) for r in relationships_data], overwrite=True)
            
            # Generate Audit Assets
            exporter._generate_audit_manifest()
            exporter.generate_immutability_constraints()
            
            # Populate file_paths for backward compatibility
            file_paths['nodes'] = output_dir / "nodes.csv"
            file_paths['relationships'] = output_dir / "relationships.csv"
            file_paths['manifest'] = output_dir / "manifest.json"
        else:
            # Fallback to legacy manual export if 6.8 is not available
            logger.warning("Hardened Neo4jExporter (6.8) NOT found. Falling back to legacy export.")
            # Export nodes
            nodes_path = output_dir / "nodes.csv"
            self._export_nodes_to_csv(nodes_path)
            file_paths['nodes'] = nodes_path
            
            # Export relationships
            relationships_path = output_dir / "relationships.csv"
            self._export_relationships_to_csv(relationships_path)
            file_paths['relationships'] = relationships_path
        
        # Shared assets
        constraints_path = output_dir / "constraints.cypher"
        self._generate_constraints_script(constraints_path)
        file_paths['constraints'] = constraints_path
        
        report_path = output_dir / "import_report.json"
        self._generate_import_report(report_path)
        file_paths['report'] = report_path
        
        cypher_path = output_dir / "statements.cypher"
        self._generate_cypher_statements(cypher_path)
        file_paths['cypher'] = cypher_path
        
        logger.info(f"Graph exported to {output_dir}")
        
        return file_paths
    
    def _export_nodes_to_csv(self, output_path: Path):
        """Export nodes to CSV."""
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            if self.nodes:
                # Get all possible fieldnames
                fieldnames = set()
                for node in self.nodes:
                    fieldnames.update(node.to_csv_row().keys())
                
                fieldnames = sorted(fieldnames)
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for node in self.nodes:
                    row = node.to_csv_row()
                    # Ensure all fields are present
                    for field in fieldnames:
                        if field not in row:
                            row[field] = ''
                    writer.writerow(row)
                
                logger.info(f"Exported {len(self.nodes)} nodes to {output_path}")
    
    def _export_relationships_to_csv(self, output_path: Path):
        """Export relationships to CSV."""
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            if self.relationships:
                # Get all possible fieldnames
                fieldnames = set()
                for rel in self.relationships:
                    fieldnames.update(rel.to_csv_row().keys())
                
                fieldnames = sorted(fieldnames)
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for rel in self.relationships:
                    row = rel.to_csv_row()
                    # Ensure all fields are present
                    for field in fieldnames:
                        if field not in row:
                            row[field] = ''
                    writer.writerow(row)
                
                logger.info(f"Exported {len(self.relationships)} relationships to {output_path}")
    
    def _generate_constraints_script(self, output_path: Path):
        """Generate Cypher constraints script."""
        constraints = [
            "-- KPK Forestry Knowledge Graph Constraints and Indexes",
            f"-- Generated by KPKGraphBuilder on {datetime.now().isoformat()}",
            "--",
            ""
        ]
        
        # Unique constraints from schema
        constraints.append("-- UNIQUE CONSTRAINTS")
        try:
            unique_constraints = self.schema.queries.get_constraint_queries()
            constraints.extend(unique_constraints)
        except (AttributeError, TypeError):
            # Fallback if schema doesn't provide these yet
            constraints.append("-- (Standard unique constraints below)")
        constraints.append("")
        
        # Additional constraints for KPK
        constraints.append("-- KPK-SPECIFIC CONSTRAINTS")
        constraints.extend([
            "CREATE CONSTRAINT kpk_law_unique IF NOT EXISTS FOR (l:Law) REQUIRE (l.title, l.year) IS NODE KEY;",
            "CREATE CONSTRAINT species_scientific_name_unique IF NOT EXISTS FOR (s:Species) REQUIRE s.scientific_name IS UNIQUE;",
            "CREATE CONSTRAINT officer_id_unique IF NOT EXISTS FOR (o:Officer) REQUIRE (o.rank, o.division) IS UNIQUE;"
        ])
        constraints.append("")
        
        # Indexes for performance
        constraints.append("-- INDEXES FOR QUERY PERFORMANCE")
        constraints.extend([
            "CREATE INDEX law_jurisdiction_index IF NOT EXISTS FOR (l:Law) ON (l.jurisdiction, l.kpk_specific);",
            "CREATE INDEX species_protection_index IF NOT EXISTS FOR (s:Species) ON (s.legal_status, s.protection_level);",
            "CREATE INDEX penalty_amount_index IF NOT EXISTS FOR (p:Penalty) ON (p.amount, p.currency);",
            "CREATE INDEX location_type_index IF NOT EXISTS FOR (loc:Location) ON (loc.type, loc.jurisdiction_level);",
            "CREATE INDEX abstention_review_index IF NOT EXISTS FOR (a:Abstention) ON (a.requires_human_review, a.confidence);",
            "CREATE INDEX relationship_type_index IF NOT EXISTS FOR ()-[r]-() ON (r.type);"
        ])
        constraints.append("")
        
        # Full-text indexes for search
        constraints.append("-- FULL-TEXT INDEXES FOR SEARCH")
        constraints.extend([
            "CREATE FULLTEXT INDEX law_content_search IF NOT EXISTS FOR (l:Law) ON EACH [l.title, l.description];",
            "CREATE FULLTEXT INDEX section_content_search IF NOT EXISTS FOR (s:Section) ON EACH [s.content];",
            "CREATE FULLTEXT INDEX species_search IF NOT EXISTS FOR (s:Species) ON EACH [s.common_name, s.scientific_name, s.local_names];"
        ])
        
        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(constraints))
        
        logger.info(f"Generated constraints script: {output_path}")
    
    def _generate_import_report(self, output_path: Path):
        """Generate import report."""
        stats = self._generate_statistics()
        quality = self._generate_quality_report()
        kpk_summary = self._get_kpk_entities_summary()
        
        report = {
            'export_timestamp': datetime.now().isoformat(),
            'graph_statistics': stats,
            'quality_assessment': quality,
            'kpk_entities_summary': kpk_summary,
            'validation_summary': self._validate_graph(),
            'pipeline_tracking': self.pipeline_tracking,
            'abstention_analysis': {
                'total_abstentions': len(self.abstention_nodes),
                'by_reason': Counter([a.reason for a in self.abstention_nodes]),
                'requiring_review': sum(1 for a in self.abstention_nodes if a.requires_human_review),
                'pipeline_sources': Counter([a.pipeline_phase for a in self.abstention_nodes])
            },
            'recommendations': {
                'immediate': quality.get('recommendations', []),
                'long_term': [
                    "Consider adding climate impact nodes for FYP extension",
                    "Integrate with Agentic AI components in Phase 7",
                    "Add temporal reasoning for amendment chains",
                    "Enhance multilingual support for Urdu/Pashto content"
                ]
            }
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Generated import report: {output_path}")
    
    def _generate_cypher_statements(self, output_path: Path):
        """Generate Cypher statements for direct import."""
        statements = [
            f"-- KPK Forestry Knowledge Graph Import",
            f"-- Generated on {datetime.now().isoformat()}",
            f"-- Total nodes: {len(self.nodes)}",
            f"-- Total relationships: {len(self.relationships)}",
            ""
        ]
        
        # Node creation statements
        statements.append("-- CREATE NODES")
        for node in self.nodes:
            cypher = node.to_cypher_create()
            statements.append(cypher)
            # Add parameters
            params = json.dumps(node.properties, ensure_ascii=False)
            statements.append(f"-- Parameters: {params}")
            statements.append("")
        
        # Relationship creation statements
        statements.append("-- CREATE RELATIONSHIPS")
        for rel in self.relationships:
            # Get node labels for MATCH
            start_node = self.node_registry.get(rel.start_node_id)
            end_node = self.node_registry.get(rel.end_node_id)
            
            if start_node and end_node:
                start_label = start_node.labels[0] if start_node.labels else "Node"
                end_label = end_node.labels[0] if end_node.labels else "Node"
                
                cypher = rel.to_cypher_create(start_label, end_label)
                statements.append(cypher)
                # Add parameters
                params = {
                    "start_id": rel.start_node_id,
                    "end_id": rel.end_node_id,
                    **rel.properties
                }
                statements.append(f"-- Parameters: {json.dumps(params, ensure_ascii=False)}")
                statements.append("")
        
        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(statements))
        
        logger.info(f"Generated Cypher statements: {output_path}")
    
    def get_graph_summary(self) -> str:
        """Get human-readable graph summary."""
        stats = self._generate_statistics()
        quality = self._generate_quality_report()
        
        summary_lines = [
            "KPK FORESTRY KNOWLEDGE GRAPH SUMMARY",
            "=" * 60,
            f"Total Nodes: {stats['nodes']['total']}",
            f"Total Relationships: {stats['relationships']['total']}",
            f"Abstention Nodes: {stats['nodes']['with_abstentions']}",
            f"KPK-Specific Nodes: {stats['nodes']['kpk_specific']}",
            f"Quality Score: {quality['overall_quality']:.2%}",
            "",
            "Node Distribution:"
        ]
        
        for label, count in sorted(stats['nodes']['by_label'].items()):
            if count > 0:
                summary_lines.append(f"  {label}: {count}")
        
        summary_lines.extend([
            "",
            "Relationship Distribution (Top 5):"
        ])
        
        for rel_type, count in sorted(stats['relationships']['by_type'].items(), 
                                    key=lambda x: x[1], reverse=True)[:5]:
            summary_lines.append(f"  {rel_type}: {count}")
        
        summary_lines.extend([
            "",
            "KPK Analysis:",
            f"  KPK Coverage: {stats['kpk_analysis']['kpk_nodes_percentage']:.1f}%",
            f"  Protected Species: {stats['kpk_analysis']['protected_species_count']}",
            f"  Forest Officers: {stats['kpk_analysis']['forest_officers_count']}",
            f"  Hazara Coverage: {stats['kpk_analysis']['hazara_coverage']}",
            "",
            "Quality Indicators:",
            f"  Completeness: {quality['completeness']:.2%}",
            f"  Consistency: {quality['consistency']:.2%}",
            f"  Richness: {quality['richness']:.2%}",
        ])
        
        if quality['recommendations']:
            summary_lines.extend([
                "",
                "Recommendations:"
            ])
            for rec in quality['recommendations'][:3]:
                summary_lines.append(f"  • {rec}")
        
        summary_lines.append("=" * 60)
        
        return "\n".join(summary_lines)


# Utility functions
def create_kpk_graph_builder() -> KPKGraphBuilder:
    """Factory function to create KPK graph builder."""
    return KPKGraphBuilder()


def build_and_export_graph(mapped_data: Dict, 
                         output_dir: Union[str, Path]) -> Dict[str, Any]:
    """Convenience function to build and export graph."""
    builder = KPKGraphBuilder()
    result = builder.build_graph_from_mapped_data(mapped_data)
    
    # Export to CSV
    file_paths = builder.export_to_csv(output_dir)
    
    return {
        'build_result': result,
        'file_paths': file_paths,
        'graph_summary': builder.get_graph_summary()
    }


# Example usage and testing
if __name__ == "__main__":
    print("=== Testing KPKGraphBuilder ===\n")
    
    # Create sample mapped data (output from 6.2_graph_mapper.py)
    sample_mapped_data = {
        "nodes": [
            {
                "label": "Law",
                "node_id": "LAW_KPK_FOREST_ORDINANCE_2002",
                "title": "KPK Forest Ordinance, 2002",
                "year": 2002,
                "jurisdiction": "provincial",
                "kpk_specific": True,
                "source_document": "kpk_forest_ordinance.pdf",
                "confidence_score": 0.95
            },
            {
                "label": "Section",
                "node_id": "SECTION_KPK_FO_2002_27",
                "section_number": "27",
                "title": "Penalty for unauthorized felling",
                "content": "Any person who fells Deodar or Kail tree without permission...",
                "law_id": "LAW_KPK_FOREST_ORDINANCE_2002",
                "confidence_score": 0.88
            },
            {
                "label": "Species",
                "node_id": "SPECIES_DEODAR",
                "common_name": "Deodar",
                "scientific_name": "Cedrus deodara",
                "legal_status": "protected",
                "kpk_endemic": True,
                "confidence_score": 0.92
            },
            {
                "label": "Location",
                "node_id": "LOCATION_SWAT_DIVISION",
                "name": "Swat, Malakand Division",
                "type": "division",
                "division": "Malakand",
                "district": "Swat",
                "confidence_score": 0.90
            },
            {
                "label": "Penalty",
                "node_id": "PENALTY_100000_PKR_FELLING",
                "amount": 100000,
                "currency": "PKR",
                "violation_type": "unauthorized_felling",
                "species_specific": "deodar",
                "confidence_score": 0.85
            }
        ],
        "relationships": [
            {
                "type": "HAS_SECTION",
                "from_id": "LAW_KPK_FOREST_ORDINANCE_2002",
                "to_id": "SECTION_KPK_FO_2002_27",
                "section_number": "27",
                "confidence": 0.95,
                "source_document": "kpk_forest_ordinance.pdf"
            },
            {
                "type": "IMPOSES",
                "from_id": "SECTION_KPK_FO_2002_27",
                "to_id": "PENALTY_100000_PKR_FELLING",
                "condition": "species_specific",
                "confidence": 0.85
            },
            {
                "type": "PROTECTS_SPECIES",
                "from_id": "LAW_KPK_FOREST_ORDINANCE_2002",
                "to_id": "SPECIES_DEODAR",
                "protection_level": "highest",
                "confidence": 0.90
            }
        ],
        "node_id_map": {},
        "metadata": {
            "pipeline_phase": "phase_6.2",
            "jurisdiction": "KPK",
            "timestamp": datetime.now().isoformat()
        },
        "mapping_statistics": {
            "abstention_cases": [
                {
                    "entity_id": "ambiguous_location_001",
                    "reason": "authority_conflict",
                    "entity_type": "Location",
                    "confidence": 0.4,
                    "node_id": "LOCATION_AMBIGUOUS_001"
                }
            ]
        }
    }
    
    # Build graph
    builder = KPKGraphBuilder()
    result = builder.build_graph_from_mapped_data(sample_mapped_data)
    
    print("Graph Build Result:")
    print("-" * 40)
    print(f"Nodes built: {result['build_summary']['nodes_count']}")
    print(f"Relationships built: {result['build_summary']['relationships_count']}")
    print(f"Abstention nodes: {result['build_summary']['abstention_nodes_count']}")
    
    print("\n" + "=" * 60)
    
    # Display graph summary
    print("\nGraph Summary:")
    print("-" * 40)
    print(builder.get_graph_summary())
    
    print("\n" + "=" * 60)
    
    # Display KPK entities summary
    print("\nKPK Entities Summary:")
    print("-" * 40)
    kpk_summary = result.get('kpk_entities_summary', {})
    print(f"KPK Laws: {kpk_summary.get('kpk_laws_count', 0)}")
    print(f"Protected Species: {kpk_summary.get('protected_species_count', 0)}")
    print(f"Forest Officers: {kpk_summary.get('forest_officers_count', 0)}")
    
    print("\n" + "=" * 60)
    
    # Export to CSV
    print("\nExporting to CSV...")
    output_dir = Path("kpk_graph_output")
    file_paths = builder.export_to_csv(output_dir)
    
    print(f"Files exported to {output_dir}:")
    for file_type, file_path in file_paths.items():
        print(f"  {file_type}: {file_path}")
    
    print("\n" + "=" * 60)
    print("KPKGraphBuilder Test Complete ✓")
