from typing import List, Dict, Any, Optional
from loguru import logger
from core.contracts import BasePipelineComponent, AgentResponseProtocol
from core.schemas import AudienceType, UnifiedVerdict, ConsensusStatus
import json
import os


class FusionEngine(BasePipelineComponent):
    """
    Fusion Engine (FORMATTER ONLY)
    Registry-Compatible (Phase 3)
    """

    def __init__(self, component_id: str = "fusion_engine"):
        super().__init__(component_id)

    async def load(self, config: Dict[str, Any]) -> bool:
        """Lifecycle: Load configuration."""
        self._is_loaded = True
        logger.info(f"[FusionEngine] {self.component_id} loaded.")
        return True

    async def unload(self) -> bool:
        """Lifecycle: Shutdown."""
        self._is_loaded = False
        return True

    def validate(self, raw_outputs: List[AgentResponseProtocol]) -> List[AgentResponseProtocol]:
        validated = []
        for out in raw_outputs:
            # Check for Protocol compliance
            if not all(hasattr(out, attr) for attr in ["simple_explanation", "legal_explanation", "citations", "abstain"]):
                 logger.error(f"[FusionEngine] Invalid object structure: {type(out)}.")
                 continue
            validated.append(out)
        return validated

    def order(self, responses: List[AgentResponseProtocol]) -> List[AgentResponseProtocol]:
        """
        Priority: non-abstain > higher confidence
        """
        return sorted(
            responses,
            key=lambda r: (r.abstain, -float(r.confidence or 0.0))
        )

    def select(self, responses: List[AgentResponseProtocol]) -> AgentResponseProtocol | None:
        for r in responses:
            if not r.abstain:
                return r
        return None

    def format(self, response: AgentResponseProtocol | None, audience: AudienceType | None = None) -> dict:
        if response is None:
            return self.abstain_template(audience=audience)

        return {
            "simple_explanation": response.simple_explanation,
            "legal_explanation": response.legal_explanation,
            "citations": [c.dict() if hasattr(c, "dict") else c for c in response.citations],
            "abstain": response.abstain,
            "confidence": response.confidence,
            "confidence_breakdown": getattr(response, "confidence_breakdown", {}),
            "trust_score": getattr(response, "trust_score", 0.0),
            "display_allowed": getattr(response, "display_allowed", False),
            "agent": response.agent_name,
            "audience": response.audience.value if hasattr(response.audience, "value") else str(response.audience)
        }

    def abstain_template(self, audience: AudienceType | None = None) -> dict:
        return {
            "simple_explanation": "No grounded legal answer found in the available documents.",
            "legal_explanation": "The retrieved sources do not contain statutory provisions addressing this query.",
            "citations": [],
            "abstain": True,
            "confidence": 0.0,
            "trust_score": 0.0,
            "display_allowed": False,
            "agent": None,
            "audience": audience.value if audience and hasattr(audience, "value") else str(audience) if audience else None
        }

    def reconcile(self, responses: List[AgentResponseProtocol]) -> UnifiedVerdict:
        """
        Cross-agent reasoning: Detect conflicts and synthesize a unified verdict.
        """
        if not responses:
            abstain = self.abstain_template()
            return UnifiedVerdict(
                consensus_status=ConsensusStatus.ABSTAIN,
                trust_score=0.0,
                summary=abstain["simple_explanation"],
                legal_grounding=abstain["legal_explanation"],
                contributing_agents=[],
                primary_agent="None"
            )

        # 1. Conflict Detection (Phases 3.4)
        conflicts = self.detect_conflicts(responses)
        status = ConsensusStatus.AGREEMENT if not conflicts else ConsensusStatus.CONFLICT
        
        # 2. Score Synthesis
        ordered = self.order(responses)
        primary = ordered[0]
        
        # Final trust score = average of contributing agents * penalty for conflicts
        avg_confidence = sum(r.confidence for r in responses) / len(responses)
        penalty = 0.5 if conflicts else 1.0
        final_trust = avg_confidence * penalty

        # 3. Content Synthesis
        # In Phase 3, we pick the most confident non-abstaining agent as the primary content
        # But we augment it with consensus metadata
        
        return UnifiedVerdict(
            consensus_status=status,
            trust_score=round(final_trust, 2),
            summary=primary.simple_explanation,
            legal_grounding=primary.legal_explanation,
            conflicts=conflicts,
            contributing_agents=[r.agent_name for r in responses],
            primary_agent=primary.agent_name,
            validation_flags={
                "HABITAT_OK": "Species/Region Mismatch" not in "".join(conflicts),
                "ACTIVITY_OK": "Active Threat Mismatch" not in "".join(conflicts)
            }
        )

    def detect_conflicts(self, responses: List[AgentResponseProtocol]) -> List[str]:
        """
        Rule-based conflict detection between specialized agents.
        """
        conflicts = []
        agent_names = [r.agent_name.lower() for r in responses]
        
        # Rule A: Legal vs Scientific Alignment (Habitat Check)
        # If Judiciary mentions a species, but Climate has no habitat data for it in the query region
        if "judiciary" in agent_names and "climate" in agent_names:
            jud = next(r for r in responses if r.agent_name.lower() == "judiciary")
            cli = next(r for r in responses if r.agent_name.lower() == "climate")
            
            # Simple heuristic check: if Judiciary penalty is for 'Deodar' but Climate says 'Scrub'
            jud_species = jud.graph_metadata.get("penalty_details", {}).get("species_involved", "").lower()
            cli_species = cli.graph_metadata.get("metrics", {}).get("species", "").lower()
            
            if jud_species and cli_species and jud_species != cli_species:
                if "mixed" not in cli_species:
                    conflicts.append(f"Species Mismatch: Judiciary assumes {jud_species}, but Climate reports {cli_species}.")

        # Rule B: Intelligence vs Monitoring (Activity Check)
        if "monitoring" in agent_names and "judiciary" in agent_names:
            mon = next(r for r in responses if r.agent_name.lower() == "monitoring")
            # If monitoring sees no activity but judiciary is proposing a penalty
            if mon.graph_metadata.get("activity_detected") is False:
                conflicts.append("Active Threat Mismatch: Judiciary proposing penalty but Monitoring sees no recent thermal/GFW activity.")

        return conflicts

    def fuse(self, raw_agent_outputs: List[AgentResponseProtocol], audience: AudienceType | None = None) -> dict:
        """
        Main Fusion Entry Point (Enhanced for Consensus)
        """
        validated = self.validate(raw_agent_outputs)

        if not validated:
            return self.abstain_template(audience=audience)

        # Reconcile into a Unified Verdict
        verdict = self.reconcile(validated)
        
        # Combine result for UI
        final_output = self.format(self.select(self.order(validated)), audience=audience)
        final_output["consensus"] = verdict.dict()
        final_output["trust_score"] = verdict.trust_score # Override with scientific consensus score
        
        return final_output