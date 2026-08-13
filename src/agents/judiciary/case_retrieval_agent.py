import os
import sys
from typing import List, Dict, Any
from copy import deepcopy

# Add src to path
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from agents.base_agent import BaseAgent
from core.schemas import CanonicalAgentResponse, AudienceType, Citation
from data_pipeline.indexing.faiss_store import FAISSStore
from data_pipeline.indexing.embedding_generator import EmbeddingGenerator
from loguru import logger
from neo4j import GraphDatabase

class CaseRetrievalAgent(BaseAgent):
    """
    Upgraded Phase 4 Judiciary Agent.
    Uses FAISS (Semantic) + Neo4j (Graph) for hybrid precedent retrieval.
    """
    
    def __init__(self, config: Dict[str, Any] = None, component_id: str = "judiciary", llm_manager=None):
        config = config or {}
        super().__init__(
            name="CaseRetrievalAgent",
            component_id=component_id,
            tools=[],
            config=config
        )
        self.llm_manager = llm_manager
        
        # 1. Initialize Vector Store
        self.index_path = config.get("faiss_index_path", "e:/GL_AI/faiss_index_cases")
        self.store = None
        self.embedder = None
        
        # 2. Neo4j Integration
        self.neo4j_uri = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
        self.neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_pass = os.getenv("NEO4J_PASSWORD", "password")
        self.neo4j_driver = None

        try:
            if os.path.exists(self.index_path):
                self.store = FAISSStore(persist_directory=self.index_path, collection_name="court_cases")
                self.embedder = EmbeddingGenerator()
                logger.info(f"Scaled Judiciary Agent loaded FAISS: {self.index_path}")
            
            # Initialize Neo4j driver
            self.neo4j_driver = GraphDatabase.driver(self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_pass))
            logger.info(f"Neo4j Graph Driver initialized for {self.neo4j_uri}")
            
        except Exception as e:
            logger.error(f"Failed to initialize search providers: {e}")

    def _graph_retrieve(self, sections: List[str]) -> List[Dict]:
        """Perform relationship-based search in Neo4j."""
        if not self.neo4j_driver:
            return []
            
        results = []
        try:
            with self.neo4j_driver.session() as session:
                # Find cases sharing similar statutory sections
                query = """
                MATCH (c:CourtCase)-[:CITES_SECTION]->(s:Section)
                WHERE s.id IN $sections
                RETURN c.id as id, c.title as title, c.citation as citation LIMIT 5
                """
                records = session.run(query, sections=sections)
                for record in records:
                    results.append({
                        "case_id": record["id"],
                        "title": record["title"],
                        "citation": record["citation"],
                        "retrieval_mode": "graph_relationship"
                    })
        except Exception as e:
            logger.error(f"Neo4j retrieval failed: {e}")
            
        return results

    async def run(self, query: str, retrieved_chunks: list = None, audience: AudienceType = AudienceType.PROFESSIONAL, context: Dict[str, Any] = None) -> CanonicalAgentResponse:
        logger.info(f"Searching hybrid precedents for: {query}")
        
        # Stage 1: Vector-Based Semantic Retrieval
        results = self._vector_retrieve(query)
        
        # Stage 2: Graph-Based Relationship Retrieval (Optional)
        if context and "sections" in context:
            graph_results = self._graph_retrieve(context["sections"])
            results.extend(graph_results)
        
        # Stage 3: Structural Refinement
        enriched_results = self._enrich_results(results, query)
        
        # Format response
        content = self._format_response(enriched_results, query)
        
        return CanonicalAgentResponse(
            simple_explanation=f"Found {len(enriched_results)} relevant precedents for your inquiry.",
            legal_explanation=content,
            citations=[
                Citation(document=r.get("title", "Unknown Case"), section=r.get("citation", "N/A"), chunk_id=r.get("case_id"))
                for r in enriched_results[:3]
            ],
            agent_name="CaseRetrievalEngine",
            confidence=0.95,
            source_chunks=[r.get("case_id", "Unknown") for r in enriched_results[:3]],
            graph_metadata={"top_cases": enriched_results[:3], "hybrid_mode": True},
            abstain=len(enriched_results) == 0
        )

    def _vector_retrieve(self, query: str) -> List[Dict]:
        if not self.store or not self.embedder:
            return []
        try:
            query_vec = self.embedder.encode_single(query)
            search_results = self.store.search(query_vec, k=5)
            mapped = []
            for r in search_results:
                case = deepcopy(r["metadata"])
                case["similarity_score"] = r["score"]
                case["relevance_score"] = r["score"]
                case["retrieval_mode"] = "semantic_vector"
                mapped.append(case)
            return mapped
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

    def _enrich_results(self, results: List[Dict], query: str) -> List[Dict]:
        filtered = []
        seen = set()
        for r in results:
            cid = r.get("case_id") or r.get("id")
            if cid not in seen:
                r["case_id"] = cid
                filtered.append(r)
                seen.add(cid)
        return filtered

    def _format_response(self, results: List[Dict], query: str) -> str:
        if not results:
            return "No relevant precedents found."
            
        md = f"**[HYBRID SEARCH] Found {len(results)} precedents for:** *\"{query}\"*\n\n"
        for r in results[:3]:
            mode_icon = "🧠" if r.get("retrieval_mode") == "semantic_vector" else "🔗"
            md += f"### {mode_icon} {r.get('title', 'Unknown')} ({r.get('citation', 'N/A')})\n"
            md += f"- **Mode:** {r.get('retrieval_mode', 'N/A')} | **Verdict:** {r.get('verdict', 'N/A')}\n"
            md += f"- **Penalty**: Rs {r.get('penalty_amount_rs', 0):,}\n\n"
            
        return md

    def get_status(self) -> Dict[str, Any]:
        return {
            "component": "judiciary",
            "vector_active": self.store is not None,
            "graph_active": self.neo4j_driver is not None,
            "hybrid_retrieval": True
        }
