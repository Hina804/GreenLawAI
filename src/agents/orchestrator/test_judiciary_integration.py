import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from agents.orchestrator.react_core import ReActAgent
from core.schemas import AudienceType

async def test_judiciary_integration():
    print("Testing Judiciary Integration in Orchestrator...")
    
    agent = ReActAgent() # uses default mock LLM logic in TaskPlanner
    
    # Query that should trigger judicial keywords
    task = "What is the likely verdict and bail eligibility for a tree cutting case in Swat?"
    
    print(f"Task: {task}")
    
    # 1. Test Planner directly
    plan = await agent.planner.create_plan(task)
    print(f"Planned Tools: {[t['name'] for t in plan.sub_tasks]}")
    
    judicial_steps = [t for t in plan.sub_tasks if t['tool'] == "judiciary_specialist"]
    
    if judicial_steps:
        print(f"✅ SUCCESS: Planner correctly identified judicial mission with {len(judicial_steps)} specialized steps.")
        for step in judicial_steps:
             print(f"   - Triggered Action: {step.get('action')}")
    else:
        print("❌ FAILURE: Planner did not trigger judiciary_specialist tool.")

if __name__ == "__main__":
    asyncio.run(test_judiciary_integration())
