
import os
import json
from pathlib import Path

# The 19 target documents (shortened versions for lookup)
DOCS_TO_PERFECT = [
    "DOC_20260214_130311_185aaa71", # Act XXII 2022
    "DOC_20260214_092951_7bd9ef5f", # KPK Forest Act 2002
    "DOC_20260214_094034_ffba3818", # Forest Act 1927
    "DOC_20260214_095138_b48d7a73", # Env Protection Act 2014
    "DOC_20260214_095552_7124e462", # Wildlife Act 2015
    "DOC_20260214_095911_e1eae640", # NWFP Forest Corp Act 1980
    "DOC_20260214_100126_bdc5720d", # Amendment Act 2006
    "DOC_20260214_100316_74b4b28c", # Duty on Forest Produce Rules 2004
    "DOC_20260214_100925_6d622853", # Guzara Forest Rules 2004
    "DOC_20260214_101828_69291d72", # Protected Forest Rules 2005
    "DOC_20260214_102540_c9251636", # Transport Rules 2004
    "DOC_20260214_103408_0e6b0664", # Local Govt Act 2013
    "DOC_20260214_103609_f8ef1724", # Minerals Act 2017
    "DOC_20260214_104008_65935823", # River Protection Act 2014
    "DOC_20260214_104513_7477507b", # Land Acquisition Act 1894
    "DOC_20260214_105007_23b3640c", # Hazara Forest Act 1936
    "DOC_20260214_105249_2fc4409c", # Grazing Rules 1980
    "DOC_20260214_143927_913b92d8", # Final 18
    "DOC_20260214_144443_e738685c"  # Final 19
]

def audit():
    root = Path("E:/GL_AI/data_processed/documents")
    report = []
    
    for folder in root.iterdir():
        if not folder.is_dir(): continue
        # Find if this folder matches one of our IDs (using partial match as IDs vary slightly)
        match = False
        for target in DOCS_TO_PERFECT:
            if target in folder.name or folder.name in target:
                match = True
                break
        
        if not match: continue
        
        doc_report = {"id": folder.name, "issues": []}
        
        # Check OCR Text (Phase 1)
        ocr_path = folder / "phase_1/phase_1_1_5_ocr.json"
        if ocr_path.exists():
            try:
                with open(ocr_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    text = data.get("data", {}).get("raw_text", "")
                    doc_report["text_len"] = len(text)
                    if len(text) < 500: doc_report["issues"].append("Empty/Short OCR")
            except: doc_report["issues"].append("OCR corrupted")
        else: doc_report["issues"].append("OCR Missing")

        # Check Entities (Phase 4)
        ent_path = folder / "phase_4/phase_4_4_2_ner.json"
        if ent_path.exists():
            try:
                with open(ent_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    ents = data.get("data", {}).get("llm_suggested_entities", [])
                    doc_report["ent_count"] = len(ents)
                    if len(ents) == 0: doc_report["issues"].append("Zero Entities")
            except: doc_report["issues"].append("NER corrupted")
        else: doc_report["issues"].append("NER Missing")

        # Check Chunks (Phase 6)
        chunk_path = folder / "phase_6/phase_6_6_4_chunks.json"
        if chunk_path.exists():
            try:
                with open(chunk_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    chunks = data.get("data", {}).get("chunks", [])
                    doc_report["chunk_count"] = len(chunks)
                    if len(chunks) == 0: doc_report["issues"].append("Zero Chunks")
            except: doc_report["issues"].append("Chunks corrupted")
        else: doc_report["issues"].append("Chunks Missing")
        
        report.append(doc_report)

    with open("data_perfection_audit.json", "w") as f:
        json.dump(report, f, indent=2)

if __name__ == "__main__":
    audit()
