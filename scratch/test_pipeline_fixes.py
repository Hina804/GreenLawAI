import asyncio
import sys
from pathlib import Path
import shutil

# Add src to path
sys.path.append(str(Path(r"E:\GL_AI\src")))

from data_pipeline.preprocessing_pipeline.phase_7_orchestration.batch_processor_v2 import KPKPipelineOrchestrator

async def test_fixes():
    # Initialize orchestrator
    orchestrator = KPKPipelineOrchestrator()
    
    test_files = [
        r"E:\GL_AI\data_raw\forestry\federal\laws\West_Pakistan_Land_Revenue_Act_1967.pdf",
        r"E:\GL_AI\data_raw\permits\historical\approved\PER-2024-001.json",
        r"E:\GL_AI\data_raw\permits\reference_data\species_price_list.csv"
    ]
    
    # Clear checkpoints first
    checkpoint_root = Path(r"e:\GL_AI\data_preprocessed\checkpoints")
    for file_path in test_files:
        doc_id = Path(file_path).stem
        shutil.rmtree(checkpoint_root / doc_id, ignore_errors=True)
    
    for file_path in test_files:
        print(f"\n--- Testing: {Path(file_path).name} ---")
        try:
            # Process with DAG enabled
            context = await orchestrator.process_document(file_path, use_dag=True)
            print(f"Status: {context.status}")
            for phase, result in context.results.items():
                # Handling both object and dict results
                status = getattr(result, 'status', 'unknown')
                if status == 'unknown' and isinstance(result, dict):
                    status = result.get('status', 'unknown')
                print(f"Phase {phase}: {status}")
        except Exception as e:
            print(f"FAILED for {Path(file_path).name}: {e}")

if __name__ == "__main__":
    asyncio.run(test_fixes())
