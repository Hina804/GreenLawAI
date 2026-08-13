from typing import Dict, Any, List
import re
from loguru import logger
import neo4j

from .base_agent import BaseAgent
from core.schemas import CanonicalAgentResponse, Citation, AudienceType


class GraphLawAgent(BaseAgent):
    """
    GraphLawAgent — STRICT STRUCTURAL PRODUCER

    Role:
    - Traverse legal graph only
    - Extract LAW → SECTION → CLAUSE → TEXT relations
    - NO generation
    - NO prompts
    - NO JSON
    - NO schema validation
    - NO fusion
    - NO confidence logic
    - NO hallucination logic
    - NO UI logic
    """

    def __init__(self, config: Dict[str, Any], neo4j_driver: neo4j.Driver, component_id: str = "graph_legal", llm_manager=None):
        super().__init__(
            name="GraphLawAgent",
            component_id=component_id,
            tools=[],
            config=config
        )
        self.driver = neo4j_driver
        self.llm_manager = llm_manager

    # -------------------------
    # Graph traversal
    # -------------------------
    async def _graph_traverse(self, query: str) -> List[Dict[str, Any]]:
        """
        STRICT PATH:
        LAW → SECTION → CLAUSE → TEXT
        """

        cypher = """
        MATCH (l:Law)-[:HAS_SECTION]->(s:Section)
              -[:HAS_CLAUSE]->(c:Clause)
              -[:HAS_TEXT]->(t:Text)
        WHERE toLower(t.content) CONTAINS toLower($q)
           OR toLower(c.title) CONTAINS toLower($q)
           OR toLower(s.title) CONTAINS toLower($q)
        RETURN 
            l.title      AS law_title,
            s.title      AS section,
            c.title      AS clause,
            t.content    AS text,
            t.id         AS text_id
        LIMIT 10
        """

        try:
            with self.driver.session() as session:
                res = session.run(cypher, q=query)
                return [r.data() for r in res]
        except Exception as e:
            logger.error(f"[GraphLawAgent] Neo4j traversal error: {e}")
            return []

    # -------------------------
    # Producer entrypoint
    # -------------------------
    async def run(
        self,
        query: str,
        retrieved_chunks: list,
        audience: AudienceType
    ) -> CanonicalAgentResponse:

        if not self.driver:
            return CanonicalAgentResponse(
                simple_explanation="Legal graph database is not available.",
                legal_explanation="Graph source is offline.",
                citations=[],
                abstain=True,
                agent_name=self.name,
                audience=audience,
                confidence=0.0,
                source_chunks=[],
                graph_metadata={},
                validation_passed=False,
                errors=["GRAPH_OFFLINE"]
            )

        results = await self._graph_traverse(query)

        if not results:
            return CanonicalAgentResponse(
                simple_explanation="No connected legal structure was found in the law graph.",
                legal_explanation="The legal knowledge graph contains no matching statutory relationships for this query.",
                citations=[],
                abstain=True,
                agent_name=self.name,
                audience=audience,
                confidence=0.0,
                source_chunks=[],
                graph_metadata={},
                validation_passed=False,
                errors=["NO_GRAPH_MATCH"]
            )

        # Transform graph outputs to chunk format for Synthesizer Pipeline
        retrieved_chunks = []
        for r in results:
            retrieved_chunks.append({
                "text": r.get("text", ""),
                "chunk_id": str(r.get("text_id")),
                "metadata": {
                    "law_title": r.get("law_title"),
                    "section": r.get("section"),
                    "clause": r.get("clause"),
                    "type": "section" # Forcing section type to trigger ranking boosts safely
                },
                "graph_data": r
            })

        # -------------------------
        # Legal Synthesizer Intelligence Layer
        # -------------------------
        from pipeline.legal_synthesizer.clause_ranker import ClauseRanker
        from pipeline.legal_synthesizer.deduplicator import Deduplicator
        from pipeline.legal_synthesizer.section_builder import SectionBuilder
        from pipeline.legal_synthesizer.synthesizer import LegalSynthesizer
        from pipeline.legal_synthesizer.validator import OutputValidator
        from pipeline.legal_synthesizer.formatter import OutputFormatter

        ranker = ClauseRanker(max_tokens=1200)
        deduper = Deduplicator()
        builder = SectionBuilder()
        synth = LegalSynthesizer()
        validator = OutputValidator()
        formatter = OutputFormatter()

        from pipeline.legal_synthesizer.intent_mode import LegalIntentMode

        # Extract strict intent mode from query
        q_lower = query.lower()
        if any(w in q_lower for w in ["what is", "define", "definition", "meaning", "meant by"]):
            intent_mode = LegalIntentMode.DEFINITION
        elif any(w in q_lower for w in ["penalty", "fine", "imprisonment", "punish", "offence"]):
            intent_mode = LegalIntentMode.PENALTY
        elif any(w in q_lower for w in ["arrest", "warrant"]):
            intent_mode = LegalIntentMode.ARREST
        else:
            intent_mode = LegalIntentMode.GENERAL

    def _filter_by_intent(self, chunks: list, intent_mode: Any) -> list:
        """Relaxed Intent Filtering (V4.1)."""
        from pipeline.legal_synthesizer.intent_mode import LegalIntentMode
        if intent_mode not in [LegalIntentMode.DEFINITION, LegalIntentMode.PENALTY]:
            return chunks
            
        filtered = []
        import re
        for chunk in chunks:
            text = chunk.get("text", "").lower()
            from pipeline.legal_synthesizer.deduplicator import Deduplicator
            deduper = Deduplicator()
            text = deduper.clean_raw_text(text).lower()
            
            meta = chunk.get("metadata", {})

            if intent_mode == LegalIntentMode.DEFINITION:
                if meta.get("type") == "definition":
                    filtered.append(chunk)
                elif re.search(r'["\'][^"\']+["\']\s+(?:means|includes)', text):
                    filtered.append(chunk)
                elif re.search(r'^\s*\(?\w\)?\s+["\'][^"\']+["\']', text):
                    filtered.append(chunk)
                elif "means" in text and "includes" in text:
                    filtered.append(chunk)

            elif intent_mode == LegalIntentMode.PENALTY:
                # V5 Sharpened Filter: Penalty queries must contain core penalty terms
                penalty_terms = ["fine", "penalty", "imprisonment", "punish", "offender", "liable", "conviction", "schedule", "rs."]
                if meta.get("category") == "penalty" or meta.get("type") == "penalty":
                    filtered.append(chunk)
                elif any(w in text for w in penalty_terms):
                    filtered.append(chunk)

        return filtered

    def _species_intersection_filter(self, chunks: list, query: str) -> list:
        """Soft Species Intersection (V4.1): Fallback if 0 results."""
        species_terms = ["deodar", "cedrus deodara", "chir", "pine", "spruce", "diyar", "kail"]
        matched_species = [s for s in species_terms if s in query.lower()]
        
        if not matched_species: return chunks

        filtered = []
        for chunk in chunks:
            text = chunk.get("text", "").lower()
            if any(s in text for s in matched_species):
                filtered.append(chunk)
        
        if not filtered:
            logger.info(f"[GraphLawAgent] Species intersection for {matched_species} yielded 0. Falling back to all chunks.")
            return chunks
            
        return filtered

    async def _retrieve_from_act(self, act_name: str) -> list:
        """Helper for cross-reference expansion."""
        from tools.legal_tools import LegalSearchTool
        search_tool = LegalSearchTool()
        if await search_tool.load(self.config):
            res = await search_tool.execute(query=f"definitions and provisions in {act_name}", k=3)
            if res.get("status") == "success":
                return res.get("results", [])
        return []
    async def _expand_cross_references(self, chunks: list, depth: int = 0) -> list:
        """Priority 5: Cross-Reference Resolution (V5 Recursive)."""
        if depth > 1: return chunks
        
        expanded = []
        seen_texts = set()
        for c in chunks:
            seen_texts.add(c.get("text", "").lower())
            expanded.append(c)
        
        for chunk in chunks:
            text = chunk.get("text", "")
            
            # Detect "as defined in" markers
            if any(w in text.lower() for w in ["as defined in", "defined under", "referred to in"]):
                # Extract act name roughly
                act_match = re.search(r'(?:defined\s+in|under|to\s+in)\s+the\s+([^,.;)]+Act(?:\s+\d+)?)', text, re.I)
                if act_match:
                    act_name = act_match.group(1).strip()
                    logger.info(f"[GraphLawAgent] Resolving cross-reference: {act_name}")
                    additional = await self._retrieve_from_act(act_name)
                    
                    new_chunks = []
                    for ad in additional:
                        if ad.get("text", "").lower() not in seen_texts:
                            # V5.1 Force definition type to ensure survival through ranker
                            ad["metadata"] = ad.get("metadata", {})
                            ad["metadata"]["type"] = "definition"
                            new_chunks.append(ad)
                            seen_texts.add(ad.get("text", "").lower())
                    
                    if new_chunks:
                        # Recursive call for the new chunks
                        recursive_chunks = await self._expand_cross_references(new_chunks, depth=depth + 1)
                        expanded.extend(recursive_chunks)
                        
        return expanded

    async def run(
        self,
        query: str,
        retrieved_chunks: list,
        audience: AudienceType
    ) -> CanonicalAgentResponse:

        if not self.driver:
            return CanonicalAgentResponse(
                simple_explanation="Legal graph database is not available.",
                legal_explanation="Graph source is offline.",
                citations=[],
                abstain=True,
                agent_name=self.name,
                audience=audience,
                confidence=0.0,
                source_chunks=[],
                graph_metadata={},
                validation_passed=False,
                errors=["GRAPH_OFFLINE"]
            )

        results = await self._graph_traverse(query)

        if not results:
            return CanonicalAgentResponse(
                simple_explanation="No connected legal structure was found in the law graph.",
                legal_explanation="The legal knowledge graph contains no matching statutory relationships for this query.",
                citations=[],
                abstain=True,
                agent_name=self.name,
                audience=audience,
                confidence=0.0,
                source_chunks=[],
                graph_metadata={},
                validation_passed=False,
                errors=["NO_GRAPH_MATCH"]
            )

        # Transform graph outputs to chunk format for Synthesizer Pipeline
        raw_chunks = []
        for r in results:
            raw_chunks.append({
                "text": r.get("text", ""),
                "chunk_id": str(r.get("text_id")),
                "metadata": {
                    "law_title": r.get("law_title"),
                    "section": r.get("section"),
                    "clause": r.get("clause"),
                    "type": "section"
                },
                "graph_data": r
            })

        # -------------------------
        # Legal Synthesizer Intelligence Layer
        # -------------------------
        from pipeline.legal_synthesizer.clause_ranker import ClauseRanker
        from pipeline.legal_synthesizer.deduplicator import Deduplicator
        from pipeline.legal_synthesizer.section_builder import SectionBuilder
        from pipeline.legal_synthesizer.synthesizer import LegalSynthesizer
        from pipeline.legal_synthesizer.validator import OutputValidator
        from pipeline.legal_synthesizer.formatter import OutputFormatter
        from pipeline.legal_synthesizer.intent_mode import LegalIntentMode

        deduper = Deduplicator()
        
        # 0. Surgical Clean
        clean_chunks = [{**c, "text": deduper.clean_raw_text(c.get("text", ""))} for c in raw_chunks]
        clean_chunks = [c for c in clean_chunks if c["text"]]

        # Extract strict intent mode
        q_lower = query.lower()
        if any(w in q_lower for w in ["what is", "define", "definition", "meaning", "meant by"]):
            intent_mode = LegalIntentMode.DEFINITION
        elif any(w in q_lower for w in ["penalty", "fine", "imprisonment", "punish", "offence"]):
            intent_mode = LegalIntentMode.PENALTY
        elif any(w in q_lower for w in ["arrest", "warrant"]):
            intent_mode = LegalIntentMode.ARREST
        else:
            intent_mode = LegalIntentMode.GENERAL

        # 1. Intent & Species Filtering
        filtered_chunks = self._filter_by_intent(clean_chunks, intent_mode)
        if intent_mode == LegalIntentMode.PENALTY:
            filtered_chunks = self._species_intersection_filter(filtered_chunks, query)
        
        # 1.5 Nucleus Fallback (V4.1): Don't hard block if filtered is empty
        if not filtered_chunks:
            logger.warning(f"[GraphLawAgent] Intent filter yielded 0. Falling back to top chunks.")
            filtered_chunks = clean_chunks[:3] 

        # 2. Expand Cross-References
        final_context = await self._expand_cross_references(filtered_chunks if filtered_chunks else clean_chunks)

        ranker = ClauseRanker(max_tokens=1500)
        builder = SectionBuilder()
        synth = LegalSynthesizer()
        validator = OutputValidator()
        formatter = OutputFormatter()

        # 3. Rank & Deduplicate (V5 Ranking Layer)
        ranked_chunks = ranker.rank_and_truncate(final_context, intent_mode, query)
        unique_chunks = deduper.deduplicate(ranked_chunks)

        # Keep only top 4 most relevant chunks for graph context
        unique_chunks.sort(key=lambda x: x.get("similarity", 0.0), reverse=True)
        final_chunks = unique_chunks[:4]

        # 4. Group & Synthesize
        grouped_context = builder.group_clauses(final_chunks)
        prompt, valid_tags = synth.generate_synthesis_prompt(query, grouped_context)
        
        fallback_text = "\n\n".join([c.get("text", "") for c in unique_chunks])

        try:
            logger.info(f"[GraphLawAgent] Firing Synthesis for query: {query[:30]}...")
            raw_generation = "".join(self.llm_manager.generate(prompt, stream=False))
            logger.debug(f"[GraphLawAgent] Raw Synthesis Output:\n{raw_generation}")
            raw_generation = deduper.postprocess_text(raw_generation)
            
            # Priority 8: Cleanup Rule/Conclusion duplication
            raw_generation = synth.cleanup_rule_conclusion(raw_generation, intent_mode)
            
            is_valid = validator.validate_anchors(raw_generation, valid_tags, intent_mode=intent_mode)
            if not is_valid:
                logger.warning("[GraphLawAgent] Hallucination Validator rejected synthesis!")
                raw_generation = "\n\n".join([c.get("text", "") for c in unique_chunks])
        except Exception as e:
            logger.error(f"[GraphLawAgent] LLM Synthesis failure: {e}")
            raw_generation = fallback_text

        used_chunks = [c.get("text", "") for c in unique_chunks]
        used_chunks.extend(valid_tags)
        graph_meta = [c.get("graph_data", {}) for c in unique_chunks]

        # 5. Deduplicate Citations
        citations = []
        unique_sources = set()
        citation_source = unique_chunks if unique_chunks else ranked_chunks

        for chunk in citation_source:
            meta = chunk.get("metadata", {})
            law_title = meta.get("law_title", "Verified Statutory Source")
            if law_title.startswith("Doc_"): law_title = "Verified Statutory Source"
            
            section = str(meta.get("section", ""))
            cite_key = (law_title, section)
            
            if cite_key not in unique_sources:
                unique_sources.add(cite_key)
                citations.append(
                    Citation(
                        document=law_title,
                        section=section,
                        clause=str(meta.get("clause", "")),
                        chunk_id=chunk.get("chunk_id", "")
                    )
                )

        if not citations:
            return CanonicalAgentResponse(
                simple_explanation="No structured legal relationships were found in the graph.",
                legal_explanation="The graph traversal yielded no valid statutory citations for this query.",
                citations=[],
                abstain=True,
                agent_name=self.name,
                audience=audience,
                confidence=0.0,
                source_chunks=[],
                graph_metadata={},
                validation_passed=False,
                errors=["EMPTY_GRAPH_CITATIONS"]
            )

        response = CanonicalAgentResponse(
            simple_explanation="This answer provides a unified legal position derived from consolidated statutory evidence.",
            legal_explanation=raw_generation,
            citations=citations,
            abstain=False,
            agent_name=self.name,
            audience=audience,
            confidence=0.0,
            source_chunks=used_chunks,
            graph_metadata={
                "relations": graph_meta,
                "path": "LAW→SECTION→CLAUSE→TEXT"
            },
            validation_passed=True,
            errors=[]
        )

        return formatter.format_output(response, query=query)
