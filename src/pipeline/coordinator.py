# E:\GL_AI\src\pipeline\coordinator.py
from loguru import logger
import operator
import json
import yaml
import asyncio
from pathlib import Path
from typing import Dict, Any, TypedDict, Annotated, List, Optional

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

# Contract-based abstractions (Phase 3, 3.5, 4)
from core.contracts import (
    AgentResponseProtocol, 
    BasePipelineComponent, 
    validate_agent_response, 
    PipelineFailureType,
    TrustVerdict,
    ConfidenceVerdict
)
from core.registry_loader import ModuleLoader
from core.schemas import AudienceType, CanonicalAgentResponse

# Utility functional imports
from audience.audience_classifier import AudienceClassifier 
from pipeline.grounding_gate import GroundingGate 
from verification.hallucination_guard import hallucination_guard
from verification.citation_map import citation_mapper
from audience.audience_layer import AudienceLayer
from ui.ux_layer import ux_gate, ux_allowed, UXBlockReason, UXState
from data.cache_manager import cache

import neo4j

# -----------------------------
# Reducers
# -----------------------------
def merge_dicts(a: Dict, b: Dict) -> Dict:
    res = a.copy()
    res.update(b)
    return res

# -----------------------------
# Graph State Schema
# -----------------------------
class AgentState(TypedDict):
    query: str
    intent_data: Annotated[Dict[str, Any], merge_dicts]
    history: Annotated[List[Dict[str, str]], operator.add]
    next_nodes: List[str]
    agent_outputs: Annotated[Dict[str, Any], merge_dicts]
    response: str
    intermediate_steps: List[str]
    audience: AudienceType
    # Added for V6/Governance flow
    primary_response: Any
    hallucination_verdict: Any
    grounding_result: Dict[str, Any]
    # Phase 2 UI Integration
    multi_agent_data: Annotated[Dict[str, Any], merge_dicts]
    ux_state: str
    final_output: Dict[str, Any]

# -----------------------------
# Coordinator
# -----------------------------
class AgentCoordinator:
    """
    Registry-Driven Orchestration Engine (Phase 4 Granular).
    
    Responsibilities:
    - Component lifecycle management
    - Registry resolution & Validation
    - Deterministic Graph Orchestration (Phase 4 Pure Decision Nodes)
    - UX State Machine Management (Phase 3.5)
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.initialized = False
        self._init_lock = asyncio.Lock()  # Prevent concurrent initializations
        self.components = {}
        self.agents = {}
        self.neo4j_driver = None
        
        # 1. Load Registry Metadata
        self._load_registry_metadata()
        
        # 2. Compile Graph
        self.memory_saver = MemorySaver()
        self.graph = self._build_graph()



    def _load_registry_metadata(self):
        """Loads registration maps from YAML."""
        try:
            reg_dir = Path(__file__).parent.parent / "core" / "regs"
            with open(reg_dir / "component_registry.yaml", "r") as f:
                self.comp_reg = yaml.safe_load(f).get("components", {})
            with open(reg_dir / "agent_registry.yaml", "r") as f:
                self.agent_reg = yaml.safe_load(f).get("agents", {})
            logger.info(f"[Coordinator] Registries loaded: {len(self.comp_reg)} comps, {len(self.agent_reg)} agents")
        except Exception as e:
            logger.error(f"[Coordinator] Registry load failed: {e}")
            self.comp_reg = {}
            self.agent_reg = {}

    async def initialize(self):
        """Async Lifecycle: Instantiate and load all registered components."""
        if self.initialized:
            return

        async with self._init_lock:
            # Double-check locking pattern
            if self.initialized:
                return
                
            logger.info("[Coordinator] Initializing Hardened Dynamic Registry...")

            # A. Shared Infrastructure (Neo4j)
            if not self.neo4j_driver:
                try:
                    self.neo4j_driver = neo4j.GraphDatabase.driver(
                        self.config.get("NEO4J_URI", "bolt://localhost:7687"),
                        auth=(
                            self.config.get("NEO4J_USER", "neo4j"),
                            self.config.get("NEO4J_PASSWORD", "password")
                        )
                    )
                except Exception as e:
                     logger.error(f"[FAIL] Neo4j unavailable: {e}")

            # B. Components (Engines, Tools, Classifiers)
            for cid, data in self.comp_reg.items():
                if cid in self.components:
                    continue
                try:
                    inst = ModuleLoader.instantiate(data["module"], data["class"], component_id=cid)
                    if inst:
                        comp_config = data.get("config", {})
                        comp_config.update(self.config)
                        if await inst.load(comp_config):
                            self.components[cid] = inst
                            logger.info(f"[Coordinator] Loaded component: {cid}")
                except Exception as e:
                    logger.error(f"[ERROR] Component {cid} fail: {e}")

            # C. Agents
            for aid, data in self.agent_reg.items():
                if aid in self.agents:
                    continue
                try:
                    injection = {
                        "config": self.config,
                        "component_id": aid,
                        "llm_manager": self.components.get("llm_manager")
                    }
                    if aid == "graph_legal" and self.neo4j_driver:
                        injection["neo4j_driver"] = self.neo4j_driver

                    inst = ModuleLoader.instantiate(data["module"], data["class"], **injection)
                    if inst and await inst.load(data.get("config", {})):
                        self.agents[aid] = inst
                        logger.info(f"[Coordinator] Loaded agent: {aid}")
                except Exception as e:
                    logger.error(f"[ERROR] Agent {aid} fail: {e}")

            self.initialized = True
            logger.info(f"[Coordinator] Initialization Complete. Components: {len(self.components)}, Agents: {len(self.agents)}")

    # -----------------------------
    # Helper Aliases
    # -----------------------------
    @property
    def trust_engine(self): return self.components.get("trust_engine")
    @property
    def confidence_engine(self): return self.components.get("confidence_engine")
    @property
    def fusion_engine(self): return self.components.get("fusion_engine")
    @property
    def classifier(self): return self.components.get("intent_classifier")
    @property
    def retrieval_tool(self): return self.components.get("retrieval_tool")
    @property
    def grounding_gate(self): return self.components.get("grounding_gate")
    @property
    def audience_classifier(self): return self.components.get("audience_classifier")
    @property
    def security(self): return self.components.get("security_manager")

    # -----------------------------
    # Graph Builder
    # -----------------------------
    def _build_graph(self):
        """
        Phase 4: Granular execution graph with pure decision nodes.
        """
        workflow = StateGraph(AgentState)
        
        # Nodes
        workflow.add_node("classify", self.classify_node)
        workflow.add_node("retrieval", self.retrieval_node)
        workflow.add_node("grounding_gate", self.grounding_gate_node) 
        
        workflow.add_node("legal_agent", self.legal_node)
        workflow.add_node("graph_agent", self.graph_node)
        workflow.add_node("climate_agent", self.climate_node)
        workflow.add_node("monitoring_agent", self.monitoring_node)
        workflow.add_node("awareness_agent", self.awareness_node)
        workflow.add_node("incident_agent", self.incident_node)
        workflow.add_node("summary_agent", self.summary_node)
        workflow.add_node("prediction_agent", self.prediction_node)  # Phase 3
        workflow.add_node("general_agent", self.general_node)
        
        workflow.add_node("contract_enforcer", self.contract_enforcer_node)
        workflow.add_node("hallucination_guard", self.hallucination_guard_node)
        workflow.add_node("fusion", self.fusion_node) 
        workflow.add_node("trust_engine", self.trust_engine_node) 
        workflow.add_node("confidence_engine", self.confidence_engine_node)
        workflow.add_node("ux_state", self.ux_state_node)
        
        workflow.set_entry_point("classify")

        # Routing logic
        workflow.add_conditional_edges("classify", self.route_intent, {
            "legal": "retrieval", 
            "definition": "retrieval", 
            "precedent": "retrieval",
            "awareness": "retrieval", 
            "summary": "retrieval", 
            "incident": "retrieval",
            "climate": "retrieval", 
            "monitoring": "retrieval", 
            "general": "general_agent"
        })
        
        workflow.add_edge("retrieval", "grounding_gate")
        
        # Grounding decision - Dynamic parallel routing
        workflow.add_conditional_edges("grounding_gate", self.route_after_grounding)
        
        for node in ["legal_agent", "graph_agent", "climate_agent", "monitoring_agent", 
                     "awareness_agent", "incident_agent", "general_agent"]:
            workflow.add_edge(node, "contract_enforcer")
            
        workflow.add_edge("contract_enforcer", "hallucination_guard")
        workflow.add_edge("hallucination_guard", "fusion")
        workflow.add_edge("fusion", "summary_agent") # Summary now runs after fusion
        workflow.add_edge("summary_agent", "prediction_agent")  # Phase 3: Predictions after summary
        workflow.add_edge("prediction_agent", "trust_engine") 
        workflow.add_edge("trust_engine", "confidence_engine")
        workflow.add_edge("confidence_engine", "ux_state")
        workflow.add_edge("ux_state", END)
        
        return workflow.compile(checkpointer=self.memory_saver)

    def route_after_grounding(self, state: AgentState) -> List[str]:
        """Phase 4.2 & 7: Dynamic parallel routing or failure redirection."""
        if state.get("intent_data", {}).get("failure"):
            return ["ux_state"]
        
        # Determine parallel agents based on intents
        intents = state.get("intent_data", {}).get("possible_intents", ["legal"])
        target_nodes = []
        
        mapping = {
            "legal": "legal_agent",
            "definition": "legal_agent",
            "precedent": "legal_agent",
            "awareness": "awareness_agent",
            "summary": "summary_agent",
            "incident": "incident_agent",
            "climate": "climate_agent",
            "monitoring": "monitoring_agent"
        }
        
        for i in intents:
            if i in mapping:
                target_nodes.append(mapping[i])
        
        # Phase 7: Selective Rich Routing
        # Trigger rich mode only if query is complex or explicitly about risk/prediction
        q_lower = state.get("query", "").lower()
        needs_rich = any(w in q_lower for w in ["risk", "forecast", "predict", "impact", "future"])
        
        if needs_rich:
            target_nodes.extend(["legal_agent", "awareness_agent", "climate_agent", "incident_agent", "monitoring_agent"])

        # Always ensure at least legal is present for domain queries
        if not target_nodes:
            target_nodes = ["legal_agent"]
            
        return list(set(target_nodes))

    def should_continue(self, state: AgentState) -> str:
        """Deprecated in favor of route_after_grounding but kept for compatibility."""
        if state.get("intent_data", {}).get("failure"):
            return "blocked"
        return "continue"

    def route_to_agents(self, state: AgentState) -> List[str]:
        """Deprecated in favor of route_after_grounding."""
        return self.route_after_grounding(state)

    # -----------------------------
    # Nodes
    # -----------------------------
    async def classify_node(self, state: AgentState) -> Dict:
        logger.info(f"[CLASSIFY] {state['query']}")
        q_lower = state["query"].lower()
        
        # 🚨 HARDWARE RESET: Ensure no state leakage from recycled threads (Audit Fix)
        intent_info = self.classifier.classify(state["query"])
        audience = self.audience_classifier.classify(state["query"])
        
        return {
            "intent_data": intent_info,
            "next_nodes": intent_info.get("possible_intents", [intent_info["primary_intent"]]),
            "agent_outputs": {},      # Reset outputs
            "multi_agent_data": {},   # Reset storage
            "audience": audience
        }

    def route_intent(self, state: AgentState) -> List[str]:
        return state.get("next_nodes", ["general"])

    async def retrieval_node(self, state: AgentState) -> Dict:
        logger.info("[RETRIEVAL] Legal grounding (with cache check)")
        
        async def fetch():
            return await self.retrieval_tool.execute(query=state["query"], k=6)
            
        results = await cache.get_or_fetch_async(f"retrieval:{state['query']}", fetch)
        chunks = results.get("results", [])
        logger.info(f"[RETRIEVAL] Found {len(chunks)} chunks for query: {state['query']}")
        return {"intent_data": {"retrieved_chunks": chunks}}

    async def grounding_gate_node(self, state: AgentState) -> Dict:
        """Phase 4.1: Pure decision node for grounding."""
        logger.info("[GATE] Grounding check")
        chunks = state.get("intent_data", {}).get("retrieved_chunks", [])
        decision = self.grounding_gate.evaluate(chunks)
        if not decision["allowed"]:
            return {"grounding_result": decision, "intent_data": {"failure": "SAFE_ABSTAIN", "failure_message": decision["message"]}}
        return {"grounding_result": decision, "intent_data": {"grounding_passed": True}}

    async def legal_node(self, state: AgentState) -> Dict:
        if state.get("intent_data", {}).get("failure"):
            return {}
        
        chunks = state.get("intent_data", {}).get("retrieved_chunks", [])
        
        # ── CRITICAL DEBUG LOGGING (Claude's recommendation) ─────────────
        logger.info(f"[LEGAL_NODE] Chunks available: {len(chunks)}")
        if chunks:
            first = chunks[0]
            if isinstance(first, dict):
                logger.info(f"[LEGAL_NODE] First chunk text: {first.get('text', '')[:80]}")
                logger.info(f"[LEGAL_NODE] First chunk metadata: {first.get('metadata', {})}")
            else:
                logger.info(f"[LEGAL_NODE] First chunk: {getattr(first, 'text', '')[:80]}")
        else:
            logger.warning("[LEGAL_NODE] NO CHUNKS — agent will hallucinate!")
        # ─────────────────────────────────────────────────────────────
        
        agent = self.agents.get("legal")
        if not agent:
            return {"agent_outputs": {
                "legal": self._abstain_response(
                    "legal", "Agent unavailable", state["audience"]
                )
            }}
    
        # Do NOT cache legal responses — queries are unique
        result = await agent.run(
            state["query"],
            chunks,          # ← pass chunks explicitly
            state["audience"]
        )
        
        # ── ADD THIS: Log the result for debugging ──────────────────────
        logger.info(f"[LEGAL_NODE] Agent response confidence: {getattr(result, 'confidence', 'N/A')}")
        logger.info(f"[LEGAL_NODE] Agent response abstain: {getattr(result, 'abstain', 'N/A')}")
        # ─────────────────────────────────────────────────────────────
        
        return {"agent_outputs": {"legal": result}}


    async def graph_node(self, state: AgentState) -> Dict:
        if state.get("intent_data", {}).get("failure"): return {}
        chunks = state.get("intent_data", {}).get("retrieved_chunks", [])
        agent = self.agents.get("graph_legal") or self.agents.get("legal")
        if not agent: return {"agent_outputs": {"graph": self._abstain_response("graph_legal", "Agent unavailable", state["audience"])}}
        result = await agent.run(state["query"], chunks, state["audience"])
        return {"agent_outputs": {"graph": result}}

    async def climate_node(self, state: AgentState) -> Dict:
        if state.get("intent_data", {}).get("failure"): return {}
        agent = self.agents.get("climate")
        if not agent: return {"agent_outputs": {"climate": self._abstain_response("climate", "Agent unavailable", state["audience"])}}
        result = await agent.run(state["query"], [], state["audience"])
        return {"agent_outputs": {"climate": result}}

    async def monitoring_node(self, state: AgentState) -> Dict:
        if state.get("intent_data", {}).get("failure"): return {}
        agent = self.agents.get("monitoring")
        if not agent: return {"agent_outputs": {"monitoring": self._abstain_response("monitoring", "Agent unavailable", state["audience"])}}
        result = await agent.run(state["query"], [], state["audience"])
        return {"agent_outputs": {"monitoring": result}}

    async def awareness_node(self, state: AgentState) -> Dict:
        if state.get("intent_data", {}).get("failure"): return {}
        chunks = state.get("intent_data", {}).get("retrieved_chunks", [])
        agent = self.agents.get("awareness") or self.agents.get("legal")
        if not agent: return {"agent_outputs": {"awareness": self._abstain_response("awareness", "Agent unavailable", state["audience"])}}
        result = await agent.run(state["query"], chunks, state["audience"])
        return {"agent_outputs": {"awareness": result}}

    async def incident_node(self, state: AgentState) -> Dict:
        if state.get("intent_data", {}).get("failure"): return {}
        chunks = state.get("intent_data", {}).get("retrieved_chunks", [])
        agent = self.agents.get("incident") or self.agents.get("legal")
        if not agent: return {"agent_outputs": {"incident": self._abstain_response("incident", "Agent unavailable", state["audience"])}}
        result = await agent.run(state["query"], chunks, state["audience"])
        return {"agent_outputs": {"incident": result}}

    async def summary_node(self, state: AgentState) -> Dict:
        if state.get("intent_data", {}).get("failure"): return {}
        # NEW: Check if summary is actually needed
        intents = state.get("intent_data", {}).get("possible_intents", [])
        if not any(i in ["legal", "incident", "summary"] for i in intents):
            return {}

        chunks = state.get("intent_data", {}).get("retrieved_chunks", [])
        agent = self.agents.get("summary")
        if not agent: return {}
        
        # Pass multi_agent_data for context sharing
        context = {"agent_results": state.get("multi_agent_data", {})}
        result = await agent.run(state["query"], chunks, state["audience"], context=context)
        
        return {
            "agent_outputs": {"summary": result},
            "multi_agent_data": {"summary": result}
        }

    async def prediction_node(self, state: AgentState) -> Dict:
        """Phase 3: Predictive Analytics node — runs after summary, before trust engine."""
        if state.get("intent_data", {}).get("failure"): return {}
        
        # Only run predictions for legal/incident/climate queries OR risk keywords
        intents = state.get("intent_data", {}).get("possible_intents", [])
        q_lower = state.get("query", "").lower()
        has_risk_query = any(w in q_lower for w in ["risk", "forecast", "predict", "deforestation", "fire"])
        
        if not (any(i in ["legal", "incident", "climate", "monitoring"] for i in intents) or has_risk_query):
            return {}
        
        agent = self.agents.get("prediction")
        if not agent:
            logger.info("[PREDICTION] PredictionAgent not registered, skipping")
            return {}
        
        chunks = state.get("intent_data", {}).get("retrieved_chunks", [])
        # Pass all agent results as context
        context = {"agent_results": state.get("multi_agent_data", {})}
        
        try:
            result = await agent.run(state["query"], chunks, state["audience"], context=context)
            logger.info(f"[PREDICTION] Generated predictions: risk={result.graph_metadata.get('predictions', {}).get('deforestation', {}).get('risk_level', 'N/A')}")
        except Exception as e:
            logger.error(f"[PREDICTION] Failed: {e}")
            return {}
        
        return {
            "agent_outputs": {"prediction": result},
            "multi_agent_data": {"prediction": result}
        }

    async def general_node(self, state: AgentState) -> Dict:
        if state.get("intent_data", {}).get("failure"): return {}
        response = self._abstain_response("GeneralAgent", "Query falls outside domain.", state["audience"])
        return {"agent_outputs": {"general": response}}

    def _abstain_response(self, name: str, message: str, audience: AudienceType) -> CanonicalAgentResponse:
        return CanonicalAgentResponse(
            simple_explanation=message,
            legal_explanation=message,
            citations=[],
            abstain=True,
            agent_name=name,
            audience=audience,
            confidence=0.0,
            source_chunks=[],
            graph_metadata={},
            validation_passed=True,
            errors=[]
        )

    async def contract_enforcer_node(self, state: AgentState) -> Dict:
        """Phase 3.5: Semantic Contract Enforcement."""
        if state.get("intent_data", {}).get("failure"): return {}
        logger.info("[ENFORCER] Validating semantic contracts")

        # DEBUG: what did we receive from prior nodes?
        logger.debug(f"[ENFORCER][DEBUG] agent_outputs keys: {list(state.get('agent_outputs', {}).keys())}")
        logger.debug(f"[ENFORCER][DEBUG] incoming intent_data: {state.get('intent_data', {})}")

        valid_outputs = {}
        # NEW: collect per-agent contract violations so ConfidenceEngine can
        # actually deduct for them instead of the finding being log-only.
        violations_by_agent: Dict[str, list] = {}
        total_unverified = 0
        for name, response in state["agent_outputs"].items():
            per_call_context: Dict[str, Any] = {}
            is_valid = validate_agent_response(response, per_call_context)

            # DEBUG: raw output of validate_agent_response for this agent
            logger.debug(f"[ENFORCER][DEBUG] agent='{name}' is_valid={is_valid} "
                         f"per_call_context={per_call_context}")

            if is_valid:
                valid_outputs[name] = response

            # validate_agent_response also attaches this directly to the
            # response object as a fallback — read whichever is populated.
            response_attr_violations = getattr(response, "_contract_violations", None)
            agent_violations = (
                per_call_context.get("contract_violations")
                or response_attr_violations
                or []
            )

            # DEBUG: show which source the violations came from (context vs attr vs none)
            source = ("per_call_context" if per_call_context.get("contract_violations")
                      else "response_attr" if response_attr_violations
                      else "none")
            logger.debug(f"[ENFORCER][DEBUG] agent='{name}' violation_source={source} "
                         f"agent_violations={agent_violations}")

            if agent_violations:
                violations_by_agent[name] = agent_violations
                total_unverified += len(agent_violations)

        if not valid_outputs:
            logger.debug("[ENFORCER][DEBUG] No valid_outputs — returning CONTRACT_VIOLATION failure")
            return {"intent_data": {"failure": "CONTRACT_VIOLATION"}}

        # Preserve any existing intent_data fields (e.g. grounding_coverage
        # set by an earlier node) and merge in the new violation data —
        # ConfidenceEngine reads context["intent_data"], so this is the one
        # place that needs to change for the deduction to actually apply.
        existing_intent_data = state.get("intent_data", {}) or {}
        merged_intent_data = {
            **existing_intent_data,
            "contract_violations": violations_by_agent,
            "unverified_citation_count": total_unverified,
        }

        if total_unverified > 0:
            logger.info(
                f"[ENFORCER] {total_unverified} unverified citation(s) across "
                f"{len(violations_by_agent)} agent(s) recorded for confidence scoring."
            )

        # DEBUG: final shape being returned to the graph state
        logger.debug(f"[ENFORCER][DEBUG] returning merged_intent_data: {merged_intent_data}")
        logger.debug(f"[ENFORCER][DEBUG] valid_outputs keys: {list(valid_outputs.keys())}")

        return {"agent_outputs": valid_outputs, "intent_data": merged_intent_data}

    async def hallucination_guard_node(self, state: AgentState) -> Dict[str, Any]:
        """Phase 4.3: Pure signal check for hallucinations."""
        if state.get("intent_data", {}).get("failure"): return {}
        logger.info("[GUARD] Hallucination check")
        
        outputs = state.get("agent_outputs", {})
        if not outputs: 
            logger.warning("[GUARD] No agent outputs found for hallucination check.")
            return {}
        
        # Prioritize legal response for hallucination checking
        primary = outputs.get("legal") or outputs.get("primary")
        if not primary:
            # If no legal/primary, take the first available non-empty result
            valid_vals = [v for v in outputs.values() if v]
            if not valid_vals: return {}
            primary = valid_vals[0]
        
        if not primary or getattr(primary, "abstain", False): 
            return {}
        
        result = hallucination_guard(primary)
        
        # 🚨 NEW: Inject coverage metrics into the response object for ConfidenceEngine
        primary.grounding_coverage = getattr(result, "coverage_ratio", 0.0)
        logger.info(f"[GUARD] Grounding metrics injected: {primary.grounding_coverage}")
            
        if result.blocked:
            return {"hallucination_verdict": result, "intent_data": {"failure": "HALLUCINATION_DETECTED"}}
            
        return {
            "hallucination_verdict": result, 
            "intent_data": {
                "hallucination_passed": True,
                "grounding_coverage": getattr(result, "coverage_ratio", 0.0)
            }
        }

    async def fusion_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fusion Node - Retains ALL valid agent outputs for multi-domain responses.
        """
        logger.info("[FUSION] Processing multi-agent outputs")
        
        agent_outputs = state.get("agent_outputs", [])
        if not agent_outputs:
            logger.warning("[FUSION] No agent outputs available")
            return {
                **state,
                "primary_response": None,
                "multi_agent_data": {}
            }
        
        # Structure to hold all agent responses by type
        multi_agent_data = {
            "primary": None  # Keep primary for backward compatibility
        }
        
        # Process each agent output
        # Filter out None responses early (Audit Fix)
        raw_list = agent_outputs.values() if isinstance(agent_outputs, dict) else agent_outputs
        responses_list = [r for r in raw_list if r is not None]
        
        if not responses_list:
            logger.warning("[FUSION] All agent responses were None or invalid")
            return {
                **state,
                "primary_response": None,
                "multi_agent_data": {}
            }

        for output in responses_list:
            agent_name = ""
            if hasattr(output, "agent_name"):
                agent_name = output.agent_name.lower()
            elif isinstance(output, dict):
                agent_name = output.get("agent_name", "").lower()
            
            # Categorize by agent type
            if "law" in agent_name or "legal" in agent_name:
                multi_agent_data["legal"] = output
                if not multi_agent_data["primary"]:
                    multi_agent_data["primary"] = output
                    logger.info("[FUSION] LegalAgent selected as primary")
            elif "awareness" in agent_name:
                multi_agent_data["awareness"] = output
            elif "summary" in agent_name:
                multi_agent_data["summary"] = output
            elif "incident" in agent_name:
                multi_agent_data["incident"] = output
            elif "climate" in agent_name:
                multi_agent_data["climate"] = output
            elif "monitoring" in agent_name:
                multi_agent_data["monitoring"] = output
            elif "prediction" in agent_name:
                multi_agent_data["prediction"] = output
            
            elif "graph" in agent_name:
                multi_agent_data["graph_legal"] = output
                logger.info("[FUSION] GraphLegalAgent data captured")
        
        # Ensure we have at least one response as primary
        if not multi_agent_data["primary"] and responses_list:
            # Filter again to be absolutely sure
            valid_responses = [r for r in responses_list if r]
            if valid_responses:
                multi_agent_data["primary"] = valid_responses[0]
                logger.info(f"[FUSION] Using first available agent ({getattr(multi_agent_data['primary'], 'agent_name', 'unknown')}) as primary")
        
        return {
            **state,
            "primary_response": multi_agent_data["primary"],
            "multi_agent_data": multi_agent_data,
            "intent_data": {**state.get("intent_data", {}), "active_response": multi_agent_data["primary"]}
        }

    async def trust_engine_node(self, state: AgentState) -> Dict:
        """Phase 4.2: Pure trust evaluation signal."""
        if state.get("intent_data", {}).get("failure"): return {}
        logger.info("[TRUST] Evaluating source credibility")
        response = state["intent_data"].get("active_response")
        
        # Citation Map integrated here as data prep for trust
        cited_sources = citation_mapper(response)
        if not cited_sources:
             logger.warning("[TRUST] No explicit citations found via mapping. Proceeding with grounding evaluation.")
             # Pass empty list - TrustEngine will apply penalty but NOT zero out.
             
        trust = self.trust_engine.evaluate(response, cited_sources, audience=state["audience"])
        if not trust.is_trustworthy:
             logger.warning(f"[TRUST] Low trust verdict: {trust.reason}. Score: {trust.score}. Proceeding to confidence engine for weighted evaluation.")
             # Allow pipeline to continue to confidence engine
             
        return {"intent_data": {"trust_passed": True, "trust_score": trust.score, "cited_sources": cited_sources}}

    async def confidence_engine_node(self, state: AgentState) -> Dict:
        """Phase 4.2: Pure confidence calculation."""
        if state.get("intent_data", {}).get("failure"): return {}
        logger.info("[CONFIDENCE] Calculating final uncertainty")
        
        # Get active response (which is a reference to the primary in agent_outputs/multi_agent_data)
        response = state["intent_data"].get("active_response")
        if not response:
             logger.warning("[CONFIDENCE] No active response found for confidence calculation.")
             return {}
             
        trust_score = state["intent_data"].get("trust_score", 0.0)
        
        # Reconstruct verdict object for engine
        verdict = TrustVerdict(is_trustworthy=True, score=trust_score, reason="TRUST_OK")
        
        # Phase 2.2 Polish: Use state-passed grounding coverage if available
        grounding_coverage = state.get("intent_data", {}).get("grounding_coverage")
        if grounding_coverage is not None:
            logger.info(f"[CONFIDENCE] Using state-passed grounding coverage: {grounding_coverage}")
        
        confidence = self.confidence_engine.calculate(
            response, 
            verdict, 
            audience=state["audience"],
            context={
                "agent_results": state.get("multi_agent_data", {}),
                "query": state.get("query", "")
            }
        )
        
        # 🚨 CRITICAL FIX: Mutate the response object directly so confidence PERSISTS
        if response:
            response.confidence = confidence.score
            logger.info(f"[CONFIDENCE] Mutated response with score: {confidence.score}")
            
        return {"intent_data": {**state.get("intent_data", {}), "confidence_score": confidence.score}}

    # [DEPRECATED Phase 1 node removed]

    async def ux_state_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        UX State Resolution - Packages multi-agent responses for UI.
        """
        logger.info("[UX_STATE] Packaging multi-agent responses")
        
        multi_agent_data = state.get("multi_agent_data", {})
        primary_response = state.get("primary_response")
        
        if not primary_response and not multi_agent_data:
            logger.warning("[UX_STATE] No responses available")
            return {
                **state,
                "ux_state": "NO_RESPONSE",
                "final_output": "No response generated. Please try rephrasing your question."
            }
        
        # Build structured output for UI
        final_output = {
            "primary": None,
            "legal": None,
            "climate": None,
            "monitoring": None,
            "graph_legal": None,
            "has_multi_agent": False
        }
        
        # Process each agent type into serializable format
        for agent_type, agent_data in multi_agent_data.items():
            if not agent_data:
                continue
                
            final_output["has_multi_agent"] = True
            
            if hasattr(agent_data, "model_dump"):
                # Pydantic v2
                final_output[agent_type] = agent_data.model_dump()
            elif hasattr(agent_data, "__dict__"):
                # Custom object
                data = agent_data.__dict__.copy()
                # Handle citations specially
                if "citations" in data and data["citations"]:
                    data["citations"] = [
                        c.model_dump() if hasattr(c, "model_dump") else 
                        c.__dict__ if hasattr(c, "__dict__") else 
                        {"document": str(c)} for c in data["citations"]
                    ]
                final_output[agent_type] = data
            elif isinstance(agent_data, dict):
                final_output[agent_type] = agent_data
            else:
                final_output[agent_type] = {"text": str(agent_data)}
        
        # Ensure primary is set
        if primary_response and not final_output["primary"]:
            if hasattr(primary_response, "model_dump"):
                final_output["primary"] = primary_response.model_dump()
            elif hasattr(primary_response, "__dict__"):
                final_output["primary"] = primary_response.__dict__
            elif isinstance(primary_response, dict):
                final_output["primary"] = primary_response
        
        logger.info(f"[UX_STATE] Multi-agent data packaged: {[k for k,v in final_output.items() if v and k != 'primary']}")
        
        return {
            **state,
            "ux_state": "SUCCESS",
            "final_output": final_output
        }

    async def run(self, query: str, thread_id: str = None) -> Dict[str, Any]:
        """
        Main execution entry point (Phase 4 Orchestration).
        Ensures thread isolation to prevent state pollution.
        """
        try:
            import uuid
            # Use unique thread ID if none provided (Audit Fix for state pollution)
            active_thread_id = thread_id or str(uuid.uuid4())
            
            await self.initialize()
            
            # FIX: Check if security exists before calling
            if self.security and not self.security.check_request("ui", query):
                return {"response": "Blocked by security policy."}

            initial_state = {
                "query": query, 
                "intent_data": {}, 
                "history": [], 
                "next_nodes": [],
                "agent_outputs": {}, 
                "response": "", 
                "intermediate_steps": [],
                "audience": AudienceType.DUAL,
                "multi_agent_data": {}  # Explicitly initialize
            }
            config = {"configurable": {"thread_id": active_thread_id}}
            return await self.graph.ainvoke(initial_state, config=config)
        except Exception as e:
            logger.error(f"[FATAL] Coordinator failure: {e}")
            # Fix #1: Recovery for penalty_display NameError specifically
            penalty_info = {'species': 'unknown', 'base_penalty': 0, 'multiplier': 1.0}
            penalty_display = "Penalty information unavailable"
            
            return {
                "response": "Critical system failure.", 
                "error": str(e),
                "penalty_display": penalty_display
            }
