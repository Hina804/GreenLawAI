import sys
from pathlib import Path

# Setup paths
_this_file = Path(__file__).resolve()
_scratch_dir = _this_file.parent
_project_root = _scratch_dir.parent
_src_dir = _project_root / "src"

sys.path.insert(0, str(_src_dir))

print("Starting import tests...")

try:
    print("Importing case_retrieval_agent...")
    from agents.judiciary.case_retrieval_agent import CaseRetrievalAgent
    print("Importing legal_reasoning_agent...")
    from agents.judiciary.legal_reasoning_agent import LegalReasoningAgent
    print("Importing judgment_prediction_agent...")
    from agents.judiciary.judgment_prediction_agent import JudgmentPredictionAgent
    print("Importing evidence_analyzer_agent...")
    from agents.judiciary.evidence_analyzer_agent import EvidenceAnalyzerAgent
    print("Importing bail_analyzer_agent...")
    from agents.judiciary.bail_analyzer_agent import BailAnalyzerAgent
    print("Importing citation_validator_agent...")
    from agents.judiciary.citation_validator_agent import CitationValidatorAgent
    print("All imports successful!")
except Exception as e:
    print(f"FAILED with error: {e}")
    import traceback
    traceback.print_exc()
