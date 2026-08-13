import logging
from typing import Dict, Any, List
from tools.base_tool import BaseTool
from tools.legal_tools import LegalSearchTool

logger = logging.getLogger(__name__)

class ForestLawSearch(BaseTool):
    """
    Agentic Tool for searching KP Forest Laws.
    Wraps the existing LegalSearchTool to provide hybrid GraphRAG results.
    """
    def __init__(self, config: Dict = None):
        super().__init__(
            name="search_forest_laws",
            description="Searches Pakistani forest laws, mandates, and penalties. Use this for legal grounded questions."
        )
        self.legal_search_component = LegalSearchTool()
        self.config = config or {
            "CHROMA_PERSIST_DIR": "e:/GL_AI/data/chroma_db",
            "NEO4J_URI": "bolt://localhost:7687",
            "NEO4J_USER": "neo4j",
            "NEO4J_PASSWORD": "password" # Placeholder
        }
        self._initialized = False

    async def _ensure_loaded(self):
        if not self._initialized:
            await self.legal_search_component.load(self.config)
            self._initialized = True

    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parameters:
        - query: The law-related question or keyword.
        - k: Number of results (default 5).
        """
        query = parameters.get("query")
        if not query:
            return {"error": "No query provided for search_forest_laws."}

        k = parameters.get("k", 5)
        
        try:
            await self._ensure_loaded()
            result = await self.legal_search_component.execute(query=query, k=k)
            return {
                "results": result.get("results", []),
                "count": result.get("count", 0),
                "source": "KP Forest Law Database (GraphRAG)"
            }
        except Exception as e:
            logger.error(f"Error in ForestLawSearch: {e}")
            return {"error": str(e)}
