"""Verify Phase 1 extraction after batch_processor fix (does not touch documents/)."""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "data_pipeline"))

from preprocessing_pipeline.phase_7_orchestration.batch_processor_v2 import KPKPipelineOrchestrator
from preprocessing_pipeline.common.config import load_config


async def main():
    pdf = ROOT / "data_raw" / "forestry" / "federal" / "laws" / "forest_act_1927.pdf"
    orch = KPKPipelineOrchestrator(load_config())
    from preprocessing_pipeline.phase_7_orchestration.batch_processor_v2 import PipelineContext
    from pathlib import Path as P

    ctx = PipelineContext(
        document_id=pdf.stem,
        file_path=pdf,
        metadata={},
    )
    await orch._execute_phase_0(ctx)
    await orch._execute_phase_1(ctx)
    p0 = ctx.results.get(0)
    if p0 and hasattr(p0, "data"):
        prof = p0.data.get("profile")
        pages = getattr(prof, "total_pages", None) if prof is not None else p0.data
        print("Phase 0 total_pages:", getattr(prof, "total_pages", pages) if prof is not None else "n/a")
    p1 = ctx.results.get(1)
    data = p1.data if hasattr(p1, "data") else {}
    raw = data.get("raw_text", "")
    meta = data.get("metadata", {})
    print("Phase 1 raw_text length:", len(raw))
    print("metadata:", meta)
    print("snippet:", raw[:200].replace("\n", " ") if raw else "(empty)")


if __name__ == "__main__":
    asyncio.run(main())
