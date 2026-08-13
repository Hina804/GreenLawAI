from typing import Dict, Any, List
from loguru import logger
from core.contracts import BasePipelineComponent, AgentResponseProtocol, TrustVerdict
from core.schemas import AudienceType


class TrustEngine(BasePipelineComponent):
    """
    Deterministic trust computation engine.
    Registry-Compatible (Phase 3)
    """

    def __init__(self, component_id: str = "trust_engine"):
        super().__init__(component_id)
        # Thresholds (can be overridden by load config)
        self.min_citations = 1
        self.min_trust_score = 0.35
        self.grounded_multiplier = 1.0
        self.ungrounded_multiplier = 0.3
        self.schema_valid_multiplier = 1.0
        self.schema_invalid_multiplier = 0.0

    async def load(self, config: Dict[str, Any]) -> bool:
        """Lifecycle: Load configuration from registry."""
        self.min_citations = config.get("min_citations", self.min_citations)
        self.min_trust_score = config.get("min_trust_score", self.min_trust_score)
        self._is_loaded = True
        logger.info(f"[TrustEngine] {self.component_id} loaded with config: {config}")
        return True

    async def unload(self) -> bool:
        """Lifecycle: Shutdown."""
        self._is_loaded = False
        return True

    def compute_trust(
        self,
        grounded: bool,
        citation_count: int,
        schema_valid: bool
    ) -> float:
        trust = 1.0
        if not schema_valid:
            trust *= self.schema_invalid_multiplier
        else:
            trust *= self.schema_valid_multiplier

        if not grounded:
            trust *= self.ungrounded_multiplier
        else:
            trust *= self.grounded_multiplier

        if citation_count < self.min_citations:
            # Audit Fix: Penalize instead of zeroing out (allows grounded-but-unmapped responses to pass)
            trust *= 0.2
        else:
            citation_factor = min(citation_count, 3) / 3
            trust *= citation_factor

        return round(min(max(trust, 0.0), 1.0), 4)

    def evaluate(
        self,
        response: AgentResponseProtocol,
        cited_sources: List[Any],
        audience: AudienceType = AudienceType.DUAL
    ) -> TrustVerdict:
        """
        Policy-level trust evaluation.
        Uses AgentResponseProtocol (Phase 3 Decoupling).
        """
        threshold = self.min_trust_score
        if audience == AudienceType.VILLAGER:
            threshold = 0.65
            logger.info(f"[TrustEngine] Escalating threshold to {threshold} for VILLAGER")

        grounded = not response.abstain
        schema_valid = response.validation_passed
        citation_count = len(cited_sources)

        score = self.compute_trust(grounded, citation_count, schema_valid)
        is_trustworthy = score >= threshold
        reason = "TRUST_OK" if is_trustworthy else "LOW_TRUST_THRESHOLD"
        
        return TrustVerdict(
            score=score,
            is_trustworthy=is_trustworthy,
            reason=reason
        )