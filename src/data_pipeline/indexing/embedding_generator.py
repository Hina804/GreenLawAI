"""
Embedding Generator
Wraps sentence-transformers/all-MiniLM-L6-v2 for generating embeddings.
"""

from typing import List, Union
import numpy as np
from sentence_transformers import SentenceTransformer


class EmbeddingGenerator:
    """
    Generates embeddings using all-MiniLM-L6-v2 model.
    
    Model Specs:
    - Dimensions: 384
    - Max sequence length: 256 tokens
    - Speed: ~3000 sentences/sec on CPU
    """
    
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2', device: str = 'cpu'):
        """
        Initialize embedding model.
        
        Args:
            model_name: HuggingFace model identifier
            device: 'cpu' or 'cuda'
        """
        print(f"Loading embedding model: {model_name}...")
        self.model = SentenceTransformer(model_name, device=device)
        self.dimension = self.model.get_sentence_embedding_dimension()
        print(f"[OK] Model loaded. Embedding dimension: {self.dimension}")
    
    def encode(
        self, 
        texts: Union[str, List[str]], 
        batch_size: int = 32,
        show_progress: bool = True
    ) -> np.ndarray:
        """
        Generate embeddings for text(s).
        
        Args:
            texts: Single text or list of texts
            batch_size: Batch size for encoding
            show_progress: Show progress bar
            
        Returns:
            numpy array of embeddings (N x 384)
        """
        if isinstance(texts, str):
            texts = [texts]
        
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            convert_to_numpy=True
        )
        
        return embeddings
    
    def encode_single(self, text: str) -> np.ndarray:
        """
        Generate embedding for a single text (faster, no batching).
        
        Args:
            text: Input text
            
        Returns:
            numpy array of shape (384,)
        """
        return self.model.encode(text, convert_to_numpy=True)
    
    def get_dimension(self) -> int:
        """Get embedding dimension."""
        return self.dimension


if __name__ == "__main__":
    # Test
    generator = EmbeddingGenerator()
    
    # Test single text
    text = "Section 1: Short title and extent"
    embedding = generator.encode_single(text)
    print(f"\nSingle text embedding shape: {embedding.shape}")
    print(f"First 5 values: {embedding[:5]}")
    
    # Test batch
    texts = [
        "This Act may be called the Forest Act, 1927",
        "It extends to the whole of Pakistan",
        "Penalty for illegal logging"
    ]
    embeddings = generator.encode(texts, show_progress=False)
    print(f"\nBatch embeddings shape: {embeddings.shape}")
