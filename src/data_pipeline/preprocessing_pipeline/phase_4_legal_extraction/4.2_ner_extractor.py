"""
NER EXTRACTOR - Phase 4.2 of KPK Legal Extraction
LLM-assisted Named Entity Recognition for ambiguous cases.
OPERATING PRINCIPLE: "LLM suggests, Rules decide" - LLM provides suggestions, rules validate.
"""

import re
import json
import logging
import hashlib
from typing import Dict, List, Tuple, Optional, Any, Set, Generator
from dataclasses import dataclass, asdict, field
from collections import defaultdict, Counter
import sys
import os
from datetime import datetime
import concurrent.futures
import asyncio

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from preprocessing_pipeline.common.identity import IdentityFactory
    IDENTITY_LOADED = True
except ImportError:
    IDENTITY_LOADED = False

try:
    from config.kpk_forestry_config import (
        KPK_OFFICER_RANKS, KPK_TREE_SPECIES, KPK_FOREST_DIVISIONS,
        KPK_GOVERNMENT_ENTITIES, KPK_MULTILINGUAL_TERMS
    )
    KPK_CONFIG_LOADED = True
except ImportError:
    KPK_CONFIG_LOADED = False
    print("WARNING: KPK Configuration not found. Using fallback patterns.")

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class LLMSuggestion:
    """Suggestion from LLM (to be validated by rules)"""
    entity_type: str
    value: str
    original_text: str
    context: str
    llm_confidence: float
    suggestion_id: str = ""
    validation_status: str = "pending"  # pending, accepted, rejected, ambiguous
    rule_validation: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.suggestion_id:
            content_hash = hashlib.md5(
                f"{self.entity_type}:{self.value}:{self.context}".encode()
            ).hexdigest()[:8]
            self.suggestion_id = f"llm_{content_hash}"


@dataclass
class ValidatedEntity:
    """Entity validated by rules after LLM suggestion"""
    entity_type: str
    value: str
    original_text: str
    context: str
    final_confidence: float
    llm_suggestion_id: str
    validation_method: str  # rule_match, pattern_match, config_match, rejected
    validated_by: List[str] = field(default_factory=list)  # Which rules validated it
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AmbiguityCase:
    """Case where LLM and rules disagree"""
    llm_suggestion: LLMSuggestion
    rule_findings: List[Dict]
    conflict_type: str  # type_mismatch, value_mismatch, confidence_disagreement
    resolution: str = "unresolved"  # unresolved, llm_correct, rules_correct, both_wrong
    human_review_needed: bool = True


class LLMNERExtractor:
    """LLM-assisted NER extractor for ambiguous cases in KPK forestry documents.
    IMPLEMENTATION RULE: LLM suggests, deterministic rules decide."""
    
    def __init__(self, config: Optional[Any] = None, llm_client=None, use_llm_fallback: bool = True):
        self.config = config
        """
        Initialize NER extractor.
        
        Args:
            llm_client: Optional LLM client (if None, uses fallback patterns)
            use_llm_fallback: Whether to use pattern-based fallback when LLM unavailable
        """
        self.llm_client = llm_client
        self.use_llm_fallback = use_llm_fallback
        self.llm_available = llm_client is not None
        
        # Statistics
        self.stats = {
            "llm_suggestions": 0,
            "rule_validations": 0,
            "ambiguity_cases": 0,
            "human_review_cases": 0,
            "abstention_decisions": 0
        }
        
        # Initialize validation patterns
        self.initialize_validation_patterns()
        self.initialize_fallback_patterns()
        
        # Cache for common entities
        self.entity_cache = {}
        
        logger.info(f"NERExtractor initialized: LLM={self.llm_available}, Fallback={use_llm_fallback}")
    
    def initialize_validation_patterns(self):
        """Initialize patterns for validating LLM suggestions"""
        
        # Officer validation patterns
        self.officer_patterns = {
            "DFO": {
                "patterns": [r'\bDFO\b', r'Divisional Forest Officer'],
                "authority_level": 3,
                "min_confidence": 0.8
            },
            "SDFO": {
                "patterns": [r'\bSDFO\b', r'Sub-Divisional Forest Officer'],
                "authority_level": 4,
                "min_confidence": 0.8
            },
            "RO": {
                "patterns": [r'\bRO\b', r'Range Officer', r'رینج آفیسر'],
                "authority_level": 5,
                "min_confidence": 0.7
            },
            "BG": {
                "patterns": [r'\bBG\b', r'Beat Guard', r'بیٹ گارڈ'],
                "authority_level": 6,
                "min_confidence": 0.7
            }
        }
        
        # Species validation patterns
        self.species_patterns = {
            "deodar": {
                "patterns": [r'deodar', r'cedar', r'دیار'],
                "protected": True,
                "min_confidence": 0.85
            },
            "chir_pine": {
                "patterns": [r'chir\s+pine', r'chirpine', r'چیر'],
                "protected": True,
                "min_confidence": 0.8
            },
            "kail": {
                "patterns": [r'kail', r'blue\s+pine', r'کائل'],
                "protected": True,
                "min_confidence": 0.8
            },
            "walnut": {
                "patterns": [r'walnut', r'اخروٹ'],
                "protected": True,
                "min_confidence": 0.75
            }
        }
        
        # Location validation patterns
        self.location_patterns = {
            "division": {
                "patterns": [r'Division\s+([A-Z][a-z]+)', r'ڈویژن\s+([^\s،]+)'],
                "parent": "province",
                "min_confidence": 0.9
            },
            "range": {
                "patterns": [r'Range\s+([A-Z][a-z]+)', r'رینج\s+([^\s،]+)'],
                "parent": "division",
                "min_confidence": 0.85
            },
            "beat": {
                "patterns": [r'Beat\s+([A-Z][a-z]+)', r'بیٹ\s+([^\s،]+)'],
                "parent": "range",
                "min_confidence": 0.8
            }
        }
        
        # Penalty validation patterns
        self.penalty_patterns = {
            "fine": {
                "patterns": [
                    r'fine\s+of\s+Rs\.?\s*([\d,]+)',
                    r'جرمانہ\s+روپے\s*([\d,]+)',
                    r'Rs\.?\s*([\d,]+)\s+fine'
                ],
                "currency": "PKR",
                "min_confidence": 0.9
            },
            "compensation": {
                "patterns": [
                    r'compensation\s+of\s+Rs\.?\s*([\d,]+)',
                    r'ہرجہ\s+روپے\s*([\d,]+)'
                ],
                "currency": "PKR",
                "min_confidence": 0.85
            }
        }
        
        # Amendment validation patterns
        self.amendment_patterns = {
            "substitution": {
                "patterns": [r'Substituted\s+by\s+(.+)', r'متبادل\s+بذریعہ\s+(.+)'],
                "min_confidence": 0.95
            },
            "insertion": {
                "patterns": [r'Inserted\s+by\s+(.+)', r'شامل\s+بذریعہ\s+(.+)'],
                "min_confidence": 0.95
            },
            "deletion": {
                "patterns": [r'Deleted\s+by\s+(.+)', r'خارج\s+بذریعہ\s+(.+)'],
                "min_confidence": 0.95
            }
        }
        
        # Court Case validation patterns (Broad to accept LLM suggestions)
        self.court_patterns = {
            "judge": {
                "patterns": [r'.+'], # Accept anything the LLM highly confident about
                "min_confidence": 0.5
            },
            "party": {
                "patterns": [r'.+'],
                "min_confidence": 0.5
            },
            "verdict": {
                "patterns": [r'.+'],
                "min_confidence": 0.5
            }
        }
    
    def initialize_fallback_patterns(self):
        """Initialize fallback patterns for when LLM is unavailable"""
        
        # Fallback regex patterns (used when LLM unavailable)
        self.fallback_regex = {
            "OFFICER": [
                (r'\b(?:Divisional Forest Officer|DFO)\b', "DFO", 0.9),
                (r'\b(?:Sub-Divisional Forest Officer|SDFO)\b', "SDFO", 0.9),
                (r'\b(?:Range Officer|RO|رینج آفیسر)\b', "Range Officer", 0.8),
                (r'\b(?:Beat Guard|BG|بیٹ گارڈ)\b', "Beat Guard", 0.8),
                (r'\b(?:Forest Guard|FG|فورسٹ گارڈ)\b', "Forest Guard", 0.8),
            ],
            "SPECIES": [
                (r'\b(deodar|cedar|دیار)\b', "Deodar", 0.85),
                (r'\b(chir\s+pine|chirpine|چیر)\b', "Chir Pine", 0.8),
                (r'\b(kail|blue\s+pine|کائل)\b', "Kail", 0.8),
                (r'\b(walnut|اخروٹ)\b', "Walnut", 0.75),
                (r'\b(oak|شاہ بلوط)\b', "Oak", 0.7),
                (r'\b(poplar|پوپلر)\b', "Poplar", 0.7),
            ],
            "LOCATION": [
                (r'Division\s+([A-Z][a-z]+)', "Division", 0.9),
                (r'Range\s+([A-Z][a-z]+)', "Range", 0.85),
                (r'Beat\s+([A-Z][a-z]+)', "Beat", 0.8),
                (r'ڈویژن\s+([^\s،]+)', "ڈویژن", 0.85),
                (r'رینج\s+([^\s،]+)', "رینج", 0.8),
                (r'بیٹ\s+([^\s،]+)', "بیٹ", 0.75),
            ],
            "PENALTY": [
                (r'fine\s+of\s+Rs\.?\s*([\d,]+)', "Fine", 0.9),
                (r'Rs\.?\s*([\d,]+)\s+fine', "Fine", 0.9),
                (r'جرمانہ\s+روپے\s*([\d,]+)', "جرمانہ", 0.85),
                (r'compensation\s+of\s+Rs\.?\s*([\d,]+)', "Compensation", 0.8),
                (r'ہرجہ\s+روپے\s*([\d,]+)', "ہرجہ", 0.8),
            ],
            "AMENDMENT": [
                (r'\[(\d+)\]\s+(Substituted|Inserted|Omitted|Deleted)', "Amendment", 0.95),
                (r'Amended\s+by\s+(.+?)(?:\s+Act)?\s+(\d{4})', "Amendment", 0.9),
                (r'متروک\s+ہو\s+گیا\s+بذریعہ\s+(.+)', "متروک", 0.85),
            ]
        }
    
    def extract_with_assistance(self, text: str, context_metadata: Dict = None) -> Dict[str, Any]:
        """
        Extract entities with LLM assistance, validated by rules.
        
        Args:
            text: Text to analyze
            context_metadata: Document metadata for context
            
        Returns:
            Dictionary with extracted entities, suggestions, and validation results
        """
        logger.info(f"Starting LLM-assisted NER extraction (text length: {len(text)})")
        
        results = {
            "llm_suggestions": [],
            "validated_entities": [],
            "ambiguity_cases": [],
            "fallback_extractions": [],
            "abstention_decisions": [],
            "statistics": self.stats.copy(),
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "llm_used": self.llm_available,
                "text_length": len(text),
                "context_provided": context_metadata is not None
            }
        }
        
        try:
            # Step 1: Get LLM suggestions (or fallback)
            if self.llm_available:
                llm_suggestions = self._get_llm_suggestions(text, context_metadata)
                results["llm_suggestions"] = [asdict(s) for s in llm_suggestions]
                self.stats["llm_suggestions"] += len(llm_suggestions)
            else:
                llm_suggestions = []
                if self.use_llm_fallback:
                    fallback_results = self._fallback_extraction(text)
                    results["fallback_extractions"] = fallback_results
            
            # Step 2: Validate each LLM suggestion with rules
            validated_entities = []
            ambiguity_cases = []
            
            for suggestion in llm_suggestions:
                validation_result = self._validate_with_rules(suggestion, text)
                
                if validation_result["status"] == "validated":
                    validated_entities.append(validation_result["entity"])
                    self.stats["rule_validations"] += 1
                
                elif validation_result["status"] == "ambiguous":
                    ambiguity_case = AmbiguityCase(
                        llm_suggestion=suggestion,
                        rule_findings=validation_result["rule_findings"],
                        conflict_type=validation_result["conflict_type"]
                    )
                    ambiguity_cases.append(ambiguity_case)
                    self.stats["ambiguity_cases"] += 1
                    
                    # Decide if human review needed
                    if self._needs_human_review(ambiguity_case):
                        ambiguity_case.human_review_needed = True
                        self.stats["human_review_cases"] += 1
                
                elif validation_result["status"] == "rejected":
                    # Log as abstention
                    abstention = {
                        "type": "llm_suggestion_rejected",
                        "suggestion_id": suggestion.suggestion_id,
                        "reason": validation_result["reason"],
                        "llm_confidence": suggestion.llm_confidence,
                        "timestamp": datetime.now().isoformat()
                    }
                    results["abstention_decisions"].append(abstention)
                    self.stats["abstention_decisions"] += 1
            
            # Step 3: Process validated entities
            results["validated_entities"] = [asdict(e) for e in validated_entities]
            
            # Step 4: Process ambiguity cases
            results["ambiguity_cases"] = [asdict(c) for c in ambiguity_cases]
            
            # Step 5: Apply deterministic resolution for some ambiguities
            if ambiguity_cases:
                resolved = self._resolve_ambiguities_deterministically(ambiguity_cases, text)
                results["deterministic_resolutions"] = resolved
            
            # Forensic Invariants Injection (v2.3 Hardened)
            source_doc_id = context_metadata.get('document_id') or context_metadata.get('source_doc_id', 'unknown') if context_metadata else 'unknown'
            source_bbox = context_metadata.get('bbox') or context_metadata.get('logical_span', 'N/A') if context_metadata else 'N/A'
            
            for entity in results.get("validated_entities", []):
                # Inject into properties if present, else top-level
                target = entity.get("properties", entity)
                target["source_doc_id"] = source_doc_id
                target["bbox"] = source_bbox
                target["extraction_phase"] = "phase_4.2"
                if "confidence_score" not in target:
                    target["confidence_score"] = entity.get("final_confidence", entity.get("llm_confidence", 0.7))
            
            for case in results.get("ambiguity_cases", []):
                if isinstance(case, dict) and "llm_suggestion" in case:
                    case["llm_suggestion"]["source_doc_id"] = source_doc_id
                    case["llm_suggestion"]["bbox"] = source_bbox
                    case["llm_suggestion"]["extraction_phase"] = "phase_4.2"
            
            # CRITICAL FIX: Inject forensic metadata into fallback_extractions
            # Fallback extractions are used when validated_entities is empty
            for entity in results.get("fallback_extractions", []):
                if isinstance(entity, dict):
                    # Inject into metadata if present, else top-level
                    target = entity.get("metadata", entity)
                    target["source_doc_id"] = source_doc_id
                    target["bbox"] = source_bbox
                    target["extraction_phase"] = "phase_4.2_fallback"
                    if "confidence_score" not in target:
                        target["confidence_score"] = entity.get("confidence", 0.8)
            
            # Update statistics
            results["statistics"] = self.stats.copy()
            
            logger.info(f"NER extraction complete: {len(validated_entities)} entities validated")
            
        except Exception as e:
            logger.error(f"Error in NER extraction: {e}")
            results["error"] = str(e)
            results["success"] = False
        
        return results
    
    def _get_llm_suggestions(self, text: str, context_metadata: Dict = None) -> List[LLMSuggestion]:
        """
        Get entity suggestions from LLM.
        
        Args:
            text: Text to analyze
            context_metadata: Document metadata
            
        Returns:
            List of LLM suggestions
        """
        if not self.llm_client:
            return []
        
        try:
            # Prepare context-aware prompt
            prompt = self._create_llm_prompt(text, context_metadata)
            
            # Call LLM
            response = self.llm_client.generate(
                prompt=prompt,
                max_tokens=2000,
                temperature=0.1  # Low temperature for consistency
            )
            
            # Parse response
            suggestions = self._parse_llm_response(response, text)
            
            # Filter and deduplicate
            filtered_suggestions = self._filter_suggestions(suggestions)
            
            return filtered_suggestions
            
        except Exception as e:
            logger.error(f"LLM suggestion generation failed: {e}")
            return []
    
    def _create_llm_prompt(self, text: str, context_metadata: Dict = None) -> str:
        """Create prompt for LLM entity suggestion"""
        
        # Extract sample for prompt (first 1500 chars)
        sample_text = text[:1500]
        if len(text) > 1500:
            sample_text += "..."
        
        metadata_context = ""
        is_court_case = False
        if context_metadata:
            doc_type = context_metadata.get("document_type", "unknown")
            jurisdiction = context_metadata.get("jurisdiction", "KPK")
            file_name = context_metadata.get("file_name", "").lower()
            metadata_context = f"\nDocument Type: {doc_type}\nJurisdiction: {jurisdiction}"
            
            if doc_type.lower() in ["court_case", "judgment"] or any(x in file_name for x in ["scmr", "pld", "court", "case", "judgment", "vs"]):
                is_court_case = True

        if is_court_case:
            prompt = f"""
You are analyzing a Legal Court Case or Judgment from Pakistan/KPK. 
Identify the following specific entities in the text:
1. JUDGE (The names of the judges presiding over the case)
2. PARTY (The petitioner, respondent, appellant, or state involved)
3. VERDICT (The final outcome: e.g., "Appeal Dismissed", "Acquitted", "Sentenced")
4. PENALTY (Any fines, prison sentences, or compensation amounts)
5. LAW (Specific acts or sections explicitly invoked, e.g., "Section 27 of Forest Act")

IMPORTANT: Return ONLY a JSON list of suggestions.
For each suggestion, provide:
- Type: JUDGE, PARTY, VERDICT, PENALTY, or LAW
- Value: The actual entity value
- Original text: The exact text from the document
- Context: 2-3 sentences around the entity
- Confidence: Your confidence (0.0 to 1.0)

Example:
[
  {{
    "type": "JUDGE",
    "value": "Justice Qazi Faez Isa",
    "original_text": "Before Qazi Faez Isa, J",
    "context": "Before Qazi Faez Isa, J. The appellant challenges...",
    "confidence": 0.95
  }}
]

Document Metadata:{metadata_context}

Text to analyze:
{sample_text}

Return ONLY the JSON list:
"""
        else:
            prompt = f"""
You are analyzing a Khyber Pakhtunkhwa (KPK) forestry document. 
Identify potential entities in the text that might be:
1. FORESTRY OFFICERS (DFO, SDFO, RO, BG, etc.)
2. TREE SPECIES (Deodar, Chir Pine, Kail, etc. - include local names)
3. GEOGRAPHIC LOCATIONS (Divisions, Ranges, Beats in KPK)
4. PENALTY AMOUNTS (Fines in PKR, compensation amounts)
5. LEGAL AMENDMENTS (Changes to laws, notifications, SROs)
6. LAW REFERENCES (Section numbers, Act names)

IMPORTANT: You are ONLY SUGGESTING potential entities. The final decision will be made by deterministic rules.
For each suggestion, provide:
- Type: OFFICER, SPECIES, LOCATION, PENALTY, AMENDMENT, or LAW
- Value: The actual entity value
- Original text: The exact text from the document
- Context: 2-3 sentences around the entity
- Confidence: Your confidence (0.0 to 1.0)

Return as a JSON list. Example:
[
  {{
    "type": "OFFICER",
    "value": "Divisional Forest Officer",
    "original_text": "The Divisional Forest Officer may...",
    "context": "The Divisional Forest Officer may impose fines for illegal cutting...",
    "confidence": 0.9
  }}
]

Document Metadata:{metadata_context}

Text to analyze:
{sample_text}

Return ONLY the JSON list:
"""
        
        return prompt
    
    def _parse_llm_response(self, response: str, full_text: str) -> List[LLMSuggestion]:
        """Parse LLM response into suggestions"""
        suggestions = []
        
        try:
            # Try to extract JSON
            json_match = re.search(r'\[\s*\{.*\}\s*\]', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                data = json.loads(json_str)
                
                for item in data:
                    suggestion = LLMSuggestion(
                        entity_type=item.get("type", "").upper(),
                        value=item.get("value", ""),
                        original_text=item.get("original_text", ""),
                        context=item.get("context", ""),
                        llm_confidence=float(item.get("confidence", 0.5))
                    )
                    suggestions.append(suggestion)
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return []
    
    # Hardcoded stop words to prevent common hallucinations
    STOP_WORDS = {
        "is", "at", "the", "of", "in", "and", "or", "to", "for", 
        "with", "by", "on", "as", "an", "a", "it", "this", "that", 
        "which", "who", "what", "where", "when", "why", "how",
        "be", "been", "being", "have", "has", "had", "do", "does", "did",
        "uncategorized", "unknown", "none", "null", "n/a", "id", "no", "yes",
        "act", "law", "section", "rules", "rule", "provincial", "government",
        "kpk", "punjab", "pakistan", "gazette", "notification", "dated",
        "pursuant", "hereby", "thereof", "aforesaid", "herewith", "notwithstanding"
    }

    def _filter_suggestions(self, suggestions: List[LLMSuggestion]) -> List[LLMSuggestion]:
        """Filter and deduplicate suggestions"""
        filtered = []
        seen = set()
        
        for suggestion in suggestions:
            # Basic validation
            if not suggestion.entity_type or not suggestion.value:
                continue
            
            # CRITICAL FIX: Stop word and length filtering
            val_lower = suggestion.value.lower().strip()
            
            # 1. Stop Word Check
            if val_lower in self.STOP_WORDS:
                continue
                
            # 2. Length Check (unless it's an acronym like "KP" or "UN")
            if len(val_lower) < 3 and not val_lower.isupper():
                # Allow strictly uppercase acronyms of length 2
                if not (len(val_lower) == 2 and suggestion.value.isupper()):
                    continue
            
            # 3. Confidence Check
            if suggestion.llm_confidence < 0.3:  # Very low confidence
                continue
            
            # Deduplicate based on type, value, and context hash
            key = f"{suggestion.entity_type}:{suggestion.value}:{hash(suggestion.context) % 10000}"
            if key in seen:
                continue
            
            filtered.append(suggestion)
            seen.add(key)
        
        return filtered
    
    def _validate_with_rules(self, suggestion: LLMSuggestion, full_text: str) -> Dict[str, Any]:
        """
        Validate LLM suggestion using deterministic rules.
        
        Returns:
            Dict with validation result
        """
        entity_type = suggestion.entity_type
        value = suggestion.value
        context = suggestion.context
        
        validation_results = {
            "suggestion_id": suggestion.suggestion_id,
            "status": "pending",
            "rule_findings": [],
            "conflict_type": None,
            "reason": ""
        }
        
        # Get appropriate validation patterns
        patterns = self._get_validation_patterns(entity_type)
        
        if not patterns:
            validation_results["status"] = "ambiguous"
            validation_results["conflict_type"] = "no_validation_patterns"
            validation_results["reason"] = "No validation patterns for this entity type"
            return validation_results
        
        # Check if value matches any validation pattern
        matches = []
        for pattern_key, pattern_info in patterns.items():
            for pattern in pattern_info.get("patterns", []):
                try:
                    # Check if pattern matches the value or context
                    regex = re.compile(pattern, re.IGNORECASE | re.UNICODE)
                    
                    # Check value
                    if regex.search(value):
                        matches.append({
                            "pattern_key": pattern_key,
                            "matched_value": value,
                            "validation_type": "value_match",
                            "confidence": pattern_info.get("min_confidence", 0.7)
                        })
                    
                    # Check context
                    if regex.search(context):
                        matches.append({
                            "pattern_key": pattern_key,
                            "matched_value": "context_match",
                            "validation_type": "context_match",
                            "confidence": pattern_info.get("min_confidence", 0.7) * 0.9
                        })
                    
                    # Check original text
                    if regex.search(suggestion.original_text):
                        matches.append({
                            "pattern_key": pattern_key,
                            "matched_value": suggestion.original_text,
                            "validation_type": "original_text_match",
                            "confidence": pattern_info.get("min_confidence", 0.7) * 0.95
                        })
                        
                except re.error as e:
                    logger.debug(f"Regex error: {e}")
                    continue
        
        validation_results["rule_findings"] = matches
        
        # Determine validation status
        if matches:
            # Calculate overall validation confidence
            match_confidence = max([m.get("confidence", 0) for m in matches], default=0)
            
            # Compare with LLM confidence
            confidence_ratio = match_confidence / suggestion.llm_confidence if suggestion.llm_confidence > 0 else 1
            
            if confidence_ratio > 0.7:  # Rules generally agree with LLM
                if IDENTITY_LOADED:
                    id_spec = IdentityFactory.canonicalize(value, role=entity_type)
                    suggestion.rule_validation["identity"] = id_spec

                validation_results["status"] = "validated"
                validation_results["entity"] = ValidatedEntity(
                    entity_type=entity_type,
                    value=value,
                    original_text=suggestion.original_text,
                    context=context,
                    final_confidence=min(match_confidence, suggestion.llm_confidence),
                    llm_suggestion_id=suggestion.suggestion_id,
                    validation_method="rule_validation",
                    validated_by=[m["pattern_key"] for m in matches],
                    metadata={
                        "validation_confidence_ratio": confidence_ratio,
                        **(suggestion.rule_validation.get("identity", {}) if IDENTITY_LOADED else {})
                    }
                )
            
            elif confidence_ratio < 0.3:  # Rules strongly disagree
                validation_results["status"] = "rejected"
                validation_results["conflict_type"] = "confidence_disagreement"
                validation_results["reason"] = f"Rule confidence ({match_confidence:.2f}) much lower than LLM confidence ({suggestion.llm_confidence:.2f})"
            
            else:  # Some disagreement
                validation_results["status"] = "ambiguous"
                validation_results["conflict_type"] = "confidence_disagreement"
                validation_results["reason"] = f"Moderate confidence disagreement: rules={match_confidence:.2f}, LLM={suggestion.llm_confidence:.2f}"
        
        else:  # No rule matches
            validation_results["status"] = "ambiguous"
            validation_results["conflict_type"] = "no_rule_matches"
            validation_results["reason"] = "No deterministic rules matched this suggestion"
        
        return validation_results
    
    def _get_validation_patterns(self, entity_type: str) -> Dict:
        """Get validation patterns for entity type"""
        pattern_maps = {
            "OFFICER": self.officer_patterns,
            "SPECIES": self.species_patterns,
            "LOCATION": self.location_patterns,
            "PENALTY": self.penalty_patterns,
            "AMENDMENT": self.amendment_patterns,
            "JUDGE": self.court_patterns,
            "PARTY": self.court_patterns,
            "VERDICT": self.court_patterns
        }
        return pattern_maps.get(entity_type, {})
    
    def _needs_human_review(self, ambiguity_case: AmbiguityCase) -> bool:
        """Determine if ambiguity case needs human review"""
        
        # Cases that definitely need human review
        if ambiguity_case.conflict_type == "no_rule_matches":
            return True
        
        # Check confidence levels
        llm_conf = ambiguity_case.llm_suggestion.llm_confidence
        if llm_conf > 0.8 and ambiguity_case.conflict_type == "confidence_disagreement":
            # High LLM confidence but rules disagree - needs review
            return True
        
        # Legal entities always need review if ambiguous
        entity_type = ambiguity_case.llm_suggestion.entity_type
        if entity_type in ["LAW", "AMENDMENT", "PENALTY"]:
            return True
        
        return False
    
    def _resolve_ambiguities_deterministically(self, 
                                              ambiguity_cases: List[AmbiguityCase],
                                              text: str) -> List[Dict]:
        """
        Try to resolve some ambiguities using deterministic rules.
        """
        resolutions = []
        
        for case in ambiguity_cases:
            if case.human_review_needed:
                continue  # Skip cases marked for human review
            
            resolution = self._resolve_single_ambiguity(case, text)
            if resolution["resolved"]:
                resolutions.append(resolution)
                case.resolution = resolution["resolution"]
        
        return resolutions
    
    def _resolve_single_ambiguity(self, 
                                 ambiguity_case: AmbiguityCase,
                                 text: str) -> Dict[str, Any]:
        """
        Try to resolve a single ambiguity case.
        """
        entity_type = ambiguity_case.llm_suggestion.entity_type
        value = ambiguity_case.llm_suggestion.value
        
        resolution = {
            "suggestion_id": ambiguity_case.llm_suggestion.suggestion_id,
            "resolved": False,
            "resolution": "unresolved",
            "method": "",
            "confidence": 0.0
        }
        
        # Strategy 1: Check if entity appears multiple times in document
        if text.count(value) > 2:
            # Entity mentioned multiple times - likely correct
            resolution["resolved"] = True
            resolution["resolution"] = "llm_correct"
            resolution["method"] = "frequency_analysis"
            resolution["confidence"] = min(0.8, ambiguity_case.llm_suggestion.llm_confidence)
        
        # Strategy 2: Check proximity to known patterns
        elif self._check_proximity_to_known_patterns(value, text, entity_type):
            resolution["resolved"] = True
            resolution["resolution"] = "llm_correct"
            resolution["method"] = "proximity_analysis"
            resolution["confidence"] = 0.7
        
        # Strategy 3: For species, check against known KPK species
        elif entity_type == "SPECIES" and KPK_CONFIG_LOADED:
            if value.lower() in [s.lower() for s in KPK_TREE_SPECIES.keys()]:
                resolution["resolved"] = True
                resolution["resolution"] = "llm_correct"
                resolution["method"] = "config_validation"
                resolution["confidence"] = 0.85
        
        return resolution
    
    def _check_proximity_to_known_patterns(self, value: str, text: str, entity_type: str) -> bool:
        """Check if value appears near known patterns of same type"""
        
        # Find position of value in text
        match = re.search(re.escape(value), text, re.IGNORECASE)
        if not match:
            return False
        
        pos = match.start()
        
        # Look for known patterns within 200 characters
        window_start = max(0, pos - 200)
        window_end = min(len(text), pos + 200)
        context_window = text[window_start:window_end]
        
        # Get patterns for this entity type
        patterns = self._get_validation_patterns(entity_type)
        
        for pattern_key, pattern_info in patterns.items():
            for pattern in pattern_info.get("patterns", []):
                try:
                    if re.search(pattern, context_window, re.IGNORECASE | re.UNICODE):
                        return True
                except re.error:
                    continue
        
        return False
    
    def _fallback_extraction(self, text: str) -> List[Dict]:
        """
        Fallback extraction when LLM is unavailable.
        Uses regex patterns to extract entities.
        """
        extracted = []
        
        for entity_type, patterns in self.fallback_regex.items():
            for pattern, label, confidence in patterns:
                try:
                    regex = re.compile(pattern, re.IGNORECASE | re.UNICODE)
                    matches = regex.finditer(text)
                    
                    for match in matches:
                        # Extract value based on pattern
                        if match.groups():
                            value = match.group(1) if match.group(1) else match.group(0)
                        else:
                            value = match.group(0)
                        
                        # Get context
                        context = self._get_context(text, match.start(), match.end())
                        
                        entity = {
                            "type": entity_type,
                            "value": value,
                            "label": label,
                            "original_text": match.group(0),
                            "context": context,
                            "confidence": confidence,
                            "method": "regex_fallback",
                            "deterministic": True
                        }
                        
                        if IDENTITY_LOADED:
                            entity["metadata"] = IdentityFactory.canonicalize(value, role=entity_type)
                        
                        extracted.append(entity)
                        
                except re.error as e:
                    logger.debug(f"Regex error in fallback: {e}")
                    continue
        
        # Deduplicate
        seen = set()
        deduplicated = []
        for entity in extracted:
            key = f"{entity['type']}:{entity['value']}:{hash(entity['context']) % 10000}"
            if key not in seen:
                deduplicated.append(entity)
                seen.add(key)
        
        return deduplicated
    
    def _get_context(self, text: str, start: int, end: int, window: int = 200) -> str:
        """Get context window around position"""
        context_start = max(0, start - window)
        context_end = min(len(text), end + window)
        return text[context_start:context_end].strip()
    
    def batch_extract(self, texts: List[str], metadata_list: List[Dict] = None) -> List[Dict]:
        """
        Batch extraction for multiple documents.
        
        Args:
            texts: List of text documents
            metadata_list: Optional list of metadata dicts
            
        Returns:
            List of extraction results
        """
        results = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            
            for i, text in enumerate(texts):
                metadata = metadata_list[i] if metadata_list and i < len(metadata_list) else None
                future = executor.submit(self.extract_with_assistance, text, metadata)
                futures.append(future)
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"Error in batch extraction: {e}")
                    results.append({"error": str(e)})
        
        return results


# ========== INTEGRATION WITH PIPELINE ==========

class NERProcessor:
    """
    Main processor for integrating NER extraction into the pipeline.
    Handles coordination between LLM suggestions and rule validation.
    """
    
    def __init__(self, llm_client=None):
        self.extractor = KPKNERExtractor(llm_client)
        
    def process_document(self, document_data: Dict) -> Dict:
        """
        Process a document through the NER pipeline.
        
        Args:
            document_data: Dictionary containing 'normalized_text' and metadata
            
        Returns:
            Enhanced document data with NER results
        """
        try:
            text = document_data.get('normalized_text', '')
            metadata = document_data.get('metadata', {})
            
            # Extract entities with LLM assistance
            ner_results = self.extractor.extract_with_assistance(text, metadata)
            
            # Enhance document data
            document_data['ner_extraction'] = ner_results
            document_data['ner_timestamp'] = datetime.now().isoformat()
            
            # Generate summary for pipeline
            summary = self._generate_summary(ner_results)
            document_data['ner_summary'] = summary
            
            return document_data
            
        except Exception as e:
            logger.error(f"Error in NER processing: {e}")
            document_data['ner_extraction'] = {"error": str(e)}
            return document_data
    
    def _generate_summary(self, ner_results: Dict) -> Dict:
        """Generate summary of NER extraction"""
        validated = ner_results.get('validated_entities', [])
        ambiguities = ner_results.get('ambiguity_cases', [])
        
        entity_counts = Counter()
        for entity in validated:
            entity_counts[entity.get('entity_type', 'UNKNOWN')] += 1
        
        return {
            "total_validated": len(validated),
            "entity_type_counts": dict(entity_counts),
            "ambiguity_cases": len(ambiguities),
            "human_review_needed": sum(1 for c in ambiguities if c.get('human_review_needed', False)),
            "llm_suggestions": ner_results.get('statistics', {}).get('llm_suggestions', 0),
            "rule_validations": ner_results.get('statistics', {}).get('rule_validations', 0)
        }


# ========== COMMAND LINE INTERFACE ==========

def main():
    """Command line interface for NER extraction"""
    import argparse
    
    parser = argparse.ArgumentParser(description="LLM-assisted NER extraction for KPK forestry documents")
    parser.add_argument("--input", "-i", required=True, help="Input JSON file from normalization")
    parser.add_argument("--output", "-o", help="Output JSON file")
    parser.add_argument("--use-llm", action="store_true", help="Use LLM if available")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Load document data
        with open(args.input, 'r', encoding='utf-8') as f:
            document_data = json.load(f)
        
        # Initialize processor (with or without LLM)
        llm_client = None
        if args.use_llm:
            try:
                import ollama
                llm_client = ollama
                print("✓ LLM available for NER extraction")
            except ImportError:
                print("⚠️ Ollama not available, using fallback patterns")
        
        processor = NERProcessor(llm_client)
        result = processor.process_document(document_data)
        
        # Print summary
        summary = result.get('ner_summary', {})
        print("\n" + "=" * 60)
        print("NER EXTRACTION RESULTS")
        print("=" * 60)
        
        print(f"Validated Entities: {summary.get('total_validated', 0)}")
        for entity_type, count in summary.get('entity_type_counts', {}).items():
            print(f"  {entity_type}: {count}")
        
        print(f"\nLLM Suggestions: {summary.get('llm_suggestions', 0)}")
        print(f"Rule Validations: {summary.get('rule_validations', 0)}")
        print(f"Ambiguity Cases: {summary.get('ambiguity_cases', 0)}")
        print(f"Human Review Needed: {summary.get('human_review_needed', 0)}")
        
        # Show sample validated entities
        ner_results = result.get('ner_extraction', {})
        validated = ner_results.get('validated_entities', [])
        if validated:
            print(f"\nSample Validated Entities:")
            for i, entity in enumerate(validated[:3]):
                print(f"  {i+1}. {entity.get('entity_type')}: {entity.get('value')} "
                      f"(Confidence: {entity.get('final_confidence', 0):.0%})")
        
        # Save if output specified
        if args.output:
            os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else '.', exist_ok=True)
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"\nResults saved to: {args.output}")
        
        print("\n" + "=" * 60)
        print("NER extraction complete. Remember: 'LLM suggests, Rules decide' ✓")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


if __name__ == "__main__":
    main()
