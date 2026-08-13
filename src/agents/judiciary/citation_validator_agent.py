import re
import os
import json
from typing import Dict, Any, Optional, List
from agents.base_agent import BaseAgent
from core.schemas import CanonicalAgentResponse, Citation

class CitationValidatorAgent(BaseAgent):
    """
    Offline Intelligence agent bridging raw natural language citations to the GreenLawAI
    Constitutional & Environmental logic engine. Evaluates repeals, amendments, and operational validity.
    
    The legal knowledge base is loaded dynamically from data/legal_statutes.json 
    so it can be expanded without modifying code.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, component_id: str = "citation_validator", llm_manager = None, **kwargs):
        super().__init__(name="CitationValidatorAgent", component_id=component_id, config=config)
        self.legal_database = self._load_legal_database()
        
    def _load_legal_database(self) -> Dict[str, Any]:
        """Dynamically loads the legal statutes from the external JSON file."""
        # Walk up from agents/judiciary/ to src/, then into data/
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        json_path = os.path.join(base_dir, "data", "legal_statutes.json")
        
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            # Graceful degradation if JSON is missing
            return {}
        except json.JSONDecodeError:
            return {}
        
    def validate(self, query: str) -> Dict[str, Any]:
        """
        Parses the query text using NLP regex to extract the statutory Section
        and evaluates it against the dynamically loaded knowledge base.
        """
        query_clean = query.lower()
        
        # Extract the Section Number (e.g. "Section 26", "Sec 26", "26(1)")
        section_match = re.search(r'sec(?:tion)?\s*(\d+[a-z]*(\(\d+\))?)', query_clean)
        sec_num = section_match.group(1) if section_match else None
        
        if not sec_num:
             # Fallback naked number extraction
             num_match = re.search(r'\b(\d+[a-z]?)\b', query_clean)
             if num_match:
                 sec_num = num_match.group(1)
                 
        # Core stripping for dictionary lookup
        lookup_num = sec_num.split('(')[0] if sec_num else None
                 
        if lookup_num and lookup_num in self.legal_database:
            data = self.legal_database[lookup_num]
            
            # Dynamically resolve related section titles
            related = []
            for rel_sec in data.get("related_sections", []):
                rel_data = self.legal_database.get(rel_sec)
                if rel_data:
                    related.append(f"Section {rel_sec} ({rel_data['title']})")
                else:
                    related.append(f"Section {rel_sec}")
            
            res = {
                "valid": True,
                "found_section": sec_num,
                "act_matched": data["act"],
                "title": data["title"],
                "status": data["status"],
                "details": data["details"],
                "penalty": data["penalty"],
                "amendments": data["amendments"],
                "related_sections": related,
                "case_references": data.get("case_references", [])
            }
        else:
            res = {
                "valid": False,
                "found_section": sec_num or query[:30],
                "act_matched": "Unknown",
                "status": "NOT FOUND",
                "details": "The requested citation could not be found in the GreenLawAI registry. You may add it to data/legal_statutes.json.",
                "related_sections": [],
                "case_references": []
            }
            
        return res

    def run(self, input_text: str, source_docs: list = None, audience: Any = None, context: Dict = None) -> CanonicalAgentResponse:
        result = self.validate(input_text)
        
        if result["valid"]:
            status_color = "#ef4444" if "REPEALED" in result["status"] else "#10b981"
            explanation = f"#### 🏛️ {result['act_matched']} — Section {result['found_section']}\n"
            explanation += f"*{result['title']}*\n\n"
            explanation += f"- **Enforcement Status:** <span style='color:{status_color}; font-weight:bold;'>{result['status']}</span>\n"
            explanation += f"- **Operational Details:** {result['details']}\n"
            explanation += f"- **Prescribed Penalty:** {result['penalty']}\n"
            explanation += f"- **Key Amendments:** {result['amendments']}\n"
            
            # Dynamic cross-references
            if result["related_sections"]:
                explanation += f"\n**📎 Related Sections:**\n"
                for rel in result["related_sections"]:
                    explanation += f"- {rel}\n"
                    
            # Dynamic case law citations
            if result["case_references"]:
                explanation += f"\n**📚 Cited in Case Law:**\n"
                for case in result["case_references"]:
                    explanation += f"- *{case}*\n"
            
            simple = f"Section {result['found_section']} of {result['act_matched']} is {result['status']}."
            citations_list = [Citation(document=result['act_matched'], section=str(result['found_section']))]
        else:
            explanation = f"⚠️ **Citation Not Found:** Could not validate Section '{result['found_section']}' against known forestry statutes.\n\n"
            explanation += f"**💡 Tip:** You can add new statutes to `data/legal_statutes.json` to expand the knowledge base."
            simple = f"Could not find Section '{result['found_section']}' in the law library."
            citations_list = [Citation(document="Unknown", section=str(result.get('found_section', 'N/A')))]
            
        return CanonicalAgentResponse(
            simple_explanation=simple,
            legal_explanation=explanation,
            citations=citations_list,
            agent_name="CitationValidatorAgent",
            trust_score=0.9 if result["valid"] else 0.3,
            confidence=0.95 if result["valid"] else 0.2,
            source_chunks=[],
            graph_metadata={"validation": result}
        )
