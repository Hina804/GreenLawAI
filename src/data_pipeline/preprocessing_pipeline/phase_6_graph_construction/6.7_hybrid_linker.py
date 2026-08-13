"""
HYBRID_LINKER.PY - Phase 6
Establishes links between Graph Nodes (Concept/Entity level) and Vector Chunks (Text level).
Enables Hybrid RAG by connecting semantic search results to structured knowledge graph.
"""
from typing import List, Dict, Any
import logging
import pickle
from typing import Dict, List, Tuple, Optional, Any, Union, Set, Callable
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import numpy as np
import networkx as nx
from collections import defaultdict, Counter
import faiss
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import from previous phases
try:
    from preprocessing_pipeline.phase_6_graph_construction import (
        NodeLabel, RelationshipType, FAISSIndexer, SearchResult, IndexedChunk
    )
except ImportError:
    try:
        from . import (
            NodeLabel, RelationshipType, FAISSIndexer, SearchResult, IndexedChunk
        )
    except (ImportError, ValueError):
        # Define minimal versions for standalone testing
        class NodeLabel:
            DOCUMENT_CHUNK = "DocumentChunk"
            LAW = "Law"
            SECTION = "Section"
            SPECIES = "Species"
            LOCATION = "Location"
            OFFICER = "Officer"
            PENALTY = "Penalty"
            ABSTENTION = "Abstention"
        
        class RelationshipType:
            HAS_CHUNK = "HAS_CHUNK"
            MENTIONS = "MENTIONS"
            SIMILAR_TO = "SIMILAR_TO"
            RELATED_TO = "RELATED_TO"
            ABSTAINS_FROM = "ABSTAINS_FROM"

    
    class FAISSIndexer:
        pass
    class SearchResult:
        pass
    class IndexedChunk:
        pass


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class HybridLink:
    """A link between FAISS vector and Neo4j entity."""
    link_id: str
    faiss_index_id: int
    neo4j_node_id: str
    link_type: str  # DIRECT, INDIRECT, SEMANTIC, GRAPH
    confidence: float
    similarity_score: float
    linking_method: str
    verification_status: str = "proposed" # proposed | validated | human_approved
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class GraphNodeContext:
    """Context information for a Neo4j node."""
    node_id: str
    node_labels: List[str]
    properties: Dict[str, Any]
    connected_entities: List[str]  # IDs of connected nodes
    relationship_types: List[str]
    centrality_score: float  # Importance in graph
    kpk_specific: bool

@dataclass
class HybridSearchResult:
    """Result from hybrid search."""
    entity_id: str
    entity_type: str
    similarity_score: float
    graph_relevance: float
    hybrid_score: float
    source: str  # "vector", "graph", "hybrid"
    explanation: str
    supporting_chunks: List[Dict[str, Any]]
    neo4j_node_data: Optional[Dict[str, Any]] = None

@dataclass
class LinkingStrategy:
    """Strategy for linking FAISS vectors to Neo4j."""
    name: str
    methods: List[str]  # DIRECT_MAPPING, ENTITY_MATCH, SEMANTIC_SIMILARITY, GRAPH_WALK
    confidence_threshold: float
    max_links_per_node: int
    enable_bidirectional: bool
    kpk_priority_boost: float

class Neo4jLinkManager:
    """Manages links between FAISS and Neo4j."""
    
    def __init__(self, faiss_indexer_path: Optional[Path] = None):
        self.links: Dict[str, HybridLink] = {}  # link_id -> HybridLink
        self.node_to_links: Dict[str, List[str]] = defaultdict(list)  # neo4j_node_id -> link_ids
        self.faiss_to_links: Dict[int, List[str]] = defaultdict(list)  # faiss_id -> link_ids
        
        # Graph structure for local caching
        self.local_graph = nx.Graph()
        self.node_contexts: Dict[str, GraphNodeContext] = {}
        
        # Statistics
        self.stats = {
            "total_links": 0,
            "by_type": Counter(),
            "by_node_type": Counter(),
            "average_confidence": 0.0,
            "kpk_links": 0
        }
        
        # Load FAISS indexer if provided
        self.faiss_indexer = None
        if faiss_indexer_path:
            self._load_faiss_indexer(faiss_indexer_path)
        
        logger.info("Neo4jLinkManager initialized")
    
    def _load_faiss_indexer(self, indexer_path: Path):
        """Load FAISS indexer from saved files."""
        try:
            # This would load the actual FAISS indexer
            # For now, we'll simulate it
            logger.info(f"Loading FAISS indexer from {indexer_path}")
            # In production, this would load the actual FAISS index
            self.faiss_indexer = {"loaded": True, "path": indexer_path}
        except Exception as e:
            logger.error(f"Failed to load FAISS indexer: {e}")
            self.faiss_indexer = None

    def link_nodes_to_vectors(self, graph_structure: Dict[str, Any], chunk_embeddings: Any) -> Dict[str, Any]:
        """Compatibility method for run_sequential_pipeline.py."""
        # Extract nodes from graph_structure
        nodes_by_type = graph_structure.get("nodes_by_type", {})
        all_nodes = []
        if nodes_by_type:
            for type_nodes in nodes_by_type.values():
                all_nodes.extend(type_nodes)
        else:
            all_nodes = graph_structure.get("nodes", [])
            
        # Get chunks from chunk_embeddings (EmbeddingBatch)
        faiss_chunks = []
        if hasattr(chunk_embeddings, 'embeddings'):
            for emb in chunk_embeddings.embeddings:
                faiss_chunks.append(IndexedChunk(
                    chunk_id=emb.chunk_id,
                    faiss_index_id=0, # Not needed for simple linking
                    neo4j_node_id="",
                    text="", # Text not available in EmbeddingBatch
                    metadata=emb.metadata,
                    embedding_hash=""
                ))
            
        strategy = LinkingStrategy("hybrid", ["direct", "entity"], 0.7, 5, True, 0.2)
        stats = self.create_links(faiss_chunks, all_nodes, strategy)
        
        # Return the modified graph_structure or a linked version
        graph_structure["links"] = [asdict(l) for l in self.links.values()]
        graph_structure["linking_stats"] = stats
        return graph_structure
    
    def create_links(self, faiss_chunks: List[IndexedChunk], 
                    neo4j_nodes: List[Dict[str, Any]],
                    strategy: LinkingStrategy) -> Dict[str, Any]:
        """
        Create links between FAISS chunks and Neo4j nodes.
        
        Args:
            faiss_chunks: Indexed chunks from FAISS
            neo4j_nodes: Nodes from Neo4j
            strategy: Linking strategy
            
        Returns:
            Linking statistics
        """
        logger.info(f"Creating links with strategy: {strategy.name}")
        logger.info(f"FAISS chunks: {len(faiss_chunks)}, Neo4j nodes: {len(neo4j_nodes)}")
        
        # Reset stats
        self._reset_stats()
        
        # Create local graph cache
        self._build_local_graph(neo4j_nodes)
        
        # Apply each linking method
        link_count = 0
        
        for method in strategy.methods:
            method_links = self._apply_linking_method(
                method, faiss_chunks, neo4j_nodes, strategy
            )
            link_count += len(method_links)
            
            logger.info(f"Method {method}: created {len(method_links)} links")
        
        # Post-process links
        self._post_process_links(strategy)
        
        # Generate statistics
        stats = self._generate_linking_statistics()
        
        logger.info(f"Linking complete: {link_count} total links created")
        return stats
    
    def _apply_linking_method(self, method: str, 
                             faiss_chunks: List[IndexedChunk],
                             neo4j_nodes: List[Dict[str, Any]],
                             strategy: LinkingStrategy) -> List[HybridLink]:
        """Apply a specific linking method."""
        if method == "DIRECT_MAPPING":
            return self._direct_mapping(faiss_chunks, neo4j_nodes, strategy)
        elif method == "ENTITY_MATCH":
            return self._entity_matching(faiss_chunks, neo4j_nodes, strategy)
        elif method == "SEMANTIC_SIMILARITY":
            return self._semantic_similarity(faiss_chunks, neo4j_nodes, strategy)
        elif method == "GRAPH_WALK":
            return self._graph_walk_linking(faiss_chunks, neo4j_nodes, strategy)
        else:
            logger.warning(f"Unknown linking method: {method}")
            return []
    
    def _direct_mapping(self, faiss_chunks: List[IndexedChunk],
                       neo4j_nodes: List[Dict[str, Any]],
                       strategy: LinkingStrategy) -> List[HybridLink]:
        """Direct mapping based on metadata."""
        links = []
        
        # Create lookup for Neo4j nodes
        neo4j_lookup = {node.get("node_id"): node for node in neo4j_nodes}
        
        for chunk in faiss_chunks:
            neo4j_node_id = chunk.neo4j_node_id
            
            if neo4j_node_id in neo4j_lookup:
                # Direct match found
                link = self._create_link(
                    chunk=chunk,
                    neo4j_node=neo4j_lookup[neo4j_node_id],
                    link_type="DIRECT",
                    confidence=1.0,
                    method="direct_mapping",
                    strategy=strategy
                )
                if link:
                    links.append(link)
        
        return links
    
    def _entity_matching(self, faiss_chunks: List[IndexedChunk],
                        neo4j_nodes: List[Dict[str, Any]],
                        strategy: LinkingStrategy) -> List[HybridLink]:
        """Match based on entity mentions in chunks."""
        links = []
        
        # Extract entities from Neo4j nodes
        node_entities = self._extract_node_entities(neo4j_nodes)
        
        for chunk in faiss_chunks:
            chunk_entities = chunk.metadata.get("entities_mentioned", [])
            
            for entity in chunk_entities:
                # Find matching Neo4j nodes
                matching_nodes = self._find_nodes_for_entity(entity, node_entities)
                
                for node_id in matching_nodes:
                    # Check if link already exists
                    if self._link_exists(chunk.faiss_index_id, node_id):
                        continue
                    
                    # Calculate confidence based on entity match strength
                    confidence = self._calculate_entity_match_confidence(entity, node_id, node_entities)
                    
                    # Apply KPK boost if applicable
                    if self._is_kpk_entity(entity) or self._is_kpk_node(node_id):
                        confidence *= strategy.kpk_priority_boost
                    
                    if confidence >= strategy.confidence_threshold:
                        node = next((n for n in neo4j_nodes if n.get("node_id") == node_id), None)
                        if node:
                            link = self._create_link(
                                chunk=chunk,
                                neo4j_node=node,
                                link_type="ENTITY_MATCH",
                                confidence=confidence,
                                method="entity_matching",
                                strategy=strategy,
                                metadata={"matched_entity": entity}
                            )
                            if link:
                                links.append(link)
        
        return links
    
    def _semantic_similarity(self, faiss_chunks: List[IndexedChunk],
                           neo4j_nodes: List[Dict[str, Any]],
                           strategy: LinkingStrategy) -> List[HybridLink]:
        """Create links based on semantic similarity of node properties and chunk text."""
        links = []
        
        # This would use embeddings of node properties
        # For now, we'll use text similarity
        for chunk in faiss_chunks:
            chunk_text = chunk.text.lower()
            
            for node in neo4j_nodes:
                node_id = node.get("node_id")
                
                # Skip if link already exists
                if self._link_exists(chunk.faiss_index_id, node_id):
                    continue
                
                # Calculate similarity based on shared terms
                node_text = self._extract_node_text(node).lower()
                similarity = self._calculate_text_similarity(chunk_text, node_text)
                
                # Apply KPK boost
                if self._is_kpk_chunk(chunk) or self._is_kpk_node(node_id):
                    similarity *= strategy.kpk_priority_boost
                
                if similarity >= strategy.confidence_threshold:
                    link = self._create_link(
                        chunk=chunk,
                        neo4j_node=node,
                        link_type="SEMANTIC",
                        confidence=similarity,
                        method="semantic_similarity",
                        strategy=strategy,
                        metadata={"similarity_score": similarity}
                    )
                    if link:
                        links.append(link)
        
        return links
    
    def _graph_walk_linking(self, faiss_chunks: List[IndexedChunk],
                          neo4j_nodes: List[Dict[str, Any]],
                          strategy: LinkingStrategy) -> List[HybridLink]:
        """Create links by walking the graph from directly linked nodes."""
        links = []
        
        # Start from existing direct links
        direct_links = [link for link in self.links.values() 
                       if link.link_type == "DIRECT"]
        
        for direct_link in direct_links:
            start_node_id = direct_link.neo4j_node_id
            chunk = next((c for c in faiss_chunks 
                         if c.faiss_index_id == direct_link.faiss_index_id), None)
            
            if not chunk:
                continue
            
            # Find nodes connected to start node
            connected_nodes = self._find_connected_nodes(start_node_id, max_depth=2)
            
            for node_id in connected_nodes:
                # Skip if link already exists
                if self._link_exists(chunk.faiss_index_id, node_id):
                    continue
                
                node = next((n for n in neo4j_nodes if n.get("node_id") == node_id), None)
                if node:
                    # Confidence decreases with graph distance
                    distance = self._get_graph_distance(start_node_id, node_id)
                    confidence = max(0.1, 1.0 - (distance * 0.3))
                    
                    if confidence >= strategy.confidence_threshold:
                        link = self._create_link(
                            chunk=chunk,
                            neo4j_node=node,
                            link_type="GRAPH_WALK",
                            confidence=confidence,
                            method="graph_walk",
                            strategy=strategy,
                            metadata={
                                "source_node": start_node_id,
                                "graph_distance": distance
                            }
                        )
                        if link:
                            links.append(link)
        
        return links
    
    def _create_link(self, chunk: IndexedChunk, neo4j_node: Dict[str, Any],
                    link_type: str, confidence: float, method: str,
                    strategy: LinkingStrategy, 
                    metadata: Optional[Dict] = None) -> Optional[HybridLink]:
        """Create a HybridLink object."""
        # Check max links per node
        node_id = neo4j_node.get("node_id")
        if len(self.node_to_links.get(node_id, [])) >= strategy.max_links_per_node:
            return None
        
        # Generate link ID
        link_id = f"link_{chunk.faiss_index_id}_{node_id}_{link_type}_{hashlib.md5(str(metadata).encode()).hexdigest()[:8]}"
        
        # Prepare metadata
        link_metadata = metadata or {}
        link_metadata.update({
            "linking_method": method,
            "chunk_text_preview": chunk.text[:100],
            "node_type": neo4j_node.get("labels", ["Unknown"])[0],
            "created_at": datetime.now().isoformat(),
            "is_kpk_chunk": self._is_kpk_chunk(chunk),
            "is_kpk_node": self._is_kpk_node(node_id)
        })
        
        link = HybridLink(
            link_id=link_id,
            faiss_index_id=chunk.faiss_index_id,
            neo4j_node_id=node_id,
            link_type=link_type,
            confidence=confidence,
            similarity_score=metadata.get("similarity_score", confidence),
            linking_method=method,
            verification_status="proposed",
            metadata=link_metadata
        )
        
        # Store the link
        self.links[link_id] = link
        self.node_to_links[node_id].append(link_id)
        self.faiss_to_links[chunk.faiss_index_id].append(link_id)
        
        # Update statistics
        self.stats["total_links"] += 1
        self.stats["by_type"][link_type] += 1
        self.stats["average_confidence"] = (
            (self.stats["average_confidence"] * (self.stats["total_links"] - 1) + confidence) 
            / self.stats["total_links"]
        )
        
        # Track KPK links
        if link_metadata.get("is_kpk_chunk") or link_metadata.get("is_kpk_node"):
            self.stats["kpk_links"] += 1
        
        return link
    
    def _link_exists(self, faiss_id: int, node_id: str) -> bool:
        """Check if a link already exists."""
        for link_id in self.faiss_to_links.get(faiss_id, []):
            link = self.links.get(link_id)
            if link and link.neo4j_node_id == node_id:
                return True
        return False
    
    def _is_kpk_chunk(self, chunk: IndexedChunk) -> bool:
        """Check if chunk is KPK-specific."""
        metadata = chunk.metadata
        text = chunk.text.lower()
        
        # Check metadata
        if metadata.get("is_kpk_document", False):
            return True
        
        # Check text for KPK keywords
        kpk_keywords = ["kpk", "khyber pakhtunkhwa", "hazara", "deodar", "kail", "dfo", "swat"]
        return any(keyword in text for keyword in kpk_keywords)
    
    def _is_kpk_node(self, node_id: str) -> bool:
        """Check if node is KPK-specific."""
        # Check node ID for KPK patterns
        node_id_lower = node_id.lower()
        kpk_patterns = ["kpk", "khyber", "hazara", "swat", "abbottabad", "mansehra"]
        return any(pattern in node_id_lower for pattern in kpk_patterns)
    
    def _is_kpk_entity(self, entity: str) -> bool:
        """Check if entity is KPK-specific."""
        entity_lower = entity.lower()
        kpk_entities = ["deodar", "kail", "fir", "spruce", "hazara", "swat", "dfo"]
        return any(kpk_entity in entity_lower for kpk_entity in kpk_entities)
    
    def _build_local_graph(self, neo4j_nodes: List[Dict[str, Any]]):
        """Build a local graph cache from Neo4j nodes."""
        self.local_graph.clear()
        self.node_contexts.clear()
        
        for node in neo4j_nodes:
            node_id = node.get("node_id")
            labels = node.get("labels", [])
            properties = node.get("properties", {})
            
            # Add node to graph
            self.local_graph.add_node(node_id, labels=labels, properties=properties)
            
            # Create node context
            context = GraphNodeContext(
                node_id=node_id,
                node_labels=labels,
                properties=properties,
                connected_entities=[],
                relationship_types=[],
                centrality_score=0.0,
                kpk_specific=self._is_kpk_node(node_id)
            )
            
            self.node_contexts[node_id] = context
        
        logger.info(f"Built local graph with {len(self.local_graph.nodes())} nodes")
    
    def _extract_node_entities(self, neo4j_nodes: List[Dict[str, Any]]) -> Dict[str, Set[str]]:
        """Extract entities from Neo4j nodes."""
        node_entities = defaultdict(set)
        
        for node in neo4j_nodes:
            node_id = node.get("node_id")
            properties = node.get("properties", {})
            
            # Extract entities from properties
            if "name" in properties:
                node_entities[node_id].add(f"name:{properties['name']}")
            if "title" in properties:
                node_entities[node_id].add(f"title:{properties['title']}")
            if "common_name" in properties:
                node_entities[node_id].add(f"species:{properties['common_name']}")
            if "scientific_name" in properties:
                node_entities[node_id].add(f"species:{properties['scientific_name']}")
            
            # Add KPK flag if applicable
            if self._is_kpk_node(node_id):
                node_entities[node_id].add("kpk:true")
        
        return node_entities
    
    def _find_nodes_for_entity(self, entity: str, node_entities: Dict[str, Set[str]]) -> List[str]:
        """Find nodes that match an entity."""
        matching_nodes = []
        
        for node_id, entities in node_entities.items():
            # Check for exact match or partial match
            if any(entity.lower() in e.lower() for e in entities):
                matching_nodes.append(node_id)
            elif ":" in entity:
                # Check type match
                entity_type = entity.split(":")[0]
                if any(e.startswith(entity_type + ":") for e in entities):
                    matching_nodes.append(node_id)
        
        return matching_nodes
    
    def _calculate_entity_match_confidence(self, entity: str, node_id: str, 
                                         node_entities: Dict[str, Set[str]]) -> float:
        """Calculate confidence for entity match."""
        entities = node_entities.get(node_id, set())
        
        # Exact match
        if entity in entities:
            return 1.0
        
        # Partial match
        for e in entities:
            if entity.lower() in e.lower() or e.lower() in entity.lower():
                return 0.8
        
        # Type match
        if ":" in entity:
            entity_type = entity.split(":")[0]
            if any(e.startswith(entity_type + ":") for e in entities):
                return 0.6
        
        return 0.0
    
    def _extract_node_text(self, node: Dict[str, Any]) -> str:
        """Extract text from node properties."""
        text_parts = []
        properties = node.get("properties", {})
        
        # Add relevant properties
        for key in ["title", "name", "common_name", "description", "content"]:
            if key in properties:
                text_parts.append(str(properties[key]))
        
        return " ".join(text_parts)
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple text similarity."""
        if not text1 or not text2:
            return 0.0
        
        # Simple Jaccard similarity on words
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
    
    def _find_connected_nodes(self, start_node_id: str, max_depth: int = 2) -> Set[str]:
        """Find nodes connected to start node within max_depth."""
        connected = set()
        
        # This would query Neo4j in production
        # For now, we'll simulate with local graph
        if start_node_id in self.local_graph:
            # Get neighbors within max_depth
            for depth in range(1, max_depth + 1):
                # BFS to get nodes at this depth
                # Simplified for now
                pass
        
        return connected
    
    def _get_graph_distance(self, node1_id: str, node2_id: str) -> int:
        """Get distance between two nodes in graph."""
        try:
            if node1_id in self.local_graph and node2_id in self.local_graph:
                # Try to find shortest path
                try:
                    path = nx.shortest_path(self.local_graph, node1_id, node2_id)
                    return len(path) - 1  # Distance is path length - 1
                except nx.NetworkXNoPath:
                    return 999  # No path found
        except:
            pass
        
        return 999  # Default large distance
    
    def _post_process_links(self, strategy: LinkingStrategy):
        """Post-process links after creation."""
        # Remove low-confidence links
        links_to_remove = []
        for link_id, link in self.links.items():
            if link.confidence < strategy.confidence_threshold:
                links_to_remove.append(link_id)
        
        for link_id in links_to_remove:
            self._remove_link(link_id)
        
        # Create bidirectional links if enabled
        if strategy.enable_bidirectional:
            self._create_bidirectional_links()
        
        # Update graph centrality scores
        self._update_centrality_scores()
    
    def _remove_link(self, link_id: str):
        """Remove a link from all data structures."""
        if link_id in self.links:
            link = self.links[link_id]
            
            # Remove from node_to_links
            if link.neo4j_node_id in self.node_to_links:
                self.node_to_links[link.neo4j_node_id] = [
                    lid for lid in self.node_to_links[link.neo4j_node_id]
                    if lid != link_id
                ]
            
            # Remove from faiss_to_links
            if link.faiss_index_id in self.faiss_to_links:
                self.faiss_to_links[link.faiss_index_id] = [
                    lid for lid in self.faiss_to_links[link.faiss_index_id]
                    if lid != link_id
                ]
            
            # Remove from links
            del self.links[link_id]
            
            # Update stats
            self.stats["total_links"] -= 1
    
    def _create_bidirectional_links(self):
        """Create bidirectional links for graph traversal."""
        # For each link, check if reverse link exists
        links_to_add = []
        
        for link in self.links.values():
            # Create reverse link ID
            reverse_link_id = f"rev_{link.link_id}"
            
            if reverse_link_id not in self.links:
                reverse_link = HybridLink(
                    link_id=reverse_link_id,
                    faiss_index_id=link.faiss_index_id,  # Same FAISS ID
                    neo4j_node_id=link.neo4j_node_id,  # Same node
                    link_type=f"REVERSE_{link.link_type}",
                    confidence=link.confidence * 0.9,  # Slightly lower confidence
                    metadata={
                        **link.metadata,
                        "is_bidirectional": True,
                        "original_link": link.link_id
                    }
                )
                
                links_to_add.append(reverse_link)
        
        # Add reverse links
        for link in links_to_add:
            self.links[link.link_id] = link
            self.node_to_links[link.neo4j_node_id].append(link.link_id)
            self.faiss_to_links[link.faiss_index_id].append(link.link_id)
            
            self.stats["total_links"] += 1
            self.stats["by_type"][link.link_type] += 1
    
    def _update_centrality_scores(self):
        """Update centrality scores for nodes based on link structure."""
        # Build link graph
        link_graph = nx.Graph()
        
        # Add nodes
        for node_id in self.node_to_links.keys():
            link_graph.add_node(node_id)
        
        # Add edges based on shared FAISS chunks
        faiss_to_nodes = defaultdict(set)
        for link in self.links.values():
            faiss_to_nodes[link.faiss_index_id].add(link.neo4j_node_id)
        
        # Create edges between nodes sharing FAISS chunks
        for nodes in faiss_to_nodes.values():
            node_list = list(nodes)
            for i in range(len(node_list)):
                for j in range(i + 1, len(node_list)):
                    link_graph.add_edge(node_list[i], node_list[j], weight=1.0)
        
        # Calculate centrality
        if link_graph.number_of_nodes() > 0:
            centrality = nx.degree_centrality(link_graph)
            
            # Update node contexts
            for node_id, score in centrality.items():
                if node_id in self.node_contexts:
                    self.node_contexts[node_id].centrality_score = score
    
    def _generate_linking_statistics(self) -> Dict[str, Any]:
        """Generate comprehensive linking statistics."""
        total_links = self.stats["total_links"]
        
        # Calculate coverage
        total_nodes = len(self.node_to_links)
        nodes_with_links = sum(1 for links in self.node_to_links.values() if links)
        node_coverage = nodes_with_links / total_nodes if total_nodes > 0 else 0
        
        # Calculate link density
        links_per_node = total_links / total_nodes if total_nodes > 0 else 0
        
        # KPK analysis
        kpk_nodes = sum(1 for node_id in self.node_to_links.keys() 
                       if self._is_kpk_node(node_id))
        kpk_coverage = kpk_nodes / total_nodes if total_nodes > 0 else 0
        
        return {
            "total_links": total_links,
            "link_types": dict(self.stats["by_type"]),
            "node_coverage": {
                "total_nodes": total_nodes,
                "nodes_with_links": nodes_with_links,
                "coverage_percentage": node_coverage * 100,
                "average_links_per_node": links_per_node
            },
            "confidence_metrics": {
                "average_confidence": self.stats["average_confidence"],
                "high_confidence_links": sum(1 for link in self.links.values() 
                                           if link.confidence >= 0.8),
                "medium_confidence_links": sum(1 for link in self.links.values() 
                                             if 0.5 <= link.confidence < 0.8),
                "low_confidence_links": sum(1 for link in self.links.values() 
                                          if link.confidence < 0.5)
            },
            "kpk_analysis": {
                "kpk_links": self.stats["kpk_links"],
                "kpk_nodes": kpk_nodes,
                "kpk_coverage_percentage": kpk_coverage * 100,
                "kpk_link_density": self.stats["kpk_links"] / total_links if total_links > 0 else 0
            },
            "graph_metrics": {
                "connected_components": nx.number_connected_components(self.local_graph) 
                                       if self.local_graph else 0,
                "average_centrality": np.mean([ctx.centrality_score 
                                             for ctx in self.node_contexts.values()]) 
                                     if self.node_contexts else 0
            }
        }
    
    def _reset_stats(self):
        """Reset statistics."""
        self.stats = {
            "total_links": 0,
            "by_type": Counter(),
            "by_node_type": Counter(),
            "average_confidence": 0.0,
            "kpk_links": 0
        }
    
    def hybrid_search(self, query_embedding: np.ndarray,
                     faiss_results: List[SearchResult],
                     neo4j_context: Optional[Dict[str, Any]] = None,
                     k: int = 10) -> List[HybridSearchResult]:
        """
        Perform hybrid search combining FAISS and graph.
        
        Args:
            query_embedding: Query embedding
            faiss_results: FAISS search results
            neo4j_context: Neo4j context information
            k: Number of results
            
        Returns:
            Hybrid search results
        """
        # Step 1: Get initial FAISS results
        initial_results = faiss_results[:k * 2]
        
        # Step 2: Expand via graph links
        expanded_results = self._expand_via_graph_links(initial_results, neo4j_context)
        
        # Step 3: Combine and rank
        ranked_results = self._rank_hybrid_results(expanded_results, query_embedding, neo4j_context)
        
        return ranked_results[:k]
    
    def _expand_via_graph_links(self, faiss_results: List[SearchResult],
                               neo4j_context: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Expand FAISS results via graph links."""
        expanded = []
        
        for result in faiss_results:
            # Get Neo4j node for this chunk
            node_id = result.neo4j_node_id
            
            # Add the original result
            expanded.append({
                "entity_id": node_id,
                "entity_type": "direct",
                "similarity_score": result.similarity_score,
                "graph_relevance": 1.0,  # Direct match
                "source": "vector",
                "explanation": f"Direct FAISS match: {result.similarity_score:.3f}",
                "supporting_chunks": [{
                    "chunk_id": result.chunk_id,
                    "text": result.text,
                    "score": result.similarity_score
                }]
            })
            
            # Expand via graph links
            linked_nodes = self._get_linked_nodes(node_id, max_hops=2)
            
            for linked_node_id, link in linked_nodes.items():
                # Calculate graph relevance
                graph_relevance = self._calculate_graph_relevance(node_id, linked_node_id, link)
                
                expanded.append({
                    "entity_id": linked_node_id,
                    "entity_type": link.get("type", "linked"),
                    "similarity_score": result.similarity_score * 0.8,  # Discounted
                    "graph_relevance": graph_relevance,
                    "source": "graph",
                    "explanation": f"Graph link from {node_id} via {link.get('link_type', 'link')}",
                    "supporting_chunks": [{
                        "chunk_id": result.chunk_id,
                        "text": f"Linked from: {result.text[:100]}...",
                        "score": result.similarity_score * graph_relevance
                    }]
                })
        
        return expanded
    
    def _get_linked_nodes(self, node_id: str, max_hops: int = 2) -> Dict[str, Dict]:
        """Get nodes linked to the given node."""
        linked = {}
        
        # Get direct links
        for link_id in self.node_to_links.get(node_id, []):
            link = self.links.get(link_id)
            if link:
                # The link connects FAISS to Neo4j, not Neo4j to Neo4j
                # For graph expansion, we need Neo4j to Neo4j links
                # This would come from actual Neo4j relationships
                pass
        
        # In production, this would query Neo4j for connected nodes
        # For now, we'll simulate with local graph
        
        return linked
    
    def _calculate_graph_relevance(self, source_node: str, target_node: str, 
                                  link_info: Dict) -> float:
        """Calculate relevance based on graph connection."""
        # Base relevance
        relevance = 1.0
        
        # Adjust based on link type
        link_type = link_info.get("type", "")
        if "DIRECT" in link_type:
            relevance *= 1.0
        elif "ENTITY" in link_type:
            relevance *= 0.8
        elif "SEMANTIC" in link_type:
            relevance *= 0.7
        elif "GRAPH" in link_type:
            relevance *= 0.6
        
        # Adjust based on distance
        distance = link_info.get("distance", 1)
        relevance *= (1.0 / distance)
        
        # Adjust based on confidence
        confidence = link_info.get("confidence", 1.0)
        relevance *= confidence
        
        return relevance
    
    def _rank_hybrid_results(self, results: List[Dict[str, Any]],
                            query_embedding: np.ndarray,
                            neo4j_context: Optional[Dict[str, Any]]) -> List[HybridSearchResult]:
        """Rank hybrid search results."""
        ranked = []
        
        for result in results:
            # Calculate hybrid score
            similarity = result.get("similarity_score", 0.0)
            graph_relevance = result.get("graph_relevance", 0.0)
            
            # Weights can be adjusted based on context
            if neo4j_context and neo4j_context.get("prefer_graph", False):
                vector_weight = 0.3
                graph_weight = 0.7
            else:
                vector_weight = 0.7
                graph_weight = 0.3
            
            hybrid_score = (similarity * vector_weight) + (graph_relevance * graph_weight)
            
            # Apply KPK boost if applicable
            if self._is_kpk_node(result["entity_id"]):
                hybrid_score *= 1.2
            
            # Create HybridSearchResult
            hybrid_result = HybridSearchResult(
                entity_id=result["entity_id"],
                entity_type=result["entity_type"],
                similarity_score=similarity,
                graph_relevance=graph_relevance,
                hybrid_score=hybrid_score,
                source=result["source"],
                explanation=result["explanation"],
                supporting_chunks=result["supporting_chunks"]
            )
            
            ranked.append(hybrid_result)
        
        # Sort by hybrid score
        ranked.sort(key=lambda x: x.hybrid_score, reverse=True)
        
        return ranked
    
    def generate_neo4j_relationships(self) -> List[Dict[str, Any]]:
        """Generate Neo4j relationships from links."""
        relationships = []
        
        for link in self.links.values():
            # Create relationship between DocumentChunk and Neo4j node
            relationship = {
                "start_node_id": f"DocumentChunk_{link.faiss_index_id}",
                "end_node_id": link.neo4j_node_id,
                "type": self._map_link_type_to_relationship(link.link_type),
                "properties": {
                    "link_id": link.link_id,
                    "confidence": link.confidence,
                    "linking_method": link.metadata.get("linking_method", "unknown"),
                    "created_at": link.created_at,
                    "is_kpk": link.metadata.get("is_kpk_chunk", False) or 
                             link.metadata.get("is_kpk_node", False)
                }
            }
            
            relationships.append(relationship)
        
        return relationships
    
    def _map_link_type_to_relationship(self, link_type: str) -> str:
        """Map internal link type to Neo4j relationship type."""
        mapping = {
            "DIRECT": "HAS_CHUNK",
            "ENTITY_MATCH": "MENTIONS",
            "SEMANTIC": "RELATED_TO",
            "GRAPH_WALK": "CONNECTED_TO",
            "REVERSE_DIRECT": "HAS_SOURCE",
            "REVERSE_ENTITY_MATCH": "MENTIONED_IN",
            "REVERSE_SEMANTIC": "RELATED_FROM",
            "REVERSE_GRAPH_WALK": "CONNECTED_FROM"
        }
        
        return mapping.get(link_type, "LINKED_TO")
    
    def save_links(self, output_dir: Union[str, Path]) -> Dict[str, Path]:
        """
        Save links to disk.
        
        Args:
            output_dir: Directory to save files
            
        Returns:
            Dict of saved file paths
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        file_paths = {}
        
        # Save links as JSON
        links_path = output_dir / "hybrid_links.json"
        links_data = {
            "links": [
                {
                    "link_id": link.link_id,
                    "faiss_index_id": link.faiss_index_id,
                    "neo4j_node_id": link.neo4j_node_id,
                    "link_type": link.link_type,
                    "confidence": link.confidence,
                    "metadata": link.metadata,
                    "created_at": link.created_at
                }
                for link in self.links.values()
            ],
            "statistics": self._generate_linking_statistics(),
            "save_timestamp": datetime.now().isoformat()
        }
        
        with open(links_path, 'w', encoding='utf-8') as f:
            json.dump(links_data, f, indent=2, ensure_ascii=False)
        
        file_paths["links"] = links_path
        
        # Save Neo4j relationships
        relationships_path = output_dir / "neo4j_relationships.json"
        relationships = self.generate_neo4j_relationships()
        
        with open(relationships_path, 'w', encoding='utf-8') as f:
            json.dump(relationships, f, indent=2, ensure_ascii=False)
        
        file_paths["relationships"] = relationships_path
        
        # Save mapping structures
        mapping_path = output_dir / "link_mappings.pkl"
        mapping_data = {
            "node_to_links": dict(self.node_to_links),
            "faiss_to_links": dict(self.faiss_to_links)
        }
        
        with open(mapping_path, 'wb') as f:
            pickle.dump(mapping_data, f)
        
        file_paths["mappings"] = mapping_path
        
        # Save local graph
        graph_path = output_dir / "local_graph.pkl"
        with open(graph_path, 'wb') as f:
            pickle.dump(self.local_graph, f)
        
        file_paths["graph"] = graph_path
        
        logger.info(f"Saved {len(self.links)} links to {output_dir}")
        return file_paths
    
    def load_links(self, input_dir: Union[str, Path]) -> bool:
        """
        Load links from disk.
        
        Args:
            input_dir: Directory containing saved files
            
        Returns:
            True if successful
        """
        input_dir = Path(input_dir)
        
        try:
            # Load links
            links_path = input_dir / "hybrid_links.json"
            if links_path.exists():
                with open(links_path, 'r', encoding='utf-8') as f:
                    links_data = json.load(f)
                
                # Recreate links
                self.links.clear()
                for link_data in links_data.get("links", []):
                    link = HybridLink(**link_data)
                    self.links[link.link_id] = link
                
                logger.info(f"Loaded {len(self.links)} links from {links_path}")
            else:
                logger.warning(f"Links file not found: {links_path}")
                return False
            
            # Load mappings
            mapping_path = input_dir / "link_mappings.pkl"
            if mapping_path.exists():
                with open(mapping_path, 'rb') as f:
                    mapping_data = pickle.load(f)
                
                self.node_to_links = defaultdict(list, mapping_data.get("node_to_links", {}))
                self.faiss_to_links = defaultdict(list, mapping_data.get("faiss_to_links", {}))
            
            # Load graph
            graph_path = input_dir / "local_graph.pkl"
            if graph_path.exists():
                with open(graph_path, 'rb') as f:
                    self.local_graph = pickle.load(f)
            
            logger.info(f"Successfully loaded links from {input_dir}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load links: {e}")
            return False

class KPKHybridLinker:
    """Main class for KPK-specific hybrid linking."""
    
    def __init__(self, faiss_indexer_path: Optional[Path] = None):
        self.link_manager = Neo4jLinkManager(faiss_indexer_path)
        self.strategies = self._initialize_strategies()
        
        # KPK-specific configurations
        self.kpk_entity_priority = {
            "species": 1.3,
            "location": 1.2,
            "officer": 1.1,
            "law": 1.0,
            "penalty": 1.0,
            "abstention": 0.8
        }
        
        logger.info("KPKHybridLinker initialized")
    
    def _initialize_strategies(self) -> Dict[str, LinkingStrategy]:
        """Initialize linking strategies."""
        return {
            "comprehensive": LinkingStrategy(
                name="comprehensive",
                methods=["DIRECT_MAPPING", "ENTITY_MATCH", "SEMANTIC_SIMILARITY", "GRAPH_WALK"],
                confidence_threshold=0.5,
                max_links_per_node=10,
                enable_bidirectional=True,
                kpk_priority_boost=1.2
            ),
            "kpk_focused": LinkingStrategy(
                name="kpk_focused",
                methods=["ENTITY_MATCH", "GRAPH_WALK"],
                confidence_threshold=0.4,  # Lower threshold for KPK
                max_links_per_node=15,
                enable_bidirectional=True,
                kpk_priority_boost=1.5  # Higher boost for KPK
            ),
            "precision": LinkingStrategy(
                name="precision",
                methods=["DIRECT_MAPPING", "ENTITY_MATCH"],
                confidence_threshold=0.7,
                max_links_per_node=5,
                enable_bidirectional=False,
                kpk_priority_boost=1.1
            )
        }
    
    def create_hybrid_graph(self, faiss_chunks: List[IndexedChunk],
                          neo4j_nodes: List[Dict[str, Any]],
                          strategy_name: str = "comprehensive") -> Dict[str, Any]:
        """
        Create hybrid graph linking FAISS and Neo4j.
        
        Args:
            faiss_chunks: FAISS indexed chunks
            neo4j_nodes: Neo4j nodes
            strategy_name: Linking strategy to use
            
        Returns:
            Linking results and statistics
        """
        strategy = self.strategies.get(strategy_name)
        if not strategy:
            logger.error(f"Unknown strategy: {strategy_name}")
            return {"error": f"Unknown strategy: {strategy_name}"}
        
        logger.info(f"Creating hybrid graph with {strategy_name} strategy")
        
        # Enhance chunks with KPK metadata
        enhanced_chunks = self._enhance_chunks_with_kpk(faiss_chunks)
        
        # Enhance nodes with KPK metadata
        enhanced_nodes = self._enhance_nodes_with_kpk(neo4j_nodes)
        
        # Create links
        stats = self.link_manager.create_links(enhanced_chunks, enhanced_nodes, strategy)
        
        # Generate KPK-specific analysis
        kpk_analysis = self._analyze_kpk_coverage()
        
        # Generate Neo4j import data
        neo4j_import = self._generate_neo4j_import_data()
        
        return {
            "linking_statistics": stats,
            "kpk_analysis": kpk_analysis,
            "neo4j_import": neo4j_import,
            "strategy_used": strategy_name,
            "timestamp": datetime.now().isoformat()
        }
    
    def _enhance_chunks_with_kpk(self, chunks: List[IndexedChunk]) -> List[IndexedChunk]:
        """Enhance chunks with KPK metadata."""
        enhanced = []
        
        for chunk in chunks:
            # Create enhanced metadata
            enhanced_metadata = chunk.metadata.copy()
            
            # Add KPK classification
            is_kpk = self._classify_kpk_chunk(chunk)
            enhanced_metadata["is_kpk_chunk"] = is_kpk
            
            # Add KPK entity flags
            kpk_entities = self._extract_kpk_entities(chunk)
            enhanced_metadata["kpk_entities"] = kpk_entities
            
            # Add priority score
            priority = self._calculate_kpk_priority(chunk, kpk_entities)
            enhanced_metadata["kpk_priority"] = priority
            
            # Create enhanced chunk
            enhanced_chunk = IndexedChunk(
                chunk_id=chunk.chunk_id,
                faiss_index_id=chunk.faiss_index_id,
                neo4j_node_id=chunk.neo4j_node_id,
                text=chunk.text,
                metadata=enhanced_metadata,
                embedding_hash=chunk.embedding_hash,
                created_at=chunk.created_at
            )
            
            enhanced.append(enhanced_chunk)
        
        return enhanced
    
    def _classify_kpk_chunk(self, chunk: IndexedChunk) -> bool:
        """Classify if chunk is KPK-specific."""
        text = chunk.text.lower()
        metadata = chunk.metadata
        
        # Check metadata
        if metadata.get("is_kpk_document", False):
            return True
        
        # Check for KPK keywords
        kpk_keywords = [
            "kpk", "khyber pakhtunkhwa", "nwfp", "hazara",
            "deodar", "kail", "fir", "spruce",
            "swat", "dir", "malakand", "abbottabad", "mansehra"
        ]
        
        if any(keyword in text for keyword in kpk_keywords):
            return True
        
        # Check for KPK entities
        entities = metadata.get("entities_mentioned", [])
        kpk_entity_patterns = ["species:deodar", "species:kail", "location:hazara", "officer:dfo"]
        
        if any(any(pattern in entity for pattern in kpk_entity_patterns) for entity in entities):
            return True
        
        return False
    
    def _extract_kpk_entities(self, chunk: IndexedChunk) -> List[str]:
        """Extract KPK-specific entities from chunk."""
        kpk_entities = []
        entities = chunk.metadata.get("entities_mentioned", [])
        
        kpk_entity_map = {
            "species": ["deodar", "kail", "fir", "spruce", "chir pine", "oak"],
            "location": ["hazara", "swat", "dir", "malakand", "abbottabad", "mansehra"],
            "officer": ["dfo", "range officer", "beat guard", "conservator"]
        }
        
        for entity in entities:
            if ":" in entity:
                entity_type, entity_name = entity.split(":", 1)
                if entity_type in kpk_entity_map:
                    if any(kpk_entity in entity_name.lower() for kpk_entity in kpk_entity_map[entity_type]):
                        kpk_entities.append(entity)
        
        return kpk_entities
    
    def _calculate_kpk_priority(self, chunk: IndexedChunk, kpk_entities: List[str]) -> float:
        """Calculate KPK priority score for chunk."""
        priority = 1.0
        
        # Base priority
        if self._classify_kpk_chunk(chunk):
            priority *= 1.5
        
        # Entity-based priority
        for entity in kpk_entities:
            if ":" in entity:
                entity_type = entity.split(":")[0]
                priority *= self.kpk_entity_priority.get(entity_type, 1.0)
        
        # Content-based priority
        text = chunk.text.lower()
        if any(keyword in text for keyword in ["penalty", "fine", "punishment"]):
            priority *= 1.2  # Legal provisions are important
        
        if any(keyword in text for keyword in ["permit", "license", "authorization"]):
            priority *= 1.1  # Administrative content
        
        return priority
    
    def _enhance_nodes_with_kpk(self, nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enhance Neo4j nodes with KPK metadata."""
        enhanced = []
        
        for node in nodes:
            # Create enhanced node
            enhanced_node = node.copy()
            
            # Add KPK classification
            node_id = node.get("node_id", "")
            is_kpk = self._classify_kpk_node(node_id, node)
            enhanced_node["is_kpk_node"] = is_kpk
            
            # Add KPK priority
            priority = self._calculate_node_kpk_priority(node_id, node, is_kpk)
            enhanced_node["kpk_priority"] = priority
            
            enhanced.append(enhanced_node)
        
        return enhanced
    
    def _classify_kpk_node(self, node_id: str, node: Dict[str, Any]) -> bool:
        """Classify if node is KPK-specific."""
        node_id_lower = node_id.lower()
        
        # Check node ID
        kpk_patterns = ["kpk", "khyber", "hazara", "swat", "dir", "malakand"]
        if any(pattern in node_id_lower for pattern in kpk_patterns):
            return True
        
        # Check properties
        properties = node.get("properties", {})
        
        # Check for KPK in properties
        for value in properties.values():
            if isinstance(value, str):
                value_lower = value.lower()
                if any(pattern in value_lower for pattern in kpk_patterns):
                    return True
        
        # Check labels
        labels = node.get("labels", [])
        if any("KPK" in label or "Hazara" in label for label in labels):
            return True
        
        return False
    
    def _calculate_node_kpk_priority(self, node_id: str, node: Dict[str, Any], is_kpk: bool) -> float:
        """Calculate KPK priority score for node."""
        priority = 1.0
        
        if is_kpk:
            priority *= 1.5
        
        # Entity type priority
        labels = node.get("labels", [])
        for label in labels:
            label_lower = label.lower()
            if "species" in label_lower:
                priority *= self.kpk_entity_priority["species"]
            elif "location" in label_lower:
                priority *= self.kpk_entity_priority["location"]
            elif "officer" in label_lower:
                priority *= self.kpk_entity_priority["officer"]
            elif "law" in label_lower:
                priority *= self.kpk_entity_priority["law"]
        
        # Check for Hazara specificity
        if "hazara" in node_id.lower():
            priority *= 1.3  # Extra boost for Hazara
        
        return priority
    
    def _analyze_kpk_coverage(self) -> Dict[str, Any]:
        """Analyze KPK coverage in links."""
        links = self.link_manager.links
        node_contexts = self.link_manager.node_contexts
        
        # Count KPK links
        kpk_links = sum(1 for link in links.values() 
                       if link.metadata.get("is_kpk_chunk", False) or 
                          link.metadata.get("is_kpk_node", False))
        
        # Count KPK nodes
        kpk_nodes = sum(1 for ctx in node_contexts.values() 
                       if ctx.kpk_specific)
        
        # Analyze KPK entity distribution
        entity_distribution = Counter()
        for link in links.values():
            if link.metadata.get("is_kpk_chunk", False):
                entities = link.metadata.get("kpk_entities", [])
                for entity in entities:
                    if ":" in entity:
                        entity_type = entity.split(":")[0]
                        entity_distribution[entity_type] += 1
        
        total_links = len(links)
        total_nodes = len(node_contexts)
        
        return {
            "kpk_links_count": kpk_links,
            "kpk_nodes_count": kpk_nodes,
            "kpk_link_coverage": (kpk_links / total_links * 100) if total_links > 0 else 0,
            "kpk_node_coverage": (kpk_nodes / total_nodes * 100) if total_nodes > 0 else 0,
            "kpk_entity_distribution": dict(entity_distribution),
            "recommendations": self._generate_kpk_recommendations(kpk_links, total_links, 
                                                               kpk_nodes, total_nodes)
        }
    
    def _generate_kpk_recommendations(self, kpk_links: int, total_links: int,
                                     kpk_nodes: int, total_nodes: int) -> List[str]:
        """Generate recommendations for improving KPK coverage."""
        recommendations = []
        
        # Check KPK link coverage
        link_coverage = kpk_links / total_links if total_links > 0 else 0
        if link_coverage < 0.3:
            recommendations.append("Increase linking of KPK-specific chunks to improve coverage")
        
        # Check KPK node coverage
        node_coverage = kpk_nodes / total_nodes if total_nodes > 0 else 0
        if node_coverage < 0.4:
            recommendations.append("Add more KPK-specific nodes to the graph")
        
        # Check for Hazara coverage
        hazara_links = sum(1 for link in self.link_manager.links.values() 
                          if "hazara" in link.metadata.get("matched_entity", "").lower() or
                             "hazara" in link.neo4j_node_id.lower())
        
        if hazara_links == 0:
            recommendations.append("Include links to Hazara Division specific content")
        
        return recommendations
    
    def _generate_neo4j_import_data(self) -> Dict[str, Any]:
        """Generate Neo4j import data."""
        relationships = self.link_manager.generate_neo4j_relationships()
        
        # Generate Cypher queries
        cypher_queries = self._generate_cypher_queries(relationships)
        
        # Generate CSV files for bulk import
        csv_data = self._generate_csv_data(relationships)
        
        return {
            "relationships_count": len(relationships),
            "cypher_queries_count": len(cypher_queries),
            "sample_cypher_query": cypher_queries[0] if cypher_queries else "",
            "csv_files": list(csv_data.keys()),
            "timestamp": datetime.now().isoformat()
        }
    
    def _generate_cypher_queries(self, relationships: List[Dict[str, Any]]) -> List[str]:
        """Generate Cypher queries for Neo4j import."""
        queries = []
        
        # Header
        queries.append("-- Hybrid Linker: FAISS to Neo4j Relationships")
        queries.append(f"-- Generated: {datetime.now().isoformat()}")
        queries.append(f"-- Total relationships: {len(relationships)}")
        queries.append("")
        
        # Create relationships
        for rel in relationships:
            query = f"""
            MATCH (chunk:DocumentChunk {{faiss_index_id: {rel['start_node_id'].split('_')[-1]}}})
            MATCH (node {{node_id: '{rel['end_node_id']}'}})
            MERGE (chunk)-[r:{rel['type']}]->(node)
            SET r += {json.dumps(rel['properties'], ensure_ascii=False)}
            RETURN r.link_id
            """
            queries.append(query)
        
        # Create indexes
        queries.append("")
        queries.append("-- Create indexes for performance")
        queries.append("CREATE INDEX IF NOT EXISTS FOR (c:DocumentChunk) ON (c.faiss_index_id);")
        queries.append("CREATE INDEX IF NOT EXISTS FOR ()-[r]-() ON (r.link_id);")
        
        return queries
    
    def _generate_csv_data(self, relationships: List[Dict[str, Any]]) -> Dict[str, str]:
        """Generate CSV data for bulk import."""
        # This would generate actual CSV strings
        # For now, return placeholder
        return {
            "relationships.csv": f"Total relationships: {len(relationships)}",
            "metadata.csv": "Link metadata for relationships"
        }
    
    def hybrid_retrieval(self, query: str, query_embedding: np.ndarray,
                        neo4j_context: Optional[Dict[str, Any]] = None,
                        k: int = 10,
                        use_kpk_boost: bool = True) -> Dict[str, Any]:
        """
        Perform hybrid retrieval combining FAISS and graph.
        
        Args:
            query: Original query text
            query_embedding: Query embedding
            neo4j_context: Neo4j context
            k: Number of results
            use_kpk_boost: Whether to boost KPK results
            
        Returns:
            Hybrid retrieval results
        """
        # This would use the actual FAISS indexer to get initial results
        # For now, we'll simulate
        
        # Simulate FAISS results
        simulated_results = self._simulate_faiss_results(query_embedding)
        
        # Perform hybrid search
        hybrid_results = self.link_manager.hybrid_search(
            query_embedding, simulated_results, neo4j_context, k
        )
        
        # Apply KPK boosting if requested
        if use_kpk_boost:
            hybrid_results = self._apply_kpk_boosting(hybrid_results, query)
        
        # Prepare response
        return {
            "query": query,
            "total_results": len(hybrid_results),
            "results": [
                {
                    "entity_id": result.entity_id,
                    "entity_type": result.entity_type,
                    "hybrid_score": result.hybrid_score,
                    "explanation": result.explanation,
                    "source": result.source,
                    "is_kpk": self._is_kpk_node(result.entity_id)
                }
                for result in hybrid_results[:k]
            ],
            "kpk_analysis": {
                "kpk_results": sum(1 for result in hybrid_results[:k] 
                                 if self._is_kpk_node(result.entity_id)),
                "total_results": min(k, len(hybrid_results))
            },
            "retrieval_timestamp": datetime.now().isoformat()
        }
    
    def _simulate_faiss_results(self, query_embedding: np.ndarray) -> List[Any]:
        """Simulate FAISS search results for testing."""
        # In production, this would call the actual FAISS indexer
        return []
    
    def _apply_kpk_boosting(self, results: List[HybridSearchResult], query: str) -> List[HybridSearchResult]:
        """Apply KPK-specific boosting to results."""
        query_lower = query.lower()
        
        # Check if query is KPK-related
        is_kpk_query = any(keyword in query_lower 
                          for keyword in ["kpk", "khyber", "hazara", "deodar", "kail", "swat"])
        
        if not is_kpk_query:
            return results
        
        # Boost KPK results
        for result in results:
            if self._is_kpk_node(result.entity_id):
                result.hybrid_score *= 1.3  # 30% boost for KPK
                result.explanation += " (KPK-boosted)"
        
        # Re-sort by boosted score
        results.sort(key=lambda x: x.hybrid_score, reverse=True)
        
        return results
    
    def save_hybrid_system(self, output_dir: Union[str, Path]) -> Dict[str, Path]:
        """
        Save complete hybrid linking system.
        
        Args:
            output_dir: Directory to save files
            
        Returns:
            Dict of saved file paths
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save links
        link_files = self.link_manager.save_links(output_dir)
        
        # Save KPK-specific metadata
        kpk_metadata_path = output_dir / "kpk_hybrid_metadata.json"
        kpk_metadata = {
            "entity_priority": self.kpk_entity_priority,
            "strategies": {name: strategy.__dict__ 
                          for name, strategy in self.strategies.items()},
            "save_timestamp": datetime.now().isoformat()
        }
        
        with open(kpk_metadata_path, 'w', encoding='utf-8') as f:
            json.dump(kpk_metadata, f, indent=2, ensure_ascii=False)
        
        link_files["kpk_metadata"] = kpk_metadata_path
        
        # Generate comprehensive report
        report_path = output_dir / "hybrid_linking_report.json"
        report = self._generate_comprehensive_report()
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        link_files["report"] = report_path
        
        logger.info(f"Saved hybrid linking system to {output_dir}")
        return link_files
    
    def _generate_comprehensive_report(self) -> Dict[str, Any]:
        """Generate comprehensive hybrid linking report."""
        stats = self.link_manager._generate_linking_statistics()
        kpk_analysis = self._analyze_kpk_coverage()
        
        return {
            "summary": {
                "total_links": stats["total_links"],
                "node_coverage": stats["node_coverage"]["coverage_percentage"],
                "average_confidence": stats["confidence_metrics"]["average_confidence"],
                "kpk_coverage": kpk_analysis["kpk_link_coverage"]
            },
            "detailed_statistics": stats,
            "kpk_analysis": kpk_analysis,
            "system_health": self._check_system_health(),
            "recommendations": kpk_analysis.get("recommendations", []) + 
                             self._generate_system_recommendations(stats),
            "generated_at": datetime.now().isoformat()
        }
    
    def _check_system_health(self) -> Dict[str, Any]:
        """Check health of hybrid linking system."""
        links = self.link_manager.links
        
        # Check for orphaned links
        orphaned_links = 0
        for link in links.values():
            if not self.link_manager.faiss_to_links.get(link.faiss_index_id):
                orphaned_links += 1
        
        # Check for isolated nodes
        isolated_nodes = sum(1 for node_id, link_ids in self.link_manager.node_to_links.items() 
                           if not link_ids)
        
        return {
            "total_links": len(links),
            "orphaned_links": orphaned_links,
            "isolated_nodes": isolated_nodes,
            "link_integrity": (len(links) - orphaned_links) / len(links) if links else 1.0,
            "node_connectivity": 1.0 - (isolated_nodes / len(self.link_manager.node_to_links)) 
                               if self.link_manager.node_to_links else 1.0
        }
    
    def _generate_system_recommendations(self, stats: Dict[str, Any]) -> List[str]:
        """Generate system improvement recommendations."""
        recommendations = []
        
        # Check link confidence
        avg_confidence = stats["confidence_metrics"]["average_confidence"]
        if avg_confidence < 0.6:
            recommendations.append("Improve linking confidence by refining matching algorithms")
        
        # Check node coverage
        coverage = stats["node_coverage"]["coverage_percentage"]
        if coverage < 70:
            recommendations.append(f"Increase node coverage (currently {coverage:.1f}%)")
        
        # Check link density
        density = stats["node_coverage"]["average_links_per_node"]
        if density < 2.0:
            recommendations.append("Create more links per node for better connectivity")
        
        return recommendations

# Utility functions
def create_kpk_hybrid_linker(faiss_indexer_path: Optional[Path] = None) -> KPKHybridLinker:
    """Factory function to create KPK hybrid linker."""
    return KPKHybridLinker(faiss_indexer_path)


def create_hybrid_graph(faiss_chunks: List[IndexedChunk],
                       neo4j_nodes: List[Dict[str, Any]],
                       output_dir: Union[str, Path],
                       strategy: str = "comprehensive") -> Dict[str, Any]:
    """
    Complete hybrid graph creation pipeline.
    
    Args:
        faiss_chunks: FAISS indexed chunks
        neo4j_nodes: Neo4j nodes
        output_dir: Directory to save results
        strategy: Linking strategy
        
    Returns:
        Complete results
    """
    # Create linker
    linker = create_kpk_hybrid_linker()
    
    # Create hybrid graph
    results = linker.create_hybrid_graph(faiss_chunks, neo4j_nodes, strategy)
    
    # Save system
    file_paths = linker.save_hybrid_system(output_dir)
    results["saved_files"] = {k: str(v) for k, v in file_paths.items()}
    
    return results


# Example usage and testing
if __name__ == "__main__":
    print("=== Testing KPKHybridLinker ===\n")
    
    # Create sample data
    sample_chunks = [
        IndexedChunk(
            chunk_id="chunk_1",
            faiss_index_id=0,
            neo4j_node_id="LAW_KPK_FOREST_ORDINANCE_2002",
            text="Section 27: Penalty for unauthorized felling of Deodar trees.",
            metadata={
                "entities_mentioned": ["species:deodar", "law:kpk_forest_ordinance"],
                "document_type": "law",
                "confidence": 0.95
            },
            embedding_hash="abc123"
        ),
        IndexedChunk(
            chunk_id="chunk_2",
            faiss_index_id=1,
            neo4j_node_id="SPECIES_DEODAR",
            text="Deodar (Cedrus deodara) is a protected species in KPK forests.",
            metadata={
                "entities_mentioned": ["species:deodar", "location:kpk"],
                "document_type": "species_info",
                "confidence": 0.92
            },
            embedding_hash="def456"
        )
    ]
    
    sample_nodes = [
        {
            "node_id": "LAW_KPK_FOREST_ORDINANCE_2002",
            "labels": ["Law", "KPK_Specific"],
            "properties": {
                "title": "KPK Forest Ordinance, 2002",
                "year": 2002,
                "jurisdiction": "KPK"
            }
        },
        {
            "node_id": "SPECIES_DEODAR",
            "labels": ["Species", "Protected"],
            "properties": {
                "common_name": "Deodar",
                "scientific_name": "Cedrus deodara",
                "legal_status": "protected"
            }
        },
        {
            "node_id": "LOCATION_SWAT",
            "labels": ["Location", "Division"],
            "properties": {
                "name": "Swat Division",
                "type": "forest_division",
                "jurisdiction": "KPK"
            }
        }
    ]
    
    print("Sample data created:")
    print(f"  FAISS chunks: {len(sample_chunks)}")
    print(f"  Neo4j nodes: {len(sample_nodes)}")
    
    print("\n" + "=" * 60)
    
    # Create hybrid graph
    print("\nCreating hybrid graph...")
    linker = create_kpk_hybrid_linker()
    
    results = linker.create_hybrid_graph(sample_chunks, sample_nodes, "kpk_focused")
    
    print("\nLinking Results:")
    print("-" * 40)
    stats = results.get("linking_statistics", {})
    print(f"Total links created: {stats.get('total_links', 0)}")
    print(f"Node coverage: {stats.get('node_coverage', {}).get('coverage_percentage', 0):.1f}%")
    print(f"Average confidence: {stats.get('confidence_metrics', {}).get('average_confidence', 0):.3f}")
    
    kpk_analysis = results.get("kpk_analysis", {})
    print(f"KPK link coverage: {kpk_analysis.get('kpk_link_coverage', 0):.1f}%")
    
    print("\n" + "=" * 60)
    
    # Test hybrid retrieval
    print("\nTesting hybrid retrieval...")
    
    # Simulate query
    query = "What are the penalties for cutting Deodar trees in KPK?"
    query_embedding = np.random.randn(384).astype(np.float32)  # Simulated embedding
    
    retrieval_results = linker.hybrid_retrieval(
        query=query,
        query_embedding=query_embedding,
        neo4j_context={"jurisdiction": "KPK", "entity_types": ["species", "law"]},
        k=5,
        use_kpk_boost=True
    )
    
    print(f"\nQuery: {query}")
    print(f"Total results: {retrieval_results.get('total_results', 0)}")
    
    kpk_results = retrieval_results.get("kpk_analysis", {}).get("kpk_results", 0)
    total_results = retrieval_results.get("kpk_analysis", {}).get("total_results", 0)
    print(f"KPK results: {kpk_results}/{total_results}")
    
    print("\nTop results:")
    for i, result in enumerate(retrieval_results.get("results", [])[:3], 1):
        print(f"\nResult {i}:")
        print(f"  Entity: {result['entity_id']}")
        print(f"  Type: {result['entity_type']}")
        print(f"  Score: {result['hybrid_score']:.3f}")
        print(f"  Source: {result['source']}")
        print(f"  KPK: {'Yes' if result['is_kpk'] else 'No'}")
    
    print("\n" + "=" * 60)
    
    # Save system
    print("\nSaving hybrid linking system...")
    output_dir = Path("kpk_hybrid_linking")
    file_paths = linker.save_hybrid_system(output_dir)
    
    print(f"\nSaved files:")
    for file_type, file_path in file_paths.items():
        print(f"  {file_type}: {file_path}")
    
    print("\n" + "=" * 60)
    
    # Generate Neo4j import data
    print("\nGenerating Neo4j import data...")
    neo4j_import = results.get("neo4j_import", {})
    print(f"Relationships to import: {neo4j_import.get('relationships_count', 0)}")
    print(f"Cypher queries generated: {neo4j_import.get('cypher_queries_count', 0)}")
    
    print("\n" + "=" * 60)
    print("KPKHybridLinker Test Complete ✓")
