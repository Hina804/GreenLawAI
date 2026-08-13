
import os
import sys
import pytesseract
from PIL import Image
import fitz
import io
from pathlib import Path

# Try to find tesseract
def find_tesseract():
    common_paths = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe'
    ]
    for path in common_paths:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            return path
    return None

def test_ocr(pdf_path):
    print(f"Testing OCR on: {pdf_path}")
    tess_path = find_tesseract()
    print(f"Tesseract Path: {tess_path}")
    
    if not os.path.exists(pdf_path):
        print("ERROR: PDF file not found")
        return

    try:
        doc = fitz.open(pdf_path)
        print(f"PDF Pages: {len(doc)}")
        
        total_text = ""
        for i in range(len(doc)):
            page = doc.load_page(i)
            pix = page.get_pixmap(dpi=300)
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            
            text = pytesseract.image_to_string(img)
            print(f"Page {i+1} text length: {len(text)}")
            total_text += text + "\n\n"
            
        print(f"Total extracted text length: {len(total_text)}")
        
    except Exception as e:
        print(f"OCR Test Failed: {e}")

if __name__ == "__main__":
    test_pdf = Path("E:/GL_AI/data_raw/forestry/kpk/laws/The-Khyber-Pakhtunkhwa-Forest-Amendment-Act-2022-Khyber-Pakhtunkhwa-Act-No.-XXXI-of-2022.pdf")
    test_ocr(str(test_pdf))
