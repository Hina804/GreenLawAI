"""
export_manual_graphs_to_csv.py
Compiles graph CSVs directly from manually optimized nodes and relationships in phase 6.
Optimized version:
  - Flattens properties_json into top-level columns.
  - Deduplicates logical duplicates (e.g. LOC_KPK, LOCATION_KPK_PROVINCE -> LOC_KPK_PROVINCE).
  - Standardizes labels to singular PascalCase.
  - Renames node_id:ID to node_id.
  - Backfills :START_ID and :END_ID in relationships.
  - Sorts nodes by node_id and relationships by :START_ID and :END_ID.
  - Ensures Unix line endings (\n) and UTF-8 encoding.
"""

import os
import sys
import json
import csv
import logging
import hashlib
import re
from pathlib import Path
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ExportCSV")

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

NEW_DOCS_DIR = Path("E:/GL_AI/data_processed/new_documents")
OUTPUT_DIR = Path("E:/GL_AI/data_processed/graph_exports")

EXPORT_VERSION = "manual_v1.0"
TIMESTAMP = datetime.utcnow().isoformat()

# Explicit manual merge mappings for deduplication
ID_MERGE_MAP = {
    # Khyber Pakhtunkhwa Locations
    "LOCATION_KPK_PROVINCE": "LOC_KPK_PROVINCE",
    "LOC_KPK": "LOC_KPK_PROVINCE",
    "LOC_KHYBER_PAKHTUNKHWA": "LOC_KPK_PROVINCE",
    "LOC_KPK_PROVINCE": "LOC_KPK_PROVINCE",
    
    # Hazara Locations
    "LOCATION_HAZARA_DISTRICT": "LOC_HAZARA_DISTRICT",
    "LOCATION_HAZARA_DIVISION": "LOC_HAZARA_DIVISION",
    "LOC_HAZARA_DISTRICT": "LOC_HAZARA_DISTRICT",
    "LOC_HAZARA_DIVISION": "LOC_HAZARA_DIVISION",
    
    # Swat Locations
    "LOCATION_SWAT": "LOC_SWAT",
    "LOC_SWAT": "LOC_SWAT",
    
    # Abbottabad Locations
    "LOCATION_ABBOTTABAD": "LOC_ABBOTTABAD",
    "LOC_ABBOTTABAD": "LOC_ABBOTTABAD",
    
    # Forest Department Authority
    "GOVT_FOREST_DEPT_KPK": "AUTHORITY_KPK_FOREST_DEPARTMENT",
    "BODY_FOREST_DEPARTMENT": "AUTHORITY_KPK_FOREST_DEPARTMENT",
    "AUTHORITY_KPK_FOREST_DEPARTMENT": "AUTHORITY_KPK_FOREST_DEPARTMENT",
    
    # Government of KPK
    "AUTH_GOVT_KPK": "AUTH_GOVT_KPK",
    "GOVT_KPK": "AUTH_GOVT_KPK",
    "AUTH_GOVERNMENT_OF_KPK": "AUTH_GOVT_KPK"
}

# Standardized label mappings
LABEL_MAP = {
    "Document": "Document",
    "Act": "Document",
    "ForestAct": "Document",
    "LegalDocument": "Document",
    "Statute": "Document",
    "StatutoryProvision": "Section",
    "Section": "Section",
    "Clause": "Section",
    "Definition": "Definition",
    "Authority": "Authority",
    "GovernmentBody": "Authority",
    "Government": "Authority",
    "Court": "Court",
    "Officer": "Officer",
    "AdministrativeRole": "AdministrativeRole",
    "Location": "Location",
    "District": "Location",
    "Province": "Location",
    "Division": "Location",
    "SpecialArea": "Location",
    "ProtectedArea": "Location",
    "WaterBody": "Location",
    "GeographicEntity": "Location",
    "Penalty": "Penalty",
    "Fine": "Penalty",
    "LegalConsequence": "Penalty",
    "Abstention": "Abstention",
    "Uncertainty": "Abstention",
    "DocumentChunk": "DocumentChunk",
    "Content": "DocumentChunk",
    "Species": "Species",
    "ForestEntity": "Species",
    "Amendment": "Amendment",
    "CrossReference": "CrossReference",
    "Body": "Body",
    "LegalPrinciple": "LegalPrinciple",
    "Party": "Party",
    "Pattern": "Pattern",
    "Procedure": "Procedure",
    "Policy": "Procedure"
}


def _logic_hash(data: dict) -> str:
    """Generate a short hash for forensic verification."""
    raw = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def standardize_label(label_str: str) -> str:
    """Standardize labels to singular, PascalCase."""
    if not label_str:
        return "GenericNode"
    labels = [l.strip() for l in label_str.split(";") if l.strip()]
    standardized = []
    for l in labels:
        canonical = LABEL_MAP.get(l, l)
        if canonical not in standardized:
            standardized.append(canonical)
    
    final_labels = []
    for l in standardized:
        pascal = "".join([w.capitalize() for w in re.split(r'[_ ]', l)])
        if pascal.endswith("s") and pascal.lower() != "species":
            pascal = pascal[:-1]
        if pascal not in final_labels:
            final_labels.append(pascal)
            
    return ";".join(final_labels) if final_labels else "GenericNode"


def get_canonical_id(node_id: str, label: str, props: dict) -> str:
    """Get canonical node ID based on merge mapping and name matches."""
    if node_id in ID_MERGE_MAP:
        return ID_MERGE_MAP[node_id]
    
    if label == "Location":
        name = props.get("name") or props.get("title")
        if name:
            norm_name = str(name).lower().strip()
            # Strip common suffixes for matching
            for suffix in ["province", "division", "district", "tehsil", "area", "valley", "ilqa"]:
                norm_name = norm_name.replace(suffix, "").strip()
            
            if norm_name in ["khyber pakhtunkhwa", "kpk", "kp"]:
                return "LOC_KPK_PROVINCE"
            if norm_name == "hazara":
                if "division" in str(name).lower():
                    return "LOC_HAZARA_DIVISION"
                return "LOC_HAZARA_DISTRICT"
            if norm_name == "swat":
                return "LOC_SWAT"
            if norm_name == "abbottabad":
                return "LOC_ABBOTTABAD"
                
    return node_id


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Temporary lists to load everything in memory
    raw_nodes = []
    raw_relationships = []
    node_id_map = {} # Maps original node_id -> canonical_id

    # 1. Scan document directories
    doc_dirs = [
        d for d in NEW_DOCS_DIR.iterdir()
        if d.is_dir() and not d.name.startswith((".", "graph_exports"))
    ]
    logger.info(f"Found {len(doc_dirs)} document directories.")

    total_nodes_read = 0
    total_rels_read = 0

    for doc_dir in doc_dirs:
        doc_id = doc_dir.name
        phase_6_path = doc_dir / "phase_6" / "phase_6_6_graph_construction.json"

        if not phase_6_path.exists():
            logger.warning(f"Skipping {doc_id}: Missing phase_6_6_graph_construction.json")
            continue

        try:
            with open(phase_6_path, "r", encoding="utf-8") as f:
                raw_content = f.read()
            graph_data = json.loads(raw_content)
        except json.JSONDecodeError as e:
            logger.warning(f"Malformed JSON in {doc_id} (line {e.lineno} col {e.colno}): {e.msg}")
            logger.warning(f"Attempting auto-repair by truncating to last valid '}}' ...")
            try:
                last_brace = raw_content.rfind("}")
                if last_brace != -1:
                    repaired = raw_content[: last_brace + 1]
                    graph_data = json.loads(repaired)
                    logger.info(f"Auto-repair succeeded for {doc_id} ✓")
                else:
                    raise ValueError("No closing brace found")
            except Exception as repair_err:
                logger.error(f"Auto-repair FAILED for {doc_id}: {repair_err}")
                continue

        data = graph_data.get("data", {})
        nodes_by_type = data.get("nodes_by_type", {})
        relationships_by_type = data.get("relationships_by_type", {})

        # Load Nodes
        for node_type, nodes in nodes_by_type.items():
            for node in nodes:
                node_id = node.get("node_id")
                if not node_id:
                    continue
                
                props = node.get("properties", {})
                
                # Standardize Label
                node_labels = node.get("labels")
                if not node_labels:
                    node_labels = [node_type]
                elif isinstance(node_labels, str):
                    node_labels = [node_labels]
                
                std_label = standardize_label(";".join(node_labels))
                primary_label = std_label.split(";")[0]
                
                # Determine canonical ID
                canonical_id = get_canonical_id(node_id, primary_label, props)
                node_id_map[node_id] = canonical_id
                
                raw_nodes.append({
                    "original_id": node_id,
                    "canonical_id": canonical_id,
                    "label": std_label,
                    "properties": props,
                    "source_doc_id": doc_id,
                    "source_file": str(phase_6_path)
                })
                total_nodes_read += 1

        # Load Relationships
        for rel_type, rels in relationships_by_type.items():
            for rel in rels:
                raw_relationships.append({
                    "rel_type": rel_type,
                    "rel": rel,
                    "doc_id": doc_id,
                    "source_file": str(phase_6_path)
                })
                total_rels_read += 1

    logger.info(f"Loaded {total_nodes_read} raw nodes and {total_rels_read} raw relationships.")

    # 2. Process and Deduplicate Nodes
    nodes_by_id = {}
    for rn in raw_nodes:
        cid = rn["canonical_id"]
        props = rn["properties"]
        
        # Invariants
        source_doc_id = props.get("source_doc_id", rn["source_doc_id"])
        extraction_phase = props.get("extraction_phase", props.get("source_phase", props.get("pipeline_source", "manual_curation")))
        confidence_score = props.get("confidence_score", props.get("extraction_confidence", 1.0))
        bbox = props.get("bbox", "document_level")
        
        node_data = {
            "node_id": cid,
            ":LABEL": rn["label"],
            "source_doc_id": source_doc_id,
            "extraction_phase": extraction_phase,
            "confidence_score": confidence_score,
            "bbox": bbox,
            "source_file": rn["source_file"],
            "creation_timestamp": TIMESTAMP,
            "export_version": EXPORT_VERSION,
            "logic_hash": _logic_hash(props)
        }
        
        # Flatten properties
        for k, v in props.items():
            if k not in ["source_doc_id", "extraction_phase", "confidence_score", "bbox"]:
                if isinstance(v, (dict, list)):
                    node_data[k] = json.dumps(v, ensure_ascii=False)
                elif v is None:
                    node_data[k] = ""
                else:
                    node_data[k] = str(v)
                    
        if cid in nodes_by_id:
            existing = nodes_by_id[cid]
            # Union labels
            exist_lbls = set(existing[":LABEL"].split(";"))
            new_lbls = set(node_data[":LABEL"].split(";"))
            existing[":LABEL"] = ";".join(sorted(list(exist_lbls.union(new_lbls))))
            
            # Merge properties (keep the longest value to avoid losing detail)
            for k, v in node_data.items():
                if k not in ["node_id", ":LABEL"]:
                    if k not in existing or not existing[k]:
                        existing[k] = v
                    elif v and len(str(v)) > len(str(existing[k])):
                        existing[k] = v
        else:
            nodes_by_id[cid] = node_data

    # Sort nodes by node_id
    sorted_nodes = sorted(nodes_by_id.values(), key=lambda x: x["node_id"])

    # 3. Process and Deduplicate Relationships
    relationships_by_key = {}
    total_rels_extracted = 0
    
    for rr in raw_relationships:
        rel = rr["rel"]
        rel_type = rr["rel_type"]
        doc_id = rr["doc_id"]
        
        start_node = rel.get("start_node_id", rel.get("from", rel.get("source", "")))
        end_node = rel.get("end_node_id", rel.get("to", rel.get("target", "")))
        
        if not start_node or not end_node:
            continue
            
        # Resolve to canonical ID
        canonical_start = node_id_map.get(start_node, get_canonical_id(start_node, "", {}))
        canonical_end = node_id_map.get(end_node, get_canonical_id(end_node, "", {}))
        
        # Backfill check
        if not canonical_start or not canonical_end:
            continue
            
        rel_id = rel.get("relationship_id", f"{doc_id}_{rel_type}_{total_rels_extracted}")
        
        # Build flattened properties
        rel_props = {}
        # Get standard properties
        for k, v in rel.items():
            if k not in ["start_node_id", "end_node_id", "source", "target", "from", "to", "relationship_id", "source_document", "type", "properties"]:
                rel_props[k] = v
        # Flatten nested properties
        nested_props = rel.get("properties", {})
        if isinstance(nested_props, dict):
            for k, v in nested_props.items():
                rel_props[k] = v
                
        rel_data = {
            ":START_ID": canonical_start,
            ":END_ID": canonical_end,
            ":TYPE": rel_type,
            "relationship_id": rel_id,
            "source_document": rel.get("source_document", doc_id),
            "source_file": rr["source_file"],
            "creation_timestamp": TIMESTAMP,
            "export_version": EXPORT_VERSION,
            "logic_hash": _logic_hash(rel)
        }
        
        # Flattened properties
        for k, v in rel_props.items():
            if isinstance(v, (dict, list)):
                rel_data[k] = json.dumps(v, ensure_ascii=False)
            elif v is None:
                rel_data[k] = ""
            else:
                rel_data[k] = str(v)
                
        # Deduplicate relationships
        rel_key = (canonical_start, canonical_end, rel_type)
        if rel_key in relationships_by_key:
            existing = relationships_by_key[rel_key]
            # Merge properties
            for k, v in rel_data.items():
                if k not in [":START_ID", ":END_ID", ":TYPE", "relationship_id"]:
                    if k not in existing or not existing[k]:
                        existing[k] = v
                    elif v and len(str(v)) > len(str(existing[k])):
                        existing[k] = v
        else:
            relationships_by_key[rel_key] = rel_data
            total_rels_extracted += 1

    # Sort relationships by :START_ID and :END_ID
    sorted_rels = sorted(relationships_by_key.values(), key=lambda x: (x[":START_ID"], x[":END_ID"]))

    # 4. Write nodes.csv
    nodes_csv_path = OUTPUT_DIR / "nodes.csv"
    if sorted_nodes:
        # Compute all fieldnames across all nodes
        all_keys = set()
        for n in sorted_nodes:
            all_keys.update(n.keys())
        
        # Base headers first, then dynamic property columns sorted alphabetically
        base_keys = ["node_id", ":LABEL", "source_doc_id", "extraction_phase", "confidence_score", "bbox", "source_file", "creation_timestamp", "export_version", "logic_hash"]
        prop_keys = sorted([k for k in all_keys if k not in base_keys])
        node_fieldnames = base_keys + prop_keys
        
        with open(nodes_csv_path, "w", encoding="utf-8", newline="\n") as f:
            writer = csv.DictWriter(f, fieldnames=node_fieldnames, restval="")
            writer.writeheader()
            writer.writerows(sorted_nodes)
        logger.info(f"Written {len(sorted_nodes)} optimized nodes to {nodes_csv_path}")
    else:
        logger.warning("No nodes to write! Skipping nodes.csv.")

    # 5. Write relationships.csv
    rels_csv_path = OUTPUT_DIR / "relationships.csv"
    if sorted_rels:
        # Compute all fieldnames across all relationships
        all_keys = set()
        for r in sorted_rels:
            all_keys.update(r.keys())
            
        base_keys = [":START_ID", ":END_ID", ":TYPE", "relationship_id", "source_document", "source_file", "creation_timestamp", "export_version", "logic_hash"]
        prop_keys = sorted([k for k in all_keys if k not in base_keys])
        rel_fieldnames = base_keys + prop_keys
        
        with open(rels_csv_path, "w", encoding="utf-8", newline="\n") as f:
            writer = csv.DictWriter(f, fieldnames=rel_fieldnames, restval="")
            writer.writeheader()
            writer.writerows(sorted_rels)
        logger.info(f"Written {len(sorted_rels)} optimized relationships to {rels_csv_path}")
    else:
        logger.warning("No relationships to write! Skipping relationships.csv.")

    # 6. Write constraints.cypher
    constraints_path = OUTPUT_DIR / "constraints.cypher"
    labels_set = set()
    for n in sorted_nodes:
        for lbl in n[":LABEL"].split(";"):
            if lbl.strip():
                labels_set.add(lbl.strip())
    node_types = sorted(list(labels_set))
    
    with open(constraints_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("-- Auto-generated constraint file (optimized manual export)\n\n")
        for label in node_types:
            safe = label.replace("`", "``")
            f.write(f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:`{safe}`) REQUIRE n.node_id IS UNIQUE;\n")
        f.write("\n-- Relationship index\n")
        f.write("CREATE INDEX IF NOT EXISTS FOR ()-[r:RELATES_TO]-() ON (r.relationship_id);\n")
    logger.info(f"Written constraints to {constraints_path}")

    # 7. Write manifest.json
    manifest = {
        "export_timestamp": TIMESTAMP,
        "export_version": EXPORT_VERSION,
        "nodes_exported": len(sorted_nodes),
        "relationships_exported": len(sorted_rels),
        "node_types": node_types,
        "relationship_types": list({r[":TYPE"] for r in sorted_rels}),
        "source_directory": str(NEW_DOCS_DIR),
        "output_directory": str(OUTPUT_DIR),
    }
    with open(OUTPUT_DIR / "manifest.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    logger.info("Written manifest.json")

    logger.info("CSV Optimization Ingest Generation Complete! ✓")
    logger.info(f"Nodes exported: {len(sorted_nodes)}")
    logger.info(f"Relationships exported: {len(sorted_rels)}")


if __name__ == "__main__":
    main()
