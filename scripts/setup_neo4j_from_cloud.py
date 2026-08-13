"""
Setup Neo4j from Cloud Storage
Imports chunks and entities from cloud storage to Neo4j.
"""

import sys
import os
from pathlib import Path
import yaml

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from rag.cloud_storage import CloudStorageManager
from indexing.neo4j_import import import_to_neo4j

def main():
    print("\n" + "="*70)
    print("  NEO4J IMPORT FROM CLOUD STORAGE")
    print("="*70)
    
    # Load configuration
    config_path = "config/rag_config.yaml"
    if not os.path.exists(config_path):
        print(f"\n❌ Configuration file not found: {config_path}")
        return
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Initialize cloud storage manager
    print("\n📁 Initializing cloud storage...")
    cloud_config = config.get('cloud_storage', {})
    cloud = CloudStorageManager(
        provider=cloud_config.get('provider', 'gdrive'),
        mount_point=cloud_config.get('mount_point'),
        auto_detect=False
    )
    
    # Validate artifacts
    print("\n🔍 Validating cloud artifacts...")
    validation = cloud.validate_artifacts(['entity_registry', 'chunks_export'])
    
    if not all(validation.values()):
        print("\n❌ Missing required artifacts:")
        for artifact, exists in validation.items():
            if not exists:
                print(f"  - {artifact}")
        print("\n⚠ Run: scripts/copy_artifacts_to_cloud.bat")
        return
    
    print("✓ All artifacts found")
    
    # Get file paths
    entity_registry_path = cloud.get_path('entity_registry')
    chunks_export_path = cloud.get_path('chunks_export')
    
    print(f"\n📄 Entity Registry: {entity_registry_path}")
    print(f"📄 Chunks Export: {chunks_export_path}")
    
    # Get Neo4j configuration
    neo4j_config = config.get('neo4j', {})
    uri = neo4j_config.get('uri', 'bolt://localhost:7687')
    user = neo4j_config.get('user', 'neo4j')
    password = neo4j_config.get('password', 'password')
    
    print(f"\n🔗 Connecting to Neo4j: {uri}")
    
    # Import to Neo4j
    try:
        print("\n" + "-"*70)
        print("IMPORTING TO NEO4J")
        print("-"*70)
        
        import_to_neo4j(
            neo4j_uri=uri,
            username=user,
            password=password,
            entity_registry_path=entity_registry_path,
            chunks_export_path=chunks_export_path,
            batch_size_entities=100,
            batch_size_chunks=50
        )
        
        print("\n" + "="*70)
        print("  ✅ IMPORT COMPLETE!")
        print("="*70)
        
        print("\n📊 Summary:")
        print("  - Entities imported from cloud storage")
        print("  - Chunks imported from cloud storage")
        print("  - Relationships created")
        print("  - Neo4j database ready")
        
        print("\n🎯 Next Steps:")
        print("  1. Set OpenAI API key: set OPENAI_API_KEY=your-key")
        print("  2. Test RAG Q&A: python scripts/demo_rag_qa.py")
        
    except ImportError:
        print("\n❌ Error: neo4j package not installed")
        print("Install with: pip install neo4j")
    except Exception as e:
        print(f"\n❌ Error during import: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
