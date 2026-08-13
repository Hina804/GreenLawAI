import json
import os
import logging
from datetime import datetime
from typing import List, Dict, Optional
try:
    from .court_schema import CourtCase
    from .case_parser import AgenticParser, PDFExtractor
except ImportError:
    from court_schema import CourtCase
    from case_parser import AgenticParser, PDFExtractor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CaseIngestor:
    """
    Ingests raw JSON/PDF court cases, chunks them, and prepares them for
    Vector DB (FAISS) and Graph DB (Neo4j) storage.
    """
    
    def __init__(self, data_dir: str, llm_manager=None):
        self.data_dir = data_dir
        self.cases: List[CourtCase] = []
        self.parser = AgenticParser(llm_manager)
        try:
            from knowledge.versioning import version_manager
            self.versioning = version_manager
        except:
            self.versioning = None
        
    def save_cases_to_json(self, output_path: str) -> None:
        """Saves current case list to JSON with automated versioning."""
        logger.info(f"Saving {len(self.cases)} cases to {output_path}")
        
        # Load existing if available to check for delta
        existing_cases = {}
        if os.path.exists(output_path):
            try:
                with open(output_path, "r", encoding="utf-8") as f:
                    old_data = json.load(f)
                    for item in old_data:
                        existing_cases[item.get("case_id")] = item
            except: pass

        final_data = []
        for case in self.cases:
            case_dict = case.dict()
            cid = case.case_id
            
            if cid in existing_cases:
                old_item = existing_cases[cid]
                # Deep comparison (excluding metadata timestamp)
                comparison_old = {k:v for k,v in old_item.items() if k != "metadata"}
                comparison_new = {k:v for k,v in case_dict.items() if k != "metadata"}
                
                if comparison_old != comparison_new:
                    if self.versioning:
                        logger.info(f"Change detected in {cid}. Archiving old version...")
                        self.versioning.create_snapshot(cid, old_item)
                        # Increment version
                        old_ver = old_item.get("metadata", {}).get("version", "1.0")
                        new_ver = self.versioning.increment_version(old_ver)
                        case_dict["metadata"]["version"] = new_ver
                        case_dict["metadata"]["lineage"].append(f"v{old_ver}")
                        case_dict["metadata"]["last_verified"] = datetime.now().strftime("%Y-%m-%d")
                else:
                    # No change, keep old metadata (especially last_verified)
                    case_dict["metadata"] = old_item.get("metadata", case_dict["metadata"])
            
            final_data.append(case_dict)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(final_data, f, indent=4)
        logger.info(f"Ingestion saved to {output_path}")

    def load_cases_from_json(self, file_path: str) -> None:
        """Loads cases from a JSON file and validates against the schema."""
        logger.info(f"Loading cases from {file_path}")
        with open(file_path, "r") as f:
            raw_data = json.load(f)
            
        valid_count = 0
        for item in raw_data:
            try:
                case = CourtCase(**item)
                self.cases.append(case)
                valid_count += 1
            except Exception as e:
                logger.error(f"Failed to validate case {item.get('case_id', 'UNKNOWN')}: {e}")
                
        logger.info(f"Successfully loaded and validated {valid_count} cases.")
        
    def process_pdf_directory(self, dir_path: str) -> None:
        """Processes all PDF files in a directory using the AgenticParser."""
        if not os.path.exists(dir_path):
            logger.error(f"PDF Directory not found: {dir_path}")
            return
            
        logger.info(f"Scanning directory for PDFs: {dir_path}")
        pdf_files = [f for f in os.listdir(dir_path) if f.lower().endswith(".pdf")]
        
        for pdf in pdf_files:
            file_path = os.path.join(dir_path, pdf)
            logger.info(f"Processing PDF: {pdf}")
            
            text = PDFExtractor.extract_text(file_path)
            case = self.parser.parse_text(text)
            
            if case:
                # Deduplication check
                if any(c.case_id == case.case_id for c in self.cases):
                    logger.warning(f"Case {case.case_id} already exists in memory. Skipping.")
                    continue
                    
                self.cases.append(case)
                logger.info(f"Successfully parsed and ingested: {case.case_id}")
            else:
                logger.error(f"Failed to parse PDF: {pdf}")

    def save_to_disk(self, file_path: str) -> None:
        """Persists all cases to a JSON file."""
        if not self.cases:
            logger.warning("No cases to save.")
            return
            
        logger.info(f"Saving {len(self.cases)} cases to {file_path}")
        
        # Load existing if file exists for merge
        existing_cases = []
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                try:
                    existing_data = json.load(f)
                    existing_cases = [CourtCase(**d) for d in existing_data]
                except: pass
        
        # Merge logic (Simple deduplication by ID)
        current_ids = {c.case_id for c in self.cases}
        merged_cases = [c for c in existing_cases if c.case_id not in current_ids]
        merged_cases.extend(self.cases)
        
        # Sort by date
        merged_cases.sort(key=lambda x: x.judgment_date, reverse=True)
        
        with open(file_path, "w") as f:
            json.dump([c.model_dump() for c in merged_cases], f, indent=2)
            
        logger.info(f"Successfully persisted storage at {file_path}")

    def extract_graph_nodes(self) -> List[Dict]:
        """Extracts nodes and relationships for Neo4j injection."""
        logger.info(f"Extracting graph relationships for {len(self.cases)} cases.")
        nodes = []
        for case in self.cases:
            nodes.append(case.to_neo4j_nodes())
        return nodes
        
    def process_for_vector_db(self):
        """
        Chunks the judgment_summary and full_text for FAISS embedding.
        """
        logger.info(f"Preparing {len(self.cases)} cases for vector embeddings (Phase 2).")
        chunks = []
        for case in self.cases:
            chunk = {
                "id": case.case_id,
                "text": f"Title: {case.title}. Summary: {case.judgment_summary}",
                "metadata": {
                    "case_id": case.case_id,
                    "title": case.title,
                    "court": case.court_name,
                    "offense": case.offense_category,
                    "offense_type": case.offense_category,
                    "verdict": case.verdict,
                    "penalty": f"{case.penalty_type} - {case.penalty_amount_rs} rs",
                    "penalty_amount_rs": case.penalty_amount_rs,
                    "sentence_months": case.imprisonment_months,
                    "judgment_date": case.judgment_date,
                    "location": case.location,
                    "is_night": case.is_night_violation,
                    "is_protected": case.is_protected_forest,
                    "repeat_offender": case.repeat_offender,
                    "trees_cut": case.trees_cut,
                    "bail_granted": case.verdict.lower() not in ["guilty", "convicted"]
                }
            }
            chunks.append(chunk)
        return chunks

if __name__ == "__main__":
    # Test the ingestion logic against the mock data
    mock_data_path = os.path.join(os.path.dirname(__file__), "court_cases", "processed", "mock_cases.json")
    
    ingestor = CaseIngestor(data_dir=os.path.dirname(mock_data_path))
    
    if os.path.exists(mock_data_path):
        ingestor.load_cases_from_json(mock_data_path)
        nodes = ingestor.extract_graph_nodes()
        vectors = ingestor.process_for_vector_db()
        
        logger.info("Ingestion pipeline verified against schema successfully.")
    else:
        logger.warning("Mock data not found. Please run case_generator.py first.")
