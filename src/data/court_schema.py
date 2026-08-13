from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import date, datetime

class KnowledgeMetadata(BaseModel):
    """Temporal metadata for versioning and validity."""
    version: str = Field(default="1.0")
    last_verified: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    status: str = Field(default="CURRENT") # CURRENT, STALE, SUPERSEDED, ARCHIVED
    superseded_by: Optional[str] = None
    lineage: List[str] = Field(default_factory=list) # List of previous version IDs

class CourtCase(BaseModel):
    """
    Core schema defining a legal precedent for the Judiciary Module.
    """
    case_id: str = Field(..., description="Unique identifier for the case (e.g., SC-2025-001)")
    metadata: KnowledgeMetadata = Field(default_factory=KnowledgeMetadata)
    title: str = Field(..., description="Case title (e.g., State vs. Muhammad Khan)")
    court_level: str = Field(..., description="Supreme Court, High Court, Session Court, or Forest Tribunal")
    court_name: str = Field(..., description="Specific court name (e.g., Peshawar High Court)")
    bench: List[str] = Field(default_factory=list, description="List of presiding judges")
    judgment_date: str = Field(..., description="Date of the judgment in YYYY-MM-DD")
    citation: str = Field(..., description="Legal citation (e.g., 2025 SCMR 123)")
    
    # Offense Details
    law_sections: List[str] = Field(default_factory=list, description="Statutory sections invoked")
    offense_category: str = Field(..., description="Category (e.g., Illegal Logging, Encroachment)")
    offense_details: str = Field(..., description="Specific facts of the offense")
    location: str = Field(..., description="Where the offense occurred")
    is_night_violation: bool = Field(default=False, description="Whether the offense occurred at night")
    is_protected_forest: bool = Field(default=False, description="Whether it was a reserved/protected forest")
    trees_cut: int = Field(default=0, description="Number of trees cut, if applicable")
    
    # Outcome
    verdict: str = Field(..., description="Guilty, Not Guilty, Dismissed, Quashed")
    penalty_type: str = Field(..., description="Fine, Imprisonment, Fine + Imprisonment, None")
    penalty_amount_rs: int = Field(default=0, description="Fine amount in Pakistani Rupees")
    imprisonment_months: int = Field(default=0, description="Imprisonment duration in months")
    
    # Offender Profile
    repeat_offender: bool = Field(default=False, description="Is the accused a known repeat offender?")
    prior_convictions: int = Field(default=0, description="Number of prior convictions")
    
    # Relationships
    precedents_cited: List[str] = Field(default_factory=list, description="Citations of cases referenced in this judgment")
    
    # Text content
    judgment_summary: str = Field(..., description="Summary of the decision")
    full_text: str = Field(default="", description="Full judgment text block")
    keywords: List[str] = Field(default_factory=list, description="Tags for search filtering")

    def to_neo4j_nodes(self) -> Dict:
        """Helper to extract nodes for graph ingestion"""
        return {
            "case": {"id": self.case_id, "title": self.title, "date": self.judgment_date},
            "court": {"name": self.court_name, "level": self.court_level},
            "judges": self.bench,
            "sections": self.law_sections,
            "location": self.location,
            "offense": self.offense_category,
            "citations": self.precedents_cited
        }
