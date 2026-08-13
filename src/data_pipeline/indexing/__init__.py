"""
Indexing Package
Vector store creation and management.
"""

from .embedding_generator import EmbeddingGenerator
from .chunking_strategy import LegalDocumentChunker
from .chroma_store import ChromaStore
from .vector_indexer import VectorIndexer

__all__ = [
    'EmbeddingGenerator',
    'LegalDocumentChunker',
    'ChromaStore',
    'VectorIndexer'
]
