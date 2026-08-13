import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from data.case_parser import AgenticParser
from data.court_schema import CourtCase

def test_parser_fallback():
    print("Testing AgenticParser with fallback rules...")
    parser = AgenticParser(llm_manager=None) # Force fallback
    
    sample_text = """
    IN THE PESHAWAR HIGH COURT, ABBOTTABAD BENCH
    State vs. Ahmad Gul
    Judgment Date: 15-05-2025
    Facts: The accused was caught cutting 40 Deodar trees in the protected forest of Kaghan.
    Verdict: The accused is found Guilty and sentenced to a fine of Rs. 150,000.
    """
    
    case = parser.parse_text(sample_text)
    
    if case and isinstance(case, CourtCase):
        print(f"Parser Success! Extracted Case ID: {case.case_id}")
        print(f"Extracted Title: {case.title}")
        print(f"Extracted Verdict: {case.verdict}")
        print(f"Extracted Fine: {case.penalty_amount_rs}")
        return True
    else:
        print("Parser Failed to return a valid CourtCase object.")
        return False

if __name__ == "__main__":
    test_parser_fallback()
