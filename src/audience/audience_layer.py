from typing import Dict, Any
from loguru import logger

from core.schemas import CanonicalAgentResponse, AudienceType


class AudienceLayer:
    """
    Audience Adaptation Layer (Presentation Intelligence Layer)

    Purpose:
    - Transform a validated CanonicalAgentResponse
    - Adapt tone, structure, verbosity, and language
    - WITHOUT modifying facts, logic, citations, or legal meaning

    This is a UX + Communication layer, NOT reasoning or retrieval.
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        self.config = config or {}

    def adapt(
        self,
        response: CanonicalAgentResponse,
        audience: AudienceType
    ) -> CanonicalAgentResponse:
        """
        Main entrypoint for audience adaptation.
        """
        logger.info(f"[AudienceLayer] Adapting response for audience={audience}")

        if response.abstain:
            # Abstentions should not be stylized — safety first
            return response

        if audience == AudienceType.VILLAGER:
            return self._adapt_for_villager(response)

        elif audience == AudienceType.PROFESSIONAL:
            return self._adapt_for_professional(response)

        elif audience == AudienceType.DUAL:
            return self._adapt_for_dual(response)

        else:
            logger.warning(f"[AudienceLayer] Unknown audience type: {audience}")
            return response

    # ---------------------------
    # Audience Profiles
    # ---------------------------

    def _adapt_for_villager(self, response: CanonicalAgentResponse) -> CanonicalAgentResponse:
        """
        Low-literacy, high-clarity, simple language, minimal legal jargon.
        """
        logger.debug("[AudienceLayer] Applying villager adaptation")

        response.simple_explanation = self._simplify_language(response.simple_explanation)
        response.legal_explanation = self._compress_legal_content(response.legal_explanation)

        response.formatting = {
            "tone": "simple",
            "style": "conversational",
            "legal_density": "low",
            "verbosity": "low",
            "explanation_mode": "practical"
        }

        return response

    def _adapt_for_professional(self, response: CanonicalAgentResponse) -> CanonicalAgentResponse:
        """
        High-precision, legal terminology preserved, structured output.
        """
        logger.debug("[AudienceLayer] Applying professional adaptation")

        response.simple_explanation = self._formalize_language(response.simple_explanation)
        response.legal_explanation = self._expand_legal_structure(response.legal_explanation)

        response.formatting = {
            "tone": "formal",
            "style": "legal-technical",
            "legal_density": "high",
            "verbosity": "high",
            "explanation_mode": "doctrinal"
        }

        return response

    def _adapt_for_dual(self, response: CanonicalAgentResponse) -> CanonicalAgentResponse:
        """
        Balanced mode: public + legal clarity.
        """
        logger.debug("[AudienceLayer] Applying dual adaptation")

        response.formatting = {
            "tone": "neutral",
            "style": "educational",
            "legal_density": "medium",
            "verbosity": "medium",
            "explanation_mode": "hybrid"
        }

        return response

    # ---------------------------
    # Transformation utilities
    # ---------------------------

    def simplify(self, text: str) -> str:
        """
        Public API for text simplification (Phase 2 contract).
        """
        return self._simplify_language(text)

    def _simplify_language(self, text: str) -> str:
        """
        Reduce complexity heuristically.
        """
        if not text:
            return text

        replacements = {
            "pursuant to": "under",
            "in accordance with": "under",
            "shall be liable to": "can be punished with",
            "notwithstanding": "even if",
            "hereinafter": "later called",
        }

        simplified = text
        for k, v in replacements.items():
            simplified = simplified.replace(k, v)

        return simplified

    def _compress_legal_content(self, text: str) -> str:
        """
        Keep meaning, reduce density.
        """
        if not text:
            return text

        # Simple heuristic: limit length
        max_len = self.config.get("villager_legal_max_length", 500)
        return text[:max_len] + ("..." if len(text) > max_len else "")

    def _formalize_language(self, text: str) -> str:
        """
        Professional tone normalizer.
        """
        if not text:
            return text

        # Placeholder for NLP style normalizer later
        return text.strip()

    def _expand_legal_structure(self, text: str) -> str:
        """
        Prepare content for structured legal formatting.
        """
        if not text:
            return text

        # Placeholder for future structured formatting
        return text.strip()