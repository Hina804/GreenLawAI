import os
import json
import pdfplumber
import zipfile
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

def safe_print(msg):
    try:
        print(msg)
    except:
        try:
            print(msg.encode('ascii', errors='replace').decode('ascii'))
        except:
            pass

def extract_text_from_pdf(path):
    text = ""
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages[:10]:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        safe_print(f"Error reading PDF {path}: {e}")
    return text

def extract_text_from_docx_no_lib(path):
    text = ""
    try:
        with zipfile.ZipFile(path) as z:
            content = z.read('word/document.xml')
            root = ET.fromstring(content)
            namespace = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            for para in root.findall('.//w:t', namespace):
                if para.text:
                    text += para.text + " "
    except Exception as e:
        safe_print(f"Error reading DOCX (no-lib) {path}: {e}")
    return text

def extract_text_from_pptx_no_lib(path):
    text = ""
    try:
        with zipfile.ZipFile(path) as z:
            slide_files = [f for f in z.namelist() if f.startswith('ppt/slides/slide')]
            for slide_f in slide_files:
                content = z.read(slide_f)
                root = ET.fromstring(content)
                namespace = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
                for t in root.findall('.//a:t', namespace):
                    if t.text:
                        text += t.text + " "
    except Exception as e:
        safe_print(f"Error reading PPTX (no-lib) {path}: {e}")
    return text

def extract_text_from_doc(path):
    text = ""
    try:
        with open(path, "rb") as f:
            content = f.read()
            readable = re.findall(rb"[a-zA-Z0-9\s,.]{8,}", content)
            text = " ".join([b.decode('ascii', errors='ignore') for b in readable])
    except Exception as e:
        safe_print(f"Error reading DOC {path}: {e}")
    return text

def run_extraction():
    data_raw = Path("e:/GL_AI/data_raw")
    results = []
    
    file_list = list(data_raw.rglob("*"))
    safe_print(f"Processing {len(file_list)} items...")
    
    for f_path in file_list:
        if not f_path.is_file():
            continue
            
        ext = f_path.suffix.lower()
        if ext not in [".pdf", ".docx", ".doc", ".pptx", ".txt"]:
            continue
            
        text = ""
        if ext == ".pdf":
            text = extract_text_from_pdf(f_path)
        elif ext == ".docx":
            text = extract_text_from_docx_no_lib(f_path)
        elif ext == ".pptx":
            text = extract_text_from_pptx_no_lib(f_path)
        elif ext == ".doc":
            text = extract_text_from_doc(f_path)
        elif ext == ".txt":
            try:
                text = f_path.read_text(encoding='utf-8', errors='ignore')
            except:
                pass
        
        if text.strip():
            clean_text = " ".join(text.split())
            results.append({
                "path": str(f_path),
                "name": f_path.name,
                "text": clean_text[:10000]
            })
            safe_print(f"  [OK] Extracted text from {f_path.name}")
        else:
            safe_print(f"  [WARN] No text found in {f_path.name}")

    output_path = Path("e:/GL_AI/scratch/extracted_corpus.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    safe_print(f"\nExtraction complete. Saved to {output_path}")

if __name__ == "__main__":
    run_extraction()
