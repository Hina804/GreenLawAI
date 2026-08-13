from transformers.models.chameleon import image_processing_chameleon_fast
import re
from typing import List, Dict, Any, Optional
from loguru import logger

from .base_agent import BaseAgent
from core.schemas import CanonicalAgentResponse, Citation, AudienceType
from utils.safe_runner import safe_execute


class LawAgent(BaseAgent):
    """
    LawAgent — STRICT PRODUCER

    Role:
    - Extract grounded legal answers from retrieved_chunks
    - Build structured CanonicalAgentResponse
    - NO generation
    - NO prompting
    - NO validation
    - NO formatting
    - NO fusion
    - NO confidence scoring
    - NO hallucination logic
    - NO grounding gate
    """

    def __init__(self, config: Dict[str, Any], component_id: str = "legal", llm_manager=None):
        super().__init__(
            name="LawAgent",
            component_id=component_id,
            tools=[],   # retrieval handled by coordinator
            config=config
        )
        self.llm_manager = llm_manager

    async def run(
        self,
        query: str,
        retrieved_chunks: list,
        audience: AudienceType,
        context: Dict[str, Any] = None
    ) -> CanonicalAgentResponse:

        # -------------------------
        # Risk / Prediction Intent Detection (Audit Fix: Allow penalties)
        # -------------------------
        if ('risk' in query.lower() or 'forecast' in query.lower() or 'predict' in query.lower()) and \
           not any(kw in query.lower() for kw in ['penalty', 'fine', 'law', 'punish', 'section', 'ordinance', 'legal', 'provision']):
            return CanonicalAgentResponse(
                simple_explanation="For legal penalties related to fires, please ask specifically about \"penalty\" or \"fine\".",
                legal_explanation="Prediction/Risk assessment routing active. Query contains predictive keywords without legal grounding (penalty, fine, law). Redirecting to Monitoring/Predictions layer.",
                citations=[Citation(document="System Routing", section="Predictions", clause="", chunk_id="")],
                abstain=False,
                agent_name=self.name,
                audience=audience,
                confidence=0.9,
                source_chunks=[],
                graph_metadata={"redirect_to": "predictions"},
                validation_passed=True,
                errors=[]
            )

        # -------------------------
        # Structural safety
        # -------------------------
        if not retrieved_chunks:
            return CanonicalAgentResponse(
                simple_explanation="No legal text found in the provided documents.",
                legal_explanation="No statutory provisions were retrieved for this query.",
                citations=[],
                abstain=True,
                agent_name=self.name,
                audience=audience,
                confidence=0.0,
                source_chunks=[],
                graph_metadata={},
                validation_passed=False,
                errors=["NO_RETRIEVAL_DATA"]
            )

        q_lower = query.lower()
        named_doc_match = re.search(r'\b(forest manual|working plan|field manual)[\s\-]*(vol[\.\s]*[ivx0-9]+)?\b', q_lower)
        if named_doc_match:
            doc_titles_retrieved = {c.get("metadata", {}).get("law_title", "") for c in unique_chunks}
            if not any(named_doc_match.group(1).split()[0] in t.lower() for t in doc_titles_retrieved):
                return CanonicalAgentResponse(
                    simple_explanation=f"'{named_doc_match.group(0).title()}' does not appear to be indexed in this system.",
                    legal_explanation=f"No chunks were retrieved from a document matching '{named_doc_match.group(0)}'. The retrieved content is from other statutes and may not reflect what that specific manual states.",
                    citations=[], abstain=True, agent_name=self.name, audience=audience,
                    confidence=0.0, source_chunks=[], graph_metadata={},
                    validation_passed=False, errors=["NAMED_DOCUMENT_NOT_INDEXED"]
                )

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



        section_ref = re.search(r'\b(?:section|sec\.?)\s*\d+', q_lower)

        # Case citation pattern: "2023 PLD 442", "2022 SCMR 708", etc.
        citation_ref = re.search(
            r'\b(19|20)\d{2}\s*(PLD|SCMR|MLD|YLR|CLC|PLJ|CLD)\s*\d+\b',
            query, re.IGNORECASE
        )
        case_law_kws = ["prosecution", "arguments", "argument", "judgment",
                        "judgement", "held", "petitioner", "respondent",
                        "vs ", " v ", "v. ", "appellant", "verdict", "ruling in"]

        # NEW: "what does <document/act/manual> say about <topic>" is a
        # document-lookup question, NOT a definition request, even though it
        # contains "what does". Must be checked before the DEFINITION branch.
        doc_reference_ref = re.search(
            r'what\s+does.*(manual|act|ordinance|rule|schedule|section|"'
            r'|circular|notification|policy|working plan)\s*.*\bsay\b',
            q_lower
        )

        if citation_ref or any(w in q_lower for w in case_law_kws):
            intent_mode = LegalIntentMode.CASE_LAW
        elif any(w in q_lower for w in ["penalty", "fine", "imprisonment", "punish",
                                        "offence", "cutting", "cut", "felling", "fell",
                                        "illegal logging", "violation"]):
            intent_mode = LegalIntentMode.PENALTY
        elif any(w in q_lower for w in ["arrest", "warrant"]):
            intent_mode = LegalIntentMode.ARREST
        elif section_ref:
            intent_mode = LegalIntentMode.GENERAL
        elif doc_reference_ref:
            intent_mode = LegalIntentMode.GENERAL
        elif any(w in q_lower for w in ["define", "definition", "meaning", "meant by",
                                          "what is meant"]):
            intent_mode = LegalIntentMode.DEFINITION
        elif "what does" in q_lower and ("mean" in q_lower or "meant" in q_lower):
            intent_mode = LegalIntentMode.DEFINITION
        elif any(w in q_lower for w in ["what is", "what are"]) and not section_ref:
            intent_mode = LegalIntentMode.DEFINITION
        else:
            intent_mode = LegalIntentMode.GENERAL

        # 1. Rank, Context Budget, & Filter Noise
        ranked_chunks = ranker.rank_and_truncate(retrieved_chunks, intent_mode, query)
        
        # 2. Deduplicate near-identical PDFs points
        unique_chunks = deduper.deduplicate(ranked_chunks)

        # 3. Group by Hierarchy and resolve Precedence
        grouped_context = builder.group_clauses(unique_chunks)

        # 🎯 PHASE 2.6: PENALTY HINTING (Audit Alignment)
        from core.penalty_calculator import PenaltyCalculator
        penalty_result = safe_execute(
            PenaltyCalculator.analyze_query, 
            default_return={'species': 'Unknown', 'base_penalty': 0, 'multiplier': 1.0, 'rules_applied': [], 'final_penalty': 0},
            query=query
        )
        
        penalty_hint = ""
        # Only inject a NUMERIC penalty hint when the calculator actually
        # resolved a species and a non-zero fine. A PENALTY-intent query with
        # final_penalty == 0 means "no match" — that must NOT be presented
        # as a verified numeric answer.
        if penalty_result['species'] != 'Unknown' and penalty_result['final_penalty'] > 0:
            penalty_hint = (
                f"\n**PENALTY GROUNDING HINT (STRICT STATUTORY DATA)**:\n"
                f"- Species Detected: {penalty_result['species']}\n"
                f"- BASE Fine: Rs. {penalty_result['base_penalty']:,}\n"
                f"- Multiplier: {penalty_result['multiplier']}x ({', '.join(penalty_result['rules_applied']) if penalty_result['rules_applied'] else 'Standard'})\n"
                f"- FINAL STATUTORY TOTAL: Rs. {penalty_result['final_penalty']:,}\n"
                f"**MANDATORY**: Use ONLY the numeric value Rs. {penalty_result['final_penalty']:,} in your CONCLUSION. Do NOT use Rs. 100,000 (outdated).\n"
            )
        elif intent_mode == LegalIntentMode.PENALTY:
            # PENALTY intent but calculator found no species/amount — tell the
            # synthesizer explicitly NOT to fabricate a number.
            penalty_hint = (
                "\n**PENALTY GROUNDING HINT**: No species or offence could be "
                "matched to a specific Schedule-III amount for this query. "
                "**MANDATORY**: Do NOT state any numeric penalty (including "
                "Rs. 0). State plainly that the specific amount could not be "
                "determined from indexed data.\n"
            )

        # 4. Deterministic Tags & Synthesize via LLM
        prompt, valid_tags = synth.generate_synthesis_prompt(query, grouped_context, penalty_hint=penalty_hint)

        fallback_text = "\n\n".join([c.get("text", "") for c in unique_chunks])

        # ── Deterministic path: skip LLM for DEFINITION and PENALTY ──
        if intent_mode in (LegalIntentMode.DEFINITION, LegalIntentMode.PENALTY,
                        LegalIntentMode.ARREST, LegalIntentMode.GENERAL,
                        LegalIntentMode.CASE_LAW):
            raw_generation = synth.build_deterministic_answer(
                query, grouped_context, intent_mode, penalty_hint=penalty_hint
            )
            valid_tags = []            
        else:
            try:
                raw_generation = "".join(self.llm_manager.generate(prompt, stream=False))                # 5. Sentence-Level Validation
                is_valid = validator.validate_anchors(raw_generation, valid_tags)
                if not is_valid:
                    logger.warning("[LawAgent] Hallucination Validator rejected synthesis! Missing sentence anchors. Degrading to raw extraction.")
                    raw_generation = fallback_text
                else:
                    # V7: Apply IRAC block cleanup and formatting
                    raw_generation = synth.cleanup_rule_conclusion(raw_generation, intent_mode)
            except Exception as e:
                logger.error(f"[LawAgent] LLM Synthesis failure: {e}")
                # Improved UI fallback: Structured Evidence Report
                sections = []
                sections.append("### 🏛️ REGULATORY EVIDENCE (REASONING OFFLINE)")
                sections.append("The high-precision reasoning engine is currently unreachable. The system has extracted the following primary law sections matching your query:")
                sections.append("\n---\n")
                
                for i, chunk in enumerate(unique_chunks):
                    meta = chunk.get("metadata", {})
                    title = meta.get("law_title") or meta.get("source") or "Forest Regulation"
                    sec = f" | Section {meta.get('section')}" if meta.get('section') else ""
                    sections.append(f"**Source {i+1}: {title}{sec}**")
                    sections.append(f"> {chunk.get('text', '').strip()}")
                    sections.append("")
                
                if penalty_hint:
                    sections.append("\n---\n")
                    sections.append(f"**[!IMPORTANT] Penalty Accuracy Hint:** {penalty_hint}")
                
                raw_generation = "\n".join(sections)

        used_chunks = [c.get("text", "") for c in unique_chunks]
        used_chunks.extend(valid_tags) # Whitelist deterministic tags for HallucinationGuard

        citations = []
        for chunk in unique_chunks:
            meta = chunk.get("metadata", {})

            # ============================================================
            # FIX: Use the actual law_title from metadata first.
            # Only fall back to heuristic mapping if truly unknown.
            # ============================================================
            doc_name = (
                meta.get("law_title") or
                meta.get("document_id") or
                meta.get("source") or
                ""
            )

            # Strip file paths down to basename
            if '/' in doc_name or '\\' in doc_name:
                import os
                doc_name = os.path.basename(doc_name)

            doc_name_lower = doc_name.lower()

            # Only apply heuristic mapping for truly generic/unknown names
            generic_names = {"", "unknown", "none", "forest regulation", "legal document", "n/a"}
            if doc_name_lower.strip() in generic_names:
                # Heuristic fallback only when name is genuinely missing
                chunk_text = chunk.get("text", "").lower()
                if "amendment act 2022" in chunk_text or "schedule-iii" in chunk_text:
                    doc_name = "KPK Forest Amendment Act 2022"
                elif "ordinance 2002" in chunk_text or "forest ordinance" in chunk_text:
                    doc_name = "KPK Forest Ordinance 2002"
                elif "forest act" in chunk_text and "1927" in chunk_text:
                    doc_name = "The Forest Act, 1927"
                else:
                    doc_name = "Forest Regulation"
            else:
                # ── Clean up known specific names ──────────────────────
                if "amendment act 2022" in doc_name_lower or "2022 amendment" in doc_name_lower:
                    doc_name = "KPK Forest Amendment Act 2022"
                elif "kpk forest ordinance" in doc_name_lower or "ordinance 2002" in doc_name_lower:
                    doc_name = "KPK Forest Ordinance 2002"
                elif "hazara forest act" in doc_name_lower:
                    doc_name = doc_name  # Keep exact name — do NOT remap to 1927 Act
                elif "forest act, 1927" in doc_name_lower or "forest act 1927" in doc_name_lower:
                    doc_name = "The Forest Act, 1927"
                else:
                    doc_name = doc_name.replace("_", " ").title()

            # ============================================================
            # FIXED SECTION MAPPING
            # ============================================================
            sec = meta.get("section", "")
            if not sec or any(kw in str(sec).lower() for kw in ["unknown", "none", "null", "placeholder", "summary"]):
                if "schedule" in str(meta.get("law_title", "")).lower() or "schedule" in str(meta.get("section_id", "")).lower():
                    sec = meta.get("section_id", "").replace("_", " ").title()
                else:
                    sec = ""
            elif re.match(r'^(SEC|SUB|PAR)_', str(sec)):
                sec = str(sec).replace('SEC_', '').replace('SUB_', '').replace('PAR_', '')

            citations.append(
                Citation(
                    document=doc_name,
                    section=str(sec) if sec else "",
                    clause=str(meta.get("clause", "")),
                    chunk_id=chunk.get("chunk_id", str(hash(chunk.get("text", ""))))
                )
            )

        if not citations:
            return CanonicalAgentResponse(
                simple_explanation="No specific legal sections matched the synthesized results.",
                legal_explanation="The legal synthesis could not be grounded in specific statutory citations.",
                citations=[],
                abstain=True,
                agent_name=self.name,
                audience=audience,
                confidence=0.0,
                source_chunks=[],
                graph_metadata={},
                validation_passed=False,
                errors=["EMPTY_CITATIONS"]
            )

        # -------------------------
        # FIX: Calculate confidence from retrieved chunks' scores
        # -------------------------
        grounding_score = 0.0
        if unique_chunks:
            scores = []
            for c in unique_chunks:
                s = c.get("final_score") or c.get("vector_score") or c.get("score") or 0.0
                scores.append(float(s))
            if scores:
                grounding_score = min(1.0, sum(scores) / len(scores))

        # -------------------------
        # Structured output
        # -------------------------
        response = CanonicalAgentResponse(
            simple_explanation="This answer is derived from structured statutory reasoning, synthesizing applicable legal clauses with strict citation tracking.",
            legal_explanation=raw_generation,
            citations=citations,
            abstain=False,
            agent_name=self.name,
            audience=audience,
            confidence=grounding_score,  # FIX: use actual grounding score
            source_chunks=used_chunks,
            graph_metadata={},
            validation_passed=True,
            errors=[]
        )

        # 🎯 PHASE 2.6: PENALTY GUIDANCE (Audit Alignment)
        try:
            from core.penalty_calculator import PenaltyCalculator
            penalty_result = PenaltyCalculator.analyze_query(query)
            
            if penalty_result and penalty_result.get('multiplier', 1.0) > 1.0:
                raw_generation += f"\n\n> [!TIP]\n> **Statutory Multiplier Calculation**: {PenaltyCalculator.format_for_ui(penalty_result)}"
                
                final_val = penalty_result.get('final_penalty', 0)
                base_val = penalty_result.get('base_penalty', 0)
                
                final_val_str = f"{int(final_val):,}"
                final_val_str2 = f"{int(final_val)}" 
                base_val_str = f"{int(base_val):,}"
                
                pattern = re.compile(r'(?i)(base[^0-9]{0,30}?)(' + re.escape(final_val_str) + r'|' + re.escape(final_val_str2) + r')(?:\.0+)?')
                raw_generation = pattern.sub(r'\g<1>' + base_val_str, raw_generation)
                
                response.legal_explanation = raw_generation
        except Exception as e:
            logger.error(f"[LawAgent] Penalty breakdown error: {e}")

        return formatter.format_output(response, query=query)

    def extract_conditions(self, query: str) -> List[Dict[str, Any]]:
        """
        PRODUCTION-GRADE: Detect special conditions that modify penalties (Audit Plan)
        """
        conditions = []
        q_lower = query.lower()
        
        # 1. Night detection
        if any(word in q_lower for word in ['night', 'after sunset', 'before sunrise', 'darkness']):
            conditions.append({
                'condition': 'offense committed at night',
                'multiplier': 2.0,
                'legal_basis': 'Section 73 - Enhanced penalty for nighttime offenses'
            })
        
        # 2. Repeat offender detection (Audit Requirement)
        if any(word in q_lower for word in ['previous', 'convicted', 'repeat', 'second time']):
            conditions.append({
                'condition': 'repeat offender',
                'multiplier': 2.0,
                'legal_basis': 'Section 74 - Double penalty for prior convictions'
            })
            
        return conditions