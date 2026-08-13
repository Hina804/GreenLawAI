"""Audit phase_6 graph outputs for all pipeline-success documents."""
import json
import statistics as stats
from collections import Counter
from pathlib import Path

ND = Path(r"E:\GL_AI\data_processed\new_documents")
P6_NAME = "phase_6_6_graph_construction.json"


def load_success_docs():
    docs = []
    for d in sorted(ND.iterdir()):
        if not d.is_dir() or d.name == "graph_exports":
            continue
        summ = d / "pipeline_summary.json"
        if not summ.exists():
            continue
        try:
            if json.loads(summ.read_text(encoding="utf-8")).get("success"):
                docs.append(d)
        except Exception:
            pass
    return docs


def audit_p6(doc_dir: Path) -> dict:
    p6 = doc_dir / "phase_6" / P6_NAME
    name = doc_dir.name
    out = {"doc_id": name, "has_p6": p6.exists(), "issues": []}
    if not p6.exists():
        out["issues"].append("missing_phase6_file")
        out["grade"] = "FAIL"
        return out
    try:
        root = json.loads(p6.read_text(encoding="utf-8"))
        data = root.get("data", root)
    except Exception as e:
        out["issues"].append(f"json_error:{e}")
        out["grade"] = "FAIL"
        return out

    nodes = data.get("nodes") or []
    rels = data.get("relationships") or []
    bs = data.get("build_summary") or {}
    qr = data.get("quality_report") or {}
    rag = data.get("rag_statistics") or {}
    kpk_sum = data.get("kpk_entities_summary") or {}
    val = data.get("validation") or {}

    n_nodes = bs.get("nodes_count", len(nodes))
    n_rels = bs.get("relationships_count", len(rels))
    out["nodes"] = n_nodes
    out["rels"] = n_rels
    out["chunks"] = rag.get("chunks_created", 0)
    out["embeddings"] = rag.get("embeddings_generated", 0)
    out["overall_quality"] = qr.get("overall_quality")
    out["completeness"] = qr.get("completeness")
    out["validation_passed"] = qr.get("validation_passed")
    out["schema_errors"] = val.get("schema_errors", 0)

    synthetic = 0
    for n in nodes:
        props = n.get("properties") or {}
        sid = str(props.get("source_doc_id", n.get("source_document", "")))
        if "synthetic_seed" in sid or n.get("source_document") == "graph_builder":
            synthetic += 1
    out["synthetic_nodes"] = synthetic

    only_seed_pattern = n_nodes <= 4 and n_rels == 0 and synthetic >= 2
    kpk_laws = kpk_sum.get("kpk_laws_count", 0) or 0
    protected = kpk_sum.get("protected_species_count", 0) or 0
    officers = kpk_sum.get("forest_officers_count", 0) or 0
    extracted_entities = kpk_laws + protected + officers

    if n_rels == 0:
        out["issues"].append("zero_relationships")
    if n_nodes == 0:
        out["issues"].append("zero_nodes")
    if out["chunks"] == 0:
        out["issues"].append("zero_chunks")
    if out["embeddings"] == 0:
        out["issues"].append("zero_embeddings")
    if synthetic >= max(n_nodes - 1, 1) and n_nodes > 0:
        out["issues"].append("mostly_synthetic_seed_nodes")
    if only_seed_pattern:
        out["issues"].append("template_only_graph")
    if extracted_entities == 0 and n_nodes > 0:
        out["issues"].append("no_kpk_entity_summary")
    if out["overall_quality"] is not None and out["overall_quality"] < 0.5:
        out["issues"].append(f"low_quality_score:{out['overall_quality']:.2f}")
    if out["completeness"] is not None and out["completeness"] < 0.5:
        out["issues"].append(f"low_completeness:{out['completeness']:.2f}")

    # STRICT: relationships + chunks + not template + quality >= 0.5
    if (
        n_nodes >= 1
        and n_rels >= 1
        and out["chunks"] >= 1
        and out["embeddings"] >= 1
        and not only_seed_pattern
        and (out["overall_quality"] or 0) >= 0.5
        and synthetic < n_nodes
    ):
        out["grade"] = "PERFECT_STRICT"
    elif n_nodes >= 1 and out["chunks"] >= 1 and out["embeddings"] >= 1 and not only_seed_pattern:
        out["grade"] = "OK_VECTOR_WEAK_GRAPH"
    elif n_nodes >= 1 and out["chunks"] >= 1:
        out["grade"] = "WEAK_GRAPH_HAS_CHUNKS"
    elif only_seed_pattern or (n_nodes <= 4 and n_rels == 0):
        out["grade"] = "TEMPLATE_GRAPH"
    else:
        out["grade"] = "FAIL"

    return out


def main():
    docs = load_success_docs()
    results = [audit_p6(d) for d in docs]
    grades = Counter(r["grade"] for r in results)

    print(f"success_docs={len(docs)}")
    print("=== GRADE DISTRIBUTION ===")
    for g, c in grades.most_common():
        print(f"  {g}: {c}")

    issue_counts = Counter()
    for r in results:
        for i in r.get("issues", []):
            issue_counts[i.split(":")[0]] += 1
    print("=== ISSUE FREQUENCY ===")
    for k, v in issue_counts.most_common():
        print(f"  {k}: {v}")

    nodes_list = [r["nodes"] for r in results if "nodes" in r]
    rels_list = [r["rels"] for r in results if "rels" in r]
    chunks_list = [r["chunks"] for r in results if "chunks" in r]
    print("=== AGGREGATE STATS ===")
    print(f"nodes: min={min(nodes_list)} max={max(nodes_list)} median={stats.median(nodes_list):.0f}")
    print(f"rels: min={min(rels_list)} max={max(rels_list)} median={stats.median(rels_list):.0f}")
    print(f"chunks: min={min(chunks_list)} max={max(chunks_list)} median={stats.median(chunks_list):.0f}")
    print(f"zero_relationships: {sum(1 for r in results if r.get('rels') == 0)}/{len(results)}")
    print(f"PERFECT_STRICT: {grades.get('PERFECT_STRICT', 0)}")
    print(f"TEMPLATE_GRAPH: {grades.get('TEMPLATE_GRAPH', 0)}")

    report_path = ND / "phase6_audit_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "total": len(results),
                "grades": dict(grades),
                "issues": dict(issue_counts),
                "documents": results,
            },
            f,
            indent=2,
        )
    print(f"Full report: {report_path}")


if __name__ == "__main__":
    main()
