import sys
sys.path.insert(0, 'e:/GL_AI/src')
import asyncio

# Test 1: Grazing comparison
from core.penalty_calculator import PenaltyCalculator as P
r = P.analyze_query('fines for unauthorized grazing in Reserved vs Protected forest')
print("=== GRAZING (Reserved vs Protected) ===")
print(P.format_for_ui(r))

# Test 2: Incident date filtering
print("\n=== INCIDENTS (Swat, last 30 days) ===")
from tools.phase2_wrappers.incident_wrapper import IncidentAgent
a = IncidentAgent()
r2 = asyncio.run(a.execute({'query': 'Investigate deforestation alerts in Swat last 30 days'}))
print(f"Count: {r2['count']}, Filter: {r2['date_filter']}")
for e in r2['evidence']:
    print(f"  {e}")
