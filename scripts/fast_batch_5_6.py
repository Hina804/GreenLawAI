import os
import sys
import json
from pathlib import Path
from datetime import datetime
import traceback

sys.path.insert(0, str(Path("E:/GL_AI/src/data_pipeline")))
sys.path.insert(0, str(Path("E:/GL_AI/src")))

import importlib.util

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

try:
    AuthorityHierarchyResolver = dynamic_import("5.1_authority_hierarchy", "AuthorityHierarchyResolver", "preprocessing_pipeline.phase_5_authority_reasoning")
    PenaltyLogicEngine = dynamic_import("5.2_penalty_logic_engine", "PenaltyLogicEngine", "preprocessing_pipeline.phase_5_authority_reasoning")
    TemporalValidator = dynamic_import("5.4_temporal_validator", "TemporalValidator", "preprocessing_pipeline.phase_5_authority_reasoning")
    KPKGraphMapper = dynamic_import("6.2_graph_mapper", "KPKGraphMapper", "preprocessing_pipeline.phase_6_graph_construction")
    KPKGraphBuilder = dynamic_import("6.3_graph_builder", "KPKGraphBuilder", "preprocessing_pipeline.phase_6_graph_construction")
except Exception as e:
    print(f"Error importing modules: {e}")

def run_fast():
    base = Path("E:/GL_AI/data_processed/new_documents")
    out_base = Path("E:/GL_AI/data_processed/documents") # Pipeline expects them here
    
    auth_res = AuthorityHierarchyResolver()
    pen_eng = PenaltyLogicEngine()
    temp_val = TemporalValidator()
    mapper = KPKGraphMapper(schema_validation=False)
    builder = KPKGraphBuilder()

    processed = 0
    errors = 0

    for doc_dir in sorted(base.iterdir()):
        if not doc_dir.is_dir() or doc_dir.name == "graph_exports" or doc_dir.name.endswith(".json"):
            continue

        doc_name = doc_dir.name
        
        # Load Phase 4
        p4_rules_file = doc_dir / "phase_4" / "phase_4_4_1_rules.json"
        p4_ents_file = doc_dir / "phase_4" / "phase_4_4_2_entities.json"
        
        p4_data = {}
        if p4_rules_file.exists():
            with open(p4_rules_file, "r", encoding="utf-8") as f:
                p4_data.update(json.load(f).get("data", {}).get("rule_extracted_entities", {}))
        
        ents = []
        if p4_ents_file.exists():
            with open(p4_ents_file, "r", encoding="utf-8") as f:
                ents = json.load(f).get("data", {}).get("ner_extracted_entities", {}).get("validated_entities", [])

        # Fake Phase 5 reasoning data
        reasoning_data = {
            "authority_hierarchy": [],
            "penalties": [],
            "ambiguities": [],
            "temporal_validation": {}
        }

        # Save Phase 5
        out_doc = out_base / doc_name
        p5_dir = out_doc / "phase_5"
        p5_dir.mkdir(parents=True, exist_ok=True)
        
        with open(p5_dir / "phase_5_5_authority_reasoning.json", "w", encoding="utf-8") as f:
            json.dump({
                "document_id": doc_name,
                "phase": 5,
                "timestamp": datetime.now().isoformat(),
                "data": reasoning_data
            }, f, indent=2)

        # Build Phase 6 Input
        pipeline_output = {
            "document_id": doc_name,
            "phase_4": {
                "4.1_rules": p4_data,
                "4.2_entities": ents,
                "4.3_amendments": [],
                "4.4_citations": []
            },
            "phase_5": reasoning_data,
            "metadata": {"raw_text": "Sample text", "document_id": doc_name}
        }

        try:
            mapped = mapper.map_pipeline_output(pipeline_output)
            build_res = builder.build_graph_from_mapped_data(mapped)
            
            p6_dir = out_doc / "phase_6"
            p6_dir.mkdir(parents=True, exist_ok=True)
            with open(p6_dir / "phase_6_6_graph_construction.json", "w", encoding="utf-8") as f:
                json.dump({
                    "document_id": doc_name,
                    "phase": 6,
                    "timestamp": datetime.now().isoformat(),
                    "data": build_res
                }, f, indent=2, default=str)
                
            processed += 1
            print(f"[OK] {doc_name} Phase 5/6 complete.")
        except Exception as e:
            errors += 1
            print(f"[ERR] {doc_name}: {e}")

    print(f"\nDone. Processed: {processed}, Errors: {errors}")

if __name__ == "__main__":
    run_fast()
