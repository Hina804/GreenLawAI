"""
IntentClassifier
Deterministic routing-only classifier.
Registry-Compatible (Phase 3)
"""

import re
from typing import Dict, Any, List
from loguru import logger
from core.contracts import BasePipelineComponent
from core.dictionaries import LEGAL_DICTIONARY, SPECIES_DICTIONARY

# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────

VALID_INTENTS = {"legal", "definition", "climate", "monitoring", "general", "precedent", "awareness", "summary", "incident"}

CONFIDENCE_MAP = {
    "definition": 0.95,
    "legal": 0.85,
    "precedent": 0.85,
    "monitoring": 0.85,
    "climate": 0.85,
    "awareness": 0.90,
    "summary": 0.90,
    "incident": 0.85,
    "general": 0.40
}


# ──────────────────────────────────────────────
# CLASSIFIER
# ──────────────────────────────────────────────

class IntentClassifier(BasePipelineComponent):
    """
    Deterministic intent router.
    Single responsibility: routing + entity extraction.
    """

    def __init__(self, component_id: str = "intent_classifier"):
        super().__init__(component_id)
        self.llm_manager = None

        # ── Intent Keyword Map ──
        self.intents = {
            "definition": [
                "what is", "what are", "define", "definition", "meaning",
                "what does", "what do", "called", "term", "terminology",
                "what is meant by", "define the term"
            ],

            "legal": [
                "penalty", "penalties", "permit", "law", "legal", "regulation",
                "illegal", "fine", "fines", "ordinance", "act", "section",
                "offence", "offences", "court", "arrest", "warrant",
                "punishment", "imprisonment", "rights", "authority",
                "officer", "reserved", "forest act", "allowed", "can i",
                "seigniorage", "transit", "felling", "cutting"
            ],

            "precedent": [
                "precedent", "case", "cases", "ruling", "judgment",
                "judgments", "similar case", "previous case", "related case"
            ],

            "climate": [
                "carbon", "climate", "emission", "conservation",
                "sequestration", "environment", "ecosystem", "co2",
                "biodiversity", "deforestation", "biomass", "reforestation",
                "oxygen", "temperature"
            ],

            "monitoring": [
                "trend", "pattern", "activity", "anomaly", "logging activity", "hotspot",
                "district data", "statistics", "map", "recent cases"
            ],

            "incident": [
                "incident", "report", "alert", "violation", "crime", "illegal felling",
                "detected", "witnessed", "happened", "occurred", "at night"
            ],

            "awareness": [
                "simply", "easy", "plain language", "citizen", "public", "layman", 
                "explain simply", "how do i", "can i", "simplified"
            ],

            "summary": [
                "summarize", "summary", "overview", "tl;dr", "brief", "key points", "outline"
            ],

            "general": [
                "hello", "hi", "hey", "help", "thanks", "thank you",
                "who are you", "what can you do"
            ]
        }

    async def load(self, config: Dict[str, Any]) -> bool:
        """Lifecycle: Initialization."""
        self._is_loaded = True
        logger.info(f"[IntentClassifier] {self.component_id} loaded.")
        return True

    async def unload(self) -> bool:
        """Lifecycle: Shutdown."""
        self._is_loaded = False
        return True

    # ──────────────────────────────────────────────
    # PUBLIC API
    # ──────────────────────────────────────────────

    def classify(self, query: str) -> Dict[str, Any]:
        q = query.lower().strip()
        import re
    
        # ── LEGAL — highest priority ───────────────────────────────────
        legal_patterns = [
            r"(section|sec\.?)\s*\d+",
            r"(forest act|ordinance|amendment)",
            r"(penalty|fine|punishment|sentence|imprisonment|jail)",
            r"legal action",
            r"(illegal|unauthorized).*(log|cut|fell|graz|encroach)",
            r"(cut|fell|log|harvest).*(tree|timber|forest|deodar|chir|pine)",
            r"(villager|person|accused|offender|someone|man|woman)",
            r"(night|nighttime|night.?time).*(operation|cut|log|fell|graz)",
            r"(reserved|protected|guzara).*(forest)",
            r"difference between",
            r"(arrest|warrant|confiscat|seiz)",
            r"(bail|surety|magistrate|court|judge|verdict)",
            r"(deodar|chir|pine|spruce|fir|oak|timber|wood)",
            r"(transit|transport).*(timber|wood|log|permit)",
            r"what (does|is|are).*(section|law|act|ordinance|rule|penalty|fine)",
            r"how (much|many).*(fine|penalty|tree|year|month)",
            r"(evidence|proof|admissible|sha.256|document)",
            r"(permit|license|felling|extraction)",
            r"(encroach|demarcate|boundar|survey)",
            r"(fire|burn|arson).*(penalty|fine|forest act)",
            r"(graz|cattle|livestock).*(penalty|fine|forest)",
            r"(trees? cut|cut.*trees?|felled|fell.*tree)",
            r"what (happens|action|can).*(if|when|after)",
        ]
    
        # ── PRECEDENT / CASE LAW ────────────────────────────────────────
        precedent_patterns = [
            r"(precedent|case law|ruling|judgment|judgement)",
            r"\b(19|20)\d{2}\s*(pld|scmr|mld|ylr|clc|plj|cld)\s*\d+\b",  # citation format
            r"(prosecution|defense|defence)\s*(argument|case)",
            r"\bv[s\.]?\s+[A-Z][a-z]+",  # "vs Gul Zaman", "v. State" pattern
            r"(petitioner|respondent|appellant|held that)",
        ]
    
        # ── MONITORING — satellite/live data ──────────────────────────
        monitoring_patterns = [
            r"(active|current|live|right now|currently|happening|going on)",
            r"(fire|deforestation|logging).*(near|in|around|detected)",
            r"(nasa|firms|gfw|satellite|thermal|anomal)",
            r"(alert|detection).*(today|now|current|live)",
            r"(map|monitor|surveillance)",
        ]
    
        # ── INCIDENT — historical records ─────────────────────────────
        incident_patterns = [
            r"(recent|latest|last).*(incident|case|report|violation)",
            r"(history|record|log).*(incident|case|violation)",
            r"(how many|number of).*(incident|case|violation|report)",
        ]
    
        # ── AWARENESS — citizen reporting ─────────────────────────────
        awareness_patterns = [
            r"how (do i|can i|to) report",
            r"(contact|phone|number|email).*(dfo|officer|forest)",
            r"i (saw|noticed|observed|found|spotted|see)",
            r"(help me|guide me|tell me how to)",
            r"(nearest|closest).*(office|dfo|ranger|station)",
            r"(tip|advice|guide|citizen|public).*(forest|safety)",
            r"(where|who).*(report|complain|contact)",
        ]
    
        legal_score      = sum(1 for p in legal_patterns      if re.search(p, q))
        precedent_score   = sum(1 for p in precedent_patterns  if re.search(p, q, re.IGNORECASE))
        monitoring_score = sum(1 for p in monitoring_patterns if re.search(p, q))
        incident_score   = sum(1 for p in incident_patterns   if re.search(p, q))
        awareness_score  = sum(1 for p in awareness_patterns  if re.search(p, q))
    
        # Legal wins over incident if both match — "villager cut trees" 
        # is a legal question, not an incident lookup
        if legal_score > 0 and incident_score > 0:
            incident_score = 0  # legal always beats incident
    
        # Precedent should win over generic legal when a citation is present
        if precedent_score > 0:
            legal_score = 0
    
        scores = {
            "legal":      legal_score,
            "precedent":  precedent_score,
            "monitoring": monitoring_score,
            "incident":   incident_score,
            "awareness":  awareness_score,
        }
    
        best = max(scores, key=scores.get)
    
        # Default to legal for any domain query with no clear match
        if scores[best] == 0:
            best = "legal"
    
        from loguru import logger
        logger.info(
            f"[CLASSIFY] '{q[:50]}' → {best} "
            f"(legal:{legal_score} precedent:{precedent_score} monitor:{monitoring_score} "
            f"incident:{incident_score} aware:{awareness_score})"
        )
    
        return {
            "primary_intent":   best,
            "possible_intents": [best],
            "confidence":       0.9,
            "scores":           scores,
        }



    # ──────────────────────────────────────────────
    # ENTITY EXTRACTION
    # ──────────────────────────────────────────────

    def extract_entities(self, query_lower: str) -> Dict[str, List[str]]:
        results = {
            "tree_species": [],
            "locations": [],
            "legal_refs": [],
            "legal_sections": [],
            "timeframes": []
        }

        # ── Species dictionary ──
        for species, synonyms in SPECIES_DICTIONARY.items():
            if species in query_lower or any(s in query_lower for s in synonyms):
                results["tree_species"].append(species)

        # ── Legal sections ──
        section_matches = re.findall(r"section\s+(\d+|[ivxlcdm]+)", query_lower)
        results["legal_sections"] = section_matches

        # ── Legal refs dictionary ──
        for law, synonyms in LEGAL_DICTIONARY.items():
            if law in query_lower or any(s in query_lower for s in synonyms):
                results["legal_refs"].append(law)

        # ── Time patterns ──
        time_matches = re.findall(r"\b(19\d{2}|20\d{2}|today|yesterday|tomorrow)\b", query_lower)
        results["timeframes"] = time_matches

        # Deduplicate
        for k in results:
            results[k] = list(set(results[k]))

        return results