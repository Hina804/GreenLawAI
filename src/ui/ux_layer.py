# src/ui/ux_layer.py

from typing import Dict, List, Any, Optional
from enum import Enum


class UXBlockReason(str, Enum):
    NO_RETRIEVAL = "NO_RETRIEVAL"
    NO_LEGAL_GROUNDING = "NO_LEGAL_GROUNDING"
    NO_CITATIONS_FOUND = "NO_CITATIONS_FOUND"
    HALLUCINATION_DETECTED = "HALLUCINATION_DETECTED"
    LOW_TRUST_SCORE = "LOW_TRUST_SCORE"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    POLICY_RESTRICTED = "POLICY_RESTRICTED"
    SYSTEM_ERROR = "SYSTEM_ERROR"
    REGISTRY_FAILURE = "REGISTRY_FAILURE"
    CONTRACT_VIOLATION = "CONTRACT_VIOLATION"


class UXStatus(str, Enum):
    BLOCKED = "blocked"
    WARNING = "warning"
    INFO = "info"
    ALLOWED = "allowed"

class UXState(str, Enum):
    """
    Phase 3.5: Deterministic UX State Machine.
    Ensures the system communicates its internal governance state precisely.
    """
    SYSTEM_DEGRADED = "SYSTEM_DEGRADED"           # Registry/Load failure
    PARTIAL_RESPONSE = "PARTIAL_RESPONSE"         # Some agents failed, others succeeded
    SAFE_ABSTAIN = "SAFE_ABSTAIN"                 # Grounding gate blocked or agent abstained
    BLOCKED_QUERY = "BLOCKED_QUERY"               # Security or Policy violation
    VERIFIED_RESPONSE = "VERIFIED_RESPONSE"       # High trust, high confidence
    LOW_CONFIDENCE_RESPONSE = "LOW_CONFIDENCE_RESPONSE" # Passable but uncertain


# ─────────────────────────────────────────────────────────────
# Core UX Gate Contract
# ─────────────────────────────────────────────────────────────

def ux_gate(
    *,
    state: UXState,
    reason: UXBlockReason,
    query: str,
    trust_score: float = 0.0,
    confidence: float = 0.0,
    citations: Optional[List[str]] = None,
    sources: Optional[List[str]] = None,
    audience: str = "dual",
    system_layer: str = "unknown"
) -> Dict[str, Any]:
    """
    Phase 3.5: Central UX State Machine & Control Layer.
    Converts internal system state + reason into a deterministic UX payload.
    """

    citations = citations or []
    sources = sources or []

    BASE = {
        UXBlockReason.NO_RETRIEVAL: {
            "title": "No Legal Source Found",
            "message": "No verified forestry or environmental law text was found in the system for your question.",
            "severity": UXStatus.BLOCKED,
            "guidance": ["Use official legal terms.", "Ask about a specific law.", "Upload a document."]
        },
        UXBlockReason.NO_LEGAL_GROUNDING: {
            "title": "No Legal Basis Detected",
            "message": "The system could not connect your question to verified legal statutes.",
            "severity": UXStatus.BLOCKED,
            "guidance": ["Ask about a specific law.", "Provide official documents.", "Rephrase with legal terms."]
        },
        UXBlockReason.NO_CITATIONS_FOUND: {
            "title": "Unverifiable Legal Reference",
            "message": "Relevant text was found, but no official legal citation could be verified.",
            "severity": UXStatus.WARNING,
            "guidance": ["Ask for a specific section.", "Use the official law name."]
        },
        UXBlockReason.HALLUCINATION_DETECTED: {
            "title": "Unverified Content Blocked",
            "message": "The system blocked the answer because it contains content not supported by verified legal sources.",
            "severity": UXStatus.BLOCKED,
            "guidance": ["Only verified law-based answers are allowed."]
        },
        UXBlockReason.LOW_TRUST_SCORE: {
            "title": "Answer Not Trustworthy",
            "message": "The system confidence and source verification are insufficient to safely display this answer.",
            "severity": UXStatus.BLOCKED,
            "guidance": ["Narrow the legal scope.", "Provide documents."]
        },
        UXBlockReason.LOW_CONFIDENCE: {
            "title": "Low Confidence Answer",
            "message": "This answer has low confidence and may be incomplete.",
            "severity": UXStatus.WARNING,
            "guidance": ["Ask more specific questions."]
        },
        UXBlockReason.POLICY_RESTRICTED: {
            "title": "Policy Restricted",
            "message": "This query cannot be answered due to system policy restrictions.",
            "severity": UXStatus.BLOCKED,
            "guidance": ["Ask within forestry scope."]
        },
        UXBlockReason.SYSTEM_ERROR: {
            "title": "System Error",
            "message": "An internal system error occurred.",
            "severity": UXStatus.BLOCKED,
            "guidance": ["Try again later.", "Contact admin."]
        },
        UXBlockReason.REGISTRY_FAILURE: {
            "title": "System Integrity Alert",
            "message": "A critical system component failed to initialize.",
            "severity": UXStatus.BLOCKED,
            "guidance": ["System maintenance.", "Try again in a few minutes."]
        },
        UXBlockReason.CONTRACT_VIOLATION: {
            "title": "Data Integrity Block",
            "message": "Internal data format violation detected.",
            "severity": UXStatus.BLOCKED,
            "guidance": ["Strict legal schema enforcement active."]
        }
    }

    template = BASE.get(reason, BASE[UXBlockReason.SYSTEM_ERROR])

    payload = {
        "state": state.value,
        "status": template["severity"].value,
        "reason": reason.value,
        "title": template["title"],
        "message": template["message"],
        "guidance": template["guidance"],
        "meta": {
            "query": query,
            "trust_score": trust_score,
            "confidence": confidence,
            "citations": citations,
            "sources": sources,
            "audience": audience,
            "system_layer": system_layer
        }
    }

    if audience == "villager":
        payload = simplify_for_villager(payload)

    return payload


def simplify_for_villager(ux_payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        **ux_payload,
        "guidance": ["Ask in simple words.", "Ask about one law only."]
    }

# ─────────────────────────────────────────────────────────────
# Allowed UX Payload (for valid answers)
# ─────────────────────────────────────────────────────────────

def ux_allowed(
    *,
    answer: str,
    citations: List[str],
    trust_score: float,
    confidence: float,
    audience: str,
    sources: List[str],
    state: UXState = UXState.VERIFIED_RESPONSE
) -> Dict[str, Any]:
    """
    UX wrapper for approved answers.
    Phase 3.5: Added state tracking.
    """

    payload = {
        "state": state.value,
        "status": UXStatus.ALLOWED.value,
        "answer": answer,
        "citations": citations,
        "sources": sources,
        "trust_score": trust_score,
        "confidence": confidence,
        "audience": audience
    }

    if audience == "villager":
        payload["confidence_label"] = "High" if confidence > 0.75 else "Medium"
    else:
        payload["confidence_label"] = f"{confidence:.2f}"

    return payload