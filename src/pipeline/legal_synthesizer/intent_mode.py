from enum import Enum

class LegalIntentMode(str, Enum):
    DEFINITION = "definition"
    PENALTY = "penalty"
    ARREST = "arrest"
    GENERAL = "general"
    CASE_LAW = "case_law" 
