"""Smoke test: one PDF through isolated new_documents pipeline."""
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "data_pipeline"))

from run_new_documents_pipeline import (
    NEW_DOCS_OUTPUT_DIR,
    save_phase_output_isolated,
    save_pipeline_summary,
)


async def main():
    pdf = ROOT / "data_raw" / "forestry" / "federal" / "laws" / "forest_act_1927.pdf"
    from preprocessing_pipeline.phase_7_orchestration.batch_processor_v2 import (
        KPKPipelineOrchestrator,
    )

    print(f"Smoke test file: {pdf}")
    orch = KPKPipelineOrchestrator()
    ctx = await orch.process_document(str(pdf), use_dag=True)

    for phase_num in range(8):
        if phase_num in ctx.results:
            await save_phase_output_isolated(ctx, phase_num)

    save_pipeline_summary(ctx, pdf, success=True)

    p1_path = NEW_DOCS_OUTPUT_DIR / ctx.document_id / "phase_1" / "phase_1_1_extraction.json"
    if not p1_path.exists():
        print("FAIL: phase_1 file not written")
        sys.exit(1)

    data = json.loads(p1_path.read_text(encoding="utf-8"))
    raw = data.get("data", {}).get("raw_text", "")
    meta = data.get("data", {}).get("metadata", {})
    print("document_id:", ctx.document_id)
    print("raw_text length:", len(str(raw).strip()))
    print("metadata:", meta)
    if len(str(raw).strip()) < 100:
        print("FAIL: raw_text still empty")
        sys.exit(1)
    print("PASS: Phase 1 has extracted text")


if __name__ == "__main__":
    asyncio.run(main())
