import os
import sys
import logging
import asyncio
from fpdf import FPDF

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from data.case_ingestor import CaseIngestor
from agents.judiciary.case_retrieval_agent import CaseRetrievalAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_valid_test_pdf(path: str):
    """Generates a valid binary PDF for Phase 4 testing."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="IN THE PESHAWAR HIGH COURT, ABBOTTABAD BENCH", ln=True, align='C')
    pdf.ln(10)
    pdf.cell(200, 10, txt="State vs. Gul Khan", ln=True)
    pdf.cell(200, 10, txt="Case ID: PHC-2026-X01", ln=True)
    pdf.cell(200, 10, txt="Verdict: Guilty", ln=True)
    pdf.cell(200, 10, txt="Penalty: Rs. 250,000 fine for illegal timber transport.", ln=True)
    pdf.output(path)

async def run_bridge_validation():
    print("\n" + "="*50)
    print("🚀 GreenLawAI Judiciary: Bridge Validation (Real PDF)")
    print("="*50 + "\n")

    base_dir = os.path.join(os.path.dirname(__file__), "court_cases")
    incoming_dir = os.path.join(base_dir, "incoming")
    processed_file = os.path.join(base_dir, "processed", "mock_cases.json")
    
    os.makedirs(incoming_dir, exist_ok=True)
    
    test_pdf = os.path.join(incoming_dir, "phc_gul_khan_2026.pdf")
    create_valid_test_pdf(test_pdf)
    print(f"Phase 4: Created valid test PDF: {test_pdf}")

    # Initialize Ingestor
    ingestor = CaseIngestor(data_dir=base_dir, llm_manager=None) 
    
    # Process
    print("Phase 4: Extracting and Parsing...")
    ingestor.process_pdf_directory(incoming_dir)
    
    # Persist
    print("Phase 5: Saving to central knowledge base...")
    ingestor.save_to_disk(processed_file)
    
    # Search
    print("Phase 5: Verifying retrieval...")
    retriever = CaseRetrievalAgent(data_path=processed_file)
    from core.schemas import AudienceType
    
    # We search specifically for the newly added case title
    response = await retriever.run("Gul Khan Illegal Timber", retrieved_chunks=[], audience=AudienceType.JUDICIAL)
    
    print("\n" + "-"*30)
    print("AGENT RESPONSE:")
    print(response.response)
    print("-" * 30 + "\n")
    
    if "Gul Khan" in response.response:
        print("✅ PHASE 5 COMPLETE: Bridge validated end-to-end!")
    else:
        print("❌ PHASE 5 FAILED: Data not visible to agent.")

if __name__ == "__main__":
    asyncio.run(run_bridge_validation())
