"""
Batch Space Recovery - Applies space recovery to all Phase 1 JSONs in new_documents.
"""
import json, sys, os
from pathlib import Path

sys.path.insert(0, str(Path("E:/GL_AI/src/data_pipeline/preprocessing_pipeline/utils")))
from space_recovery import SpaceRecoveryEngine

def run():
    base = Path("E:/GL_AI/data_processed/new_documents")
    engine = SpaceRecoveryEngine()
    fixed, skipped, errors = 0, 0, 0

    for doc_dir in sorted(base.iterdir()):
        if not doc_dir.is_dir():
            continue
        p1 = doc_dir / "phase_1" / "phase_1_1_extraction.json"
        if not p1.exists():
            continue
        try:
            with open(p1, "r", encoding="utf-8") as f:
                data = json.load(f)
            raw = data.get("data", {}).get("raw_text", "")
            if not raw or data.get("data", {}).get("space_recovery_applied"):
                skipped += 1
                continue
            recovered = engine.recover_spaces(raw)
            if recovered != raw:
                data["data"]["raw_text"] = recovered
                data["data"]["space_recovery_applied"] = True
                with open(p1, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                fixed += 1
                print(f"  [FIXED] {doc_dir.name}")
            else:
                skipped += 1
        except Exception as e:
            errors += 1
            print(f"  [ERROR] {doc_dir.name}: {e}")

    print(f"\n[DONE] Fixed: {fixed} | Skipped: {skipped} | Errors: {errors}")

if __name__ == "__main__":
    run()
