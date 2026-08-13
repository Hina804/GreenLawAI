import sys
import os

# Add e:\GL_AI\src to path
sys.path.append(os.path.join("e:", os.sep, "GL_AI", "src"))

try:
    from agents.judiciary.case_retrieval_agent import CaseRetrievalAgent
    from agents.judiciary.fir_generator_agent import FIRGeneratorAgent
    from agents.judiciary.procedure_guide_agent import ProcedureGuideAgent
    from agents.judiciary.legal_reasoning_agent import LegalReasoningAgent
    from agents.judiciary.judgment_prediction_agent import JudgmentPredictionAgent
    from agents.judiciary.evidence_analyzer_agent import EvidenceAnalyzerAgent
    from agents.judiciary.bail_analyzer_agent import BailAnalyzerAgent
    
    config = {}
    agents = {
        "retrieval": CaseRetrievalAgent(config),
        "fir": FIRGeneratorAgent(config),
        "procedure": ProcedureGuideAgent(config),
        "reasoning": LegalReasoningAgent(config),
        "prediction": JudgmentPredictionAgent(config),
        "evidence": EvidenceAnalyzerAgent(config),
        "bail": BailAnalyzerAgent(config)
    }
    print("SUCCESS: All 7 Judiciary Agents initialized successfully.")
    
    # Check data file
    if os.path.exists("e:\\GL_AI\\src\\data\\court_cases\\processed\\mock_cases.json"):
        print("SUCCESS: mock_cases.json found and ready for analytics.")
    else:
        print("WARNING: mock_cases.json not found.")

except Exception as e:
    print(f"FAILURE: {e}")
    sys.exit(1)
