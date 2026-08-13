from core.schemas import AudienceType
from core.contracts import BasePipelineComponent
from typing import Dict, Any, List
from loguru import logger

class AudienceClassifier(BasePipelineComponent):
    """
    Deterministic audience classifier.
    Registry-Compatible (Phase 3)
    """

    def __init__(self, component_id: str = "audience_classifier"):
        super().__init__(component_id)
        
        self.villager_patterns = {
            "can i": 2,
            "is it allowed": 3,
            "fine": 1,
            "arrest": 2,
            "forest officer": 2,
            "village": 2,
            "guzara": 3,
            "rights": 1,
            "punishment": 2,
            "jail": 2,
            "permit": 2,
            "illegal": 1,
            "allowed": 1,
            "complaint": 1,
        }

        self.pro_patterns = {
            "section": 3,
            "clause": 3,
            "act": 2,
            "ordinance": 3,
            "statute": 3,
            "liability": 3,
            "jurisdiction": 3,
            "amendment": 3,
            "legal": 2,
            "provision": 3,
            "regulation": 2,
            "compliance": 2,
            "interpretation": 2,
            "enforcement": 2,
            "precedent": 3,
        }

    async def load(self, config: Dict[str, Any]) -> bool:
        """Lifecycle: Initialization."""
        self._is_loaded = True
        logger.info(f"[AudienceClassifier] {self.component_id} loaded.")
        return True

    async def unload(self) -> bool:
        """Lifecycle: Shutdown."""
        self._is_loaded = False
        return True

    def classify(self, query: str) -> AudienceType:
        """
        Structural intent inference.
        """
        if not query:
            return AudienceType.DUAL

        q = query.lower()
        villager_score = 0
        pro_score = 0

        for k, w in self.villager_patterns.items():
            if k in q:
                villager_score += w

        for k, w in self.pro_patterns.items():
            if k in q:
                pro_score += w

        if villager_score >= pro_score + 2:
            return AudienceType.VILLAGER
        elif pro_score >= villager_score + 2:
            return AudienceType.PROFESSIONAL
        else:
            return AudienceType.DUAL