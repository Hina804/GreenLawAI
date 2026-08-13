"""
Unified Ingestion Pipeline (Colab & Local)
Orchestrates the full PDF -> Knowledge Graph pipeline.
"""

import sys
import os
from pathlib import Path
import shutil

# Add src to path (works for both local and Colab)
ROOT = Path(os.getcwd())
if ROOT.name == "scripts":
    ROOT = ROOT.parent
    
# Add src directory to Python path
src_path = ROOT / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

try:
    from preprocessing_pipeline.extract_layout import LawPDFProcessor
    from preprocessing_pipeline.normalize_text import run_normalizer
    from preprocessing_pipeline.normalize_split import run_splitter
    from preprocessing_pipeline.structure_detector import process_file as run_structure
    
    # Add root to path for scripts
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from scripts.index_documents import main as run_indexing
except ImportError as e:
    print(f"Import Error: {e}")
    print(f"Current directory: {os.getcwd()}")
    print(f"Python path: {sys.path}")
    print("Make sure you are running this from the project root.")
    sys.exit(1)

def main():
    # 1. Setup Paths
    # We assume we are in the project root or scripts folder
    ROOT = Path(os.getcwd())
    if ROOT.name == "scripts":
        ROOT = ROOT.parent
        
    DATA_RAW = ROOT / "data_raw"
    DATA_PROCESSED = ROOT / "data_processed"
    
    print(f"🚀 Starting Ingestion Pipeline")
    print(f"   Root: {ROOT}")
    print(f"   Raw Data: {DATA_RAW}")
    
    # 2. Find all PDFs recursively
    pdfs = list(DATA_RAW.rglob("*.pdf"))
    if not pdfs:
        print("❌ No PDFs found in data_raw!")
        return

    print(f"   Found {len(pdfs)} PDFs to process.")
    
    # 3. Process each PDF
    processor = LawPDFProcessor()
    
    for i, pdf in enumerate(pdfs):
        print(f"\n[{i+1}/{len(pdfs)}] Processing: {pdf.name}")
        
        # Determine category (forestry/climate) from path
        # e.g. data_raw/forestry/kpk/laws/Act.pdf -> category=forestry
        try:
            rel_path = pdf.relative_to(DATA_RAW)
            category = rel_path.parts[0] # 'forestry' or 'climate'
        except:
            category = "general"
            
        # Setup output dirs for this category
        layout_dir = DATA_PROCESSED / category / "layout"
        norm_dir = DATA_PROCESSED / category / "normalized"
        struct_dir = DATA_PROCESSED / category / "structured"
        
        for d in [layout_dir, norm_dir, struct_dir]:
            d.mkdir(parents=True, exist_ok=True)
            
        # Define file paths
        layout_json = layout_dir / f"{pdf.stem}_layout.json"
        
        # --- Phase 1: Layout ---
        if not layout_json.exists():
            print("   Phase 1: Layout Extraction...")
            processor.extract_layout(str(pdf), str(layout_json))
        else:
            print("   Phase 1: Skipped (Already exists)")
            
        # --- Phase 2: Normalize ---
        print("   Phase 2: Normalization...")
        run_normalizer(layout_json, norm_dir)
        
        # --- Phase 3: Split ---
        # Output of Phase 2 is <stem>_normalized.json
        norm_json = norm_dir / f"{pdf.stem}_normalized.json"
        print("   Phase 3: Splitting...")
        run_splitter(norm_json, norm_dir)
        
        # --- Phase 4: Structure Detection (with ATC fallback) ---
        # Output of Phase 3 is <stem>_split.json
        # ATC (Adaptive Tiered Chunking) will automatically:
        #   - Try regex-based detection first (Tier 1)
        #   - Fall back to paragraph chunking if needed (Tier 2)
        #   - Use fixed-size chunking as last resort (Tier 3)
        split_json = norm_dir / f"{pdf.stem}_split.json"
        print("   Phase 4: Structure Detection...")
        run_structure(split_json, struct_dir)
        
    print(f"\n✅ Preprocessing Complete!")
    
    # 4. Run Indexing
    print(f"\n🚀 Starting Vector Indexing...")
    
    # Index Forestry
    forestry_struct = DATA_PROCESSED / "forestry" / "structured"
    if forestry_struct.exists():
        print("   Indexing Forestry...")
        run_indexing(input_dir=str(forestry_struct), persist_dir=str(ROOT / "chroma_db"))
        
    # Index Climate
    climate_struct = DATA_PROCESSED / "climate" / "structured"
    if climate_struct.exists():
        print("   Indexing Climate...")
        run_indexing(input_dir=str(climate_struct), persist_dir=str(ROOT / "chroma_db"))
        
    print(f"\n🎉 INGESTION COMPLETE!")

if __name__ == "__main__":
    main()
