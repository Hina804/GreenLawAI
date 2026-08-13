import sys
import os
import yaml
from pathlib import Path
import importlib

# Add src to sys.path
# Insert src at the BEGINNING of sys.path to avoid conflicts with installed packages (like 'agents')
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))

from core.contracts import BasePipelineComponent

def fast_verify():
    reg_path = Path('src/core/regs/agent_registry.yaml')
    with open(reg_path, 'r') as f:
        registry = yaml.safe_load(f).get('agents', {})

    print(f"--- Fast Contract Verification ({len(registry)} agents) ---")
    
    success_count = 0
    for aid, data in registry.items():
        print(f"Checking {aid}...", end=" ", flush=True)
        try:
            module = importlib.import_module(data['module'])
            cls = getattr(module, data['class'])
            if issubclass(cls, BasePipelineComponent):
                print("OK")
                success_count += 1
            else:
                print("FAILED: Does not inherit from BasePipelineComponent")
        except Exception:
            import traceback
            print(f"FAILED")
            traceback.print_exc()

    print(f"\nSummary: {success_count}/{len(registry)} agents passed.")
    sys.exit(0 if success_count == len(registry) else 1)

if __name__ == "__main__":
    fast_verify()
