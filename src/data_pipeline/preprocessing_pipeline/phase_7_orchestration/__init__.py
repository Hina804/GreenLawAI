import importlib.util
from pathlib import Path
import sys

def load_numeric(file_name, class_name):
    base_dir = Path(__file__).parent
    file_path = base_dir / f"{file_name}.py"
    if not file_path.exists():
        return None
    sanitized_name = file_name.replace(".", "_")
    spec = importlib.util.spec_from_file_location(sanitized_name, str(file_path))
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = __name__
    spec.loader.exec_module(mod)
    
    if isinstance(class_name, list):
        return [getattr(mod, c, None) for c in class_name]
    return getattr(mod, class_name, None)

# 7.1
BatchProcessor = load_numeric("batch_processor_v2", "KPKPipelineOrchestrator")
KPKPipelineOrchestrator = BatchProcessor

# Export classes for other modules
from .batch_processor_v2 import PhaseResult, PipelineContext
from preprocessing_pipeline.common.constants import ProcessingStatus

# 7.2
items_7_2 = ["KPKQualityGateManager", "QualityReport", "GateResult"]
loaded_7_2 = load_numeric("7.2_quality_gates", items_7_2)
if loaded_7_2:
    KPKQualityGateManager, QualityReport, GateResult = loaded_7_2
    QualityGateManager = KPKQualityGateManager

