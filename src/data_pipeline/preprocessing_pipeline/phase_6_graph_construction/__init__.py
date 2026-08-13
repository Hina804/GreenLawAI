import importlib.util
from pathlib import Path
import sys

def load_numeric(file_name, class_name):
    base_dir = Path(__file__).parent
    file_path = base_dir / f"{file_name}.py"
    if not file_path.exists():
        return None
    sanitized_name = file_name.replace(".", "_")
    spec = importlib.util.spec_from_file_location(sanitized_name, str(file_path))
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = __name__
    spec.loader.exec_module(mod)
    
    if isinstance(class_name, list):
        return [getattr(mod, c, None) for c in class_name]
    return getattr(mod, class_name, None)

# 6.1
items_6_1 = ["KPKGraphSchema", "NodeLabel", "RelationshipType"]
loaded_6_1 = load_numeric("graph_schema_kpk", items_6_1)
if loaded_6_1:
    KPKGraphSchema, NodeLabel, RelationshipType = loaded_6_1

# 6.2
items_6_2 = ["KPKGraphMapper", "GraphMapping"]
loaded_6_2 = load_numeric("6.2_graph_mapper", items_6_2)
if loaded_6_2:
    KPKGraphMapper, GraphMapping = loaded_6_2

# 6.3
items_6_3 = ["KPKGraphBuilder", "GraphConstructionResult"]
loaded_6_3 = load_numeric("6.3_graph_builder", items_6_3)
if loaded_6_3:
    KPKGraphBuilder, GraphConstructionResult = loaded_6_3

# 6.4
items_6_4 = ["LegalChunker", "LegalChunk"]
loaded_6_4 = load_numeric("6.4_legal_chunker", items_6_4)
if loaded_6_4:
    LegalChunker, LegalChunk = loaded_6_4

# 6.5
items_6_5 = ["KPKEmbeddingGenerator", "ChunkEmbedding"]
loaded_6_5 = load_numeric("6.5_embedding_generator", items_6_5)
if loaded_6_5:
    EmbeddingGenerator, ChunkEmbedding = loaded_6_5

# 6.6
items_6_6 = ["FAISSIndexManager", "IndexedChunk", "SearchResult", "FAISSConfig"]
loaded_6_6 = load_numeric("6.6_faiss_indexer", items_6_6)
if loaded_6_6:
    FAISSIndexer, IndexedChunk, SearchResult, FAISSConfig = loaded_6_6
    VectorIndex = IndexedChunk # Alias for pipeline compatibility

# 6.7
items_6_7 = ["Neo4jLinkManager", "HybridLink"]
loaded_6_7 = load_numeric("6.7_hybrid_linker", items_6_7)
if loaded_6_7:
    HybridLinker, NodeVectorLink = loaded_6_7

# 6.8
# 6.8
items_6_8 = ["Neo4jCSVExporter", "ExportNode", "ExportRelationship"]
loaded_6_8 = load_numeric("6.8_neo4j_exporter", items_6_8)
if loaded_6_8:
    Neo4jExporter, ExportNode, ExportRelationship = loaded_6_8

