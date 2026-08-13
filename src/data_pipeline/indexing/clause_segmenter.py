"""
Clause Segmenter - Production-Grade Clause Detection with OCR Fixes
Segments chunks into clauses, subclauses, and sentences with deterministic IDs.
"""

from typing import List, Dict, Any, Tuple
import re
import hashlib


class ClauseSegmenter:
    """
    Segment legal text into hierarchical clauses with OCR error handling.
    """
    
    # Robust clause patterns (handle OCR errors and formatting variations)
    RE_CLAUSE = re.compile(
        r'^\s*[\(\[]?\s*(\d+)\s*[\)\]]?\s*[\.:]?\s*',
        re.MULTILINE
    )
    
    RE_SUBCLAUSE = re.compile(
        r'^\s*[\(\[]?\s*([a-z])\s*[\)\]]?\s*[\.:]?\s*',
        re.MULTILINE | re.IGNORECASE
    )
    
    RE_SUBSUBCLAUSE = re.compile(
        r'^\s*[\(\[]?\s*([ivxlcdm]+)\s*[\)\]]?\s*[\.:]?\s*',
        re.MULTILINE | re.IGNORECASE
    )
    
    # OCR error mappings
    OCR_FIXES = {
        'l': '1',  # lowercase L -> 1
        'O': '0',  # uppercase O -> 0
        'I': '1',  # uppercase I -> 1 (in numeric context)
    }
    
    def __init__(self):
        # Load spaCy for sentence segmentation (fallback)
        try:
            import spacy
            self.nlp = spacy.load("en_core_web_sm", disable=["ner"])
            # Add sentencizer if not present
            if "sentencizer" not in self.nlp.pipe_names:
                self.nlp.add_pipe("sentencizer")
        except:
            self.nlp = None
    
    def normalize_clause_marker(self, text: str) -> str:
        """Normalize clause marker with OCR fixes."""
        text = text.strip()
        
        # Apply OCR fixes BEFORE standardizing
        for wrong, right in self.OCR_FIXES.items():
            text = text.replace(wrong, right)
        
        # Standardize brackets
        text = text.replace('[', '(').replace(']', ')')
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        return text.strip()
    
    def clean_text(self, text: str) -> str:
        """Clean text for hashing."""
        text = ' '.join(text.split())
        text = text.lower()
        text = re.sub(r'[\r\n\t]+', ' ', text)
        return text.strip()
    
    def create_clause_id(
        self,
        chunk_id: str,
        clause_marker: str,
        clause_text: str,
        start_offset: int
    ) -> str:
        """
        Generate deterministic clause ID using SHA256.
        
        Components:
        - chunk_id (parent)
        - clause_marker (normalized)
        - clause_text (cleaned)
        - start_offset (position)
        """
        components = [
            chunk_id,
            self.normalize_clause_marker(clause_marker),
            self.clean_text(clause_text),
            str(start_offset)
        ]
        
        content = '||'.join(components)
        hash_obj = hashlib.sha256(content.encode('utf-8'))
        
        return hash_obj.hexdigest()[:16]
    
    def segment_subclauses(
        self,
        clause_text: str,
        clause_id: str,
        start_offset: int
    ) -> List[Dict]:
        """Segment subclauses within a clause."""
        subclauses = []
        
        for match in self.RE_SUBCLAUSE.finditer(clause_text):
            subclause_marker = match.group(0)
            sub_start = match.start() + start_offset
            
            # Find end
            next_match = self.RE_SUBCLAUSE.search(clause_text, match.end())
            sub_end = (next_match.start() + start_offset) if next_match else (start_offset + len(clause_text))
            
            subclause_text = clause_text[match.start():next_match.start() if next_match else len(clause_text)].strip()
            
            subclause_id = self.create_clause_id(
                chunk_id=clause_id,
                clause_marker=subclause_marker,
                clause_text=subclause_text,
                start_offset=sub_start
            )
            
            subclauses.append({
                "subclause_id": subclause_id,
                "subclause_marker": self.normalize_clause_marker(subclause_marker),
                "text": subclause_text,
                "start_offset": sub_start,
                "end_offset": sub_end
            })
        
        return subclauses
    
    def segment_chunk_with_offsets(
        self,
        chunk_text: str,
        chunk_id: str
    ) -> Dict[str, Any]:
        """
        Segment chunk into clauses with character offsets.
        
        Returns:
            {
                "clauses": [...],
                "sentences": [...],  # Fallback
                "has_clauses": bool
            }
        """
        clauses = []
        
        # Find all clause markers
        clause_matches = list(self.RE_CLAUSE.finditer(chunk_text))
        
        if clause_matches:
            for i, match in enumerate(clause_matches):
                clause_marker = match.group(0)
                start = match.start()
                
                # Find end (next clause or end of text)
                if i + 1 < len(clause_matches):
                    end = clause_matches[i + 1].start()
                else:
                    end = len(chunk_text)
                
                clause_text = chunk_text[start:end].strip()
                
                clause_id = self.create_clause_id(
                    chunk_id=chunk_id,
                    clause_marker=clause_marker,
                    clause_text=clause_text,
                    start_offset=start
                )
                
                # Segment subclauses
                subclauses = self.segment_subclauses(clause_text, clause_id, start)
                
                clauses.append({
                    "clause_id": clause_id,
                    "clause_marker": self.normalize_clause_marker(clause_marker),
                    "text": clause_text,
                    "start_offset": start,
                    "end_offset": end,
                    "subclauses": subclauses
                })
        
        # Fallback: sentence segmentation
        sentences = self._segment_sentences(chunk_text)
        
        return {
            "clauses": clauses,
            "sentences": sentences,
            "has_clauses": len(clauses) > 0
        }
    
    def _segment_sentences(self, text: str) -> List[str]:
        """Fallback sentence segmentation."""
        if self.nlp:
            doc = self.nlp(text)
            return [sent.text.strip() for sent in doc.sents]
        else:
            # Simple fallback: split on periods
            sentences = re.split(r'[.!?]+', text)
            return [s.strip() for s in sentences if s.strip()]
    
    def segment_chunk(self, chunk_text: str, chunk_id: str = "unknown") -> Dict[str, Any]:
        """
        Segment chunk (wrapper for backward compatibility).
        """
        return self.segment_chunk_with_offsets(chunk_text, chunk_id)


if __name__ == "__main__":
    # Test
    segmenter = ClauseSegmenter()
    
    test_text = """
(1) This Act may be called the Forest Act, 1927.
(a) It applies to reserved forests.
(b) It applies to protected forests.
(2) It extends to the whole of Pakistan.
"""
    
    result = segmenter.segment_chunk_with_offsets(test_text, "test_chunk_id")
    
    print("Clauses found:", len(result['clauses']))
    for clause in result['clauses']:
        print(f"  {clause['clause_marker']}: {clause['text'][:50]}...")
        print(f"    Subclauses: {len(clause['subclauses'])}")
