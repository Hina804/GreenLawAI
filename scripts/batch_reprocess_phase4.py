"""
Batch Phase 4 Re-processor - Re-runs legal extraction on space-recovered documents.
"""
import json, sys, os, traceback
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path("E:/GL_AI/src/data_pipeline")))
sys.path.insert(0, str(Path("E:/GL_AI/src")))

def run():
    base = Path("E:/GL_AI/data_processed/new_documents")
    fixed, skipped, errors = 0, 0, 0

    # Lazy-load extractors once
    rule_ext = None
    ner_ext = None
    try:
        from preprocessing_pipeline.phase_4_legal_extraction import KPKRuleExtractor, LLMNERExtractor
        rule_ext = KPKRuleExtractor()
        ner_ext = LLMNERExtractor()
        print("[OK] Phase 4 extractors loaded.")
    except Exception as e:
        print(f"[WARN] Could not load extractors: {e}")
        print("[FALLBACK] Will use standalone regex extraction.")

    for doc_dir in sorted(base.iterdir()):
        if not doc_dir.is_dir():
            continue

        p1_file = doc_dir / "phase_1" / "phase_1_1_extraction.json"
        if not p1_file.exists():
            continue

        # Only re-process documents that had space recovery applied
        try:
            with open(p1_file, "r", encoding="utf-8") as f:
                p1_data = json.load(f)
        except:
            continue

        if not p1_data.get("data", {}).get("space_recovery_applied", False):
            skipped += 1
            continue

        raw_text = p1_data.get("data", {}).get("raw_text", "")
        if not raw_text or len(raw_text) < 50:
            skipped += 1
            continue

        doc_name = doc_dir.name
        doc_meta = {
            "document_id": doc_name,
            "source_doc_id": doc_name,
            "file_name": doc_name,
            "document_type": _detect_doc_type(doc_name),
            "jurisdiction": "KPK",
        }

        try:
            # Phase 4.1: Rule-based extraction
            phase4_dir = doc_dir / "phase_4"
            phase4_dir.mkdir(exist_ok=True)

            if rule_ext:
                rules_result = rule_ext.extract_all_entities(raw_text, doc_meta)
            else:
                rules_result = _fallback_extraction(raw_text, doc_meta)

            rules_output = {
                "document_id": doc_name,
                "phase": "4.1",
                "timestamp": datetime.now().isoformat(),
                "data": {
                    "rule_extracted_entities": rules_result,
                    "reprocessed": True,
                    "space_recovery_applied": True,
                }
            }
            with open(phase4_dir / "phase_4_4_1_rules.json", "w", encoding="utf-8") as f:
                json.dump(rules_output, f, indent=2, ensure_ascii=False, default=str)

            # Phase 4.2: NER extraction
            if ner_ext:
                ner_result = ner_ext.extract_with_assistance(raw_text, doc_meta)
            else:
                ner_result = {"fallback": True, "entities": []}

            ner_output = {
                "document_id": doc_name,
                "phase": "4.2",
                "timestamp": datetime.now().isoformat(),
                "data": {
                    "ner_extracted_entities": ner_result,
                    "reprocessed": True,
                    "space_recovery_applied": True,
                }
            }
            with open(phase4_dir / "phase_4_4_2_entities.json", "w", encoding="utf-8") as f:
                json.dump(ner_output, f, indent=2, ensure_ascii=False, default=str)

            fixed += 1
            print(f"  [OK] {doc_name}")

        except Exception as e:
            errors += 1
            print(f"  [ERR] {doc_name}: {e}")

    print(f"\n[DONE] Re-processed: {fixed} | Skipped: {skipped} | Errors: {errors}")


def _detect_doc_type(name):
    nl = name.lower()
    if any(x in nl for x in ["scmr", "pld", "court", "case", "vs", "clc", "ylr", "cpla", "phc", "lhc"]):
        return "court_case"
    if "working plan" in nl:
        return "working_plan"
    if "per-" in nl:
        return "permit"
    if any(x in nl for x in ["act", "ordinance", "rules"]):
        return "legislation"
    return "general"


def _fallback_extraction(text, meta):
    """Minimal regex extraction when the full extractor can't load."""
    import re
    sections = [m.group(1) for m in re.finditer(r'Section\s+(\d+[A-Z]?)', text, re.I)]
    fines = [m.group(1) for m in re.finditer(r'Rs\.?\s*([\d,]+)', text)]
    officers = [m.group() for m in re.finditer(r'\b(?:DFO|SDFO|Range Officer|Forest Guard)\b', text, re.I)]
    return {
        "legal_sections": [{"section_number": s} for s in set(sections)],
        "penalties": [{"amount": f} for f in set(fines[:20])],
        "officers": [{"title": o} for o in set(officers)],
        "fallback_mode": True,
    }


if __name__ == "__main__":
    run()
