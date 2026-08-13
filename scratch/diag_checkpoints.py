
import json
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class ProcessingStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ABSTAINED = "abstained"

@dataclass
class PhaseResult:
    status: ProcessingStatus
    data: dict
    metrics: dict = None
    warnings: list = None
    errors: list = None
    duration_seconds: float = 0.0
    timestamp: datetime = None

def diagnostic():
    checkpoint_file = Path("e:/GL_AI/data_preprocessed/checkpoints/The NWFP Police Rules 1937 reduced size/The NWFP Police Rules 1937 reduced size_1_ocr.json")
    
    with open(checkpoint_file, 'r', encoding='utf-8') as f:
        checkpoint_data = json.load(f)
    
    # Simulate pipeline_dag_wrapper logic
    task_result = checkpoint_data.get('data')
    
    phase_result = PhaseResult(
        status=ProcessingStatus(task_result.get('status', 'completed')),
        data=task_result.get('data', {}),
        metrics=task_result.get('metrics', {}),
        warnings=task_result.get('warnings', []),
        errors=task_result.get('errors', []),
        duration_seconds=task_result.get('duration_seconds', 0),
        timestamp=datetime.now()
    )
    
    print(f"Phase Result Status: {phase_result.status}")
    print(f"Data keys: {list(phase_result.data.keys())}")
    
    raw_text = phase_result.data.get("raw_text", "")
    print(f"Raw text length: {len(raw_text)}")
    
    if not raw_text:
        print("CRITICAL: Raw text is empty!")

if __name__ == "__main__":
    diagnostic()
