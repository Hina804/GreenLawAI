import os
import sys
import json
from datetime import datetime, timedelta

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from data.court_schema import CourtCase
from data.case_ingestor import CaseIngestor
from knowledge.evolution import evolution_engine

def test_knowledge_evolution():
    print("Testing Knowledge Evolution & Versioning System...")
    
    test_db = "e:/GL_AI/data/knowledge/test_cases.json"
    os.makedirs(os.path.dirname(test_db), exist_ok=True)
    
    # 1. Create a case with old verification date
    old_date = (datetime.now() - timedelta(days=200)).strftime("%Y-%m-%d")
    case1 = CourtCase(
        case_id="KPK-2024-EVO",
        title="Test Heritage Tree Protection",
        court_level="Forest Tribunal",
        court_name="Abbottabad",
        judgment_date="2024-01-01",
        citation="2024 FT 01",
        offense_category="Illegal Cutting",
        offense_details="Cutting ancient Deodar",
        location="Galiyat",
        verdict="Guilty",
        penalty_type="Fine",
        judgment_summary="Protection of heritage trees is mandatory."
    )
    case1.metadata.last_verified = old_date
    
    # Save to file
    with open(test_db, "w", encoding="utf-8") as f:
        json.dump([case1.dict()], f, indent=4)
        
    print("1. Old case created and saved.")

    # 2. Test Staleness Detection
    print("2. Testing Staleness Detection...")
    stale_entries = evolution_engine.scan_knowledge_base(test_db)
    if stale_entries and stale_entries[0]["status"] == "STALE":
        print(f"SUCCESS: Case flagged as STALE (Age: {stale_entries[0]['age']} days)")
    else:
        print("FAILURE: Case not flagged as STALE correctly.")

    # 3. Test Versioning via Ingestion
    print("3. Testing Automated Versioning...")
    # Change content of the same case
    case1_updated = case1.copy()
    case1_updated.penalty_amount_rs = 50000 
    
    ingestor = CaseIngestor(data_dir="e:/GL_AI/data/knowledge")
    ingestor.cases = [case1_updated]
    ingestor.save_cases_to_json(test_db)
    
    # Verify new version
    with open(test_db, "r", encoding="utf-8") as f:
        updated_data = json.load(f)
        new_case = updated_data[0]
        
    if new_case["metadata"]["version"] == "1.1":
        print("SUCCESS: Automated version incremented to 1.1")
        print(f"Lineage: {new_case['metadata']['lineage']}")
    else:
        print(f"FAILURE: Version not incremented (Current: {new_case['metadata']['version']})")

    # 4. Verify Archival
    archive_dir = "e:/GL_AI/data/knowledge/archive"
    archives = [f for f in os.listdir(archive_dir) if "KPK-2024-EVO_v1.0" in f]
    if archives:
        print(f"SUCCESS: Old version v1.0 archived: {archives[0]}")
    else:
        print("FAILURE: Old version snapshot not found in archive.")

if __name__ == "__main__":
    test_knowledge_evolution()
    # Cleanup test file
    # if os.path.exists("e:/GL_AI/data/knowledge/test_cases.json"):
    #     os.remove("e:/GL_AI/data/knowledge/test_cases.json")
