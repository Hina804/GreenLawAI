from typing import Dict, Any, Optional, List
from loguru import logger
from core.contracts import BasePipelineComponent
from retrieval.graph_rag_retriever import GraphRAGRetriever

class LegalSearchTool(BasePipelineComponent):
    """
    GreenLawAI Legal Search Tool
    Registry-Compatible (Phase 3)
    """

    def __init__(self, component_id: str = "retrieval_tool"):
        super().__init__(component_id)
        self.name = "legal_search"
        self.description = (
            "Search legal provisions, penalties, forestry laws, statutes, "
            "and regulations using hybrid GraphRAG retrieval."
        )
        self.retriever = None

    async def load(self, config: Dict[str, Any]) -> bool:
        """Lifecycle: Dependency Injection / Initialization."""
        try:
            if "retriever" in config:
                self.retriever = config["retriever"]
            else:
                kwargs = {}
                if config.get("NEO4J_URI"): kwargs["neo4j_uri"] = config["NEO4J_URI"]
                if config.get("NEO4J_USER"): kwargs["neo4j_user"] = config["NEO4J_USER"]
                if config.get("NEO4J_PASSWORD"): kwargs["neo4j_password"] = config["NEO4J_PASSWORD"]
                if config.get("CHROMA_PERSIST_DIR"): kwargs["chroma_persist_dir"] = config["CHROMA_PERSIST_DIR"]
                
                self.retriever = GraphRAGRetriever(**kwargs)
            self._is_loaded = True
            logger.info(f"[LegalSearchTool] {self.component_id} loaded.")
            return True
        except Exception as e:
            logger.error(f"[LegalSearchTool] Failed to load retriever: {e}")
            return False

    async def unload(self) -> bool:
        """Lifecycle: Shutdown."""
        self._is_loaded = False
        return True

    async def execute(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute legal search.
        """
        if not self._is_loaded or not self.retriever:
            raise RuntimeError(f"[LegalSearchTool] Component {self.component_id} not loaded.")

        if not query or not isinstance(query, str):
            raise ValueError("LegalSearchTool.execute(): query must be a non-empty string")

        k = int(kwargs.get("k", 5))

        try:
            results = await self.retriever.hybrid_search(query=query, k=k)
        except Exception as e:
            logger.error(f"[LegalSearchTool] Hybrid search error: {e}")
            return {
                "tool": self.name,
                "query": query,
                "status": "error",
                "error": str(e),
                "results": [],
                "count": 0
            }

        return {
            "tool": self.name,
            "query": query,
            "status": "success",
            "results": results,
            "count": len(results),
            "metadata": {
                "k": k,
                "domain": "legal",
                "version": "1.0"
            }
        }

    def schema(self) -> Dict[str, Any]:
        """
        Tool schema for agent planners / tool routers.
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "query": {
                    "type": "string",
                    "required": True,
                    "description": "Natural language legal query"
                },
                "k": {
                    "type": "integer",
                    "required": False,
                    "default": 5,
                    "description": "Number of retrieval results"
                }
            }
        }