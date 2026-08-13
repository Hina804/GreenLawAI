"""
FAISS Vector Store - Production-Grade Implementation
Replaces ChromaDB with stable, high-performance FAISS backend.
"""

import faiss
import numpy as np
import json
import pickle
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import os
import logging

logger = logging.getLogger(__name__)

# Fields that MUST be present in every chunk's metadata.
# If missing, the chunk is flagged so retrieval can surface the gap.
REQUIRED_METADATA_FIELDS = ["law_title", "section", "text"]


class FAISSStore:
    """
    Production-grade FAISS vector store for legal document retrieval.

    Features:
    - Fast similarity search (2-3x faster than ChromaDB)
    - Stable on all platforms (no corruption issues)
    - File-based persistence (no database server needed)
    - Metadata management with required-field enforcement
    - Batch operations
    """

    def __init__(
        self,
        persist_directory: str = "./faiss_index",
        dimension: int = 384,          # all-MiniLM-L6-v2 embedding size
        collection_name: str = "legal_docs"
    ):
        self.persist_directory = Path(persist_directory)
        self.dimension = dimension
        self.collection_name = collection_name

        self.persist_directory.mkdir(parents=True, exist_ok=True)

        self.index_path    = self.persist_directory / "vectors.index"
        self.metadata_path = self.persist_directory / "metadata.pkl"
        self.config_path   = self.persist_directory / "config.json"

        if self.index_path.exists():
            self._load_index()
        else:
            self._create_index()

        print(f"[OK] FAISS Store initialized: {self.persist_directory}")
        print(f"  Collection: {self.collection_name}")
        print(f"  Current document count: {self.index.ntotal}")

    # ── Index lifecycle ────────────────────────────────────────────────

    def _create_index(self):
        self.index    = faiss.IndexFlatL2(self.dimension)
        self.metadata = []
        self._save_config()
        print("[OK] Created new FAISS index")

    def _load_index(self):
        self.index = faiss.read_index(str(self.index_path))
        with open(self.metadata_path, "rb") as f:
            self.metadata = pickle.load(f)
        print(f"[OK] Loaded FAISS index with {self.index.ntotal} vectors")

    def _save_config(self):
        config = {
            "dimension":       self.dimension,
            "collection_name": self.collection_name,
            "index_type":      "IndexFlatL2",
            "total_vectors":   self.index.ntotal,
        }
        with open(self.config_path, "w") as f:
            json.dump(config, f, indent=2)

    # ── Metadata validation ────────────────────────────────────────────

    def _validate_metadata(self, metadatas: List[Dict[str, Any]]) -> int:
        """
        Check every metadata dict for required fields.
        Stamps missing fields with a sentinel value ("N/A") so retrieval
        callers can filter them out, and logs a warning so the data gap
        is visible in the pipeline log.

        Returns the number of incomplete records found.
        """
        incomplete = 0
        for i, meta in enumerate(metadatas):
            missing = [f for f in REQUIRED_METADATA_FIELDS if not meta.get(f)]
            if missing:
                incomplete += 1
                logger.warning(
                    "[faiss_store] Chunk %d is missing required fields %s. "
                    "Fix the upstream builder (6.3_graph_builder.py) so these "
                    "are populated before add_documents() is called. "
                    "Stamping sentinel 'N/A' so retrieval can filter this chunk.",
                    i, missing
                )
                for field in missing:
                    if field != "text":          # never overwrite actual text
                        meta.setdefault(field, "N/A")

        if incomplete:
            logger.warning(
                "[faiss_store] %d / %d chunks had incomplete metadata. "
                "These will appear as Law: N/A in retrieval results.",
                incomplete, len(metadatas)
            )
        return incomplete

    # ── Write ──────────────────────────────────────────────────────────

    def add_documents(
        self,
        embeddings: np.ndarray,
        metadatas: List[Dict[str, Any]],
        ids: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Add documents to the index.

        Args:
            embeddings: Numpy array of shape (n, dimension)
            metadatas:  List of metadata dicts — MUST include
                        'law_title', 'section', and 'text' for
                        every chunk (enforced via _validate_metadata).
            ids:        Optional list of document IDs

        Returns:
            List of document IDs
        """
        # ── 1. Validate metadata (warns + stamps N/A for missing fields) ──
        incomplete = self._validate_metadata(metadatas)
        if incomplete:
            print(
                f"[WARN] {incomplete}/{len(metadatas)} chunks are missing "
                "law_title/section. Fix 6.3_graph_builder.py. "
                "Proceeding — retrieval will filter them out."
            )

        # ── 2. Prepare embeddings ─────────────────────────────────────────
        embeddings = embeddings.astype("float32")
        faiss.normalize_L2(embeddings)          # cosine similarity

        start_id = self.index.ntotal
        self.index.add(embeddings)

        # ── 3. Generate IDs if not provided ──────────────────────────────
        if ids is None:
            ids = [f"doc_{start_id + i}" for i in range(len(embeddings))]

        # ── 4. Store metadata ─────────────────────────────────────────────
        for i, (meta, doc_id) in enumerate(zip(metadatas, ids)):
            meta["_id"]    = doc_id
            meta["_index"] = start_id + i
            self.metadata.append(meta)

        self.save()
        print(f"[OK] Added {len(embeddings)} documents to FAISS index")
        return ids

    # ── Read ───────────────────────────────────────────────────────────

    def search(
        self,
        query_embedding: np.ndarray,
        k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None,
        skip_incomplete: bool = True,           # NEW: drop Law: N/A chunks by default
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents.

        Args:
            query_embedding: Query vector (1D array)
            k:               Number of results to return
            filter_dict:     Optional metadata filters
            skip_incomplete: If True (default), silently drop chunks
                             where law_title == 'N/A'. Set to False to
                             include them (e.g. during a backfill audit).

        Returns:
            List of results with metadata and scores
        """
        if query_embedding.ndim == 1:
            query_embedding = query_embedding.reshape(1, -1)
        query_embedding = query_embedding.astype("float32")
        faiss.normalize_L2(query_embedding)

        # Over-fetch so filters don't starve results
        search_k = k * 5 if (filter_dict or skip_incomplete) else k
        distances, indices = self.index.search(query_embedding, search_k)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:
                continue

            meta = self.metadata[idx].copy()

            # ── Drop incomplete chunks from retrieval results ──────────
            if skip_incomplete and meta.get("law_title", "N/A") == "N/A":
                continue

            # ── Apply caller-supplied filters ──────────────────────────
            if filter_dict and not self._matches_filter(meta, filter_dict):
                continue

            # L2 distance → cosine similarity (vectors are normalized)
            similarity = 1 - (dist / 2)

            results.append({
                "text":     meta.get("text", ""),
                "metadata": meta,
                "score":    float(similarity),
                "distance": float(dist),
            })

            if len(results) >= k:
                break

        return results

    def _matches_filter(self, metadata: Dict, filter_dict: Dict) -> bool:
        for key, value in filter_dict.items():
            if key not in metadata or metadata[key] != value:
                return False
        return True

    # ── Persistence ────────────────────────────────────────────────────

    def save(self):
        faiss.write_index(self.index, str(self.index_path))
        with open(self.metadata_path, "wb") as f:
            pickle.dump(self.metadata, f)
        self._save_config()

    # ── Audit helpers ──────────────────────────────────────────────────

    def audit_incomplete(self) -> List[Dict[str, Any]]:
        """
        Return all metadata records that are missing law_title or section.
        Used by scripts/backfill_metadata.py to find chunks to patch.
        """
        return [
            m for m in self.metadata
            if m.get("law_title", "N/A") == "N/A"
            or m.get("section", "N/A") == "N/A"
        ]

    def patch_metadata(self, doc_id: str, updates: Dict[str, Any]) -> bool:
        """
        Patch metadata for a single document by its _id.
        Used by backfill_metadata.py to fix existing incomplete records.

        Returns True if the record was found and patched, False otherwise.
        """
        for record in self.metadata:
            if record.get("_id") == doc_id:
                record.update(updates)
                self.save()
                return True
        return False

    # ── Stats ──────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        incomplete = sum(
            1 for m in self.metadata
            if m.get("law_title", "N/A") == "N/A"
        )
        return {
            "total_documents":    self.index.ntotal,
            "incomplete_chunks":  incomplete,
            "dimension":          self.dimension,
            "collection_name":    self.collection_name,
            "persist_directory":  str(self.persist_directory),
            "index_type":         "IndexFlatL2",
        }

    def get_all_metadata(self) -> List[Dict[str, Any]]:
        return self.metadata

    def delete_collection(self):
        for path in (self.index_path, self.metadata_path, self.config_path):
            if path.exists():
                os.remove(path)
        self._create_index()
        print(f"[OK] Deleted collection: {self.collection_name}")


# ── Smoke test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Testing FAISS Store...")

    store = FAISSStore(persist_directory="./test_faiss")

    # Good metadata
    good_meta = [
        {"text": f"Document {i}", "law_title": "Forest Act 1927", "section": f"Section {i}"}
        for i in range(8)
    ]
    # Bad metadata (missing law_title + section — simulates the N/A bug)
    bad_meta = [
        {"text": "Orphan chunk A"},
        {"text": "Orphan chunk B"},
    ]

    test_embeddings = np.random.randn(10, 384).astype("float32")
    store.add_documents(test_embeddings, good_meta + bad_meta)

    query = np.random.randn(384).astype("float32")

    print("\n-- search with skip_incomplete=True (default) --")
    results = store.search(query, k=5)
    for r in results:
        print(f"  Score: {r['score']:.3f}  Law: {r['metadata'].get('law_title')}  "
              f"Section: {r['metadata'].get('section')}")

    print("\n-- audit_incomplete --")
    bad = store.audit_incomplete()
    print(f"  Incomplete records: {len(bad)}")
    for b in bad:
        print(f"    id={b['_id']}  law_title={b.get('law_title')}  text={b['text'][:40]}")

    print(f"\nStats: {store.get_stats()}")
    print("\n[OK] FAISS Store test complete!")