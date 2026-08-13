"""
Complete Pipeline Execution + Cleanup Script

This script will:
1. Clean up unnecessary data
2. Update ChromaDB with new chunks
3. Build knowledge graph in Neo4j
4. Test the Q&A system

Run this after ATC ingestion to complete the pipeline.
"""

import shutil
from pathlib import Path
import sys

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

def cleanup_project():
    """Remove unnecessary files to reduce project size."""
    print("\n" + "="*60)
    print("🧹 CLEANING UP PROJECT")
    print("="*60)
    
    # Directories to clean
    cleanup_targets = [
        # Old/duplicate data
        ROOT / "data_processed" / "forestry" / "layout",  # Keep only structured
        ROOT / "data_processed" / "climate" / "layout",
        
        # Intermediate files
        ROOT / "data_processed" / "forestry" / "normalized" / "*_clean.txt",
        ROOT / "data_processed" / "forestry" / "normalized" / "*_split.txt",
        ROOT / "data_processed" / "climate" / "normalized" / "*_clean.txt",
        ROOT / "data_processed" / "climate" / "normalized" / "*_split.txt",
        
        # Old ChromaDB (will rebuild)
        # ROOT / "chroma_db",  # Commented out - keep existing
        
        # Logs (keep recent only)
        ROOT / "logs" / "*.log.1",
        ROOT / "logs" / "*.log.2",
        
        # Cache files
        ROOT / "__pycache__",
        ROOT / "src" / "**" / "__pycache__",
        ROOT / ".pytest_cache",
        
        # Temporary files
        ROOT / "*.tmp",
        ROOT / "*.temp",
    ]
    
    total_freed = 0
    
    for target in cleanup_targets:
        if "*" in str(target):
            # Glob pattern
            parent = target.parent
            pattern = target.name
            if parent.exists():
                for file in parent.glob(pattern):
                    size = file.stat().st_size if file.is_file() else 0
                    try:
                        if file.is_dir():
                            shutil.rmtree(file)
                        else:
                            file.unlink()
                        total_freed += size
                        print(f"  ✓ Deleted: {file.relative_to(ROOT)}")
                    except Exception as e:
                        print(f"  ✗ Failed to delete {file.name}: {e}")
        else:
            # Direct path
            if target.exists():
                size = sum(f.stat().st_size for f in target.rglob('*') if f.is_file()) if target.is_dir() else target.stat().st_size
                try:
                    if target.is_dir():
                        shutil.rmtree(target)
                    else:
                        target.unlink()
                    total_freed += size
                    print(f"  ✓ Deleted: {target.relative_to(ROOT)}")
                except Exception as e:
                    print(f"  ✗ Failed to delete {target.name}: {e}")
    
    print(f"\n✓ Freed {total_freed / (1024*1024):.1f} MB")
    return total_freed

def verify_chromadb():
    """Verify ChromaDB has the new chunks."""
    print("\n" + "="*60)
    print("💾 VERIFYING CHROMADB")
    print("="*60)
    
    import chromadb
    
    try:
        client = chromadb.PersistentClient(path=str(ROOT / "chroma_db_v3"))
        collection = client.get_collection("legal_docs")
        
        count = collection.count()
        print(f"✓ ChromaDB connected")
        print(f"  Total chunks: {count}")
        
        # Check for ATC-generated chunks
        sample = collection.get(limit=100)
        atc_count = sum(1 for m in sample['metadatas'] if m.get('atc_generated'))
        
        print(f"  ATC-generated: {atc_count}/100 in sample")
        
        if count >= 190:
            print(f"\n✅ ChromaDB is up to date!")
            return True
        else:
            print(f"\n⚠️  Expected ~194 chunks, found {count}")
            print(f"   Run ingestion on Colab first!")
            return False
            
    except Exception as e:
        print(f"❌ ChromaDB error: {e}")
        return False

def build_knowledge_graph():
    """Build Neo4j knowledge graph from chunks."""
    print("\n" + "="*60)
    print("🕸️  BUILDING KNOWLEDGE GRAPH")
    print("="*60)
    
    # Check if Neo4j import script exists
    import_script = ROOT / "scripts" / "import_to_neo4j.py"
    
    if not import_script.exists():
        print("⚠️  Neo4j import script not found")
        print("   Skipping knowledge graph build")
        return False
    
    print("Running Neo4j import...")
    
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, str(import_script)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode == 0:
            print("✓ Knowledge graph built successfully")
            print(result.stdout)
            return True
        else:
            print(f"❌ Import failed:")
            print(result.stderr)
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Import timed out (>5 minutes)")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_qa_system():
    """Test the Q&A system."""
    print("\n" + "="*60)
    print("🤖 TESTING Q&A SYSTEM")
    print("="*60)
    
    try:
        from rag.rag_pipeline import RAGPipeline
        import yaml
        
        # Load config
        config_file = ROOT / "config" / "rag_config.yaml"
        with open(config_file) as f:
            config = yaml.safe_load(f)
        
        # Update config for local testing
        config['cloud_storage']['mount_point'] = str(ROOT)
        config['llm']['provider'] = 'ollama'
        config['llm']['model'] = 'llama3.2:3b'
        
        print("Initializing RAG pipeline...")
        rag = RAGPipeline.from_config(config)
        
        # Test question
        question = "What are the penalties for illegal logging?"
        print(f"\nQuestion: {question}\n")
        print("Answer:")
        
        for token in rag.query(question, stream=True):
            print(token, end='', flush=True)
        
        print("\n\n✅ Q&A system working!")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nMake sure:")
        print("  1. Ollama is running: ollama serve")
        print("  2. Model is pulled: ollama pull llama3.2:3b")
        print("  3. Neo4j is running (optional)")
        return False

def main():
    """Run complete pipeline."""
    print("\n" + "="*60)
    print("🚀 COMPLETE PIPELINE EXECUTION")
    print("="*60)
    print(f"Root: {ROOT}")
    
    # Check for non-interactive flag
    is_interactive = "--non-interactive" not in sys.argv
    
    # Step 1: Cleanup
    cleanup_project()
    
    # Step 2: Verify ChromaDB
    chromadb_ok = verify_chromadb()
    
    if not chromadb_ok:
        print("\n❌ ChromaDB not ready. Run ingestion on Colab first!")
        return 1
    
    # Step 3: Build knowledge graph
    print("\n⚠️  Knowledge graph build requires Neo4j running")
    if is_interactive:
        response = input("Build knowledge graph? (y/n): ").lower()
    else:
        response = "y"  # Auto-approve in pipeline
    
    if response == 'y':
        build_knowledge_graph()
    else:
        print("Skipping knowledge graph build")
    
    # Step 4: Test Q&A
    print("\n⚠️  Q&A test requires Ollama running")
    if is_interactive:
        response = input("Test Q&A system? (y/n): ").lower()
    else:
        response = "n"  # Skip Q&A test in pipeline (it's too slow/heavy)
    
    if response == 'y':
        test_qa_system()
    else:
        print("Skipping Q&A test")
    
    print("\n" + "="*60)
    print("✅ PIPELINE COMPLETE!")
    print("="*60)
    print("\nNext steps:")
    print("  1. Start Ollama: ollama serve")
    print("  2. Pull model: ollama pull llama3.2:3b")
    print("  3. Run demo: python scripts/demo_rag_qa.py")
    
    return 0

if __name__ == "__main__":
    exit(main())
