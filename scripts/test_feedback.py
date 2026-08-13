import os
import sys
import json
from datetime import datetime

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from data.intelligence_audit import audit_trail
from data.dispatch_manager import dispatch_manager

def test_feedback_loop():
    print("Testing Field Ranger Feedback Loop...")
    
    cluster_id = "test_feedback_123"
    
    # 1. Simulate a dispatch log
    print("1. Logging a simulated dispatch...")
    audit_trail.log_decision(
        cluster_id=cluster_id,
        action="DISPATCHED",
        reasoning="Test dispatch for feedback loop verification",
        cluster_details={"lat": 34.1, "lon": 73.1}
    )
    
    # 2. Update feedback
    print("2. Updating feedback as 'CORRECT'...")
    success = audit_trail.update_feedback(
        cluster_id=cluster_id,
        rating="CORRECT",
        notes="Ground team confirmed illegal logging at coordinates."
    )
    
    if not success:
        print("Error updating feedback.")
        return

    # 3. Verify persistence
    with open(audit_trail.log_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    matches = [d for d in data.get("decisions", []) if d["cluster_id"] == cluster_id]
    if matches and "field_reality" in matches[-1]:
        print("SUCCESS: Feedback correctly persisted in audit trail.")
        print(f"Stored Notes: {matches[-1]['field_reality']['notes']}")
    else:
        print("FAILURE: Feedback not found in audit trail.")

    # 4. Test reliability logic
    print("4. Testing sector reliability calculation...")
    reliability = dispatch_manager.get_sector_reliability()
    print(f"Reliability Stats: {reliability}")

if __name__ == "__main__":
    test_feedback_loop()
