from typing import List, Dict, Any

class SectionBuilder:
    """
    Groups deduplicated clauses logically by Statute and Section to maintain legal hierarchy.
    Implements Precedence Logic: overrides older base text if a newer amendment exists for the same section.
    """

    def group_clauses(self, chunks: List[Dict[str, Any]]) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """
        Builds a hierarchical structure and resolves conflicts:
        {
          "KPK Forest Ordinance": {
              "Section 26": {"text": "...", "year": 2022, "clause_id": "..."},
          }
        }
        """
        grouped = {}

        for chunk in chunks:
            meta = chunk.get("metadata", {})
            text = chunk.get("text", "").strip()
            if not text:
                continue

            statute_base = (meta.get("law_title") or meta.get("source") or "Unknown Statute").strip()
            
            # Clean up statute string for base grouping (e.g., removing "(as amended...)" for core grouping)
            statute_name = statute_base.split("(")[0].strip().title()

            section = meta.get("section")
            if not section:
                if "Schedule" in text[:100]:
                    section = "Schedule"
                elif "Chapter" in text[:100]:
                    section = "Chapter Header"
                else:
                    section = "General Provision"
            else:
                section = f"Section {section}"
                clause_meta = meta.get("clause")
                if clause_meta and str(clause_meta).strip():
                   section += f" ({clause_meta})"

            year = meta.get("amended_by") or meta.get("year") or 0
            if isinstance(year, str) and year.isdigit():
                year = int(year)
            elif not isinstance(year, int):
                year = 0

            if statute_name not in grouped:
                grouped[statute_name] = {}
            
            # Conflict Resolution: Precedence check
            if section in grouped[statute_name]:
                existing_year = grouped[statute_name][section]["year"]
                if year > existing_year:
                    # Override with newer amendment
                    grouped[statute_name][section] = {
                        "text": text,
                        "year": year,
                        "chunk_id": chunk.get("chunk_id"),
                        "raw_doc": statute_base
                    }
                else:
                    # Skip, we already have the newer or same-year provision, or just append uniquely if year is same?
                    # For V1, if year is same, we might have multiple sub-clauses. 
                    if year == existing_year and text not in grouped[statute_name][section]["text"]:
                        grouped[statute_name][section]["text"] += f"\n- {text}"
            else:
                grouped[statute_name][section] = {
                    "text": text,
                    "year": year,
                    "chunk_id": chunk.get("chunk_id"),
                    "raw_doc": statute_base
                }

        return grouped
