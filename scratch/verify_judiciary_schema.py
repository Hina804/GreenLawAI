import asyncio
import os
import sys
from typing import Dict, Any

# Setup path
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from core.schemas import AudienceType, CanonicalAgentResponse
from agents.judiciary.case_retrieval_agent import CaseRetrievalAgent
from agents.judiciary.legal_reasoning_agent import LegalReasoningAgent
from agents.judiciary.judgment_prediction_agent import JudgmentPredictionAgent
from agents.judiciary.evidence_analyzer_agent import EvidenceAnalyzerAgent
from agents.judiciary.bail_analyzer_agent import BailAnalyzerAgent

async def test_agent_schema(agent_class, name, **run_kwargs):
    print(f"Testing {name}...")
    try:
        agent = agent_class({})
        # Mocking run slightly if needed, but let's try direct call with empty/mock data
        res = await agent.run(**run_kwargs)
        print(f"  ✅ {name} passed Pydantic validation!")
        print(f"  Summary: {res.simple_explanation[:50]}...")
    except Exception as e:
        print(f"  ❌ {name} failed: {e}")

async def test_agent_empty_run(agent_class, name, **run_kwargs):
    print(f"Testing {name} (Abstain Case)...")
    try:
        agent = agent_class({})
        res = await agent.run(**run_kwargs)
        if res.abstain:
            print(f"  ✅ {name} correctly ABSTAINED!")
        else:
            print(f"  ❌ {name} failed to abstain on empty data.")
    except Exception as e:
        print(f"  ❌ {name} failed: {e}")

async def main():
    print("--- Judiciary Agent Schema Diagnostic ---")
    
    # Normal Case Tests
    await test_agent_schema(CaseRetrievalAgent, "CaseRetrievalAgent", query="test")
    
    # Empty/Error Case Tests (Must Abstain)
    await test_agent_empty_run(LegalReasoningAgent, "LegalReasoningAgent", 
                           query="test", retrieved_chunks=[], audience=AudienceType.PROFESSIONAL,
                           context={"precedents": []})
                           
    await test_agent_empty_run(JudgmentPredictionAgent, "JudgmentPredictionAgent",
                           query="test", retrieved_chunks=[], audience=AudienceType.PROFESSIONAL,
                           context={"precedents": []})
                           
    await test_agent_schema(EvidenceAnalyzerAgent, "EvidenceAnalyzerAgent",
                           query="test", retrieved_chunks=[], audience=AudienceType.PROFESSIONAL,
                           context={"incident_data": {"location": "Test Loc", "date": "2024-01-01"}})
                           
    await test_agent_schema(BailAnalyzerAgent, "BailAnalyzerAgent",
                           query="test", retrieved_chunks=[], audience=AudienceType.PROFESSIONAL,
                           context={"offender_profile": {"is_repeat_offender": False}, "precedents": []})

if __name__ == "__main__":
    asyncio.run(main())
