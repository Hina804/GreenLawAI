
"""
master_ingest_all.py - The "Super Command" for Law Ingestion

This script automates the entire GreenLawAI pipeline from raw PDF to Knowledge Graph.
Flow:
1. Process raw PDFs (Phases 1-4)
2. Generate embeddings and update Vector Store (Phase 5)
3. Connect entities and build Knowledge Graph (Neo4j)
4. Cleanup intermediate files and verify system.
"""

import os
import sys
import time
import subprocess
import shutil
from pathlib import Path
from datetime import datetime

# Setup Paths
ROOT = Path(__file__).parent.parent
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
# Raw Data Roots
RAW_ROOT = ROOT / "data_raw" / "forestry"
STRUCTURED_DIR = ROOT / "data_processed" / "forestry" / "structured"

# Script Paths
BATCH_PROCESSOR = SRC / "preprocessing_pipeline" / "batch_processor.py"
INDEX_DOCUMENTS = SCRIPTS / "index_documents.py"
SETUP_NEO4J = SCRIPTS / "setup_neo4j.py"
RUN_PIPELINE = SCRIPTS / "run_complete_pipeline.py"

def print_banner(text):
    print("\n" + "="*80)
    print(f">> {text.upper()}")
    print("="*80)

def run_step(name, script_path, args=None):
    print(f"\n>> STARTING STEP: {name}")
    print(f"  Script: {script_path.relative_to(ROOT)}")
    
    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)
    
    start_time = time.time()
    try:
        # We use run and don't capture output so the user sees live progress
        result = subprocess.run(cmd, check=True, cwd=str(ROOT))
        duration = time.time() - start_time
        print(f"[OK] STEP COMPLETE: {name} (Took {duration:.1f}s)")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[FAIL] STEP FAILED: {name}")
        print(f"   Error Code: {e.returncode}")
        return False

def main():
    print_banner("GreenLawAI Master Ingestion Orchestrator")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Root: {ROOT}")
    
    # Aggressive Cleanup for ChromaDB
    chroma_path = ROOT / "chroma_db_v3"
    if chroma_path.exists():
        print(f"  [!] Deleting existing ChromaDB at {chroma_path} to prevent corruption...")
        try:
            shutil.rmtree(chroma_path)
            print(f"  [OK] Deleted {chroma_path}")
        except Exception as e:
            print(f"  [ERR] Cleanup failed: {e}")

    # 1. Verification of Raw Data (Recursive Scan)
    print(f"  Scanning for laws in {RAW_ROOT}...")
    pdfs = []
    # Search in both federal and kpk subfolders
    for path in RAW_ROOT.rglob("*.pdf"):
        if "laws" in str(path).lower():
            pdfs.append(path)
    
    if not pdfs:
        print(f"[!] No PDFs found in any 'laws' subdirectory under {RAW_ROOT}")
        return 1
    
    print(f"Found {len(pdfs)} PDFs across all jurisdictions.")
    for pdf in pdfs:
        print(f"  - {pdf.relative_to(RAW_ROOT)}")
    
    # 2. Sequential Execution
    steps = [
        ("PDF Processing (Phases 1-4)", BATCH_PROCESSOR),
        ("Vector Indexing (Phase 5)", INDEX_DOCUMENTS),
        ("Knowledge Graph Import (Neo4j)", SETUP_NEO4J),
        ("Final Cleanup & Verification", RUN_PIPELINE, ["--non-interactive"])
    ]
    
    for i, (name, script, *args) in enumerate(steps, 1):
        actual_args = args[0] if args else None
        print_banner(f"STEP {i}/{len(steps)}: {name}")
        success = run_step(name, script, actual_args)
        if not success:
            print("\n" + "!"*80)
            print(f"CRITICAL FAILURE IN STEP {i} ({name})")
            print("Stopping pipeline to prevent data corruption.")
            print("!"*80)
            return 1
            
    print_banner("Master Ingestion Complete!")
    print("\nNext Steps:")
    print("1. Restart your Streamlit app: python -m streamlit run src/ui/app.py")
    print("2. Ask the AI questions about the new laws!")
    print("\nTip: If you encounter retrieval issues, ask 'Is Cheerh a reserved specie?' to test synonyms.")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
