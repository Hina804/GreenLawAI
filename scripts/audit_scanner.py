import os
import json
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DATA_PROCESSED = Path("e:/GL_AI/data_processed/documents")
OUTPUT_FILE = Path("e:/GL_AI/data_processed/comprehensive_audit_results.json")

def get_json_data(file_path):
    if not file_path.exists():
        return None
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error reading {file_path}: {e}")
        return None

def audit():
    if not DATA_PROCESSED.exists():
        logger.error(f"Directory not found: {DATA_PROCESSED}")
        return

    doc_dirs = sorted([d for d in DATA_PROCESSED.iterdir() if d.is_dir()])
    logger.info(f"Found {len(doc_dirs)} documents to audit.")
    
    audit_results = {
        "summary": {
            "total_documents": len(doc_dirs),
            "total_chunks": 0,
            "total_entities": 0,
            "total_sections": 0,
            "total_faiss": 0,
            "total_text_length": 0
        },
        "documents": {}
    }

    for doc_dir in doc_dirs:
        doc_id = doc_dir.name
        logger.info(f"Auditing {doc_id}...")
        
        metrics = {
            "metadata_complete": False,
            "text_length": 0,
            "section_count": 0,
            "entity_count": 0,
            "chunk_count": 0,
            "avg_chunk_size": 0,
            "has_faiss": False,
            "has_graph_nodes": False
        }

        # Phase 0: Metadata
        p0_meta = doc_dir / "phase_0" / "phase_0_0_2_metadata.json"
        meta_data = get_json_data(p0_meta)
        if meta_data:
            metrics["metadata_complete"] = all(meta_data.get(k) and meta_data.get(k) != "unknown" for k in ["document_type", "jurisdiction"])

        # Phase 1: Extraction
        p1_summary = doc_dir / "phase_1" / "phase_1_extraction_summary.json"
        p1_data = get_json_data(p1_summary)
        if p1_data:
            text = p1_data.get("full_text") or p1_data.get("raw_text") or p1_data.get("native_text") or p1_data.get("extracted_text")
            metrics["text_length"] = len(text) if text else 0

        # Phase 3: Sections
        p3_sections = doc_dir / "phase_3" / "phase_3_3_4_sections.json"
        p3_data = get_json_data(p3_sections)
        if p3_data:
            sections = p3_data.get("sections", [])
            metrics["section_count"] = len(sections)

        # Phase 4: Entities
        p4_entities = doc_dir / "phase_4" / "phase_4_4_2_entities.json"
        p4_data = get_json_data(p4_entities)
        if p4_data:
            entities = p4_data.get("validated_entities", [])
            metrics["entity_count"] = len(entities)

        # Phase 6: Chunks & Graph
        p6_chunks = doc_dir / "phase_6" / "phase_6_6_4_chunks.json"
        p6_data = get_json_data(p6_chunks)
        if p6_data:
            chunks = p6_data.get("chunks", []) if isinstance(p6_data, dict) else p6_data
            metrics["chunk_count"] = len(chunks)
            if chunks:
                # Try chunk_text if content is missing
                metrics["avg_chunk_size"] = sum(len(c.get("chunk_text", c.get("content", ""))) for c in chunks) / len(chunks)

        faiss_dir = doc_dir / "phase_6" / "faiss_index"
        metrics["has_faiss"] = faiss_dir.exists() and (any(faiss_dir.glob("*.index")) or any(faiss_dir.glob("*.faiss")))

        p6_mapped = doc_dir / "phase_6" / "phase_6_6_2_mapped.json"
        p6_mapped_data = get_json_data(p6_mapped)
        if p6_mapped_data:
             nodes = p6_mapped_data.get("nodes", [])
             metrics["has_graph_nodes"] = len(nodes) > 0
             metrics["graph_node_count"] = len(nodes)

        audit_results["documents"][doc_id] = metrics
        
        # Update Global Summary
        audit_results["summary"]["total_chunks"] += metrics["chunk_count"]
        audit_results["summary"]["total_entities"] += metrics["entity_count"]
        audit_results["summary"]["total_sections"] += metrics["section_count"]
        audit_results["summary"]["total_faiss"] += 1 if metrics["has_faiss"] else 0
        audit_results["summary"]["total_text_length"] += metrics["text_length"]

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(audit_results, f, indent=2)
    
    logger.info(f"Audit complete. Results saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    audit()
