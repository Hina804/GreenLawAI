import os
from typing import Dict, Any, Optional
from datetime import datetime
import uuid
from agents.base_agent import BaseAgent
from core.schemas import AudienceType

class FIRGeneratorAgent(BaseAgent):
    """
    Agent responsible for generating First Information Reports (FIRs) 
    in both English and Urdu (Unicode).
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None, component_id: str = "fir_generator", llm_manager = None, **kwargs):
        super().__init__(name="FIRGeneratorAgent", component_id=component_id, config=config)
        self.template_dir = os.path.join(os.path.dirname(__file__), "templates")
        
    def generate_fir(self, incident_data: Dict[str, Any], language: str = "en") -> str:
        """
        Generates a formatted FIR string based on incident data.
        
        Args:
            incident_data: Dictionary containing:
                - district, station, sections, incident_date, incident_time, 
                - location, coordinates, offense_description, tree_species, 
                - tree_count, estimated_value, accused_details, action_taken
            language: 'en' for English, 'ur' for Urdu (Unicode)
        """
        template_file = f"fir_{language}.txt"
        template_path = os.path.join(self.template_dir, template_file)
        
        if not os.path.exists(template_path):
            return f"Error: Template for language '{language}' not found."
            
        with open(template_path, 'r', encoding='utf-8') as f:
            template = f.read()
            
        # Add internal tracking data
        incident_data['verification_code'] = str(uuid.uuid4())[:8].upper()
        incident_data['received_date'] = datetime.now().strftime("%Y-%m-%d")
        
        # Safe formatting
        formatted_fir = template
        for key, value in incident_data.items():
            placeholder = "{{" + key + "}}"
            formatted_fir = formatted_fir.replace(placeholder, str(value))
            
        return formatted_fir

    def run(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Standard agent interface for generating FIRs.
        """
        incident_data = context.get("incident_data", {}) if context else {}
        lang = context.get("language", "en") if context else "en"
        
        if not incident_data:
            return {
                "status": "error",
                "message": "No incident data provided in context."
            }
            
        fir_text = self.generate_fir(incident_data, lang)
        
        return {
            "status": "success",
            "fir_content": fir_text,
            "language": lang,
            "verification_code": incident_data.get('verification_code')
        }

    def get_status(self) -> Dict[str, Any]:
        return {
            "agent": "FIRGeneratorAgent",
            "templates_loaded": os.listdir(self.template_dir) if os.path.exists(self.template_dir) else []
        }
