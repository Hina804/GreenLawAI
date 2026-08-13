import sys
import importlib.util
from pathlib import Path

def dynamic_import(module_name: str, class_name: str, package: str):
    base_dir = Path("E:/GL_AI/src/data_pipeline")
    package_path = package.replace(".", "/")
    file_path = base_dir / package_path / f"{module_name}.py"
    full_module_name = f"{package}.{module_name.replace('.', '_')}"
    spec = importlib.util.spec_from_file_location(full_module_name, str(file_path))
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = package
    spec.loader.exec_module(mod)
    return getattr(mod, class_name)

LLMNERExtractor = dynamic_import("4.2_ner_extractor", "LLMNERExtractor", "preprocessing_pipeline.phase_4_legal_extraction")

sys.path.insert(0, str(Path("E:/GL_AI/src")))
from agents.ollama_client import OllamaClient

llm = OllamaClient(model="llama3.2")
ex = LLMNERExtractor(llm_client=llm)

text = "The Divisional Forest Officer (DFO) fined Mr. Ali Rs. 50,000 for illegal logging."
res = ex.extract_with_assistance(text)

import json
print(json.dumps(res, indent=2))
