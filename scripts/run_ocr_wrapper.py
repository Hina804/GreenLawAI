
import sys
import os
import json
from pdfplumber import open as pdfopen

# Ensure src is in path
sys.path.append(os.path.join(os.getcwd(), 'src'))

try:
    from preprocessing_pipeline.extract_layout import LawPDFProcessor
    
    pdf_path = "e:/GL_AI/data_raw/forestry/kpk/laws/The-Khyber-Pakhtunkhwa-Forest-Amendment-Act-2022-Khyber-Pakhtunkhwa-Act-No.-XXXI-of-2022.pdf"
    output_path = "e:/GL_AI/data_processed/forestry/layout/ocr_test_2022.json"
    
    print(f"Wrapper: Starting extraction for {pdf_path}")
    
    print(f"Wrapper: Starting extraction for {pdf_path}")
    
    if not os.path.exists(pdf_path):
        print("Wrapper: File NOT found!")
        sys.exit(1)
    
    # Subclass to stop after 1 page
    class DebugProcessor(LawPDFProcessor):
        def extract_layout(self, pdf_path: str, output_path: str):
            # Simplified for debug
            result = []
            with pdfopen(pdf_path) as pdf:
                page = pdf.pages[0] # Just page 1
                print(f"  [DEBUG] Processing Page 1 only...")
                blocks = self.ocr_page_fallback(pdf_path, 0)
                if blocks:
                    result.append({"page": 1, "blocks": blocks})
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2)
            print(f"Wrapper: Saved {len(result)} pages to {output_path}")

    processor = DebugProcessor()
    processor.extract_layout(pdf_path, output_path)
    print("Wrapper: Extraction complete.")

except Exception as e:
    print(f"Wrapper Exception: {e}")
    import traceback
    traceback.print_exc()
