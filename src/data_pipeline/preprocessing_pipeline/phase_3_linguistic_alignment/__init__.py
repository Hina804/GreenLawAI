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

# 3.1
MultilingualHandler = load_numeric("3.1_multilingual_handler", "MultilingualHandler")

# 3.2
EnhancedKPFCircularParser = load_numeric("3.2_circular_parser", "EnhancedKPFCircularParser")

# 3.3
EnhancedKPKWorkingPlanParser = load_numeric("3.3_working_plan_parser", "EnhancedKPKWorkingPlanParser")

# 3.4
items_3_4 = ["KPKSectionDetector", "LegalSection"]
loaded_3_4 = load_numeric("3.4_section_detector", items_3_4)
if loaded_3_4:
    KPKSectionDetector, LegalSection = loaded_3_4
