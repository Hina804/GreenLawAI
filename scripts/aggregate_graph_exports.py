"""
aggregate_graph_exports.py
Collects Phase 6 JSON outputs from all processed documents into centralized
nodes.csv and relationships.csv files ready for Neo4j import.

Relationship generation strategy:
  - HAS_SECTION: Law -> Section nodes from same document
  - IMPOSES: Section -> Penalty nodes
  - MENTIONS_SPECIES: Any node -> Species nodes from same document
  - CITES: Section -> Section (cross-references detected in properties)
  - BELONGS_TO_DOCUMENT: All nodes -> their source document node
"""

import json
import csv
from pathlib import Path
from collections import defaultdict
import re


def _extract_graph_data(data: dict) -> tuple:
    """
    Robustly extract nodes and relationships from different serialization formats.
    Handles PhaseResult wrappers up to 2 levels deep.
    """
    def _dig(d):
        if not isinstance(d, dict):
            return [], []
        nodes = d.get("nodes", [])
        rels = d.get("relationships", [])
        if nodes or rels:
            return nodes, rels
        inner = d.get("data", {})
        if isinstance(inner, dict):
            nodes = inner.get("nodes", [])
            rels = inner.get("relationships", [])
            if nodes or rels:
                return nodes, rels
            inner2 = inner.get("data", {})
            if isinstance(inner2, dict):
                return inner2.get("nodes", []), inner2.get("relationships", [])
        return [], []
    return _dig(data)


def _infer_relationships(nodes: list) -> list:
    """
    Derive Neo4j relationships from co-located nodes within the same document.
    
    Rules:
      Law -> HAS_SECTION -> Section
      Section -> IMPOSES -> Penalty
      Law/Section -> MENTIONS_SPECIES -> Species
      * -> BELONGS_TO_DOCUMENT -> Document (the source document node)
    """
    rels = []
    rel_id = 0

    def make_rel(start, end, rel_type, props=None):
        nonlocal rel_id
        r = {
            "relationship_id": f"REL_INFERRED_{rel_id:06d}",
            "start_node_id": start,
            "end_node_id": end,
            "type": rel_type,
            "source_document": "aggregator",
            "confidence": 0.9,
            "pipeline_source": "aggregate_graph_exports",
        }
        if props:
            r.update(props)
        rel_id += 1
        return r

    # Group nodes by source_document
    by_doc = defaultdict(list)
    for node in nodes:
        doc = node.get("source_document", "unknown")
        by_doc[doc].append(node)

    for doc, doc_nodes in by_doc.items():
        # Index by label type
        laws, sections, penalties, species, documents = [], [], [], [], []
        for n in doc_nodes:
            labels_raw = n.get("labels", [])
            # labels may be a list or semicolon-separated string
            if isinstance(labels_raw, str):
                labels = [l.strip() for l in labels_raw.split(";")]
            else:
                labels = labels_raw

            nid = n.get("node_id", "")
            label_set = set(l.lower() for l in labels)

            if "law" in label_set or "act" in label_set or "ordinance" in label_set:
                laws.append(nid)
            if "section" in label_set:
                sections.append(nid)
            if "penalty" in label_set or "fine" in label_set:
                penalties.append(nid)
            if "species" in label_set or "tree" in label_set:
                species.append(nid)
            if "document" in label_set:
                documents.append(nid)

        # Law -> HAS_SECTION -> Section
        for law in laws:
            for sec in sections:
                rels.append(make_rel(law, sec, "HAS_SECTION"))

        # Section -> IMPOSES -> Penalty
        for sec in sections:
            for pen in penalties:
                rels.append(make_rel(sec, pen, "IMPOSES"))

        # Law/Section -> MENTIONS_SPECIES -> Species
        for sp in species:
            for parent in laws + sections:
                rels.append(make_rel(parent, sp, "MENTIONS_SPECIES"))

        # All non-document nodes -> BELONGS_TO_DOCUMENT -> Document
        for doc_node in documents:
            for n in doc_nodes:
                nid = n.get("node_id", "")
                if nid != doc_node:
                    rels.append(make_rel(nid, doc_node, "BELONGS_TO_DOCUMENT"))

    return rels


def flatten_properties(items: list) -> list:
    """Flatten nested dicts/lists to JSON strings for CSV compatibility."""
    flat_items = []
    for item in items:
        flat = {}
        for k, v in item.items():
            if isinstance(v, (dict, list)):
                flat[k] = json.dumps(v, ensure_ascii=False)
            elif v is None:
                flat[k] = ""
            else:
                flat[k] = v
        flat_items.append(flat)
    return flat_items


def write_csv(path: Path, rows: list):
    """Write a list of flat dicts to CSV."""
    if not rows:
        return 0
    fieldnames = set()
    for row in rows:
        fieldnames.update(row.keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=sorted(fieldnames), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def aggregate_graph_exports():
    base_path = Path("E:/GL_AI/src/data_processed/documents")
    graph_exports_path = Path("E:/GL_AI/data_processed/final_graph_exports")
    graph_exports_path.mkdir(parents=True, exist_ok=True)

    all_nodes = []
    all_relationships = []
    count = 0
    skipped = 0

    print(f"Searching for Phase 6 artifacts in {base_path}...")

    for phase6_file in base_path.rglob("phase_6_*.json"):
        try:
            with open(phase6_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            nodes, rels = _extract_graph_data(data)

            if not nodes:
                skipped += 1
                continue

            all_nodes.extend(nodes)
            all_relationships.extend(rels)
            count += 1

        except Exception as e:
            print(f"  [WARN] Error reading {phase6_file.name}: {e}")

    if not all_nodes:
        print(f"No graph data found. Searched {count + skipped} files.")
        return

    # Deduplicate nodes by node_id
    seen_ids = set()
    unique_nodes = []
    for n in all_nodes:
        nid = n.get("node_id", "")
        if nid not in seen_ids:
            seen_ids.add(nid)
            unique_nodes.append(n)

    # If no structural relationships exist, infer them from co-location
    if not all_relationships:
        print("No relationships found in Phase 6 output. Inferring from node co-location...")
        all_relationships = _infer_relationships(unique_nodes)

    # Deduplicate relationships
    seen_rels = set()
    unique_rels = []
    for r in all_relationships:
        key = (r.get("start_node_id", ""), r.get("end_node_id", ""), r.get("type", ""))
        if key not in seen_rels:
            seen_rels.add(key)
            unique_rels.append(r)

    # Write CSVs
    nodes_written = write_csv(graph_exports_path / "nodes.csv", flatten_properties(unique_nodes))
    rels_written = write_csv(graph_exports_path / "relationships.csv", flatten_properties(unique_rels))

    print(f"\n[SUCCESS] nodes.csv       -> {nodes_written:,} nodes")
    print(f"[SUCCESS] relationships.csv -> {rels_written:,} relationships")
    print(f"\n[SUMMARY] Aggregated {count} Phase 6 files | {nodes_written} unique nodes | {rels_written} relationships")
    print(f"[OUTPUT]  {graph_exports_path}")


if __name__ == "__main__":
    aggregate_graph_exports()
