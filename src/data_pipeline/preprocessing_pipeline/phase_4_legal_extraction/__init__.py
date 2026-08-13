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

# 4.1
items_4_1 = ["KPKRuleExtractor", "LegalRule"]
loaded_4_1 = load_numeric("4.1_rule_extractor", items_4_1)
if loaded_4_1:
    KPKRuleExtractor, LegalRule = loaded_4_1

# 4.2
LLMNERExtractor = load_numeric("4.2_ner_extractor", "LLMNERExtractor")

# 4.3
KPAmendmentTracker = load_numeric("4.3_amendment_tracker", "KPAmendmentTracker")

# 4.4
KPKCitationResolver = load_numeric("4.4_citation_resolver", "KPKCitationResolver")
