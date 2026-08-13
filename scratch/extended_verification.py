"""Extended read-only verification - writes to scratch/extended_verification.txt"""
import json
import os
from pathlib import Path

BASE = Path(r"E:/GL_AI/data_processed/new_documents")
FAISS = Path(r"E:/GL_AI/data_processed/faiss_index_new")
DATA_RAW = Path(r"E:/GL_AI/data_raw")
OUT = Path(r"E:/GL_AI/scratch/extended_verification.txt")

SUPPORTED = {".pdf", ".doc", ".docx", ".xlsx", ".xls", ".csv", ".json", ".pptx"}
BASELINE = {
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

lines = []

def p(s=""):
    lines.append(s)

# data_raw inventory
raw_files = []
if DATA_RAW.exists():
    for f in sorted(DATA_RAW.rglob("*")):
        if f.is_file() and f.suffix.lower() in SUPPORTED:
            raw_files.append(f)
non_baseline = [f for f in raw_files if f.name not in BASELINE]
p(f"data_raw supported files (total): {len(raw_files)}")
p(f"data_raw non-baseline supported: {len(non_baseline)}")

docs = sorted(d.name for d in BASE.iterdir() if d.is_dir() and d.name != "graph_exports")
p(f"new_documents folders: {len(docs)}")

processed_stems = {d.lower() for d in docs}
missing_from_output = []
for f in non_baseline:
    if f.stem not in processed_stems and f.stem.lower() not in processed_stems:
        missing_from_output.append(str(f.relative_to(DATA_RAW)))

p(f"non-baseline raw files NOT in new_documents output: {len(missing_from_output)}")
for m in missing_from_output[:25]:
    p(f"  MISSING: {m}")
if len(missing_from_output) > 25:
    p(f"  ... +{len(missing_from_output)-25} more")

# phase 1 text stats
empty_p1 = nonzero_p1 = 0
empty_p0_pages = unreadable = 0
file_sizes = []
for dname in docs:
    d = BASE / dname
    p1 = d / "phase_1"
    if p1.exists():
        for jf in p1.glob("*.json"):
            try:
                data = json.loads(jf.read_text(encoding="utf-8"))
                inner = data.get("data", {})
                text = inner.get("raw_text") or inner.get("extracted_text") or inner.get("text") or ""
                if len(str(text).strip()) == 0:
                    empty_p1 += 1
                else:
                    nonzero_p1 += 1
            except Exception:
                pass
    p0 = d / "phase_0"
    if p0.exists():
        for jf in p0.glob("*.json"):
            try:
                data = json.loads(jf.read_text(encoding="utf-8"))
                prof = data.get("data", {}).get("profile", {})
                if prof.get("total_pages", 1) == 0:
                    empty_p0_pages += 1
                if prof.get("quality") == "unreadable":
                    unreadable += 1
            except Exception:
                pass
    total = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
    file_sizes.append((dname, total))

p(f"\nPhase 1 empty raw_text: {empty_p1}/{len(docs)}")
p(f"Phase 1 non-empty: {nonzero_p1}/{len(docs)}")
p(f"Phase 0 total_pages=0: {empty_p0_pages}/{len(docs)}")
p(f"Phase 0 quality=unreadable: {unreadable}/{len(docs)}")

p("\nSmallest 5 doc folders by bytes:")
for name, sz in sorted(file_sizes, key=lambda x: x[1])[:5]:
    p(f"  {name}: {sz} bytes")
p("\nLargest 5 doc folders by bytes:")
for name, sz in sorted(file_sizes, key=lambda x: x[1], reverse=True)[:5]:
    p(f"  {name}: {sz} bytes")

# FAISS
p(f"\nFAISS dir exists: {FAISS.exists()}")
if FAISS.exists():
    ff = list(FAISS.iterdir())
    p(f"FAISS files: {[f.name for f in ff]}")
    for f in ff:
        p(f"  {f.name}: {f.stat().st_size} bytes")

# graph
g = BASE / "graph_exports"
p(f"\ngraph_exports exists: {g.exists()}")

# manifests at project level
for mp in [
    BASE / "batch_manifest_new.json",
    BASE / "deferred_bottlenecks.json",
    Path(r"E:/GL_AI/data_processed/batch_manifest_new.json"),
    Path(r"E:/GL_AI/data_processed/phase_5_6_background_log.txt"),
]:
    p(f"{mp.name} exists at {mp.parent.name}: {mp.exists()}")

# quality targets in output
targets = [
    "2022_SCMR_88",
    "PER-2024-001",
    "species_price_list",
    "HARIPUR",
    "West_Pakistan_Land_Revenue_Act_1967",
]
p("\nQuality target presence in output folders:")
for t in targets:
    matches = [d for d in docs if t.lower() in d.lower()]
    p(f"  {t}: {matches if matches else 'NOT FOUND'}")

OUT.write_text("\n".join(lines), encoding="utf-8")
print(OUT.read_text(encoding="utf-8"))
