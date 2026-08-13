from typing import List, Dict, Any
from loguru import logger
import re
from difflib import SequenceMatcher

# ==============================
# Configuration
# ==============================

SIMILARITY_THRESHOLD = 0.70   # how close a sentence must be to source text
MIN_SENTENCE_LENGTH = 20     # ignore short noise sentences


# ==============================
# Utilities
# ==============================

def normalize(text: str) -> str:
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s\-]", "", text)
    return text.strip()


def split_sentences(text: str) -> List[str]:
    """Simple sentence splitter (deterministic, no NLP models)."""
    if not text:
        return []
    parts = re.split(r"[.!?]\s+", text)
    return [p.strip() for p in parts if len(p.strip()) >= MIN_SENTENCE_LENGTH]


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


# ==============================
# Core Mapping Logic
# ==============================

def map_sentence_to_sources(
    sentence: str,
    source_chunks: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    matches = []
    norm_sentence = normalize(sentence)

    for chunk in source_chunks:
        chunk_text = chunk.get("text", "")
        if not chunk_text:
            continue

        norm_chunk = normalize(chunk_text)
        score = similarity(norm_sentence, norm_chunk)

        if score >= SIMILARITY_THRESHOLD:
            matches.append({
                "document": chunk.get("document"),
                "section": chunk.get("section"),
                "clause": chunk.get("clause"),
                "score": round(score, 4),
                "chunk_id": chunk.get("id")
            })

    return sorted(matches, key=lambda x: x["score"], reverse=True)


# ==============================
# Public API
# ==============================

def build_citation_map(
    generated_text: str,
    source_chunks: List[Dict[str, Any]]
) -> Dict[str, Any]:
    if not generated_text:
        return {"sentences": [], "unmapped_sentences": [], "coverage_ratio": 0.0}

    if not source_chunks:
        return {"sentences": [], "unmapped_sentences": split_sentences(generated_text), "coverage_ratio": 0.0}

    sentences = split_sentences(generated_text)
    mapped = []
    unmapped = []

    for sent in sentences:
        matches = map_sentence_to_sources(sent, source_chunks)
        if matches:
            mapped.append({"text": sent, "sources": matches})
        else:
            unmapped.append(sent)

    coverage_ratio = len(mapped) / max(len(sentences), 1)
    return {
        "sentences": mapped,
        "unmapped_sentences": unmapped,
        "coverage_ratio": round(coverage_ratio, 4)
    }

def citation_mapper(response: Any) -> List[Dict[str, Any]]:
    """
    Coordinator-level citation mapping wrapper.
    Accepts CanonicalAgentResponse and returns list of mapped sources.
    
    Handles two data formats:
    1. source_chunks as list of dicts (full chunk objects) → sentence-level mapping
    2. source_chunks as list of strings (chunk IDs) → falls back to citation objects
    """
    if not hasattr(response, "legal_explanation"):
        logger.error(f"[CitationMap] SCHEMA VIOLATION: Expected CanonicalAgentResponse, got {type(response)}")
        return []

    generated_text = response.legal_explanation
    source_chunks = getattr(response, "source_chunks", [])
    citations = getattr(response, "citations", [])

    # Strategy 1: Full chunk objects available → do sentence-level mapping
    chunks_to_map = []
    for chunk in source_chunks:
        if isinstance(chunk, dict):
            chunks_to_map.append(chunk)
    
    if chunks_to_map:
        result = build_citation_map(generated_text, chunks_to_map)
        unique_sources = {}
        for sent in result.get("sentences", []):
            for src in sent.get("sources", []):
                key = f"{src.get('document')}_{src.get('section')}_{src.get('clause')}"
                unique_sources[key] = src
        return list(unique_sources.values())
    
    # Strategy 2: Only string IDs or empty → extract from citation objects directly
    if citations:
        unique_sources = {}
        for cit in citations:
            if isinstance(cit, dict):
                doc = cit.get("document", "")
                sec = cit.get("section", "")
                clause = cit.get("clause", "")
            else:
                doc = getattr(cit, "document", "")
                sec = getattr(cit, "section", "")
                clause = getattr(cit, "clause", "")
            
            if doc:
                key = f"{doc}_{sec}_{clause}"
                unique_sources[key] = {
                    "document": doc,
                    "section": sec,
                    "clause": clause,
                    "score": 1.0,
                    "chunk_id": getattr(cit, "chunk_id", None) if not isinstance(cit, dict) else cit.get("chunk_id")
                }
        return list(unique_sources.values())
    
    return []