
import pytesseract
from PIL import Image, ImageDraw, ImageFont
import fitz
import sys

print("Python:", sys.version)
print("PyMuPDF Version:", fitz.VersionBind)

# Create a dummy image with text
img = Image.new('RGB', (200, 100), color = (255, 255, 255))
d = ImageDraw.Draw(img)
d.text((10,10), "Hello World", fill=(0,0,0))

print("Testing Tesseract...")
try:
    text = pytesseract.image_to_string(img)
    print(f"OCR Result: '{text.strip()}'")
    if "Hello" in text:
        print("✅ Tesseract Works!")
    else:
        print("❌ Tesseract produced unexpected output.")
except Exception as e:
    print(f"❌ Tesseract Failed: {e}")
