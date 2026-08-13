"""
Migration Script: ChromaDB → FAISS
Migrates all indexed legal documents from ChromaDB exports to FAISS.
"""

import json
import numpy as np
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from indexing.faiss_store import FAISSStore
from indexing.embedding_generator import EmbeddingGenerator


def load_chunks_export(export_path: str = "chunks_export.json"):
    """Load chunks from export file."""
    print(f"\n[1/4] Loading chunks from {export_path}...")
    
    with open(export_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    chunks = data.get('chunks', [])
    print(f"[OK] Loaded {len(chunks)} chunks")
    
    return chunks


def prepare_data_for_faiss(chunks):
    """Prepare chunks for FAISS indexing."""
    print(f"\n[2/4] Preparing data for FAISS...")
    
    texts = []
    metadatas = []
    embeddings_list = []
    
    for chunk in chunks:
        # Extract text
        text = chunk.get('text', '')
        texts.append(text)
        
        # Extract metadata
        metadata = chunk.get('metadata', {})
        metadata['text'] = text  # Store text in metadata for retrieval
        metadatas.append(metadata)
        
        # Extract embedding if available
        embedding = chunk.get('embedding')
        if embedding:
            embeddings_list.append(embedding)
    
    print(f"[OK] Prepared {len(texts)} documents")
    print(f"  Texts: {len(texts)}")
    print(f"  Metadata: {len(metadatas)}")
    print(f"  Embeddings: {len(embeddings_list)}")
    
    return texts, metadatas, embeddings_list


def generate_missing_embeddings(texts, existing_embeddings):
    """Generate embeddings for texts that don't have them."""
    print(f"\n[3/4] Checking embeddings...")
    
    if len(existing_embeddings) == len(texts):
        print(f"[OK] All {len(texts)} chunks already have embeddings")
        return np.array(existing_embeddings, dtype='float32')
    
    print(f"[!] Generating embeddings for {len(texts) - len(existing_embeddings)} chunks...")
    
    # Initialize embedding generator
    embedding_gen = EmbeddingGenerator(model_name="all-MiniLM-L6-v2", device="cpu")
    
    # Generate all embeddings
    all_embeddings = []
    batch_size = 32
    
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        batch_embeddings = embedding_gen.encode(batch, show_progress=False)
        all_embeddings.extend(batch_embeddings)
        
        if (i + batch_size) % 100 == 0:
            print(f"  Progress: {min(i+batch_size, len(texts))}/{len(texts)}")
    
    print(f"[OK] Generated {len(all_embeddings)} embeddings")
    return np.array(all_embeddings, dtype='float32')


def migrate_to_faiss(chunks, faiss_dir: str = "faiss_index"):
    """Migrate chunks to FAISS."""
    print(f"\n[4/4] Migrating to FAISS...")
    
    # Prepare data
    texts, metadatas, existing_embeddings = prepare_data_for_faiss(chunks)
    
    # Generate/load embeddings
    embeddings = generate_missing_embeddings(texts, existing_embeddings)
    
    # Create FAISS store
    print(f"\nCreating FAISS index in {faiss_dir}...")
    store = FAISSStore(
        persist_directory=faiss_dir,
        dimension=384,  # all-MiniLM-L6-v2
        collection_name="legal_docs"
    )
    
    # Add documents in batches
    batch_size = 100
    total_added = 0
    
    for i in range(0, len(embeddings), batch_size):
        batch_embeddings = embeddings[i:i+batch_size]
        batch_metadata = metadatas[i:i+batch_size]
        
        store.add_documents(batch_embeddings, batch_metadata)
        total_added += len(batch_embeddings)
        
        print(f"  Migrated: {total_added}/{len(embeddings)}")
    
    # Verify
    stats = store.get_stats()
    print(f"\n[OK] Migration complete!")
    print(f"  Total documents in FAISS: {stats['total_documents']}")
    print(f"  Storage: {stats['persist_directory']}")
    
    return store


def verify_migration(store, chunks):
    """Verify migration was successful."""
    print(f"\n[VERIFY] Testing FAISS index...")
    
    # Test search with first chunk
    if chunks:
        test_text = chunks[0].get('text', '')
        test_embedding = chunks[0].get('embedding')
        
        if test_embedding:
            results = store.search(np.array(test_embedding, dtype='float32'), k=3)
            
            print(f"[OK] Search test successful")
            print(f"  Query: {test_text[:100]}...")
            print(f"  Results: {len(results)}")
            for i, r in enumerate(results[:3]):
                print(f"    {i+1}. Score: {r['score']:.3f}, Law: {r['metadata'].get('law_title', 'Unknown')}")
    
    print(f"\n[OK] Verification complete!")


def main():
    """Main migration function."""
    print("="*70)
    print("CHROMADB TO FAISS MIGRATION")
    print("="*70)
    
    # Check if export file exists
    export_path = Path("chunks_export.json")
    if not export_path.exists():
        print(f"[ERR] Export file not found: {export_path}")
        print("Please run the indexing pipeline first to generate chunks_export.json")
        return
    
    # Load chunks
    chunks = load_chunks_export(str(export_path))
    
    if not chunks:
        print("[ERR] No chunks found in export file")
        return
    
    # Migrate to FAISS
    store = migrate_to_faiss(chunks, faiss_dir="faiss_index")
    
    # Verify
    verify_migration(store, chunks)
    
    print("\n" + "="*70)
    print("[OK] MIGRATION SUCCESSFUL!")
    print("="*70)
    print("\nYour system is now using FAISS (stable, production-grade)")
    print(f"Total documents: {len(chunks)}")
    print(f"Storage location: faiss_index/")
    print("\nNext step: Update UI to use FAISS")


if __name__ == "__main__":
    main()
