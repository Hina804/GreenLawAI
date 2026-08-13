"""Fast smoke test: Phase 1 only (no DAG checkpoints)."""
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "data_pipeline"))

from preprocessing_pipeline.common.config import load_config
from preprocessing_pipeline.phase_7_orchestration.batch_processor_v2 import (
    KPKPipelineOrchestrator,
    PipelineContext,
)
from run_new_documents_pipeline import save_phase_output_isolated


async def main():
    pdf = ROOT / "data_raw" / "forestry" / "federal" / "laws" / "forest_act_1927.pdf"
    cfg = load_config()
    orch = KPKPipelineOrchestrator()
    ctx = PipelineContext(
        document_id=pdf.stem,
        file_path=pdf,
        config=cfg,
    )
    await orch._execute_phase_1(ctx)
    await save_phase_output_isolated(ctx, 1)

    p1 = ROOT / "data_processed" / "new_documents" / pdf.stem / "phase_1" / "phase_1_1_extraction.json"
    data = json.loads(p1.read_text(encoding="utf-8"))
    raw = data.get("data", {}).get("raw_text", "")
    meta = data.get("data", {}).get("metadata", {})
    n = len(str(raw).strip())
    print("raw_text length:", n)
    print("metadata:", meta)
    if n < 100:
        sys.exit(1)
    print("PASS")


if __name__ == "__main__":
    asyncio.run(main())
