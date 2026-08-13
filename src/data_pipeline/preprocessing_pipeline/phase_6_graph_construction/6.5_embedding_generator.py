"""
EMBEDDING_GENERATOR.PY - Phase 6
Generates vector embeddings for document chunks using SentenceTransformers or Ollama.
"""
import logging
from typing import Dict, List, Tuple, Optional, Any, Union
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np
import hashlib
import re
import pickle

# SentenceTransformers will be imported lazily
SENTENCE_TRANSFORMERS_AVAILABLE = None

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class ChunkEmbedding:
    """Embedding for a legal document chunk."""
    chunk_id: str
    embedding: np.ndarray
    metadata: Dict[str, Any]
    model_name: str
    dimension: int
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to serializable dictionary."""
        return {
            "chunk_id": self.chunk_id,
            "embedding": self.embedding.tolist() if isinstance(self.embedding, np.ndarray) else self.embedding,
            "metadata": self.metadata,
            "model_name": self.model_name,
            "dimension": self.dimension,
            "created_at": self.created_at,
            "embedding_hash": hashlib.md5(str(self.embedding).encode()).hexdigest()[:8]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChunkEmbedding':
        """Create from dictionary."""
        embedding = data.get("embedding", [])
        if isinstance(embedding, list):
            embedding = np.array(embedding, dtype=np.float32)
        
        dim = len(embedding) if embedding is not None else 0
        
        return cls(
            chunk_id=data["chunk_id"],
            embedding=embedding,
            metadata=data.get("metadata", {}),
            model_name=data.get("model_name", "unknown"),
            dimension=data.get("dimension", dim),
            created_at=data.get("created_at", data.get("created_at", datetime.now().isoformat()))
        )

@dataclass
class EmbeddingBatch:
    """Batch of embeddings with metadata."""
    embeddings: List[ChunkEmbedding]
    batch_id: str
    model_config: Dict[str, Any]
    statistics: Dict[str, Any]
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to serializable dictionary."""
        return {
            "batch_id": self.batch_id,
            "embeddings": [emb.to_dict() for emb in self.embeddings],
            "model_config": self.model_config,
            "statistics": self.statistics,
            "created_at": self.created_at,
            "total_embeddings": len(self.embeddings),
            "embedding_dimension": self.model_config.get("embedding_dimension", 0)
        }

    def __len__(self) -> int:
        return len(self.embeddings)

class MultilingualEmbeddingModel:
    """Multilingual embedding model with KPK domain adaptation."""
    
    def __init__(self, model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"):
        """
        Initialize multilingual embedding model.
        
        Args:
            model_name: SentenceTransformers model name
        """
        self.model_name = model_name
        self.model = None
        self.embedding_dimension = 384  # Default for MiniLM
        
        # Language detection patterns
        self.language_patterns = {
            'urdu': r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]+',
            'pashto': r'[\u0600-\u06FF\u0750-\u077F]+',
            'english': r'[A-Za-z]+'
        }
        
        # KPK-specific terms for domain adaptation
        self.kpk_terms = [
            # Tree species
            "deodar", "kail", "fir", "spruce", "chir pine", "oak",
            "دیار", "کیل", "راڑ", "اسپروس", "چلغوزا", "بلوط",
            
            # Locations
            "kpk", "khyber pakhtunkhwa", "hazara", "swat", "dir", "malakand",
            "خیبر پختونخوا", "ہزارہ", "سوات", "دیر", "مالاکنڈ",
            
            # Legal terms
            "forest ordinance", "forest act", "penalty", "fine", "permit",
            "جنگل آرڈیننس", "جنگل ایکٹ", "جرمانہ", "اجازت نامہ",
            
            # Officer ranks
            "dfo", "range officer", "beat guard", "conservator",
            "ڈی ایف او", "رینج آفیسر", "بیٹ گارڈ", "کنسرویٹر"
        ]
        
        logger.info(f"MultilingualEmbeddingModel initialized (model load deferred: {model_name})")
    
    def _initialize_model(self):
        """Initialize the SentenceTransformer model."""
        global SENTENCE_TRANSFORMERS_AVAILABLE
        
        # Lazy import to prevent pipeline hang during initialization
        if SENTENCE_TRANSFORMERS_AVAILABLE is None:
            try:
                from sentence_transformers import SentenceTransformer
                SENTENCE_TRANSFORMERS_AVAILABLE = True
            except ImportError:
                SENTENCE_TRANSFORMERS_AVAILABLE = False
            except Exception as e:
                logger.error(f"SentenceTransformers lazy import failed: {e}")
                SENTENCE_TRANSFORMERS_AVAILABLE = False

        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            logger.error("SentenceTransformers not installed/loadable. Using fallback embeddings.")
            return
        
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            
            # Test embedding to get dimension
            try:
                test_embedding = self.model.encode(["test"])
                self.embedding_dimension = len(test_embedding[0])
                logger.info(f"Model loaded successfully. Embedding dimension: {self.embedding_dimension}")
            except Exception as e:
                 logger.warning(f"Model loaded but encoding failed: {e}. Using default dimension 384.")
            
        except Exception as e:
            logger.error(f"Failed to load model {self.model_name}: {e}")
            self.model = None
    
    def detect_language(self, text: str) -> Dict[str, float]:
        """
        Detect language composition of text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Dict with language percentages
        """
        total_chars = len(text)
        if total_chars == 0:
            return {'unknown': 1.0}
        
        language_counts = {}
        
        for lang, pattern in self.language_patterns.items():
            matches = re.findall(pattern, text)
            total_matches = sum(len(match) for match in matches)
            language_counts[lang] = total_matches / total_chars if total_chars > 0 else 0
        
        # Normalize to percentages
        total = sum(language_counts.values())
        if total > 0:
            return {lang: count/total for lang, count in language_counts.items()}
        else:
            return {'unknown': 1.0}
    
    def prepare_text_for_embedding(self, text: str, metadata: Dict[str, Any]) -> str:
        """
        Prepare text for embedding generation.
        
        Args:
            text: Original text
            metadata: Chunk metadata
            
        Returns:
            Prepared text
        """
        # Basic cleaning
        prepared = text.strip()
        
        # Remove excessive whitespace
        prepared = re.sub(r'\s+', ' ', prepared)
        
        # Add metadata context if available
        context_parts = []
        
        # Add document type context
        doc_type = metadata.get("document_type", "")
        if doc_type:
            context_parts.append(f"[Document type: {doc_type}]")
        
        # Add section context
        section_info = metadata.get("section_info", "")
        if section_info:
            context_parts.append(f"[Section: {section_info}]")
        
        # Add KPK context if KPK document
        if metadata.get("is_kpk_document", False):
            context_parts.append("[KPK Forestry Document]")
        
        # Add species mentions if present
        species_mentioned = metadata.get("species_mentioned", [])
        if species_mentioned:
            species_str = ", ".join(species_mentioned[:3])  # Limit to 3 species
            context_parts.append(f"[Species: {species_str}]")
        
        # Combine context with text
        if context_parts:
            context = " ".join(context_parts)
            prepared = f"{context} {prepared}"
        
        # Limit length (models have token limits)
        max_length = 512  # Conservative limit
        if len(prepared) > max_length * 4:  # Rough character estimate
            # Try to preserve the most important parts
            sentences = re.split(r'[.!?۔]+', prepared)
            important_sentences = []
            current_length = 0
            
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue
                
                # Check if sentence contains important terms
                is_important = any(
                    term.lower() in sentence.lower() 
                    for term in self.kpk_terms
                ) or any(keyword in sentence.lower() 
                        for keyword in ["penalty", "fine", "permit", "prohibited", "shall"])
                
                if is_important or current_length < max_length * 2:
                    important_sentences.append(sentence)
                    current_length += len(sentence)
            
            prepared = ". ".join(important_sentences)
        
        return prepared[:max_length * 4]  # Final safety limit
    
    def generate_embedding(self, text: str, metadata: Dict[str, Any]) -> Optional[np.ndarray]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            metadata: Metadata for context
            
        Returns:
            Embedding vector or None if failed
        """
        if not self.model:
            self._initialize_model()
            
        if not self.model:
            logger.warning("Model failed to initialize, using fallback embedding")
            return self._generate_fallback_embedding(text)
        
        try:
            # Prepare text
            prepared_text = self.prepare_text_for_embedding(text, metadata)
            
            # Generate embedding
            embedding = self.model.encode(
                prepared_text,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False
            )
            
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return self._generate_fallback_embedding(text)
    
    def _generate_fallback_embedding(self, text: str) -> np.ndarray:
        """Generate a simple fallback embedding when model fails."""
        # Simple hash-based deterministic embedding
        text_hash = hashlib.md5(text.encode()).hexdigest()
        hash_int = int(text_hash[:8], 16)
        
        # Create pseudo-random embedding based on hash
        np.random.seed(hash_int % (2**32 - 1))
        embedding = np.random.randn(self.embedding_dimension).astype(np.float32)
        
        # Normalize
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        
        return embedding
    
    def batch_generate_embeddings(self, texts: List[str], metadata_list: List[Dict[str, Any]]) -> List[np.ndarray]:
        """
        Generate embeddings in batch for efficiency.
        
        Args:
            texts: List of texts to embed
            metadata_list: List of metadata dicts
            
        Returns:
            List of embedding vectors
        """
        if not self.model:
            self._initialize_model()

        if not self.model or len(texts) == 0:
            return []
        
        try:
            # Prepare all texts
            prepared_texts = [
                self.prepare_text_for_embedding(text, metadata)
                for text, metadata in zip(texts, metadata_list)
            ]
            
            # Generate embeddings in batch
            embeddings = self.model.encode(
                prepared_texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=True,
                batch_size=32
            )
            
            return embeddings
            
        except Exception as e:
            logger.error(f"Batch embedding generation failed: {e}")
            # Fallback to individual generation
            embeddings = []
            for text, metadata in zip(texts, metadata_list):
                embedding = self.generate_embedding(text, metadata)
                if embedding is not None:
                    embeddings.append(embedding)
                else:
                    # Add zero vector as placeholder
                    embeddings.append(np.zeros(self.embedding_dimension, dtype=np.float32))
            
            return embeddings

class KPKEmbeddingGenerator:
    """Main embedding generator for KPK legal documents."""
    
    def __init__(self, model_name: Optional[str] = None, cache_dir: Optional[Path] = None):
        """
        Initialize KPK embedding generator.
        
        Args:
            model_name: SentenceTransformers model name
            cache_dir: Directory for caching embeddings
        """
        self.model_name = model_name or "paraphrase-multilingual-MiniLM-L12-v2"
        self.embedding_model = MultilingualEmbeddingModel(self.model_name)
        
        # Cache configuration
        self.cache_dir = cache_dir or Path("embedding_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Statistics
        self.stats = {
            "total_chunks_processed": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "errors": 0,
            "batch_processing_times": []
        }
        
        logger.info(f"KPKEmbeddingGenerator initialized with cache at {self.cache_dir}")
    
    def generate(self, texts: List[str], metadata_list: Optional[List[Dict[str, Any]]] = None) -> List[np.ndarray]:
        """
        Generate embeddings for a list of texts (Compatibility wrapper for GraphBuilder).
        
        Args:
            texts: List of texts to embed
            metadata_list: Optional list of metadata dictionaries
            
        Returns:
            List of embedding vectors
        """
        if metadata_list is None:
            metadata_list = [{} for _ in texts]
            
        return self.embedding_model.batch_generate_embeddings(texts, metadata_list)

    def generate_embeddings(self, text_chunks: List[Dict[str, Any]]) -> Any:
        """Compatibility method for run_sequential_pipeline.py."""
        # The legacy pipeline expects this to return an object or list that FAISSIndexer can use
        return self.generate_chunk_embeddings(text_chunks)
    
    def generate_chunk_embeddings(self, chunks: List[Dict[str, Any]], 
                                 batch_size: int = 32) -> EmbeddingBatch:
        """
        Generate embeddings for document chunks.
        
        Args:
            chunks: List of chunk dictionaries from 6.4_legal_chunker.py
            batch_size: Batch size for processing
            
        Returns:
            EmbeddingBatch with all embeddings
        """
        logger.info(f"Generating embeddings for {len(chunks)} chunks")
        
        embeddings = []
        processed_chunks = []
        errors = []
        
        # Check cache first
        for chunk in chunks:
            cached_embedding = self._get_cached_embedding(chunk)
            if cached_embedding:
                embeddings.append(cached_embedding)
                self.stats["cache_hits"] += 1
            else:
                processed_chunks.append(chunk)
                self.stats["cache_misses"] += 1
        
        # Generate embeddings for non-cached chunks
        if processed_chunks:
            batch_embeddings = self._process_chunk_batch(processed_chunks, batch_size)
            embeddings.extend(batch_embeddings)
            
            # Cache new embeddings
            for embedding in batch_embeddings:
                self._cache_embedding(embedding)
        
        # Update statistics
        self.stats["total_chunks_processed"] += len(chunks)
        
        # Create batch
        batch_id = f"embedding_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        return EmbeddingBatch(
            embeddings=embeddings,
            batch_id=batch_id,
            model_config={
                "model_name": self.model_name,
                "embedding_dimension": self.embedding_model.embedding_dimension,
                "multilingual": True,
                "kpk_adapted": True
            },
            statistics={
                "total_embeddings": len(embeddings),
                "cache_hits": self.stats["cache_hits"],
                "cache_misses": self.stats["cache_misses"],
                "cache_hit_rate": self.stats["cache_hits"] / len(chunks) if chunks else 0,
                "errors": len(errors),
                "batch_size_used": batch_size
            }
        )
    
    def _process_chunk_batch(self, chunks: List[Dict[str, Any]], batch_size: int) -> List[ChunkEmbedding]:
        """Process a batch of chunks."""
        embeddings = []
        
        # Split into batches
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}/{(len(chunks)-1)//batch_size + 1}")
            
            try:
                # Extract texts and metadata
                texts = [chunk.get("chunk_text", chunk.get("text", "")) for chunk in batch]
                metadata_list = [chunk.get("metadata", {}) for chunk in batch]
                
                # Generate embeddings
                embedding_vectors = self.embedding_model.batch_generate_embeddings(texts, metadata_list)
                
                # Create ChunkEmbedding objects
                for chunk, embedding_vector in zip(batch, embedding_vectors):
                    chunk_text = chunk.get("chunk_text", chunk.get("text", ""))
                    # Analyze language composition
                    language_composition = self.embedding_model.detect_language(chunk_text)
                    
                    # Create enhanced metadata
                    enhanced_metadata = chunk.get("metadata", {}).copy()
                    enhanced_metadata.update({
                        "language_composition": language_composition,
                        "embedding_generated": True,
                        "model_used": self.model_name,
                        "original_text": chunk_text,
                        "original_text_length": len(chunk_text)
                    })
                    
                    embedding = ChunkEmbedding(
                        chunk_id=chunk.get("chunk_id", f"chunk_{hashlib.md5(str(chunk).encode()).hexdigest()[:8]}"),
                        embedding=embedding_vector,
                        metadata=enhanced_metadata,
                        model_name=self.model_name,
                        dimension=self.embedding_model.embedding_dimension
                    )
                    
                    embeddings.append(embedding)
                    
            except Exception as e:
                logger.error(f"Error processing batch: {e}")
                self.stats["errors"] += 1
        
        return embeddings
    
    def _get_cached_embedding(self, chunk: Dict[str, Any]) -> Optional[ChunkEmbedding]:
        """Retrieve embedding from cache if available."""
        chunk_id = chunk.get("chunk_id")
        if not chunk_id:
            return None
        
        # Generate cache key
        cache_key = self._generate_cache_key(chunk)
        cache_file = self.cache_dir / f"{cache_key}.pkl"
        
        if cache_file.exists():
            try:
                with open(cache_file, 'rb') as f:
                    cached_data = pickle.load(f)
                
                # Verify chunk hasn't changed
                chunk_text = chunk.get("chunk_text", chunk.get("text", ""))
                text_hash = hashlib.md5(chunk_text.encode()).hexdigest()
                if cached_data.get("text_hash") == text_hash:
                    return ChunkEmbedding.from_dict(cached_data["embedding"])
                    
            except Exception as e:
                logger.warning(f"Failed to load cached embedding: {e}")
        
        return None
    
    def _cache_embedding(self, embedding: ChunkEmbedding):
        """Cache an embedding for future use."""
        try:
            # Generate cache key
            original_text = embedding.metadata.get("original_text", "")
            chunk_data = {
                "chunk_id": embedding.chunk_id,
                "text_hash": hashlib.md5(original_text.encode()).hexdigest(),
                "chunk_text": original_text
            }
            cache_key = self._generate_cache_key(chunk_data)
            cache_file = self.cache_dir / f"{cache_key}.pkl"
            
            # Prepare data for caching
            cache_data = {
                "embedding": embedding.to_dict(),
                "text_hash": chunk_data["text_hash"],
                "cached_at": datetime.now().isoformat()
            }
            
            # Save to cache
            with open(cache_file, 'wb') as f:
                pickle.dump(cache_data, f)
                
        except Exception as e:
            logger.warning(f"Failed to cache embedding: {e}")
    
    def _generate_cache_key(self, chunk: Dict[str, Any]) -> str:
        """Generate cache key for a chunk."""
        # Use chunk_id if available
        chunk_id = chunk.get("chunk_id")
        if chunk_id:
            return f"chunk_{hashlib.md5(chunk_id.encode()).hexdigest()[:12]}"
        
        # Fallback: hash of text and metadata
        text = chunk.get("chunk_text", chunk.get("text", ""))
        metadata_str = str(chunk.get("metadata", {}))
        combined = f"{text}_{metadata_str}"
        
        return f"chunk_{hashlib.md5(combined.encode()).hexdigest()[:12]}"
    
    def analyze_embeddings(self, embeddings: List[ChunkEmbedding]) -> Dict[str, Any]:
        """
        Analyze embedding quality and characteristics.
        
        Args:
            embeddings: List of embeddings to analyze
            
        Returns:
            Analysis results
        """
        if not embeddings:
            return {"error": "No embeddings provided"}
        
        # Extract embedding vectors
        vectors = np.array([emb.embedding for emb in embeddings])
        
        # Basic statistics
        mean_vector = np.mean(vectors, axis=0)
        std_vector = np.std(vectors, axis=0)
        
        # Compute pairwise similarities
        similarities = []
        for i in range(len(vectors)):
            for j in range(i + 1, len(vectors)):
                sim = np.dot(vectors[i], vectors[j])
                similarities.append(sim)
        
        # Language analysis
        language_compositions = []
        for emb in embeddings:
            lang_comp = emb.metadata.get("language_composition", {})
            language_compositions.append(lang_comp)
        
        # Aggregate language stats
        lang_stats = {}
        for comp in language_compositions:
            for lang, percent in comp.items():
                if lang not in lang_stats:
                    lang_stats[lang] = []
                lang_stats[lang].append(percent)
        
        # KPK content analysis
        kpk_embeddings = sum(1 for emb in embeddings 
                            if emb.metadata.get("is_kpk_document", False))
        
        return {
            "embedding_statistics": {
                "total_embeddings": len(embeddings),
                "embedding_dimension": vectors.shape[1],
                "mean_vector_magnitude": float(np.linalg.norm(mean_vector)),
                "std_vector_magnitude": float(np.linalg.norm(std_vector)),
                "similarity_stats": {
                    "mean": float(np.mean(similarities)) if similarities else 0,
                    "std": float(np.std(similarities)) if similarities else 0,
                    "min": float(np.min(similarities)) if similarities else 0,
                    "max": float(np.max(similarities)) if similarities else 0
                }
            },
            "language_analysis": {
                "languages_detected": list(lang_stats.keys()),
                "average_percentages": {
                    lang: float(np.mean(percentages)) 
                    for lang, percentages in lang_stats.items()
                },
                "multilingual_chunks": sum(1 for comp in language_compositions 
                                          if len([p for p in comp.values() if p > 0.1]) > 1)
            },
            "kpk_analysis": {
                "kpk_documents": kpk_embeddings,
                "kpk_percentage": kpk_embeddings / len(embeddings) if embeddings else 0,
                "protected_species_mentions": sum(1 for emb in embeddings 
                                                 if emb.metadata.get("species_mentioned"))
            },
            "quality_indicators": {
                "embedding_norm_consistency": float(np.std([np.linalg.norm(v) for v in vectors])),
                "zero_embeddings": sum(1 for v in vectors if np.all(v == 0)),
                "duplicate_embeddings": self._find_duplicate_embeddings(vectors, threshold=0.99)
            }
        }
    
    def _find_duplicate_embeddings(self, vectors: np.ndarray, threshold: float = 0.99) -> int:
        """Find duplicate embeddings based on similarity threshold."""
        if len(vectors) <= 1:
            return 0
        
        duplicates = 0
        checked = set()
        
        for i in range(len(vectors)):
            if i in checked:
                continue
            
            for j in range(i + 1, len(vectors)):
                similarity = np.dot(vectors[i], vectors[j])
                if similarity >= threshold:
                    duplicates += 1
                    checked.add(j)
        
        return duplicates
    
    def export_embeddings(self, embedding_batch: EmbeddingBatch, 
                         output_dir: Union[str, Path]) -> Dict[str, Path]:
        """
        Export embeddings to files.
        
        Args:
            embedding_batch: Batch of embeddings to export
            output_dir: Directory to save files
            
        Returns:
            Dict mapping file type to path
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        file_paths = {}
        
        # Export as JSON
        json_path = output_dir / "embeddings.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(embedding_batch.to_dict(), f, indent=2, ensure_ascii=False)
        file_paths['json'] = json_path
        
        # Export as numpy array for FAISS
        np_path = output_dir / "embeddings.npy"
        vectors = np.array([emb.embedding for emb in embedding_batch.embeddings])
        np.save(np_path, vectors)
        file_paths['numpy'] = np_path
        
        # Export metadata separately
        metadata_path = output_dir / "embedding_metadata.json"
        metadata = {
            "chunk_ids": [emb.chunk_id for emb in embedding_batch.embeddings],
            "model_config": embedding_batch.model_config,
            "statistics": embedding_batch.statistics,
            "batch_id": embedding_batch.batch_id,
            "export_timestamp": datetime.now().isoformat()
        }
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        file_paths['metadata'] = metadata_path
        
        # Export analysis report
        analysis = self.analyze_embeddings(embedding_batch.embeddings)
        analysis_path = output_dir / "embedding_analysis.json"
        with open(analysis_path, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False)
        file_paths['analysis'] = analysis_path
        
        logger.info(f"Exported {len(embedding_batch.embeddings)} embeddings to {output_dir}")
        
        return file_paths
    
    def get_embedding_report(self, embedding_batch: EmbeddingBatch) -> str:
        """Generate human-readable embedding report."""
        analysis = self.analyze_embeddings(embedding_batch.embeddings)
        
        report_lines = [
            "KPK LEGAL DOCUMENT EMBEDDING REPORT",
            "=" * 60,
            f"Batch ID: {embedding_batch.batch_id}",
            f"Total Embeddings: {len(embedding_batch.embeddings)}",
            f"Model: {embedding_batch.model_config.get('model_name', 'unknown')}",
            f"Dimension: {embedding_batch.model_config.get('embedding_dimension', 0)}",
            "",
            "Embedding Statistics:",
            f"  Mean Similarity: {analysis['embedding_statistics']['similarity_stats']['mean']:.3f}",
            f"  Similarity Std Dev: {analysis['embedding_statistics']['similarity_stats']['std']:.3f}",
            f"  Zero Embeddings: {analysis['quality_indicators']['zero_embeddings']}",
            f"  Duplicate Embeddings: {analysis['quality_indicators']['duplicate_embeddings']}",
            "",
            "Language Analysis:"
        ]
        
        lang_analysis = analysis.get('language_analysis', {})
        for lang, percent in lang_analysis.get('average_percentages', {}).items():
            report_lines.append(f"  {lang.capitalize()}: {percent:.1%}")
        
        report_lines.append(f"  Multilingual Chunks: {lang_analysis.get('multilingual_chunks', 0)}")
        
        report_lines.extend([
            "",
            "KPK Analysis:",
            f"  KPK Documents: {analysis['kpk_analysis']['kpk_documents']}",
            f"  KPK Percentage: {analysis['kpk_analysis']['kpk_percentage']:.1%}",
            f"  Species Mentions: {analysis['kpk_analysis']['protected_species_mentions']}",
            "",
            "Cache Performance:",
            f"  Cache Hits: {embedding_batch.statistics.get('cache_hits', 0)}",
            f"  Cache Misses: {embedding_batch.statistics.get('cache_misses', 0)}",
            f"  Hit Rate: {embedding_batch.statistics.get('cache_hit_rate', 0):.1%}",
        ])
        
        report_lines.append("=" * 60)
        
        return "\n".join(report_lines)


# Utility functions
def create_kpk_embedding_generator(model_name: Optional[str] = None, 
                                 cache_dir: Optional[Path] = None) -> KPKEmbeddingGenerator:
    """Factory function to create KPK embedding generator."""
    return KPKEmbeddingGenerator(model_name, cache_dir)


def generate_and_export_embeddings(chunks: List[Dict[str, Any]], 
                                 output_dir: Union[str, Path],
                                 model_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Convenience function to generate and export embeddings.
    
    Args:
        chunks: Document chunks from 6.4_legal_chunker.py
        output_dir: Directory to save embeddings
        model_name: Optional model name
        
    Returns:
        Dict with results and file paths
    """
    # Create generator
    generator = create_kpk_embedding_generator(model_name)
    
    # Generate embeddings
    embedding_batch = generator.generate_chunk_embeddings(chunks)
    
    # Export embeddings
    file_paths = generator.export_embeddings(embedding_batch, output_dir)
    
    # Generate report
    report = generator.get_embedding_report(embedding_batch)
    
    return {
        "embedding_batch": embedding_batch.to_dict(),
        "file_paths": {k: str(v) for k, v in file_paths.items()},
        "analysis": generator.analyze_embeddings(embedding_batch.embeddings),
        "report": report
    }


# Example usage and testing
if __name__ == "__main__":
    print("=== Testing KPKEmbeddingGenerator ===\n")
    
    # Create sample chunks (output from 6.4_legal_chunker.py)
    sample_chunks = [
        {
            "chunk_id": "chunk_1",
            "text": "Section 27 of KPK Forest Ordinance 2002 imposes a penalty of Rs. 50,000 for unauthorized felling of Deodar trees in reserved forests.",
            "metadata": {
                "document_type": "ordinance",
                "section_info": "Section 27",
                "is_kpk_document": True,
                "species_mentioned": ["deodar"],
                "source_document": "kpk_forest_ordinance_2002.pdf"
            }
        },
        {
            "chunk_id": "chunk_2",
            "text": "دیار کے درختوں کی غیر مجوزہ کٹائی پر جرمانہ لاگو ہوتا ہے۔",
            "metadata": {
                "document_type": "circular",
                "section_info": "Notification 45/2023",
                "is_kpk_document": True,
                "species_mentioned": ["دیار"],
                "source_document": "fd_circular_2023.pdf"
            }
        },
        {
            "chunk_id": "chunk_3",
            "text": "The Range Officer has authority to issue permits for transportation of timber within their jurisdiction.",
            "metadata": {
                "document_type": "rules",
                "section_info": "Rule 15",
                "is_kpk_document": True,
                "officer_mentioned": ["Range Officer"],
                "source_document": "forest_rules_2010.pdf"
            }
        }
    ]
    
    print("Sample Chunks:")
    print("-" * 40)
    for i, chunk in enumerate(sample_chunks):
        print(f"\nChunk {i+1}:")
        print(f"  ID: {chunk['chunk_id']}")
        print(f"  Text: {chunk['text'][:80]}...")
        print(f"  KPK Document: {chunk['metadata'].get('is_kpk_document', False)}")
    
    print("\n" + "=" * 60)
    
    # Create generator
    generator = create_kpk_embedding_generator()
    
    # Generate embeddings
    print("\nGenerating embeddings...")
    embedding_batch = generator.generate_chunk_embeddings(sample_chunks)
    
    print(f"\nEmbedding Generation Complete:")
    print(f"  Total embeddings: {len(embedding_batch.embeddings)}")
    print(f"  Dimension: {embedding_batch.model_config.get('embedding_dimension')}")
    print(f"  Cache hits: {embedding_batch.statistics.get('cache_hits')}")
    print(f"  Cache misses: {embedding_batch.statistics.get('cache_misses')}")
    
    print("\n" + "=" * 60)
    
    # Display embedding report
    report = generator.get_embedding_report(embedding_batch)
    print("\n" + report)
    
    print("\n" + "=" * 60)
    
    # Export embeddings
    print("\nExporting embeddings...")
    output_dir = Path("test_embeddings_output")
    file_paths = generator.export_embeddings(embedding_batch, output_dir)
    
    print(f"\nFiles exported to {output_dir}:")
    for file_type, file_path in file_paths.items():
        print(f"  {file_type}: {file_path}")
    
    print("\n" + "=" * 60)
    print("KPKEmbeddingGenerator Test Complete ✓")
