import sys
import os
import yaml
from pathlib import Path

# Add src to sys.path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from core.registry_loader import ModuleLoader

def test_registry():
    reg_path = Path('src/core/regs/agent_registry.yaml')
    if not reg_path.exists():
        print(f"Error: {reg_path} not found")
        return

    with open(reg_path, 'r') as f:
        registry = yaml.safe_load(f).get('agents', {})

    print(f"--- Testing Agent Registry ({len(registry)} agents) ---")
    
    success_count = 0
    for aid, data in registry.items():
        print(f"Testing {aid}...", end=" ", flush=True)
        try:
            # Instantiate with sample injection
            inst = ModuleLoader.instantiate(
                data['module'], 
                data['class'], 
                component_id=aid, 
                config=data.get('config', {}), 
                llm_manager=None
            )
            if inst:
                print("OK")
                success_count += 1
            else:
                print("FAILED (returned None)")
        except Exception as e:
            print(f"FAILED (error: {e})")

    print(f"\nSummary: {success_count}/{len(registry)} agents loaded successfully.")
    if success_count == len(registry):
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    test_registry()
