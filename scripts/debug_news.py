import sys
sys.path.insert(0, 'e:/GL_AI/src')
import asyncio

# Test 1: Does the planner route news queries correctly?
print("=== PLANNER ROUTING TEST ===")
from agents.orchestrator.planner import TaskPlanner
planner = TaskPlanner()
plan = asyncio.run(planner.create_plan("Search for news reports on forest fire alerts in Hazara"))
for st in plan.sub_tasks:
    print(f"  Step {st['id']}: {st['name']} -> tool={st['tool']}")

# Test 2: Does the web search tool actually return results?
print("\n=== WEB SEARCH TOOL TEST ===")
from tools.search.web_search import WebSearch
ws = WebSearch()
result = asyncio.run(ws.execute({"query": "forest fire alerts Hazara Pakistan 2026"}))
print(f"Status: {result.get('status')}")
print(f"Results count: {len(result.get('results', []))}")
for r in result.get('results', [])[:3]:
    print(f"  - {r.get('title')}: {r.get('snippet', '')[:80]}")
if not result.get('results'):
    print(f"  Note: {result.get('note', 'No note')}")
    print(f"  Full result: {result}")
