"""
Document Registry — maps every document in system to a category.
"""

DOCUMENT_REGISTRY = {

    # ── PRIMARY LEGAL STATUTES (answer legal queries) ────────────────────────
    "DOC_20260214_094034_ffba3818": {
        "law_title":  "Forest Act 1927",
        "category":   "legal_statute",
        "priority":   1,  # highest priority in retrieval
    },
    "DOC_20260214_100316_74b4b28c": {
        "law_title":  "KPK Forest Ordinance 2002",
        "category":   "legal_statute",
        "priority":   1,
    },
    "DOC_20260214_130309_185aaa71": {
        "law_title":  "KPK Forest Amendment Act 2022",
        "category":   "legal_statute",
        "priority":   1,
    },
    "DOC_20260214_101828_69291d72": {
        "law_title":  "KPK Forest Ordinance 2002 (NWFP)",
        "category":   "legal_statute",
        "priority":   1,
    },
    "DOC_20260214_092951_7bd9ef5f": {
        "law_title":  "KPK Climate Action Board Act 2025",
        "category":   "legal_statute",
        "priority":   1,
    },
    "DOC_20260214_095138_b48d7a73": {
        "law_title":  "Conservation and Exploitation of Forests in Hazara Ordinance 1980",
        "category":   "legal_statute",
        "priority":   1,
    },
    "DOC_20260214_095552_7124e462": {
        "law_title":  "West Pakistan Firewood and Charcoal Restriction Act 1964",
        "category":   "legal_statute",
        "priority":   1,
    },
    "DOC_20260214_095911_e1eae640": {
        "law_title":  "KPK Forestry Commission Act 1999",
        "category":   "legal_statute",
        "priority":   1,
    },
    "DOC_20260214_100126_bdc5720d": {
        "law_title":  "Forest Development Corporation Ordinance 1980",
        "category":   "legal_statute",
        "priority":   1,
    },
    "DOC_20260214_100925_6d622853": {
        "law_title":  "KPK Parks and Horticulture Act 2024",
        "category":   "legal_statute",
        "priority":   1,
    },
    "DOC_20260214_102540_c9251636": {
        "law_title":  "KPK Wildlife and Biodiversity Protection Act 2015",
        "category":   "legal_statute",
        "priority":   1,
    },
    "DOC_20260214_103408_0e6b0664": {
        "law_title":  "KPK Forest Produce Transport Rules 2004",
        "category":   "legal_rules",
        "priority":   2,
    },
    "DOC_20260214_103609_f8ef1724": {
        "law_title":  "KPK Management of Guzara Forest Rules 2004",
        "category":   "legal_rules",
        "priority":   2,
    },
    "DOC_20260214_104008_65935823": {
        "law_title":  "KPK Protected Forest Management Rules 2005",
        "category":   "legal_rules",
        "priority":   2,
    },
    "DOC_20260214_104513_7477507b": {
        "law_title":  "KPK Climate Change Policy 2022",
        "category":   "policy",
        "priority":   3,
    },
    "DOC_20260214_105007_23b3640c": {
        "law_title":  "KPK Environmental Protection Act 2014",
        "category":   "legal_statute",
        "priority":   1,
    },
    "DOC_20260214_105249_2fc4409c": {
        "law_title":  "KPK Private Game Reserve Rules 1993",
        "category":   "legal_rules",
        "priority":   2,
    },
    "DOC_20260214_143927_913b92d8": {
        "law_title":  "NWFP Forest Development Corporation Amendment Act 2006",
        "category":   "legal_statute",
        "priority":   1,
    },
    "DOC_20260214_144443_e738685c": {
        "law_title":  "KPK Duty on Forest Produce Rules 2004",
        "category":   "legal_rules",
        "priority":   2,
    },

    # ── CASE LAW (answer case/precedent queries) ──────────────────────────────
    "2023_PLD_442_State_vs_Gul_Zaman": {
        "law_title":  "2023 PLD 442 State vs Gul Zaman",
        "category":   "case_law",
        "priority":   2,
    },
    "2025_CLC_12_Govt_KPK_vs_Timber_Mafia": {
        "law_title":  "2025 CLC 12 Govt KPK vs Timber Mafia",
        "category":   "case_law",
        "priority":   2,
    },
    "2022_SCMR_88_Muhammad_Akram_vs_State": {
        "law_title":  "2022 SCMR 88 Muhammad Akram vs State",
        "category":   "case_law",
        "priority":   2,
    },
    "2022_SCMR_708_State_vs_Sher_Wali": {
        "law_title":  "2022 SCMR 708 State vs Sher Wali",
        "category":   "case_law",
        "priority":   2,
    },
    "2025_PLD_35_Forest_Dept_vs_Residents_Madyan": {
        "law_title":  "2025 PLD 35 Forest Dept vs Residents Madyan",
        "category":   "case_law",
        "priority":   2,
    },

    # ── OPERATIONAL (only answer ops/permit/rate queries) ────────────────────
    "Working Plan 2015-2025":   {"law_title": "Working Plan 2015-2025",   "category": "operational", "priority": 4},
    "Working Plan 2025-2035":   {"law_title": "Working Plan 2025-2035",   "category": "operational", "priority": 4},
    "MRS 2015":                 {"law_title": "MRS 2015",                 "category": "rates",        "priority": 5},
    "penalty_analysis":         {"law_title": "Penalty Analysis Data",    "category": "analytics",    "priority": 5},
    "Building Code of Pakistan (Fire Safety Provisions-2016),": {
        "law_title": "Building Code of Pakistan Fire Safety 2016",
        "category":  "building_code",
        "priority":  5,
    },
    "BTASP PC-I": {"law_title": "BTASP PC-I", "category": "operational", "priority": 4},
}

# Categories that should NOT appear in legal query answers
LEGAL_QUERY_EXCLUDED_CATEGORIES = {
    "operational", "rates", "analytics", "building_code"
}

# Categories that should NOT appear in operational query answers  
OPERATIONAL_QUERY_EXCLUDED_CATEGORIES = {
    "case_law"
}


def get_doc_info(doc_id: str) -> dict:
    """Look up a document by its ID or law_title."""
    # Direct lookup
    if doc_id in DOCUMENT_REGISTRY:
        return DOCUMENT_REGISTRY[doc_id]
    # Case-insensitive lookup
    doc_id_lower = doc_id.lower().replace(" ", "_")
    for key, val in DOCUMENT_REGISTRY.items():
        if key.lower().replace(" ", "_") == doc_id_lower:
            return val
    return {"law_title": doc_id, "category": "unknown", "priority": 3}


def get_real_law_title(doc_id: str) -> str:
    """Get the real human-readable law title for a document ID."""
    return get_doc_info(doc_id).get("law_title", doc_id)


def get_category(doc_id: str) -> str:
    """Get the category of a document."""
    return get_doc_info(doc_id).get("category", "unknown")


def should_exclude_for_legal_query(doc_id: str) -> bool:
    """Returns True if this document should be excluded from legal query results."""
    cat = get_category(doc_id)
    return cat in LEGAL_QUERY_EXCLUDED_CATEGORIES