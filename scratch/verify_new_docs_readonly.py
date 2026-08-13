"""Read-only verification for new_documents - no file modifications."""
import csv
import json
import random
import sys
from pathlib import Path

BASE = Path(r"E:/GL_AI/data_processed/new_documents")
FAISS = Path(r"E:/GL_AI/data_processed/faiss_index_new")
GRAPH = BASE / "graph_exports"
DATA_RAW = Path(r"E:/GL_AI/data_raw")
OUT = Path(r"E:/GL_AI/scratch/verify_new_docs_report.json")

SUPPORTED = {".pdf", ".doc", ".docx", ".xlsx", ".xls", ".csv", ".json", ".pptx"}
BASELINE_NAMES = {
    "forest_act_1927.pdf",
    "kpk_forest_ordinance_2002.pdf",
    "The-Khyber-Pakhtunkhwa-Parks-and-Horticulture-Act-2024.pdf",
    "The-Khyber-Pakhtunkhwa-Forest-Amendment-Act-2022-Khyber-Pakhtunkhwa-Act-No.-XXXI-of-2022.pdf",
    "1999_15_THE_KHYBER_PAKHTUNKHWA_FORESTRY_COMMISSION_ACT_1999.pdf",
    "The-North-West-Frontier-Province-Forest-Development-Corporation-Amendment-Act-2006-Act-No.-VI-2006.pdf",
    "The-North-West-Frontier-Province-Forest-Ordinance-2002-Ord-No.-XIX-2002.pdf",
    "FOREST_DEVELOPMENT_CORPORATION_ORDINANCE,_1980.pdf",
    "(CONSERVATION_AND_EXPLOITATION_OF_CERTAIN_FORESTS_IN_HAZARA_DIVISION)_ORDINANCE,_1980.pdf",
    "1964_11_THE_WEST_PAKISTAN_FIREWOOD_AND_CHARCOAL_RESTRICTION_ACT_1964.pdf",
    "KPK_Private_Game_Reserve_Rules_1993.pdf",
    "KPK_Environmental_Protection_Act_2014.pdf",
    "KPK_Climate_Change_Policy_2022.pdf",
    "Khyber_Pakhtunkhwa_Forest_Produce_Transport_Rules,_2004.pdf",
    "Khyber_Pakhtunkhwa_Protected_Forest_Management_Rules,_2005.pdf",
    "2015_1_THE_KHYBER_PAKHTUNKHWA_WILDLIFE_AND_BIODIVERSITY_PROTECTION_PRESERVATION_CONSERVATION_AND_MANAGEMENT_ACT_2015.pdf",
    "Khyber_Pakhtunkhwa_Management_of_Guzara_Forest_Rules,_2004._.pdf",
    "Khyber_Pakhtunkhwa_Duty_on_Forest_Produce_Rules,_2004.pdf",
    "The-Khyber-Pakhtunkhwa-Climate-Action-Board-Act-2025-GC.pdf",
}

PHASE_CHECKS = [
    (0, "phase_0/phase_0_0_foundation.json"),
    (1, "phase_1/phase_1_1_extraction.json"),
    (2, "phase_2/phase_2_2_restoration.json"),
    (3, "phase_3/phase_3_3_linguistic_alignment.json"),  # alt name in checklist
    (4, "phase_4/phase_4_4_legal_extraction.json"),
    (5, "phase_5/phase_5_5_authority_reasoning.json"),  # alt name in checklist
    (6, "phase_6/phase_6_6_graph_construction.json"),
]


def count_csv_rows(path: Path) -> int:
    if not path.exists():
        return -1
    with open(path, newline="", encoding="utf-8-sig") as f:
        return max(sum(1 for _ in f) - 1, 0)


def expected_raw_files():
    if not DATA_RAW.exists():
        return []
    files = []
    for f in DATA_RAW.rglob("*"):
        if f.is_file() and f.suffix.lower() in SUPPORTED and f.name not in BASELINE_NAMES:
            files.append(f)
    return files


def resolve_phase_file(doc_dir: Path, phase_num: int, default_rel: str) -> Path | None:
    p = doc_dir / default_rel
    if p.exists():
        return p
    phase_dir = doc_dir / f"phase_{phase_num}"
    if phase_dir.exists():
        jsons = list(phase_dir.glob("*.json"))
        if jsons:
            return jsons[0]
    return None


def check_phases(doc_dir: Path) -> dict:
    row = {}
    for num, rel in PHASE_CHECKS:
        fp = resolve_phase_file(doc_dir, num, rel)
        row[f"phase_{num}"] = fp is not None and fp.exists()
    p7 = doc_dir / "phase_7" / "phase_7_7_orchestration.json"
    if not p7.exists():
        p7 = doc_dir / "phase_7" / "phase_7_orchestration.json"
        if not p7.exists():
            p7_dir = doc_dir / "phase_7"
            if p7_dir.exists():
                js = list(p7_dir.glob("*.json"))
                p7 = js[0] if js else Path()
    row["phase_7_or_summary"] = (
        p7.exists()
        if isinstance(p7, Path) and str(p7)
        else False
    ) or (doc_dir / "pipeline_summary.json").exists()
    return row


def phase1_quality(doc_dir: Path) -> dict:
    fp = resolve_phase_file(doc_dir, 1, "phase_1/phase_1_1_extraction.json")
    q = {"raw_text_len": 0, "raw_text_nonempty": False, "total_pages": None, "quality": None}
    if not fp:
        q["error"] = "phase_1 missing"
        return q
    data = json.loads(fp.read_text(encoding="utf-8"))
    inner = data.get("data", {})
    text = inner.get("raw_text") or inner.get("extracted_text") or inner.get("text") or ""
    q["raw_text_len"] = len(str(text).strip())
    q["raw_text_nonempty"] = q["raw_text_len"] > 0
    meta = inner.get("metadata") or {}
    q["total_pages"] = meta.get("total_pages")
    q["quality"] = meta.get("quality")
    p0 = resolve_phase_file(doc_dir, 0, "phase_0/phase_0_0_foundation.json")
    if p0 and p0.exists():
        p0d = json.loads(p0.read_text(encoding="utf-8"))
        prof = p0d.get("data", {}).get("profile", {})
        if isinstance(prof, dict):
            q["phase0_total_pages"] = prof.get("total_pages")
            q["phase0_quality"] = prof.get("quality")
    return q


def faiss_status() -> dict:
    st = {"dir_exists": FAISS.exists(), "files": [], "faiss_index.bin": False,
          "chunk_registry.pkl": False, "index_metadata.json": False, "vector_count": None}
    if not FAISS.exists():
        return st
    for f in sorted(FAISS.iterdir()):
        if f.is_file():
            st["files"].append({"name": f.name, "size": f.stat().st_size})
    for key in ("faiss_index.bin", "chunk_registry.pkl", "index_metadata.json"):
        st[key] = (FAISS / key).exists()
    bin_path = FAISS / "faiss_index.bin"
    if bin_path.exists():
        try:
            import faiss
            idx = faiss.read_index(str(bin_path))
            st["vector_count"] = int(idx.ntotal)
        except Exception as e:
            st["vector_count_error"] = str(e)
    reg = FAISS / "chunk_registry.pkl"
    if reg.exists() and st["vector_count"] is None:
        try:
            import pickle
            with open(reg, "rb") as f:
                st["vector_count"] = len(pickle.load(f))
        except Exception as e:
            st["registry_error"] = str(e)
    return st


def main():
    random.seed(42)
    report = {}
    docs = sorted(
        d for d in BASE.iterdir()
        if d.is_dir() and d.name not in {"graph_exports"}
    ) if BASE.exists() else []
    report["folder_count"] = len(docs)
    report["folder_names"] = [d.name for d in docs]

    raw = expected_raw_files()
    report["expected_from_data_raw"] = len(raw)
    out_stems = {d.name.lower(): d.name for d in docs}
    missing = []
    for f in raw:
        stem = f.stem
        if stem not in out_stems and stem.lower() not in out_stems:
            missing.append(str(f.relative_to(DATA_RAW)).replace("\\", "/"))
    report["missing_count"] = len(missing)
    report["missing_sample"] = missing[:30]
    report["missing_all_count"] = len(missing)

    sample_n = min(10, len(docs))
    sample = random.sample(docs, sample_n) if docs else []
    phase_table = []
    quality_table = []
    for d in sorted(sample, key=lambda x: x.name):
        phase_table.append({"document": d.name, **check_phases(d)})
        quality_table.append({"document": d.name, **phase1_quality(d)})

    report["phase_sample"] = phase_table
    report["quality_sample"] = quality_table
    report["faiss"] = faiss_status()
    graph = {"exists": GRAPH.exists(), "nodes_csv": False, "relationships_csv": False,
             "node_count": -1, "relationship_count": -1}
    if GRAPH.exists():
        graph["files"] = [f.name for f in GRAPH.iterdir() if f.is_file()]
        nodes = GRAPH / "nodes.csv"
        rels = GRAPH / "relationships.csv"
        graph["nodes_csv"] = nodes.exists()
        graph["relationships_csv"] = rels.exists()
        if nodes.exists():
            graph["node_count"] = count_csv_rows(nodes)
        if rels.exists():
            graph["relationship_count"] = count_csv_rows(rels)
    report["graph"] = graph

    OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
