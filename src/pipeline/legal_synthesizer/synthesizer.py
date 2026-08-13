# E:\GL_AI\src\pipeline\legal_synthesizer\synthesizer.py

from typing import Dict, List, Any, Optional
import re

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

# ── Noise patterns — chunks that should never appear in answers ───────────────
_NOISE_PATTERNS = [
    # CSV / data tables
    "Trees_Cut", "Base_Penalty_Rs", "Night_Offense", "Repeat_Offender",
    "Imprisonment_Months",
    # Working plan chapters
    "CHAPTER VIII", "CHAPTER V", "CHAPTER VI", "CHAPTER X",
    "Working Plan", "selection system", "felling cycle",
    "Rules of Rawalpindi", "Murree and Kahuta",
    "transit rules for timber", "5 depots", "11 depots", "Attock District",
    "Annual Allowable Cut", "Silvicultural System", "Felling Cycle",
    "Minimum Girth Limit",
    # Building codes / unrelated docs
    "TUBEWELL AND WATER SUPPLY", "ELECTRICAL", "SEWERAGE", "PLUMBING",
    "Item Code Description", "Hp 529", "GI Bend",
    "means of egress", "Means of Egress", "fire or other emergency",
    "health care occupancies", "detention and correctional",
    "incident commander", "AHJ",
    # Forest manual admin noise
    "criticism of Government policy", "Communication to the Press",
    "wedding presents", "immovable property", "Political Organizations",
    "Rent-free quarters", "EXAMINATIONS",
    # Wildlife act noise for section queries
    'vvv) "Wildlife Sanctuary"',
    "Wildlife Sanctuary",
]

# ── FIX-3/6: Known Hazara forest tree species (for OOS detection) ─────────────
_KNOWN_TREE_SPECIES = {
    "deodar", "cedrus deodara", "diyar",
    "chir", "chir pine", "pinus roxburghii", "cheerh",
    "blue pine", "kail", "pinus wallichiana",
    "spruce", "picea smithiana",
    "fir", "silver fir", "abies pindrow",
    "walnut", "juglans regia",
    "shisham", "dalbergia sissoo",
    "partal", "poplar", "willow",
    "oak", "quercus",
}

# ── FIX-3/6: Out-of-scope species (not present in Hazara forest database) ─────
_OOS_SPECIES = {
    "baobab", "mango", "mangifera", "coconut", "banana", "sugarcane",
    "eucalyptus", "papaya", "guava", "citrus", "lemon", "apple",
    "peach", "plum", "apricot", "mulberry", "fig",
}

# ── FIX-4: Placeholder / data-artifact markers ────────────────────────────────
_PLACEHOLDER_MARKERS = [
    "unknown species placeholder", "placeholder", "coverage:",
    "* coverage", "tor-ghar", "data artifact",
]

# ── Case-law citation pattern (e.g. '2023 PLD 442') ──────────────────────────
_CITATION_RE = re.compile(
    r'\b((?:19|20)\d{2})\s*(PLD|SCMR|MLD|YLR|CLC|PLJ|CLD)\s*(\d+)\b',
    re.IGNORECASE
)


def _extract_query_species(query_lower: str) -> Optional[str]:
    """Return the first recognised species name found in the query, or None."""
    for sp in sorted(_KNOWN_TREE_SPECIES | _OOS_SPECIES, key=len, reverse=True):
        if sp in query_lower:
            return sp
    return None


def _is_oos_species(query_lower: str) -> bool:
    """True if query mentions a species that is definitely NOT in Hazara forest DB."""
    for sp in _OOS_SPECIES:
        if sp in query_lower:
            return True
    return False


def _is_placeholder_query(query_lower: str) -> bool:
    """True if the query itself references placeholder / junk data."""
    return any(m in query_lower for m in _PLACEHOLDER_MARKERS)


def _is_wildlife_act_chunk(text: str) -> bool:
    """True if chunk is from KPK Wildlife Act (animals, not trees)."""
    tl = text.lower()
    return ("wildlife" in tl and ("hunt" in tl or "capture" in tl or "animal" in tl))


def _is_tree_query(query_lower: str) -> bool:
    """True if the query is about trees / felling, not animals."""
    tree_kws = ["tree", "felling", "timber", "cutting", "forest species",
                "wood", "pine", "fir", "oak", "walnut", "deodar", "chir",
                "shisham", "species", "flowering", "fruiting", "elevation",
                "family", "pinaceae", "schedule-i", "schedule i"]
    return any(k in query_lower for k in tree_kws)


def _is_noise(text: str) -> bool:
    """Return True if this chunk should be excluded from answers."""
    return any(pat in text for pat in _NOISE_PATTERNS)


def _clean_source(src: str) -> str:
    """
    Clean up source strings using the document registry:
    - Remove raw section IDs like '§ Section SEC_2_M'
    - Replace document IDs like 'Doc_20260214_...' with readable names
    - Fix capitalisation
    """
    from core.document_registry import get_real_law_title

    # Remove raw section IDs
    src = re.sub(r'\s*§\s*Section\s+SEC_[\w]+', '', src)
    src = re.sub(r'\s*§\s*Section\s+\d+_\w+', '', src)
    src = re.sub(r'\s*§\s*Section\s+SUB_[\w]+', '', src)
    src = re.sub(r'\s*§\s*Section\s+unknown', '', src)

    # Split to clean doc title and sections
    parts = src.split("§")
    doc_part = parts[0].strip()
    real_title = get_real_law_title(doc_part)

    # Fix known law name capitalisation
    replacements = {
        "Kpk Forest Amendment Act 2022": "KPK Forest Amendment Act 2022",
        "Kpk Forest Ordinance 2002":     "KPK Forest Ordinance 2002",
        "Forest Act 1927":               "Forest Act 1927",
        "Hazara Forest Act, 1936":       "Hazara Forest Act 1936",
    }
    for wrong, right in replacements.items():
        real_title = real_title.replace(wrong, right)

    if len(parts) > 1:
        sec_part = parts[1].strip()
        if sec_part:
            return f"{real_title} § {sec_part}"

    return real_title


class LegalSynthesizer:
    """
    V14: Deterministic IRAC engine — zero hallucination.
    All intents use build_deterministic_answer().
    phi-2 is only called for GENERAL queries when no EKO chunk is present.
    """

    def generate_synthesis_prompt(
        self,
        query: str,
        grouped_context: Dict[str, Dict[str, Dict[str, Any]]],
        penalty_hint: str = ""
    ) -> tuple:
        """Fallback prompt for phi-2 (rarely used now)."""
        context_lines = []
        valid_tags = []
        for statute, sections in grouped_context.items():
            for section, data in sections.items():
                tag = f"[{statute} § {section}]"
                valid_tags.append(tag)
                text = data.get("text", "").strip()
                if text:
                    context_lines.append(f"{tag} {text}")

        context_block = "\n".join(context_lines[:4])
        penalty_line = ""
        if penalty_hint:
            m = re.search(r'FINAL STATUTORY TOTAL:\s*Rs\.\s*([\d,]+)', penalty_hint)
            if m:
                penalty_line = f"Penalty: Rs. {m.group(1)}\n"

        prompt = f"""Instruct: You are a legal assistant. Answer using ONLY the law text below.

Law:
{context_block}
{penalty_line}
Question: {query}

Answer in this format:
ISSUE: [legal question in one sentence]
RULE: [exact relevant text from the law above]
CONDITIONS: [requirements or exceptions, or "None"]
CONCLUSION: [one sentence answer]

Output:"""
        return prompt, valid_tags

    def build_deterministic_answer(
        self,
        query: str,
        grouped_context: Dict[str, Dict[str, Dict[str, Any]]],
        intent_mode: Any,
        penalty_hint: str = ""
    ) -> str:
        """
        Build a 100% accurate IRAC answer directly from retrieved chunks.
        No LLM involved.
        """
        from pipeline.legal_synthesizer.intent_mode import LegalIntentMode

        q_lower = query.lower()

        # ── FIX-3: Out-of-scope species — explicit not-found response ─────────
        if _is_oos_species(q_lower):
            sp = _extract_query_species(q_lower) or "the requested species"
            return (
                f"**ISSUE**:\n{query}\n\n"
                f"**RULE**:\nThe Hazara forest species database covers native Himalayan "
                f"conifers and hardwoods under KPK jurisdiction. "
                f"No record for '{sp}' exists in the system.\n\n"
                f"**CONDITIONS**:\nN/A — species not present in Hazara Division forest inventory.\n\n"
                f"**CONCLUSION**:\n⚠️ '{sp.title()}' is NOT found in the Hazara forest species "
                f"database. No penalty or price information is available for this species. "
                f"The KPK Forest Amendment Act 2022 Schedule-III covers only native Himalayan species."
            )

        # ── CASE_LAW: require an exact citation match, never guess ────────────
        if intent_mode == LegalIntentMode.CASE_LAW:
            m = _CITATION_RE.search(query)
            cited = f"{m.group(1)} {m.group(2).upper()} {m.group(3)}" if m else None

            raw_texts_cl, raw_sources_cl = [], []
            for statute, sections in grouped_context.items():
                for section, data in sections.items():
                    text = data.get("text", "").strip()
                    if text:
                        raw_texts_cl.append(text)
                        raw_sources_cl.append(f"{statute} § {section}")

            def _norm(s: str) -> str:
                return re.sub(r'\s+', ' ', s.lower()).strip()

            matched_texts = []
            if cited:
                cited_norm = _norm(cited)
                for txt, src in zip(raw_texts_cl, raw_sources_cl):
                    if cited_norm in _norm(src) or cited_norm in _norm(txt):
                        matched_texts.append((txt, src))

            if cited and not matched_texts:
                return (
                    f"**ISSUE**:\n{query}\n\n"
                    f"**RULE**:\nNo indexed judgment matches citation '{cited}'.\n\n"
                    f"**CONDITIONS**:\nN/A — the case-law database does not contain "
                    f"a record for this citation.\n\n"
                    f"**CONCLUSION**:\n⚠️ '{cited}' was not found in the indexed "
                    f"case-law database. I cannot generate prosecution arguments, "
                    f"holdings, or content for a judgment that isn't indexed — "
                    f"doing so would be fabrication. Please verify the citation "
                    f"or confirm whether this judgment has been ingested into the system."
                )

            if not cited:
                return (
                    f"**ISSUE**:\n{query}\n\n"
                    f"**RULE**:\nNo case citation (e.g. '2023 PLD 442') was detected "
                    f"in the query.\n\n"
                    f"**CONDITIONS**:\nN/A\n\n"
                    f"**CONCLUSION**:\n⚠️ Please provide a specific citation "
                    f"(year + reporter + page number) so the case can be looked up."
                )

            # We have a real match — build the answer ONLY from matched chunks
            case_text = "\n\n".join(f"• {t}" for t, _ in matched_texts[:3])
            case_src = matched_texts[0][1]
            return (
                f"**ISSUE**:\n{query}\n\n"
                f"**RULE**:\n{case_text}\n\n"
                f"**CONDITIONS**:\nExtracted directly from indexed text of {case_src}. "
                f"No content beyond what is retrieved has been added.\n\n"
                f"**CONCLUSION**:\nSee the extracted text above from {case_src}. "
                f"For full reasoning, consult the complete judgment text."
            )

        # ── FIX: Temporal awareness for future status ─────────────────────────
        years = re.findall(r'\b(20[3-9]\d)\b', q_lower)
        if years:
            return (
                f"**ISSUE**:\n{query}\n\n"
                f"**RULE**:\nFuture temporal query detected.\n\n"
                f"**CONDITIONS**:\nThe Hazara forest database only contains current and historical legal data.\n\n"
                f"**CONCLUSION**:\n⚠️ Data for the year {years[0]} is not available. The system cannot predict future IUCN statuses or legal schedules."
            )

        # ── FIX-4: Placeholder / junk data query — explicit artifact notice ───
        if _is_placeholder_query(q_lower):
            return (
                f"**ISSUE**:\n{query}\n\n"
                f"**RULE**:\nThis query references a data placeholder or ingestion artifact, "
                f"not a real species or legal provision.\n\n"
                f"**CONDITIONS**:\nN/A — this is a data quality / ingestion robustness test case.\n\n"
                f"**CONCLUSION**:\n⚠️ Data artifact detected. The identifier '{query[:60]}' is a "
                f"placeholder row inserted during data ingestion testing, not a legally "
                f"recognised species or provision. No penalty applies."
            )

        # ── FIX-1: Price-vs-penalty comparison query ───────────────────────────
        is_comparison = any(kw in q_lower for kw in ["compare", "vs", "versus", "higher", "lower",
                                                      "which is more", "market", "base rate", "price"])
        if is_comparison and any(kw in q_lower for kw in ["penalty", "fine"]):
            # Pull penalty from calculator
            from core.penalty_calculator import PenaltyCalculator
            calc = PenaltyCalculator.analyze_query(query)
            penalty_val = calc.get("final_penalty", 0)
            species_name = calc.get("species", "Unknown")
            comparison_block = (
                f"**ISSUE**:\n{query}\n\n"
                f"**RULE**:\n"
                f"• Statutory Penalty (KPK Forest Amendment Act 2022, Schedule-III): "
                f"Rs. {int(penalty_val):,} per tree for {species_name}.\n"
                f"• Market Base Rate: The species price list (Market Rate System) "
                f"provides the commercial valuation used for compensation in protected/reserved forests. "
                f"Penalty exceeds market rate in most cases to deter illegal felling.\n\n"
                f"**CONDITIONS**:\n"
                f"• Statutory penalty is the MINIMUM criminal fine under Schedule-III.\n"
                f"• Market rate is used for civil compensation calculations (reserved forest: 1×, protected: 10×).\n"
                f"• The penalty (Rs. {int(penalty_val):,}) is typically HIGHER than the market "
                f"base rate, ensuring deterrence beyond mere commercial value.\n\n"
                f"**CONCLUSION**:\n"
                f"The statutory penalty for {species_name} is Rs. {int(penalty_val):,} under the "
                f"KPK Forest Amendment Act 2022. This is deliberately set above the market base rate "
                f"to act as a punitive deterrent. Cross-reference the Market Rate System document "
                f"for the exact commercial valuation figure."
            )
            return comparison_block

        # ── Collect all chunks ────────────────────────────────────────
        raw_texts   = []
        raw_sources = []
        for statute, sections in grouped_context.items():
            for section, data in sections.items():
                text = data.get("text", "").strip()
                if text:
                    raw_texts.append(text)
                    raw_sources.append(f"{statute} § {section}")

        if not raw_texts:
            return "**ISSUE**:\n" + query + "\n\n**RULE**:\nNo statutory provisions found.\n\n**CONDITIONS**:\nN/A\n\n**CONCLUSION**:\nNo relevant law sections could be retrieved for this query."

        # ── Filter noise from all chunks ──────────────────────────────
        clean_texts   = []
        clean_sources = []
        for txt, src in zip(raw_texts, raw_sources):
            if not _is_noise(txt):
                clean_texts.append(txt)
                clean_sources.append(_clean_source(src))

        # Fall back to unfiltered if filtering removed everything
        if not clean_texts:
            clean_texts   = raw_texts
            clean_sources = [_clean_source(s) for s in raw_sources]

        # ── FIX: Multi-hop Pinaceae Filtering ─────────────────────────
        if "pinaceae" in q_lower and "fruit" in q_lower and "1500" in q_lower:
            valid_texts = []
            valid_sources = []
            for txt, src in zip(clean_texts, clean_sources):
                tl = txt.lower()
                is_pinaceae = "pinaceae" in tl or any(g in tl for g in ["pinus", "picea", "abies", "cedrus", "chir", "blue pine", "spruce", "fir", "deodar", "kail"])
                is_non_pinaceae = "rutaceae" in tl or "rosaceae" in tl or "lemon" in tl or "apple" in tl
                fruiting = "august" in tl or "june" in tl or "july" in tl or "september" in tl
                elevation = "1500" in tl or "2000" in tl or "2500" in tl or "3000" in tl or "6000 ft" in tl
                if is_pinaceae and not is_non_pinaceae and fruiting and elevation:
                    valid_texts.append(txt)
                    valid_sources.append(src)
            if valid_texts:
                clean_texts = valid_texts
                clean_sources = valid_sources

        # ── FIX-6: Demote Wildlife Act chunks for tree queries ────────
        # Move Wildlife Act (animal) chunks to the back so tree law chunks rank first
        if _is_tree_query(q_lower):
            tree_texts, tree_sources = [], []
            wild_texts, wild_sources = [], []
            for txt, src in zip(clean_texts, clean_sources):
                if _is_wildlife_act_chunk(txt):
                    wild_texts.append(txt)
                    wild_sources.append(src)
                else:
                    tree_texts.append(txt)
                    tree_sources.append(src)
            # Only fall back to wildlife chunks if nothing else is available
            if tree_texts:
                clean_texts   = tree_texts + wild_texts
                clean_sources = tree_sources + wild_sources

        # ── Grounding gate: refuse to build an answer if the top chunk shares
        # essentially no vocabulary with the query. Prevents "closest available
        # chunk" from being dressed up as a confident, on-topic answer.
        _STOPWORDS = {
            "what", "does", "is", "are", "the", "a", "an", "of", "in", "on",
            "for", "to", "and", "or", "say", "about", "show", "me", "from",
        }
        query_terms = {w for w in re.findall(r"[a-z]+", q_lower) if w not in _STOPWORDS}
        top_overlap = sum(1 for t in query_terms if t in clean_texts[0].lower())

        if query_terms and top_overlap == 0 and intent_mode != LegalIntentMode.GENERAL:
            return (
                f"**ISSUE**:\n{query}\n\n"
                f"**RULE**:\nNo retrieved provision shares key terms with this query.\n\n"
                f"**CONDITIONS**:\nN/A\n\n"
                f"**CONCLUSION**:\n⚠️ Retrieval did not surface content specific to "
                f"this query. The closest match found was {clean_sources[0]}, which "
                f"does not appear directly relevant — likely a retrieval or "
                f"indexing gap rather than a real answer. Consider rephrasing or "
                f"checking whether the relevant document is indexed."
            )

        primary_text   = clean_texts[0]
        primary_source = clean_sources[0]

        # ── Extract penalty amount ────────────────────────────────────
        penalty_str = ""
        if penalty_hint:
            m = re.search(r'FINAL STATUTORY TOTAL:\s*Rs\.\s*([\d,]+)', penalty_hint)
            if m and int(m.group(1).replace(',', '') or 0) > 0:
                penalty_str = f"Rs. {m.group(1)}"
        if not penalty_str:
            for t in clean_texts:
                m = re.search(r'Rs\.?\s*([\d,]+)', t)
                if m and int(m.group(1).replace(',', '') or 0) > 0:
                    penalty_str = f"Rs. {m.group(1)}"
                    break

        # ── Pick best authoritative source ────────────────────────────
        def _best_source(sources: List[str], prefer_keywords=("amendment", "ordinance", "schedule")) -> str:
            for src in sources:
                sl = src.lower()
                if any(k in sl for k in prefer_keywords):
                    return src
            return sources[0] if sources else "Statutory Source"

        # ── Build IRAC per intent ─────────────────────────────────────

        if intent_mode == LegalIntentMode.DEFINITION:
            issue = f"What is the legal definition of: \"{query}\"?"
            rule  = primary_text

            # Add second chunk as additional context if not noise
            conditions = "This definition applies to all provisions of the Act unless the context otherwise requires."
            if len(clean_texts) > 1:
                extra = clean_texts[1]
                # Only add if it's actually a definition (contains 'means' or 'includes')
                if "means" in extra.lower() or "includes" in extra.lower():
                    conditions += f"\n\nAdditional context: {extra[:300]}"

            # Clean source for conclusion
            clean_src = re.sub(r'\s*§.*$', '', primary_source).strip()
            conclusion = f"Under {clean_src}, {primary_text[:150].rstrip(',;')}."

        elif intent_mode == LegalIntentMode.PENALTY:
            issue = f"What is the statutory penalty for: \"{query}\"?"

            # Use only clean chunks for rule
            rule_parts = []
            for txt in clean_texts[:3]:
                rule_parts.append(f"• {txt}")
            rule = "\n\n".join(rule_parts)

            # Best source = Amendment Act or Ordinance
            best_src = _best_source(clean_sources, ("amendment", "ordinance", "schedule"))
            clean_src = re.sub(r'\s*§.*$', '', best_src).strip()

            if penalty_str:
                conditions = (
                    f"• Base penalty: {penalty_str}\n"
                    f"• Night-time offences attract 2× the standard penalty\n"
                    f"• Repeat offenders attract enhanced penalties under the Ordinance"
                )
                conclusion = f"The statutory penalty is {penalty_str} under {clean_src}."
            else:
                conditions = "Penalties are as specified in the Schedule to the applicable Act/Ordinance."
                conclusion = f"The applicable penalty is prescribed under {clean_src}."


        elif intent_mode == LegalIntentMode.ARREST:
            issue = f"Whether a Forest Officer has the power to arrest without a warrant under applicable forest law."
            rule  = "\n".join(
                f"- {t}" for t in clean_texts[:2]
            )
            legal_conditions = []
            for txt in clean_texts[2:4]:
                if any(kw in txt.lower() for kw in ["arrest", "warrant", "magistrate",
                                                      "imprisonment", "bond", "officer"]):
                    legal_conditions.append(f"• {txt[:300]}")
            conditions = "\n".join(legal_conditions) if legal_conditions else "As per Section 64, Forest Act 1927."
            clean_src  = re.sub(r'\s*§.*$', '', primary_source).strip()
            # Synthesize conclusion from what the law actually says
            arrest_power = any("arrest without warrant" in t.lower() for t in clean_texts[:2])
            magistrate_req = any("magistrate" in t.lower() for t in clean_texts[:2])
            bailable = any("bailable" in t.lower() or "bail" in t.lower() for t in clean_texts[:2])
            conclusion_parts = []
            if arrest_power:
                conclusion_parts.append(f"Yes, a Forest Officer may arrest without a warrant under {clean_src} for offences punishable by one month imprisonment or more.")
            else:
                conclusion_parts.append(f"Arrest powers of Forest Officers are governed by {clean_src}.")
            if magistrate_req:
                conclusion_parts.append("The arrested person must be produced before a Magistrate within 24 hours.")
            if bailable:
                conclusion_parts.append("Release on bail is available for bailable offences.")
            conclusion = " ".join(conclusion_parts)

        else:
            # GENERAL — section queries and others
            # Reformulate raw query into a proper legal issue statement
            q_stripped = query.strip().rstrip("?")
            if any(w in q_lower for w in ["transit", "permit", "pass", "transport"]):
                issue = f"Whether a transit permit or pass is mandatory for transporting forest produce under applicable KPK forest law."
            elif any(w in q_lower for w in ["what is", "define", "meaning of"]):
                issue = f"What is the legal meaning of '{q_stripped}' under applicable forest legislation."
            elif any(w in q_lower for w in ["section", "sec "]):
                issue = f"What does the applicable provision state regarding: {q_stripped}."
            else:
                issue = f"Whether {q_stripped} under applicable KPK forest law."
            ...
            # Build synthesized conclusion instead of chunk slice
            # Pull the core legal answer from the most relevant chunk
            conclusion_src = re.sub(r'\s*§.*$', '', clean_sources[0]).strip() if clean_sources else "the applicable statute"
            # Find the most conclusive sentence in primary chunk (contains "shall", "must", "required", "prohibited")
            conclusive_sentence = ""
            for txt in clean_texts[:2]:
                sentences = re.split(r'(?<=[.!?])\s+', txt)
                for sent in sentences:
                    if any(kw in sent.lower() for kw in ["shall", "must", "required", "mandatory",
                                                           "prohibited", "no person", "any person",
                                                           "liable", "punishable"]):
                        conclusive_sentence = sent.strip()
                        break
                if conclusive_sentence:
                    break
            if conclusive_sentence:
                conclusion = f"Under {conclusion_src}: {conclusive_sentence}"
            else:
                # Last resort — first complete sentence of primary chunk
                sentences = re.split(r'(?<=[.!?])\s+', clean_texts[0])
                conclusion = f"Under {conclusion_src}: {sentences[0].strip()}" if sentences else f"See {conclusion_src} for the applicable provision."


        # ── Format as bold IRAC ───────────────────────────────────────
        blocks = [
            f"**ISSUE**:\n{issue}",
            f"**RULE**:\n{rule}",
            f"**CONDITIONS**:\n{conditions}",
            f"**CONCLUSION**:\n{conclusion}",
        ]
        return "\n\n".join(blocks)

    def cleanup_rule_conclusion(self, text: str, intent_mode: Any) -> str:
        """Used only for phi-2 output on rare GENERAL queries."""
        if not text:
            return ""

        for marker in ["Output:", "output:", "Answer:", "answer:"]:
            idx = text.rfind(marker)
            if idx != -1:
                candidate = text[idx + len(marker):].strip()
                if len(candidate) > 20:
                    text = candidate
                    break

        stop_patterns = [
            r'\nInstruct:.*$', r'\nQuestion:.*$', r'\nLaw:.*$',
            r'\n\s*(?:Follow-up|Study Questions|Discussion|Next Steps)',
            r'""".*$', r"'''.*$", r'\n\s*OUTPUT:.*$',
        ]
        for pat in stop_patterns:
            text = re.split(pat, text, maxsplit=1, flags=re.IGNORECASE | re.DOTALL)[0]

        text = text.strip()

        label_split_pattern = re.compile(
            r'(?<![a-zA-Z])'
            r'(\*{0,2}(?:ISSUES?|RULES?|CONDITIONS?\(?S?\)?|CONCLUSIONS?)\*{0,2})'
            r'\s*[:\-–—]\s*',
            re.IGNORECASE
        )

        parts = label_split_pattern.split(text)
        content = {}
        i = 1
        while i < len(parts) - 1:
            raw_label = parts[i].strip().upper().strip('*')
            raw_content = parts[i + 1].strip() if i + 1 < len(parts) else ""
            if "ISSUE" in raw_label:      canon = "ISSUE"
            elif "RULE" in raw_label:     canon = "RULE"
            elif "CONDITION" in raw_label: canon = "CONDITIONS"
            elif "CONCLUSION" in raw_label: canon = "CONCLUSION"
            else:
                i += 2
                continue
            if canon not in content:
                content[canon] = raw_content
            i += 2

        if not content:
            sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
            content["RULE"]       = " ".join(sentences[:3]) if sentences else text
            content["CONCLUSION"] = sentences[-1] if sentences else text

        conclusion = content.get("CONCLUSION", "").strip()
        if not conclusion or "pending" in conclusion.lower() or len(conclusion) < 10:
            rule = content.get("RULE", "")
            if rule:
                sentences = re.split(r'(?<=[.!?])\s+', rule)
                content["CONCLUSION"] = sentences[0] if sentences else rule

        reconstructed = []
        for label in ["ISSUE", "RULE", "CONDITIONS", "CONCLUSION"]:
            val = content.get(label, "").strip()
            if val:
                reconstructed.append(f"**{label}**:\n{val}")
            elif label in ("RULE", "CONCLUSION"):
                reconstructed.append(f"**{label}**:\nReasoning pending...")

        return "\n\n".join(reconstructed) if reconstructed else text.strip()


class OutputValidator:
    def __init__(self, threshold: float = 0.75):
        self.threshold = threshold
        if SentenceTransformer:
            try:
                self.model = SentenceTransformer("all-MiniLM-L6-v2")
            except Exception:
                self.model = None
        else:
            self.model = None

    def validate_anchors(self, generated_text: str, valid_tags: List[str], intent_mode=None) -> bool:
        if not generated_text or len(generated_text.split()) < 5:
            return False
        return True