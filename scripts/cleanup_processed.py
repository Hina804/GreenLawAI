
import shutil
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

DATA_PROCESSED = Path("e:/GL_AI/data_processed/documents")
ARCHIVE_DIR = Path("e:/GL_AI/data_archive/redundant_runs")

def cleanup():
    if not DATA_PROCESSED.exists():
        logger.error("Data processed directory not found")
        return

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    
    current_folders = [f for f in DATA_PROCESSED.iterdir() if f.is_dir()]
    logger.info(f"Found {len(current_folders)} folders in data_processed/documents")

    moved_count = 0
    for folder in current_folders:
        if folder.name not in DOC_IDS:
            logger.info(f"Moving redundant folder: {folder.name} to archive")
            try:
                shutil.move(str(folder), str(ARCHIVE_DIR / folder.name))
                moved_count += 1
            except Exception as e:
                logger.error(f"Failed to move {folder.name}: {e}")
    
    logger.info(f"Cleanup complete. Moved {moved_count} folders. Archive location: {ARCHIVE_DIR}")

if __name__ == "__main__":
    cleanup()
