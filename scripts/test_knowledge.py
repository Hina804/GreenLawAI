
import sys
import os
import asyncio
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from knowledge.knowledge_evolution import KnowledgeEvolutionSystem, KnowledgeVersionControl

async def test_knowledge_flow():
    print("Testing Knowledge Evolution System...")
    
    # 1. Initialize
    test_storage = "e:/GL_AI/data/test_knowledge"
    kvc = KnowledgeVersionControl(storage_path=test_storage)
    kes = KnowledgeEvolutionSystem()
    kes.version_control = kvc # Inject test KVC
    
    # 2. Create Doc Version
    doc = {"id": "law_001", "title": "Forest Act 2002", "content": "Original text"}
    version_id = kvc.create_version(doc, source="manual_entry")
    print(f"✅ Created version: {version_id}")
    
    # 3. Create Updated Version
    doc["content"] = "Amended text 2026"
    version_id_2 = kvc.create_version(doc, source="amendment")
    print(f"✅ Created version 2: {version_id_2}")
    
    # Check history file exists
    hist_path = f"{test_storage}/law_001_versions.json"
    if os.path.exists(hist_path):
        print("✅ Version history file found.")
    else:
        print("❌ Version history missing.")

    # 4. Test Aging Logic
    knowledge_base = [
        {"id": "doc1", "title": "New Doc", "last_verified": datetime.now().isoformat()},
        {"id": "doc2", "title": "Old Doc", "last_verified": (datetime.now() - timedelta(days=200)).isoformat()},
        {"id": "doc3", "title": "Ancient Doc", "last_verified": (datetime.now() - timedelta(days=400)).isoformat()}
    ]
    
    results = await kes.validate_knowledge_freshness(knowledge_base)
    print("\nValidation Results:")
    for res in results:
        print(f" - {res['title']}: {res['status']} ({res['action']})")
        
    expected_stale = [r for r in results if r['status'] == 'stale']
    if len(expected_stale) == 1:
        print("✅ Correctly identified 1 stale document.")
    else:
        print(f"❌ Expected 1 stale doc, found {len(expected_stale)}")

    # Cleanup
    import shutil
    try:
        shutil.rmtree(test_storage)
        print("✅ Test storage cleaned up.")
    except Exception as e:
        print(f"⚠️ Cleanup failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_knowledge_flow())
