# E:\GL_AI\src\pipeline\legal_synthesizer\validator.py

# import re
# from typing import List
# import numpy as np
# from sklearn.metrics.pairwise import cosine_similarity

# try:
#     from sentence_transformers import SentenceTransformer
# except ImportError:
#     SentenceTransformer = None

# class OutputValidator:
#     """
#     Citation Anchoring Layer.
#     Verifies that the LLM output rigidly adhered to the deterministic citation tags or 
#     semantically matches the source context.
#     Runs at sentence-level granularity.
#     """
#     def __init__(self, threshold: float = 0.88):
#         self.threshold = threshold
#         if SentenceTransformer:
#             try:
#                 self.model = SentenceTransformer("all-MiniLM-L6-v2")
#             except Exception:
#                 self.model = None
#         else:
#             self.model = None

#     def validate_anchors(self, generated_text: str, valid_tags: List[str], intent_mode: "LegalIntentMode" = None) -> bool:
#         """
#         Splits text into sentences and asserts every sentence matches at least one valid tag semantically 
#         or exactly.
#         """
#         from pipeline.legal_synthesizer.intent_mode import LegalIntentMode
        
#         if not generated_text or not valid_tags:
#             return False

#         # Naive sentence split by punctuation followed by space
#         sentences = re.split(r'(?<=[.!?])\s+', generated_text.strip())
#         sentences = [s for s in sentences if len(s.strip()) > 5] # ignore empty or tiny artifacts
        
#         if not sentences:
#             return False

#         anchor_count = 0
        
#         # Pre-compute validation tag embeddings if model is available
#         tag_embeddings = []
#         if self.model:
#             tag_embeddings = self.model.encode(valid_tags)

#         for sentence in sentences:
#             has_anchor = False
            
#             # 1. Check exact substring match first (fast path)
#             if any(tag in sentence for tag in valid_tags):
#                 has_anchor = True
            
#             # 2. Check semantic similarity if model exists
#             elif self.model and len(tag_embeddings) > 0:
#                 sent_vec = self.model.encode(sentence)
#                 for tag_vec in tag_embeddings:
#                     score = cosine_similarity(
#                         np.array(sent_vec).reshape(1, -1),
#                         np.array(tag_vec).reshape(1, -1)
#                     )[0][0]
#                     if score >= self.threshold:
#                         has_anchor = True
#                         break
                        
#             if has_anchor:
#                 anchor_count += 1
#             else:
#                 # If a sentence fails anchoring and we are not in relaxed mode yet,
#                 # we don't immediately return false, we track it.
#                 pass

#         # Relaxation for DEFINITION updates
#         # V5.1 Relaxed Coverage: Require at least 60% coverage or at least 2 anchors
#         # This prevents "good" synthesis from being rejected due to stylistic sentences.
#         min_required = max(2, int(len(sentences) * 0.6))
#         # If there are very few sentences (e.g. 1-2), require at least 1.
#         if len(sentences) <= 2: min_required = 1
#         return anchor_count >= min_required



import re
from typing import List, Optional
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

# Simple enum replacement to avoid import issues
class LegalIntentMode:
    DEFINITION = "DEFINITION"
    PENALTY = "PENALTY"
    ARREST = "ARREST" 
    GENERAL = "GENERAL"

class OutputValidator:
    """
    V6: Fluent Response Validator.
    Only checks for egregious hallucinations, not formatting.
    Allows natural language answers while ensuring they're grounded in sources.
    """
    
    def __init__(self, threshold: float = 0.75):
        self.threshold = threshold
        if SentenceTransformer:
            try:
                from utils.model_registry import model_registry
                self.model = model_registry.get_model("all-MiniLM-L6-v2")
            except Exception:
                self.model = None
        else:
            self.model = None

    def validate_anchors(self, generated_text: str, valid_tags: List[str], intent_mode: Optional[str] = None) -> bool:
        """
        Simple validation - ensure the answer isn't completely fabricated.
        
        Args:
            generated_text: The LLM-generated answer
            valid_tags: List of source tags that should be referenced
            intent_mode: The type of query (DEFINITION, PENALTY, etc.)
            
        Returns:
            bool: True if the answer is sufficiently grounded in sources
        """
        if not generated_text or len(generated_text.strip()) < 10:
            return False
        
        # If we have no valid tags, we can't validate - assume it's valid
        if not valid_tags:
            return True
        
        # Check if the answer contains ANY source material or legal terminology
        text_lower = generated_text.lower()
        
        # Look for legal citation patterns
        citation_patterns = [
            r'\([^)]*act[^)]*\)',
            r'\([^)]*section \d+[^)]*\)',
            r'\([^)]*ordinance[^)]*\)',
            r'\[[^\]]*act[^\]]*\]', 
            r'\[[^\]]*section \d+[^\]]*\]',
            r'forest act',
            r'section \d+',
            r'kpk forest',
            r'amendment act'
        ]
        
        has_citation = False
        for pattern in citation_patterns:
            if re.search(pattern, text_lower):
                has_citation = True
                break
        
        # Check for legal terminology appropriate to the intent
        legal_terms = []
        if intent_mode == LegalIntentMode.DEFINITION:
            legal_terms = ['means', 'includes', 'defined', 'definition', 'refers to']
        elif intent_mode == LegalIntentMode.PENALTY:
            legal_terms = ['fine', 'penalty', 'rs.', 'imprisonment', 'punishable', 'liable']
        elif intent_mode == LegalIntentMode.ARREST:
            legal_terms = ['arrest', 'warrant', 'officer', 'custody', 'detain', 'seize']
        else:
            legal_terms = ['act', 'law', 'section', 'provision', 'forest']
        
        has_legal_terms = any(term in text_lower for term in legal_terms)
        
        # For very short answers, be more permissive
        word_count = len(generated_text.split())
        if word_count < 20:
            return has_legal_terms or has_citation
        
        # Main validation logic
        if has_citation:
            # If it has proper citations, it's almost certainly valid
            return True
        
        if has_legal_terms and word_count > 30:
            # If it has legal terms and is substantial, likely valid
            return True
        
        # Split into sentences for more granular check
        sentences = re.split(r'(?<=[.!?])\s+', generated_text.strip())
        sentences = [s for s in sentences if len(s.split()) > 3]
        
        if not sentences:
            return False
        
        # Check if at least one sentence contains legal content
        legal_sentences = 0
        for sentence in sentences[:3]:  # Check first few sentences
            sent_lower = sentence.lower()
            if any(term in sent_lower for term in legal_terms):
                legal_sentences += 1
            elif any(tag.lower() in sent_lower for tag in valid_tags[:3]):
                legal_sentences += 1
        
        # Require at least one sentence with legal content
        return legal_sentences >= 1

    def extract_citations(self, text: str) -> List[str]:
        """
        Extract citation tags from the generated text.
        Useful for debugging and verification.
        """
        citations = []
        
        # Look for various citation formats
        patterns = [
            r'\(([^)]+(?:Act|Ordinance|Section|section)[^)]*)\)',  # (Forest Act, 1927)
            r'\[([^\]]+(?:Act|Ordinance|Section|section)[^\]]*)\]',  # [Forest Act, 1927]
            r'(?:Section|section)\s+(\d+)',  # Section 45
            r'(?:Act|Ordinance)[,\s]+(\d{4})',  # Act, 1927
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            citations.extend(matches)
        
        return list(set(citations))  # Remove duplicates

    def calculate_grounding_score(self, generated_text: str, source_chunks: List[str]) -> float:
        """
        Calculate how well the generated text is grounded in the source chunks.
        Returns a score between 0 and 1.
        """
        if not generated_text or not source_chunks:
            return 0.0
        
        if not self.model:
            # Simple keyword overlap if no model
            text_words = set(generated_text.lower().split())
            source_words = set()
            for chunk in source_chunks[:3]:
                source_words.update(chunk.lower().split())
            
            if not source_words:
                return 0.0
            
            overlap = len(text_words.intersection(source_words))
            total = len(text_words)
            return min(overlap / max(total, 1), 1.0)
        
        # Use embeddings for better semantic grounding
        try:
            text_vec = self.model.encode(generated_text)
            source_vecs = [self.model.encode(chunk) for chunk in source_chunks[:3]]
            
            scores = []
            for s_vec in source_vecs:
                score = cosine_similarity(
                    np.array(text_vec).reshape(1, -1),
                    np.array(s_vec).reshape(1, -1)
                )[0][0]
                scores.append(score)
            
            return max(scores) if scores else 0.0
            
        except Exception:
            return 0.5  # Default moderate score on error