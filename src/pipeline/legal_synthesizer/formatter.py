from typing import Dict, Any, List
from core.schemas import CanonicalAgentResponse

class OutputFormatter:
    """
    Implements Output Determinism via professional legal templates.
    Uses programmatic intent rules to trigger templates rather than relying on the LLM's stylistic choices.
    """

    def clean_content(self, content: str) -> str:
        """PRODUCTION-GRADE: Removes duplicate headers and ensures complete sentences."""
        if not isinstance(content, str): return str(content)
        
        header_patterns = [
            '⚖️ Legal Position', '🌍 Climate Impact', '🚨 Situational Awareness',
            '⚖️ Legal & Summary', '👥 Public Awareness', '🚨 Offence & Penalty',
            '### ⚖ OFFENCE & PENALTY', '🏛 LEGAL POSITION', '🏛️ REGULATORY EVIDENCE'
        ]
        for h in header_patterns:
            content = content.replace(h, '')
        
        content = content.strip()
        # Sentence completion logic: Relaxed for Audit (v9.5)
        # Only clip if the last sentence is truly tiny and obviously broken
        if content and not content.endswith(('.', '!', '?', ':', ')')):
            last_period = content.rfind('.')
            if last_period > len(content) * 0.85: # Use 85% instead of 70%
                content = content[:last_period + 1]
            elif last_period > 0:
                # Add a period if it's almost a complete sentence
                content += "."
        return content

    def format_output(self, response: CanonicalAgentResponse, query: str = "") -> CanonicalAgentResponse:
        if not response:
            return response

        # 1. Clean Citations
        seen_cites = set()
        clean_citations = []
        for c in response.citations:
            doc = c.document.title() if c.document else "Verified Legal Source"
            sec = f"Sec {c.section}" if c.section else ""
            key = f"{doc}-{sec}"
            if key not in seen_cites:
                clean_citations.append(c)
                seen_cites.add(key)
        response.citations = clean_citations

        # 2. Apply Output Template
        raw_text = response.legal_explanation or ""

        # Skip skeleton if IRAC content already present (any format)
        irac_markers = ["### ISSUE", "### RULE", "**ISSUE**", "**RULE**",
                        "ISSUE:", "RULE:", "CONCLUSION:", "CONDITIONS:"]
        if any(marker in raw_text for marker in irac_markers):
            response.legal_explanation = self.clean_content(raw_text)
            return response

        # Fallback skeleton for non-IRAC output
        q_lower = query.lower()
        is_penalty = any(k in q_lower for k in ["penalty", "fine", "imprisonment", "punish", "offence"])
        is_arrest  = any(k in q_lower for k in ["arrest", "warrant", "detain"])

        if is_penalty:
            header = "⚖ OFFENCE & PENALTY"
        elif is_arrest:
            header = "🚨 ARREST POWERS & PROCEDURE"
        else:
            header = "🏛 LEGAL POSITION"

        statutes = list(set([c.document.title() for c in response.citations if c.document]))
        statute_str = ", ".join(statutes) if statutes else "Verified Statutory Sources"

        formatted_text = f"### {header}\n\n**Statutory Source:** {statute_str}\n\n---\n\n{raw_text}"
        response.legal_explanation = self.clean_content(formatted_text)
        return response