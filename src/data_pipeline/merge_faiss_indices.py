"""
merge_faiss_indices.py
Combines the baseline vector index with the new manually-grounded vector index
into a single unified FAISS retrieval database.
"""

import sys
import pickle
import json
import faiss
import numpy as np
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("MergeFAISS")

BASE_INDEX_DIR    = Path("E:/GL_AI/data_processed/faiss_index")
NEW_INDEX_DIR     = Path("E:/GL_AI/data_processed/faiss_index_new")
UNIFIED_INDEX_DIR = Path("E:/GL_AI/data_processed/faiss_index_unified")


def load_baseline(base_dir: Path):
    """Load the original baseline FAISS index + metadata list."""
    index_path = base_dir / "vectors.index"
    meta_path  = base_dir / "metadata.pkl"
    config_path = base_dir / "config.json"

    if not index_path.exists() or not meta_path.exists():
        raise FileNotFoundError(
            f"Baseline index files not found in {base_dir}. "
            "Expected: vectors.index and metadata.pkl"
        )

    logger.info(f"Loading baseline FAISS index from {base_dir} ...")
    index = faiss.read_index(str(index_path))
    with open(meta_path, "rb") as f:
        meta = pickle.load(f)

    config = {}
    if config_path.exists():
        with open(config_path, "r") as f:
            config = json.load(f)

    logger.info(f"  Baseline: {index.ntotal} vectors, dim={index.d}")
    return index, meta, config


def load_new_index(new_dir: Path):
    """Load the newly-built KPK FAISS index + chunk registry."""
    index_path = new_dir / "faiss_index.bin"
    reg_path   = new_dir / "chunk_registry.pkl"

    if not index_path.exists() or not reg_path.exists():
        raise FileNotFoundError(
            f"New index files not found in {new_dir}. "
            "Expected: faiss_index.bin and chunk_registry.pkl"
        )

    logger.info(f"Loading new manual index from {new_dir} ...")
    index = faiss.read_index(str(index_path))
    with open(reg_path, "rb") as f:
        reg_data = pickle.load(f)

    registry = reg_data.get("chunk_registry", {})
    logger.info(f"  New index: {index.ntotal} vectors, dim={index.d}")
    return index, registry


def reconstruct_vectors(index: faiss.Index) -> np.ndarray:
    """Safely reconstruct all vectors from a FAISS flat index."""
    try:
        vecs = index.reconstruct_n(0, index.ntotal)
        return np.array(vecs, dtype="float32")
    except Exception as e:
        raise RuntimeError(
            f"Could not reconstruct vectors — index must be a flat (non-quantised) type. "
            f"Error: {e}"
        )


def align_new_chunk(chunk_obj, offset_index: int, doc_index: int) -> dict:
    """Convert a chunk registry entry to the baseline metadata list format."""
    text_content  = ""
    metadata_dict = {}
    chunk_id      = f"manual_{doc_index}"

    if isinstance(chunk_obj, dict):
        text_content  = chunk_obj.get("text", chunk_obj.get("chunk_text", ""))
        metadata_dict = chunk_obj.get("metadata", {})
        chunk_id      = chunk_obj.get("chunk_id", chunk_id)
    elif hasattr(chunk_obj, "text"):
        text_content  = chunk_obj.text
        metadata_dict = getattr(chunk_obj, "metadata", {})
        chunk_id      = getattr(chunk_obj, "chunk_id", chunk_id)

    return {
        "text":     text_content,
        "id":       chunk_id,
        "_id":      chunk_id,
        "metadata": metadata_dict,
        "_index":   offset_index,
        "_source":  "manual_corrections",
    }


def main():
    UNIFIED_INDEX_DIR.mkdir(parents=True, exist_ok=True)

    # ── 1. Load both indices ──────────────────────────────────────────────────
    base_index, base_meta, base_config = load_baseline(BASE_INDEX_DIR)
    new_index,  new_registry           = load_new_index(NEW_INDEX_DIR)

    # Dimension sanity check
    if base_index.d != new_index.d:
        raise ValueError(
            f"Dimension mismatch! Baseline={base_index.d}, New={new_index.d}. "
            "Both indices must use the same embedding model."
        )
    dim = base_index.d

    # ── 2. Reconstruct & combine vectors ─────────────────────────────────────
    logger.info("Reconstructing vectors from both binary indices ...")
    base_vecs = reconstruct_vectors(base_index)
    new_vecs  = reconstruct_vectors(new_index)

    combined = np.vstack([base_vecs, new_vecs]).astype("float32")
    logger.info(f"Combined vector matrix: {combined.shape}  "
                f"({base_index.ntotal} baseline + {new_index.ntotal} new)")

    # ── 3. Merge metadata lists ───────────────────────────────────────────────
    logger.info("Merging metadata registries ...")
    combined_meta = []

    # Re-index baseline metadata
    for i, entry in enumerate(base_meta):
        if isinstance(entry, dict):
            entry["_index"] = i
            combined_meta.append(entry)
        else:
            # Fallback for non-dict entries (dataclass / namedtuple)
            combined_meta.append({
                "text":     getattr(entry, "text", ""),
                "id":       getattr(entry, "id", f"base_{i}"),
                "_id":      getattr(entry, "id", f"base_{i}"),
                "metadata": getattr(entry, "metadata", {}),
                "_index":   i,
                "_source":  "baseline",
            })

    start_offset = len(base_meta)
    for i in range(new_index.ntotal):
        chunk_obj = new_registry.get(i, {})
        aligned   = align_new_chunk(chunk_obj, start_offset + i, i)
        combined_meta.append(aligned)

    logger.info(f"Total metadata records: {len(combined_meta)}")

    # ── 4. Build unified IndexFlatIP (inner-product / cosine after L2-norm) ──
    logger.info("Building unified IndexFlatIP database ...")
    unified_index = faiss.IndexFlatIP(dim)   # inner product → cosine after normalisation

    faiss.normalize_L2(combined)
    unified_index.add(combined)

    logger.info(f"Unified index built: {unified_index.ntotal} vectors total.")

    # ── 5. Save everything ────────────────────────────────────────────────────
    logger.info(f"Saving unified database to {UNIFIED_INDEX_DIR} ...")

    faiss.write_index(unified_index, str(UNIFIED_INDEX_DIR / "vectors.index"))
    logger.info("  vectors.index saved ✓")

    with open(UNIFIED_INDEX_DIR / "metadata.pkl", "wb") as f:
        pickle.dump(combined_meta, f, protocol=pickle.HIGHEST_PROTOCOL)
    logger.info("  metadata.pkl saved ✓")

    unified_config = {
        "dimension":      dim,
        "collection_name":"legal_docs_unified",
        "index_type":     "IndexFlatIP",
        "metric":         "cosine",
        "total_vectors":  unified_index.ntotal,
        "baseline_vectors": base_index.ntotal,
        "new_vectors":    new_index.ntotal,
        "normalize":      True,
    }
    with open(UNIFIED_INDEX_DIR / "config.json", "w") as f:
        json.dump(unified_config, f, indent=2)
    logger.info("  config.json saved ✓")

    # ── 6. Quick sanity check ─────────────────────────────────────────────────
    logger.info("\n── Sanity Check ──")
    logger.info(f"  Baseline vectors : {base_index.ntotal}")
    logger.info(f"  New vectors      : {new_index.ntotal}")
    logger.info(f"  Unified total    : {unified_index.ntotal}  "
                f"(expected {base_index.ntotal + new_index.ntotal})")
    assert unified_index.ntotal == base_index.ntotal + new_index.ntotal, \
        "Vector count mismatch after merge!"
    logger.info("  Count assertion  : ✓ PASSED")

    logger.info("\nStep 3 Complete! ✓")
    logger.info(f"Consolidated retrieval database ready with "
                f"{unified_index.ntotal:,} vectors at {UNIFIED_INDEX_DIR}")


if __name__ == "__main__":
    main()
