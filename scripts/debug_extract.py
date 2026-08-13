
import sys
import traceback

print("Attempting to import extract_layout...")
try:
    sys.path.append('src/preprocessing_pipeline')
    import extract_layout
    print("Import successful.")
except Exception:
    print("Import failed!")
    traceback.print_exc()
except SystemExit as e:
    print(f"SystemExit during import: {e}")
