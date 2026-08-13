import logging
import uuid
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
import os

try:
    import chromadb
    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False

logger = logging.getLogger(__name__)

class SemanticMemory:
    """
    Stores structured knowledge, facts, and generalized rules.
    Uses ChromaDB for fact retrieval.
    """
    
def __init__(self, collection_name: str = "semantic", persist_dir: str = None):
    if persist_dir is None:
        persist_dir = os.path.join(os.path.dirname(__file__), "semantic_data")
    self.persist_dir = persist_dir
    os.makedirs(self.persist_dir, exist_ok=True)
    
    if HAS_CHROMADB:
        try:
            self.client = chromadb.PersistentClient(path=self.persist_dir)
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"SemanticMemory initialized at {persist_dir}")
        except Exception as e:
            logger.error(f"Failed to initialize SemanticMemory ChromaDB: {e}")
            self.collection = None
    else:
        logger.warning("chromadb not installed. SemanticMemory running in MOCK mode.")
        self.collection = None
    
    async def store_fact(self, fact_text: str, source: str = "agent_reasoning", tags: List[str] = None):
        """
        Stores a generalized fact.
        """
        if not self.collection:
            return

        metadata = {
            "source": source,
            "created_at": datetime.now().isoformat(),
            "tags": json.dumps(tags or [])
        }
        
        try:
            self.collection.add(
                documents=[fact_text],
                metadatas=[metadata],
                ids=[f"fact_{uuid.uuid4()}"]
            )
            logger.debug(f"Fact stored: {fact_text[:50]}...")
        except Exception as e:
            logger.error(f"Error storing fact: {e}")

    async def query_knowledge(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieves knowledge related to a query.
        """
        if not self.collection:
            return []

        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=limit
            )
            
            formatted = []
            if results['documents']:
                for i in range(len(results['documents'][0])):
                    formatted.append({
                        'fact': results['documents'][0][i],
                        'metadata': results['metadatas'][0][i]
                    })
            return formatted
        except Exception as e:
            logger.error(f"Error querying semantic memory: {e}")
            return []
