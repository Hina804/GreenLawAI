"""
Semantic Chunker - Boundary-Aware Legal Document Chunking
Respects structural boundaries: chapters, sections, clauses, subclauses, definitions, schedules.
"""

from typing import List, Dict, Any, Optional, Tuple
import re
import hashlib
from datetime import datetime


class SemanticChunker:
    """
    Production-grade semantic chunker for legal documents.
    
    Features:
    - Boundary-aware chunking (never splits mid-structure)
    - Hierarchy path tracking
    - Rich metadata generation
    - Token estimation
    """
    
    # Structural boundary patterns
    RE_CHAPTER = re.compile(r'^Chapter\s+[IVXLCDM]+|^CHAPTER\s+\d+', re.I)
    RE_SECTION = re.compile(r'^Section\s+\d+|^\d+\.\s+', re.I)
    RE_CLAUSE = re.compile(r'^\(\d+\)')
    RE_SUBCLAUSE = re.compile(r'^\([a-z]+\)')
    RE_ITEM = re.compile(r'^\(i+\)')
    RE_DEFINITION_START = re.compile(r'^In this (Act|Ordinance)—', re.I)
    RE_SCHEDULE = re.compile(r'^SCHEDULE', re.I)
    
    def __init__(
        self,
        max_chunk_size: int = 512,
        min_chunk_size: int = 120,
        respect_boundaries: bool = True
    ):
        """
        Initialize semantic chunker.
        
        Args:
            max_chunk_size: Maximum tokens per chunk
            min_chunk_size: Minimum tokens per chunk
            respect_boundaries: Never split at structural boundaries
        """
        self.max_chunk_size = max_chunk_size
        self.min_chunk_size = min_chunk_size
        self.respect_boundaries = respect_boundaries
    
    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count (1 token ≈ 4 characters for English).
        
        Args:
            text: Input text
            
        Returns:
            Estimated token count
        """
        return len(text) // 4
    
    def detect_boundary_type(self, text: str) -> Optional[str]:
        """
        Detect if text starts with a structural boundary.
        
        Args:
            text: Text to check
            
        Returns:
            Boundary type or None
        """
        text_stripped = text.strip()
        
        if self.RE_CHAPTER.match(text_stripped):
            return "chapter"
        elif self.RE_SECTION.match(text_stripped):
            return "section"
        elif self.RE_CLAUSE.match(text_stripped):
            return "clause"
        elif self.RE_SUBCLAUSE.match(text_stripped):
            return "subclause"
        elif self.RE_ITEM.match(text_stripped):
            return "item"
        elif self.RE_DEFINITION_START.match(text_stripped):
            return "definition"
        elif self.RE_SCHEDULE.match(text_stripped):
            return "schedule"
        
        return None
    
    def build_hierarchy_path(
        self,
        law_title: str,
        chapter: str,
        section: str,
        clause: Optional[str] = None,
        subclause: Optional[str] = None
    ) -> str:
        """
        Build hierarchy path string.
        
        Args:
            law_title: Law title
            chapter: Chapter title
            section: Section number
            clause: Clause number (optional)
            subclause: Subclause letter (optional)
            
        Returns:
            Hierarchy path like "Act → Chapter I → Section 2 → Clause (3)"
        """
        path_parts = [law_title, chapter, f"Section {section}"]
        
        if clause:
            path_parts.append(f"Clause {clause}")
        if subclause:
            path_parts.append(f"Subclause {subclause}")
        
        return " → ".join(path_parts)
    
    def extract_clause_info(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract clause and subclause from text.
        
        Args:
            text: Text to analyze
            
        Returns:
            (clause, subclause) tuple
        """
        clause_match = self.RE_CLAUSE.search(text)
        subclause_match = self.RE_SUBCLAUSE.search(text)
        
        clause = clause_match.group(0) if clause_match else None
        subclause = subclause_match.group(0) if subclause_match else None
        
        return clause, subclause
    
    def clean_text_for_hashing(self, text: str) -> str:
        """
        Clean text for deterministic hashing.
        
        Args:
            text: Input text
            
        Returns:
            Normalized text
        """
        # Remove extra whitespace
        text = ' '.join(text.split())
        # Lowercase for consistency
        text = text.lower()
        # Remove special characters that might vary
        text = re.sub(r'[\r\n\t]+', ' ', text)
        return text.strip()
    
    def normalize_law_title(self, title: str) -> str:
        """
        Normalize law title for cross-document consistency.
        
        Examples:
            "Forest Act 1927" -> "forest act 1927"
            "Forest Act, 1927" -> "forest act 1927"
            "(Act XVI of 1927)" -> "act xvi 1927"
        """
        # Remove punctuation
        title = re.sub(r'[,\.\(\)]', '', title)
        # Normalize whitespace
        title = ' '.join(title.split())
        # Lowercase
        title = title.lower()
        # Standardize "act X of Y" pattern
        title = re.sub(r'act\s+(\w+)\s+of\s+(\d+)', r'act \1 \2', title)
        return title.strip()
    
    def normalize_chapter(self, chapter: str) -> str:
        """
        Normalize chapter for consistency.
        
        Examples:
            "Chapter I" -> "chapter_1"
            "CHAPTER 1" -> "chapter_1"
            "Chapter One" -> "chapter_1"
        """
        # Extract roman/arabic numerals or words
        match = re.search(r'(chapter|chap\.?)\s+([IVXLCDM]+|\d+|\w+)', chapter, re.I)
        if match:
            num_str = match.group(2).upper()
            
            # Convert roman to arabic if needed
            roman_to_arabic = {
                'I': '1', 'II': '2', 'III': '3', 'IV': '4', 'V': '5',
                'VI': '6', 'VII': '7', 'VIII': '8', 'IX': '9', 'X': '10'
            }
            
            if num_str in roman_to_arabic:
                return f"chapter_{roman_to_arabic[num_str]}"
            else:
                return f"chapter_{num_str.lower()}"
        
        return chapter.lower().strip().replace(' ', '_')
    
    def normalize_section(self, section: str) -> str:
        """
        Normalize section for consistency.
        
        Examples:
            "1" -> "section_1"
            "Section 1" -> "section_1"
            "1." -> "section_1"
        """
        # Extract number
        match = re.search(r'(\d+)', str(section))
        if match:
            return f"section_{match.group(1)}"
        return str(section).lower().strip()
    
    def generate_chunk_id(self, text: str, section_number: str, law_title: str, section_id: str = "unknown") -> str:
        """Generate a unique ID for a chunk."""
        clean_text = self.clean_text_for_hashing(text)
        text_hash = hashlib.md5(f"{clean_text}_{section_id}".encode()).hexdigest()[:8]
        law_slug = self.normalize_law_title(law_title).replace(" ", "_").lower()[:15]
        sec_slug = self.normalize_section(section_number).replace(" ", "_").lower()
        return f"CHNK_{law_slug}_{sec_slug}_{text_hash}"
    
    def chunk_section(
        self,
        section: Dict[str, Any],
        law_title: str,
        chapter_title: str,
        chapter_number: str,
        source_file: str,
        document_id: str = "unknown",
        version: str = "v1"
    ) -> List[Dict[str, Any]]:
        """
        Chunk a single section with boundary awareness.
        
        Args:
            section: Section dict from structured JSON
            law_title: Law title
            chapter_title: Chapter title
            chapter_number: Chapter number
            source_file: Source JSON filename
            version: Version identifier
            
        Returns:
            List of chunk dicts with rich metadata
        """
        chunks = []
        
        section_number = section.get('number', 'unknown')
        section_id = "unknown"
        if 'metadata' in section and 'section_id' in section['metadata']:
            section_id = section['metadata']['section_id']
        elif 'section_id' in section:
            section_id = section['section_id']
            
        section_heading = section.get('title') or section.get('heading', '') # Match both schema versions
        paragraphs = []
        subclauses = []
        
        # Pull from optimized structure if available (Gap 9 Correction)
        # Prioritize 'structure.text', then 'text' (if no internal structure), then 'metadata.text', then 'content'
        if 'structure' in section and isinstance(section['structure'], dict) and 'text' in section['structure']:
            section_text = section['structure']['text']
        elif 'text' in section and isinstance(section['text'], str) and section['text'] and not section.get('paragraphs') and not section.get('subclauses'):
            section_text = section['text']
        elif 'content' in section:
            if isinstance(section['content'], str):
                section_text = section['content']
            elif isinstance(section['content'], dict) and 'text' in section['content']:
                section_text = section['content']['text']
            else:
                section_text = ""
        elif 'metadata' in section and isinstance(section['metadata'], dict) and 'text' in section['metadata'] and isinstance(section['metadata']['text'], str):
            section_text = section['metadata']['text']
        elif 'metadata' in section and isinstance(section['metadata'], dict) and 'content' in section['metadata'] and isinstance(section['metadata']['content'], str):
            section_text = section['metadata']['content']
        else:
            section_text = ""
            
        if not section_text:
            # Fallback for building from sub-components
            paragraphs = section.get('paragraphs', [])
            subclauses = section.get('subclauses', [])
            
            section_text = f"{section_heading}\n\n"
            for para in paragraphs:
                if isinstance(para, str):
                    section_text += f"{para}\n\n"
            for sc in subclauses:
                if isinstance(sc, dict) and 'text' in sc:
                    label = sc.get('label', '')
                    section_text += f"{label} {sc['text']}\n\n"
        
        section_text = section_text.strip()
        
        # Estimate total tokens
        total_tokens = self.estimate_tokens(section_text)
        
        # If section fits in one chunk, keep it intact
        if total_tokens <= self.max_chunk_size:
            clause, subclause = self.extract_clause_info(section_text)
            
            # Create metadata first (without chunk_id)
            metadata = {
                # Document hierarchy
                'law_title': law_title,
                'chapter': chapter_title,
                'chapter_number': chapter_number,
                'section': section_number,
                'section_id': section_id,
                'document_id': document_id,
                'section_title': section_heading,
                'clause': clause,
                'subclause': subclause,
                'hierarchy_path': self.build_hierarchy_path(
                    law_title, chapter_title, section_number, clause, subclause
                ),
                
                # Chunk metrics
                'text_length': len(section_text),
                'token_count': total_tokens,
                'chunk_index': 0,
                'total_chunks_in_section': 1,
                
                # Versioning & provenance
                'version': version,
                'source_file': source_file,
                'indexed_at': datetime.utcnow().isoformat() + 'Z'
            }
            
            # Generate deterministic chunk_id
            metadata['chunk_id'] = self.generate_chunk_id(section_text, section_number, law_title, section_id)
            metadata['neo4j_chunk_id'] = metadata['chunk_id']  # Same ID for Neo4j
            
            chunks.append({
                'text': section_text,
                'metadata': metadata
            })
        else:
            # Split long section at boundaries
            parts = []
            
            # Add heading as first part
            if section_heading:
                parts.append(('heading', section_heading))
            
            # Add paragraphs
            for para in paragraphs:
                parts.append(('paragraph', para))
            
            # Add subclauses
            for sc in subclauses:
                parts.append(('subclause', f"{sc['label']} {sc['text']}"))
            
            # Accumulate parts into chunks
            current_chunk_text = ""
            current_chunk_parts = []
            chunk_index = 0
            
            # SMALL CHUNK AGGREGATOR:
            # Accumulate parts until we reach min_chunk_size OR max_chunk_size
            for part_type, part_text in parts:
                part_tokens = self.estimate_tokens(part_text)
                current_tokens = self.estimate_tokens(current_chunk_text)
                
                # If adding this part exceeds max_chunk_size, or we have enough text and hit a major boundary
                if (current_tokens + part_tokens > self.max_chunk_size) or \
                   (current_tokens >= self.min_chunk_size and part_type in ['chapter', 'section']):
                    
                    if current_chunk_text.strip():
                        # Save current chunk
                        clause, subclause = self.extract_clause_info(current_chunk_text)
                        
                        metadata = {
                            'law_title': law_title,
                            'chapter': chapter_title,
                            'chapter_number': chapter_number,
                            'section': section_number,
                            'section_id': section_id,
                            'document_id': document_id,
                            'section_title': section_heading,
                            'clause': clause,
                            'subclause': subclause,
                            'hierarchy_path': self.build_hierarchy_path(
                                law_title, chapter_title, section_number, clause, subclause
                            ),
                            'text_length': len(current_chunk_text),
                            'token_count': current_tokens,
                            'chunk_index': chunk_index,
                            'total_chunks_in_section': -1,
                            'version': version,
                            'source_file': source_file,
                            'indexed_at': datetime.utcnow().isoformat() + 'Z'
                        }
                        
                        metadata['chunk_id'] = self.generate_chunk_id(current_chunk_text.strip(), section_number, law_title, section_id)
                        metadata['neo4j_chunk_id'] = metadata['chunk_id']
                        
                        chunks.append({
                            'text': current_chunk_text.strip(),
                            'metadata': metadata
                        })
                        
                        chunk_index += 1
                        current_chunk_text = ""
                
                # Add to current chunk
                if current_chunk_text:
                    current_chunk_text += "\n\n" + part_text
                else:
                    current_chunk_text = part_text
            
            # Add final accumulated chunk
            if current_chunk_text.strip():
                current_tokens = self.estimate_tokens(current_chunk_text)
                clause, subclause = self.extract_clause_info(current_chunk_text)
                
                metadata = {
                    'law_title': law_title,
                    'chapter': chapter_title,
                    'chapter_number': chapter_number,
                    'section': section_number,
                    'section_id': section_id,
                    'document_id': document_id,
                    'section_title': section_heading,
                    'clause': clause,
                    'subclause': subclause,
                    'hierarchy_path': self.build_hierarchy_path(
                        law_title, chapter_title, section_number, clause, subclause
                    ),
                    'text_length': len(current_chunk_text),
                    'token_count': current_tokens,
                    'chunk_index': chunk_index,
                    'total_chunks_in_section': -1,
                    'version': version,
                    'source_file': source_file,
                    'indexed_at': datetime.utcnow().isoformat() + 'Z'
                }
                
                chunk_id = self.generate_chunk_id(metadata, current_chunk_text.strip())
                metadata['chunk_id'] = chunk_id
                metadata['neo4j_chunk_id'] = chunk_id
                
                chunks.append({
                    'text': current_chunk_text.strip(),
                    'metadata': metadata
                })
            
            # Update total_chunks_in_section
            total_chunks = len(chunks)
            for chunk in chunks:
                chunk['metadata']['total_chunks_in_section'] = total_chunks
        
        return chunks
    
    def chunk_document(
        self,
        structured_json: Dict[str, Any],
        source_file: str,
        version: str = "v1"
    ) -> List[Dict[str, Any]]:
        """
        Chunk entire legal document with boundary awareness.
        """
        all_chunks = []
        
        # Pull from root (Gap 9 Correction)
        law_title = structured_json.get('act_title') or structured_json.get('document_id', 'unknown')
        document_id = structured_json.get('document_id', 'unknown')
        
        # Scenario A: Hierarchy (chapters -> sections)
        if 'chapters' in structured_json and structured_json['chapters']:
            for chapter in structured_json.get('chapters', []):
                chapter_title = chapter.get('title', 'unknown')
                chapter_number = chapter.get('number', 'unknown')
                
                for section in chapter.get('sections', []):
                    section_chunks = self.chunk_section(
                        section,
                        law_title,
                        chapter_title,
                        chapter_number,
                        source_file,
                        document_id,
                        version
                    )
                    all_chunks.extend(section_chunks)
        
        # Scenario B: Flat Section List (Phase 4 Rules structure)
        elif 'sections' in structured_json and structured_json['sections']:
            for section in structured_json['sections']:
                section_chunks = self.chunk_section(
                    section,
                    law_title,
                    "General", # Default chapter
                    "0",       # Default chapter number
                    source_file,
                    document_id,
                    version
                )
                all_chunks.extend(section_chunks)
        
        print(f"[OK] Created {len(all_chunks)} boundary-aware chunks")
        
        # Statistics
        if all_chunks:
            avg_tokens = sum(c['metadata']['token_count'] for c in all_chunks) / len(all_chunks)
            print(f"  Average chunk size: {avg_tokens:.1f} tokens")
        else:
            print(f"  [!] WARNING: No chunks created (document may have no sections)")
        
        return all_chunks


if __name__ == "__main__":
    # Test
    import json
    from pathlib import Path
    
    # Load sample
    json_path = Path(r"e:\GL_AI\data_processed\forestry\structured\forest_act_1927_final_structured.json")
    with open(json_path, encoding='utf-8') as f:
        doc = json.load(f)
    
    # Create chunker
    chunker = SemanticChunker(
        max_chunk_size=512,
        min_chunk_size=120,
        respect_boundaries=True
    )
    
    # Chunk document
    chunks = chunker.chunk_document(doc, json_path.name, version="v1")
    
    print(f"\n{'='*60}")
    print(f"SEMANTIC CHUNKING TEST")
    print(f"{'='*60}")
    print(f"Total chunks: {len(chunks)}")
    
    # Show first chunk
    print(f"\nFirst chunk:")
    print(f"Text: {chunks[0]['text'][:200]}...")
    print(f"\nMetadata:")
    for key, value in chunks[0]['metadata'].items():
        print(f"  {key}: {value}")
    
    # Show chunk size distribution
    token_counts = [c['metadata']['token_count'] for c in chunks]
    print(f"\nChunk size distribution:")
    print(f"  Min: {min(token_counts)} tokens")
    print(f"  Max: {max(token_counts)} tokens")
    print(f"  Avg: {sum(token_counts)/len(token_counts):.1f} tokens")
