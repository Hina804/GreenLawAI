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

# 2.1
items_2_1 = ["LLMTextSanitizer", "SanitizationResult"]
loaded_2_1 = load_numeric("2.1_llm_text_sanitizer", items_2_1)
if loaded_2_1:
    LLMTextSanitizer, SanitizationResult = loaded_2_1

# 2.2
MultilingualSegmenter = load_numeric("2.2_multilingual_segmenter", "MultilingualSegmenter")
