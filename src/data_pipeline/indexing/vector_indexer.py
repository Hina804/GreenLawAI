"""
Vector Indexer - Main Orchestrator
Coordinates the entire indexing pipeline.
Updated to use FAISS for stable, production-grade vector storage.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
import sys
import numpy as np
from loguru import logger

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from indexing.embedding_generator import EmbeddingGenerator
from indexing.semantic_chunker import SemanticChunker
from indexing.faiss_store import FAISSStore
from indexing.entity_extractor import EntityExtractor, EntityRegistry
from indexing.clause_segmenter import ClauseSegmenter


class VectorIndexer:
    """
    Main orchestrator for vector indexing pipeline.
    
    Pipeline:
    1. Load structured JSONs
    2. Chunk sections intelligently
    3. Generate embeddings
    4. Store in FAISS with metadata
    """
    
    def __init__(
        self,
        persist_dir: str = "e:\\GL_AI\\data_processed\\faiss_index_unified",
        collection_name: str = "legal_docs",
        max_chunk_size: int = 512,
        embedding_model: str = "all-MiniLM-L6-v2",
        device: str = "cpu",
        enable_entities: bool = True,
        **kwargs
    ):
        """
        Initialize vector indexer.
        """
        # # Backward compatibility for ChromaDB scripts
        # if "chroma_persist_dir" in kwargs:
        #     persist_dir = kwargs["chroma_persist_dir"]
        
        print("="*60)
        print("VECTOR INDEXER INITIALIZATION (FAISS)")
        print("="*60)
        
        # Initialize components
        self.embedding_generator = EmbeddingGenerator(
            model_name=embedding_model,
            device=device
        )
        
        self.chunker = SemanticChunker(
            max_chunk_size=max_chunk_size,
            min_chunk_size=120,
            respect_boundaries=True
        )
        
        self.vector_store = FAISSStore(
            persist_directory=persist_dir,
            collection_name=collection_name
        )
        
        # Initialize entity extractor and registry
        self.enable_entities = enable_entities
        if enable_entities:
            self.entity_extractor = EntityExtractor(
                model_name="en_core_web_sm",
                min_entities_per_chunk=3,
                use_custom_patterns=True,
                enable_post_filtering=True
            )
            self.entity_registry = EntityRegistry()
        else:
            self.entity_extractor = None
            self.entity_registry = None
        
        # Initialize clause segmenter
        self.clause_segmenter = ClauseSegmenter()
        
        print("="*60)
        print("[OK] All components initialized successfully (FAISS Backend)")
        print("="*60)
    
    def index_document(
        self, 
        json_path: str,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """Index a single structured JSON document."""
        if verbose:
            print(f"\n{'='*60}")
            print(f"INDEXING: {Path(json_path).name}")
            print(f"{'='*60}")
        
        # 1. Load structured JSON
        with open(json_path, 'r', encoding='utf-8') as f:
            doc = json.load(f)
        
        # Pull from root (Gap 9 Correction)
        law_title = doc.get('act_title', 'unknown')
        total_chapters = len(doc.get('chapters', []))
        total_sections = sum(len(c.get('sections', [])) for c in doc.get('chapters', []))
        
        if verbose:
            print(f"\nDocument: {law_title}")
            print(f"Chapters: {total_chapters}, Sections: {total_sections}")
        
        # 2. Chunk document
        if verbose:
            print(f"\n[1/3] Chunking sections...")
        
        chunks = self.chunker.chunk_document(
            doc,
            source_file=Path(json_path).name,
            version="v1"
        )
        
        if verbose:
            print(f"      Created {len(chunks)} chunks")
        
        # 3. Process Chunks (Clauses + Entities)
        for chunk in chunks:
            # Clause segmentation
            segmentation = self.clause_segmenter.segment_chunk_with_offsets(
                chunk['text'],
                chunk['metadata']['chunk_id']
            )
            chunk['metadata']['clauses'] = json.dumps(segmentation['clauses']) # Stringify for FAISS/Neo4j compatibility
            chunk['metadata'].update({k: v for k, v in segmentation.items() if k != 'clauses'})
            
            # Entity extraction (Gap 10 Correction)
            if self.enable_entities and self.entity_extractor:
                raw_mentions, raw_types = self.entity_extractor.extract_entities(chunk['text'])
                if verbose and raw_mentions:
                    print(f"      [DEBUG] Extracted {len(raw_mentions)} raw entities")
                
                canonical_mentions = []
                canonical_types = []
                
                for mention, ent_type in zip(raw_mentions, raw_types):
                    # Canonicalize
                    canonical_name, is_confident = self.entity_extractor.canonicalizer.canonicalize(
                        mention, context=chunk['text'][:100]
                    )
                    
                    if is_confident:
                        canonical_mentions.append(canonical_name)
                        canonical_types.append(ent_type)
                        
                        # Register in global registry for Neo4j import
                        self.entity_registry.register_entity(
                            canonical_name=canonical_name,
                            entity_type=ent_type,
                            chunk_id=chunk['metadata']['chunk_id'],
                            original_mention=mention,
                            source_file=Path(json_path).name,
                            context_snippet=chunk['text']
                        )
                
                # Add to chunk metadata
                chunk['metadata']['entity_mentions_raw'] = raw_mentions
                chunk['metadata']['entity_mentions_canonical'] = json.dumps(canonical_mentions)
                chunk['metadata']['entity_types_canonical'] = json.dumps(canonical_types)
                
                if verbose and canonical_mentions:
                    print(f"      [DEBUG] Registered {len(canonical_mentions)} canonical entities")
        
        # 4. Generate embeddings
        if verbose:
            print(f"\n[2/3] Generating embeddings...")
        
        if not chunks:
            return {'total_chunks': 0}
        
        texts = [chunk['text'] for chunk in chunks]
        embeddings = self.embedding_generator.encode(
            texts,
            batch_size=32,
            show_progress=verbose
        )
        
        # 5. Store in FAISS
        if verbose:
            print(f"\n[3/3] Storing in FAISS...")
        
        # Prepare metadata
        metadatas = []
        for chunk in chunks:
            meta = chunk['metadata'].copy()
            meta['text'] = chunk['text'] # Store text in metadata for FAISS retrieval
            metadatas.append(meta)
            
        ids = self.vector_store.add_documents(
            embeddings,
            metadatas
        )
        
        if verbose:
            print(f"      Stored {len(ids)} chunks")
        
        return {
            'law_title': law_title,
            'total_chapters': total_chapters,
            'total_sections': total_sections,
            'total_chunks': len(chunks),
            'chunk_ids': ids[:5]
        }
    


    def query(self, query_text: str, n_results: int = 5, filter_dict: Dict = None) -> Dict:
        """Query the FAISS index and return results with normalized metadata."""
        
        # Generate query embedding
        query_embedding = self.embedding_generator.encode_single(query_text)
        
        # ✅ Use vector_store.search() — it already handles normalization,
        #    filtering, skip_incomplete, and returns clean dicts
        results = self.vector_store.search(
            query_embedding=query_embedding,
            k=n_results,
            filter_dict=filter_dict,
            skip_incomplete=True
        )
        
        if not results:
            logger.warning("[VectorIndexer] No results returned from FAISS search")
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
        
        ids, documents, metadatas, dists = [], [], [], []
        
        for r in results:
            meta = r["metadata"]
            text = r["text"]
            chunk_id = meta.get("chunk_id", meta.get("_id", "unknown"))
            
            ids.append(chunk_id)
            documents.append(text)
            metadatas.append(meta)
            dists.append(r["distance"])
        
        return {
            "ids":       [ids],
            "documents": [documents],
            "metadatas": [metadatas],
            "distances": [dists]
        }



    def index_directory(
        self,
        directory: str,
        pattern: str = "*_structured.json",
        verbose: bool = True
    ) -> List[Dict[str, Any]]:
        """Index all documents in a directory matching a pattern."""
        dir_path = Path(directory)
        if not dir_path.exists():
            print(f"[ERR] Directory not found: {directory}")
            return []
            
        json_files = list(dir_path.glob(pattern))
        if verbose:
            print(f"\nFound {len(json_files)} documents to index in {directory}")
            
        results = []
        for json_file in json_files:
            try:
                result = self.index_document(str(json_file), verbose=verbose)
                results.append(result)
            except Exception as e:
                print(f"[ERR] Failed to index {json_file.name}: {e}")
                
        return results

    def export_entity_registry(self, output_path: str):
        """Export entity registry for Neo4j."""
        if self.entity_registry:
            self.entity_registry.export_for_neo4j(output_path)
            print(f"[OK] Exported entity registry to {output_path}")
        else:
            print("[WARN] Entity extraction is disabled. No registry to export.")

    def export_chunks_for_neo4j(self, output_path: str):
        """Export all chunks for Neo4j import."""
        print(f"Exporting chunks for Neo4j to {output_path}...")
        
        chunks_data = {
            "chunks": [],
            "total": 0
        }
        
        # Pull metadata from FAISS store
        if hasattr(self.vector_store, 'get_all_metadata'):
            metadata_list = self.vector_store.get_all_metadata()
            
            # Neo4j import expects 'text' to be at the same level as 'metadata' or 'content'
            # Based on neo4j_import.py, it expects a list of dicts with 'text' and 'metadata'
            for meta in metadata_list:
                chunk_entry = {
                    "text": meta.get("text", ""),
                    "chunk_id": meta.get("chunk_id"),
                    "law_title": meta.get("law_title"),
                    "section": meta.get("section"),
                    "section_id": meta.get("section_id"),
                    "document_id": meta.get("document_id"),
                    "token_count": meta.get("token_count", 0),
                    "source_file": meta.get("source_file"),
                    "version": meta.get("version"),
                    "entity_mentions_canonical": meta.get("entity_mentions_canonical", []),
                    "entity_types_canonical": meta.get("entity_types_canonical", []),
                    "clauses": meta.get("clauses", []),
                    "metadata": meta # Keep full metadata for safety
                }
                chunks_data["chunks"].append(chunk_entry)
            
            chunks_data["total"] = len(chunks_data["chunks"])
            
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(chunks_data, f, indent=2, ensure_ascii=False)
        print(f"[OK] Exported {chunks_data['total']} chunks to {output_path}")

    def get_stats(self) -> Dict[str, Any]:
        """Get indexing statistics."""
        count = 0
        if hasattr(self.vector_store, 'metadata'):
            count = len(self.vector_store.metadata)
            
        return {
            "total_documents": count,
            "collection_name": self.vector_store.collection_name,
            "persist_directory": self.vector_store.persist_directory
        }

if __name__ == "__main__":
    # Test
    indexer = VectorIndexer(persist_dir="./test_faiss_idx")
    print("VectorIndexer initialized with FAISS backend.")
