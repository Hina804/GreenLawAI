"""
Core Legal & Species Dictionaries.
Centralized reference data for intent classification and entity extraction.

These dictionaries are the source of truth for:
- Intent classifier entity boosting
- Legal reference detection
- Species name canonicalization
"""

# Legal references: canonical name → list of synonyms/aliases
LEGAL_DICTIONARY = {
    "forest act": ["forestry act", "forest law", "kpk forest act", "forest ordinance"],
    "wildlife act": ["wildlife protection act", "wildlife law", "wildlife ordinance"],
    "environmental act": ["environment protection act", "environmental law", "epa"],
    "timber act": ["timber law", "wood act"],
    "timber": ["lakdi", "wood", "lumber"],
    "forest produce": ["forest product", "produce of the forest"],
    "land act": ["land law", "land revenue act"],
    "penal code": ["pakistan penal code", "ppc", "criminal code"],
    "criminal procedure": ["crpc", "code of criminal procedure"],
    "local government": ["local government act", "lga"],
}

# Species: canonical name → list of synonyms/local names
SPECIES_DICTIONARY = {
    "deodar": ["cedrus deodara", "himalayan cedar", "diar"],
    "chir pine": ["pinus roxburghii", "cheer pine", "chir"],
    "blue pine": ["pinus wallichiana", "biar", "nakhtar", "kail"],
    "shisham": ["dalbergia sissoo", "sisau", "tali"],
    "mulberry": ["morus", "toot", "shahtoot"],
    "poplar": ["populus", "sufaida"],
    "walnut": ["juglans regia", "akhrot"],
    "oak": ["quercus", "banj", "ban oak"],
    "spruce": ["picea smithiana", "kachal"],
    "fir": ["abies pindrow", "partal"],
    "eucalyptus": ["safaida", "lachi"],
    "neem": ["azadirachta indica", "nim"],
    "kikar": ["acacia nilotica", "babool", "babul"],
    "mango": ["mangifera indica", "aam"],
}

