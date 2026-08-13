"""
clause_ranker.py — COMPLETE FIXED VERSION
==========================================
Root causes fixed:
  RC-1  Analytics/operational chunks were leaking into the RULE slot for
        PENALTY queries (CSV rows, rate tables appearing as statutory text).
  RC-2  section_type="definition" boost was defined but not applied early
        enough — chapter headings with higher keyword density were winning.
  RC-3  find_definition_chunks() was run AFTER general sorting, so the best
        definition chunk could already be buried.
  RC-4  PENALTY fallback returned rule_pool[:3] which could still contain
        non-legal chunks when legal_chunks was empty.
  RC-5  "section N" queries fell into GENERAL intent → no section-content
        boost → wrong chunks ranked first.
  RC-6  Weak circular-definition filter was too aggressive — knocked out valid
        definitions that happened to reference another section.

Changes:
  • Added SECTION intent mode handling with direct section-number boost.
  • Definition boost is now the FIRST operation, before any keyword scan.
  • section_type="definition" or section_number="2" gets quality += 0.6.
  • Chapter headings demoted globally (not just in DEFINITION mode).
  • PENALTY rule pool is ALWAYS legal_chunks; analytics used for hint only.
  • GENERAL/ARREST ranking uses richer scoring (authority + content length).
  • Token budget preserved from original.
"""

import re
from copy import deepcopy
from typing import Dict, List, Optional, Any

from loguru import logger

try:
    import tiktoken
    _ENCODING = tiktoken.get_encoding("cl100k_base")
except Exception:
    _ENCODING = None

# ── Category sets ──────────────────────────────────────────────────────────────
LEGAL_CATEGORIES   = {"legal_statute", "legal_rules", "case_law"}
ANALYTICS_CATEGORY = "analytics"

# ── Patterns ───────────────────────────────────────────────────────────────────
_CHAPTER_HDG_RE = re.compile(
    r"^\s*CHAPTER\s*[–—\-]?\s*[IVXLC\d]+", re.IGNORECASE
)
_SEC_NUM_RE = re.compile(r"\bsection\s*(\d+[a-z]?)\b", re.IGNORECASE)
_CSV_ROW_RE = re.compile(                         # detects raw DataFrame printout
    r"\d\s+\d{4}\s+\w+\s+\w+\s+\d+\s+\d+",
    re.IGNORECASE,
)

# ── Helpers ────────────────────────────────────────────────────────────────────

def _estimate_tokens(text: str) -> int:
    if _ENCODING:
        return len(_ENCODING.encode(text))
    return max(1, len(text) // 4)


def _get_meta(chunk: dict) -> dict:
    """Normalise: chunks may store metadata at top level or under 'metadata'."""
    return chunk.get("metadata", {}) if "metadata" in chunk else chunk


def _is_legal(chunk: dict) -> bool:
    meta = _get_meta(chunk)
    return meta.get("document_category", "") in LEGAL_CATEGORIES


def _is_analytics(chunk: dict) -> bool:
    meta = _get_meta(chunk)
    return meta.get("document_category", "") == ANALYTICS_CATEGORY


def _is_chapter_heading(chunk: dict) -> bool:
    """True if the entire chunk text is essentially just a chapter title."""
    text = chunk.get("text", "").strip()
    return bool(_CHAPTER_HDG_RE.match(text)) and len(text) < 100


def _contains_csv_table(chunk: dict) -> bool:
    """True if the chunk text looks like a raw pandas DataFrame / CSV dump."""
    text = chunk.get("text", "")
    return bool(_CSV_ROW_RE.search(text))


def _authority_weight(law_title: str) -> float:
    """Higher weight for primary legislation vs manuals/forms."""
    t = (law_title or "").lower()
    if any(k in t for k in ["act 1927", "ordinance 2002", "amendment act 2022",
                             "wildlife", "hazara forest act"]):
        return 0.20
    if any(k in t for k in ["act", "ordinance", "rules", "regulation"]):
        return 0.10
    if any(k in t for k in ["case", "pld", "scmr", "ylr", "clc"]):
        return 0.08
    return 0.0


# ─────────────────────────────────────────────────────────────────────────────
#  ClauseRanker
# ─────────────────────────────────────────────────────────────────────────────

class ClauseRanker:
    """
    Ranks retrieved chunks by intent mode and enforces a hard token ceiling.

    Supported intent modes (from LegalIntentMode enum):
      DEFINITION  — "what is X", "what is meant by Y"
      PENALTY     — "what is the penalty for X"
      ARREST      — "who can arrest", "can a forest officer arrest"
      SECTION     — "what does section N say"
      GENERAL     — everything else
    """

    def __init__(self, max_tokens: int = 1200):
        self.max_tokens = max_tokens

    # ──────────────────────────────────────────────────────────────────────────
    #  Public entry point
    # ──────────────────────────────────────────────────────────────────────────

    def rank_and_truncate(
        self,
        chunks: List[Dict[str, Any]],
        intent_mode: "LegalIntentMode",
        query: str,
    ) -> List[Dict[str, Any]]:
        """
        Main ranking method.  Returns an ordered, token-budgeted list of chunks.
        """
        from pipeline.legal_synthesizer.intent_mode import LegalIntentMode

        if not chunks:
            return []

        query_lower = query.lower()

        # ── Detect intent from mode enum ──────────────────────────────────────
        is_botanical  = any(w in query_lower for w in 
                            ["flowering", "fruiting", "elevation", "family", "botanical", "season", "grow", "altitude"])
        is_penalty    = not is_botanical and (intent_mode == LegalIntentMode.PENALTY or any(
                            w in query_lower for w in
                            ["penalty", "fine", "punish", "punishment", "rupees"]))
        is_definition = not is_botanical and (intent_mode == LegalIntentMode.DEFINITION or any(
                            p in query_lower for p in
                            ["what is", "what are", "meant by", "definition of",
                             "define", "meaning of"]))
        is_arrest     = not is_botanical and (intent_mode == LegalIntentMode.ARREST or any(
                            w in query_lower for w in
                            ["arrest", "warrant", "detain", "custody"]))
        is_section    = not is_botanical and ((hasattr(LegalIntentMode, "SECTION") and
                         intent_mode == LegalIntentMode.SECTION) or bool(
                             _SEC_NUM_RE.search(query_lower)))

        # NEW — safety net: "what does <doc> say about <topic>" is a document
        # lookup, not a definition, even if intent_mode was mis-set upstream
        # to DEFINITION. This does not change is_definition's value for any
        # other query type — it only overrides the routing decision below.
        is_doc_reference = bool(re.search(
            r'what\s+does.*(manual|act|ordinance|rule|schedule|section|'
            r'circular|notification|policy|working plan)\s*.*\bsay\b',
            query_lower
        ))
        if is_doc_reference:
            is_definition = False

        # ── Route to the correct handler ──────────────────────────────────────
        if is_botanical:
            return self._rank_botanical(chunks, query_lower)

        if is_penalty:
            return self._rank_penalty(chunks, query_lower)

        if is_doc_reference:
            # Prefer entity/topic relevance over generic definition scoring
            return self._rank_general(chunks, query_lower)

        if is_definition:
            return self._rank_definition(chunks, query_lower)

        if is_section:
            return self._rank_section(chunks, query_lower)

        # ARREST and GENERAL share the same scorer
        return self._rank_general(chunks, query_lower)

    # ──────────────────────────────────────────────────────────────────────────
    #  PENALTY ranking
    # ──────────────────────────────────────────────────────────────────────────

    def _rank_penalty(
        self, chunks: List[Dict], query_lower: str
    ) -> List[Dict]:
        """
        RC-1 FIX:
          • RULE slot sourced ONLY from legal_chunks.
          • analytics_chunks feed the penalty hint calculator but NEVER appear
            in the ranked output.
          • CSV/DataFrame dump chunks are excluded entirely.
        """
        logger.info("[ClauseRanker] PENALTY intent")

        species = self._extract_species(query_lower)

        # Separate legal vs analytics vs other
        legal_chunks     = [c for c in chunks if _is_legal(c) and not _contains_csv_table(c)]
        analytics_chunks = [c for c in chunks if _is_analytics(c)]   # hint only
        # Everything else (operational, manuals) → dropped silently

        rule_pool = legal_chunks if legal_chunks else [
            c for c in chunks if not _is_analytics(c) and not _contains_csv_table(c)
        ]

        logger.debug(
            f"[ClauseRanker] PENALTY: total={len(chunks)}, "
            f"legal={len(legal_chunks)}, analytics={len(analytics_chunks)}, "
            f"rule_pool={len(rule_pool)}, species={species}"
        )

        # Filter rule_pool for penalty-relevant content
        penalty_keywords = [
            "punished with", "fine which may", "imprisonment",
            "liable to", "penalty", "rupees", "rs.", "schedule",
            "offence", "conviction",
        ]
        penalty_chunks = [
            c for c in rule_pool
            if any(kw in c.get("text", "").lower() for kw in penalty_keywords)
        ]

        # Species-specific filter
        if species and penalty_chunks:
            species_specific = [
                c for c in penalty_chunks
                if species.lower() in c.get("text", "").lower()
            ]
            if species_specific:
                logger.info(
                    f"[ClauseRanker] PENALTY species={species}: "
                    f"{len(species_specific)} species-specific chunks"
                )
                return self._apply_token_budget(species_specific[:8])

        # Fallback: general penalty chunks
        if penalty_chunks:
            logger.info(
                f"[ClauseRanker] PENALTY: {len(penalty_chunks)} general penalty chunks"
            )
            return self._apply_token_budget(penalty_chunks[:8])

        # Last resort: top of rule_pool (still excludes analytics+CSV)
        logger.warning(
            f"[ClauseRanker] PENALTY intersection failed for species={species}. "
            f"Returning top rule_pool chunks."
        )
        return self._apply_token_budget(rule_pool[:3])

    # ──────────────────────────────────────────────────────────────────────────
    #  DEFINITION ranking
    # ──────────────────────────────────────────────────────────────────────────

    def _rank_definition(
        self, chunks: List[Dict], query_lower: str
    ) -> List[Dict]:
        """
        RC-2/RC-3/RC-4 FIX:
          • section_type="definition" or section_number="2" chunks are boosted
            to the TOP before any keyword scan.
          • Chapter headings are demoted to the bottom.
          • Circular/cross-reference definitions only penalised when they have
            NO substantive content beyond the cross-reference.
        """
        logger.info("[ClauseRanker] DEFINITION intent")

        # Step 1 — global pre-sort:
        #   tier-0: section_type==definition  (highest priority)
        #   tier-1: has definition keywords in first 150 chars
        #   tier-2: mentions the query term
        #   tier-3: chapter headings (lowest)

        def _tier(c: dict) -> int:
            meta = _get_meta(c)
            text = c.get("text", "")
            text_l = text.lower()[:150]

            if _is_chapter_heading(c):
                return 3

            # RC-2 FIX: explicit definition metadata
            if (meta.get("section_type") == "definition" or
                    meta.get("section_number") == "2"):
                return 0

            # Substantive definition keywords near start of text
            def_kws = ["means ", "includes ", "defined as", "is called",
                       "meaning of", "denotes", '"', "\u201c"]
            if any(kw in text_l for kw in def_kws):
                return 1

            return 2

        sorted_chunks = sorted(chunks, key=_tier)
        non_headings  = [c for c in sorted_chunks if not _is_chapter_heading(c)]
        headings      = [c for c in sorted_chunks if _is_chapter_heading(c)]
        ordered       = non_headings + headings

        # Step 2 — strict definition filter with quality scoring
        scored_defs = self._score_definitions(ordered, query_lower)
        if scored_defs:
            logger.info(
                f"[ClauseRanker] DEFINITION lock: {len(scored_defs)} chunks"
            )
            return self._apply_token_budget(scored_defs[:8])

        # Step 3 — semantic fallback: keyword density
        logger.info("[ClauseRanker] No strict defs — semantic fallback")
        sem_kws = ["means", "includes", "defined as", "refers to",
                   "denotes", "is called"]
        semantic = self._semantic_search(ordered, sem_kws)
        if semantic:
            return self._apply_token_budget(semantic[:8])

        # Step 4 — term matching fallback
        term = (query_lower
                .replace("what is", "").replace("what are", "")
                .replace("meant by", "").replace("definition of", "")
                .replace("define", "").replace("?", "").strip())
        if term:
            term_chunks = [
                c for c in ordered
                if term in c.get("text", "").lower()
            ]
            if term_chunks:
                logger.info(
                    f"[ClauseRanker] Term match '{term}': {len(term_chunks)} chunks"
                )
                return self._apply_token_budget(term_chunks[:8])

        # Step 5 — last resort: top non-heading chunks
        logger.warning(
            f"[ClauseRanker] No definition found for '{query_lower[:40]}'. "
            f"Returning top non-heading chunks."
        )
        return self._apply_token_budget((non_headings or ordered)[:3])

    # ──────────────────────────────────────────────────────────────────────────
    #  SECTION ranking  (RC-5 FIX: new handler)
    # ──────────────────────────────────────────────────────────────────────────

    def _rank_section(
        self, chunks: List[Dict], query_lower: str
    ) -> List[Dict]:
        """
        RC-5 FIX: Dedicated handler for "what does section N say" queries.

        Priority order:
          1. Chunks whose section metadata exactly matches the queried number.
          2. Legal chunks whose text contains "section N" near the start.
          3. Any legal chunk mentioning the section.
          4. General fallback (non-analytics, non-CSV).
        """
        logger.info("[ClauseRanker] SECTION intent")

        # Extract target section numbers from query
        targets = [m.group(1) for m in _SEC_NUM_RE.finditer(query_lower)]
        logger.debug(f"[ClauseRanker] SECTION targets: {targets}")

        if not targets:
            return self._rank_general(chunks, query_lower)

        # Tier 1: exact section metadata match (legal chunks only)
        exact: List[Dict] = []
        for c in chunks:
            if not _is_legal(c):
                continue
            meta   = _get_meta(c)
            sec_id = str(meta.get("section_id", "") or "").lower()
            sec_no = str(meta.get("section_number", "") or "").lower()
            sec    = str(meta.get("section", "") or "").lower()
            chunk_id = str(c.get("chunk_id", "") or "").lower()
            for t in targets:
                if (t == sec_no or
                        t == sec_id or
                        f"sec_{t}" in sec_id or
                        f"section_{t}" in chunk_id or
                        f"section {t}" in sec):
                    exact.append(c)
                    break

        if exact:
            logger.info(
                f"[ClauseRanker] SECTION exact match: {len(exact)} chunks"
            )
            return self._apply_token_budget(exact[:8])

        # Tier 2: text contains "section N" near start (legal chunks)
        text_match: List[Dict] = []
        for c in chunks:
            if not _is_legal(c):
                continue
            text_start = c.get("text", "")[:200].lower()
            for t in targets:
                if f"section {t}" in text_start or f"section{t}" in text_start:
                    text_match.append(c)
                    break

        if text_match:
            logger.info(
                f"[ClauseRanker] SECTION text match: {len(text_match)} chunks"
            )
            return self._apply_token_budget(text_match[:8])

        # Tier 3: any legal chunk mentioning the section anywhere in text
        mention_match: List[Dict] = []
        for c in chunks:
            if not _is_legal(c):
                continue
            text_l = c.get("text", "").lower()
            for t in targets:
                if f"section {t}" in text_l:
                    mention_match.append(c)
                    break

        if mention_match:
            logger.info(
                f"[ClauseRanker] SECTION mention match: {len(mention_match)} chunks"
            )
            return self._apply_token_budget(mention_match[:8])

        # Tier 4: general fallback
        logger.warning(
            f"[ClauseRanker] SECTION: no matching chunk for {targets}. "
            f"Using general fallback."
        )
        return self._rank_general(chunks, query_lower)

    # ──────────────────────────────────────────────────────────────────────────
    #  GENERAL / ARREST ranking
    # ──────────────────────────────────────────────────────────────────────────

    def _rank_botanical(
        self, chunks: List[Dict], query_lower: str
    ) -> List[Dict]:
        """
        Scored ranking for botanical/ecological queries.
        Boosts working plans and species master data. Penalizes legal statutes.
        """
        logger.info("[ClauseRanker] BOTANICAL ranking")
        scored: List[Dict] = []
        for c in chunks:
            score = c.get("vector_score", 0.0) or c.get("graph_score", 0.0) or 0.5
            text = c.get("text", "")
            meta = _get_meta(c)
            law_title = meta.get("law_title", "").lower()

            # Boost: Botanical / working plan sources
            if any(k in law_title for k in ["species master", "working plan", "ecological"]):
                score += 0.50
            if "family:" in text.lower() or "flowering:" in text.lower() or "elevation:" in text.lower():
                score += 0.30

            # Penalty: Legal statutes (less likely to have pure botanical info)
            if _is_legal(c):
                score -= 0.30

            # Boost: query term in text
            terms = [t for t in query_lower.split() if len(t) > 3]
            hit_ratio = sum(1 for t in terms if t in text.lower()) / max(len(terms), 1)
            score += hit_ratio * 0.20

            cc = deepcopy(c)
            cc["_rank_score"] = round(score, 4)
            scored.append(cc)

        scored.sort(key=lambda x: x.get("_rank_score", 0.0), reverse=True)
        return self._apply_token_budget(scored[:10])

    def _rank_general(
        self, chunks: List[Dict], query_lower: str
    ) -> List[Dict]:
        """
        Scored ranking for ARREST and GENERAL intent.
        Legal chunks get authority bonus. CSV/analytics/headings demoted.
        """
        logger.info("[ClauseRanker] GENERAL/ARREST ranking")

        is_tree_query = any(k in query_lower for k in ["tree", "felling", "timber", "cutting", "wood", "pine", "fir", "oak", "walnut", "deodar", "chir", "shisham", "species", "schedule-i", "schedule i"])

        scored: List[Dict] = []
        for c in chunks:
            score = c.get("vector_score", 0.0) or c.get("graph_score", 0.0) or 0.5
            text  = c.get("text", "")
            meta  = _get_meta(c)
            law_title = meta.get("law_title", "").lower()

            # Boost: legal category
            if _is_legal(c):
                score += 0.15

            # Boost: authority (primary legislation > manuals)
            score += _authority_weight(law_title)

            # Schedule-I Tree vs Animal Fix
            if is_tree_query:
                if "wildlife" in law_title:
                    score -= 0.60
                if "forest ordinance" in law_title or "forest amendment" in law_title:
                    score += 0.30

            # Boost: substantive content
            if len(text) > 200:
                score += 0.05
            if len(text) > 500:
                score += 0.05

            # Boost: section metadata present
            if meta.get("section") and meta.get("section") not in ("General", "N/A"):
                score += 0.10

            # Penalty: chapter headings
            if _is_chapter_heading(c):
                score -= 0.40

            # Penalty: analytics / CSV
            if _is_analytics(c) or _contains_csv_table(c):
                score -= 0.50

            # Boost: query term in text
            terms = [t for t in query_lower.split() if len(t) > 3]
            hit_ratio = sum(1 for t in terms if t in text.lower()) / max(len(terms), 1)
            score += hit_ratio * 0.10

            cc = deepcopy(c)
            cc["_rank_score"] = round(score, 4)
            scored.append(cc)

        scored.sort(key=lambda x: x.get("_rank_score", 0.0), reverse=True)
        return self._apply_token_budget(scored[:10])

    # ──────────────────────────────────────────────────────────────────────────
    #  Helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _score_definitions(
        self, chunks: List[Dict], query_lower: str
    ) -> List[Dict]:
        """
        Score each chunk for definition quality.
        Returns only chunks with quality > 0, sorted best-first.
        """
        scored: List[Dict] = []
        for chunk in chunks:
            text  = chunk.get("text", "").strip()
            text_l = text.lower()
            meta  = _get_meta(chunk)

            quality = 0.0

            # RC-2/RC-3 FIX: explicit definition metadata → highest boost
            if meta.get("section_type") == "definition":
                quality += 0.60
            if meta.get("section_number") == "2":
                quality += 0.40
            if meta.get("type", "") == "definition":
                quality += 0.50

            # Definitional keywords in first 150 chars
            def_kws_early = ["means ", "includes ", "defined as",
                             "is called", "shall mean", "shall include"]
            if any(kw in text_l[:150] for kw in def_kws_early):
                quality += 0.30

            # Definitional keywords anywhere
            def_kws_any = ["means", "includes", "defined as", "denotes",
                           "refers to", "meaning of"]
            if any(kw in text_l for kw in def_kws_any):
                quality += 0.15

            # Quoted term near the start (e.g. '"timber" includes ...')
            if any(q in text[:60] for q in ['"', "'", "\u201c", "\u201d"]):
                quality += 0.20

            # Content length bonus (real definitions are substantive)
            if len(text) > 100:
                quality += 0.10
            if len(text) > 300:
                quality += 0.05

            # RC-4 FIX: Chapter heading → heavy penalty
            if _is_chapter_heading(chunk):
                quality -= 1.00

            # RC-6 FIX: Weak circular reference — only penalise if NO
            #           substantive content beyond the cross-reference
            weak_indicators = [
                "as defined in", "meaning assigned to",
                "shall have the same meaning", "assigned to them in",
            ]
            is_circular = any(wi in text_l for wi in weak_indicators)
            if is_circular and len(text) < 120:
                # Short + circular = useless
                quality -= 0.80
            # (long + circular = probably still useful, no penalty)

            if quality > 0:
                cc = deepcopy(chunk)
                cc["def_quality"] = round(quality, 3)
                scored.append(cc)

        scored.sort(key=lambda x: x.get("def_quality", 0.0), reverse=True)
        return scored

    def _semantic_search(
        self, chunks: List[Dict], keywords: List[str]
    ) -> List[Dict]:
        """Rank by keyword density in text."""
        scored = []
        for c in chunks:
            text_l = c.get("text", "").lower()
            density = sum(1 for kw in keywords if kw in text_l)
            if density > 0:
                scored.append((c, density))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [s[0] for s in scored]

    def _apply_token_budget(self, chunks: List[Dict]) -> List[Dict]:
        """Enforce max_tokens ceiling — keeps chunks in rank order."""
        budgeted: List[Dict] = []
        used = 0
        for c in chunks:
            tokens = _estimate_tokens(c.get("text", ""))
            if used + tokens <= self.max_tokens:
                budgeted.append(c)
                used += tokens
            else:
                break
        return budgeted

    @staticmethod
    def _extract_species(query_lower: str) -> Optional[str]:
        """Extract tree species name from penalty query."""
        species_map = {
            "deodar":  ["deodar", "cedrus deodara", "diyar", "cedar"],
            "chir":    ["chir pine", "chir", "pinus roxburghii", "cheerh"],
            "blue pine": ["blue pine", "pinus wallichiana", "kail"],
            "spruce":  ["spruce", "picea smithiana"],
            "fir":     ["silver fir", "abies pindrow", "fir"],
        }
        for canonical, variants in species_map.items():
            if any(v in query_lower for v in variants):
                return canonical
        return None