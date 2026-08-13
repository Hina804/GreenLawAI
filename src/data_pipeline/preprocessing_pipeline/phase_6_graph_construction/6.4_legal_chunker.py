"""
6.4_LEGAL_CHUNKER.PY - Semantic Chunking for KPK Legal Documents
"""
import re
import logging
import hashlib
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class LegalChunk:
    chunk_id: str
    text: str
    metadata: Dict[str, Any]
    entities_mentioned: List[str] = field(default_factory=list)

class SmallChunkAggregator:
    """Aggregates small chunks (like orphaned section numbers) with adjacent chunks."""
    def __init__(self, min_chunk_size: int = 150):
        self.min_chunk_size = min_chunk_size

    def aggregate(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not chunks:
            return []
            
        aggregated = []
        i = 0
        while i < len(chunks):
            current = chunks[i]
            # If chunk is too small and not the last one
            if len(current['chunk_text']) < self.min_chunk_size and (i + 1) < len(chunks):
                # Look ahead
                next_chunk = chunks[i+1]
                # Merge current into next
                next_chunk['chunk_text'] = current['chunk_text'] + " " + next_chunk['chunk_text']
                next_chunk['metadata']['char_length'] = len(next_chunk['chunk_text'])
                # Don't add current to aggregated, just jump to next loop iteration
            else:
                aggregated.append(current)
            i += 1
            
        # Final pass check: If the last chunk is still too small, merge it backward if possible
        if len(aggregated) > 1 and len(aggregated[-1]['chunk_text']) < self.min_chunk_size:
            last = aggregated.pop()
            aggregated[-1]['chunk_text'] += " " + last['chunk_text']
            aggregated[-1]['metadata']['char_length'] = len(aggregated[-1]['chunk_text'])
            
        return aggregated

class LegalChunker:
    def __init__(self, chunk_size: int = 1000, overlap: int = 100):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.aggregator = SmallChunkAggregator(min_chunk_size=150)

    def _recursive_split(self, text: str, separators: List[str]) -> List[str]:
        """Recursively split text into chunks smaller than chunk_size."""
        final_chunks = []
        if len(text) <= self.chunk_size:
            return [text]
        
        # Filter out empty separators which cause split() to fail
        active_separators = [s for s in separators if s]
        
        if not active_separators:
            # If no valid separators left and still too big, force split by character size
            return [text[i:i+self.chunk_size] for i in range(0, len(text), self.chunk_size)]
        
        separator = active_separators[0]
        splits = text.split(separator)
        
        # If separation didn't work (text is one big block), try next separator
        if len(splits) == 1:
            return self._recursive_split(text, active_separators[1:])
            
        current_chunk = ""
        for split in splits:
            if not split.strip(): continue
            
            # If this single split is huge, we must recurse deeper on it
            if len(split) > self.chunk_size:
                if current_chunk:
                    final_chunks.append(current_chunk)
                    current_chunk = ""
                # Recurse on the split with REMAINING separators
                sub_chunks = self._recursive_split(split, active_separators[1:])
                final_chunks.extend(sub_chunks)
            
            # If we can add this split to current chunk
            elif len(current_chunk) + len(split) + len(separator) <= self.chunk_size:
                current_chunk += (separator + split if current_chunk else split)
            
            # If adding would exceed, save current and start new
            else:
                if current_chunk:
                    final_chunks.append(current_chunk)
                current_chunk = split
                
        if current_chunk:
            final_chunks.append(current_chunk)
            
        return final_chunks

    def chunk(self, text: str, doc_metadata: Dict = None) -> List[Dict[str, Any]]:
        if not text:
            return []
        
        # Use recursive splitting
        separators = ["\n\n", "\n", ". ", " ", ""]
        chunks_text = self._recursive_split(text, separators)
        
        chunks = chunks_text # Already list of strings
            
        result = []
        for i, chunk_text in enumerate(chunks):
            chunk_id = hashlib.md5(chunk_text.encode()).hexdigest()[:8]
            result.append({
                "chunk_id": f"chunk_{i}_{chunk_id}",
                "chunk_text": chunk_text,
                "metadata": {
                    **(doc_metadata or {}),
                    "chunk_index": i,
                    "char_length": len(chunk_text)
                }
            })
            
        # NEW: Aggregate small orphans
        return self.aggregator.aggregate(result)

    # Alias for compatibility with other scripts
    def chunk_document(self, text: str, metadata: Dict = None) -> List[Any]:
        chunks_data = self.chunk(text, metadata)
        return [LegalChunk(c["chunk_id"], c["chunk_text"], c["metadata"]) for c in chunks_data]

    def create_chunks_from_sections(self, sections: List[Any]) -> List[Dict[str, Any]]:
        """Recursively extracts chunks from sections and sub-sections."""
        all_chunks = []
        
        def process_recursive(section_list):
            for section in section_list:
                # Handle both dict and object formats
                if isinstance(section, dict):
                    content_obj = section.get("content", {})
                    if isinstance(content_obj, dict):
                        content_text = content_obj.get("text", "")
                    elif isinstance(content_obj, str):
                        content_text = content_obj
                    else:
                        content_text = ""
                    metadata = section.copy()
                    # Remove children from metadata to keep it clean
                    if "child_sections" in metadata:
                        del metadata["child_sections"]
                    children = section.get("child_sections", [])
                else:
                    content_obj = getattr(section, "content", None)
                    if content_obj is None:
                        content_text = ""
                    elif isinstance(content_obj, str):
                        content_text = content_obj
                    elif isinstance(content_obj, dict):
                        content_text = content_obj.get("text", "")
                    else:
                        content_text = getattr(content_obj, "text", "")
                    metadata = {"section_id": getattr(section, "id", "unknown")}
                    children = getattr(section, "child_sections", [])

                if content_text:
                    all_chunks.extend(self.chunk(content_text, metadata))
                
                # RECURSE into children
                if children:
                    process_recursive(children)
        
        process_recursive(sections)
        
        # FINAL GLOBAL AGGREGATION to handle small orphan sections
        return self.aggregator.aggregate(all_chunks)
