import logging
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional
from collections import deque

logger = logging.getLogger(__name__)

class EpisodicMemory:
    """
    Remembers conversations, reasoning steps, and incidents.
    Uses a lightweight in-memory store (no ChromaDB dependency).
    """
    
    def __init__(self, collection_name: str = "episodic", max_episodes: int = 500):
        self.collection_name = collection_name
        self.episodes = deque(maxlen=max_episodes)
        logger.info(f"EpisodicMemory initialized (in-memory, max={max_episodes})")

    async def store(self, episode: Dict[str, Any]):
        """Stores an episode with its metadata."""
        doc = episode.get('query') or episode.get('task') or ""
        entry = {
            'id': f"ep_{uuid.uuid4()}",
            'content': doc,
            'timestamp': datetime.now().isoformat(),
            'metadata': {k: v for k, v in episode.items() if isinstance(v, (str, int, float, bool))}
        }
        self.episodes.append(entry)
        logger.debug(f"Stored episode: {doc[:50]}...")

    async def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Finds recent episodes matching the query (simple keyword match)."""
        query_lower = query.lower()
        matches = []
        for ep in reversed(list(self.episodes)):
            if query_lower in ep.get('content', '').lower():
                matches.append(ep)
                if len(matches) >= limit:
                    break
        return matches

    async def get_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieves the most recent episodes."""
        return list(self.episodes)[-limit:]
