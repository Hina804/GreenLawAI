# E:\GL_AI\src\core\contracts.py
import abc
from typing import Protocol, List, Dict, Any, Optional, runtime_checkable

@runtime_checkable
class AgentResponseProtocol(Protocol):
    """
    Structural Interface for Agent Responses (PEP 544).
    Enables Phase 3 decoupling by removing hard attribute coupling to 
    CanonicalAgentResponse in verification and fusion engines.
    """
    simple_explanation: str
    legal_explanation: str
    citations: List[Any]
    abstain: bool
    agent_name: str
    audience: Any
    confidence: float
    grounding_coverage: float
    source_chunks: List[Any]
    graph_metadata: Dict[str, Any]
    validation_passed: bool
    errors: List[str]

    def dict(self) -> Dict[str, Any]:
        ...


class BasePipelineComponent(abc.ABC):
    """
    Abstract Base Class for all Registry-Compatible components.
    Enables Phase 3 Lifecycle Control and Dynamic Registry integration.
    """

    def __init__(self, component_id: str):
        self.component_id = component_id
        self._is_loaded = False

    @abc.abstractmethod
    async def load(self, config: Dict[str, Any]) -> bool:
        """
        Lifecycle: Initialization logic for the component.
        """
        pass

    @abc.abstractmethod
    async def unload(self) -> bool:
        """
        Lifecycle: Shutdown logic/cleanup.
        """
        pass

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    def __repr__(self):
        return f"<{self.__class__.__name__} id={self.component_id} loaded={self._is_loaded}>"


import enum
from dataclasses import dataclass
from loguru import logger

class PipelineFailureType(enum.Enum):
    LOAD_ERROR = "LOAD_ERROR"           # Component failed to load/instantiate
    CONTRACT_ERROR = "CONTRACT_ERROR"   # Component does not implement required interface
    RUNTIME_ERROR = "RUNTIME_ERROR"     # Component crashed during execution
    LOGIC_ERROR = "LOGIC_ERROR"         # Invalid internal state transitions
    DATA_ERROR = "DATA_ERROR"           # Component returned invalid/malformed data
    SECURITY_ERROR = "SECURITY_ERROR"   # Request blocked by security

@dataclass
class PipelineFailure:
    failure_type: PipelineFailureType
    component_id: str
    message: str
    details: Optional[Dict[str, Any]] = None

@dataclass
class TrustVerdict:
    score: float
    is_trustworthy: bool
    reason: str

@dataclass
class ConfidenceVerdict:
    score: float
    breakdown: Dict[str, Any]

def validate_agent_response(response: Any, context: Optional[Dict[str, Any]] = None) -> bool:
    """
    Phase 3.5: Runtime & Semantic Contract Enforcer.
    Verifies that the response object adheres to AgentResponseProtocol
    and maintains semantic coherence.

    NEW: This function used to compute `missing` (unfound citations) and
    only log it — the finding never reached anywhere downstream that could
    act on it (e.g. ConfidenceEngine). It now attaches that finding to:
      1. response._contract_violations / response._unverified_citation_count
         (dynamic attributes on the response object itself — works even if
         callers never pass a context dict)
      2. context["contract_violations"] / context["unverified_citation_count"]
         (if a context dict is passed in)
    ConfidenceEngine.compute_confidence() reads from context first, and can
    be pointed at response._contract_violations as a fallback.

    `context` param is optional and defaults to None so this remains
    backward-compatible with any existing call sites that only pass
    `response`.
    """
    if not response:
        logger.error("[CONTRACT] Received None instead of response object.")
        return False

    required_attrs = ["simple_explanation", "legal_explanation", "citations", "abstain"]
    for attr in required_attrs:
        if not hasattr(response, attr):
            logger.error(f"[CONTRACT] Missing required attribute: {attr}")
            return False

    # 1. Structural Type Checking
    if not isinstance(response.citations, list):
        logger.error("[CONTRACT] 'citations' must be a list")
        return False
    if not isinstance(response.abstain, bool):
        logger.error("[CONTRACT] 'abstain' must be a boolean")
        return False

    # 2. Semantic Coherence Checks (Phase 3.5)

    # If not abstaining, must have citations (policy)
    if not response.abstain and not response.citations:
        logger.error("[CONTRACT] Semantic Violation: Non-abstaining response must have citations.")
        return False

    # Check citation-to-text alignment (Basic check for mentions)
    missing: List[str] = []

    if not response.abstain:
        combined_text = (response.simple_explanation + response.legal_explanation).lower()

        for cit in response.citations:
            # Handle potential dict or object citations
            doc_hint = ""
            if isinstance(cit, dict):
                doc_hint = str(cit.get('document', '')).lower()
            else:
                doc_hint = str(getattr(cit, 'document', '')).lower()

            if not doc_hint or doc_hint == "unknown source":
                continue

            # PRODUCTION-GRADE citation validation logic (Audit Fix)
            # 1. Normalize and create variations
            doc_normalized = doc_hint.strip()
            variations = [
                doc_normalized,
                doc_normalized.replace(' ', ''),
                doc_normalized.replace('the ', ''),
                doc_normalized.split()[-1] if ' ' in doc_normalized else doc_normalized
            ]

            # Add act-specific variations
            if 'act' in doc_normalized:
                act_name = doc_normalized.replace('act', '').strip()
                variations.append(f"{act_name} act")
                variations.append(f"act {act_name}")

            # 2. Check variations
            found = any(variation in combined_text for variation in variations)

            # 3. Fuzzy fallback (Year/Name density)
            if not found:
                import re
                years = re.findall(r'\d{4}', doc_hint)
                for year in years:
                    if year in combined_text:
                        found = True
                        break

                if not found:
                    terms = [w for w in doc_hint.split() if len(w) > 3]
                    if terms:
                        match_count = sum(1 for w in terms if w in combined_text)
                        if (match_count / len(terms)) >= 0.7:
                            found = True

            if not found:
                missing.append(doc_hint)

        # Only log info for unmatched citations (NEVER block)
        if missing:
            if len(missing) == len(response.citations):
                logger.info(f"[CONTRACT] Info: {len(missing)} citations not explicitly referenced in text (non-blocking).")
            else:
                logger.info(f"[CONTRACT] Minor: {len(missing)} citations ('{', '.join(missing)}') not explicitly found.")

    # ── NEW: propagate the finding instead of discarding it ────────────────
    try:
        setattr(response, "_contract_violations", list(missing))
        setattr(response, "_unverified_citation_count", len(missing))
    except Exception as e:
        # response may be a frozen dataclass / use __slots__ — don't let
        # attribute assignment failure break validation itself.
        logger.debug(f"[CONTRACT] Could not attach violation data to response object: {e}")

    if context is not None:
        context["contract_violations"] = list(missing)
        context["unverified_citation_count"] = len(missing)

    return True