import os
import json
import re
from typing import List, Dict, Any, Optional
from loguru import logger
from pydantic import ValidationError

from data.court_schema import CourtCase

try:
    from pypdf import PdfReader
except ImportError:
    # Fallback for older environments
    from PyPDF2 import PdfReader

class PDFExtractor:
    """Handles raw text extraction from PDF files."""
    
    @staticmethod
    def extract_text(file_path: str) -> str:
        """Extracts all text from a PDF file."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF not found: {file_path}")
            
        try:
            reader = PdfReader(file_path)
            full_text = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    full_text.append(text)
            return "\n".join(full_text)
        except Exception as e:
            logger.error(f"Failed to extract text from {file_path}: {e}")
            return ""

class AgenticParser:
    """Agentic layer that uses LLM to structure legal text into CourtCase schema."""
    
    def __init__(self, llm_manager=None):
        self.llm = llm_manager
        
    def _create_parsing_prompt(self, text: str) -> str:
        return f"""
        TASK: Parse the following legal judgment text into a structured JSON format matching the CourtCase schema.
        
        JUDGMENT TEXT:
        {text[:6000]}  # Limit to avoid token overflow
        
        SCHEMA REQUIREMENTS:
        - case_id: Unique ID (e.g., SC-2024-123)
        - title: Case name (e.g., State vs. X)
        - court_level: Supreme Court, High Court, or Session Court
        - court_name: Full name of the court
        - bench: List of judge names
        - judgment_date: YYYY-MM-DD
        - citation: Legal citation (e.g., 2024 SCMR 12)
        - law_sections: List of sections (e.g., ['26-A', '33'])
        - offense_category: Illegal Logging, Forest Fire, etc.
        - offense_details: Brief fact summary
        - location: Tehsil/District
        - is_night_violation: boolean
        - verdict: Guilty, Not Guilty, or Dismissed
        - penalty_amount_rs: Integer fine
        - imprisonment_months: Integer duration
        
        OUTPUT FORMAT: Strict JSON only.
        """

    def parse_text(self, text: str) -> Optional[CourtCase]:
        """Uses LLM to transform text into CourtCase object."""
        if not text:
            return None
            
        prompt = self._create_parsing_prompt(text)
        
        try:
            # If no real LLM provided, we return a structured mock (fallback)
            if not self.llm:
                logger.warning("[AgenticParser] No LLMManager provided. Using rule-based fallback parsing.")
                return self._fallback_rule_parsing(text)
            
            # Call LLM
            response_chunks = list(self.llm.generate(prompt, stream=False))
            raw_json = "".join(response_chunks)
            
            # Clean JSON if LLM added markdown blocks
            json_match = re.search(r'\{.*\}', raw_json, re.DOTALL)
            if json_match:
                raw_json = json_match.group(0)
                
            data = json.loads(raw_json)
            
            # Ensure full_text is preserved
            data["full_text"] = text[:1000] # Representative snippet
            data["judgment_summary"] = data.get("judgment_summary", "Extracted via Agentic Parser")
            
            return CourtCase(**data)
            
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(f"Parsing failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected parsing error: {e}")
            return None

    def _fallback_rule_parsing(self, text: str) -> CourtCase:
        """Simple regex-based fallback for demo stability."""
        # Simple extraction logic for "State vs" patterns
        title_match = re.search(r"State vs\.?\s+([^,\n\r]+)", text, re.I)
        title = title_match.group(0) if title_match else "Extracted Case"
        
        return CourtCase(
            case_id=f"EXT-{hash(text) % 10000}",
            title=title,
            court_level="High Court",
            court_name="Peshawar High Court",
            judgment_date="2025-01-01",
            citation="PENDING",
            offense_category="Illegal Logging",
            offense_details="Extracted via fallback rules.",
            location="Hazara",
            verdict="Guilty",
            penalty_type="Fine",
            penalty_amount_rs=50000,
            judgment_summary="Automated fallback summary."
        )

class LegalDataSanitizer:
    """Cleans and normalizes legal data fields."""
    
    @staticmethod
    def clean_currency(raw: str) -> int:
        """Extracts digits from 'Rs. 50,000' or similar."""
        digits = re.sub(r'[^\d]', '', raw)
        return int(digits) if digits else 0
        
    @staticmethod
    def clean_citation(raw: str) -> str:
        """Normalizes citation spacing."""
        return re.sub(r'\s+', ' ', raw).strip()
