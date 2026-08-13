import importlib.util
from pathlib import Path
import sys

def load_numeric(file_name, class_name):
    base_dir = Path(__file__).parent
    file_path = base_dir / f"{file_name}.py"
    if not file_path.exists():
        return None
    sanitized_name = file_name.replace(".", "_")
    spec = importlib.util.spec_from_file_location(sanitized_name, str(file_path))
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = __name__
    spec.loader.exec_module(mod)
    
    if isinstance(class_name, list):
        return [getattr(mod, c, None) for c in class_name]
    return getattr(mod, class_name, None)

# 1.1
KPKPDFParser = load_numeric("1.1_pdf_parser", "KPKPDFParser")
PDFParseResult = load_numeric("1.1_pdf_parser", "PDFParseResult")
PDFPage = load_numeric("1.1_pdf_parser", "PDFPage")
TextBlock = load_numeric("1.1_pdf_parser", "TextBlock")

# 1.2
LayoutExtractor = load_numeric("1.2_extract_layout", "LayoutExtractor")
DocumentLayout = load_numeric("1.2_extract_layout", "DocumentLayout")
PageLayout = load_numeric("1.2_extract_layout", "PageLayout")
LayoutElement = load_numeric("1.2_extract_layout", "LayoutElement")
LayoutElementType = load_numeric("1.2_extract_layout", "LayoutElementType")

# 1.3
TableExtractor = load_numeric("1.3_table_extractor", "TableExtractor")
ExtractedTable = load_numeric("1.3_table_extractor", "ExtractedTable")
ImageProcessor = load_numeric("1.4_image_processor", "ImageProcessor")

# 1.5
KPKOCREngine = load_numeric("1.5_ocr_engine", "KPKOCREngine")
KPKOCRCorrector = load_numeric("1.5_ocr_engine", "KPKOCRCorrector")
OCRPageResult = load_numeric("1.5_ocr_engine", "OCRPageResult")
OCREngineResult = load_numeric("1.5_ocr_engine", "OCREngineResult")
OCRResult = OCREngineResult

# 1.6
KPKOCRTrainer = load_numeric("1.6_kpk_ocr_trainer", "KPKOCRTrainer")
KPKFontDatabase = load_numeric("1.6_kpk_ocr_trainer", "KPKFontDatabase")
