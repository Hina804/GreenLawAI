"""
Export Neo4j-ready chunks from faiss_index_unified WITHOUT modifying data_processed.

Reads:  data_processed/faiss_index_unified/metadata.pkl
Writes: chunks_export_unified.json  (repo root by default)

Does NOT re-run phase 6 or change anything under data_processed/documents or new_documents.
"""
from __future__ import annotations

import argparse
import json
import pickle
import sys
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FAISS_DIR = ROOT / "data_processed" / "faiss_index_unified"
DEFAULT_OUTPUT = ROOT / "chunks_export_unified.json"


def _inner(meta: Dict[str, Any]) -> Dict[str, Any]:
    inner = meta.get("metadata")
    if isinstance(inner, dict):
        # Some new-index rows nest again under metadata.metadata
        if isinstance(inner.get("metadata"), dict):
            return {**inner.get("metadata", {}), **{k: v for k, v in inner.items() if k != "metadata"}}
        return inner
    return {}


def normalize_faiss_record(record: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Map one unified-FAISS metadata row to neo4j_import chunk shape."""
    inner = _inner(record)

    faiss_row_id = record.get("_id") or record.get("id") or f"doc_{index}"
    faiss_index = record.get("_index", index)
    # Neo4j key = one per vector position (metadata _id is NOT unique across 13k rows).
    source_chunk_id = (
        record.get("chunk_id")
        or inner.get("chunk_id")
        or inner.get("neo4j_chunk_id")
    )
    chunk_id = f"faiss_unified_{faiss_index}"

    document_id = (
        record.get("doc_id")
        or record.get("document_id")
        or inner.get("document_id")
        or inner.get("doc_id")
    )

    law_title = (
        record.get("law_title")
        or inner.get("law_title")
        or document_id
        or "N/A"
    )

    section = (
        record.get("section")
        or record.get("section_id")
        or inner.get("section")
        or inner.get("section_id")
        or "unknown"
    )

    text = record.get("text") or inner.get("text") or inner.get("content") or ""
    if not isinstance(text, str):
        text = str(text)

    return {
        "text": text,
        "chunk_id": chunk_id,
        "faiss_index": int(faiss_index),
        "source_chunk_id": source_chunk_id,
        "faiss_row_id": str(faiss_row_id),
        "law_title": law_title,
        "section": section,
        "section_id": record.get("section_id") or inner.get("section_id") or section,
        "document_id": document_id,
        "token_count": int(record.get("token_count") or inner.get("token_count") or 0),
        "source_file": record.get("source_file") or inner.get("source_file") or record.get("_source"),
        "version": record.get("version") or inner.get("version") or "unified",
        "entity_mentions_canonical": record.get("entity_mentions_canonical")
        or inner.get("entity_mentions_canonical")
        or [],
        "entity_types_canonical": record.get("entity_types_canonical")
        or inner.get("entity_types_canonical")
        or [],
        "clauses": record.get("clauses") or inner.get("clauses") or [],
        "metadata": {**inner, **{k: v for k, v in record.items() if k != "metadata"}},
    }


def export_unified(faiss_dir: Path, output_path: Path) -> int:
    meta_path = faiss_dir / "metadata.pkl"
    if not meta_path.exists():
        print(f"[FAIL] Missing {meta_path}")
        return 1

    print(f"Loading {meta_path} ...")
    with open(meta_path, "rb") as handle:
        records = pickle.load(handle)

    if not isinstance(records, list):
        print("[FAIL] metadata.pkl is not a list")
        return 1

    chunks = [normalize_faiss_record(row, i) for i, row in enumerate(records)]
    payload = {"chunks": chunks, "total": len(chunks), "source": str(faiss_dir)}

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)

    print(f"[OK] Wrote {len(chunks):,} chunks -> {output_path}")
    print(f"     Sample chunk_id: {chunks[0]['chunk_id']}")
    print(f"     Sample faiss_row_id: {chunks[0]['faiss_row_id']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export unified FAISS metadata to Neo4j import JSON (read-only on data_processed)."
    )
    parser.add_argument(
        "--faiss-dir",
        type=Path,
        default=DEFAULT_FAISS_DIR,
        help="Unified FAISS directory (default: data_processed/faiss_index_unified)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output JSON path (default: repo root chunks_export_unified.json)",
    )
    args = parser.parse_args()
    return export_unified(args.faiss_dir.resolve(), args.output.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
