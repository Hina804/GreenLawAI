"""
Simple RAG (Retrieval-Augmented Generation) System

A straightforward RAG implementation that:
1. Takes a user question
2. Retrieves relevant chunks from ChromaDB
3. Generates an answer using the context

This is the foundation for the GreenLawAI Q&A system.
"""

import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
import chromadb

# Setup paths
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from indexing.embedding_generator import EmbeddingGenerator

class SimpleRAG:
    """Simple RAG system for legal document Q&A."""
    
    def __init__(
        self,
        chroma_path: str,
        collection_name: str = "legal_docs",
        top_k: int = 5
    ):
        """
        Initialize the RAG system.
        
        Args:
            chroma_path: Path to ChromaDB directory
            collection_name: Name of the collection
            top_k: Number of chunks to retrieve
        """
        self.top_k = top_k
        
        # Initialize embedding generator
        print("Loading embedding model...")
        self.embedder = EmbeddingGenerator()
        
        # Initialize ChromaDB
        print(f"Connecting to ChromaDB at {chroma_path}...")
        self.client = chromadb.PersistentClient(path=chroma_path)
        self.collection = self.client.get_collection(collection_name)
        
        print(f"✓ RAG system initialized")
        print(f"  Collection: {collection_name}")
        print(f"  Total chunks: {self.collection.count()}")
    
    def retrieve(self, query: str, top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Retrieve relevant chunks for a query.
        
        Args:
            query: User question
            top_k: Number of chunks to retrieve (overrides default)
        
        Returns:
            List of retrieved chunks with metadata
        """
        k = top_k or self.top_k
        
        # Generate query embedding
        query_embedding = self.embedder.encode([query])[0]
        
        # Search ChromaDB
        results = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=k
        )
        
        # Format results
        chunks = []
        if results['documents']:
            for i, (doc, metadata, distance) in enumerate(zip(
                results['documents'][0],
                results['metadatas'][0],
                results['distances'][0]
            )):
                chunks.append({
                    'text': doc,
                    'metadata': metadata,
                    'distance': distance,
                    'rank': i + 1
                })
        
        return chunks
    
    def format_context(self, chunks: List[Dict[str, Any]]) -> str:
        """
        Format retrieved chunks into context for LLM.
        
        Args:
            chunks: Retrieved chunks
        
        Returns:
            Formatted context string
        """
        if not chunks:
            return "No relevant information found."
        
        context_parts = []
        for chunk in chunks:
            source = chunk['metadata'].get('source_file', 'Unknown')
            text = chunk['text']
            
            context_parts.append(f"[Source: {source}]\n{text}")
        
        return "\n\n---\n\n".join(context_parts)
    
    def generate_prompt(self, query: str, context: str) -> str:
        """
        Generate a prompt for the LLM.
        
        Args:
            query: User question
            context: Retrieved context
        
        Returns:
            Formatted prompt
        """
        prompt = f"""You are a legal expert assistant specializing in Pakistani forestry and environmental law. Answer the question based ONLY on the provided context from legal documents.

Context from Legal Documents:
{context}

Question: {query}

Instructions:
1. Answer based ONLY on the provided context
2. Cite the source document when possible
3. If the context doesn't contain enough information, say so
4. Be precise and use legal terminology when appropriate
5. Keep your answer concise but complete

Answer:"""
        
        return prompt
    
    def answer(
        self,
        query: str,
        llm_function: Optional[callable] = None,
        return_context: bool = False
    ) -> Dict[str, Any]:
        """
        Answer a question using RAG.
        
        Args:
            query: User question
            llm_function: Optional LLM function (if None, returns context only)
            return_context: Whether to return retrieved chunks
        
        Returns:
            Dictionary with answer and optional context
        """
        # Retrieve relevant chunks
        chunks = self.retrieve(query)
        
        # Format context
        context = self.format_context(chunks)
        
        # Generate prompt
        prompt = self.generate_prompt(query, context)
        
        # Generate answer (if LLM provided)
        if llm_function:
            answer = llm_function(prompt)
        else:
            # Return context only (for testing without LLM)
            answer = f"[Context Retrieved - {len(chunks)} chunks]\n\n{context}"
        
        result = {
            'query': query,
            'answer': answer,
            'num_chunks': len(chunks)
        }
        
        if return_context:
            result['chunks'] = chunks
            result['context'] = context
            result['prompt'] = prompt
        
        return result
    
    def batch_answer(
        self,
        queries: List[str],
        llm_function: Optional[callable] = None
    ) -> List[Dict[str, Any]]:
        """
        Answer multiple questions.
        
        Args:
            queries: List of questions
            llm_function: Optional LLM function
        
        Returns:
            List of answer dictionaries
        """
        return [self.answer(q, llm_function) for q in queries]


def create_ollama_llm(model: str = "llama3.2:3b"):
    """
    Create an Ollama LLM function.
    
    Args:
        model: Ollama model name
    
    Returns:
        LLM function
    """
    try:
        import requests
        
        def ollama_llm(prompt: str) -> str:
            """Call Ollama API."""
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False
                }
            )
            
            if response.status_code == 200:
                return response.json()['response']
            else:
                return f"Error: {response.status_code}"
        
        return ollama_llm
    
    except ImportError:
        print("⚠️  requests library not found. Install with: pip install requests")
        return None


def create_gemini_llm(api_key: Optional[str] = None):
    """
    Create a Gemini LLM function.
    
    Args:
        api_key: Gemini API key (optional, will use env var if not provided)
    
    Returns:
        LLM function
    """
    try:
        import google.generativeai as genai
        import os
        
        # Configure API key
        key = api_key or os.getenv('GEMINI_API_KEY')
        if not key:
            print("⚠️  No Gemini API key found. Set GEMINI_API_KEY environment variable.")
            return None
        
        genai.configure(api_key=key)
        model = genai.GenerativeModel('gemini-pro')
        
        def gemini_llm(prompt: str) -> str:
            """Call Gemini API."""
            response = model.generate_content(prompt)
            return response.text
        
        return gemini_llm
    
    except ImportError:
        print("⚠️  google-generativeai library not found. Install with: pip install google-generativeai")
        return None


# Example usage
if __name__ == "__main__":
    # Initialize RAG
    rag = SimpleRAG(
        chroma_path=str(ROOT / "chroma_db"),
        top_k=3
    )
    
    # Test questions
    test_questions = [
        "What are the penalties for illegal logging?",
        "Who can grant forest permits?",
        "What is the definition of forest produce?",
        "What are the climate change mitigation strategies?",
        "What is the role of the Forest Department?"
    ]
    
    print("\n" + "="*60)
    print("TESTING RAG SYSTEM (Context Only)")
    print("="*60)
    
    for i, question in enumerate(test_questions, 1):
        print(f"\n[{i}/{len(test_questions)}] Question: {question}")
        
        result = rag.answer(question, return_context=True)
        
        print(f"  Retrieved: {result['num_chunks']} chunks")
        print(f"  Top source: {result['chunks'][0]['metadata'].get('source_file', 'Unknown')}")
        print(f"  Distance: {result['chunks'][0]['distance']:.3f}")
        
        # Show snippet
        snippet = result['chunks'][0]['text'][:150]
        print(f"  Snippet: {snippet}...")
    
    print("\n" + "="*60)
    print("✓ RAG SYSTEM WORKING!")
    print("="*60)
    print("\nTo use with LLM:")
    print("  1. Install Ollama: https://ollama.ai")
    print("  2. Run: ollama pull llama3.2:3b")
    print("  3. Use: rag.answer(question, llm_function=create_ollama_llm())")
