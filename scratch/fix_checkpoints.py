
import json, dataclasses, datetime, os
from pathlib import Path
from enum import Enum

class ProcessingStatus(Enum):
    PENDING = 'pending'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'
    SKIPPED = 'skipped'
    PARTIAL = 'partial'

@dataclasses.dataclass
class PhaseResult:
    status: ProcessingStatus
    data: dict
    metrics: dict
    warnings: list
    errors: list
    duration_seconds: float
    timestamp: datetime.datetime

def handle_enums(obj):
    if isinstance(obj, dict): return {k: handle_enums(v) for k, v in obj.items()}
    if isinstance(obj, list): return [handle_enums(i) for i in obj]
    if isinstance(obj, Enum): return obj.value
    if isinstance(obj, datetime.datetime): return obj.isoformat()
    return obj

root = Path('e:/GL_AI/data_preprocessed/checkpoints')
print(f"Scanning {root}...")
for p in root.glob('**/*.json'):
    if '_1_ocr.json' in p.name:
        try:
            with open(p, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data.get('data'), str) and 'PhaseResult' in data['data']:
                print(f'Fixing {p}')
                s = data['data']
                # Clean up the repr string to be eval-able
                s = s.replace("<ProcessingStatus.COMPLETED: 'completed'>", "ProcessingStatus.COMPLETED")
                s = s.replace("<ProcessingStatus.FAILED: 'failed'>", "ProcessingStatus.FAILED")
                
                res = eval(s, {'PhaseResult': PhaseResult, 'ProcessingStatus': ProcessingStatus, 'datetime': datetime})
                data['data'] = handle_enums(dataclasses.asdict(res))
                with open(p, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
            else:
                print(f"Already fixed or compatible: {p.name}")
        except Exception as e:
            print(f'Error fixing {p.name}: {e}')
    else:
        # Delete Phase 2-6 checkpoints
        print(f'Deleting {p.name}')
        try:
            os.remove(p)
        except:
            pass

# Also clean up empty pipeline_summary files or those with 0 text
processed_root = Path('e:/GL_AI/data_processed/new_documents')
for p in processed_root.glob('**/pipeline_summary.json'):
    try:
        with open(p, 'r', encoding='utf-8') as f:
            summary = json.load(f)
        
        # Check if it was a failed run (0 chunks in index or 0 text)
        # Actually, just delete them all to be safe and let them re-run from Phase 2
        print(f"Deleting summary {p}")
        os.remove(p)
    except:
        pass
