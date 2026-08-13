import logging
from typing import Dict, Any, Optional, List
from memory.episodic import EpisodicMemory
from memory.semantic import SemanticMemory
from memory.procedural import ProceduralMemory
from memory.working import WorkingMemory
from memory.contacts import ContactMemory

# Unified memory fabric
class MemoryFabric:
    """
    Unified memory system for the Agentic AI phase.
    Supports Episodic, Semantic, Procedural, Working, and Contact memory.
    """
    
    def __init__(self):
        self.episodic = EpisodicMemory()
        self.semantic = SemanticMemory()
        self.procedural = ProceduralMemory()
        self.working = WorkingMemory()
        self.contacts = ContactMemory()
        
    async def remember(self, query: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Cross-memory retrieval to provide the agent with relevant context.
        """
        # Search episodic for past similar tasks
        past_episodes = await self.episodic.search(query)
        
        # Search semantic for facts
        facts = await self.semantic.search(query)
        
        return {
            "past_episodes": past_episodes,
            "facts": facts,
            "working_context": self.working.context
        }

    async def learn(self, interaction: Dict[str, Any]):
        """
        Store interaction data across memory types for future learning.
        """
        # Store in episodic
        await self.episodic.store(interaction)
        
        # Update working memory
        if "context" in interaction:
            self.working.bulk_update(interaction["context"])
            
        logger.info("Interaction stored in Memory Fabric.")
