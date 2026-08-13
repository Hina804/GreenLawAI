"""
READ-ONLY verification of new_documents pipeline outputs.
Does not modify any data files.
"""
import csv
import json
import os
import random
import re
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(r"E:/GL_AI")
BASE = PROJECT_ROOT / "data_processed" / "new_documents"
FAISS_DIR = PROJECT_ROOT / "data_processed" / "faiss_index_new"
GRAPH_DIR = BASE / "graph_exports"
LOG_PATH = BASE / "batch_execution_log_new.txt"
DATA_RAW = PROJECT_ROOT / "data_raw"
OUT_PATH = PROJECT_ROOT / "scratch" / "verification_report_data.json"

PHASE_FILE_PATTERNS = {
    i: re.compile(rf"^phase_{i}_.*\.json$", re.I) for i in range(8)
}


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def find_registry_added() -> list[str]:
    """Find Registry v5.1 ADDED entries from common locations."""
    candidates = [
        PROJECT_ROOT / "data_processed" / "registry_v5.1.json",
        PROJECT_ROOT / "data_processed" / "KPK_Registry_v5.1.json",
        PROJECT_ROOT / "data_raw" / "registry_v5.1.json",
        PROJECT_ROOT / "docs" / "KPK_Registry_v5.1.json",
    ]
    for p in list(PROJECT_ROOT.glob("**/*Registry*v5*")) + list(PROJECT_ROOT.glob("**/*registry*v5*")):
        if p.suffix.lower() in {".json", ".csv", ".yaml", ".yml"}:
            candidates.append(p)

    added = []
    seen_paths = set()
    for path in candidates:
        if not path.exists() or path in seen_paths:
            continue
        seen_paths.add(path)
        try:
            if path.suffix.lower() == ".json":
                data = load_json(path)
                items = data if isinstance(data, list) else data.get("documents", data.get("entries", []))
                if isinstance(data, dict) and not items:
                    items = list(data.values())
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    status = str(item.get("status", item.get("registry_status", ""))).upper()
                    marker = str(item.get("marker", item.get("note", "")))
                    if "ADDED" in status or "🆕" in marker or "ADDED" in marker:
                        name = item.get("filename") or item.get("file") or item.get("name") or item.get("document_id")
                        if name:
                            added.append(str(name))
            elif path.suffix.lower() == ".csv":
                with open(path, newline="", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        row_text = " ".join(str(v) for v in row.values())
                        if "ADDED" in row_text.upper() or "🆕" in row_text:
                            name = (
                                row.get("filename")
                                or row.get("file")
                                or row.get("name")
                                or row.get("document")
                                or row.get("path")
                            )
                            if name:
                                added.append(str(name))
        except Exception:
            continue
    return sorted(set(added))


def stem_normalize(name: str) -> str:
    return Path(name).stem.lower().replace(" ", "_")


def doc_folders():
    if not BASE.exists():
        return []
    return sorted(
        d for d in BASE.iterdir() if d.is_dir() and d.name not in {"graph_exports"}
    )


def phase_status(doc_dir: Path) -> dict:
    status = {}
    for i in range(8):
        phase_dir = doc_dir / f"phase_{i}"
        flat = any(PHASE_FILE_PATTERNS[i].match(f.name) for f in doc_dir.glob("*.json"))
        subdir = phase_dir.exists() and any(phase_dir.glob("*.json"))
        status[i] = bool(flat or subdir)
    return status


def count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with open(path, newline="", encoding="utf-8-sig") as f:
        return max(sum(1 for _ in f) - 1, 0)


def scan_zero_byte_files(root: Path, limit=500) -> list:
    found = []
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            fp = Path(dirpath) / fn
            try:
                if fp.stat().st_size == 0:
                    found.append(str(fp.relative_to(root)))
                    if len(found) >= limit:
                        return found
            except OSError:
                pass
    return found


def faiss_info():
    info = {"exists": FAISS_DIR.exists(), "files": [], "vector_count": None, "search_ok": False, "search_error": None}
    if not FAISS_DIR.exists():
        return info
    for f in sorted(FAISS_DIR.iterdir()):
        info["files"].append({"name": f.name, "size": f.stat().st_size})
    bin_path = FAISS_DIR / "faiss_index.bin"
    meta_path = FAISS_DIR / "chunk_registry.pkl"
    if meta_path.exists():
        try:
            import pickle

            with open(meta_path, "rb") as f:
                reg = pickle.load(f)
            info["vector_count"] = len(reg)
        except Exception as e:
            info["registry_load_error"] = str(e)
    if bin_path.exists():
        try:
            import faiss
            import numpy as np

            idx = faiss.read_index(str(bin_path))
            info["faiss_ntotal"] = int(idx.ntotal)
            if info["vector_count"] is None:
                info["vector_count"] = int(idx.ntotal)
            if idx.ntotal > 0:
                dim = idx.d
                q = np.random.randn(1, dim).astype("float32")
                faiss.normalize_L2(q)
                scores, ids = idx.search(q, min(5, idx.ntotal))
                info["search_ok"] = True
                info["search_sample_ids"] = ids[0].tolist()
                info["search_sample_scores"] = scores[0].tolist()
        except Exception as e:
            info["search_error"] = str(e)
    return info


def log_errors(text: str) -> dict:
    patterns = {
        "add_vectors_attributeerror": len(re.findall(r"AttributeError.*add_vectors", text, re.I)),
        "phase_6_errors": len(re.findall(r"Phase 6|phase_6|graph_construction", text, re.I)),
        "failed_entries": len(re.findall(r"\[FAILED\]", text)),
        "save_errors": len(re.findall(r"\[SAVE ERROR\]", text)),
    }
    return patterns


def quality_sample(docs: list[Path], report: dict):
    targets = [
        ("Act", "West_Pakistan_Land_Revenue_Act_1967"),
        ("Court Case", "2022_SCMR_88"),
        ("Permit JSON", "PER-2024-001"),
        ("CSV Reference", "species_price_list"),
        ("Working Plan", "WORKING PLAN FOR HARIPUR"),
    ]
    samples = []
    for label, needle in targets:
        match = next((d for d in docs if needle.lower() in d.name.lower()), None)
        if not match:
            samples.append({"label": label, "needle": needle, "found": False})
            continue
        entry = {"label": label, "document": match.name, "found": True, "checks": {}}
        p1_dir = match / "phase_1"
        p4_dir = match / "phase_4"
        if p1_dir.exists():
            p1_files = list(p1_dir.glob("*.json"))
            if p1_files:
                try:
                    data = load_json(p1_files[0]).get("data", {})
                    text = data.get("extracted_text") or data.get("text") or ""
                    entry["checks"]["phase1_text_len"] = len(str(text))
                    entry["checks"]["phase1_snippet"] = str(text)[:200]
                    if label == "CSV Reference":
                        entry["checks"]["rows"] = len(data.get("rows", data.get("tables", [])))
                except Exception as e:
                    entry["checks"]["phase1_error"] = str(e)
        if p4_dir.exists():
            p4_files = list(p4_dir.glob("*.json"))
            if p4_files:
                try:
                    data = load_json(p4_files[0]).get("data", {})
                    if label == "Court Case":
                        ents = data.get("entities", data.get("legal_entities", {}))
                        entry["checks"]["entity_keys"] = list(ents.keys())[:20] if isinstance(ents, dict) else str(type(ents))
                    elif label == "Act":
                        secs = data.get("sections", [])
                        entry["checks"]["sections_count"] = len(secs)
                    elif label == "Permit JSON":
                        entry["checks"]["preserved_keys"] = list(data.keys())[:15]
                except Exception as e:
                    entry["checks"]["phase4_error"] = str(e)
        samples.append(entry)
    report["quality_targets"] = samples


def main():
    report = {
        "base_exists": BASE.exists(),
        "doc_folder_count": 0,
        "phase_counts": {},
        "full_8_phases": 0,
        "partial": 0,
        "zero_phases": 0,
        "pipeline_summary": {"success": 0, "failed": 0, "missing": 0},
        "missing_phases": [],
        "manifests": {},
        "registry_added_count": 0,
        "registry_missing_from_output": [],
        "output_not_in_registry": [],
        "faiss": {},
        "graph": {},
        "zero_byte_files": [],
        "log_scan": {},
        "quality_targets": [],
    }

    docs = doc_folders()
    report["doc_folder_count"] = len(docs)
    phase_counts = Counter()
    for d in docs:
        st = phase_status(d)
        for i, ok in st.items():
            if ok:
                phase_counts[i] += 1
        if all(st.values()):
            report["full_8_phases"] += 1
        elif any(st.values()):
            report["partial"] += 1
            miss = [i for i, v in st.items() if not v]
            report["missing_phases"].append({"document": d.name, "missing": miss})
        else:
            report["zero_phases"] += 1

        sp = d / "pipeline_summary.json"
        if sp.exists():
            try:
                s = load_json(sp)
                if s.get("success"):
                    report["pipeline_summary"]["success"] += 1
                else:
                    report["pipeline_summary"]["failed"] += 1
            except Exception:
                report["pipeline_summary"]["failed"] += 1
        else:
            report["pipeline_summary"]["missing"] += 1

    report["phase_counts"] = {f"phase_{i}": phase_counts[i] for i in range(8)}

    for mf in [
        "batch_manifest_new.json",
        "deferred_batch_manifest.json",
        "deferred_bottlenecks.json",
    ]:
        p = BASE / mf
        if p.exists():
            try:
                report["manifests"][mf] = load_json(p)
            except Exception as e:
                report["manifests"][mf] = {"error": str(e)}

    added = find_registry_added()
    report["registry_added_count"] = len(added)
    report["registry_source_found"] = len(added) > 0

    if added:
        out_stems = {d.name.lower(): d.name for d in docs}
        out_stem_norm = {stem_normalize(k): k for k in out_stems}
        for name in added:
            stem = stem_normalize(name)
            if stem not in out_stem_norm and Path(name).stem not in out_stems:
                report["registry_missing_from_output"].append(name)
        added_stems = {stem_normalize(n) for n in added}
        for d in docs:
            if stem_normalize(d.name) not in added_stems and d.name not in added:
                report["output_not_in_registry"].append(d.name)

    report["zero_byte_files"] = scan_zero_byte_files(BASE)
    report["faiss"] = faiss_info()

    graph = {"exists": GRAPH_DIR.exists(), "files": []}
    if GRAPH_DIR.exists():
        for f in sorted(GRAPH_DIR.iterdir()):
            graph["files"].append({"name": f.name, "size": f.stat().st_size})
        nodes = GRAPH_DIR / "nodes.csv"
        rels = GRAPH_DIR / "relationships.csv"
        graph["node_count"] = count_csv_rows(nodes)
        graph["relationship_count"] = count_csv_rows(rels)
        if nodes.exists():
            with open(nodes, newline="", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                graph["node_headers"] = next(reader, [])
        if rels.exists():
            with open(rels, newline="", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                graph["relationship_headers"] = next(reader, [])
    report["graph"] = graph

    if LOG_PATH.exists():
        try:
            text = LOG_PATH.read_text(encoding="utf-8", errors="replace")
            report["log_scan"] = log_errors(text)
            report["log_size"] = len(text)
        except Exception as e:
            report["log_scan"] = {"error": str(e)}

    quality_sample(docs, report)

  # Baseline FAISS structure compare (file names only, no index load from baseline)
    baseline = PROJECT_ROOT / "data_processed" / "faiss_index"
    if baseline.exists():
        report["faiss_baseline_file_names"] = sorted(f.name for f in baseline.iterdir() if f.is_file())
    report["faiss_new_file_names"] = sorted(f.name for f in FAISS_DIR.iterdir() if f.is_file()) if FAISS_DIR.exists() else []

    OUT_PATH.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: report[k] for k in report if k != "manifests"}, indent=2, default=str))
    print(f"\nFull report: {OUT_PATH}")


if __name__ == "__main__":
    main()
