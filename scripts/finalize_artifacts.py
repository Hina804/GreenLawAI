import os
import json
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path("E:/GL_AI/src")))
sys.path.insert(0, str(Path("E:/GL_AI/src/data_pipeline")))

import importlib.util

def dynamic_import(module_name: str, class_name: str, package: str):
    base_dir = Path("E:/GL_AI/src/data_pipeline")
    package_path = package.replace(".", "/")
    file_path = base_dir / package_path / f"{module_name}.py"
    full_module_name = f"{package}.{module_name.replace('.', '_')}"
    spec = importlib.util.spec_from_file_location(full_module_name, str(file_path))
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = package
    spec.loader.exec_module(mod)
    return getattr(mod, class_name)

try:
    KPKGraphBuilder = dynamic_import("6.3_graph_builder", "KPKGraphBuilder", "preprocessing_pipeline.phase_6_graph_construction")
except Exception as e:
    print(f"Error importing modules: {e}")
def finalize_artifacts():
    print("Starting finalization of vector and graph artifacts...")
    docs_dir = Path("E:/GL_AI/data_processed/new_documents")
    
    # We will use the builder to export CSVs and update FAISS
    builder = KPKGraphBuilder()
    
    doc_count = 0
    
    for doc_folder in docs_dir.iterdir():
        if not doc_folder.is_dir():
            continue
            
        p6_dir = doc_folder / "phase_6"
        p6_json = p6_dir / "phase_6_6_graph_construction.json"
        
        if p6_json.exists():
            with open(p6_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # data structure: {"data": {"nodes": [...], "relationships": [...]}}
            graph_data = data.get("data", {})
            nodes = graph_data.get("nodes", [])
            rels = graph_data.get("relationships", [])
            
            # 1. Generate CSV Exports
            export_dir = p6_dir / "graph_export"
            export_dir.mkdir(exist_ok=True)
            
            if nodes:
                pd.DataFrame(nodes).to_csv(export_dir / "nodes.csv", index=False)
            if rels:
                pd.DataFrame(rels).to_csv(export_dir / "relationships.csv", index=False)
                
            # 2. Extract Chunks for FAISS
            # For the 18 new docs, we need text from phase_1
            p1_json = doc_folder / "phase_1" / "phase_1_1_extraction.json"
            raw_text = ""
            if p1_json.exists():
                with open(p1_json, 'r', encoding='utf-8') as f:
                    raw_text = json.load(f).get("data", {}).get("raw_text", "")
            
            if raw_text and builder.indexer and builder.embedder:
                chunks = [{"text": raw_text[:2000], "metadata": {"doc_id": doc_folder.name}}]
                try:
                    emb = builder.embedder.generate_chunk_embeddings(chunks)
                    emb_array = np.array([e.embedding for e in emb.embeddings], dtype=np.float32)
                    builder.indexer.index_chunks(chunks, emb_array)
                except Exception as e:
                    print(f"[{doc_folder.name}] FAISS Indexing Error: {e}")
            
            doc_count += 1
            print(f"Finalized artifacts for {doc_folder.name}")
            
    # Save the global FAISS index
    if builder.indexer:
        faiss_dir = Path("E:/GL_AI/data_processed/faiss_index_new")
        faiss_dir.mkdir(exist_ok=True)
        try:
            # Depending on FAISS Indexer architecture
            if hasattr(builder.indexer, 'index_manager'):
                builder.indexer.index_manager.save_index(faiss_dir)
            elif hasattr(builder.indexer, 'save'):
                builder.indexer.save(faiss_dir)
            print(f"Successfully saved global FAISS index to {faiss_dir}")
        except Exception as e:
            print(f"Error saving FAISS index: {e}")
            
    print(f"Finalization complete for {doc_count} documents.")

if __name__ == "__main__":
    finalize_artifacts()
