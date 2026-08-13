
import os
import json
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DOC_IDS = [
    "DOC_20260214_130309_185aaa71",
    "DOC_20260214_094034_ffba3818",
    "DOC_20260213_225202_7bd9ef5f",
    "DOC_20260213_231607_b48d7a73",
    "DOC_20260213_231944_7124e462",
    "DOC_20260213_232319_e1eae640",
    "DOC_20260213_233138_bdc5720d",
    "DOC_20260213_233648_74b4b28c",
    "DOC_20260213_235022_6d622853",
    "DOC_20260214_001730_c9251636",
    "DOC_20260214_003025_0e6b0664",
    "DOC_20260214_003817_f8ef1724",
    "DOC_20260214_004424_65935823",
    "DOC_20260214_005011_7477507b",
    "DOC_20260214_010506_23b3640c",
    "DOC_20260214_011048_2fc4409c",
    "DOC_20260213_230426_ffba3818",
    "DOC_20260214_000232_69291d72",
    "DOC_20260214_092951_7bd9ef5f"
]

DATA_PROCESSED = Path("E:/GL_AI/data_processed/documents")

def audit_document(doc_id):
    doc_path = DATA_PROCESSED / doc_id
    if not doc_path.exists():
        logger.error(f"FAIL: Document directory not found: {doc_id}")
        return False

    # Check Phase 1
    p1 = doc_path / "phase_1/phase_1_extraction_summary.json"
    if not p1.exists():
        logger.error(f"FAIL: Phase 1 Missing for {doc_id}")
        return False
    try:
        with open(p1, 'r', encoding='utf-8') as f:
            d = json.load(f)
            # Check for native_text, extracted_text, or raw_text
            text_content = d.get('native_text') or d.get('extracted_text') or d.get('raw_text')
            if not text_content:
                 logger.warning(f"WARN: Phase 1 text empty for {doc_id}")
    except Exception as e:
        logger.error(f"FAIL: Phase 1 JSON invalid for {doc_id}: {e}")
        return False

    # Check Phase 4
    p4 = doc_path / "phase_4/phase_4_4_2_entities.json"
    if not p4.exists():
        logger.error(f"FAIL: Phase 4 Missing for {doc_id}")
        return False
    try:
        with open(p4, 'r', encoding='utf-8') as f:
            d = json.load(f)
            # Basic validation
            pass
    except Exception as e:
        logger.error(f"FAIL: Phase 4 JSON invalid for {doc_id}: {e}")
        return False
    
    # Check Phase 6
    p6 = doc_path / "phase_6/phase_6_6_4_chunks.json"
    if not p6.exists():
        logger.error(f"FAIL: Phase 6 Missing for {doc_id}")
        return False
    try:
        with open(p6, 'r', encoding='utf-8') as f:
            data = json.load(f)
            chunks = []
            if isinstance(data, list):
                chunks = data
            elif isinstance(data, dict) and 'chunks' in data:
                chunks = data['chunks']
            
            if len(chunks) == 0:
                 logger.warning(f"WARN: Phase 6 chunks empty for {doc_id}")
            else:
                logger.info(f"OK: {doc_id} - {len(chunks)} chunks")
    except Exception as e:
        logger.error(f"FAIL: Phase 6 JSON invalid for {doc_id}: {e}")
        return False

    return True

def main():
    logger.info("Starting Batch Audit for 19 Documents...")
    passed = 0
    failed = 0
    for doc_id in DOC_IDS:
        if audit_document(doc_id):
            passed += 1
        else:
            failed += 1
    
    logger.info(f"Audit Complete. Passed: {passed}, Failed: {failed}")

if __name__ == "__main__":
    main()
