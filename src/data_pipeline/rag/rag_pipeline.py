"""
RAG Pipeline
Integrates GraphRAG retrieval with LLM generation for Q&A.
"""

import sys
from pathlib import Path
from typing import Generator, Optional, Dict, Any

# Add src to path
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

from data_pipeline.rag.cloud_storage import CloudStorageManager
from data_pipeline.rag.llm_manager import LLMManager
from data_pipeline.rag.prompts import build_full_prompt, DEFAULT_SYSTEM_PROMPT
from retrieval.graph_rag_retriever import GraphRAGRetriever


class RAGPipeline:
    """
    End-to-end RAG pipeline for legal Q&A.
    
    Flow:
    1. Validate cloud artifacts
    2. Initialize GraphRAG retriever (from cloud)
    3. Retrieve relevant chunks
    4. Assemble context
    5. Generate answer with LLM
    6. Format citations
    """
    
    def __init__(
        self,
        cloud_manager: CloudStorageManager,
        llm_manager: LLMManager,
        neo4j_uri: str = "bolt://localhost:7687",
        neo4j_user: str = "neo4j",
        neo4j_password: str = "password",
        top_k: int = 5,
        min_score: float = 0.3,
        system_prompt: Optional[str] = None,
        show_scores: bool = True
    ):
        """
        Initialize RAG pipeline.
        
        Args:
            cloud_manager: Cloud storage manager
            llm_manager: LLM manager
            neo4j_uri: Neo4j connection URI
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
            top_k: Number of chunks to retrieve
            min_score: Minimum relevance score
            system_prompt: Custom system prompt (uses default if None)
            show_scores: Show relevance scores in context
        """
        self.cloud = cloud_manager
        self.llm = llm_manager
        self.top_k = top_k
        self.min_score = min_score
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        self.show_scores = show_scores
        
        # Security hard-fail for default password
        if neo4j_password == "password":
            raise RuntimeError(
                "\n[SECURITY] Default Neo4j password detected!\n"
                "For Pillar 4, you MUST explicitly set your password in rag_config.yaml or via environment variables.\n"
                "This is a safety gate to ensure you are not using production defaults in development.\n"
                "If using the 'bypass_auth' logic, please set it explicitly."
            )
        
        # Validate essential runtime artifacts only
        print("\n[CHECK] Validating runtime artifacts...")
        validation = self.cloud.validate_artifacts(required=["chroma_db"])
        
        if not all(validation.values()):
            missing = [k for k, v in validation.items() if not v]
            raise RuntimeError(
                f"[ERR] Missing cloud artifacts: {', '.join(missing)}\n"
                f"[!] Run Colab ingestion pipeline first!\n"
                f"[NOTE] See: colab/ingestion_pipeline.ipynb"
            )
        
        print("[OK] All cloud artifacts validated")
        
        # Initialize GraphRAG retriever from cloud paths
        print("\n[INIT] Initializing GraphRAG retriever...")
        self.retriever = GraphRAGRetriever(
            chroma_persist_dir=self.cloud.get_path("chroma_db"),
            neo4j_uri=neo4j_uri,
            neo4j_user=neo4j_user,
            neo4j_password=neo4j_password
        )
        
        print("[OK] RAG Pipeline ready")
    
    def query(
        self,
        question: str,
        stream: bool = True,
        return_chunks: bool = False
    ) -> Generator[str, None, None]:
        """
        Answer a question using RAG.
        
        Args:
            question: User's question
            stream: Stream response token-by-token
            return_chunks: Return retrieved chunks at the end
        
        Yields:
            Response tokens and citations
        """
        # 1. Retrieve relevant chunks safely across sync/async contexts
        import asyncio
        from loguru import logger
        
        def run_async(coro):
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(lambda: asyncio.run(coro))
                    return future.result()
            else:
                return loop.run_until_complete(coro)

        try:
            chunks = run_async(self.retriever.hybrid_search(question, k=self.top_k))
        except Exception as e:
            logger.error(f"Error in hybrid search during RAG pipeline query: {e}")
            chunks = []
        
        # Filter by minimum score
        filtered_chunks = [c for c in chunks if c.get('final_score', 0) >= self.min_score]
        
        # RELAXATION FALLBACK: If no chunks pass the high bar, dynamically lower threshold
        if not filtered_chunks and chunks:
            relaxed_score = max(0.15, self.min_score * 0.5)
            filtered_chunks = [c for c in chunks if c.get('final_score', 0) >= relaxed_score]
            logger.info(f"[RELAXATION] No chunks passed {self.min_score}. Lowered threshold to {relaxed_score}. Retrieved {len(filtered_chunks)} chunks.")
            
        # QUERY SIMPLIFICATION FALLBACK: If still no chunks, retry with stop-words removed
        if not filtered_chunks:
            stop_words = {"what", "is", "are", "the", "under", "for", "of", "in", "a", "an", "does", "do", "how", "can", "who", "define", "meaning"}
            words = [w for w in question.lower().split() if w not in stop_words and len(w) > 2]
            if words:
                simplified_query = " ".join(words)
                logger.info(f"[FALLBACK] Retrying with simplified query: '{simplified_query}'")
                try:
                    chunks = run_async(self.retriever.hybrid_search(simplified_query, k=self.top_k))
                    filtered_chunks = [c for c in chunks if c.get('final_score', 0) >= 0.15]
                except Exception as ex:
                    logger.error(f"[FALLBACK] Simplified query search failed: {ex}")
        
        chunks = filtered_chunks
        
        if not chunks:
            yield "I don't have enough information to answer this question. "
            yield "No relevant sections were found in the legal documents."
            return
        
        # 2. Build prompt
        prompt = build_full_prompt(
            chunks,
            question,
            system_prompt=self.system_prompt,
            show_scores=self.show_scores
        )
        
        # 3. Generate answer
        for token in self.llm.generate(prompt, stream=stream):
            yield token
        
        # 4. Return chunks if requested
        if return_chunks:
            yield "\n\n[DEBUG] Retrieved chunks:\n"
            for i, chunk in enumerate(chunks, 1):
                yield f"{i}. Score: {chunk.get('final_score', 0):.3f} - {chunk.get('text', '')[:100]}...\n"
    
    def query_simple(self, question: str) -> str:
        """
        Non-streaming query (returns complete answer).
        
        Args:
            question: User's question
        
        Returns:
            Complete answer with citations
        """
        return "".join(self.query(question, stream=False))
    
    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> 'RAGPipeline':
        """
        Create RAG pipeline from configuration dict.
        
        Args:
            config: Configuration dictionary (from YAML)
        
        Returns:
            RAGPipeline instance
        """
        # Initialize cloud manager
        cloud_config = config.get('cloud_storage', {})
        cloud = CloudStorageManager(
            provider=cloud_config.get('provider', 'gdrive'),
            mount_point=cloud_config.get('mount_point')
        )
        
        # Initialize LLM manager
        llm = LLMManager.from_config(config)
        
        # Get other settings
        neo4j_config = config.get('neo4j', {})
        retrieval_config = config.get('retrieval', {})
        prompts_config = config.get('prompts', {})
        
        # Custom system prompt handling removed in v2.2 (unified prompt)
        system_prompt = None
        
        return cls(
            cloud_manager=cloud,
            llm_manager=llm,
            neo4j_uri=neo4j_config.get('uri', 'bolt://localhost:7687'),
            neo4j_user=neo4j_config.get('user', 'neo4j'),
            neo4j_password=neo4j_config.get('password', 'password'),
            top_k=retrieval_config.get('top_k', 5),
            min_score=retrieval_config.get('min_score', 0.3),
            system_prompt=system_prompt,
            show_scores=prompts_config.get('show_scores', True)
        )


if __name__ == "__main__":
    # Test
    import yaml
    
    with open("config/rag_config.yaml") as f:
        config = yaml.safe_load(f)
    
    rag = RAGPipeline.from_config(config)
    
    question = "What are the powers of a Forest Officer?"
    print(f"\nQuestion: {question}\n")
    print("Answer:")
    for token in rag.query(question):
        print(token, end='', flush=True)
    print()
