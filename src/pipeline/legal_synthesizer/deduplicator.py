# #E:\GL_AI\src\pipeline\legal_synthesizer\deduplicator.py
# import re
# from typing import List, Dict, Any
# import numpy as np
# from sklearn.metrics.pairwise import cosine_similarity
# from difflib import SequenceMatcher

# try:
#     from sentence_transformers import SentenceTransformer
# except ImportError:
#     SentenceTransformer = None

# class Deduplicator:
#     """
#     V3: Statutory Reasoning Engine Deduplicator.
#     Removes semantic duplicates at SENTENCE level and enforces Legal Concept Keying.
#     """

#     def __init__(self, similarity_threshold: float = 0.85):
#         self.similarity_threshold = similarity_threshold
#         if SentenceTransformer:
#             try:
#                 self.model = SentenceTransformer("all-MiniLM-L6-v2")
#             except Exception:
#                 self.model = None
#         else:
#             self.model = None

#     def _normalize(self, text: str) -> str:
#         """Relaxed normalization (V5): Preserves numeric integrity (fines, commas, sections)."""
#         if not text: return ""
#         text = text.lower()
#         # Preserve numbers, commas, and legal punctuation essential for fines/sections
#         text = re.sub(r'[^\w\s.,:/()-]', '', text)
#         return text.strip()

#     def clean_raw_text(self, text: str) -> str:
#         """Surgical OCR Repair (V5): Fixes leading fragments and artifacts."""
#         if not text: return ""
#         text = text.strip()

#         # Fix leading broken characters
#         text = re.sub(r'^[^A-Za-z"0-9]+', '', text)

#         # Fix common OCR leading fragment failures
#         text = re.sub(r'^He\s+Forest', 'The Forest', text) # "He Forest" -> "The Forest"
#         text = re.sub(r'^F\s+a\s+forest', 'If a forest', text) # "F a forest" -> "If a forest"

#         # Auto-capitalize first letter if needed
#         if text and text[0].islower():
#             text = text[0].upper() + text[1:]
            
#         # Drop fragments shorter than 4-5 words UNLESS they contain legal keys (Rs., Section)
#         has_legal_key = any(k in text for k in ["Rs.", "Rs", "Section", "Schedule"])
#         if len(text.split()) < 5 and not has_legal_key:
#             return ""

#         return text

#     def validate_numeric_integrity(self, text: str):
#         """CRITICAL: Ensures legal fine amounts (Rs.) are not truncated or corrupt."""
#         if "Rs." in text and not re.search(r'Rs\.\s*\d', text):
#             # If Rs. exists but is not followed by a digit, something is wrong.
#             return False
#         return True

#     def _extract_legal_keys(self, text: str) -> set:
#         """Extracts hard keys: monetary amounts, sections, species."""
#         keys = set()
#         text_low = text.lower()
        
#         # 1. Monetary (Rs. 206,000) - Preserve comma for hard key
#         money = re.findall(r'rs\.?\s*[\d,]+', text_low)
#         keys.update(money)
        
#         # 2. Species (Deodar, Chir, etc)
#         species = ["deodar", "diyar", "chir", "kail", "spruce", "fir"]
#         for s in species:
#             if s in text_low:
#                 keys.add(s)
                
#         # 3. Sections (Section 45)
#         sections = re.findall(r'section\s*\d+', text_low)
#         keys.update(sections)
        
#         return keys

#     def deduplicate(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
#         """
#         V4 Surgical Sentence-Level Deduplication.
#         Splits chunks ONLY on sentence terminators, never on commas.
#         """
#         unique_chunks = []
#         seen_sentence_embeddings = []
#         seen_legal_keys = set()

#         for chunk in chunks:
#             raw_text = chunk.get("text", "")
#             if len(raw_text) < 15: continue
            
#             # Clean raw text BEFORE processing
#             raw_text = self.clean_raw_text(raw_text)
#             if not raw_text: continue

#             # 1. Split into sentences - strictly avoid commas
#             raw_sentences = re.split(r'(?<=[.;:])\s+', raw_text)
#             kept_sentences = []
            
#             for sent in raw_sentences:
#                 sent = sent.strip()
#                 if len(sent) < 10: continue
                
#                 norm_sent = self._normalize(sent)
                
#                 # 2. Hard Key Check (Deterministic)
#                 keys = self._extract_legal_keys(norm_sent)
#                 if keys and keys.issubset(seen_legal_keys):
#                     continue
                
#                 # 3. Semantic Similarity
#                 is_dup = False
#                 if self.model:
#                     vec = self.model.encode(norm_sent)
#                     for existing_vec in seen_sentence_embeddings:
#                         score = cosine_similarity(
#                             np.array(vec).reshape(1, -1),
#                             np.array(existing_vec).reshape(1, -1)
#                         )[0][0]
#                         if score > self.similarity_threshold:
#                             is_dup = True
#                             break
                    
#                     if not is_dup:
#                         kept_sentences.append(sent)
#                         seen_sentence_embeddings.append(vec)
#                         seen_legal_keys.update(keys)
#                 else:
#                     kept_sentences.append(sent)
            
#             if kept_sentences:
#                 new_chunk = chunk.copy()
#                 new_chunk["text"] = " ".join(kept_sentences)
#                 unique_chunks.append(new_chunk)
                
#         return unique_chunks

#     def postprocess_text(self, text: str) -> str:
#         """Final cleanup of LLM output: numeric validation and sentence uniqueness."""
#         if not text: return ""
        
#         # Split into sentences - preserve decimal points in numbers
#         sentences = re.split(r'(?<=[.!?])\s+', text)
#         unique_sents = []
#         seen_norms = set()
        
#         for s in sentences:
#             s = self.clean_raw_text(s)
            
#             # Numeric Integrity Guard
#             if not self.validate_numeric_integrity(s):
#                 continue
                
#             norm = self._normalize(s)
#             if norm not in seen_norms and len(norm) > 10:
#                 unique_sents.append(s)
#                 seen_norms.add(norm)
                
#         return " ".join(unique_sents)




import re
from typing import List, Dict, Any
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

class Deduplicator:
    """
    V6: Fluent Response Deduplicator.
    Preserves natural language flow while removing true duplicates.
    """

    def __init__(self, similarity_threshold: float = 0.92):
        self.similarity_threshold = similarity_threshold
        if SentenceTransformer:
            try:
                from utils.model_registry import model_registry
                self.model = model_registry.get_model("all-MiniLM-L6-v2")
            except Exception:
                self.model = None
        else:
            self.model = None

    def clean_raw_text(self, text: str) -> str:
        """Minimal cleaning - only remove obvious OCR artifacts, preserve everything else."""
        if not text: return ""
        
        # Remove only the most obvious OCR failures
        text = re.sub(r'^[^A-Za-z0-9"{]+', '', text)
        text = re.sub(r'He\s+Forest', 'The Forest', text)
        
        # Don't drop short texts - they might be valid definitions
        return text.strip()

    def _normalize_for_comparison(self, text: str) -> str:
        """Normalize only for duplicate comparison, not for display."""
        if not text: return ""
        text = text.lower()
        # Remove punctuation and extra spaces for comparison only
        text = re.sub(r'[^\w\s]', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def deduplicate(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Preserve full paragraphs, remove only near-identical duplicates.
        """
        if not chunks:
            return []
            
        unique_chunks = []
        seen_texts = []
        
        for chunk in chunks:
            raw_text = chunk.get("text", "")
            if not raw_text or len(raw_text) < 10:
                continue
                
            # Clean but don't split into sentences
            cleaned_text = self.clean_raw_text(raw_text)
            if not cleaned_text:
                continue
            
            # Normalize for comparison
            norm_text = self._normalize_for_comparison(cleaned_text)
            
            # Check if this is a duplicate
            is_duplicate = False
            
            if self.model and len(seen_texts) > 0:
                # Semantic deduplication for longer texts
                if len(norm_text.split()) > 10:
                    vec = self.model.encode(norm_text)
                    for existing_vec in seen_texts:
                        if isinstance(existing_vec, np.ndarray):
                            score = cosine_similarity(
                                np.array(vec).reshape(1, -1),
                                np.array(existing_vec).reshape(1, -1)
                            )[0][0]
                            if score > self.similarity_threshold:
                                is_duplicate = True
                                break
                else:
                    # Short texts: exact or near-exact match only
                    if any(self._normalize_for_comparison(ex) == norm_text for ex in seen_texts if isinstance(ex, str)):
                        is_duplicate = True
                    elif any(self._fuzzy_match(norm_text, self._normalize_for_comparison(ex)) for ex in seen_texts if isinstance(ex, str)):
                        is_duplicate = True
            
            if not is_duplicate:
                # Store both the embedding (if available) and the normalized text
                if self.model and len(norm_text.split()) > 10:
                    vec = self.model.encode(norm_text)
                    seen_texts.append(vec)
                else:
                    seen_texts.append(norm_text)
                
                # Keep the original chunk with cleaned text
                new_chunk = chunk.copy()
                new_chunk["text"] = cleaned_text
                unique_chunks.append(new_chunk)
        
        return unique_chunks
    
    def _fuzzy_match(self, text1: str, text2: str, threshold: float = 0.95) -> bool:
        """Simple character-based similarity for short texts."""
        if not text1 or not text2:
            return False
        
        # Quick length check
        if abs(len(text1) - len(text2)) > 5:
            return False
        
        # Count matching characters in sequence
        matches = 0
        min_len = min(len(text1), len(text2))
        for i in range(min_len):
            if text1[i] == text2[i]:
                matches += 1
        
        similarity = matches / max(len(text1), len(text2))
        return similarity > threshold

    def postprocess_text(self, text: str) -> str:
        """Minimal post-processing - just ensure clean spacing."""
        if not text:
            return ""
        
        # Fix spacing issues
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\s+([.,;:!?])', r'\1', text)
        
        return text.strip()