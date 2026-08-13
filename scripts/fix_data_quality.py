
import json
import os
import re
import glob

DOCS_DIR = r"e:\GL_AI\data_processed\documents"

# Common OCR fix patterns
OCR_CORRECTIONS = [
    (r"\bGO1IERNMENT\b", "GOVERNMENT"),
    (r"\bGovt\b", "Government"),
    (r"\bPeshawar\b", "Peshawar"), # Verify capitalization
    (r"Tm]RSDAE", "Thursday"), # Example from user
    (r"REGiSTEREf't'l", "REGISTERED"),
    (r"\bKHreER\b", "Khyber"),
    (r"\bPAIffiTT]NKITT\+'A\b", "Pakhtunkhwa"),
    (r"\bKPK\b", "Khyber Pakhtunkhwa"), # Standardization
]

def clean_text(text):
    for pattern, replacement in OCR_CORRECTIONS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text

def extract_metadata(text):
    # Try to find Chapter/Section
    meta = {}
    
    # Section
    sec_match = re.search(r"^(Section\s+\d+|Article\s+\d+)", text, re.MULTILINE | re.IGNORECASE)
    if sec_match:
        meta['start_section'] = sec_match.group(1)
    
    # Chapter
    chap_match = re.search(r"^(Chapter\s+[IVX]+|Part\s+[IVX]+)", text, re.MULTILINE | re.IGNORECASE)
    if chap_match:
        meta['chapter'] = chap_match.group(1)
        
    return meta

def fix_documents():
    print("Starting Data Quality Fixes...")
    
    chunk_files = glob.glob(os.path.join(DOCS_DIR, "*", "phase_6", "phase_6_6_4_chunks.json"))
    
    for file_path in chunk_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                chunks = json.load(f)
            
            updated = False
            for chunk in chunks:
                if not isinstance(chunk, dict): continue
                
                original_text = chunk.get("chunk_text", "")
                
                # 1. Fix OCR
                new_text = clean_text(original_text)
                if new_text != original_text:
                    chunk["chunk_text"] = new_text
                    updated = True
                
                # 2. Enrich Metadata
                metadata = chunk.get("metadata", {})
                if metadata.get("section_id") == "auto_extracted":
                    extra_meta = extract_metadata(new_text)
                    if extra_meta:
                        metadata.update(extra_meta)
                        if "start_section" in extra_meta:
                            metadata["section_id"] = extra_meta["start_section"]
                        updated = True
                
                chunk["metadata"] = metadata

            if updated:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(chunks, f, indent=2)
                # print(f"Fixed chunks in: {file_path}")
        
        except Exception as e:
            print(f"Error processing chunks {file_path}: {e}")

    # 3. Check Entities
    entity_files = glob.glob(os.path.join(DOCS_DIR, "*", "phase_4", "phase_4_4_2_entities.json"))
    for file_path in entity_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # If validated is empty but suggestions exist, promote suggestions
            if not data.get("validated_entities") and data.get("llm_suggestions"):
                data["validated_entities"] = data["llm_suggestions"]
                data["statistics"]["validated_count"] = len(data["validated_entities"])
                
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                print(f"Restored entities from suggestions in: {file_path}")

        except Exception as e:
            print(f"Error processing entities {file_path}: {e}")

    print("Data Quality Fixes Complete.")

if __name__ == "__main__":
    fix_documents()
