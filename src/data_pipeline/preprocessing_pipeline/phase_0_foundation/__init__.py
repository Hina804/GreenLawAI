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

# 0.1_doc_profiler
KPKDocumentProfiler = load_numeric("0.1_doc_profiler", "KPKDocumentProfiler")
DocProfiler = KPKDocumentProfiler
DocumentProfile = load_numeric("0.1_doc_profiler", "DocumentProfile")

# 0.2_kpk_metadata_enricher
KPKMetadataEnricher = load_numeric("0.2_kpk_metadata_enricher", "KPKMetadataEnricher")

# 0.3_abstention_log
abstention_items = ["AbstentionLogger", "AbstentionType", "AbstentionSeverity", "PipelineStage", "create_abstention_context", "AbstentionContext"]
loaded_abstention = load_numeric("0.3_abstention_log", abstention_items)
if loaded_abstention:
    AbstentionLogger, AbstentionType, AbstentionSeverity, PipelineStage, create_abstention_context, AbstentionContext = loaded_abstention
    AbstentionLog = AbstentionLogger

# 0.4_doc_quality_assessor
items_0_4 = ["DocQualityAssessor", "QualityAssessment", "ProcessingDecision", "QualityCategory"]
loaded_0_4 = load_numeric("0.4_doc_quality_assessor", items_0_4)
if loaded_0_4:
    DocQualityAssessor, QualityAssessment, ProcessingDecision, QualityCategory = loaded_0_4
    DocumentQualityAssessor = DocQualityAssessor
