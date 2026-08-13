import logging
import os
import chromadb
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class LessonLearner:
    """
    Manages the storage and retrieval of 'lessons' found during reflection.
    Uses ChromaDB to perform semantic search over past failures and corrections.
    """
    def __init__(self, persist_dir: str = "e:/GL_AI/data/memory/chroma_lessons"):
        self.persist_dir = persist_dir
        os.makedirs(os.path.dirname(persist_dir), exist_ok=True)
        
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name="agent_lessons",
            metadata={"hnsw:space": "cosine"}
        )

    def save_lesson(self, query: str, lesson: str, metadata: Dict[str, Any] = None):
        """
        Stores a semantic lesson linked to the original query.
        """
        lesson_id = f"lesson_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        doc_metadata = {
            "query": query,
            "timestamp": datetime.now().isoformat(),
            **(metadata or {})
        }
        
        self.collection.add(
            documents=[lesson],
            metadatas=[doc_metadata],
            ids=[lesson_id]
        )
        logger.info(f"[LessonLearner] Saved lesson: {lesson_id}")

    def get_relevant_lessons(self, query: str, k: int = 3) -> List[str]:
        """
        Retrieves the top k lessons most semantically similar to the current query.
        """
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=k
            )
            
            lessons = results.get("documents", [[]])[0]
            if lessons:
                logger.info(f"[LessonLearner] Retrieved {len(lessons)} relevant lessons for query.")
            return lessons
        except Exception as e:
            logger.error(f"[LessonLearner] Error retrieving lessons: {e}")
            return []

    def clear_lessons(self):
        """Wipes the lesson database."""
        self.client.delete_collection("agent_lessons")
        self.collection = self.client.get_or_create_collection("agent_lessons")
        logger.warning("[LessonLearner] Lesson database cleared.")
