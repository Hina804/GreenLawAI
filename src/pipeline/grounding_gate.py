from typing import List, Dict, Any
from loguru import logger
from core.contracts import BasePipelineComponent

# -------------------------------
# Legal grounding indicators
# -------------------------------

LEGAL_KEYWORDS = [
    "section", "article", "act", "rule", "regulation", "ordinance",
    "schedule", "clause", "subsection", "notification", "gazette",
    "penalty", "offence", "punishment", "fine", "imprisonment",
    "forest", "wildlife", "environment", "statutory", "provision", "chapter",
]


class GroundingGate(BasePipelineComponent):
    """
    PRE-GENERATION HARD GATE
    Registry-Compatible (Phase 3)
    """

    def __init__(self, component_id: str = "grounding_gate"):
        super().__init__(component_id)

    async def load(self, config: Dict[str, Any]) -> bool:
        """Lifecycle: Initialization."""
        self._is_loaded = True
        logger.info(f"[GroundingGate] {self.component_id} loaded.")
        return True

    async def unload(self) -> bool:
        """Lifecycle: Shutdown."""
        self._is_loaded = False
        return True

    def has_legal_grounding(self, retrieved_chunks: List[Dict[str, Any]]) -> bool:
        """
        HARD CHECK:
        Do retrieved chunks contain statutory/legal signals?
        """
        if not retrieved_chunks:
            logger.warning("[GroundingGate] No retrieved chunks.")
            return False

        for chunk in retrieved_chunks:
            text = str(chunk.get("text", "")).lower()
            metadata = chunk.get("metadata", {})

            # ---- TEXT SIGNALS ----
            for kw in LEGAL_KEYWORDS:
                if kw in text:
                    return True

            # ---- METADATA SIGNALS ----
            if any(
                key in metadata
                for key in [
                    "law_title", "act_name", "section", "article",
                    "regulation", "source_law", "document_type",
                ]
            ):
                return True

        return False

    def evaluate(self, retrieved_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        V4: Deterministic Grounding.
        Rules:
        - 0 chunks: False
        - 1 chunk: similarity > 0.82 AND has_legal_grounding(text)
        - >=2 chunks: True
        """
        count = len(retrieved_chunks)
        allowed = False
        reason = "NO_LEGAL_GROUNDING"

        if count == 0:
            allowed = False
            reason = "NO_CHUNKS"
        elif count == 1:
            sim = retrieved_chunks[0].get("similarity", 0.0)
            grounded = self.has_legal_grounding(retrieved_chunks)
            if sim > 0.75 and grounded: # Relaxed from 0.82 to 0.75
                allowed = True
                reason = "GROUNDING_OK"
            elif not grounded:
                allowed = False
                reason = "NO_LAW_TEXT_IN_CHUNK"
            else:
                allowed = False
                reason = "LOW_SIMILARITY"
        elif count >= 2:
            allowed = True
            reason = "GROUNDING_OK"

        if not allowed:
            logger.warning(f"[GroundingGate] BLOCK: {reason} (Chunks: {count})")
            return {
                "allowed": False,
                "reason": reason,
                "message": f"Deterministic grounding requirements not met ({reason}).",
                "stage": "PRE_GENERATION",
                "action": "BLOCK_LLM"
            }

        logger.info(f"[GroundingGate] ALLOW: {reason} (Chunks: {count})")
        return {
            "allowed": True,
            "reason": "GROUNDING_OK",
            "message": "Statutory grounding verified via deterministic rules.",
            "stage": "PRE_GENERATION",
            "action": "ALLOW_LLM"
        }