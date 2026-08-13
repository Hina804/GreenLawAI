from enum import Enum
from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
# GeoEvent Schema (Restored & Optimized Phase 12.23)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class GeoEvent:
    id: str
    type: str # fire, deforestation, logging, incident, correlated_threat
    lat: float
    lon: float
    timestamp: datetime
    severity: str # LOW, MEDIUM, HIGH, CRITICAL
    confidence: str # TACTICAL, NOMINAL, HIGH
    source: str # NASA-FIRMS, GFW-Integrated, etc.
    details: Dict[str, Any]

# ─────────────────────────────────────────────────────────────────────────────
# Audience Type
# ─────────────────────────────────────────────────────────────────────────────

class AudienceType(str, Enum):
    VILLAGER     = "villager"
    PROFESSIONAL = "professional"
    DUAL         = "dual"
    CITIZEN      = "citizen"
    OFFICIAL     = "official"

# ─────────────────────────────────────────────────────────────────────────────
# Citation Model
# ─────────────────────────────────────────────────────────────────────────────

class Citation(BaseModel):
    document:  str            = Field(...,  description="Exact document name")
    section:   Optional[str]  = Field(None, description="Section of the law, if applicable")
    clause:    Optional[str]  = Field(None, description="Clause within section, if applicable")
    chunk_id:  Optional[str]  = Field(None, description="Internal chunk ID (vector/graph reference)")

# ─────────────────────────────────────────────────────────────────────────────
# Canonical Agent Response Contract
# ─────────────────────────────────────────────────────────────────────────────

class CanonicalAgentResponse(BaseModel):
    # ── Core answer fields ──────────────────────────────────────────────
    simple_explanation: str            = Field(
        ..., max_length=5000,
        description="Plain language explanation for layman, <=30 words recommended"
    )
    legal_explanation: str             = Field(
        ..., max_length=8000,
        description="Formal statute-grounded legal explanation, <=50 words recommended"
    )
    citations: List[Citation]          = Field(
        ...,
        description="Structured citations; must be non-empty if abstain=False"
    )
    abstain: bool                      = Field(
        False,
        description="True = no grounding found; response is suppressed"
    )
    violations: List[str]              = Field(
        default_factory=list,
        description="Hallucination or policy violations detected"
    )

    # ── Extended metadata fields ─────────────────────────────────────────
    agent_name: str                    = Field(
        ...,
        description="Producing agent identifier"
    )
    audience: AudienceType             = Field(
        AudienceType.DUAL,
        description="Target audience"
    )
    graph_metadata: Dict[str, Any]     = Field(
        default_factory=dict,
        description="Graph traversal metadata"
    )

    # ── Trust & confidence layer ─────────────────────────────────────────
    confidence: float                  = Field(
        0.0, ge=0.0, le=1.0,
        description="Confidence score assigned by ConfidenceEngine"
    )
    confidence_breakdown: Dict[str, Any] = Field(
        default_factory=dict,
        description="Detailed scoring components"
    )
    trust_score: float                 = Field(
        0.0, ge=0.0, le=1.0,
        description="Multiplicative trust score (grounding*citation*schema)"
    )

    # ── Presentation control ─────────────────────────────────────────────
    display_allowed: bool              = Field(
        False,
        description="True only if trust_score >= threshold"
    )

    # ── Validation layer ─────────────────────────────────────────────────
    validation_passed: bool            = Field(
        True,
        description="False if schema/citation/trust validation failed"
    )
    errors: List[str]                  = Field(
        default_factory=list,
        description="Validation or pipeline error messages"
    )

    # ── Enrichment ───────────────────────────────────────────────────────
    answer_points: List[str]           = Field(
        default_factory=list,
        description="Structured bullet points (optional)"
    )
    source_chunks: List[str]           = Field(
        default_factory=list,
        description="Raw grounded source chunks"
    )

    grounding_coverage: float          = Field(
        0.0, ge=0.0, le=1.0,
        description="Grounding coverage ratio from HallucinationGuard"
    )

    # ─────────────────────────────────────────────────────────────────────
    # Validators
    # ─────────────────────────────────────────────────────────────────────

    @model_validator(mode='after')
    def grounding_rules(self) -> 'CanonicalAgentResponse':
        # Rule 1: If not abstaining → citations required
        if not self.abstain and not self.citations:
            raise ValueError("Citations list cannot be empty if abstain is False. Grounding is mandatory.")

        # Rule 2: If abstaining → no citations allowed
        if self.abstain and self.citations:
            raise ValueError("Citations must be empty if abstain is True.")

        # Rule 3: Trust gate enforcement
        if self.trust_score < 0.5:
            self.display_allowed = False
        else:
            self.display_allowed = True

        # Rule 4: Validation consistency
        if self.errors:
            self.validation_passed = False

        return self

# ─────────────────────────────────────────────────────────────────────────────
# Consensus Models (Phase 3 Week 4)
# ─────────────────────────────────────────────────────────────────────────────

class ConsensusStatus(str, Enum):
    AGREEMENT    = "agreement"     # All agents align on the tactical situation
    CONFLICT     = "conflict"      # Significant discrepancy detected (e.g., Legal vs Scientific)
    PARTIAL      = "partial"       # Some alignment, some minor divergence
    ABSTAIN      = "abstain"       # Insufficient data for consensus

class UnifiedVerdict(BaseModel):
    """
    Final synthesized verdict after Multi-Agent Reconciliation.
    """
    consensus_status: ConsensusStatus = Field(ConsensusStatus.AGREEMENT)
    trust_score: float                = Field(..., ge=0.0, le=1.0)
    
    # ── Final Synthesized Content ──
    summary: str                      = Field(..., description="Unified simple explanation")
    legal_grounding: str               = Field(..., description="Unified statutory grounding")
    
    # ── Conflict Layer ──
    conflicts: List[str]               = Field(default_factory=list, description="Descriptions of any agentic conflicts")
    resolution: Optional[str]          = Field(None, description="How conflicts were resolved (heuristic/human)")
    
    # ── Source Agents ──
    contributing_agents: List[str]     = Field(..., description="List of agents involved in the verdict")
    primary_agent: str                 = Field(..., description="Agent with the highest trust score")
    
    # ── Metadata ──
    timestamp: datetime                = Field(default_factory=datetime.now)
    validation_flags: Dict[str, bool]  = Field(default_factory=dict, description="HABITAT_OK, ACTIVITY_OK, etc.")

