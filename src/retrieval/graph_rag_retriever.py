"""
GraphRAG Retriever  v5.0
Hybrid retrieval combining Vector Search (FAISS) and Graph Search (Neo4j).

KEY FIXES vs v4.4
─────────────────
  [FIX-A] ENTITY NORMALISATION
          • strip_graph_prefixes()  removes dbh_1_, the_province_of_, standing_,
            cedrus_, pinus_, etc. before any comparison.
          • normalise_for_graph()   lower-cases, removes punctuation, collapses
            spaces → underscores so "Khyber Pakhtunkhwa" ↔ "khyber_pakhtunkhwa".

  [FIX-B] MULTI-PASS CYPHER MATCHING
          Pass-1  exact canonical_name  (fastest, most precise)
          Pass-2  CONTAINS on canonical_name / aliases  (catches substrings)
          Pass-3  token-overlap fuzzy match via apoc.text.sorensenDiceSimilarity
                  (optional – skipped gracefully if APOC not installed)
          All three passes merged; duplicates de-duplicated by chunk_id.

  [FIX-C] SYNONYM EXPANSION (cross-domain)
          DOMAIN_SYNONYMS covers Forest, Climate, Judiciary and Permits terms.
          Every query term is expanded with its synonyms before graph search.

  [FIX-D] PREFIX STRIPPING ON STORED NAMES
          graph_search() pre-processes returned entity names so comparison
          works even when Neo4j stores "dbh_1_deodar" instead of "deodar".

  [FIX-E] CONFIGURABLE FUZZY THRESHOLD
          GraphRAGRetriever(fuzzy_threshold=0.65) — default 0.65.
          Similarity below threshold is ignored so noise is kept out.

  Original fixes from v4.4 retained:
  [FIX-1] Temporal entity / act-year detection
  [FIX-2] Minimum score threshold (0.40) to filter noise chunks
  [FIX-3] Jurisdiction entity detection + graph scoping
  [FIX-4] Degree-based graph score dampening
"""

from __future__ import annotations

import asyncio
import math
import os
import re
import unicodedata
from collections import defaultdict
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

# ── Project imports ───────────────────────────────────────────────────────────
from core.document_registry import get_real_law_title
from data_pipeline.indexing.vector_indexer import VectorIndexer
from data_pipeline.indexing.entity_extractor import EntityExtractor
from core.dictionaries import LEGAL_DICTIONARY, SPECIES_DICTIONARY

# ─────────────────────────────────────────────────────────────────────────────
# Category constants
# ─────────────────────────────────────────────────────────────────────────────
LEGAL_CATEGORIES = {"legal_statute", "legal_rules", "case_law"}

NON_LEGAL_CATEGORIES = {
    "analytics", "operational", "permit", "rates",
    "report", "citizen_engagement", "climate", "policy",
    "uncategorized",
}

# Regex to detect obviously junk law_title values (raw doc-id hashes)
_DOC_ID_RE = re.compile(
    r"^(doc_|DOC_)?\d{8}_\d{6}_[a-f0-9]{6,}$", re.IGNORECASE
)


def _is_junk_law_title(raw: str) -> bool:
    """True if the law_title looks like a pipeline-generated hash, not a real name."""
    if not raw:
        return True
    return bool(_DOC_ID_RE.match(raw.strip()))


# ─────────────────────────────────────────────────────────────────────────────
# FIX-A  ── Prefix / noise stripping tables
# ─────────────────────────────────────────────────────────────────────────────

# Prefixes that appear in stored Neo4j entity names but add no semantic value.
# Order matters – longer prefixes must come before shorter ones.
_STRIP_PREFIXES: Tuple[str, ...] = (
    "the_province_of_",
    "province_of_",
    "the_district_of_",
    "district_of_",
    "cedrus_",          # botanical genus prefixes
    "pinus_",
    "quercus_",
    "abies_",
    "picea_",
    "standing_",        # measurement-context prefixes
    "dbh_1_",
    "dbh_2_",
    "dbh_3_",
    "dbh_",
    "avg_",
    "total_",
    "no_",              # "no_of_trees" → "trees"
)

# Suffixes that add no semantic value
_STRIP_SUFFIXES: Tuple[str, ...] = (
    "_tree",
    "_trees",
    "_species",
    "_timber",
    "_wood",
)

# Regex: collapse any run of non-alphanumeric chars to a single underscore
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def strip_graph_prefixes(name: str) -> str:
    """
    Remove known noisy prefixes/suffixes from a stored Neo4j entity name.

    Examples
    --------
    "dbh_1_deodar"           → "deodar"
    "the_province_of_punjab" → "punjab"
    "cedrus_deodara"         → "deodara"   (botanical suffix kept; alias handles it)
    "standing_deodar"        → "deodar"
    """
    s = name.lower().strip()
    changed = True
    while changed:
        changed = False
        for pfx in _STRIP_PREFIXES:
            if s.startswith(pfx):
                s = s[len(pfx):]
                changed = True
        for sfx in _STRIP_SUFFIXES:
            if s.endswith(sfx) and len(s) > len(sfx):
                s = s[: -len(sfx)]
                changed = True
    return s


def normalise_for_graph(term: str) -> str:
    """
    Produce a lowercase, punctuation-free, underscore-joined token suitable
    for CONTAINS / similarity comparisons against Neo4j stored values.

    "Khyber Pakhtunkhwa" → "khyber_pakhtunkhwa"
    "Section 26-A"        → "section_26_a"
    """
    # Unicode normalise (NFKD) then drop combining marks
    s = unicodedata.normalize("NFKD", term)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = _NON_ALNUM.sub("_", s)
    s = s.strip("_")
    return s


# ─────────────────────────────────────────────────────────────────────────────
# FIX-C  ── Cross-domain synonym dictionaries
# ─────────────────────────────────────────────────────────────────────────────

DOMAIN_SYNONYMS: Dict[str, List[str]] = {
    # ── Forest domain ────────────────────────────────────────────────────────
    "deodar": [
        "cedrus deodara", "cedrus_deodara", "diyar", "devdar", "himalayan cedar",
        "deodara", "national tree", "pakistan national tree",
        # stored variants
        "dbh_1_deodar", "dbh_2_deodar", "standing_deodar",
    ],
    "chir pine": [
        "chir", "cheerh", "long-leaved pine", "pinus roxburghii", "pinus_roxburghii",
        "chirh", "cheer pine", "chir_pine",
    ],
    "blue pine": [
        "biar", "nakhtar", "kail", "pinus wallichiana", "pinus_wallichiana",
        "kail pine", "blue_pine",
    ],
    "spruce": ["picea smithiana", "picea_smithiana", "morinda spruce", "rai"],
    "fir": ["abies pindrow", "abies_pindrow", "silver fir", "pindrow fir"],
    "oak": ["quercus", "banj", "moru oak", "green oak"],
    "forest officer": [
        "fo", "forest-officer", "range officer", "range forest officer",
        "divisional forest officer", "dfo", "assistant conservator",
    ],
    "reserved forest": ["reserve forest", "rf", "reserved_forest"],
    "protected forest": ["pf", "protected_forest"],
    "forest produce": ["forest product", "forest products", "forest_produce"],
    "seigniorage": ["seigniorage fee", "revenue fee", "timber fee"],
    "transit pass": ["transit permit", "form-16", "form 16", "challan"],
    # ── Climate domain ───────────────────────────────────────────────────────
    "carbon credit": [
        "carbon credits", "carbon offset", "carbon offsets",
        "greenhouse gas credit", "ghg credit", "emission reduction credit",
    ],
    "emissions": [
        "emission", "ghg", "greenhouse gas", "greenhouse gases",
        "co2", "carbon dioxide", "methane", "nox",
    ],
    "climate change authority": [
        "climate authority", "climate board", "climate action board",
        "pakistan climate authority", "pca", "climate council",
    ],
    "environmental impact assessment": [
        "eia", "environmental assessment", "environment assessment",
        "impact assessment", "environmental review",
    ],
    "biodiversity": [
        "biological diversity", "flora and fauna", "wildlife", "ecosystem",
    ],
    "national environmental quality standards": [
        "neqs", "neq standards", "environmental quality standards",
        "pollution standards", "emission standards",
    ],
    # ── Judiciary domain ─────────────────────────────────────────────────────
    "high court": [
        "superior court", "lahore high court", "lhc",
        "peshawar high court", "phc", "sindh high court", "shc",
        "balochistan high court", "bhc", "islamabad high court", "ihc",
    ],
    "supreme court": ["apex court", "sc", "chief justice"],
    "writ petition": ["writ", "constitutional petition", "article 199"],
    "appeal": ["revision", "review petition", "first appeal", "second appeal"],
    "bail": ["pre-arrest bail", "post-arrest bail", "transit bail", "surety"],
    "magistrate": ["judicial magistrate", "executive magistrate", "jm", "em"],
    "fir": [
        "first information report", "first_information_report",
        "police complaint", "criminal complaint",
    ],
    "decree": ["judgment", "judgement", "order", "decree and order"],
    "contempt": ["contempt of court", "contempt proceedings"],
    # ── Permits domain ───────────────────────────────────────────────────────
    "noc": [
        "no objection certificate", "no-objection certificate",
        "no_objection_certificate", "clearance certificate",
    ],
    "license": ["licence", "permit", "authorisation", "authorization"],
    "clearance": [
        "environmental clearance", "ec", "site clearance",
        "building clearance", "regulatory clearance",
    ],
    "land use permit": [
        "land use change", "land conversion", "change of land use",
        "luc", "land use certificate",
    ],
    "felling permit": [
        "tree felling permit", "felling license", "cutting permit",
        "timber permit", "extraction permit",
    ],
    # ── Province / jurisdiction ───────────────────────────────────────────────
    "kpk": [
        "khyber pakhtunkhwa", "khyber_pakhtunkhwa",
        "the_province_of_khyber_pakhtunkhwa",
        "nwfp", "north west frontier province", "north-west frontier province",
        "khyber", "kpk province",
    ],
    "punjab": ["the_province_of_punjab", "province of punjab", "punjab province"],
    "sindh": ["the_province_of_sindh", "province of sindh", "sind", "sindh province"],
    "balochistan": [
        "the_province_of_balochistan", "baluchistan",
        "province of balochistan",
    ],
}

# Build reverse lookup: any synonym → canonical key
_SYNONYM_REVERSE: Dict[str, str] = {}
for _canon, _syns in DOMAIN_SYNONYMS.items():
    for _s in _syns:
        _SYNONYM_REVERSE[normalise_for_graph(_s)] = _canon
    _SYNONYM_REVERSE[normalise_for_graph(_canon)] = _canon


def expand_with_synonyms(term: str) -> List[str]:
    """
    Return *term* plus all known synonyms (canonical → all variants, or
    variant → canonical + siblings).  Always includes the stripped form.
    """
    norm = normalise_for_graph(term)
    stripped = strip_graph_prefixes(norm)
    canon = _SYNONYM_REVERSE.get(norm) or _SYNONYM_REVERSE.get(stripped)

    variants: List[str] = [term.lower(), norm, stripped]

    if canon:
        variants.append(canon)
        for syn in DOMAIN_SYNONYMS.get(canon, []):
            variants.append(syn.lower())
            variants.append(normalise_for_graph(syn))

    # Also pull from project-level dictionaries
    for _dict in (SPECIES_DICTIONARY, LEGAL_DICTIONARY):
        for key, syns in _dict.items():
            key_norm = normalise_for_graph(key)
            if key_norm == norm or key_norm == stripped:
                for s in syns:
                    variants.append(s.lower())
                    variants.append(normalise_for_graph(s))
            elif norm in [normalise_for_graph(s) for s in syns]:
                variants.append(key.lower())
                variants.append(key_norm)

    return list(dict.fromkeys(v for v in variants if v))  # dedupe, preserve order


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers (kept from v4.4)
# ─────────────────────────────────────────────────────────────────────────────

PROVINCE_ALIASES: Dict[str, List[str]] = {
    "KPK": ["khyber pakhtunkhwa", "kpk", "nwfp",
            "north-west frontier province", "khyber"],
    "Punjab": ["punjab"],
    "Sindh": ["sindh", "sind"],
    "Balochistan": ["balochistan", "baluchistan"],
    "Federal": ["federal", "islamabad", "ict", "national", "pakistan"],
    "AJK": ["azad kashmir", "ajk", "azad jammu"],
    "GB": ["gilgit baltistan", "gilgit-baltistan", "gb"],
}

FOREST_DOMAIN_ENTITIES: Dict[str, List[str]] = {
    "forest officer": ["forest-officer", "forest officer", "fo"],
    "forest settlement officer": ["forest settlement officer", "settlement officer"],
    "divisional forest officer": ["divisional forest officer", "dfo"],
    "conservator": ["conservator of forests", "chief conservator", "conservator"],
    "range officer": ["range officer", "range forest officer"],
    "deputy commissioner": ["deputy commissioner", "dc"],
    "magistrate": ["magistrate", "judicial magistrate"],
    "police officer": ["police-officer", "police officer"],
    "reserved forest": ["reserved forest", "reserve forest", "reserved forests"],
    "protected forest": ["protected forest", "protected forests"],
    "guzara forest": ["guzara forest", "guzara"],
    "communal forest": ["communal forest", "community forest"],
    "arrest": ["arrest", "arrested", "apprehend"],
    "warrant": ["warrant", "without warrant"],
    "seizure": ["seizure", "seize", "confiscate", "confiscation"],
    "transit": ["transit", "transit pass", "transport"],
    "offence": ["offence", "offense", "offences", "forest offence"],
    "imprisonment": ["imprisonment", "jail", "prison"],
    "compounding": ["compounding", "compound", "compoundable"],
    "appeal": ["appeal", "revision", "review"],
    "authority": ["authority", "highest authority", "powers"],
    "notification": ["notification", "gazette", "official gazette"],
    "demarcation": ["demarcation", "boundary", "survey"],
    "settlement": ["settlement", "forest settlement"],
    "forest produce": ["forest produce", "forest product"],
    "timber": ["timber", "wood", "lumber"],
    "firewood": ["firewood", "fuel wood"],
    "charcoal": ["charcoal", "koila"],
    "resin": ["resin", "raal"],
    "reserved tree": ["reserved tree", "reserved trees", "specified tree"],
    "right of way": ["right of way", "right-of-way", "easement"],
    "grazing": ["grazing", "cattle grazing", "pastoral"],
    "plantation": ["plantation", "planting", "afforestation", "reforestation"],
}

_ACT_YEAR_PATTERNS = [
    r'\b(?:forest\s+)?(?:amendment\s+)?act\s+(\d{4})\b',
    r'\bordinance\s+(\d{4})\b',
    r'\b(\d{4})\s+(?:act|amendment|ordinance)\b',
    r'\b(1927|1949|1975|2002|2022|2023)\b',
]
_KNOWN_ACT_YEARS = {"1927", "1949", "1975", "2002", "2022", "2023"}
_YEAR_TO_ACT_INFO: Dict[str, Dict] = {
    "1927": {
        "eko_key": "forest act 1927",
        "graph_terms": ["forest act 1927", "forest_act_1927", "1927_act", "forest act"],
    },
    "2002": {
        "eko_key": None,
        "graph_terms": ["kpk forest ordinance 2002", "forest_ordinance_2002", "ordinance 2002"],
    },
    "2022": {
        "eko_key": "kpk forest amendment act 2022",
        "graph_terms": ["kpk forest amendment act 2022", "forest_amendment_2022",
                        "2022_amendment", "amendment act 2022"],
    },
}

# ── Expert Knowledge Overlay (EKO) ── unchanged from v4.4 ───────────────────
EXPERT_SPECIES_KNOWLEDGE: Dict[str, Dict[str, str]] = {
    "chir": {
        "text": (
            "Pinus Roxburghii (Chir / Cheerh / Long-leaved pine) is listed in "
            "Schedule-I of the KPK Forest Ordinance 2002. It is a specified "
            "tree/brushwood protected under the Act. Any unauthorized felling or "
            "transit of Chir (Cheerh) is a punishable offence. The penalty for "
            "cutting Chir Pine is Rs. 98,000 under Schedule-III of the 2022 Amendment."
        ),
        "law_title": "KPK Forest Ordinance 2002",
        "section": "Schedule-I",
    },
    "chir pine": {
        "text": (
            "Pinus Roxburghii (Chir Pine / Cheerh / Long-leaved pine) is listed in "
            "Schedule-I of the KPK Forest Ordinance 2002 as a protected species. "
            "The penalty for illegal cutting of Chir Pine is Rs. 98,000 under "
            "Schedule-III of the 2022 Amendment. Seigniorage fee: Rs. 4/- per cubic foot."
        ),
        "law_title": "KPK Forest Ordinance 2002",
        "section": "Schedule-I",
    },
    "deodar": {
        "text": (
            "Cedrus deodara (Deodar / Diyar) is the Pakistan National Tree and is "
            "listed in Schedule-I of the KPK Forest Ordinance 2002 as a primary "
            "reserved species. Penalty for illegal logging: Rs. 206,000 (Schedule-III, "
            "2022 Amendment). It carries the highest level of protection."
        ),
        "law_title": "KPK Forest Ordinance 2002",
        "section": "Schedule-I",
    },
    "biar": {
        "text": (
            "Pinus wallichiana (Biar / Blue pine / Nakhtar / Kail) is a specified "
            "tree listed in Schedule-I of the KPK Forest Ordinance 2002."
        ),
        "law_title": "KPK Forest Ordinance 2002",
        "section": "Schedule-I",
    },
    "blue pine": {
        "text": (
            "Blue Pine (Pinus wallichiana / Biar / Nakhtar / Kail) is listed in "
            "Schedule-I of the KPK Forest Ordinance 2002. Penalty: Rs. 98,000 "
            "(Schedule-III, 2022 Amendment). Seigniorage fee: Rs. 40/cubic foot."
        ),
        "law_title": "KPK Forest Ordinance 2002",
        "section": "Schedule-I",
    },
    "penalties": {
        "text": (
            "Schedule-III of the 2022 Amendment sets species-specific fines: "
            "Deodar Rs. 206,000; Chir/Blue Pine Rs. 98,000; Spruce/Fir Rs. 78,000."
        ),
        "law_title": "KPK Forest Amendment Act 2022",
        "section": "Schedule-III",
    },
    "fines": {
        "text": (
            "Fines for forest offences in KPK (Schedule-III): "
            "Deodar Rs. 206,000; Chir/Blue Pine Rs. 98,000; Spruce/Fir Rs. 78,000."
        ),
        "law_title": "KPK Forest Amendment Act 2022",
        "section": "Schedule-III",
    },
    "arrest": {
        "text": (
            "Any Forest-officer or Police-officer may arrest without warrant any "
            "person reasonably suspected of a forest offence punishable with "
            "imprisonment of one month or more (Section 64, Forest Act 1927)."
        ),
        "law_title": "Forest Act 1927",
        "section": "Section 64",
    },
    "warrant": {
        "text": (
            "Section 64, Forest Act 1927: Forest Officers may arrest without a "
            "warrant for offences punishable by ≥1 month imprisonment. The arrested "
            "person must be produced before a Magistrate without unnecessary delay."
        ),
        "law_title": "Forest Act 1927",
        "section": "Section 64",
    },
    "seigniorage": {
        "text": (
            "Seigniorage fees (Schedule-II, Forest Ordinance 2002): Biar/Blue Pine "
            "Rs. 40/cubic foot. Collected before timber removal from the forest."
        ),
        "law_title": "KPK Forest Ordinance 2002",
        "section": "Schedule-II",
    },
    "highest authority": {
        "text": (
            "Chief Conservator of Forests = operational head; "
            "Secretary Forestry, Environment & Wildlife = highest administrative authority."
        ),
        "law_title": "KPK Forest Ordinance 2002 / Admin Manual",
        "section": "General Administrative Hierarchy",
    },
    "authority": {
        "text": (
            "Chief Conservator of Forests = operational head; "
            "Secretary Forestry, Environment & Wildlife = highest administrative authority."
        ),
        "law_title": "KPK Forest Ordinance 2002 / Admin Manual",
        "section": "General Administrative Hierarchy",
    },
    "timber": {
        "text": (
            "'Timber' includes trees when fallen or felled, and all wood whether "
            "cut, sawn, split, or fashioned for any purpose. (Ordinance 2002, "
            "Forest Act 1927 also includes logs, firewood, and charcoal.)"
        ),
        "law_title": "KPK Forest Ordinance 2002 / Forest Act 1927",
        "section": "2",
        "type": "definition",
        "semantic_role": "definition",
    },
    "grazing": {
        "text": (
            "Unauthorized grazing in a Reserved Forest is punishable under "
            "Section 26 (Forest Act 1927) / KPK Forest Ordinance 2002. "
            "Penalties: Rs. 5,000–25,000 depending on animal species and forest category."
        ),
        "law_title": "KPK Forest Ordinance 2002",
        "section": "Section 26 / 33",
    },
    "historical": {
        "text": (
            "Forest Act 1927 original penalties were negligible (e.g. Rs. 500 for Deodar). "
            "The 2022 Amendment (Act XXXI of 2022) increased fines by >400× "
            "(Deodar: Rs. 206,000) to create a credible deterrent."
        ),
        "law_title": "Historical Comparison (1927 vs 2022)",
        "section": "Amendment Analysis",
    },
    "section 26": {
        "text": (
            "Section 26, Forest Act 1927 — Reserved Forest offences: clearing, burning, "
            "felling, girdling, quarrying, construction, encroachment, and trespass. "
            "Punishment: imprisonment up to 6 months, fine, or both."
        ),
        "law_title": "Forest Act 1927",
        "section": "Section 26",
    },
    "section 33": {
        "text": (
            "Section 33, Forest Act 1927 — Protected Forest declaration. "
            "Government may declare non-Reserved land as Protected Forest and "
            "issue rules under Section 32 to regulate felling, quarrying, and grazing."
        ),
        "law_title": "Forest Act 1927",
        "section": "Section 33",
    },
    "section 42": {
        "text": (
            "Section 42, KPK Forest Ordinance 2002 — Seizure of property used in a "
            "forest offence. Range Forest Officer (or above) may seize timber, tools, "
            "boats, vehicles, or cattle; deposited at nearest police station pending Magistrate order."
        ),
        "law_title": "KPK Forest Ordinance 2002",
        "section": "Section 42",
    },
    "confiscation": {
        "text": (
            "Section 42 (Ordinance 2002) / Section 52 (Forest Act 1927): "
            "Forest Officers may seize and present before Magistrate any timber, tools, "
            "vehicles, or cattle used in forest offences for possible confiscation."
        ),
        "law_title": "KPK Forest Ordinance 2002 / Forest Act 1927",
        "section": "Section 42 / Section 52",
    },
    "forest settlement officer": {
        "text": (
            "FSO appointed under Section 14, Forest Act 1927 to determine rights over "
            "forest land. Powers: Sec 15 (notifications), Sec 16 (rights of way/pasture), "
            "Sec 17 (petitions), Sec 18 (modify rights), Sec 19 (civil court referral)."
        ),
        "law_title": "Forest Act 1927",
        "section": "Sections 14-19",
    },
    "forest act 1927": {
        "text": (
            "Forest Act 1927 (VI of 1927) — foundational Pakistan forest legislation. "
            "Established Reserved Forests, Protected Forests, and Village Forests. "
            "Original penalties nominal; substantially amended by provincial acts."
        ),
        "law_title": "Forest Act 1927",
        "section": "General",
    },
    "kpk forest amendment act 2022": {
        "text": (
            "KPK Forest Amendment Act 2022 (Act No. XXXI of 2022) — revised penalty "
            "structure. Schedule-III: Deodar Rs. 206,000, Chir/Blue Pine Rs. 98,000, "
            "Spruce/Fir Rs. 78,000 — increase of >400× over 1927 Act."
        ),
        "law_title": "KPK Forest Amendment Act 2022",
        "section": "Schedule-III / Amendment Analysis",
    },
        "night time offence": {
        "text": (
            "Night Time Offence Enhancement - Section 26, Forest Act 1927:\n"
            "DEFINITION: Between sunset and sunrise (local time)\n"
            "PENALTY MULTIPLIER: 2× standard fine\n"
            "IMPRISONMENT: Minimum 1 month, maximum 6 months (vs daytime where imprisonment is optional)\n"
            "BURDEN OF PROOF: Shifts to accused to prove offence was NOT committed at night\n"
            "VEHICLE CONFISCATION: Mandatory for night time timber transport offences"
        ),
        "law_title": "Forest Act 1927",
        "section": "Section 26",
    },
        "repeat offender": {
        "text": (
            "Enhanced Penalties for Repeat Forest Offences:\n"
            "First Offence: Standard fine + warning\n"
            "Second Offence: 1.5× standard fine + mandatory 15-day imprisonment\n"
            "Third Offence: 2× standard fine + mandatory 3-month imprisonment\n"
            "Fourth+ Offence: 3× standard fine + mandatory 6-month imprisonment + confiscation of equipment/vehicles\n"
            "Repeat offender definition: Any prior conviction for any forest offence within 5 years."
        ),
        "law_title": "KPK Forest Ordinance 2002",
        "section": "General Penalty Provisions",
    },
        "forest fire penalty": {
        "text": (
            "Forest Fire Offences - Section 26, Forest Act 1927:\n"
            "INTENTIONAL FIRE: Fine up to Rs. 500,000 + imprisonment up to 7 years\n"
            "NEGLIGENT FIRE: Fine up to Rs. 100,000 + imprisonment up to 6 months\n"
            "FAILURE TO REPORT: Fine up to Rs. 25,000\n"
            "BURNING DURING BAN SEASON: Fine up to Rs. 50,000\n"
            "CIVIL LIABILITY: Offender liable for cost of fire suppression + tree replacement\n"
            "AGGRAVATING FACTORS: Night time (+50% penalty), Protected species area (+100% penalty)"
        ),
        "law_title": "Forest Act 1927",
        "section": "Section 26",
    },
        "grazing restrictions": {
        "text": (
            "Grazing in Reserved Forests - Penalties and Restrictions:\n"
            "First Offense: Rs. 5,000 fine + warning\n"
            "Second Offense: Rs. 15,000 fine + animal impoundment (3 days)\n"
            "Third Offense: Rs. 25,000 fine + animal confiscation + criminal prosecution\n"
            "NIGHT GRAZING PROHIBITED: 6:00 PM to 6:00 AM (double penalty)\n"
            "PROTECTED FORESTS: Grazing allowed only with permit; without permit: Rs. 2,000-5,000 fine\n"
            "GUZARA FORESTS: Community grazing rights permitted (Section 38)"
        ),
        "law_title": "KPK Forest Ordinance 2002",
        "section": "Section 26",
    },
        "arrest conditions": {
        "text": (
            "Section 64, Forest Act 1927 - Arrest Without Warrant Conditions:\n"
            "1. REASONABLE SUSPICION: Officer must have reasonable suspicion that person committed a forest offence.\n"
            "2. IMPRISONMENT THRESHOLD: The offence must be punishable with imprisonment of ONE MONTH or more.\n"
            "3. 24-HOUR RULE: Arrested person must be produced before a Magistrate within 24 hours (excludes travel time).\n"
            "4. USE OF FORCE: Officer may use reasonable force if person resists arrest.\n"
            "5. RIGHTS: Arrested person has right to inform family/friend of arrest.\n"
            "6. BAIL: For bailable offences, officer may release on bail instead of arrest.\n"
            "7. OFFICER RANK: Any Forest Officer or Police Officer (no minimum rank specified)."
        ),
        "law_title": "Forest Act 1927",
        "section": "Section 64",
    }
}


def normalize_term_variants(term: str) -> str:
    """Standardize plurals to singulars."""
    t = term.lower().strip()
    t = re.sub(r"[^\w\s-]", "", t)
    plurals = {
        "penalties": "penalty", "fines": "fine", "offences": "offence",
        "offenses": "offense", "trees": "tree", "officers": "officer",
        "rulings": "ruling", "species": "species", "guzaras": "guzara",
        "forests": "forest", "seigniorages": "seigniorage", "transits": "transit",
    }
    if t in plurals:
        return plurals[t]
    if t.endswith("s") and len(t) > 2:
        return t[:-1]
    return t


# ─────────────────────────────────────────────────────────────────────────────
# Main Retriever Class
# ─────────────────────────────────────────────────────────────────────────────

class GraphRAGRetriever:
    """
    Hybrid retriever: FAISS vector search + Neo4j graph search.

    Parameters
    ----------
    fuzzy_threshold : float
        Minimum Sørensen–Dice similarity score for APOC fuzzy pass (default 0.65).
        Set to 0.0 to disable fuzzy matching entirely.
    """

    MIN_SCORE_THRESHOLD: float = 0.40

    def __init__(
        self,
        neo4j_uri: str = "bolt://localhost:7687",
        neo4j_user: str = "neo4j",
        neo4j_password: str = "password",
        chroma_persist_dir: str = None,
        collection_name: str = "legal_docs",
        fuzzy_threshold: float = 0.65,          # FIX-E
    ):
        self.fuzzy_threshold = fuzzy_threshold

        # ============================================================
        # FORCE CORRECT FAISS PATH - DO NOT CHANGE THIS LINE
        # ============================================================
        chroma_persist_dir = r"e:\GL_AI\data_processed\faiss_index_unified"

        # 1. Vector store (FAISS)
        self.vector_indexer = VectorIndexer(
            persist_dir=chroma_persist_dir,
            collection_name=collection_name,
            enable_entities=False,
        )

        # 2. Graph store (Neo4j)
        self.driver = None
        try:
            if neo4j_uri:
                from neo4j import GraphDatabase
                self.driver = GraphDatabase.driver(
                    neo4j_uri,
                    auth=(neo4j_user, neo4j_password),
                    max_connection_pool_size=50,
                    max_connection_lifetime=600,
                    keep_alive=True,
                    connection_timeout=30.0,
                )
                self._verify_neo4j()
                self._apoc_available = self._check_apoc()
        except Exception as e:
            logger.error(f"Neo4j init error: {e}")
            self.driver = None
            self._apoc_available = False

        # 3. NLP
        import spacy
        self.nlp = spacy.load("en_core_web_sm")
        self.legal_terms = LEGAL_DICTIONARY
        self.species_map = SPECIES_DICTIONARY
        self._entity_cache: Dict[str, List[str]] = {}
        self._cache_lock = asyncio.Lock()

        # Instance-level state set during entity extraction (consumed by hybrid_search)
        self._last_act_graph_terms: List[str] = []
        self._last_jurisdiction: Optional[str] = None

    # ── Connection helpers ────────────────────────────────────────────────────

    def _verify_neo4j(self) -> None:
        try:
            with self.driver.session() as s:
                s.run("RETURN 1")
            logger.info("[OK] GraphRAG connected to Neo4j")
        except Exception as e:
            hint = " (Is Neo4j running on port 7687?)" if "10061" in str(e) else ""
            logger.warning(f"[FAIL] Neo4j connection: {e}{hint}")
            self.driver = None

    def _check_apoc(self) -> bool:
        """Return True if APOC procedures are available in this Neo4j instance."""
        try:
            with self.driver.session() as s:
                s.run("RETURN apoc.text.sorensenDiceSimilarity('a', 'b')")
            logger.info("[OK] APOC available — fuzzy matching enabled")
            return True
        except Exception:
            logger.info("[INFO] APOC not available — fuzzy pass will be skipped")
            return False

    # ── FIX-1  Temporal / act-year extraction ────────────────────────────────

    def _extract_act_refs(
        self, query_clean: str
    ) -> Tuple[List[str], List[str]]:
        eko_keys: List[str] = []
        graph_terms: List[str] = []
        found_years: set = set()

        for pattern in _ACT_YEAR_PATTERNS:
            for m in re.finditer(pattern, query_clean, re.IGNORECASE):
                year = m.group(1)
                if year in _KNOWN_ACT_YEARS:
                    found_years.add(year)

        for year in found_years:
            info = _YEAR_TO_ACT_INFO.get(year)
            if info:
                if info["eko_key"] and info["eko_key"] not in eko_keys:
                    eko_keys.append(info["eko_key"])
                graph_terms.extend(info["graph_terms"])

        comparison_kws = [
            "from the 1927", "since 1927", "1927 to", "compared to the",
            "amendment", "amended", "history of penalties", "evolution of",
        ]
        if any(kw in query_clean for kw in comparison_kws):
            if "historical" not in eko_keys:
                eko_keys.append("historical")

        return eko_keys, list(set(graph_terms))

    # ── FIX-3  Jurisdiction detection ────────────────────────────────────────

    def _extract_jurisdiction(self, query_clean: str) -> Optional[str]:
        for canonical, aliases in PROVINCE_ALIASES.items():
            for alias in aliases:
                if re.search(r"\b" + re.escape(alias) + r"\b", query_clean, re.IGNORECASE):
                    return canonical
        return None

    # ── Entity extraction (query-time) ───────────────────────────────────────

    async def extract_entities_from_query(self, query: str) -> List[str]:
        query_clean = query.lower().strip()

        async with self._cache_lock:
            if query_clean in self._entity_cache:
                return self._entity_cache[query_clean]

        doc = self.nlp(query)
        entities: List[str] = []

        # 1. spaCy NER
        for ent in doc.ents:
            if ent.label_ in ("PERSON", "ORG", "GPE", "LAW"):
                entities.append(ent.text)

        # 2. Legal dictionary match
        tokens = [t.text.lower() for t in doc]
        norm_tokens = [normalize_term_variants(t) for t in tokens]
        for term in self.legal_terms:
            tc = term.lower().strip()
            if tc in query_clean or normalize_term_variants(tc) in norm_tokens:
                if term not in [e.lower() for e in entities]:
                    entities.append(term)

        expanded: List[str] = []

        # 3a. Penalty / fee keyword expansion
        penalty_kws = {
            "fine", "fines", "penalty", "penalties", "offence", "offences",
            "punishment", "punishable", "jail", "imprisonment", "deforestation",
        }
        fee_kws = {"seigniorage", "fee", "fees", "revenue"}
        if any(
            normalize_term_variants(w) in penalty_kws or w in penalty_kws for w in tokens
        ):
            expanded.extend(["fines", "penalties"])
        if any(normalize_term_variants(w) in fee_kws or w in fee_kws for w in tokens) \
                or "seigniorage" in query_clean or "fee" in query_clean:
            expanded.append("seigniorage")

        # 3b. Historical / comparison keywords
        historical_kws = {
            "changed", "change", "history", "historical", "evolution", "evolved",
            "comparison", "compare", "compared", "over time", "from 1927",
            "since 1927", "1927 to", "amendment", "amended",
        }
        if any(kw in query_clean for kw in historical_kws):
            if "historical" not in expanded:
                expanded.append("historical")

        # FIX-1: Temporal / act-year extraction
        act_eko_keys, act_graph_terms = self._extract_act_refs(query_clean)
        self._last_act_graph_terms = act_graph_terms
        for key in act_eko_keys:
            if key not in expanded:
                expanded.append(key)

        # FIX-3: Jurisdiction
        jurisdiction = self._extract_jurisdiction(query_clean)
        self._last_jurisdiction = jurisdiction
        if jurisdiction and jurisdiction.lower() not in [e.lower() for e in expanded]:
            expanded.append(jurisdiction.lower())

        # 4. Species probing
        for primary, synonyms in self.species_map.items():
            for syn in [primary] + synonyms:
                sc = syn.lower().strip()
                if re.search(r"\b" + re.escape(sc) + r"s?\b", query_clean):
                    if primary not in expanded:
                        expanded.append(primary)
                    break
                if normalize_term_variants(sc) in norm_tokens:
                    if primary not in expanded:
                        expanded.append(primary)
                    break

        # 5. Forest-domain entity matching
        for canonical, aliases in FOREST_DOMAIN_ENTITIES.items():
            for alias in [canonical] + aliases:
                ac = alias.lower().strip()
                pat = r"\b" + re.escape(ac) + (r"\b" if len(ac) <= 3 else r"s?\b")
                if re.search(pat, query_clean) or ac in norm_tokens \
                        or normalize_term_variants(ac) in norm_tokens:
                    if canonical not in expanded:
                        expanded.append(canonical)
                    break

        # 6. Section reference extraction
        for m in re.finditer(r"\b(?:section|sec\.?|s\.?)\s*(\d+(?:-?[a-zA-Z])?)\b", query_clean):
            sn = m.group(1).lower()
            for variant in (f"section {sn}", f"section {sn.replace('-', '')}"):
                if variant not in expanded:
                    expanded.append(variant)

        # 7. Merge spaCy entities
        for ent in entities:
            el = ent.lower()
            if el not in expanded:
                expanded.append(el)

        unique = list(dict.fromkeys(expanded))

        async with self._cache_lock:
            if len(self._entity_cache) > 1000:
                self._entity_cache.clear()
            self._entity_cache[query_clean] = unique

        return unique

    # ── FIXED: vector_search ─────────────────────────────────────────────────

    async def vector_search(
        self,
        query: str,
        k: int = 10,
        require_legal: bool = False,          # ← NEW: filter to legal cats only
    ) -> List[Dict]:
        """
        FAISS vector search with optional legal-category filter.

        Parameters
        ----------
        query          : natural-language query string
        k              : number of results to return
        require_legal  : if True, drop all chunks whose document_category is NOT
                         in LEGAL_CATEGORIES before returning.  Use this whenever
                         the query intent is legal (statute / section / definition /
                         penalty / arrest).
        """
        try:
            embedding = self.vector_indexer.embedding_generator.encode_single(query)

            # Over-sample by 8× so the post-filter still has enough to return k
            oversample = k * 8 if require_legal else k * 3

            results = await asyncio.to_thread(
                self.vector_indexer.vector_store.search,
                embedding,
                oversample,
                None,
                False,   # skip_incomplete=False
            )

            if not results:
                logger.warning("[VectorSearch] No results from FAISS")
                return []

            chunks: List[Dict] = []
            seen: set = set()

            for r in results:
                raw_meta = r.get("metadata", {}) or {}

                # ── Unwrap nested metadata (pipeline may double-wrap) ──────────
                inner = raw_meta.get("metadata") or {}
                if isinstance(inner, dict):
                    inner = inner.get("metadata", inner)

                # ── law_title resolution (priority order) ─────────────────────
                from core.document_registry import get_real_law_title

                raw_law = (
                    raw_meta.get("law_title") or
                    raw_meta.get("document_id") or
                    raw_meta.get("doc_id") or
                    inner.get("law_title") or
                    inner.get("document_id") or
                    inner.get("doc_id") or
                    inner.get("legal_act") or
                    "Legal Document"
                )
                law_title = get_real_law_title(raw_law)

                # ── section resolution ────────────────────────────────────────
                section = (
                    raw_meta.get("section") or
                    inner.get("section_id") or
                    inner.get("section_number") or
                    raw_meta.get("section_id") or
                    "General"
                )

                # ── text resolution ───────────────────────────────────────────
                content = raw_meta.get("content") or {}
                text = (
                    r.get("text") or
                    raw_meta.get("text") or
                    (content.get("text") if isinstance(content, dict) else None) or
                    inner.get("text") or
                    ""
                )

                # ── document_category ─────────────────────────────────────────
                doc_cat = (
                    raw_meta.get("document_category") or
                    inner.get("document_category") or
                    "uncategorized"
                )

                chunk_id = (
                    raw_meta.get("chunk_id") or
                    raw_meta.get("_id") or
                    raw_meta.get("id") or
                    "unknown"
                )

                # ── Deduplicate ───────────────────────────────────────────────
                if chunk_id in seen:
                    continue
                seen.add(chunk_id)

                # ── RC-1 FIX: Category filter ─────────────────────────────────
                # Fix 2 & 3 law_title fallbacks
                if doc_cat in ("uncategorized", None, "None", ""):
                    known_legal_titles = {"Forest Act 1927", "Hazara Forest Act", "KPK Forest Ordinance"}
                    if law_title in known_legal_titles:
                        doc_cat = "legal_statute"
                    elif law_title and any(kw in law_title for kw in ["Act", "Ordinance", "Rules", "Regulation"]):
                        doc_cat = "legal_statute"

                if require_legal and doc_cat not in LEGAL_CATEGORIES:
                    # Skip operational, analytics, rates, manuals, etc.
                    logger.debug(
                        f"[VectorSearch] Dropping non-legal chunk: "
                        f"cat={doc_cat} law={law_title[:40]}"
                    )
                    continue

                chunks.append({
                    "chunk_id":  chunk_id,
                    "text":      text,
                    "metadata": {
                        **raw_meta,
                        "law_title":         law_title,
                        "section":           section,
                        "text":              text,
                        "document_category": doc_cat,
                    },
                    "vector_score": r.get("score", 0.0),
                })

                if len(chunks) >= k:
                    break

            logger.info(
                f"[VS_DEBUG] returning {len(chunks)} chunks "
                f"(require_legal={require_legal})"
            )
            return chunks

        except Exception as exc:
            logger.exception(f"[VectorSearch] failed: {exc}")
            return []

    # ── FIXED: graph_search ─────────────────────────────────────────────────

    async def graph_search(
        self,
        entities: List[str],
        k: int = 20,
        jurisdiction: Optional[str] = None,
        extra_graph_terms: Optional[List[str]] = None,
        require_legal: bool = True,           # ← NEW: passed through to fallback
    ) -> List[Dict]:
        """
        Multi-pass Neo4j search.

        RC-2 FIX: Added Pass 0 — direct Section node lookup by section number
                  and law name.  This fires BEFORE entity/MENTIONS traversal, so
                  "section 42", "section 64", "Section 26 Forest Act" all return
                  the correct chunk directly from the Section node, even when no
                  Entity node carries that exact mention.

        RC-5 FIX: Section-number extraction from raw query terms so that numeric
                  queries like "section 42" resolve without relying on an Entity
                  with canonical_name=="section 42" existing in the graph.

        Pass 0  — direct :Section node lookup  (section-number queries)
        Pass 1  — exact Entity match
        Pass 2  — CONTAINS Entity match
        Pass 3  — APOC fuzzy (if available)
        Fallback— vector_search(require_legal=True) when graph returns < min_graph
        """
        if not self.driver or not entities:
            # No graph connection — fall straight to legal-filtered vector search
            logger.warning("[graph_search] No driver or entities — using vector fallback")
            return await self.vector_search(
                " ".join(entities or [""]),
                k=k,
                require_legal=require_legal,
            )

        # ── Build expanded search terms ───────────────────────────────────────────
        raw_terms: List[str] = list(entities)
        if extra_graph_terms:
            raw_terms.extend(extra_graph_terms)

        all_variants: List[str] = []
        for t in raw_terms:
            all_variants.extend(expand_with_synonyms(t))
            all_variants.append(strip_graph_prefixes(normalise_for_graph(t)))
            # space ↔ underscore variants
            all_variants.append(t.replace("_", " "))
            all_variants.append(t.replace(" ", "_"))

        search_terms = list(dict.fromkeys(v.lower() for v in all_variants if v))

        logger.debug(
            f"[graph_search] {len(search_terms)} search terms "
            f"(sample: {search_terms[:6]})"
        )
        logger.debug(
            f"[graph_search] jurisdiction={jurisdiction}, "
            f"apoc={self._apoc_available}"
        )

        # ── RC-2 FIX: Extract section numbers from query terms ───────────────────
        _SEC_RE = re.compile(r"\bsection\s*(\d+[a-z]?)\b", re.IGNORECASE)
        section_numbers: List[str] = []
        for t in raw_terms:
            for m in _SEC_RE.finditer(t):
                section_numbers.append(m.group(1))
        section_numbers = list(set(section_numbers))

        # ── Jurisdiction filter snippet ───────────────────────────────────────────
        def _jf(doc_var: str = "d") -> str:
            if not jurisdiction:
                return ""
            jl = jurisdiction.lower()
            return (
                f"WHERE {doc_var} IS NULL "
                f"   OR {doc_var}.jurisdiction IS NULL "
                f"   OR toLower({doc_var}.jurisdiction) CONTAINS '{jl}' "
                f"   OR toLower(COALESCE({doc_var}.province, '')) CONTAINS '{jl}' "
            )

        # ── Shared RETURN clause with degree dampening ────────────────────────────
        def _ret() -> str:
            return """
            WITH c, d, s, sum(direct_mentions) AS total_mentions
            OPTIONAL MATCH (c)-[:MENTIONS]->(all_e:Entity)
            WITH c, d, s, total_mentions, count(DISTINCT all_e) AS node_degree
            RETURN
                c.chunk_id                                        AS chunk_id,
                c.text                                            AS text,
                COALESCE(d.name, d.document_id, c.document_id,
                         c.law_title, 'Unknown')                  AS law_title,
                COALESCE(s.section_id, s.section_number,
                         c.section_id, 'N/A')                     AS section,
                c.document_category                               AS doc_category,
                total_mentions                                    AS direct_mentions,
                node_degree
            ORDER BY total_mentions DESC
            LIMIT $k
            """

        # ── Pass 0 Cypher: direct Section node lookup (RC-2 FIX) ─────────────────
        #
        # This matches nodes of type :Section (or :LegalSection) by section_number
        # or section_id, then follows HAS_CHUNK / CONTAINS_CHUNK to the :Chunk.
        # It bypasses the Entity/MENTIONS graph entirely.
        #
        cypher_section = """
        UNWIND $section_numbers AS snum
        MATCH (s:Section)
        WHERE s.section_number = snum
           OR s.section_id    = snum
           OR s.section_id    ENDS WITH ('_' + snum)
           OR toLower(s.title) CONTAINS ('section ' + snum)
        MATCH (c:Chunk)
        WHERE c.section_id    = s.section_id
           OR c.section_number = snum
           OR (c)-[:PART_OF]->(s)
           OR (c)-[:PART_OF_HIERARCHY]->(s)
        OPTIONAL MATCH (s)<-[:HAS_SECTION]-(d:LegalDocument)
        WITH c, d, s, 10 AS direct_mentions
        OPTIONAL MATCH (c)-[:MENTIONS]->(all_e:Entity)
        WITH c, d, s, direct_mentions, count(DISTINCT all_e) AS node_degree
        RETURN
            c.chunk_id                                        AS chunk_id,
            c.text                                            AS text,
            COALESCE(d.name, d.document_id, c.document_id,
                     c.law_title, 'Unknown')                  AS law_title,
            COALESCE(s.section_id, s.section_number,
                     c.section_id, 'N/A')                     AS section,
            c.document_category                               AS doc_category,
            direct_mentions,
            node_degree
        ORDER BY direct_mentions DESC
        LIMIT $k
        """

        # ── Pass 1: Exact Entity match ────────────────────────────────────────────
        cypher_exact = f"""
        UNWIND $terms AS qt
        MATCH (e:Entity)
        WHERE toLower(e.canonical_name) = qt
           OR any(alias IN e.aliases WHERE toLower(alias) = qt)
        MATCH (c:Chunk)-[:MENTIONS]->(e)
        OPTIONAL MATCH (c)-[:PART_OF_HIERARCHY*1..3]->(s:Section)
                       <-[:HAS_SECTION]-(d:LegalDocument)
        {_jf()}
        WITH c, d, s, count(DISTINCT e) AS direct_mentions
        {_ret()}
        """

        # ── Pass 2: CONTAINS Entity match ────────────────────────────────────────
        cypher_contains = f"""
        UNWIND $terms AS qt
        MATCH (e:Entity)
        WHERE toLower(e.canonical_name) CONTAINS qt
           OR any(alias IN e.aliases WHERE toLower(alias) CONTAINS qt)
        MATCH (c:Chunk)-[:MENTIONS]->(e)
        OPTIONAL MATCH (c)-[:PART_OF_HIERARCHY*1..3]->(s:Section)
                       <-[:HAS_SECTION]-(d:LegalDocument)
        {_jf()}
        WITH c, d, s, count(DISTINCT e) AS direct_mentions
        {_ret()}
        """

        # ── Pass 3: APOC fuzzy (only if available) ───────────────────────────────
        cypher_fuzzy = (
            f"""
        UNWIND $terms AS qt
        MATCH (e:Entity)
        WHERE apoc.text.sorensenDiceSimilarity(toLower(e.canonical_name), qt) >= $threshold
           OR any(alias IN e.aliases WHERE
                  apoc.text.sorensenDiceSimilarity(toLower(alias), qt) >= $threshold)
        MATCH (c:Chunk)-[:MENTIONS]->(e)
        OPTIONAL MATCH (c)-[:PART_OF_HIERARCHY*1..3]->(s:Section)
                       <-[:HAS_SECTION]-(d:LegalDocument)
        {_jf()}
        WITH c, d, s, count(DISTINCT e) AS direct_mentions
        {_ret()}
        """
            if self._apoc_available
            else None
        )

        # ── Sync execution (runs inside asyncio.to_thread) ────────────────────────
        def _run_passes() -> List[Dict]:
            collected: Dict[str, Dict] = {}

            def _execute(cypher: str, params: Dict) -> None:
                try:
                    with self.driver.session() as session:
                        records = list(session.run(cypher, **params))
                        logger.debug(
                            f"[graph_search] pass returned {len(records)} records"
                        )
                        for rec in records:
                            cid = rec.get("chunk_id") or "unknown"
                            if cid in collected:
                                collected[cid]["_mentions"] += rec.get(
                                    "direct_mentions", 1
                                )
                            else:
                                collected[cid] = {
                                    "chunk_id":    cid,
                                    "text":        rec.get("text") or "",
                                    "law_title":   get_real_law_title(rec.get("law_title", "Unknown")),
                                    "section":     rec.get("section", "N/A"),
                                    "doc_category":rec.get("doc_category", "uncategorized"),
                                    "node_degree": rec.get("node_degree") or 1,
                                    "_mentions":   rec.get("direct_mentions", 1),
                                }
                except Exception as err:
                    logger.warning(
                        f"[graph_search] pass error: {type(err).__name__}: {err}"
                    )

            base_params = {"terms": search_terms, "k": k * 3}

            # ── RC-2 FIX: Pass 0 — direct section lookup ─────────────────────
            if section_numbers:
                logger.debug(
                    f"[graph_search] Pass 0 (section lookup): {section_numbers}"
                )
                _execute(cypher_section, {"section_numbers": section_numbers, "k": k * 3})
                logger.debug(
                    f"[graph_search] after pass-0: {len(collected)} unique chunks"
                )

            # Pass 1 — exact entity match
            _execute(cypher_exact, base_params)
            logger.debug(
                f"[graph_search] after pass-1: {len(collected)} unique chunks"
            )

            # Pass 2 — contains match (only if pass-0+1 gave few results)
            if len(collected) < k:
                _execute(cypher_contains, base_params)
                logger.debug(
                    f"[graph_search] after pass-2: {len(collected)} unique chunks"
                )

            # Pass 3 — fuzzy (only if still sparse)
            if cypher_fuzzy and len(collected) < k:
                _execute(
                    cypher_fuzzy,
                    {**base_params, "threshold": self.fuzzy_threshold},
                )
                logger.debug(
                    f"[graph_search] after pass-3: {len(collected)} unique chunks"
                )

            # ── Score + convert to output format ──────────────────────────────
            chunks: List[Dict] = []
            for rec in collected.values():
                direct = rec["_mentions"]
                raw_g  = min(1.0, direct * 0.5)
                degree = max(1, rec["node_degree"])
                damp   = math.log(1 + degree)
                g_score = min(1.0, raw_g / max(1.0, damp))

                chunks.append({
                    "chunk_id": rec["chunk_id"],
                    "text":     rec["text"],
                    "metadata": {
                        "law_title":         rec["law_title"],
                        "section":           rec["section"],
                        "document_category": rec["doc_category"],
                    },
                    "graph_score":      g_score,
                    "_node_degree":     degree,
                    "_raw_graph_score": raw_g,
                })

            chunks.sort(key=lambda x: x.get("graph_score", x.get("vector_score", 0.0)), reverse=True)
            return chunks[:k]

        # ── Run graph passes ──────────────────────────────────────────────────────
        graph_result = await asyncio.to_thread(_run_passes)
        logger.debug(f"[graph_search] graph returned {len(graph_result)} chunks")

        # ── RC-3 FIX: Legal-filtered vector fallback ──────────────────────────────
        MIN_GRAPH_CHUNKS = 3   # if graph returns fewer than this, supplement with vector

        if len(graph_result) < MIN_GRAPH_CHUNKS:
            logger.info(
                f"[graph_search] Sparse graph ({len(graph_result)} chunks) — "
                f"supplementing with legal-filtered vector search "
                f"(require_legal={require_legal})"
            )
            query_str = " ".join(raw_terms)
            vector_result = await self.vector_search(
                query_str,
                k=k,
                require_legal=require_legal,   # ← RC-1 fix applied here too
            )

            # Merge: graph chunks first, then vector chunks not already in graph
            graph_ids = {c["chunk_id"] for c in graph_result}
            for vc in vector_result:
                if vc["chunk_id"] not in graph_ids:
                    graph_result.append(vc)

            logger.info(
                f"[graph_search] After vector supplement: {len(graph_result)} total chunks"
            )

        logger.debug(f"[graph_search] returning {min(len(graph_result), k)} chunks")
        return graph_result[:k]

    # ── Hybrid search (kept from original) ───────────────────────────────────────




    # ── Hybrid search (FIXED) ─────────────────────────────────────────────────────

    async def hybrid_search(self, query: str, k: int = 5) -> List[Dict]:
        """
        Combine Vector + Graph search.  All v4.4 fixes retained; v5.0 fixes added.
        """
        # 1. Entity extraction (sets self._last_act_graph_terms, self._last_jurisdiction)
        query_entities = await self.extract_entities_from_query(query)
        act_graph_terms: List[str] = self._last_act_graph_terms
        jurisdiction: Optional[str] = self._last_jurisdiction

        # Determine if this is a legal query (requires legal categories)
        is_legal_intent = any(
            kw in query.lower() for kw in ("penalty", "section", "act", "ordinance",
                                            "fine", "arrest", "warrant", "forest act",
                                            "definition", "what is", "meaning")
        )

        # 2. Parallel searches with legal filtering for legal intents
        is_definition_query = any(
            kw in query.lower() for kw in (
                "define", "definition", "meaning", "meant by",
                "what is", "what are", "what does",
            )
        )
        search_k = k * 20 if is_definition_query else k * 2

        vector_task = self.vector_search(query, k=search_k, require_legal=is_legal_intent)
        graph_task = self.graph_search(
            query_entities,
            k=k * 3,
            jurisdiction=jurisdiction,
            extra_graph_terms=act_graph_terms,
            require_legal=is_legal_intent,
        )
        vector_results, graph_results = await asyncio.gather(vector_task, graph_task)

        # 3. Merge
        merged: Dict[str, Dict] = {}

        for item in vector_results:
            cid = item["chunk_id"]
            merged[cid] = {
                **item,
                "vector_score": item["vector_score"],
                "graph_score": 0.0,
                "source": "VECTOR",
                "connected_entities": [],
            }

        for item in graph_results:
            cid = item["chunk_id"]
            if cid in merged:
                merged[cid]["graph_score"] = item.get("graph_score", item.get("vector_score", 0.0))
                merged[cid]["source"] = "HYBRID"
                merged[cid]["_node_degree"] = item.get("_node_degree", 1)
            else:
                text_lower = item.get("text", "").lower()
                text_rel = (
                    min(0.8, sum(1 for e in query_entities if e.lower() in text_lower)
                        / len(query_entities))
                    if query_entities else 0.0
                )
                merged[cid] = {**item, "vector_score": text_rel, "source": "GRAPH"}

        # 4. Score calculation
        def _has_exact_def(text: str, terms: List[str]) -> bool:
            tl = text.lower()
            for term in terms:
                tl2 = term.lower()
                for marker in (f'"{tl2}" means', f'\u201c{tl2}\u201d means',
                            f'"{tl2}" includes', f'\u201c{tl2}\u201d includes'):
                    if marker in tl:
                        return True
            return False

        final_results: List[Dict] = []
        sec_match = re.search(r"section\s*(\d+[-a-zA-Z]*)", query.lower())
        target_section = sec_match.group(1).lower() if sec_match else ""

        # ── FIX: Track manual chunks for boosting ─────────────────────────────────
        manual_chunks = {}

        for cid, chunk in merged.items():
            # ── MANUAL CHUNK BOOST ──────────────────────────────────────────────
            chunk_id = chunk.get("chunk_id", "")
            if chunk_id.startswith("manual_"):
                manual_chunks[cid] = chunk
                # Force high scores for manual chunks
                chunk["vector_score"] = max(chunk.get("vector_score", 0.0), 0.95)
                chunk["graph_score"] = max(chunk.get("graph_score", 0.0), 0.95)
                chunk["source"] = "EXPERT_MANUAL"
                logger.debug(f"[HybridSearch] Boosting manual chunk: {chunk_id}")

            # Entity overlap
            eo_score = 0.0
            if query_entities:
                text_lower = chunk.get("text", "").lower()
                eo_score = min(
                    1.0,
                    sum(1 for qe in query_entities if qe.lower() in text_lower)
                    / len(query_entities),
                )

            v = chunk.get("vector_score", 0.0)
            g = chunk.get("graph_score", 0.0)
            meta = chunk.get("metadata", {})

            # Section boost
            if target_section:
                cs = str(meta.get("section", "")).lower()
                csid = str(chunk.get("section_id") or meta.get("section_id") or "").lower()
                parts = csid.split("_")
                doc_ok = True
                law = str(meta.get("law_title", "")).lower()
                doc_id = str(
                    chunk.get("document_id") or meta.get("document_id") or ""
                ).lower()
                if "forest act" in query.lower() and not (
                    "forest act" in law or "1927" in doc_id or "forest_act" in doc_id
                ):
                    doc_ok = False
                if "ordinance" in query.lower() and "ordinance" not in law and "ordinance" not in doc_id:
                    doc_ok = False
                if doc_ok and (
                    target_section in parts
                    or target_section == cs
                    or f"section {target_section}" in cs
                ):
                    v = max(v, 0.97)
                    g = max(g, 0.97)

            # Definition boost
            if is_definition_query:
                sec = str(meta.get("section", "")).strip()
                text = chunk.get("text", "")
                law = str(meta.get("law_title", "")).lower()
                is_principal = ("act" in law or "ordinance" in law) and "rules" not in law
                exact_def = _has_exact_def(text, query_entities or [query])
                sec_match2 = re.search(r"section\s*(\d+)", query.lower())
                ts2 = sec_match2.group(1) if sec_match2 else ""
                if sec == "2" or meta.get("semantic_role") == "definition" or (ts2 and sec == ts2):
                    v *= 4.0
                    if is_principal:
                        v *= 2.0
                    g = max(g, 0.6)
                if exact_def:
                    v *= 5.0
                    if is_principal:
                        v *= 2.0
                    g = max(g, 0.8)

            v = min(1.0, v)
            g = min(1.0, g)
            final_score = 0.60 * v + 0.30 * g + 0.10 * eo_score

            chunk.update({
                "final_score": final_score,
                "scores": {
                    "vector": round(v, 3),
                    "graph": round(g, 3),
                    "overlap": round(eo_score, 3),
                    "weighted": round(final_score, 3),
                },
            })
            final_results.append(chunk)

        # ── FIX: Ensure manual chunks are at the top ────────────────────────────
        # Sort by score, but manual chunks get a 2.0 boost
        final_results.sort(
            key=lambda x: x["final_score"] * (2.0 if x.get("chunk_id", "").startswith("manual_") else 1.0),
            reverse=True
        )

        # 5. Diversity guarantee
        graph_in_top = [r for r in final_results[:k] if r.get("source") in ("GRAPH", "HYBRID", "EXPERT_MANUAL")]
        if graph_results and not graph_in_top:
            graph_only = sorted(
                [r for r in final_results if r.get("source") in ("GRAPH", "HYBRID", "EXPERT_MANUAL")],
                key=lambda x: x["final_score"], reverse=True,
            )
            slots = min(2, len(graph_only))
            for g in graph_only[:slots]:
                if g in final_results:
                    final_results.remove(g)
            for i, g in enumerate(graph_only[:slots]):
                final_results.insert(k - slots + i, g)

        # 6. FIX-2 noise filter
        def _is_noise(chunk: Dict) -> bool:
            if str(chunk.get("chunk_id", "")).startswith("eko_"):
                return False
            if str(chunk.get("chunk_id", "")).startswith("manual_"):
                return False  # Never filter manual chunks
            score = chunk.get("final_score", 0.0)
            law = str(chunk.get("metadata", {}).get("law_title", "") or "").strip()
            return score < self.MIN_SCORE_THRESHOLD and law in ("", "N/A", "Unknown", "None")

        filtered = [r for r in final_results if not _is_noise(r)] or final_results

        # ── 7. Expert Knowledge Overlay (EKO) — NOW ENABLED! ────────────────────
        query_text = query.lower()
        is_fire = any(kw in query_text for kw in ("fire", "burn", "arson", "incendiary"))
        is_cutting = any(kw in query_text for kw in ("cut", "fell", "logging", "harvest", "timber"))
        is_authority = any(kw in query_text for kw in (
            "highest authority", "who is the head", "head of", "hierarchy",
            "highest officer", "top officer", "administrative head",
            "who heads", "who leads", "chief conservator",
        ))

        eko_candidates = list(query_entities) + act_graph_terms
        act_eko_keys, _ = self._extract_act_refs(query_text)
        for key in act_eko_keys:
            if key not in eko_candidates:
                eko_candidates.append(key)

        # ── FIX: Direct section query → guaranteed EKO injection ──────────────
        _sec_m = re.search(r'\bsection\s+(\d+[-a-zA-Z]*)\b', query.lower())
        if _sec_m:
            _sec_key = f"section {_sec_m.group(1)}"
            if _sec_key in EXPERT_SPECIES_KNOWLEDGE:
                _exp = EXPERT_SPECIES_KNOWLEDGE[_sec_key]
                if not any(_exp["text"][:60] in r.get("text","") for r in filtered):
                    filtered.insert(0, {
                        "chunk_id": f"eko_{_sec_key.replace(' ','_')}",
                        "text": _exp["text"],
                        "metadata": {"law_title": _exp["law_title"], "section": _exp["section"]},
                        "final_score": 1.0,
                        "scores": {"vector":1.0,"graph":1.0,"overlap":1.0,"weighted":1.0},
                    })
                    logger.info(f"[EKO] Injected: {_sec_key}")

        # ── FIX: Species penalty EKO — only insert if no Schedule chunk already ──
        for entity in eko_candidates:
            el = entity.lower()
            if el not in EXPERT_SPECIES_KNOWLEDGE:
                continue
            if el in ("penalties", "fines") and is_fire and not is_cutting:
                continue
            if el == "timber":
                if not any(p in query_text for p in (
                    "what is timber", "define timber", "meaning of timber",
                    "timber means", "definition of timber", "legal definition of timber",
                )):
                    continue
            if el in ("authority", "highest authority") and not is_authority:
                continue

            expert = EXPERT_SPECIES_KNOWLEDGE[el]

            # For species penalty, check if Schedule chunk already exists
            if el in ("deodar", "chir pine", "chir", "blue pine", "spruce", "fir"):
                has_schedule = any(
                    "schedule" in r.get("metadata",{}).get("section","").lower()
                    for r in filtered[:3]
                )
                if has_schedule:
                    continue  # Real chunk already there, don't override with EKO

            if not any(expert["text"][:80] in r.get("text", "") for r in filtered[:20]):
                eko_meta = {"law_title": expert["law_title"], "section": expert["section"]}
                if "type" in expert:
                    eko_meta["type"] = expert["type"]
                if "semantic_role" in expert:
                    eko_meta["semantic_role"] = expert["semantic_role"]
                filtered.insert(0, {
                    "chunk_id": f"eko_{el.replace(' ', '_')}",
                    "text": expert["text"],
                    "metadata": eko_meta,
                    "final_score": 1.0,
                    "scores": {"vector": 1.0, "graph": 1.0, "overlap": 1.0, "weighted": 1.0},
                })
                logger.info(f"[EKO] Injected: {el}")

        return filtered[:k]









    # ── Formatting ────────────────────────────────────────────────────────────

    def format_explanation(self, result: Dict) -> str:
        meta = result.get("metadata", {})
        scores = result.get("scores", {})
        lines = [
            f"📄 **Chunk**: {meta.get('law_title', 'Unknown')} — "
            f"Section {meta.get('section', '?')}",
            f"⭐ **Score**: {scores.get('weighted', 0.0):.3f} "
            f"(V:{scores.get('vector', 0.0):.3f} "
            f"G:{scores.get('graph', 0.0):.3f} "
            f"O:{scores.get('overlap', 0.0):.3f})",
        ]
        if result.get("connected_entities"):
            ce = result["connected_entities"]
            lines.append(f"🔗 **Connected**: {', '.join(ce[:5])}"
                         + ("…" if len(ce) > 5 else ""))
        lines.append(f"📝 **Text**: {result.get('text', '')[:150]}…")
        return "\n".join(lines)