"""Manual PyMuPDF smoke test (read-only on source PDF)."""
import os
import fitz  # PyMuPDF

pdf_path = r"E:\GL_AI\data_raw\forestry\federal\laws\forest_act_1927.pdf"

print(f"Testing PDF: {pdf_path}")
print(f"File exists: {os.path.exists(pdf_path)}")

doc = fitz.open(pdf_path)
print(f"Number of pages: {len(doc)}")

for page_num in range(min(3, len(doc))):
    page = doc[page_num]
    text = page.get_text()
    print(f"Page {page_num}: {len(text)} characters")
    if text:
        print(f"First 200 chars: {text[:200]}")

doc.close()
