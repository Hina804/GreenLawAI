"""
Intelligent Chunking Strategy for Legal Documents
Respects section boundaries and maintains context.
"""

from typing import List, Dict, Any
import re


class LegalDocumentChunker:
    """
    Chunks legal documents intelligently while preserving structure.
    
    Strategy:
    1. Keep sections intact if < max_chunk_size
    2. Split long sections at paragraph boundaries
    3. Maintain metadata (law, chapter, section) for each chunk
    """
    
    def __init__(
        self, 
        max_chunk_size: int = 512,
        overlap_size: int = 50,
        min_chunk_size: int = 100
    ):
        """
        Initialize chunker.
        
        Args:
            max_chunk_size: Maximum tokens per chunk (default: 512)
            overlap_size: Overlap between chunks (default: 50)
            min_chunk_size: Minimum chunk size (default: 100)
        """
        self.max_chunk_size = max_chunk_size
        self.overlap_size = overlap_size
        self.min_chunk_size = min_chunk_size
    
    def estimate_tokens(self, text: str) -> int:
        """
        Rough token estimation (1 token ≈ 4 characters for English).
        
        Args:
            text: Input text
            
        Returns:
            Estimated token count
        """
        return len(text) // 4
    
    def chunk_section(
        self, 
        section: Dict[str, Any],
        law_title: str,
        chapter_title: str
    ) -> List[Dict[str, Any]]:
        """
        Chunk a single section intelligently.
        
        Args:
            section: Section dict with 'number', 'heading', 'paragraphs', 'subclauses'
            law_title: Law title for metadata
            chapter_title: Chapter title for metadata
            
        Returns:
            List of chunk dicts with text and metadata
        """
        chunks = []
        
        # Build full section text
        section_number = section.get('number', 'unknown')
        section_heading = section.get('heading', '')
        paragraphs = section.get('paragraphs', [])
        subclauses = section.get('subclauses', [])
        
        # Combine heading + paragraphs
        section_text = f"{section_heading}\n\n"
        section_text += "\n\n".join(paragraphs)
        
        # Add subclauses
        if subclauses:
            subclause_text = "\n".join([
                f"{sc['label']} {sc['text']}" 
                for sc in subclauses
            ])
            section_text += f"\n\n{subclause_text}"
        
        section_text = section_text.strip()
        
        # Estimate tokens
        estimated_tokens = self.estimate_tokens(section_text)
        
        # If section fits in one chunk, keep it intact
        if estimated_tokens <= self.max_chunk_size:
            chunks.append({
                'text': section_text,
                'metadata': {
                    'law': law_title,
                    'chapter': chapter_title,
                    'section': section_number,
                    'section_title': section_heading,
                    'chunk_index': 0,
                    'total_chunks': 1
                }
            })
        else:
            # Split long section at paragraph boundaries
            parts = [section_heading] + paragraphs
            
            current_chunk = ""
            chunk_index = 0
            
            for part in parts:
                part_tokens = self.estimate_tokens(part)
                current_tokens = self.estimate_tokens(current_chunk)
                
                # If adding this part exceeds limit, save current chunk
                if current_tokens + part_tokens > self.max_chunk_size and current_chunk:
                    chunks.append({
                        'text': current_chunk.strip(),
                        'metadata': {
                            'law': law_title,
                            'chapter': chapter_title,
                            'section': section_number,
                            'section_title': section_heading,
                            'chunk_index': chunk_index,
                            'total_chunks': -1  # Will update later
                        }
                    })
                    chunk_index += 1
                    
                    # Start new chunk with overlap (last sentence of previous)
                    sentences = current_chunk.split('. ')
                    if len(sentences) > 1:
                        current_chunk = sentences[-1] + ". " + part
                    else:
                        current_chunk = part
                else:
                    current_chunk += "\n\n" + part if current_chunk else part
            
            # Add final chunk
            if current_chunk.strip():
                chunks.append({
                    'text': current_chunk.strip(),
                    'metadata': {
                        'law': law_title,
                        'chapter': chapter_title,
                        'section': section_number,
                        'section_title': section_heading,
                        'chunk_index': chunk_index,
                        'total_chunks': -1
                    }
                })
            
            # Update total_chunks for all chunks
            total = len(chunks)
            for chunk in chunks:
                chunk['metadata']['total_chunks'] = total
        
        return chunks
    
    def chunk_document(self, structured_json: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Chunk entire legal document.
        
        Args:
            structured_json: Output from structure_detector.py
            
        Returns:
            List of all chunks with metadata
        """
        all_chunks = []
        
        law_title = structured_json['metadata']['title']
        
        # Chunk each chapter's sections
        for chapter in structured_json['content']:
            chapter_title = chapter['chapter']
            
            for section in chapter['sections']:
                section_chunks = self.chunk_section(
                    section, 
                    law_title, 
                    chapter_title
                )
                all_chunks.extend(section_chunks)
        
        print(f"[OK] Created {len(all_chunks)} chunks from document")
        return all_chunks


if __name__ == "__main__":
    # Test
    import json
    
    # Load sample structured JSON
    with open(r"e:\GL_AI\data_processed\forestry\structured\forest_act_1927_final_structured.json") as f:
        doc = json.load(f)
    
    chunker = LegalDocumentChunker(max_chunk_size=512)
    chunks = chunker.chunk_document(doc)
    
    print(f"\nTotal chunks: {len(chunks)}")
    print(f"\nFirst chunk:")
    print(f"Text: {chunks[0]['text'][:200]}...")
    print(f"Metadata: {chunks[0]['metadata']}")
