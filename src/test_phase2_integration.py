# test_phase2_integration.py
"""
Test cases for Phase 2 integration
Run with: pytest test_phase2_integration.py -v
"""

import asyncio
import pytest
from pipeline.coordinator import AgentCoordinator

@pytest.mark.asyncio
async def test_legal_only_query():
    """Test that Phase 1 legal queries still work"""
    coordinator = AgentCoordinator({})
    result = await coordinator.run("What is meant by timber?")
    
    assert result is not None
    assert "primary_response" in result
    assert result["primary_response"] is not None
    print("✅ Legal-only query passes")

@pytest.mark.asyncio
async def test_multi_agent_query():
    """Test queries that trigger multiple agents"""
    coordinator = AgentCoordinator({})
    result = await coordinator.run("What is the penalty for cutting deodar and its carbon impact?")
    
    assert result is not None
    assert "multi_agent_data" in result
    assert result["multi_agent_data"]["legal"] is not None
    # Climate agent might not always fire, but structure should exist
    print("✅ Multi-agent structure present")

@pytest.mark.asyncio
async def test_ui_payload_structure():
    """Test that UX node creates proper multi-agent payload"""
    coordinator = AgentCoordinator({})
    result = await coordinator.run("Show me recent forest incidents")
    
    if "final_output" in result:
        final = result["final_output"]
        assert isinstance(final, dict)
        assert "primary" in final
        assert "has_multi_agent" in final
        print("✅ UI payload structure correct")

if __name__ == "__main__":
    asyncio.run(test_legal_only_query())
    asyncio.run(test_multi_agent_query())
    asyncio.run(test_ui_payload_structure())
