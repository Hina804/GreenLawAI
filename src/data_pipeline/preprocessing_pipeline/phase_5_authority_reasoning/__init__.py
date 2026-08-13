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

# 5.1
items_5_1 = ["AuthorityHierarchy", "AuthorityNode"]
loaded_5_1 = load_numeric("5.1_authority_hierarchy", items_5_1)
if loaded_5_1:
    AuthorityHierarchy, AuthorityNode = loaded_5_1

# 5.2
items_5_2 = ["PenaltyLogicEngine", "PenaltyCalculation"]
loaded_5_2 = load_numeric("5.2_penalty_logic_engine", items_5_2)
if loaded_5_2:
    PenaltyLogicEngine, PenaltyCalculation = loaded_5_2

# 5.3
items_5_3 = ["LLMAmbiguityResolver", "AmbiguityResolution"]
loaded_5_3 = load_numeric("5.3_llm_ambiguity_resolver", items_5_3)
if loaded_5_3:
    LLMAmbiguityResolver, AmbiguityResolution = loaded_5_3

# 5.4
items_5_4 = ["TemporalValidator", "TemporalConsistency"]
loaded_5_4 = load_numeric("5.4_temporal_validator", items_5_4)
if loaded_5_4:
    TemporalValidator, TemporalConsistency = loaded_5_4
