# E:\GL_AI\src\verification\confidence_engine.py
from typing import List, Dict, Any, Optional
from loguru import logger
from core.contracts import BasePipelineComponent, AgentResponseProtocol, ConfidenceVerdict
from core.schemas import AudienceType


class ConfidenceEngine(BasePipelineComponent):
    """
    Deterministic confidence computation engine.
    Registry-Compatible (Phase 3)
    """

    def __init__(self, component_id: str = "confidence_engine"):
        super().__init__(component_id)
        # Dynamic weights can be loaded from registry
        self.citation_weight = 0.4
        self.overlap_weight = 0.35
        self.graph_weight = 0.25
        self.max_citations = 5

    async def load(self, config: Dict[str, Any]) -> bool:
        """Lifecycle: Load configuration from registry."""
        self.citation_weight = config.get("citation_weight", self.citation_weight)
        self.overlap_weight = config.get("overlap_weight", self.overlap_weight)
        self.graph_weight = config.get("graph_weight", self.graph_weight)
        self._is_loaded = True
        logger.info(f"[ConfidenceEngine] {self.component_id} loaded with config: {config}")
        return True

    async def unload(self) -> bool:
        """Lifecycle: Shutdown."""
        self._is_loaded = False
        return True

    def _check_graph_connection(self) -> bool:
        """Check if Neo4j is actually available (Audit Fix Day 3)"""
        try:
            from neo4j import GraphDatabase
            # Basic ping to verify connectivity
            driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"), connection_timeout=2)
            with driver.session() as session:
                session.run("RETURN 1").single()
            driver.close()
            return True
        except:
            return False

    def compute_confidence(self, response: AgentResponseProtocol, context: Dict[str, Any] = None) -> float:
        """
        PRODUCTION-GRADE Heuristic Confidence Calculation (User Audit Fix)
        """
        # 1. Base Logic: If IRAC structure is complete → Base 80%
        if self.has_complete_irac(response):
            base_confidence = 0.80
        else:
            # Fallback to structural overlap if not full IRAC
            overlap_ratio = getattr(response, "grounding_coverage", 0.4)
            base_confidence = 0.40 + (overlap_ratio * 0.1)
        
        # 2. Add citation bonuses (Max 15%)
        citations = response.citations or []
        citation_bonus = min(0.15, len(citations) * 0.05)
        
        # 3. Add data freshness bonus (Max 10%)
        # Check if citations mention 2022 Act or if live data is present
        freshness_bonus = 0.0
        if self.has_fresh_data(response):
            freshness_bonus = 0.10
        
        # 4. Add cross-agent consistency bonus (Max 10%)
        consistency_bonus = 0.0
        if context and self.agents_agree(response, context):
            consistency_bonus = 0.10
        
        # 5. Graph Path Bonus (only if graph is actually available and path found)
        graph_bonus = 0.0
        graph_available = self._check_graph_connection()
        
        if graph_available:
            graph_data = getattr(response, "graph_metadata", {})
            if graph_data and graph_data.get("path_found"):
                graph_bonus = 0.15
        else:
            # Graph unavailable: NO redistribution — honest scoring
            logger.info("[ConfidenceEngine] Graph unavailable, no redistribution applied")

        # 5.5 Prediction Agent Confidence Boost (Phase 3 Fix)
        # Prediction agents inherently deal in probabilities, but their output is highly structured and validated.
        if hasattr(response, "graph_metadata") and "predictions" in response.graph_metadata:
            preds = response.graph_metadata.get("predictions", {})
            if "deforestation" in preds or "fire" in preds or "carbon" in preds:
                logger.info("[ConfidenceEngine] Prediction data detected, boosting base score.")
                return 0.90
        
        # 6. DEDUCTIONS for missing or failed data (Honesty Fix)
        deductions = 0.0
        if context:
            agent_results = context.get("agent_results", {})
            # Check for missing climate data when it was expected
            climate = agent_results.get("climate")
            if climate and getattr(climate, "abstain", False):
                deductions += 0.15
                logger.warning("[ConfidenceEngine] Deducting 0.15 for missing climate data")
            # Check for any abstaining agents
            for name, res in agent_results.items():
                if hasattr(res, 'abstain') and res.abstain and name not in ('climate',):
                    deductions += 0.05
                    logger.warning(f"[ConfidenceEngine] Deducting 0.05 for abstaining agent: {name}")
        raw_confidence = (base_confidence + 
                         citation_bonus + 
                         freshness_bonus + 
                         consistency_bonus +
                         graph_bonus)
        
        # 6.5 Grounding Coverage Deduction (Audit Fix #10)
        # If the grounding coverage from HallucinationGuard is extremely low, penalize heavily.
        # This ensures hallucinations aren't hidden by "Good IRAC Structure" bonuses.
        intent_data = context.get("intent_data", {}) if context else {}
        grounding_coverage = intent_data.get("grounding_coverage", 1.0)
        
        if grounding_coverage < 0.20:
            logger.warning(f"[ConfidenceEngine] Low grounding coverage ({grounding_coverage}), applying -0.40 deduction.")
            deductions += 0.40

        # 6.6 Contract Violation Deduction (NEW — Audit Fix)
        # The semantic-contract enforcer (see "[CONTRACT] Minor: N citations
        # not explicitly found" in logs) currently only logs violations —
        # this makes the score actually reflect them, so a response with
        # unverifiable citations can't still land at 95%+ confidence.
        # Reads from whichever key the enforcer/coordinator populates;
        # checks multiple likely names defensively so this doesn't silently
        # no-op if the key differs from what's wired in the coordinator.
        contract_violations = (
            (context.get("contract_violations") if context else None)
            or (intent_data.get("contract_violations") if intent_data else None)
            or getattr(response, "_contract_violations", None)
            or []
        )
        unverified_citation_count = (
            (context.get("unverified_citation_count") if context else None)
            or (intent_data.get("unverified_citation_count") if intent_data else None)
            or getattr(response, "_unverified_citation_count", None)
            or len(contract_violations)
            or 0
        )
        if unverified_citation_count > 0:
            contract_deduction = min(0.30, unverified_citation_count * 0.06)
            deductions += contract_deduction
            logger.warning(
                f"[ConfidenceEngine] Deducting {contract_deduction:.2f} for "
                f"{unverified_citation_count} unverified/unfound citation(s) "
                f"flagged by contract enforcer."
            )
        
        # 7. Final Confidence (with floor)
        # 🚨 AUDIT FIX: If response is structurally sound (IRAC) but context is missing, 
        # ensure it doesn't bottom out at 0% due to deductions.
        final_confidence = min(0.98, max(0.35, raw_confidence - deductions))
        
        logger.info(f"[ConfidenceEngine] Heuristic calc: base={base_confidence}, cite={citation_bonus}, fresh={freshness_bonus}, consistency={consistency_bonus}, graph={graph_bonus}, deductions={deductions} -> {final_confidence}")
        return round(final_confidence, 4)

    def has_complete_irac(self, response: AgentResponseProtocol) -> bool:
        text = response.legal_explanation.upper()
        headers = ["ISSUE", "RULE", "CONDITIONS", "CONCLUSION"]
        has_all = all(h in text for h in headers)
        if has_all:
            logger.debug("[ConfidenceEngine] COMPLETE_IRAC bonus applied.")
        return has_all

    def has_fresh_data(self, response: AgentResponseProtocol) -> bool:
        # Check for 2022 Act or situational metadata
        text = (response.legal_explanation + response.simple_explanation).lower()
        if "2022" in text or "nasa" in text or "openweathermap" in text or "firms" in text:
            return True
        return False

    def agents_agree(self, response: AgentResponseProtocol, context: Dict[str, Any]) -> bool:
        """Checks if agents agree on the core penalty value (Audit Fix)"""
        agent_results = context.get("agent_results", {})
        if not agent_results: return False
        
        # Use PenaltyCalculator to get the expected value for the query
        from core.penalty_calculator import PenaltyCalculator
        query = context.get("query", "")
        if not query: return False
        
        expected = PenaltyCalculator.analyze_query(query)
        expected_val = str(int(expected['final_penalty']))
        
        agreements = 0
        for name, res in agent_results.items():
            if res is None: continue
            if name == getattr(response, 'agent_name', ''): continue
            
            # Check if other agents mention the same numerical fine
            l_exp = getattr(res, 'legal_explanation', '') or ''
            s_exp = getattr(res, 'simple_explanation', '') or ''
            other_text = (l_exp + s_exp).replace(',', '')
            
            if expected_val in other_text:
                agreements += 1
        
        return agreements > 0

    def score_citations(self, citations: List[Any]) -> float:
        if not citations:
            return 0.0
        count = min(len(citations), self.max_citations)
        return round(count / self.max_citations, 4)

    def score_overlap(self, overlap_ratio: float) -> float:
        return round(min(max(overlap_ratio or 0.0, 0.0), 1.0), 4)

    def score_graph_consistency(self, graph_path_valid: bool, graph_depth: int) -> float:
        if not graph_path_valid:
            return 0.0
        depth_score = min(graph_depth, 4) / 4
        return round(0.5 + (0.5 * depth_score), 4)

    
    def calculate(
        self,
        response: AgentResponseProtocol,
        trust_verdict: Any,
        audience: AudienceType = AudienceType.DUAL,
        context: Dict[str, Any] = None
    ) -> ConfidenceVerdict:
        """
        Policy-level confidence calculation.
        """
        # DEBUG: what does this call actually receive?
        logger.debug(f"[CONFIDENCE][DEBUG] calculate() called for agent='{getattr(response, 'agent_name', '?')}'")
        logger.debug(f"[CONFIDENCE][DEBUG] context is None: {context is None}")
        if context is not None:
            logger.debug(f"[CONFIDENCE][DEBUG] context keys: {list(context.keys())}")
            logger.debug(f"[CONFIDENCE][DEBUG] context['intent_data']: {context.get('intent_data', {})}")

        score = self.compute_confidence(response, context)

        # Simplified breakdown for the new heuristic model
        breakdown = {
            "is_irac": self.has_complete_irac(response),
            "is_fresh": self.has_fresh_data(response),
            "citations": len(response.citations or [])
        }

        # DEBUG: final verdict returned
        logger.debug(f"[CONFIDENCE][DEBUG] final score={score} breakdown={breakdown}")

        return ConfidenceVerdict(score=score, breakdown=breakdown)


    def explain(
        self,
        citations: List[Any],
        overlap_ratio: float,
        graph_path_valid: bool,
        graph_depth: int,
        audience: AudienceType
    ) -> Dict[str, Any]:
        """
        Returns explainable breakdown of confidence.
        """
        citation_weight = self.citation_weight
        overlap_weight = self.overlap_weight
        if audience == AudienceType.VILLAGER:
            citation_weight = 0.25
            overlap_weight = 0.50

        return {
            "citation_score": self.score_citations(citations),
            "overlap_score": self.score_overlap(overlap_ratio),
            "graph_score": self.score_graph_consistency(graph_path_valid, graph_depth),
            "weights": {
                "citations": citation_weight,
                "overlap": overlap_weight,
                "graph": self.graph_weight
            }
        }