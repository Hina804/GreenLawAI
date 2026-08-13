"""
MULTILINGUAL_SEGMENTER.PY - Phase 2
Handles mixed English and Urdu text segmentation.
Uses script detection to split or tag segments.
"""
import re
from typing import List, Dict, Tuple
import logging

logger = logging.getLogger(__name__)

class MultilingualSegmenter:
    """
    Segments text based on script (Latin vs Arabic/Urdu).
    """
    
    def __init__(self):
        # Range for Arabic/Urdu Unicode blocks
        self.urdu_pattern = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]+')
        
    def segment_text(self, text: str) -> List[Dict[str, str]]:
        """Alias for segment_by_language to match pipeline expectations"""
        return self.segment_by_language(text)

    def segment_by_language(self, text: str) -> List[Dict[str, str]]:
        """
        Split text into language-tagged segments.
        """
        if not text:
            return []
            
        segments = []
        last_end = 0
        
        # Determine segments by finding continuous Urdu blocks
        for match in self.urdu_pattern.finditer(text):
            start, end = match.span()
            
            # Text before Urdu is likely English (or Latin script)
            if start > last_end:
                english_part = text[last_end:start].strip()
                if english_part:
                    segments.append({"text": english_part, "lang": "en"})
            
            # The Urdu part
            urdu_part = text[start:end].strip()
            if urdu_part:
                segments.append({"text": urdu_part, "lang": "ur"})
            
            last_end = end
            
        # Remaining text
        if last_end < len(text):
            english_part = text[last_end:].strip()
            if english_part:
                segments.append({"text": english_part, "lang": "en"})
                
        logger.info(f"Segmented text into {len(segments)} parts.")
        return segments

    def merge_segments(self, segments: List[Dict[str, str]], min_length: int = 50) -> List[Dict[str, str]]:
        """
        Merge short segments of same language or small fragments.
        """
        if not segments:
            return []
            
        merged = []
        current = segments[0]
        
        for next_seg in segments[1:]:
            # If same language, merge
            if next_seg['lang'] == current['lang']:
                current['text'] += " " + next_seg['text']
            # If current is too short/junk (like punctuation), merge into next?
            # For strictness, we just merge same-lang
            else:
                merged.append(current)
                current = next_seg
        
        merged.append(current)
        return merged
