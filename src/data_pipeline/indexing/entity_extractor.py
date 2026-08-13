"""
Entity Extractor — Production-Grade Legal Document Entity Recognition
Includes post-filtering, canonicalization, fuzzy disambiguation, and provenance tracking.

FIXES vs v2.1
─────────────
  [FIX-1]  CANONICAL NAME CLEANING
            strip_entity_prefixes() removes measurement/botanical/article prefixes
            (dbh_1_, the_province_of_, cedrus_, pinus_, standing_, etc.) from any
            entity name BEFORE it is stored in Neo4j.  This is the write-time
            counterpart of FIX-A in graph_rag_retriever v5.0 (read-time stripping).

  [FIX-2]  ALIAS LIST WRITTEN TO NEO4J
            EntityRegistry.register_entity() now accumulates ALL surface forms seen
            for a canonical entity into prov["aliases"].  get_entity_info() exports
            this as the 'aliases' array that graph_rag_retriever.py's Cypher queries
            (both CONTAINS and exact passes) rely on.

  [FIX-3]  CROSS-DOMAIN SYNONYM DICTIONARIES
            SPECIES_DICTIONARY    — Forest species (unchanged from v2.1)
            LEGAL_DICTIONARY      — now a Dict[str, List[str]] of canonical→synonyms
                                    covering Forest, Climate, Judiciary, and Permits.
            DOMAIN_ENTITY_ALIASES — flat reverse lookup built automatically so
                                    extract_entities() can expand any synonym to its
                                    canonical form at extraction time.

  [FIX-4]  STRONGER auto_canonicalize()
            • Strips all known noisy prefixes/suffixes before forming the slug.
            • Collapses botanical binomials: "cedrus_deodara" → "deodar" via alias map.
            • Normalises unicode (NFKD) so diacritics never create duplicate keys.

  [FIX-5]  CONFIDENCE SCORING FOR LEGAL_REF (retained FIX-B from v2.1)
            LEGAL_REF type scores 4 pts; single-mention section refs pass threshold=6.

  [FIX-6]  UNICODE QUOTE NORMALISATION (retained FIX-C from v2.1)
            extract_defined_terms() handles "", \u201c\u201d, \u2018\u2019.

  [FIX-7]  JURISDICTION ENRICHMENT (retained FIX-A from v2.1)
            detect_jurisdiction() + extract_from_chunk() write 'jurisdiction' to metadata.

  [FIX-8]  JSON SERIALISATION (retained FIX-F from v2.1)
            EntityRegistry.get_entity_info() converts sets → lists before export.

  [FIX-9]  CONVENIENCE PIPELINE (retained FIX-E from v2.1)
            extract_and_filter_chunks() runs both stages in one call.
"""

from __future__ import annotations

import re
import subprocess
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Set, Tuple

import spacy
from spacy.matcher import Matcher


# ═════════════════════════════════════════════════════════════════════════════
# FIX-1  ── Write-time prefix / suffix stripping
# ═════════════════════════════════════════════════════════════════════════════

# Prefixes that appear on stored entity tokens but carry no semantic value.
# Longer prefixes must come before shorter ones (greedy left-match).
_STRIP_PREFIXES: Tuple[str, ...] = (
    "the_province_of_",
    "province_of_",
    "the_district_of_",
    "district_of_",
    "the_",             # "the_forest_act" → "forest_act"
    "cedrus_",          # botanical genus
    "pinus_",
    "quercus_",
    "abies_",
    "picea_",
    "juglans_",
    "fraxinus_",
    "platanus_",
    "morus_",
    "populus_",
    "standing_",        # measurement context  e.g. "standing_deodar"
    "dbh_1_",
    "dbh_2_",
    "dbh_3_",
    "dbh_",
    "avg_",
    "total_",
    "no_of_",
)

_STRIP_SUFFIXES: Tuple[str, ...] = (
    "_tree",
    "_trees",
    "_species",
    "_timber",
    "_wood",
    "_forest",          # "reserved_forest_forest" guard
)

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _strip_prefixes_suffixes(slug: str) -> str:
    """
    Iteratively remove known noisy prefixes and suffixes from a lowercase slug.

    "dbh_1_deodar"             → "deodar"
    "the_province_of_punjab"   → "punjab"
    "cedrus_deodara"           → "deodara"   (alias map handles the rest)
    "standing_deodar"          → "deodar"
    "pinus_roxburghii"         → "roxburghii" (alias map maps → "chir pine")
    """
    changed = True
    while changed:
        changed = False
        for pfx in _STRIP_PREFIXES:
            if slug.startswith(pfx):
                slug = slug[len(pfx):]
                changed = True
                break
        for sfx in _STRIP_SUFFIXES:
            if slug.endswith(sfx) and len(slug) > len(sfx):
                slug = slug[: -len(sfx)]
                changed = True
                break
    return slug


def _unicode_slug(text: str) -> str:
    """
    Lowercase, unicode-normalise (NFKD), strip diacritics, collapse
    non-alphanumeric runs to underscores.

    "Khyber Pakhtunkhwa" → "khyber_pakhtunkhwa"
    "Section 26-A"        → "section_26_a"
    "Cèdre déodara"       → "cedre_deodara"
    """
    s = unicodedata.normalize("NFKD", text)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = _NON_ALNUM.sub("_", s)
    return s.strip("_")


# ═════════════════════════════════════════════════════════════════════════════
# FIX-3  ── Cross-domain synonym dictionaries
# ═════════════════════════════════════════════════════════════════════════════
#
# LEGAL_DICTIONARY is now Dict[str, List[str]]  (canonical → synonym variants).
# This replaces the flat Set[str] from v2.1.
#
# Rules:
#   • Key   = clean canonical form (what will be stored as canonical_name in Neo4j)
#   • Value = list of surface forms / aliases / botanical names / abbreviations
#             that should all map back to this canonical during extraction AND
#             be stored in the entity's `aliases` array for retrieval.

LEGAL_DICTIONARY: Dict[str, List[str]] = {

    # ── FOREST DOMAIN ─────────────────────────────────────────────────────────

    # Species
    "deodar": [
        "cedrus deodara", "cedrus_deodara", "diyar", "devdar",
        "himalayan cedar", "deodara", "national tree",
        "pakistan national tree",
        # Measurement-prefix variants that appear in OCR/parsed data
        "dbh_1_deodar", "dbh_2_deodar", "dbh_3_deodar", "standing_deodar",
    ],
    "chir pine": [
        "chir", "cheerh", "chirh", "cheer", "cheer pine",
        "long leaved pine", "long-leaved pine",
        "pinus roxburghii", "pinus_roxburghii",
    ],
    "blue pine": [
        "biar", "nakhtar", "kail", "kail pine",
        "pinus wallichiana", "pinus_wallichiana",
    ],
    "spruce": [
        "kachal", "rai", "morinda spruce",
        "picea smithiana", "picea_smithiana",
    ],
    "fir": [
        "silver fir", "pindrow fir", "chal", "partal",
        "abies pindrow", "abies_pindrow",
    ],
    "walnut": ["akhrot", "juglans regia", "juglans_regia"],
    "ash":    ["sum", "fraxinus", "fraxinus_excelsior"],
    "mulberry": ["tut", "morus", "morus_alba"],
    "poplar": ["sofeda", "populus", "populus_alba"],
    "chenar": ["plane tree", "platanus", "platanus_orientalis"],
    "oak":    ["banj", "moru oak", "green oak", "quercus", "quercus_semecarpifolia"],
    "shisham": ["sheesham", "dalbergia sissoo", "dalbergia_sissoo", "tahli"],

    # Forest types
    "reserved forest":  ["reserve forest", "rf", "reserved forests", "reserved_forest"],
    "protected forest": ["protected forests", "pf", "protected_forest"],
    "village forest":   ["village forests", "communal forest", "community forest"],
    "guzara forest":    ["guzara", "guzara forests"],

    # Officers & roles
    "forest officer":           ["forest-officer", "fo"],
    "range forest officer":     ["range officer", "rfo", "range_forest_officer"],
    "divisional forest officer":["dfo", "divisional_forest_officer"],
    "assistant conservator":    ["acf", "assistant_conservator_of_forests"],
    "conservator of forests":   ["conservator", "chief conservator", "ccf",
                                  "conservator_of_forests"],
    "forest guard":             ["guard", "chowkidar"],
    "forest settlement officer":["settlement officer", "fso"],
    "beat officer":             ["beat_officer"],

    # Legal concepts (forest)
    "timber": [
        "wood", "lumber", "logs", "log",
        "sawn timber", "round timber", "pit props",
    ],
    "forest produce":    ["forest product", "forest products", "minor forest produce",
                          "non-timber forest produce", "ntfp"],
    "firewood":          ["fuel wood", "fuelwood", "wood fuel"],
    "charcoal":          ["koila", "coal"],
    "resin":             ["raal", "turpentine"],
    "bamboo":            ["bans", "bamboos"],
    "grazing":           ["cattle grazing", "pastoral", "pasture", "fodder"],
    "seigniorage":       ["seigniorage fee", "timber fee", "royalty fee",
                          "revenue fee", "seigniorage_fee"],
    "transit pass":      ["transit permit", "form-16", "form 16", "challan",
                          "transit_pass"],
    "encroachment":      ["trespass", "illegal occupation", "unauthorized use",
                          "illegal_encroachment"],
    "afforestation":     ["reforestation", "plantation", "planting"],
    "deforestation":     ["illegal logging", "illegal felling", "illegal_logging"],

    # Enforcement (forest)
    "seizure":           ["seize", "confiscate", "confiscation", "attachment",
                          "distress"],
    "arrest":            ["arrested", "apprehend", "detain"],
    "warrant":           ["without warrant", "search warrant", "arrest warrant"],
    "compounding":       ["compound", "compoundable", "non-compoundable"],

    # ── CLIMATE DOMAIN ────────────────────────────────────────────────────────

    "carbon credit": [
        "carbon credits", "carbon offset", "carbon offsets",
        "greenhouse gas credit", "ghg credit",
        "emission reduction credit", "certified emission reduction", "cer",
        "carbon_credit",
    ],
    "emissions": [
        "emission", "ghg", "greenhouse gas", "greenhouse gases",
        "co2", "carbon dioxide", "methane", "ch4",
        "nitrous oxide", "n2o", "nox", "sox",
    ],
    "climate change authority": [
        "climate authority", "climate board", "climate action board",
        "pakistan climate authority", "pca", "climate council",
        "climate_change_authority",
    ],
    "environmental impact assessment": [
        "eia", "environmental assessment", "environment assessment",
        "initial environmental examination", "iee",
        "strategic environmental assessment", "sea",
        "environmental review", "environmental_impact_assessment",
    ],
    "national environmental quality standards": [
        "neqs", "neq standards", "environmental quality standards",
        "pollution standards", "emission standards", "ambient standards",
    ],
    "biodiversity": [
        "biological diversity", "flora and fauna", "wildlife diversity",
        "ecosystem diversity", "species richness",
    ],
    "climate change policy": [
        "national climate policy", "climate action plan",
        "nationally determined contribution", "ndc",
        "paris agreement", "unfccc",
    ],
    "renewable energy": [
        "solar energy", "wind energy", "hydro power", "hydropower",
        "clean energy", "green energy", "alternative energy",
    ],
    "pollution": [
        "water pollution", "air pollution", "soil pollution",
        "noise pollution", "industrial effluent", "effluent discharge",
    ],
    "wetland": [
        "wetlands", "marsh", "mangrove", "ramsar site",
        "coastal wetland", "inland wetland",
    ],

    # ── JUDICIARY DOMAIN ──────────────────────────────────────────────────────

    "high court": [
        "superior court", "lahore high court", "lhc",
        "peshawar high court", "phc", "sindh high court", "shc",
        "balochistan high court", "bhc", "islamabad high court", "ihc",
        "high_court",
    ],
    "supreme court":    ["apex court", "sc", "chief justice court"],
    "district court":   ["sessions court", "sessions judge", "district judge"],
    "magistrate":       ["judicial magistrate", "executive magistrate", "jm", "em",
                          "first class magistrate", "civil judge"],
    "writ petition":    ["writ", "constitutional petition", "article 199 petition",
                          "habeas corpus", "mandamus", "certiorari", "quo warranto"],
    "appeal":           ["first appeal", "second appeal", "revision", "review petition",
                          "reference", "application"],
    "bail":             ["pre-arrest bail", "post-arrest bail", "transit bail",
                          "surety", "bail bond", "anticipatory bail"],
    "fir":              ["first information report", "police complaint",
                          "criminal complaint", "first_information_report"],
    "decree":           ["judgment", "judgement", "order", "decree and order",
                          "ex-parte decree"],
    "contempt":         ["contempt of court", "contempt proceedings", "suo motu"],
    "injunction":       ["stay order", "interim injunction", "temporary injunction",
                          "ad interim injunction"],
    "evidence":         ["proof", "testimony", "affidavit", "deposition",
                          "documentary evidence", "oral evidence"],
    "prosecution":      ["trial", "criminal trial", "criminal proceedings",
                          "charges", "indictment"],
    "conviction":       ["guilty verdict", "sentence", "sentenced"],
    "acquittal":        ["not guilty", "discharge", "acquitted"],
    "cognizable offence":     ["cognizable", "cognisable offence"],
    "non-cognizable offence": ["non-cognizable", "non-cognisable offence"],
    "bailable offence":       ["bailable"],
    "non-bailable offence":   ["non-bailable"],

    # ── PERMITS DOMAIN ────────────────────────────────────────────────────────

    "noc": [
        "no objection certificate", "no-objection certificate",
        "no_objection_certificate", "clearance certificate",
        "no_objection_cert",
    ],
    "license":          ["licence", "permit", "authorisation", "authorization",
                          "concession", "grant"],
    "clearance":        ["environmental clearance", "ec", "site clearance",
                          "building clearance", "regulatory clearance",
                          "environmental_clearance"],
    "land use permit":  ["land use change", "land conversion",
                          "change of land use", "luc", "land use certificate",
                          "land_use_permit"],
    "felling permit":   ["tree felling permit", "felling license", "cutting permit",
                          "timber permit", "extraction permit", "felling_permit"],
    "lease":            ["forest lease", "mining lease", "land lease",
                          "lease agreement", "leasehold"],
    "registration":     ["registration certificate", "registration number",
                          "registered", "enrolment"],
    "certificate":      ["compliance certificate", "completion certificate",
                          "fitness certificate", "character certificate"],

    # ── JURISDICTIONS ─────────────────────────────────────────────────────────

    "kpk": [
        "khyber pakhtunkhwa", "khyber_pakhtunkhwa",
        "the_province_of_khyber_pakhtunkhwa",
        "province_of_khyber_pakhtunkhwa",
        "nwfp", "north west frontier province",
        "north-west frontier province", "khyber",
        "kpk province",
    ],
    "punjab": [
        "the_province_of_punjab", "province_of_punjab",
        "province of punjab", "punjab province",
    ],
    "sindh": [
        "the_province_of_sindh", "province_of_sindh",
        "province of sindh", "sind", "sindh province",
    ],
    "balochistan": [
        "the_province_of_balochistan", "province_of_balochistan",
        "baluchistan", "province of balochistan",
    ],
    "gilgit baltistan": ["gilgit-baltistan", "gb", "gbla"],
    "azad kashmir":     ["ajk", "azad jammu", "azad jammu and kashmir"],
    "federal":          ["islamabad", "ict", "federal government", "national",
                          "pakistan federal"],

    # ── GENERIC LEGAL ─────────────────────────────────────────────────────────

    "government":   ["federal government", "provincial government", "state", "crown"],
    "court":        ["tribunal", "forum", "bench"],
    "officer":      ["official", "authority", "representative"],
    "fine":         ["penalty", "monetary penalty", "pecuniary penalty", "imposition"],
    "imprisonment": ["jail", "prison", "detention", "custody",
                      "confinement", "incarceration"],
    "offence":      ["offense", "offences", "offenses", "forest offence",
                      "criminal offence", "violation", "breach",
                      "contravention", "infraction"],
    "forfeiture":   ["confiscation", "seizure of property"],
    "notification": ["gazette notification", "official gazette", "gazette"],
    "ordinance":    ["act", "statute", "law", "legislation", "enactment"],
    "section":      ["clause", "subsection", "provision", "article"],
    "schedule":     ["annex", "appendix", "annexure"],
    "property":     ["land", "estate", "tenure", "immovable property"],
    "ownership":    ["title", "possession", "occupation"],
    "transfer":     ["sale", "mortgage", "conveyance", "assignment"],
    "contract":     ["agreement", "deed", "instrument", "bond", "memorandum"],
    "procedure":    ["process", "proceeding", "action", "suit"],
    "jurisdiction": ["competence", "capacity", "power"],
    "right":        ["duty", "obligation", "entitlement", "privilege"],
    "revenue":      ["royalty", "fee", "cess", "tax", "duty", "toll"],
    "settlement":   ["forest settlement", "land settlement"],
    "boundary":     ["demarcation", "survey", "border", "limit"],
    "public":       ["public interest", "public land", "state land"],
    "commencement": ["enforcement date", "effective date", "coming into force"],
}

# ── Build reverse lookup: ANY synonym slug → canonical key ──────────────────
# Used at extraction time to map surface forms back to their canonical.
_REVERSE_LOOKUP: Dict[str, str] = {}

def _build_reverse_lookup() -> None:
    for canon, synonyms in LEGAL_DICTIONARY.items():
        canon_slug = _unicode_slug(canon)
        _REVERSE_LOOKUP[canon_slug] = canon
        for syn in synonyms:
            syn_slug = _unicode_slug(syn)
            _REVERSE_LOOKUP[syn_slug] = canon

_build_reverse_lookup()


def resolve_to_canonical(surface: str) -> str:
    """
    Map any surface form (or noisy stored name) to its canonical key.

    1. Unicode-slugify the input.
    2. Strip known noisy prefixes/suffixes.
    3. Look up in the reverse synonym table.
    4. If still no match, return the stripped slug as-is (unknown entity).

    Examples
    --------
    "dbh_1_deodar"                     → "deodar"
    "the_province_of_khyber_pakhtunkhwa" → "kpk"
    "cedrus_deodara"                   → "deodar"
    "Pinus Roxburghii"                 → "chir pine"
    "Section 26"                       → "section 26"  (unchanged, not in map)
    """
    slug = _unicode_slug(surface)
    # Direct reverse lookup first (e.g. "cedrus_deodara" is a synonym of "deodar")
    if slug in _REVERSE_LOOKUP:
        return _REVERSE_LOOKUP[slug]
    # Strip prefixes and retry
    stripped = _strip_prefixes_suffixes(slug)
    if stripped in _REVERSE_LOOKUP:
        return _REVERSE_LOOKUP[stripped]
    # Return stripped slug (will be stored as-is but at least prefix-free)
    return stripped if stripped else slug


# ── SPECIES_DICTIONARY kept as a separate dict for graph_rag_retriever ──────
SPECIES_DICTIONARY: Dict[str, List[str]] = {
    "chir pine":  ["chir", "cheer", "cheerh", "long leaved pine",
                   "pinus roxburghii", "pinus_roxburghii"],
    "deodar":     ["cedrus deodara", "cedrus_deodara", "diyar", "devdar",
                   "himalayan cedar"],
    "blue pine":  ["biar", "pinus wallichiana", "pinus_wallichiana",
                   "nakhtar", "kail"],
    "fir":        ["silver fir", "abies pindrow", "abies_pindrow", "chal", "partal"],
    "spruce":     ["kachal", "picea smithiana", "picea_smithiana", "morinda"],
    "walnut":     ["akhrot", "juglans regia", "juglans_regia"],
    "ash":        ["sum", "fraxinus", "fraxinus_excelsior"],
    "mulberry":   ["tut", "morus", "morus_alba"],
    "poplar":     ["sofeda", "populus", "populus_alba"],
    "chenar":     ["plane tree", "platanus", "platanus_orientalis"],
    "oak":        ["banj", "moru oak", "quercus", "quercus_semecarpifolia"],
    "shisham":    ["sheesham", "dalbergia sissoo", "dalbergia_sissoo", "tahli"],
}

# ── Jurisdiction alias map (FIX-7) ──────────────────────────────────────────
JURISDICTION_ALIASES: Dict[str, List[str]] = {
    "KPK":         ["khyber pakhtunkhwa", "kpk", "nwfp",
                    "north-west frontier province", "north west frontier"],
    "Punjab":      ["punjab"],
    "Sindh":       ["sindh", "sind"],
    "Balochistan": ["balochistan", "baluchistan"],
    "Federal":     ["federal", "islamabad", "ict", "national"],
    "AJK":         ["azad kashmir", "ajk", "azad jammu"],
    "GB":          ["gilgit baltistan", "gilgit-baltistan"],
}

# Stopwords for pre-filtering
STOPWORDS: Set[str] = {
    "a", "an", "the", "and", "or", "but", "if", "then",
    "he", "she", "it", "they", "this", "that", "these", "those",
    "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did",
    "will", "would", "shall", "should", "may", "might", "can", "could",
}


# ═════════════════════════════════════════════════════════════════════════════
# Jurisdiction helper
# ═════════════════════════════════════════════════════════════════════════════

def detect_jurisdiction(text: str) -> Optional[str]:
    """
    Detect the primary jurisdiction in a block of text.
    Returns canonical province name (e.g. 'KPK', 'Punjab') or None.
    """
    text_lower = text.lower()
    for canonical, aliases in JURISDICTION_ALIASES.items():
        for alias in aliases:
            if re.search(r"\b" + re.escape(alias) + r"\b", text_lower):
                return canonical
    return None


# ═════════════════════════════════════════════════════════════════════════════
# FIX-4  ── Strengthened canonicalizer
# ═════════════════════════════════════════════════════════════════════════════

class EntityCanonicalizer:
    """
    Canonicalize entity mentions with write-time prefix stripping (FIX-1/FIX-4),
    synonym resolution (FIX-3), and fuzzy disambiguation.
    """

    def __init__(self):
        self.canonical_forms: Dict[str, str] = {}
        self.context_snippets: Dict[str, List[str]] = {}
        self.similarity_threshold = 0.85

        # Hard overrides take precedence over auto-canonicalization
        self.canonical_overrides: Dict[str, str] = {
            "forest officer":   "forest officer",
            "forest guard":     "forest guard",
            "reserved forest":  "reserved forest",
            "protected forest": "protected forest",
            "village forest":   "village forest",
        }

    def auto_canonicalize(self, entity: str) -> str:
        """
        FIX-4: Produce a clean canonical slug for any entity surface form.

        Steps:
          1. Unicode-normalise and lowercase.
          2. Check synonym reverse lookup → resolve to canonical key.
          3. Strip known noisy prefixes/suffixes.
          4. De-pluralise (simple heuristic).
          5. Return space-separated canonical (NOT underscore) so it is
             human-readable in the registry; Neo4j Cypher will compare
             case-insensitively.
        """
        # Try full synonym resolution first (handles botanical names, prefixed variants)
        resolved = resolve_to_canonical(entity)

        # If the resolved form is already in LEGAL_DICTIONARY, it IS the canonical key
        if resolved in LEGAL_DICTIONARY:
            return resolved

        # Otherwise fall back to cleaned slug (strip quotes, hyphens → spaces, de-pluralise)
        s = resolved.replace("_", " ").strip("'\" ")
        if s.endswith("s") and len(s) > 3 and not s.endswith("ss"):
            s = s[:-1]
        return s

    def fuzzy_match(self, a: str, b: str) -> float:
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    def check_context_similarity(self, canonical_name: str, new_context: str) -> bool:
        if canonical_name not in self.context_snippets:
            return True
        for ctx in self.context_snippets[canonical_name][:5]:
            if self.fuzzy_match(new_context, ctx) > 0.7:
                return True
        return False

    def canonicalize(self, entity: str, context: str = "") -> Tuple[str, bool]:
        """
        Canonicalize with fuzzy disambiguation.
        Returns (canonical_name, is_confident).
        """
        entity_lower = entity.lower().strip()
        if entity_lower in self.canonical_overrides:
            return self.canonical_overrides[entity_lower], True

        canonical = self.auto_canonicalize(entity)

        # Fuzzy deduplication against already-seen canonicals
        similar = [
            (existing, self.fuzzy_match(canonical, existing))
            for existing in self.canonical_forms
            if 0.7 < self.fuzzy_match(canonical, existing) < 1.0
        ]
        if similar and context:
            for existing, _ in similar:
                if self.check_context_similarity(existing, context):
                    self.context_snippets.setdefault(existing, []).append(context)
                    return existing, True

        self.canonical_forms[canonical] = entity
        if context:
            self.context_snippets[canonical] = [context]
        return canonical, True


# ═════════════════════════════════════════════════════════════════════════════
# FIX-2 ── Entity Registry: aliases written to Neo4j
# ═════════════════════════════════════════════════════════════════════════════

class EntityRegistry:
    """
    Global entity registry for Neo4j merging with provenance tracking.

    FIX-2: Every distinct surface form seen for a canonical entity is stored in
    prov["aliases"].  get_entity_info() exports this list as the 'aliases' array
    that the retriever's Cypher queries use:

        any(alias IN e.aliases WHERE toLower(alias) CONTAINS query_term)

    Additionally, the registry pre-populates aliases from LEGAL_DICTIONARY so
    that even entities seen only once in the corpus get their full alias list.
    """

    def __init__(self):
        self.entities: Dict[str, Dict] = {}
        self.entity_chunks: Dict[str, List[str]] = {}
        self.provenance: Dict[str, Dict] = {}

    def _prepopulate_aliases(self, canonical_name: str) -> None:
        """
        Seed aliases from LEGAL_DICTIONARY when a new entity is first registered.
        Also adds all synonym variants from SPECIES_DICTIONARY.
        """
        # Normalised key lookup
        norm = _unicode_slug(canonical_name)
        stripped = _strip_prefixes_suffixes(norm)

        seed_aliases: Set[str] = set()

        # Check LEGAL_DICTIONARY
        for key, syns in LEGAL_DICTIONARY.items():
            key_slug = _unicode_slug(key)
            if key_slug == norm or key_slug == stripped or key == canonical_name:
                seed_aliases.add(key)                     # canonical itself
                seed_aliases.update(syns)                 # all known synonyms
                break

        # Check SPECIES_DICTIONARY
        for key, syns in SPECIES_DICTIONARY.items():
            key_slug = _unicode_slug(key)
            if key_slug == norm or key_slug == stripped or key == canonical_name:
                seed_aliases.add(key)
                seed_aliases.update(syns)
                break

        if seed_aliases:
            self.provenance[canonical_name]["aliases"].update(seed_aliases)

    def register_entity(
        self,
        canonical_name: str,
        entity_type: str,
        chunk_id: str,
        original_mention: str,
        source_file: str = "",
        context_snippet: str = "",
    ) -> None:
        """Register an entity mention with full provenance and alias tracking."""
        if canonical_name not in self.entities:
            self.entities[canonical_name] = {
                "canonical_name": canonical_name,
                "entity_type": entity_type,
                "mentions": set(),
                "frequency": 0,
            }
            self.entity_chunks[canonical_name] = []
            self.provenance[canonical_name] = {
                "first_seen_doc": source_file,
                "last_seen_doc": source_file,
                "contexts": [],
                "aliases": set(),       # FIX-2: full alias set
            }
            # FIX-2: seed with all known dictionary aliases
            self._prepopulate_aliases(canonical_name)

        self.entities[canonical_name]["mentions"].add(original_mention)
        self.entities[canonical_name]["frequency"] += 1

        # FIX-2: every surface form seen is added to aliases
        self.provenance[canonical_name]["aliases"].add(original_mention)
        # Also add the cleaned/stripped form as an alias
        stripped_mention = resolve_to_canonical(original_mention)
        if stripped_mention != canonical_name:
            self.provenance[canonical_name]["aliases"].add(stripped_mention)

        if chunk_id not in self.entity_chunks[canonical_name]:
            self.entity_chunks[canonical_name].append(chunk_id)

        prov = self.provenance[canonical_name]
        prov["last_seen_doc"] = source_file
        if context_snippet:
            prov["contexts"].append({
                "chunk_id": chunk_id,
                "snippet": context_snippet[:100],
                "source": source_file,
            })

    def get_entity_info(self, canonical_name: str) -> Optional[Dict]:
        """Get entity info dict ready for Neo4j (all sets → lists, FIX-8)."""
        if canonical_name not in self.entities:
            return None

        entity = self.entities[canonical_name]
        prov = self.provenance.get(canonical_name, {})

        # Build the aliases list: provenance surface forms + dictionary variants
        aliases_set: Set[str] = set(prov.get("aliases", set()))
        # Always include underscore variant of each alias for Cypher CONTAINS
        extra: Set[str] = set()
        for a in aliases_set:
            extra.add(a.replace(" ", "_"))
            extra.add(a.replace("_", " "))
        aliases_set.update(extra)

        return {
            "canonical_name": canonical_name,
            "entity_type": entity["entity_type"],
            "mentions": list(entity["mentions"]),           # FIX-8
            "frequency": entity["frequency"],
            "chunk_count": len(self.entity_chunks[canonical_name]),
            "chunk_ids": self.entity_chunks[canonical_name],
            "aliases": sorted(aliases_set),                 # FIX-2 + FIX-8
            "first_seen_doc": prov.get("first_seen_doc"),
            "last_seen_doc": prov.get("last_seen_doc"),
            "context_snippets": prov.get("contexts", [])[:5],
        }

    def get_all_entities(self) -> List[Dict]:
        return [
            info for name in self.entities
            if (info := self.get_entity_info(name)) is not None
        ]

    def export_for_neo4j(self, output_path: str) -> Dict:
        """Export entity registry as JSON for Neo4j import."""
        import json
        import datetime

        entities = self.get_all_entities()
        output = {
            "entities": entities,
            "total_unique": len(entities),
            "total_mentions": sum(e["frequency"] for e in entities),
            "exported_at": datetime.datetime.utcnow().isoformat() + "Z",
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"[OK] Exported {len(entities)} unique entities → {output_path}")
        return output


# ═════════════════════════════════════════════════════════════════════════════
# Main Extractor Class
# ═════════════════════════════════════════════════════════════════════════════

class EntityExtractor:
    """
    Production-grade entity extraction with filtering, canonicalization, and registry.
    """

    _nlp_instance: Optional[Any] = None   # singleton

    def __init__(
        self,
        model_name: str = "en_core_web_sm",
        min_entities_per_chunk: int = 3,
        use_custom_patterns: bool = True,
        enable_post_filtering: bool = True,
    ):
        if EntityExtractor._nlp_instance is None:
            print(f"Loading spaCy model: {model_name}…")
            try:
                EntityExtractor._nlp_instance = spacy.load(model_name)
            except OSError:
                print(f"  Model not found — downloading '{model_name}'…")
                subprocess.run(["python", "-m", "spacy", "download", model_name],
                               check=True)
                EntityExtractor._nlp_instance = spacy.load(model_name)

        self.nlp = EntityExtractor._nlp_instance
        self.min_entities_per_chunk = min_entities_per_chunk
        self.use_custom_patterns = use_custom_patterns
        self.enable_post_filtering = enable_post_filtering
        self.canonicalizer = EntityCanonicalizer()

        if use_custom_patterns:
            self.matcher = Matcher(self.nlp.vocab)
            self._add_legal_patterns()

        print("[OK] EntityExtractor ready")

    # ─────────────────────────────────────────────────────────────────────────
    # Pattern setup
    # ─────────────────────────────────────────────────────────────────────────

    def _add_legal_patterns(self) -> None:
        self.matcher.add("LEGAL_ACTOR", [[
            {"LOWER": {"IN": [
                "court", "government", "officer", "authority",
                "tribunal", "magistrate", "judge", "commissioner",
            ]}},
        ]])
        self.matcher.add("FOREST_ACTOR", [[
            {"LOWER": {"IN": ["forest", "forestry"]}},
            {"LOWER": {"IN": ["officer", "guard", "ranger", "department"]}},
        ]])
        self.matcher.add("PENALTY", [[
            {"LOWER": "fine"},
            {"IS_DIGIT": True, "OP": "?"},
            {"LOWER": {"IN": ["rupees", "rs", "pkr"]}, "OP": "?"},
        ]])
        self.matcher.add("IMPRISONMENT", [[
            {"LOWER": {"IN": ["imprisonment", "jail", "prison"]}},
            {"LOWER": "for", "OP": "?"},
            {"IS_DIGIT": True, "OP": "?"},
            {"LOWER": {"IN": ["years", "months", "days"]}, "OP": "?"},
        ]])
        self.matcher.add("LEGAL_CONCEPT", [[
            {"LOWER": {"IN": ["reserved", "protected", "village"]}},
            {"LOWER": "forest"},
        ]])
        self.matcher.add("PROCEDURE", [[
            {"LOWER": {"IN": ["shall", "may", "must"]}},
            {"POS": "VERB"},
        ]])

    # ─────────────────────────────────────────────────────────────────────────
    # Filtering & scoring
    # ─────────────────────────────────────────────────────────────────────────

    def pre_filter_entity(self, entity: str, entity_type: str) -> bool:
        if len(entity) < 3:
            return False
        noise = {
            "shall", "may", "must", "will", "would",
            "is", "are", "was", "were", "and", "the",
            "for", "from", "with",
        }
        if entity.lower() in noise or entity.lower() in STOPWORDS:
            return False
        if entity.isdigit() and entity_type not in {"MONEY", "DATE"}:
            return False
        return True

    def calculate_entity_confidence(
        self,
        entity: str,
        entity_type: str,
        frequency: int,
        text: str,
    ) -> int:
        """
        Calculate confidence score 0–10.
        FIX-5: LEGAL_REF scores 4 pts for type so single-mention section refs
                pass the default threshold of 6.
        """
        score = 0

        # Frequency (0–3)
        if frequency >= 5:
            score += 3
        elif frequency >= 3:
            score += 2
        elif frequency >= 2:
            score += 1

        # Type (0–4)  ── FIX-5
        if entity_type in {"ORG", "GPE", "LAW", "LEGAL_REF"}:
            score += 4
        elif entity_type in {"PERSON", "LEGAL_ACTOR"}:
            score += 2
        elif entity_type in {"DATE", "MONEY"}:
            score += 1

        # Dictionary membership (0–2)
        entity_lower = entity.lower()
        in_dict = (
            entity_lower in LEGAL_DICTIONARY
            or _unicode_slug(entity_lower) in _REVERSE_LOOKUP
        )
        if in_dict:
            score += 2

        # Legal pattern bonus (0–1)
        if self.has_legal_pattern(entity, text):
            score += 1

        return score

    def has_legal_pattern(self, entity: str, text: str) -> bool:
        patterns = [
            rf'{re.escape(entity)}\s+means',
            rf'{re.escape(entity)}\s+includes',
            rf'"{re.escape(entity)}"',
            rf'defined\s+as\s+{re.escape(entity)}',
        ]
        for pat in patterns:
            if re.search(pat, text, re.IGNORECASE):
                return True
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # Extraction helpers
    # ─────────────────────────────────────────────────────────────────────────

    def extract_defined_terms(self, text: str) -> List[str]:
        """
        Extract defined terms from quotation marks.
        FIX-6: handles straight, curly-double, and curly-single quotes.
        """
        normalised = (
            text
            .replace("\u201c", '"').replace("\u201d", '"')
            .replace("\u2018", '"').replace("\u2019", '"')
            .replace("'", '"')
        )
        matches = re.findall(r'"([^"]{2,})"', normalised)
        return [m.strip() for m in matches if len(m.strip()) > 2]

    def extract_entities(
        self, text: str, return_types: bool = True
    ) -> Tuple[List[str], List[str]]:
        """
        Extract raw entity mentions (before confidence filtering).

        FIX-3: after spaCy + patterns, every mention is resolved through
        resolve_to_canonical() so downstream storage uses clean canonical forms.
        """
        doc = self.nlp(text)
        entity_mentions: List[str] = []
        entity_types: List[str] = []

        # 1. spaCy NER
        for ent in doc.ents:
            if ent.label_ in {"PERSON", "ORG", "GPE", "LOC", "DATE", "MONEY", "LAW"}:
                entity_mentions.append(ent.text)
                entity_types.append(ent.label_)

        # 2. Custom Matcher patterns
        if self.use_custom_patterns:
            for match_id, start, end in self.matcher(doc):
                span = doc[start:end]
                label = self.nlp.vocab.strings[match_id]
                if span.text not in entity_mentions:
                    entity_mentions.append(span.text)
                    entity_types.append(label)

        # 3. Defined terms (FIX-6: unicode quotes)
        for term in self.extract_defined_terms(text):
            if term not in entity_mentions:
                entity_mentions.append(term)
                entity_types.append("DEFINED_TERM")

        # 4. Section / article references  (FIX-5: LEGAL_REF → 4 pts)
        for ref in re.findall(
            r"((?:Section|Article|Chapter|Schedule)\s+(?:[IVXLCDM]+|\d+))",
            text, re.IGNORECASE,
        ):
            if ref not in entity_mentions:
                entity_mentions.append(ref)
                entity_types.append("LEGAL_REF")

        # 5. Species / domain dictionary scan (FIX-3)
        text_lower = text.lower()
        for canon, synonyms in {**LEGAL_DICTIONARY, **SPECIES_DICTIONARY}.items():
            for surface in [canon] + synonyms:
                surf_clean = surface.lower().strip()
                if len(surf_clean) < 3:
                    continue
                pat = r"\b" + re.escape(surf_clean) + r"s?\b"
                if re.search(pat, text_lower) and canon not in entity_mentions:
                    entity_mentions.append(canon)
                    entity_types.append("DOMAIN_TERM")
                    break  # one hit per canonical is enough

        # FIX-4: resolve all mentions to canonical forms before returning
        resolved_mentions: List[str] = []
        for mention, etype in zip(entity_mentions, entity_types):
            canonical = resolve_to_canonical(mention)
            # Keep the cleaner of canonical vs original
            resolved_mentions.append(
                canonical if canonical != _unicode_slug(mention) else mention
            )

        return resolved_mentions, entity_types

    # ─────────────────────────────────────────────────────────────────────────
    # Chunk-level processing
    # ─────────────────────────────────────────────────────────────────────────

    def extract_from_chunk(self, chunk: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract entities from a single chunk (RAW — no confidence filtering).

        FIX-7: detects and writes 'jurisdiction' to metadata.
        FIX-4: entity mentions are canonicalized at write time.
        """
        text = chunk["text"]
        entity_mentions, entity_types = self.extract_entities(text)

        chunk["metadata"]["entity_mentions"] = entity_mentions
        chunk["metadata"]["entity_types"] = entity_types
        chunk["metadata"]["entity_count"] = len(entity_mentions)

        # FIX-7: jurisdiction detection
        if not chunk["metadata"].get("jurisdiction"):
            jurisdiction = detect_jurisdiction(text)
            if jurisdiction is None:
                law_title = str(chunk["metadata"].get("law_title", ""))
                jurisdiction = detect_jurisdiction(law_title)
            if jurisdiction:
                chunk["metadata"]["jurisdiction"] = jurisdiction

        return chunk

    def extract_from_chunks(
        self,
        chunks: List[Dict[str, Any]],
        verbose: bool = True,
    ) -> List[Dict[str, Any]]:
        """Raw extraction over all chunks (no confidence filtering)."""
        if verbose:
            print(f"Extracting entities from {len(chunks)} chunks…")

        enhanced, total = [], 0
        for chunk in chunks:
            ec = self.extract_from_chunk(chunk)
            enhanced.append(ec)
            total += ec["metadata"]["entity_count"]

        if verbose:
            avg = total / len(chunks) if chunks else 0
            print(f"[OK] {total} raw entities extracted ({avg:.1f}/chunk avg)")

        return enhanced

    def filter_entities_post_extraction(
        self,
        all_chunks: List[Dict[str, Any]],
        min_frequency: int = 5,
        min_confidence: int = 6,  # FIX-5: lowered 7→6 so legal refs pass
    ) -> List[Dict[str, Any]]:
        """Post-filter with confidence scoring."""
        entity_freq: Counter = Counter()
        for chunk in all_chunks:
            entity_freq.update(chunk.get("metadata", {}).get("entity_mentions", []))

        total_raw = total_filtered = 0

        for chunk in all_chunks:
            meta = chunk.get("metadata", {})
            if "entity_mentions" not in meta:
                continue

            raw_ents = meta["entity_mentions"]
            raw_types = meta["entity_types"]
            total_raw += len(raw_ents)

            kept_ents, kept_types = [], []
            for entity, etype in zip(raw_ents, raw_types):
                if not self.pre_filter_entity(entity, etype):
                    continue
                score = self.calculate_entity_confidence(
                    entity, etype, entity_freq[entity], chunk["text"]
                )
                if score >= min_confidence:
                    kept_ents.append(entity)
                    kept_types.append(etype)

            total_filtered += len(kept_ents)
            meta["entity_mentions"] = kept_ents
            meta["entity_types"] = kept_types
            meta["entity_count"] = len(kept_ents)
            meta["entity_filter_stats"] = {
                "raw_count": len(raw_ents),
                "filtered_count": len(kept_ents),
                "reduction_pct": (
                    round((1 - len(kept_ents) / len(raw_ents)) * 100, 1)
                    if raw_ents else 0
                ),
            }

        reduction = (1 - total_filtered / total_raw) * 100 if total_raw else 0
        print(
            f"[OK] Post-filter: {total_raw} raw → {total_filtered} kept "
            f"({reduction:.1f}% reduction) "
            f"[min_freq={min_frequency}, min_conf={min_confidence}]"
        )
        return all_chunks

    # FIX-9: convenience pipeline
    def extract_and_filter_chunks(
        self,
        chunks: List[Dict[str, Any]],
        min_frequency: int = 5,
        min_confidence: int = 6,
        verbose: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Run raw extraction AND post-filtering in one call.

            chunks = extractor.extract_and_filter_chunks(chunks)
        """
        chunks = self.extract_from_chunks(chunks, verbose=verbose)
        chunks = self.filter_entities_post_extraction(
            chunks, min_frequency=min_frequency, min_confidence=min_confidence
        )
        return chunks