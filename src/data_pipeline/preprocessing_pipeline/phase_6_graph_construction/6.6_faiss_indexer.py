"""
FAISS_INDEXER.PY - Phase 6
Indexes dense vectors for fast retrieval.
Supports saving/loading indices.
"""
import logging
import os
import json
import numpy as np
import pickle
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import warnings
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
from typing import Dict, List, Any, Optional, Union, Tuple, Set
from pathlib import Path
import faiss

# Suppress FAISS warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class FAISSConfig:
    """Configuration for FAISS indexing."""
    index_type: str = "FLAT"  # FLAT for incremental batches; IVF needs large train sets
    metric: str = "IP"  # IP (inner product) or L2
    nlist: int = 100  # Number of clusters for IVF
    nprobe: int = 10  # Number of clusters to search
    m: int = 16  # Number of connections for HNSW
    ef_construction: int = 200  # Construction time/accuracy tradeoff for HNSW
    ef_search: int = 64  # Search time/accuracy tradeoff for HNSW
    train_size: int = 10000  # Minimum training samples
    gpu_enabled: bool = False
    normalize_vectors: bool = True
    chunk_size: int = 1000  # Batch size for indexing
    
    def validate(self) -> bool:
        """Validate configuration parameters."""
        valid_types = ["IVF_FLAT", "HNSW_FLAT", "FLAT", "IVFPQ"]
        if self.index_type not in valid_types:
            logger.error(f"Invalid index_type: {self.index_type}. Must be one of {valid_types}")
            return False
        
        if self.metric not in ["IP", "L2"]:
            logger.error(f"Invalid metric: {self.metric}. Must be 'IP' or 'L2'")
            return False
        
        if self.nlist <= 0:
            logger.error(f"Invalid nlist: {self.nlist}. Must be positive")
            return False
        
        if self.nprobe <= 0 or self.nprobe > self.nlist:
            logger.error(f"Invalid nprobe: {self.nprobe}. Must be between 1 and nlist ({self.nlist})")
            return False
        
        return True

@dataclass
class IndexedChunk:
    """Metadata for an indexed chunk."""
    chunk_id: str
    faiss_index_id: int
    neo4j_node_id: str
    text: str
    metadata: Dict[str, Any]
    embedding_hash: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class SearchResult:
    """Result from FAISS search."""
    chunk_id: str
    neo4j_node_id: str
    similarity_score: float
    text: str
    metadata: Dict[str, Any]
    rank: int

@dataclass
class KPKIndexMetadata:
    """KPK-specific index metadata."""
    jurisdiction: str = "KPK"
    document_types: List[str] = field(default_factory=lambda: ["law", "section", "circular", "working_plan"])
    entity_types: List[str] = field(default_factory=lambda: ["species", "location", "officer", "penalty"])
    languages: List[str] = field(default_factory=lambda: ["en", "ur", "ps"])
    has_abstention_chunks: bool = False
    kpk_coverage_score: float = 0.0

class FAISSIndexManager:
    """Manages FAISS indices with KPK specialization."""
    
    def __init__(self, config: Optional[FAISSConfig] = None):
        self.config = config or FAISSConfig()
        if not self.config.validate():
            raise ValueError("Invalid FAISS configuration")
        
        self.index = None
        self.index_metadata = {}
        self.chunk_registry: Dict[int, IndexedChunk] = {}  # faiss_id -> IndexedChunk
        self.neo4j_mapping: Dict[str, List[int]] = {}  # neo4j_node_id -> List[faiss_ids]
        self.lock = threading.Lock()
        
        # KPK-specific tracking
        self.kpk_metadata = KPKIndexMetadata()
        self.specialized_indices = {}  # For entity-specific indices
        
        logger.info(f"FAISSIndexManager initialized with config: {self.config.index_type}")
        
        # PROD-HARDENING: Auto-load existing index if available to prevent chunk_registry drop-off
        default_path = Path("E:/GL_AI/data_processed/faiss_index_new")
        if default_path.exists() and (default_path / "faiss_index.bin").exists():
            try:
                self.load_index(default_path)
                logger.info(f"Auto-loaded existing FAISS index from {default_path} ({len(self.chunk_registry)} chunks)")
            except Exception as e:
                logger.warning(f"Could not auto-load existing FAISS index: {e}")
    
    def create_index(self, dimension_or_embeddings: Any) -> Any:
        """
        Create FAISS index. Support both dimension (int) and embeddings (np.ndarray/EmbeddingBatch).
        Compatibility method for run_sequential_pipeline.py.
        """
        if isinstance(dimension_or_embeddings, int):
            return self._create_index_by_dimension(dimension_or_embeddings)
        
        # Handle embeddings input
        embeddings = dimension_or_embeddings
        if hasattr(embeddings, 'embeddings'):
            # It's an EmbeddingBatch
            batch = embeddings
            vecs = np.array([e.embedding for e in batch.embeddings])
            if vecs.size == 0 or len(vecs.shape) < 2:
                # Log warning and return
                # logger might not be in scope here if imported as item, but let's assume it is or just use a safe check
                return self
            dim = vecs.shape[1]
            self._create_index_by_dimension(dim)
            self.index_chunks([{"chunk_id": e.chunk_id, "metadata": e.metadata} for e in batch.embeddings], vecs)
            return self
        
        return self

    def _create_index_by_dimension(self, dimension: int) -> None:
        """
        Internal method to create FAISS index with specified dimension.
        """
        with self.lock:
            if self.index is not None:
                logger.warning("Index already exists. Recreating...")
                self.chunk_registry.clear()
                self.neo4j_mapping.clear()
            
            index_type = self.config.index_type
            metric = faiss.METRIC_INNER_PRODUCT if self.config.metric == "IP" else faiss.METRIC_L2
            
            if index_type == "FLAT":
                self.index = faiss.IndexFlat(dimension, metric)
                logger.info(f"Created Flat index with dimension {dimension}")
                
            elif index_type == "IVF_FLAT":
                quantizer = faiss.IndexFlat(dimension, metric)
                self.index = faiss.IndexIVFFlat(quantizer, dimension, self.config.nlist, metric)
                logger.info(f"Created IVF_FLAT index with {self.config.nlist} clusters")
                
            elif index_type == "HNSW_FLAT":
                self.index = faiss.IndexHNSWFlat(dimension, self.config.m, metric)
                self.index.hnsw.efConstruction = self.config.ef_construction
                self.index.hnsw.efSearch = self.config.ef_search
                logger.info(f"Created HNSW_FLAT index with M={self.config.m}")
                
            elif index_type == "IVFPQ":
                # Product Quantization for memory efficiency
                quantizer = faiss.IndexFlat(dimension, metric)
                m = 8  # Number of sub-vectors
                nbits = 8  # Bits per sub-vector
                self.index = faiss.IndexIVFPQ(quantizer, dimension, self.config.nlist, m, nbits, metric)
                logger.info(f"Created IVFPQ index with {self.config.nlist} clusters")
            
            else:
                raise ValueError(f"Unsupported index type: {index_type}")
            
            # Store metadata
            self.index_metadata = {
                "dimension": dimension,
                "index_type": index_type,
                "metric": self.config.metric,
                "created_at": datetime.now().isoformat(),
                "total_vectors": 0,
                "is_trained": False
            }
            
            logger.info(f"Index created: {self.index_metadata}")
    
    def train_index(self, training_vectors: np.ndarray) -> None:
        """
        Train the index with sample vectors.
        
        Args:
            training_vectors: Numpy array of training vectors
        """
        with self.lock:
            if self.index is None:
                raise ValueError("Index not created. Call create_index() first.")
            
            if len(training_vectors) < self.config.train_size:
                logger.warning(f"Training with {len(training_vectors)} vectors, recommended {self.config.train_size}")
            
            # Normalize if needed
            if self.config.normalize_vectors and self.config.metric == "IP":
                faiss.normalize_L2(training_vectors)
            
            # Check if index needs training
            if hasattr(self.index, 'is_trained') and not self.index.is_trained:
                logger.info(f"Training index with {len(training_vectors)} vectors...")
                self.index.train(training_vectors)
                self.index_metadata["is_trained"] = True
                logger.info("Index training completed")
            else:
                logger.info("Index does not require training or is already trained")
    
    def add_vectors(self, embeddings: np.ndarray, chunks: List[Dict[str, Any]], start_id: int = None, stats: Dict[str, Any] = None) -> Any:
        """
        Unified vector addition method.
        Supports both GraphBuilder (2 args) and internal batch indexing (4 args).
        """
        if start_id is not None and stats is not None:
            # Internal batch indexing logic
            if len(embeddings) == 0:
                return
            
            # Auto-train if needed for IVF indices
            if hasattr(self.index, 'is_trained') and not self.index.is_trained:
                if len(embeddings) >= self.config.nlist:
                    logger.info(f"Auto-training IVF index with {len(embeddings)} vectors...")
                    self.index.train(embeddings)
                    self.index_metadata["is_trained"] = True
                else:
                    logger.warning(f"Cannot train IVF index: batch size {len(embeddings)} < nlist {self.config.nlist}")
            
            # Add to FAISS index
            self.index.add(embeddings)
            
            # Register each chunk in the registry
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                faiss_id = start_id + i
                self._register_chunk(chunk, faiss_id, embedding)
                
                stats["successful"] += 1
                if self._is_kpk_chunk(chunk):
                    stats["kpk_chunks"] += 1
            return None
        else:
            # Public alias for compatibility with GraphBuilder
            return self.index_chunks(chunks, embeddings)

    def index_chunks(self, chunks: List[Dict[str, Any]], embeddings: np.ndarray) -> Dict[str, Any]:
        """
        Index chunks with their embeddings.
        
        Args:
            chunks: List of chunk dictionaries from legal_chunker
            embeddings: Numpy array of chunk embeddings
            
        Returns:
            Indexing statistics
        """
        if len(chunks) != len(embeddings):
            raise ValueError(f"Chunks ({len(chunks)}) and embeddings ({len(embeddings)}) count mismatch")
        
        if self.index is None:
            raise ValueError("Index not created. Call create_index() first.")
        
        # Prepare embeddings
        if self.config.normalize_vectors and self.config.metric == "IP":
            faiss.normalize_L2(embeddings)
        
        # Batch indexing
        batch_size = self.config.chunk_size
        total_chunks = len(chunks)
        stats = {
            "total_chunks": total_chunks,
            "successful": 0,
            "failed": 0,
            "kpk_chunks": 0,
            "abstention_chunks": 0,
            "start_time": datetime.now().isoformat()
        }
        
        logger.info(f"Indexing {total_chunks} chunks in batches of {batch_size}...")
        
        for i in range(0, total_chunks, batch_size):
            batch_end = min(i + batch_size, total_chunks)
            batch_chunks = chunks[i:batch_end]
            batch_embeddings = embeddings[i:batch_end]
            
            # Get current index size for ID assignment
            current_size = self.index.ntotal if hasattr(self.index, 'ntotal') else 0
            
            try:
                # Ensure the slice is contiguous for FAISS
                contiguous_embeddings = np.ascontiguousarray(batch_embeddings)
                self.add_vectors(contiguous_embeddings, batch_chunks, current_size, stats)
                logger.info(f"Indexed batch {i//batch_size + 1}: {len(batch_chunks)} chunks")
            except Exception as e:
                stats["failed"] += len(batch_chunks)
                logger.error(f"Failed to index batch {i//batch_size + 1}: {e}")
        
        # PERSISTENCE FIX: Save to disk after indexing
        try:
            self.save()
            logger.info("FAISS index saved successfully after chunking.")
        except Exception as e:
            logger.error(f"Failed to auto-save FAISS index: {e}")
        
        # Update metadata
        with self.lock:
            self.index_metadata["total_vectors"] = stats["successful"]
            self.index_metadata["last_indexed"] = datetime.now().isoformat()
            
            # Update KPK metadata
            self._update_kpk_metadata(chunks)
        
        stats["end_time"] = datetime.now().isoformat()
        stats["index_size"] = self.index_metadata["total_vectors"]
        stats["kpk_coverage"] = stats["kpk_chunks"] / stats["successful"] if stats["successful"] > 0 else 0
        
        logger.info(f"Indexing complete: {stats['successful']} successful, {stats['failed']} failed")
        return stats
    
    def _register_chunk(self, chunk: Dict[str, Any], faiss_id: int, embedding: np.ndarray) -> None:
        """Register a chunk in the registry."""
        print(f"DEBUG: Registering chunk {faiss_id}")
        chunk_id = chunk.get("chunk_id", f"chunk_{faiss_id}")
        neo4j_node_id = chunk.get("metadata", {}).get("neo4j_node_id")
        
        if not neo4j_node_id:
            # Generate from chunk_id or metadata
            neo4j_node_id = self._generate_neo4j_node_id(chunk)
        
        # Create embedding hash for deduplication
        embedding_hash = hashlib.md5(embedding.tobytes()).hexdigest()[:16]
        
        indexed_chunk = IndexedChunk(
            chunk_id=chunk_id,
            faiss_index_id=faiss_id,
            neo4j_node_id=neo4j_node_id,
            text=chunk.get("chunk_text", chunk.get("text", ""))[:500],
            metadata=chunk.get("metadata", {}).copy(),
            embedding_hash=embedding_hash
        )
        
        # Store in registry
        self.chunk_registry[faiss_id] = indexed_chunk
        
        # Update Neo4j mapping
        if neo4j_node_id not in self.neo4j_mapping:
            self.neo4j_mapping[neo4j_node_id] = []
        self.neo4j_mapping[neo4j_node_id].append(faiss_id)
    
    def _generate_neo4j_node_id(self, chunk: Dict[str, Any]) -> str:
        """Generate Neo4j node ID from chunk metadata."""
        metadata = chunk.get("metadata", {})
        
        # Try to extract from existing metadata
        if "neo4j_node_id" in metadata:
            return metadata["neo4j_node_id"]
        
        # Generate based on chunk type
        chunk_type = metadata.get("chunk_type", "document_chunk")
        
        if chunk_type == "law_section":
            law_id = metadata.get("law_id", "unknown_law")
            section = metadata.get("section_number", "unknown")
            return f"chunk_{law_id}_{section}"
        
        elif chunk_type == "species":
            species_name = metadata.get("species_name", "unknown")
            return f"chunk_species_{species_name}"
        
        elif chunk_type == "location":
            location_name = metadata.get("location_name", "unknown")
            return f"chunk_location_{location_name}"
        
        else:
            # Generic ID
            chunk_id = chunk.get("chunk_id", "unknown")
            return f"chunk_{chunk_id}"
    
    def _is_kpk_chunk(self, chunk: Dict[str, Any]) -> bool:
        """Check if chunk is KPK-specific."""
        metadata = chunk.get("metadata", {})
        
        # Check metadata flags
        if metadata.get("is_kpk_document", False):
            return True
        
        # Check content for KPK keywords
        text = chunk.get("text", "").lower()
        kpk_keywords = ["kpk", "khyber pakhtunkhwa", "hazara", "abbottabad", 
                       "swat", "deodar", "kail", "dfo", "range officer"]
        
        return any(keyword in text for keyword in kpk_keywords)
    
    def _update_kpk_metadata(self, chunks: List[Dict[str, Any]]) -> None:
        """Update KPK metadata based on indexed chunks."""
        kpk_chunks = sum(1 for chunk in chunks if self._is_kpk_chunk(chunk))
        total_chunks = len(chunks)
        
        self.kpk_metadata.kpk_coverage_score = kpk_chunks / total_chunks if total_chunks > 0 else 0
        self.kpk_metadata.has_abstention_chunks = any(
            chunk.get("metadata", {}).get("is_abstention", False) for chunk in chunks
        )
        
        # Extract unique entity types
        entity_types = set()
        for chunk in chunks:
            entities = chunk.get("entities_mentioned", [])
            for entity in entities:
                if ":" in entity:
                    entity_type = entity.split(":")[0]
                    entity_types.add(entity_type)
        
        self.kpk_metadata.entity_types = list(entity_types)
    
    def search(self, query_embedding: np.ndarray, k: int = 10, 
               filters: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        """
        Search for similar chunks.
        
        Args:
            query_embedding: Query embedding vector
            k: Number of results to return
            filters: Optional filters (entity_type, document_type, etc.)
            
        Returns:
            List of SearchResult objects
        """
        if self.index is None:
            raise ValueError("Index not created or empty")
        
        if self.index_metadata.get("total_vectors", 0) == 0:
            logger.warning("Index is empty")
            return []
        
        # Prepare query embedding
        query_vector = query_embedding.reshape(1, -1).astype(np.float32)
        
        if self.config.normalize_vectors and self.config.metric == "IP":
            faiss.normalize_L2(query_vector)
        
        # Configure search parameters
        if self.config.index_type == "IVF_FLAT" and hasattr(self.index, 'nprobe'):
            self.index.nprobe = self.config.nprobe
        
        if self.config.index_type == "HNSW_FLAT" and hasattr(self.index.hnsw, 'efSearch'):
            self.index.hnsw.efSearch = self.config.ef_search
        
        # Perform search
        try:
            distances, indices = self.index.search(query_vector, min(k * 2, self.index.ntotal))
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
        
        # Convert to results
        results = []
        seen_chunks = set()
        
        for i, (distance, idx) in enumerate(zip(distances[0], indices[0])):
            if idx == -1:  # No more results
                continue
            
            if idx not in self.chunk_registry:
                logger.warning(f"Index ID {idx} not found in registry")
                continue
            
            chunk = self.chunk_registry[idx]
            
            # Skip duplicates
            if chunk.chunk_id in seen_chunks:
                continue
            
            # Apply filters if specified
            if filters and not self._passes_filters(chunk, filters):
                continue
            
            # Convert distance to similarity score
            if self.config.metric == "IP":
                similarity = float(distance)  # Inner product is similarity
            else:  # L2 distance
                similarity = 1.0 / (1.0 + float(distance))  # Convert to similarity
            
            result = SearchResult(
                chunk_id=chunk.chunk_id,
                neo4j_node_id=chunk.neo4j_node_id,
                similarity_score=similarity,
                text=chunk.text,
                metadata=chunk.metadata,
                rank=len(results) + 1
            )
            
            results.append(result)
            seen_chunks.add(chunk.chunk_id)
            
            if len(results) >= k:
                break
        
        return results
    
    def _passes_filters(self, chunk: IndexedChunk, filters: Dict[str, Any]) -> bool:
        """Check if chunk passes all filters."""
        for key, value in filters.items():
            if key == "entity_type":
                # Check if chunk mentions specific entity type
                entities = chunk.metadata.get("entities_mentioned", [])
                entity_types = [e.split(":")[0] for e in entities if ":" in e]
                if value not in entity_types:
                    return False
            
            elif key == "document_type":
                doc_type = chunk.metadata.get("document_type", "")
                if doc_type != value:
                    return False
            
            elif key == "is_kpk":
                is_kpk = self._is_kpk_chunk({"text": chunk.text, "metadata": chunk.metadata})
                if is_kpk != value:
                    return False
            
            elif key == "confidence_threshold":
                confidence = chunk.metadata.get("confidence", 1.0)
                if confidence < value:
                    return False
            
            elif key == "exclude_abstention":
                is_abstention = chunk.metadata.get("is_abstention", False)
                if is_abstention and value:
                    return False
        
        return True
    
    def hybrid_search(self, query_embedding: np.ndarray, 
                      neo4j_context: Optional[Dict[str, Any]] = None,
                      k: int = 10) -> List[SearchResult]:
        """
        Hybrid search combining FAISS similarity and Neo4j graph context.
        
        Args:
            query_embedding: Query embedding
            neo4j_context: Optional Neo4j context (entity IDs, relationships)
            k: Number of results
            
        Returns:
            List of SearchResult with hybrid ranking
        """
        # First, get FAISS results
        faiss_results = self.search(query_embedding, k * 3)  # Get more for re-ranking
        
        if not neo4j_context:
            return faiss_results[:k]
        
        # Re-rank based on Neo4j context
        reranked = self._rerank_with_neo4j_context(faiss_results, neo4j_context)
        
        return reranked[:k]
    
    def _rerank_with_neo4j_context(self, results: List[SearchResult], 
                                   neo4j_context: Dict[str, Any]) -> List[SearchResult]:
        """Re-rank results based on Neo4j graph context."""
        if not results or not neo4j_context:
            return results
        
        # Extract context information
        entity_ids = neo4j_context.get("entity_ids", [])
        relationship_types = neo4j_context.get("relationship_types", [])
        jurisdiction = neo4j_context.get("jurisdiction", "")
        
        for result in results:
            context_score = 0.0
            
            # Check if result's Neo4j node is connected to context entities
            result_node_id = result.neo4j_node_id
            
            # Jurisdiction match
            if jurisdiction and jurisdiction.lower() == "kpk":
                if self._is_kpk_chunk({"text": result.text, "metadata": result.metadata}):
                    context_score += 0.3
            
            # Entity connection (simulated - would query Neo4j in production)
            # For now, check if metadata mentions similar entities
            result_entities = result.metadata.get("entities_mentioned", [])
            for entity in entity_ids:
                if any(entity in e for e in result_entities):
                    context_score += 0.2
            
            # Boost score with context
            result.similarity_score = result.similarity_score * 0.7 + context_score * 0.3
        
        # Sort by new score
        return sorted(results, key=lambda x: x.similarity_score, reverse=True)
    
    def get_chunks_by_neo4j_node(self, neo4j_node_id: str) -> List[IndexedChunk]:
        """Get all chunks associated with a Neo4j node."""
        faiss_ids = self.neo4j_mapping.get(neo4j_node_id, [])
        return [self.chunk_registry[faiss_id] for faiss_id in faiss_ids if faiss_id in self.chunk_registry]
    
    def get_index_statistics(self) -> Dict[str, Any]:
        """Get comprehensive index statistics."""
        if self.index is None:
            return {"status": "not_initialized"}
        
        total_vectors = self.index_metadata.get("total_vectors", 0)
        kpk_chunks = sum(1 for chunk in self.chunk_registry.values() 
                        if self._is_kpk_chunk({"text": chunk.text, "metadata": chunk.metadata}))
        
        abstention_chunks = sum(1 for chunk in self.chunk_registry.values()
                               if chunk.metadata.get("is_abstention", False))
        
        # Entity type distribution
        entity_distribution = {}
        for chunk in self.chunk_registry.values():
            entities = chunk.metadata.get("entities_mentioned", [])
            for entity in entities:
                if ":" in entity:
                    entity_type = entity.split(":")[0]
                    entity_distribution[entity_type] = entity_distribution.get(entity_type, 0) + 1
        
        return {
            "index_metadata": self.index_metadata,
            "kpk_metadata": self.kpk_metadata.__dict__,
            "chunk_statistics": {
                "total_chunks": total_vectors,
                "kpk_chunks": kpk_chunks,
                "kpk_coverage": kpk_chunks / total_vectors if total_vectors > 0 else 0,
                "abstention_chunks": abstention_chunks,
                "unique_neo4j_nodes": len(self.neo4j_mapping),
                "average_chunks_per_node": total_vectors / len(self.neo4j_mapping) if self.neo4j_mapping else 0
            },
            "entity_distribution": entity_distribution,
            "performance_metrics": {
                "index_type": self.config.index_type,
                "dimension": self.index_metadata.get("dimension", 0),
                "is_trained": self.index_metadata.get("is_trained", False)
            }
        }
    
    def save_index(self, output_dir: Union[str, Path]) -> Dict[str, Path]:
        """
        Save FAISS index and metadata to disk.
        
        Args:
            output_dir: Directory to save files
            
        Returns:
            Dict of saved file paths
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        file_paths = {}
        
        # Save FAISS index
        index_path = output_dir / "faiss_index.bin"
        if self.index is not None:
            faiss.write_index(self.index, str(index_path))
            file_paths["index"] = index_path
        
        # Save metadata
        metadata_path = output_dir / "index_metadata.json"
        metadata = {
            "index_metadata": self.index_metadata,
            "kpk_metadata": self.kpk_metadata.__dict__,
            "config": self.config.__dict__,
            "save_timestamp": datetime.now().isoformat(),
            "total_chunks": len(self.chunk_registry)
        }
        
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        file_paths["metadata"] = metadata_path
        
        # Save chunk registry
        registry_path = output_dir / "chunk_registry.pkl"
        
        # Convert IndexedChunk objects to dicts to avoid pickling errors with dynamically loaded modules
        import dataclasses
        registry_dicts = {k: dataclasses.asdict(v) if hasattr(v, '__dataclass_fields__') else v 
                          for k, v in self.chunk_registry.items()}
        
        with open(registry_path, 'wb') as f:
            pickle.dump({
                "chunk_registry": registry_dicts,
                "neo4j_mapping": self.neo4j_mapping
            }, f)
        file_paths["registry"] = registry_path
        
        # Save Neo4j linking information for hybrid retrieval
        linking_path = output_dir / "neo4j_linking.json"
        linking_info = self._generate_linking_info()
        with open(linking_path, 'w', encoding='utf-8') as f:
            json.dump(linking_info, f, indent=2, ensure_ascii=False)
        file_paths["linking"] = linking_path
        
        logger.info(f"Index saved to {output_dir}")
        return file_paths

    def save(self, output_dir: Union[str, Path] = None) -> Dict[str, Path]:
        """Persist index (alias used by per-document batch indexing)."""
        target = Path(output_dir) if output_dir else Path("E:/GL_AI/data_processed/faiss_index_new")
        return self.save_index(target)
    
    def _generate_linking_info(self) -> Dict[str, Any]:
        """Generate information for Neo4j linking."""
        linking_info = {
            "neo4j_nodes": [],
            "chunk_mapping": [],
            "entity_occurrences": {},
            "timestamp": datetime.now().isoformat()
        }
        
        # Collect Neo4j node information
        for neo4j_id, faiss_ids in self.neo4j_mapping.items():
            linking_info["neo4j_nodes"].append({
                "node_id": neo4j_id,
                "chunk_count": len(faiss_ids),
                "chunk_ids": [self.chunk_registry[faiss_id].chunk_id for faiss_id in faiss_ids]
            })
        
        # Collect chunk to Neo4j mapping
        for faiss_id, chunk in self.chunk_registry.items():
            linking_info["chunk_mapping"].append({
                "chunk_id": chunk.chunk_id,
                "faiss_id": faiss_id,
                "neo4j_node_id": chunk.neo4j_node_id,
                "embedding_hash": chunk.embedding_hash
            })
        
        # Count entity occurrences
        for chunk in self.chunk_registry.values():
            entities = chunk.metadata.get("entities_mentioned", [])
            for entity in entities:
                if entity not in linking_info["entity_occurrences"]:
                    linking_info["entity_occurrences"][entity] = 0
                linking_info["entity_occurrences"][entity] += 1
        
        return linking_info
    
    def load_index(self, input_dir: Union[str, Path]) -> bool:
        """
        Load FAISS index and metadata from disk.
        
        Args:
            input_dir: Directory containing saved files
            
        Returns:
            True if successful, False otherwise
        """
        input_dir = Path(input_dir)
        
        try:
            # Load FAISS index
            index_path = input_dir / "faiss_index.bin"
            if index_path.exists():
                self.index = faiss.read_index(str(index_path))
                logger.info(f"Loaded FAISS index from {index_path}")
            else:
                logger.error(f"Index file not found: {index_path}")
                return False
            
            # Load metadata
            metadata_path = input_dir / "index_metadata.json"
            if metadata_path.exists():
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                self.index_metadata = metadata.get("index_metadata", {})
                
                # Restore KPK metadata
                kpk_metadata = metadata.get("kpk_metadata", {})
                for key, value in kpk_metadata.items():
                    if hasattr(self.kpk_metadata, key):
                        setattr(self.kpk_metadata, key, value)
                
                logger.info(f"Loaded metadata from {metadata_path}")
            else:
                logger.warning(f"Metadata file not found: {metadata_path}")
            
            # Load chunk registry
            registry_path = input_dir / "chunk_registry.pkl"
            if registry_path.exists():
                with open(registry_path, 'rb') as f:
                    registry_data = pickle.load(f)
                
                registry_dicts = registry_data.get("chunk_registry", {})
                self.neo4j_mapping = registry_data.get("neo4j_mapping", {})
                
                # Reconstruct IndexedChunk objects
                self.chunk_registry = {}
                for k, v in registry_dicts.items():
                    if isinstance(v, dict):
                        self.chunk_registry[k] = IndexedChunk(**v)
                    else:
                        self.chunk_registry[k] = v
                        
                logger.info(f"Loaded chunk registry with {len(self.chunk_registry)} chunks")
            else:
                logger.warning(f"Registry file not found: {registry_path}")
            
            logger.info(f"Successfully loaded index from {input_dir}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load index: {e}")
            return False
    
    def create_specialized_index(self, entity_type: str, 
                                chunks: List[Dict[str, Any]], 
                                embeddings: np.ndarray) -> bool:
        """
        Create a specialized index for specific entity type.
        
        Args:
            entity_type: Type of entity (species, location, officer, etc.)
            chunks: Chunks related to this entity type
            embeddings: Corresponding embeddings
            
        Returns:
            True if successful
        """
        if not chunks or not embeddings:
            logger.warning(f"No data provided for {entity_type} index")
            return False
        
        # Filter chunks for entity type
        filtered_chunks = []
        filtered_embeddings = []
        
        for chunk, embedding in zip(chunks, embeddings):
            entities = chunk.get("entities_mentioned", [])
            if any(entity.startswith(f"{entity_type}:") for entity in entities):
                filtered_chunks.append(chunk)
                filtered_embeddings.append(embedding)
        
        if not filtered_chunks:
            logger.warning(f"No {entity_type} chunks found")
            return False
        
        # Create specialized index
        dimension = embeddings.shape[1]
        specialized_config = FAISSConfig(
            index_type="HNSW_FLAT",  # Use HNSW for specialized indices
            metric=self.config.metric,
            m=8,
            ef_construction=100,
            ef_search=32
        )
        
        try:
            specialized_index = FAISSIndexManager(specialized_config)
            specialized_index.create_index(dimension)
            
            # Train if needed
            if len(filtered_embeddings) >= 1000:
                training_vectors = np.array(filtered_embeddings[:1000])
                specialized_index.train_index(training_vectors)
            
            # Index chunks
            stats = specialized_index.index_chunks(filtered_chunks, np.array(filtered_embeddings))
            
            # Store specialized index
            self.specialized_indices[entity_type] = specialized_index
            
            logger.info(f"Created specialized {entity_type} index with {stats['successful']} chunks")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create specialized index for {entity_type}: {e}")
            return False
    
    def search_specialized(self, query_embedding: np.ndarray, 
                          entity_type: str, k: int = 5) -> List[SearchResult]:
        """
        Search in specialized index.
        
        Args:
            query_embedding: Query embedding
            entity_type: Type of entity to search for
            k: Number of results
            
        Returns:
            Search results from specialized index
        """
        if entity_type not in self.specialized_indices:
            logger.warning(f"No specialized index for {entity_type}")
            return []
        
        specialized_index = self.specialized_indices[entity_type]
        return specialized_index.search(query_embedding, k)
    
    def get_kpk_coverage_report(self) -> Dict[str, Any]:
        """Generate KPK coverage report."""
        total_chunks = len(self.chunk_registry)
        kpk_chunks = sum(1 for chunk in self.chunk_registry.values() 
                        if self._is_kpk_chunk({"text": chunk.text, "metadata": chunk.metadata}))
        
        # Analyze KPK entity coverage
        kpk_entities = {
            "species": set(),
            "location": set(),
            "officer": set(),
            "law": set()
        }
        
        for chunk in self.chunk_registry.values():
            if self._is_kpk_chunk({"text": chunk.text, "metadata": chunk.metadata}):
                entities = chunk.metadata.get("entities_mentioned", [])
                for entity in entities:
                    if ":" in entity:
                        entity_type, entity_name = entity.split(":", 1)
                        if entity_type in kpk_entities:
                            kpk_entities[entity_type].add(entity_name)
        
        return {
            "total_chunks": total_chunks,
            "kpk_chunks": kpk_chunks,
            "kpk_coverage_percentage": (kpk_chunks / total_chunks * 100) if total_chunks > 0 else 0,
            "kpk_entity_coverage": {
                entity_type: len(names) for entity_type, names in kpk_entities.items()
            },
            "recommendations": self._generate_kpk_recommendations(kpk_chunks, total_chunks, kpk_entities)
        }
    
    def _generate_kpk_recommendations(self, kpk_chunks: int, total_chunks: int, 
                                     kpk_entities: Dict[str, Set]) -> List[str]:
        """Generate recommendations for improving KPK coverage."""
        recommendations = []
        
        # Check KPK coverage
        coverage = kpk_chunks / total_chunks if total_chunks > 0 else 0
        if coverage < 0.3:
            recommendations.append("Add more KPK-specific documents to improve coverage")
        
        # Check entity type coverage
        for entity_type, names in kpk_entities.items():
            if len(names) < 3:  # At least 3 entities per type
                recommendations.append(f"Add more {entity_type} entities for better KPK representation")
        
        # Check for Hazara coverage
        hazara_mentioned = any(
            "hazara" in chunk.text.lower() 
            for chunk in self.chunk_registry.values()
        )
        if not hazara_mentioned:
            recommendations.append("Include Hazara Division specific content for comprehensive KPK coverage")
        
        return recommendations

class KPKFAISSIndexer:
    """Main class for KPK-specific FAISS indexing with Neo4j integration."""
    
    def __init__(self, config: Optional[FAISSConfig] = None):
        self.index_manager = FAISSIndexManager(config)
        self.embedding_dimension = None
        
        # KPK-specific configurations
        self.kpk_entity_weights = {
            "species": 1.2,  # Higher weight for species mentions
            "location": 1.1,  # Higher weight for KPK locations
            "officer": 1.0,
            "penalty": 1.0,
            "law": 0.9
        }
        
        logger.info("KPKFAISSIndexer initialized")
    
    def prepare_for_indexing(self, chunks: List[Dict[str, Any]], 
                            embeddings: np.ndarray) -> Tuple[List[Dict], np.ndarray]:
        """
        Prepare chunks and embeddings for indexing with KPK-specific enhancements.
        
        Args:
            chunks: Chunks from legal_chunker
            embeddings: Corresponding embeddings
            
        Returns:
            Prepared (chunks, embeddings) with KPK enhancements
        """
        if self.embedding_dimension is None:
            self.embedding_dimension = embeddings.shape[1]
        
        # Enhance chunks with KPK metadata
        enhanced_chunks = []
        enhanced_embeddings = []
        
        for chunk, embedding in zip(chunks, embeddings):
            # Check if chunk is KPK-specific
            is_kpk = self._is_kpk_chunk_enhanced(chunk)
            chunk["metadata"]["is_kpk_document"] = is_kpk
            
            # Add KPK entity flags
            chunk["metadata"]["contains_kpk_entities"] = self._contains_kpk_entities(chunk)
            
            # Add chunk type based on content
            chunk_type = self._determine_chunk_type(chunk)
            chunk["metadata"]["chunk_type"] = chunk_type
            
            # Boost embedding if KPK-specific
            if is_kpk:
                boosted_embedding = self._boost_kpk_embedding(embedding, chunk)
                enhanced_embeddings.append(boosted_embedding)
            else:
                enhanced_embeddings.append(embedding)
            
            enhanced_chunks.append(chunk)
        
        return enhanced_chunks, np.array(enhanced_embeddings)
    
    def _is_kpk_chunk_enhanced(self, chunk: Dict[str, Any]) -> bool:
        """Enhanced KPK chunk detection."""
        text = chunk.get("text", "").lower()
        metadata = chunk.get("metadata", {})
        
        # Check metadata
        if metadata.get("is_kpk_document", False):
            return True
        
        # Check for KPK keywords with context
        kpk_keywords = [
            ("kpk", 1.0),
            ("khyber pakhtunkhwa", 1.0),
            ("nwfp", 0.8),
            ("hazara", 0.9),
            ("forest ordinance", 0.7),
            ("forest act", 0.7),
            ("deodar", 0.6),
            ("kail", 0.6),
            ("dfo", 0.5),
            ("range officer", 0.5)
        ]
        
        score = 0.0
        for keyword, weight in kpk_keywords:
            if keyword in text:
                score += weight
        
        # Check for KPK locations
        kpk_locations = ["abbottabad", "mansehra", "swat", "dir", "malakand", 
                        "peshawar", "mardan", "kohat", "bannu", "d.i.khan"]
        
        for location in kpk_locations:
            if location in text:
                score += 0.3
        
        return score >= 1.0  # Threshold for KPK classification
    
    def _contains_kpk_entities(self, chunk: Dict[str, Any]) -> bool:
        """Check if chunk contains KPK-specific entities."""
        entities = chunk.get("entities_mentioned", [])
        
        kpk_entity_patterns = [
            "species:deodar", "species:kail", "species:fir", "species:spruce",
            "location:hazara", "location:swat", "location:abbottabad",
            "officer:dfo", "officer:range officer", "officer:beat guard"
        ]
        
        return any(any(pattern in entity.lower() for pattern in kpk_entity_patterns) 
                  for entity in entities)
    
    def _determine_chunk_type(self, chunk: Dict[str, Any]) -> str:
        """Determine the type of chunk based on content."""
        text = chunk.get("text", "").lower()
        metadata = chunk.get("metadata", {})
        
        # Check for legal sections
        if any(marker in text for marker in ["section", "article", "धारा", "دفعہ"]):
            return "law_section"
        
        # Check for species descriptions
        if any(species in text for species in ["deodar", "kail", "fir", "spruce", "oak"]):
            return "species"
        
        # Check for location descriptions
        if any(location in text for location in ["forest", "division", "range", "beat", "compartment"]):
            return "location"
        
        # Check for penalties
        if any(penalty in text for penalty in ["fine", "penalty", "punishment", "rs.", "rupees"]):
            return "penalty"
        
        # Check for officer powers
        if any(officer in text for officer in ["officer", "dfo", "range", "beat", "authority"]):
            return "officer"
        
        # Default
        return "general"
    
    def _boost_kpk_embedding(self, embedding: np.ndarray, chunk: Dict[str, Any]) -> np.ndarray:
        """Boost embedding for KPK-specific chunks."""
        boosted = embedding.copy()
        
        # Get entity weights
        entities = chunk.get("entities_mentioned", [])
        total_weight = 1.0
        
        for entity in entities:
            if ":" in entity:
                entity_type = entity.split(":")[0]
                weight = self.kpk_entity_weights.get(entity_type, 1.0)
                total_weight *= weight
        
        # Apply boost
        if total_weight > 1.0:
            boost_factor = min(total_weight, 1.5)  # Max 50% boost
            boosted = boosted * boost_factor
            
            # Renormalize if using inner product
            if self.index_manager.config.metric == "IP":
                norm = np.linalg.norm(boosted)
                if norm > 0:
                    boosted = boosted / norm
        
        return boosted
    
    def create_and_index(self, chunks: List[Dict[str, Any]], 
                        embeddings: np.ndarray) -> Dict[str, Any]:
        """
        Create FAISS index and index chunks with KPK enhancements.
        
        Args:
            chunks: Chunks from legal_chunker
            embeddings: Corresponding embeddings
            
        Returns:
            Indexing statistics and metadata
        """
        # Prepare chunks and embeddings
        prepared_chunks, prepared_embeddings = self.prepare_for_indexing(chunks, embeddings)
        
        # Set embedding dimension
        self.embedding_dimension = prepared_embeddings.shape[1]
        
        # Create index
        self.index_manager.create_index(self.embedding_dimension)
        
        # Train index if we have enough data
        if len(prepared_embeddings) >= self.index_manager.config.train_size:
            training_size = min(self.index_manager.config.train_size, len(prepared_embeddings))
            training_vectors = prepared_embeddings[:training_size]
            self.index_manager.train_index(training_vectors)
        
        # Index chunks
        indexing_stats = self.index_manager.index_chunks(prepared_chunks, prepared_embeddings)
        
        # Create specialized indices for KPK entity types
        self._create_kpk_specialized_indices(prepared_chunks, prepared_embeddings)
        
        # Generate comprehensive report
        report = self._generate_indexing_report(indexing_stats, prepared_chunks)
        
        return report
    
    def _create_kpk_specialized_indices(self, chunks: List[Dict], embeddings: np.ndarray):
        """Create specialized indices for KPK entity types."""
        entity_types = ["species", "location", "officer", "law"]
        
        for entity_type in entity_types:
            # Filter chunks for this entity type
            filtered_chunks = []
            filtered_embeddings = []
            
            for chunk, embedding in zip(chunks, embeddings):
                entities = chunk.get("entities_mentioned", [])
                if any(entity.startswith(f"{entity_type}:") for entity in entities):
                    # Check if it's KPK-specific
                    if self._is_kpk_chunk_enhanced(chunk):
                        filtered_chunks.append(chunk)
                        filtered_embeddings.append(embedding)
            
            if filtered_chunks and len(filtered_chunks) >= 10:  # Minimum for specialized index
                success = self.index_manager.create_specialized_index(
                    entity_type, filtered_chunks, np.array(filtered_embeddings)
                )
                if success:
                    logger.info(f"Created specialized {entity_type} index with {len(filtered_chunks)} KPK chunks")
    
    def _generate_indexing_report(self, indexing_stats: Dict[str, Any], 
                                 chunks: List[Dict]) -> Dict[str, Any]:
        """Generate comprehensive indexing report."""
        total_stats = self.index_manager.get_index_statistics()
        kpk_report = self.index_manager.get_kpk_coverage_report()
        
        # Calculate quality metrics
        embedding_ready = sum(1 for chunk in chunks if chunk.get("embedding_ready", True))
        total_chunks = len(chunks)
        
        report = {
            "indexing_summary": indexing_stats,
            "index_statistics": total_stats,
            "kpk_coverage_report": kpk_report,
            "quality_metrics": {
                "embedding_ready_percentage": (embedding_ready / total_chunks * 100) if total_chunks > 0 else 0,
                "average_chunk_length": sum(len(chunk.get("text", "")) for chunk in chunks) / total_chunks if total_chunks > 0 else 0,
                "entity_density": sum(len(chunk.get("entities_mentioned", [])) for chunk in chunks) / total_chunks if total_chunks > 0 else 0
            },
            "recommendations": kpk_report.get("recommendations", []),
            "timestamp": datetime.now().isoformat(),
            "index_configuration": self.index_manager.config.__dict__
        }
        
        # Add specialized indices info
        if self.index_manager.specialized_indices:
            report["specialized_indices"] = {
                entity_type: len(index.chunk_registry)
                for entity_type, index in self.index_manager.specialized_indices.items()
            }
        
        return report
    
    def save(self, output_dir: Union[str, Path]) -> Dict[str, Path]:
        """
        Save complete FAISS indexing system.
        
        Args:
            output_dir: Directory to save files
            
        Returns:
            Dict of saved file paths
        """
        output_dir = Path(output_dir)
        
        # Save main index
        file_paths = self.index_manager.save_index(output_dir)
        
        # Save specialized indices
        specialized_dir = output_dir / "specialized_indices"
        specialized_dir.mkdir(exist_ok=True)
        
        for entity_type, index in self.index_manager.specialized_indices.items():
            entity_dir = specialized_dir / entity_type
            index.save_index(entity_dir)
        
        # Save KPK-specific metadata
        kpk_metadata_path = output_dir / "kpk_indexing_metadata.json"
        kpk_metadata = {
            "entity_weights": self.kpk_entity_weights,
            "embedding_dimension": self.embedding_dimension,
            "specialized_indices_count": len(self.index_manager.specialized_indices),
            "save_timestamp": datetime.now().isoformat()
        }
        
        with open(kpk_metadata_path, 'w', encoding='utf-8') as f:
            json.dump(kpk_metadata, f, indent=2, ensure_ascii=False)
        
        file_paths["kpk_metadata"] = kpk_metadata_path
        
        logger.info(f"Complete FAISS system saved to {output_dir}")
        return file_paths
    
    def load(self, input_dir: Union[str, Path]) -> bool:
        """
        Load complete FAISS indexing system.
        
        Args:
            input_dir: Directory containing saved files
            
        Returns:
            True if successful
        """
        input_dir = Path(input_dir)
        
        # Load main index
        success = self.index_manager.load_index(input_dir)
        if not success:
            return False
        
        # Load specialized indices
        specialized_dir = input_dir / "specialized_indices"
        if specialized_dir.exists():
            for entity_dir in specialized_dir.iterdir():
                if entity_dir.is_dir():
                    entity_type = entity_dir.name
                    specialized_index = FAISSIndexManager(self.index_manager.config)
                    if specialized_index.load_index(entity_dir):
                        self.index_manager.specialized_indices[entity_type] = specialized_index
                        logger.info(f"Loaded specialized {entity_type} index")
        
        # Load KPK metadata
        kpk_metadata_path = input_dir / "kpk_indexing_metadata.json"
        if kpk_metadata_path.exists():
            with open(kpk_metadata_path, 'r', encoding='utf-8') as f:
                kpk_metadata = json.load(f)
            
            self.kpk_entity_weights = kpk_metadata.get("entity_weights", self.kpk_entity_weights)
            self.embedding_dimension = kpk_metadata.get("embedding_dimension")
        
        logger.info(f"Complete FAISS system loaded from {input_dir}")
        return True
    
    def search_with_kpk_context(self, query_embedding: np.ndarray, 
                               neo4j_context: Optional[Dict[str, Any]] = None,
                               k: int = 10,
                               use_kpk_boost: bool = True) -> List[SearchResult]:
        """
        Search with KPK context awareness.
        
        Args:
            query_embedding: Query embedding
            neo4j_context: Neo4j context information
            k: Number of results
            use_kpk_boost: Whether to boost KPK results
            
        Returns:
            Search results
        """
        # Boost query if looking for KPK content
        if use_kpk_boost and neo4j_context and neo4j_context.get("jurisdiction") == "KPK":
            query_embedding = self._boost_kpk_query(query_embedding)
        
        # Perform hybrid search
        results = self.index_manager.hybrid_search(query_embedding, neo4j_context, k * 2)
        
        # Apply KPK-specific re-ranking
        if use_kpk_boost:
            results = self._rerank_with_kpk_preference(results)
        
        return results[:k]
    
    def _boost_kpk_query(self, query_embedding: np.ndarray) -> np.ndarray:
        """Boost query embedding for KPK content."""
        # Simple boosting - in practice, this could be more sophisticated
        boosted = query_embedding * 1.1  # 10% boost
        
        # Renormalize if using inner product
        if self.index_manager.config.metric == "IP":
            norm = np.linalg.norm(boosted)
            if norm > 0:
                boosted = boosted / norm
        
        return boosted
    
    def _rerank_with_kpk_preference(self, results: List[SearchResult]) -> List[SearchResult]:
        """Re-rank results with preference for KPK content."""
        for result in results:
            # Check if result is KPK-specific
            is_kpk = self._is_kpk_chunk_enhanced({
                "text": result.text,
                "metadata": result.metadata
            })
            
            if is_kpk:
                # Boost KPK results
                result.similarity_score *= 1.2
        
        # Sort by boosted score
        return sorted(results, key=lambda x: x.similarity_score, reverse=True)
    
    def generate_neo4j_linking_cypher(self) -> List[str]:
        """
        Generate Cypher queries to link FAISS chunks to Neo4j nodes.
        
        Returns:
            List of Cypher queries
        """
        cypher_queries = []
        
        # Header
        cypher_queries.append("-- FAISS to Neo4j Linking Queries")
        cypher_queries.append(f"-- Generated: {datetime.now().isoformat()}")
        cypher_queries.append("")
        
        # Create index on node_id for performance
        cypher_queries.append("CREATE INDEX IF NOT EXISTS FOR (n:DocumentChunk) ON (n.node_id);")
        cypher_queries.append("")
        
        # Link each chunk to its Neo4j node
        for faiss_id, chunk in self.index_manager.chunk_registry.items():
            neo4j_node_id = chunk.neo4j_node_id
            chunk_id = chunk.chunk_id
            
            query = f"""
            MATCH (n {{node_id: '{neo4j_node_id}'}})
            MERGE (c:DocumentChunk {{chunk_id: '{chunk_id}'}})
            SET c.faiss_index_id = {faiss_id},
                c.text_preview = '{chunk.text[:100].replace("'", "''")}',
                c.embedding_hash = '{chunk.embedding_hash}',
                c.indexed_at = datetime('{chunk.created_at}')
            MERGE (n)-[:HAS_CHUNK]->(c)
            RETURN c.chunk_id, n.node_id
            """
            
            cypher_queries.append(query)
            cypher_queries.append("")
        
        # Create relationships between chunks mentioning same entities
        cypher_queries.append("-- Create relationships between related chunks")
        cypher_queries.append("""
        MATCH (c1:DocumentChunk), (c2:DocumentChunk)
        WHERE c1 <> c2 AND c1.faiss_index_id IS NOT NULL AND c2.faiss_index_id IS NOT NULL
        WITH c1, c2, gds.similarity.cosine(
          [c1.faiss_index_id % 1000, c1.faiss_index_id // 1000], 
          [c2.faiss_index_id % 1000, c2.faiss_index_id // 1000]
        ) as similarity
        WHERE similarity > 0.7
        MERGE (c1)-[:SIMILAR_TO {score: similarity}]->(c2)
        RETURN count(*) as relationships_created
        """)
        
        return cypher_queries

# Utility functions
def create_kpk_faiss_indexer(index_type: str = "IVF_FLAT", 
                           dimension: Optional[int] = None) -> KPKFAISSIndexer:
    """
    Factory function to create KPK FAISS indexer.
    
    Args:
        index_type: Type of FAISS index
        dimension: Embedding dimension (if known)
        
    Returns:
        KPKFAISSIndexer instance
    """
    config = FAISSConfig(index_type=index_type)
    
    if dimension:
        config.train_size = min(config.train_size, 5000)  # Adjust for known dimension
    
    return KPKFAISSIndexer(config)


def index_kpk_documents(chunks: List[Dict[str, Any]], 
                       embeddings: np.ndarray,
                       output_dir: Union[str, Path]) -> Dict[str, Any]:
    """
    Complete indexing pipeline for KPK documents.
    
    Args:
        chunks: Chunks from legal_chunker
        embeddings: Corresponding embeddings
        output_dir: Directory to save index
        
    Returns:
        Complete indexing report
    """
    # Create indexer
    indexer = create_kpk_faiss_indexer()
    
    # Create and index
    report = indexer.create_and_index(chunks, embeddings)
    
    # Save to disk
    file_paths = indexer.save(output_dir)
    report["saved_files"] = {k: str(v) for k, v in file_paths.items()}
    
    # Generate Neo4j linking queries
    cypher_queries = indexer.generate_neo4j_linking_cypher()
    cypher_path = Path(output_dir) / "neo4j_linking.cypher"
    with open(cypher_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(cypher_queries))
    
    report["cypher_queries_generated"] = len(cypher_queries)
    report["cypher_file"] = str(cypher_path)
    
    return report


# Example usage and testing
if __name__ == "__main__":
    print("=== Testing KPKFAISSIndexer ===\n")
    
    # Create sample data
    sample_chunks = [
        {
            "chunk_id": "chunk_1",
            "text": "Section 27: Penalty for unauthorized felling of Deodar trees in KPK forests.",
            "metadata": {
                "document_type": "law",
                "section_number": "27",
                "entities_mentioned": ["species:deodar", "location:kpk", "penalty:unauthorized_felling"],
                "is_kpk_document": True,
                "confidence": 0.95
            },
            "embedding_ready": True
        },
        {
            "chunk_id": "chunk_2",
            "text": "The Range Officer in Swat Division has authority to issue permits for timber transport.",
            "metadata": {
                "document_type": "circular",
                "entities_mentioned": ["officer:range officer", "location:swat", "permit:timber_transport"],
                "is_kpk_document": True,
                "confidence": 0.88
            },
            "embedding_ready": True
        },
        {
            "chunk_id": "chunk_3",
            "text": "General environmental regulations apply across Pakistan.",
            "metadata": {
                "document_type": "policy",
                "entities_mentioned": ["location:pakistan"],
                "is_kpk_document": False,
                "confidence": 0.90
            },
            "embedding_ready": True
        }
    ]
    
    # Create sample embeddings (384-dimensional, like Sentence-BERT)
    np.random.seed(42)
    sample_embeddings = np.random.randn(3, 384).astype(np.float32)
    
    # Normalize for inner product similarity
    faiss.normalize_L2(sample_embeddings)
    
    print("Sample chunks and embeddings created")
    print(f"Chunks: {len(sample_chunks)}")
    print(f"Embedding shape: {sample_embeddings.shape}")
    
    print("\n" + "=" * 60)
    
    # Create and index
    print("\nCreating FAISS index...")
    indexer = create_kpk_faiss_indexer("IVF_FLAT", 384)
    
    report = indexer.create_and_index(sample_chunks, sample_embeddings)
    
    print("\nIndexing Report:")
    print("-" * 40)
    print(f"Total chunks indexed: {report['indexing_summary']['successful']}")
    print(f"KPK chunks: {report['indexing_summary']['kpk_chunks']}")
    print(f"KPK coverage: {report['kpk_coverage_report']['kpk_coverage_percentage']:.1f}%")
    
    print("\n" + "=" * 60)
    
    # Test search
    print("\nTesting search...")
    
    # Create a query embedding (similar to chunk 1)
    query_embedding = sample_embeddings[0].copy()
    
    # Add some noise
    query_embedding += np.random.randn(384) * 0.1
    faiss.normalize_L2(query_embedding.reshape(1, -1))
    
    # Search with KPK context
    results = indexer.search_with_kpk_context(
        query_embedding,
        neo4j_context={"jurisdiction": "KPK", "entity_ids": ["species:deodar"]},
        k=3
    )
    
    print(f"\nSearch Results (KPK context):")
    print("-" * 40)
    for i, result in enumerate(results, 1):
        print(f"\nResult {i}:")
        print(f"  Chunk ID: {result.chunk_id}")
        print(f"  Neo4j Node: {result.neo4j_node_id}")
        print(f"  Score: {result.similarity_score:.3f}")
        print(f"  Text: {result.text[:80]}...")
        print(f"  KPK: {'Yes' if 'kpk' in result.text.lower() else 'No'}")
    
    print("\n" + "=" * 60)
    
    # Test specialized search
    print("\nTesting specialized search for species...")
    
    species_results = indexer.index_manager.search_specialized(
        query_embedding,
        entity_type="species",
        k=2
    )
    
    if species_results:
        print(f"Found {len(species_results)} species-specific results")
        for result in species_results:
            print(f"  - {result.chunk_id}: {result.text[:60]}...")
    else:
        print("No specialized species index available yet")
    
    print("\n" + "=" * 60)
    
    # Save index
    print("\nSaving index to disk...")
    output_dir = Path("kpk_faiss_index")
    file_paths = indexer.save(output_dir)
    
    print(f"\nSaved files:")
    for file_type, file_path in file_paths.items():
        print(f"  {file_type}: {file_path}")
    
    print("\n" + "=" * 60)
    
    # Generate Neo4j linking
    print("\nGenerating Neo4j linking queries...")
    cypher_queries = indexer.generate_neo4j_linking_cypher()
    
    print(f"Generated {len(cypher_queries)} Cypher queries")
    print("\nSample query:")
    print("-" * 40)
    print(cypher_queries[10][:200] + "..." if len(cypher_queries) > 10 else "No queries generated")
    
    print("\n" + "=" * 60)
    print("KPKFAISSIndexer Test Complete ✓")
