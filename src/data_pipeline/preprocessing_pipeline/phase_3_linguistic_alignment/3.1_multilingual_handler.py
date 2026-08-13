"""
multilingual_handler.py
===========================================================
ENHANCED KPK MULTILINGUAL DOCUMENT HANDLER

Specialized handling for KPK forestry documents with improvements for:
- Better integration with your preprocessing pipeline phases
- Enhanced OCR error handling (fixes common OCR mistakes)
- Structured output format for downstream phases
- Legal context awareness
- Pipeline state management

Key Enhancements:
1. Added PipelineState integration for flow between phases
2. Enhanced OCR error correction patterns
3. Legal context classification for downstream processing
4. Structured output compatible with phase 4 (legal extraction)
5. Abstention tracking integration
6. Document type-specific processing rules
"""

import re
import json
from typing import Dict, List, Tuple, Set, Optional, Union, Any
from dataclasses import dataclass, asdict, field
from collections import defaultdict
import logging
from enum import Enum
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Language(Enum):
    """Supported languages in KPK documents"""
    URDU = "urdu"
    ENGLISH = "english"
    PASHTO = "pashto"
    MIXED = "mixed"
    ARABIC = "arabic"  # For Quranic/Arabic loanwords
    UNKNOWN = "unknown"
    
    @classmethod
    def from_script(cls, text: str) -> 'Language':
        """Enhanced language detection with OCR error awareness"""
        # Check for Arabic script (Urdu, Pashto, Arabic)
        if re.search(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\u0670-\u06D4]', text):
            # Fix common OCR errors first
            corrected = cls._correct_ocr_errors(text)
            
            # Try to distinguish between Urdu, Pashto, Arabic
            if re.search(r'[\u067E\u0686\u0698\u06AF\u06A9\u06BE\u06C1]', corrected):  # Urdu-specific
                return cls.URDU
            elif re.search(r'[\u069A\u069B\u069C\u069D\u069E\u06AB\u06AC\u06AD\u06AE\u06B1\u06B3\u06B5\u06B7\u06B9\u06BA\u06BB\u06BC\u06BD\u06BE\u06C0\u06C1\u06C2\u06D2]', corrected):
                return cls.PASHTO
            elif re.search(r'[\u0621-\u063A\u0641-\u064A\u0650\u0651\u0652]', corrected):
                return cls.ARABIC
            return cls.URDU  # Default to Urdu for Arabic script
        
        # Check for Latin script (English)
        if re.search(r'[A-Za-z]', text):
            # Check for common OCR errors in English
            if re.search(r'f0rest|f0r3st|fores t', text, re.IGNORECASE):
                return cls.ENGLISH  # Still English despite OCR error
            return cls.ENGLISH
        
        return cls.UNKNOWN
    
    @staticmethod
    def _correct_ocr_errors(text: str) -> str:
        """Correct common OCR errors in Urdu/Arabic script"""
        corrections = {
            'لہ': 'ل',  # Common OCR error
            'رہ': 'ر',
            'نہ': 'ن',
            'ےے': 'ے',
            'اا': 'ا',
            'رر': 'ر',
            'ںں': 'ں',
            '۰': '0',  # Eastern Arabic numeral to standard
            '۱': '1',
            '۲': '2',
            '۳': '3',
            '۴': '4',
            '۵': '5',
            '۶': '6',
            '۷': '7',
            '۸': '8',
            '۹': '9',
        }
        
        corrected = text
        for error, correction in corrections.items():
            corrected = corrected.replace(error, correction)
        
        return corrected


@dataclass
class PipelineState:
    """Tracks document state through the preprocessing pipeline"""
    doc_id: str
    phase: int = 3  # Current phase (linguistic alignment)
    subphase: str = "3.1_multilingual"
    status: str = "processing"
    metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    abstention_reasons: List[str] = field(default_factory=list)
    
    def add_abstention(self, reason: str, context: str = ""):
        """Record an abstention decision"""
        self.abstention_reasons.append(f"{reason}: {context}")
        self.status = "abstained"
    
    def add_warning(self, warning: str):
        """Add a warning"""
        self.warnings.append(f"{datetime.now()}: {warning}")
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class LanguageSegment:
    """Enhanced LanguageSegment with legal context awareness"""
    text: str
    language: Language
    confidence: float
    start_pos: int
    end_pos: int
    is_mixed: bool = False
    mixed_components: Optional[List[Dict]] = None
    legal_context: Optional[str] = None  # section, penalty, definition, etc.
    doc_type_hint: Optional[str] = None  # statute, circular, report, etc.
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class BilingualTerm:
    """Enhanced BilingualTerm with legal significance"""
    english: str
    urdu: str
    pashto: Optional[str] = None
    scientific_name: Optional[str] = None
    category: str = "general"
    confidence: float = 1.0
    legal_significance: float = 0.0  # 0-1, how important for legal interpretation
    common_ocr_errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return asdict(self)


class KPKMultilingualDictionary:
    """Enhanced dictionary with OCR error patterns and legal significance"""
    
    def __init__(self):
        self.terms: List[BilingualTerm] = []
        self.ocr_error_patterns: Dict[str, List[str]] = {}
        self._build_dictionary()
    
    def _build_dictionary(self):
        """Build comprehensive KPK forestry bilingual dictionary with OCR awareness"""
        
        # Tree Species with OCR error patterns
        species_terms = [
            BilingualTerm(
                english="Deodar",
                urdu="دیار",
                pashto="دیار",
                scientific_name="Cedrus deodara",
                category="species",
                confidence=0.99,
                legal_significance=0.9,
                common_ocr_errors=["دی ا ر", "دبار", "دیارر"]
            ),
            BilingualTerm(
                english="Kail",
                urdu="کایل",
                pashto="کایل",
                scientific_name="Pinus wallichiana",
                category="species",
                confidence=0.98,
                legal_significance=0.8,
                common_ocr_errors=["کا یل", "کابل", "کای ل"]
            ),
            BilingualTerm(
                english="Chir",
                urdu="چیر",
                pashto="چیر",
                scientific_name="Pinus roxburghii",
                category="species",
                confidence=0.98,
                legal_significance=0.8,
                common_ocr_errors=["چی ر", "چییر", "چی ر"]
            ),
            BilingualTerm(
                english="Walnut",
                urdu="اخروٹ",
                pashto="غوزۍ",
                scientific_name="Juglans regia",
                category="species",
                confidence=0.95,
                legal_significance=0.7,
                common_ocr_errors=["اخر وٹ", "اخروط", "اخروت"]
            ),
        ]
        
        # Legal Terms with high legal significance
        legal_terms = [
            BilingualTerm(
                english="Forest Ordinance",
                urdu="فارسٹ آرڈیننس",
                pashto="ځنګلي حکم",
                category="legal_term",
                confidence=0.95,
                legal_significance=1.0,
                common_ocr_errors=["فار سٹ", "فارست", "فورسٹ"]
            ),
            BilingualTerm(
                english="Section",
                urdu="سیکشن",
                pashto="برخه",
                category="legal_term",
                confidence=0.99,
                legal_significance=0.9,
                common_ocr_errors=["سی کشن", "سیک ش ن", "section"]  # OCR might output English
            ),
            BilingualTerm(
                english="Penalty",
                urdu="جرمانہ",
                pashto="جریمه",
                category="legal_term",
                confidence=0.99,
                legal_significance=0.95,
                common_ocr_errors=["جرما نہ", "جرما نا", "جرمانا"]
            ),
        ]
        
        self.terms.extend(species_terms)
        self.terms.extend(legal_terms)
        
        # Build OCR error pattern lookup
        for term in self.terms:
            for error in term.common_ocr_errors:
                self.ocr_error_patterns[error.lower()] = term.english
        
        logger.info(f"Built dictionary with {len(self.terms)} bilingual terms")
        logger.info(f"Loaded {len(self.ocr_error_patterns)} OCR error patterns")
    
    def find_term_with_ocr_correction(self, text: str) -> Optional[Tuple[BilingualTerm, bool]]:
        """
        Find term with OCR error correction.
        Returns (term, was_corrected) tuple.
        """
        text_lower = text.lower().strip()
        
        # First try exact match
        for term in self.terms:
            if term.english.lower() == text_lower:
                return term, False
            if term.urdu.lower() == text_lower:
                return term, False
            if term.pashto and term.pashto.lower() == text_lower:
                return term, False
        
        # Try OCR error patterns
        if text_lower in self.ocr_error_patterns:
            corrected_term = self.ocr_error_patterns[text_lower]
            for term in self.terms:
                if term.english.lower() == corrected_term.lower():
                    return term, True
        
        return None, False
    
    def get_translation(self, text: str, target_lang: Language) -> Optional[str]:
        """Enhanced with OCR-aware lookup"""
        result = self.find_term_with_ocr_correction(text)
        if not result[0]:
            return None
        
        term = result[0]
        if target_lang == Language.ENGLISH:
            return term.english
        elif target_lang == Language.URDU:
            return term.urdu
        elif target_lang == Language.PASHTO and term.pashto:
            return term.pashto
        
        return None
    
    def get_legal_terms(self, min_significance: float = 0.5) -> List[BilingualTerm]:
        """Get terms with high legal significance"""
        return [term for term in self.terms if term.legal_significance >= min_significance]


class CodeSwitchingDetector:
    """Enhanced detector with legal context awareness"""
    
    # Enhanced patterns including legal document patterns
    PATTERNS = [
        # Legal document patterns
        (r'(سیکشن|Section)\s*(\d+[A-Z]*)', 'section_reference'),
        (r'(\d+[A-Z]*)\s*(سیکشن|Section)', 'section_reference_reverse'),
        
        # Parentheses patterns (common in legal bilingual docs)
        (r'([\u0600-\u06FF\s]+)\s*\(([A-Za-z\s]+)\)', 'urdu_english_parentheses'),
        (r'([A-Za-z\s]+)\s*\(([\u0600-\u06FF\s]+)\)', 'english_urdu_parentheses'),
        
        # Legal citation patterns
        (r'([A-Z]+)\s*No\.?\s*(\d+/\d{4})', 'legal_citation'),
        (r'ایس آر او\s*نمبر\s*(\d+/\d{4})', 'urdu_sro_citation'),
        
        # Mixed patterns with OCR awareness
        (r'([\u0600-\u06FF]+)([A-Za-z]+)', 'mixed_word_urdu_first'),
        (r'([A-Za-z]+)([\u0600-\u06FF]+)', 'mixed_word_english_first'),
    ]
    
    def __init__(self):
        self.compiled_patterns = [(re.compile(pattern), name) 
                                  for pattern, name in self.PATTERNS]
        
        # Legal context indicators
        self.legal_indicators = {
            'section': ['سیکشن', 'Section', 'باب', 'Chapter'],
            'penalty': ['جرمانہ', 'Penalty', 'سزا', 'Fine'],
            'definition': ['تعریف', 'Definition', 'مطلب', 'Meaning'],
            'authority': ['اختیار', 'Authority', 'صلاحیت', 'Power']
        }
    
    def detect_switches(self, text: str) -> List[Dict]:
        """Enhanced detection with legal context classification"""
        switches = []
        
        for pattern, pattern_name in self.compiled_patterns:
            for match in pattern.finditer(text):
                groups = match.groups()
                if len(groups) >= 2:
                    switch_info = {
                        'pattern': pattern_name,
                        'full_match': match.group(0),
                        'components': list(groups),
                        'start': match.start(),
                        'end': match.end(),
                        'language_sequence': self._analyze_language_sequence(groups),
                        'legal_context': self._detect_legal_context(match.group(0), text, match.start())
                    }
                    switches.append(switch_info)
        
        return switches
    
    def _analyze_language_sequence(self, components: Tuple[str]) -> List[Language]:
        """Enhanced with OCR error consideration"""
        sequence = []
        for component in components:
            # Clean OCR errors before language detection
            cleaned = Language._correct_ocr_errors(component)
            sequence.append(Language.from_script(cleaned))
        return sequence
    
    def _detect_legal_context(self, matched_text: str, full_text: str, position: int) -> str:
        """Detect legal context of a code-switch"""
        # Check for legal indicators in surrounding text
        context_window = full_text[max(0, position-50):min(len(full_text), position+50)]
        
        for context_type, indicators in self.legal_indicators.items():
            for indicator in indicators:
                if indicator in context_window:
                    return context_type
        
        # Check pattern-specific context
        if 'section' in matched_text.lower() or 'سیکشن' in matched_text:
            return 'section_reference'
        elif 'penalty' in matched_text.lower() or 'جرمانہ' in matched_text:
            return 'penalty'
        elif 'definition' in matched_text.lower() or 'تعریف' in matched_text:
            return 'definition'
        
        return 'general'

    def normalize_switches(self, text: str) -> Tuple[str, List[Dict]]:
        """Normalize code-switches by standardizing their format"""
        switches = self.detect_switches(text)
        normalized_text = text
        processed_switches = []
        
        # Sort switches by position in reverse to avoid offset issues during replacement
        for switch in sorted(switches, key=lambda x: x['start'], reverse=True):
            # For now, we just record them. In a real scenario, we might merge or tag
            processed_switches.append(switch)
            
        return normalized_text, processed_switches

    def get_switch_statistics(self, text: str) -> Dict:
        """Get statistics on code-switching patterns"""
        switches = self.detect_switches(text)
        stats = defaultdict(int)
        for s in switches:
            stats[s['pattern']] += 1
        return dict(stats)


class MultilingualHandler:
    """
    Enhanced main handler with pipeline integration and legal awareness.
    """
    
    def __init__(self, dictionary: Optional[KPKMultilingualDictionary] = None, 
                 pipeline_state: Optional[PipelineState] = None):
        self.dictionary = dictionary or KPKMultilingualDictionary()
        self.switch_detector = CodeSwitchingDetector()
        self.pipeline_state = pipeline_state or PipelineState(
            doc_id="unknown",
            phase=3,
            subphase="3.1_multilingual"
        )
        
        # Enhanced patterns
        self.urdu_pattern = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\u0670-\u06D4]+')
        self.english_pattern = re.compile(r'[A-Za-z]+')
        self.pashto_pattern = re.compile(r'[\u069A\u069B\u069C\u069D\u069E\u06AB\u06AC\u06AD\u06AE\u06B1\u06B3\u06B5\u06B7\u06B9\u06BA\u06BB\u06BC\u06BD\u06BE\u06C0\u06C1\u06C2\u06D2]+')
        
        # Legal document patterns
        self.section_pattern = re.compile(r'(?:سیکشن|Section|باب)\s*(\d+[A-Z]*)', re.IGNORECASE)
        self.citation_pattern = re.compile(r'(?:SRO|ایس آر او)\s*(?:No\.?|نمبر)?\s*(\d+/\d{4})', re.IGNORECASE)
        self.sentence_end_pattern = re.compile(r'(?<=[.!?])\s+')
        
        logger.info("Enhanced MultilingualHandler initialized")
    
    def process_text(self, text: str, doc_type: str = "unknown") -> Dict:
        """
        Enhanced main processing method with pipeline integration.
        Returns structured output for downstream phases.
        """
        self.pipeline_state.metadata['doc_type'] = doc_type
        self.pipeline_state.metadata['input_length'] = len(text)
        
        logger.info(f"Processing {doc_type} document (length: {len(text)})")
        
        # Step 0: Pre-process for common OCR errors
        preprocessed_text = self._preprocess_ocr_errors(text)
        
        # Step 1: Detect code-switching with legal context
        switches = self.switch_detector.detect_switches(preprocessed_text)
        normalized_text, processed_switches = self.switch_detector.normalize_switches(preprocessed_text)
        switch_stats = self.switch_detector.get_switch_statistics(preprocessed_text)
        
        # Step 2: Detect language segments with legal hints
        segments = self.detect_language_segments(normalized_text)
        
        # Step 3: Identify bilingual terms with OCR correction
        identified_terms = self._identify_bilingual_terms_enhanced(normalized_text)
        
        # Step 4: Extract legal elements for downstream phases
        legal_elements = self._extract_legal_elements(normalized_text)
        
        # Step 5: Language-aware chunking optimized for RAG
        chunks = self._create_rag_optimized_chunks(normalized_text, segments, doc_type)
        
        # Step 6: Calculate metrics and decide on abstention
        processing_metrics = self._calculate_processing_metrics(
            text, normalized_text, switches, segments, identified_terms
        )
        
        # Step 7: Check quality gates
        self._apply_quality_gates(processing_metrics)
        
        # Build comprehensive result
        result = {
            'pipeline_state': self.pipeline_state.to_dict(),
            'original_text': text,
            'normalized_text': normalized_text,
            'preprocessed_text': preprocessed_text,
            'code_switching': {
                'total_switches': len(switches),
                'switches': switches[:10],
                'normalized_switches': processed_switches,
                'statistics': switch_stats
            },
            'language_segments': {
                'total_segments': len(segments),
                'segments': [seg.to_dict() for seg in segments[:20]],
                'distribution': self._calculate_language_distribution(segments)
            },
            'bilingual_terms': {
                'total_identified': len(identified_terms),
                'terms': identified_terms,
                'high_legal_significance': [t for t in identified_terms 
                                          if t.get('legal_significance', 0) > 0.7]
            },
            'legal_elements': legal_elements,
            'chunks': {
                'total_chunks': len(chunks),
                'chunks': chunks[:10],
                'chunking_strategy': self._get_chunking_strategy(doc_type)
            },
            'processing_metrics': processing_metrics,
            'downstream_recommendations': self._generate_downstream_recommendations(
                processing_metrics, doc_type
            )
        }
        
        # Update pipeline state
        self.pipeline_state.metadata.update({
            'processing_completed': datetime.now().isoformat(),
            'normalized_length': len(normalized_text),
            'language_segments_count': len(segments),
            'bilingual_terms_count': len(identified_terms)
        })
        
        if self.pipeline_state.status == "abstained":
            result['abstention_reasons'] = self.pipeline_state.abstention_reasons
        
        return result
    
    def _preprocess_ocr_errors(self, text: str) -> str:
        """Pre-process text to fix common OCR errors"""
        # Common OCR errors in KPK forestry documents
        ocr_corrections = {
            'f0rest': 'forest',
            'f0r3st': 'forest',
            'fores t': 'forest',
            'far est': 'forest',
            'De0dar': 'Deodar',
            'Kai1': 'Kail',
            'chi r': 'chir',
            'secti0n': 'section',
            'penaltyy': 'penalty',
            'جرم انہ': 'جرمانہ',
            'سی کشن': 'سیکشن',
            'فار سٹ': 'فارسٹ',
        }
        
        corrected = text
        for error, correction in ocr_corrections.items():
            corrected = corrected.replace(error, correction)
        
        return corrected
    
    def _identify_bilingual_terms_enhanced(self, text: str) -> List[Dict]:
        """Enhanced term identification with OCR correction and legal significance"""
        identified = []
        
        # Split into words and phrases
        words = re.findall(r'\b[\w\u0600-\u06FF][\w\u0600-\u06FF\s]*[\w\u0600-\u06FF]?\b', text)
        
        for word in words:
            term_result = self.dictionary.find_term_with_ocr_correction(word)
            if term_result[0]:
                term, was_corrected = term_result
                identified.append({
                    'original_term': word,
                    'corrected_term': term.english if was_corrected else word,
                    'bilingual_data': term.to_dict(),
                    'was_ocr_corrected': was_corrected,
                    'context': self._get_term_context(text, word),
                    'legal_significance': term.legal_significance
                })
        
        # Sort by legal significance
        identified.sort(key=lambda x: x.get('legal_significance', 0), reverse=True)
        
        return identified
    
    def _extract_legal_elements(self, text: str) -> Dict:
        """Extract legal elements for downstream processing (phase 4)"""
        elements = {
            'sections': [],
            'citations': [],
            'penalties': [],
            'authorities': []
        }
        
        # Extract section references
        for match in self.section_pattern.finditer(text):
            elements['sections'].append({
                'text': match.group(0),
                'number': match.group(1),
                'position': match.start()
            })
        
        # Extract legal citations
        for match in self.citation_pattern.finditer(text):
            elements['citations'].append({
                'text': match.group(0),
                'reference': match.group(1),
                'position': match.start()
            })
        
        # Look for penalty patterns
        penalty_keywords = ['جرمانہ', 'fine', 'penalty', 'سزا']
        for keyword in penalty_keywords:
            pattern = re.compile(rf'{keyword}[^\n.]*?(?:Rs\.|روپیے| rupees)[^\n.]*?\d+', re.IGNORECASE)
            for match in pattern.finditer(text):
                elements['penalties'].append({
                    'text': match.group(0),
                    'keyword': keyword,
                    'position': match.start()
                })
        
        return elements
    
    def _create_rag_optimized_chunks(self, text: str, segments: List[LanguageSegment], 
                                    doc_type: str) -> List[Dict]:
        """
        Create chunks optimized for RAG retrieval.
        Different strategies for different document types.
        """
        if doc_type in ['statute', 'law', 'ordinance']:
            # Legal documents: chunk by section
            return self._chunk_by_sections(text)
        elif doc_type in ['circular', 'notification']:
            # Circulars: chunk by paragraphs with metadata
            return self._chunk_by_paragraphs_with_metadata(text)
        elif doc_type in ['report', 'plan']:
            # Reports: chunk by sections with headings
            return self._chunk_by_headings(text)
        else:
            # Default: sentence-based with language awareness
            return self._create_language_aware_chunks(text, segments)
    
    def _chunk_by_sections(self, text: str) -> List[Dict]:
        """Chunk legal documents by sections"""
        chunks = []
        
        # Find all section markers
        section_pattern = re.compile(r'(?:سیکشن|Section|باب)\s*(\d+[A-Z]*)[\.:]\s*(.*?)(?=(?:سیکشن|Section|باب)\s*\d|$)', 
                                    re.IGNORECASE | re.DOTALL)
        
        for match in section_pattern.finditer(text):
            chunk_text = match.group(0).strip()
            if len(chunk_text) > 50:  # Minimum chunk size
                chunks.append({
                    'chunk_id': f"section_{match.group(1)}",
                    'text': chunk_text,
                    'section': match.group(1),
                    'title': match.group(2).strip()[:100],
                    'length': len(chunk_text),
                    'chunk_type': 'section'
                })
        
        # If no sections found, fall back to paragraph chunking
        if not chunks:
            return self._chunk_by_paragraphs(text)
        
        return chunks
    
    def _chunk_by_paragraphs_with_metadata(self, text: str) -> List[Dict]:
        """Chunk circulars with metadata extraction"""
        chunks = []
        paragraphs = re.split(r'\n\s*\n', text)
        
        for i, para in enumerate(paragraphs):
            if para.strip():
                # Extract metadata from paragraph
                metadata = self._extract_circular_metadata(para)
                
                chunks.append({
                    'chunk_id': f"para_{i:03d}",
                    'text': para.strip(),
                    'length': len(para),
                    'paragraph_num': i + 1,
                    'metadata': metadata,
                    'chunk_type': 'paragraph'
                })
        
        return chunks
    
    def _extract_circular_metadata(self, text: str) -> Dict:
        """Extract metadata from circular text"""
        metadata = {
            'has_reference': bool(re.search(r'(?:Ref|Reference|حوالہ)[:\s]*', text, re.IGNORECASE)),
            'has_date': bool(re.search(r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}', text)),
            'has_department': bool(re.search(r'(?:Forest|فارسٹ|ڈیپارٹمنٹ)', text, re.IGNORECASE)),
            'is_directive': bool(re.search(r'(?:is directed to|ہدایت کی جاتی ہے|مطلوب ہے)', text, re.IGNORECASE))
        }
        return metadata
    
    def _chunk_by_headings(self, text: str) -> List[Dict]:
        """Chunk reports by headings"""
        chunks = []
        
        # Split by lines that look like headings
        lines = text.split('\n')
        current_chunk = []
        current_heading = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if line is a heading
            if (len(line) < 100 and 
                (line.isupper() or 
                 re.match(r'^\d+\.\s+', line) or
                 re.match(r'^[A-Z][a-z]+(?: [A-Z][a-z]+)*:', line))):
                
                # Save previous chunk
                if current_chunk:
                    chunks.append({
                        'chunk_id': f"heading_{len(chunks):03d}",
                        'text': '\n'.join(current_chunk),
                        'heading': current_heading,
                        'length': len('\n'.join(current_chunk)),
                        'chunk_type': 'heading_section'
                    })
                
                # Start new chunk
                current_heading = line
                current_chunk = [line]
            else:
                current_chunk.append(line)
        
        # Add last chunk
        if current_chunk:
            chunks.append({
                'chunk_id': f"heading_{len(chunks):03d}",
                'text': '\n'.join(current_chunk),
                'heading': current_heading,
                'length': len('\n'.join(current_chunk)),
                'chunk_type': 'heading_section'
            })
        
        return chunks
    
    def _create_language_aware_chunks(self, text: str, segments: List[LanguageSegment]) -> List[Dict]:
        """Default language-aware chunking"""
        chunks = []
        sentences = self._split_into_sentences(text)
        
        for i, sentence in enumerate(sentences):
            sent_segments = self.detect_language_segments(sentence)
            lang_composition = self._calculate_language_distribution(sent_segments)
            
            chunks.append({
                'chunk_id': f"sent_{i:04d}",
                'text': sentence,
                'length': len(sentence),
                'language_composition': lang_composition,
                'is_multilingual': len(lang_composition) > 1,
                'primary_language': max(lang_composition.items(), 
                                       key=lambda x: x[1])[0] if lang_composition else 'unknown',
                'chunk_type': 'sentence'
            })
        
        return chunks
    
    def _get_chunking_strategy(self, doc_type: str) -> str:
        """Determine chunking strategy based on document type"""
        strategies = {
            'statute': 'section_based',
            'law': 'section_based',
            'ordinance': 'section_based',
            'circular': 'paragraph_with_metadata',
            'notification': 'paragraph_with_metadata',
            'report': 'heading_based',
            'plan': 'heading_based',
            'default': 'language_aware_sentence'
        }
        
        return strategies.get(doc_type, strategies['default'])
    
    def _calculate_processing_metrics(self, original: str, normalized: str, 
                                     switches: List, segments: List, 
                                     terms: List) -> Dict:
        """Calculate processing metrics for quality assessment"""
        total_chars = len(original)
        normalized_chars = len(normalized)
        
        metrics = {
            'character_reduction': ((total_chars - normalized_chars) / total_chars * 100) 
                                  if total_chars > 0 else 0,
            'code_switch_density': len(switches) / (len(original.split()) / 100) 
                                  if original.split() else 0,
            'language_segment_count': len(segments),
            'bilingual_term_density': len(terms) / (len(original.split()) / 100) 
                                     if original.split() else 0,
            'avg_segment_length': sum(len(s.text) for s in segments) / len(segments) 
                                 if segments else 0,
            'ocr_correction_rate': sum(1 for t in terms if t.get('was_ocr_corrected', False)) 
                                  / len(terms) if terms else 0
        }
        
        return metrics
    
    def _apply_quality_gates(self, metrics: Dict):
        """Apply quality gates and decide on abstention"""
        # Gate 1: Too much character reduction (might be losing content)
        if metrics['character_reduction'] > 30:
            self.pipeline_state.add_abstention(
                "excessive_normalization",
                f"Character reduction: {metrics['character_reduction']:.1f}%"
            )
        
        # Gate 2: Too many code switches (hard to process)
        if metrics['code_switch_density'] > 20:
            self.pipeline_state.add_warning(
                f"High code-switching density: {metrics['code_switch_density']:.1f}"
            )
        
        # Gate 3: Too many language segments (fragmented)
        if metrics['language_segment_count'] > 50:
            self.pipeline_state.add_warning(
                f"High language segment count: {metrics['language_segment_count']}"
            )
    
    def _generate_downstream_recommendations(self, metrics: Dict, doc_type: str) -> Dict:
        """Generate recommendations for downstream phases"""
        recommendations = {
            'phase_4_legal_extraction': {},
            'phase_5_authority_reasoning': {},
            'phase_6_graph_construction': {}
        }
        
        # Recommendations for legal extraction (phase 4)
        if doc_type in ['statute', 'law', 'ordinance']:
            recommendations['phase_4_legal_extraction'] = {
                'priority': 'high',
                'focus': 'section_extraction',
                'suggested_approach': 'rule_based_with_context',
                'confidence_threshold': 0.8
            }
        elif doc_type == 'circular':
            recommendations['phase_4_legal_extraction'] = {
                'priority': 'medium',
                'focus': 'directive_extraction',
                'suggested_approach': 'pattern_matching',
                'confidence_threshold': 0.7
            }
        
        # Recommendations for authority reasoning (phase 5)
        if metrics.get('bilingual_term_density', 0) > 10:
            recommendations['phase_5_authority_reasoning'] = {
                'requires_multilingual_analysis': True,
                'suggested_language_focus': 'urdu_english',
                'context_awareness_needed': True
            }
        
        # Recommendations for graph construction (phase 6)
        if metrics.get('language_segment_count', 0) > 20:
            recommendations['phase_6_graph_construction'] = {
                'chunking_strategy': self._get_chunking_strategy(doc_type),
                'suggested_embedding_model': 'multilingual',
                'requires_language_annotation': True
            }
        
        return recommendations
    
    # Keep the original methods but enhance where needed
    def detect_language_segments(self, text: str) -> List[LanguageSegment]:
        """Enhanced with legal context detection"""
        # Implementation similar to original but with legal context
        segments = []
        current_pos = 0
        text_length = len(text)
        
        while current_pos < text_length:
            next_boundary = self._find_next_language_boundary(text, current_pos)
            
            if next_boundary == -1:
                segment_text = text[current_pos:]
                if segment_text.strip():
                    segment = self._create_language_segment_with_context(segment_text, current_pos, text)
                    segments.append(segment)
                break
            
            segment_text = text[current_pos:next_boundary]
            if segment_text.strip():
                segment = self._create_language_segment_with_context(segment_text, current_pos, text)
                segments.append(segment)
            
            current_pos = next_boundary
        
        segments = self._merge_same_language_segments(segments)
        
        return segments
    
    def _create_language_segment_with_context(self, text: str, start_pos: int, 
                                             full_text: str) -> LanguageSegment:
        """Create segment with legal context detection"""
        # First create basic segment
        basic_segment = self._create_language_segment(text, start_pos)
        
        # Add legal context
        legal_context = self._detect_segment_legal_context(text, start_pos, full_text)
        doc_type_hint = self._detect_document_type_hint(text)
        
        return LanguageSegment(
            text=basic_segment.text,
            language=basic_segment.language,
            confidence=basic_segment.confidence,
            start_pos=basic_segment.start_pos,
            end_pos=basic_segment.end_pos,
            is_mixed=basic_segment.is_mixed,
            mixed_components=basic_segment.mixed_components,
            legal_context=legal_context,
            doc_type_hint=doc_type_hint
        )
    
    def _detect_segment_legal_context(self, segment_text: str, start_pos: int, 
                                     full_text: str) -> Optional[str]:
        """Detect legal context of a segment"""
        # Check for section references
        if self.section_pattern.search(segment_text):
            return 'section_reference'
        
        # Check for penalty mentions
        penalty_keywords = ['جرمانہ', 'fine', 'penalty', 'سزا', 'fine of', 'penalty of']
        for keyword in penalty_keywords:
            if keyword in segment_text.lower():
                return 'penalty'
        
        # Check for definitions
        definition_keywords = ['تعریف', 'definition', 'مطلب', 'means', 'shall mean']
        for keyword in definition_keywords:
            if keyword in segment_text.lower():
                return 'definition'
        
        # Check context in surrounding text
        context_start = max(0, start_pos - 100)
        context_end = min(len(full_text), start_pos + len(segment_text) + 100)
        context = full_text[context_start:context_end]
        
        if any(word in context.lower() for word in ['section', 'سیکشن', 'act', 'قانون']):
            return 'legal_reference'
        
        return None
    
    def _detect_document_type_hint(self, text: str) -> Optional[str]:
        """Detect hints about document type"""
        hints = {
            'statute': ['shall be', 'hereinafter referred to', 'enacted by', 'آن ایکٹ'],
            'circular': ['is circulated', 'for information', 'برائے معلومات', 'حوالہ نمبر'],
            'report': ['findings', 'recommendations', 'مشاہدات', 'تجاویز'],
            'plan': ['objectives', 'targets', 'اهداف', 'ہدف']
        }
        
        text_lower = text.lower()
        for doc_type, indicators in hints.items():
            for indicator in indicators:
                if indicator.lower() in text_lower:
                    return doc_type
        
        return None
    
    # Keep other original methods with minor enhancements
    def _find_next_language_boundary(self, text: str, start_pos: int) -> int:
        """Original implementation"""
        if start_pos >= len(text):
            return -1
        
        current_lang = self._detect_char_language(text[start_pos])
        
        for i in range(start_pos + 1, len(text)):
            char_lang = self._detect_char_language(text[i])
            if char_lang != current_lang and char_lang != Language.UNKNOWN:
                return i
        
        return -1
    
    def _detect_char_language(self, char: str) -> Language:
        """Original implementation"""
        if self.urdu_pattern.match(char):
            if self.pashto_pattern.match(char):
                return Language.PASHTO
            return Language.URDU
        elif self.english_pattern.match(char):
            return Language.ENGLISH
        return Language.UNKNOWN
    
    def _create_language_segment(self, text: str, start_pos: int) -> LanguageSegment:
        """Create a basic language segment with detected primary language"""
        # Determine primary language by character counts
        lang_counts = defaultdict(int)
        for char in text:
            lang = self._detect_char_language(char)
            if lang != Language.UNKNOWN:
                lang_counts[lang] += 1
        
        primary_lang = Language.UNKNOWN
        if lang_counts:
            primary_lang = max(lang_counts.items(), key=lambda x: x[1])[0]
        
        # Confidence based on dominance of primary language
        total_valid = sum(lang_counts.values())
        confidence = lang_counts[primary_lang] / total_valid if total_valid > 0 else 0.0
        
        return LanguageSegment(
            text=text,
            language=primary_lang,
            confidence=confidence,
            start_pos=start_pos,
            end_pos=start_pos + len(text)
        )
    
    def _merge_same_language_segments(self, segments: List[LanguageSegment]) -> List[LanguageSegment]:
        """Merge adjacent segments with the same language"""
        if not segments:
            return []
            
        merged = []
        current = segments[0]
        
        for next_seg in segments[1:]:
            if next_seg.language == current.language:
                # Merge
                current = LanguageSegment(
                    text=current.text + next_seg.text,
                    language=current.language,
                    confidence=(current.confidence + next_seg.confidence) / 2,
                    start_pos=current.start_pos,
                    end_pos=next_seg.end_pos,
                    legal_context=current.legal_context or next_seg.legal_context,
                    doc_type_hint=current.doc_type_hint or next_seg.doc_type_hint
                )
            else:
                merged.append(current)
                current = next_seg
        
        merged.append(current)
        return merged
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Enhanced sentence splitting with legal document awareness"""
        # Special handling for legal documents where "." might appear in numbers
        # Replace dots in numbers temporarily
        protected_text = re.sub(r'(\d+)\.(\d+)', r'\1<DOT>\2', text)
        
        # Now split on sentence boundaries
        sentences = []
        current_start = 0
        
        for match in self.sentence_end_pattern.finditer(protected_text):
            sentence_end = match.end()
            sentence = protected_text[current_start:sentence_end].strip()
            if sentence:
                # Restore dots in numbers
                sentence = sentence.replace('<DOT>', '.')
                sentences.append(sentence)
            current_start = sentence_end
        
        last_sentence = protected_text[current_start:].strip()
        if last_sentence:
            last_sentence = last_sentence.replace('<DOT>', '.')
            sentences.append(last_sentence)
        
        return sentences
    
    def _calculate_language_distribution(self, segments: List[LanguageSegment]) -> Dict[str, float]:
        """Calculate percentage distribution of languages"""
        if not segments:
            return {}
            
        total_len = sum(len(s.text) for s in segments)
        dist = defaultdict(float)
        
        for s in segments:
            dist[s.language.value] += len(s.text)
            
        return {lang: (length / total_len) * 100 for lang, length in dist.items() if total_len > 0}
    
    def _get_term_context(self, text: str, term: str, context_size: int = 50) -> str:
        """Get surrounding context for a term"""
        try:
            pos = text.find(term)
            if pos == -1:
                return ""
            start = max(0, pos - context_size)
            end = min(len(text), pos + len(term) + context_size)
            return text[start:end]
        except:
            return ""
    
    def _chunk_by_paragraphs(self, text: str) -> List[Dict]:
        """Helper method for paragraph chunking"""
        chunks = []
        paragraphs = re.split(r'\n\s*\n', text)
        
        for i, para in enumerate(paragraphs):
            if para.strip():
                chunks.append({
                    'chunk_id': f"para_{i:03d}",
                    'text': para.strip(),
                    'length': len(para),
                    'chunk_type': 'paragraph'
                })
        
        return chunks


# Enhanced utility functions
def load_multilingual_handler(dictionary_path: Optional[str] = None, 
                             pipeline_state: Optional[PipelineState] = None) -> MultilingualHandler:
    """Factory function with pipeline state support"""
    if dictionary_path:
        dictionary = KPKMultilingualDictionary()
        try:
            dictionary.import_from_json(dictionary_path)
        except FileNotFoundError:
            logger.warning(f"Dictionary file not found: {dictionary_path}, using default")
    else:
        dictionary = KPKMultilingualDictionary()
    
    return MultilingualHandler(dictionary, pipeline_state)


def analyze_document_for_pipeline(filepath: str, doc_type: str = "unknown") -> Dict:
    """Enhanced analysis for pipeline integration"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read()
        
        # Create pipeline state
        pipeline_state = PipelineState(
            doc_id=filepath,
            phase=3,
            subphase="3.1_multilingual",
            metadata={'source_file': filepath, 'doc_type': doc_type}
        )
        
        handler = MultilingualHandler(pipeline_state=pipeline_state)
        result = handler.process_text(text, doc_type)
        
        return result
    except Exception as e:
        logger.error(f"Failed to analyze document: {e}")
        error_state = PipelineState(
            doc_id=filepath,
            status="error",
            errors=[str(e)]
        )
        return {'error': str(e), 'pipeline_state': error_state.to_dict()}


# Enhanced testing with pipeline integration
if __name__ == "__main__":
    print("=== ENHANCED MultilingualHandler Test for KPK Forestry Pipeline ===\n")
    
    # Example text with various document types
    example_statute = """
    خیبر پختونخوا فارسٹ آرڈیننس، 2020
    Khyber Pakhtunkhwa Forest Ordinance, 2020
    
    سیکشن 27: غیر مجاز کٹائی کا جرمانہ (Penalty for Unauthorized Cutting)
    
    شق 27(1): اگر کوئی شخص محفوظہ جنگل (Protected Forest) میں درخت کاٹے گا بغیر ڈویژنل فارسٹ آفیسر (DFO) کے تحریری اجازت نامے کے، تو اس پر جرمانہ عائد ہوگا۔
    
    شق 27(2): جرمانے کی تفصیل:
    (الف) دیار (Deodar) درخت - Rs. 100,000 فی درخت
    (ب) کایل (Kail) درخت - Rs. 80,000 فی درخت  
    (ج) چیر (Chir) درخت - Rs. 60,000 فی درخت
    
    نوٹ: یہ قوانین ایس آر او نمبر 456/2020 کے تحت ترمیم شدہ ہیں۔
    """
    
    example_circular = """
    حوالہ نمبر: فاریسٹ/2023/456
    Reference No: Forest/2023/456
    
    تاریخ: 15 مارچ، 2023
    Date: March 15, 2023
    
    عنوان: دیار درختوں کی غیر مجاز کٹائی روکنے کے حوالے سے ہدایات
    Subject: Instructions regarding prevention of unauthorized cutting of Deodar trees
    
    تمام ڈویژنل فارسٹ آفیسران کو ہدایت کی جاتی ہے کہ وہ اپنے اپنے علاقوں میں دیار درختوں کی غیر مجاز کٹائی روکنے کے لیے فوری اقدامات کریں۔
    
    برائے معلومات و ضروری عمل۔
    """
    
    # Test with statute document type
    print("1. PROCESSING STATUTE DOCUMENT:")
    print("-" * 60)
    
    pipeline_state = PipelineState(doc_id="test_statute_001", phase=3)
    handler = MultilingualHandler(pipeline_state=pipeline_state)
    
    result = handler.process_text(example_statute, doc_type="statute")
    
    print(f"Document Type: {result['pipeline_state']['metadata']['doc_type']}")
    print(f"Status: {result['pipeline_state']['status']}")
    print(f"Language Segments: {result['language_segments']['total_segments']}")
    print(f"Code Switches: {result['code_switching']['total_switches']}")
    print(f"Bilingual Terms: {result['bilingual_terms']['total_identified']}")
    
    print(f"\nLegal Elements Found:")
    for element_type, elements in result['legal_elements'].items():
        if elements:
            print(f"  {element_type}: {len(elements)}")
    
    print(f"\nChunking Strategy: {result['chunks'].get('chunking_strategy', 'N/A')}")
    print(f"Chunks Created: {result['chunks']['total_chunks']}")
    
    print(f"\nDownstream Recommendations:")
    for phase, recs in result['downstream_recommendations'].items():
        if recs:
            print(f"  {phase}:")
            for key, value in recs.items():
                print(f"    {key}: {value}")
    
    print("-" * 60)
    
    # Test with circular document type
    print("\n2. PROCESSING CIRCULAR DOCUMENT:")
    print("-" * 60)
    
    pipeline_state2 = PipelineState(doc_id="test_circular_001", phase=3)
    handler2 = MultilingualHandler(pipeline_state=pipeline_state2)
    
    result2 = handler2.process_text(example_circular, doc_type="circular")
    
    print(f"Document Type: {result2['pipeline_state']['metadata']['doc_type']}")
    print(f"Chunking Strategy: {result2['chunks'].get('chunking_strategy', 'N/A')}")
    print(f"Chunks with Metadata: {len([c for c in result2['chunks']['chunks'] if c.get('metadata')])}")
    
    # Show sample chunk
    if result2['chunks']['chunks']:
        sample_chunk = result2['chunks']['chunks'][0]
        print(f"\nSample Chunk (ID: {sample_chunk.get('chunk_id', 'N/A')}):")
        print(f"Type: {sample_chunk.get('chunk_type', 'N/A')}")
        if sample_chunk.get('metadata'):
            print(f"Metadata: {sample_chunk.get('metadata')}")
        print(f"Preview: {sample_chunk.get('text', '')[:100]}...")
    
    print("-" * 60)
    
    # Export enhanced dictionary
    handler.dictionary.export_to_json("enhanced_kpk_dictionary.json")
    print(f"\n✓ Enhanced dictionary exported to 'enhanced_kpk_dictionary.json'")
    
    print("\n" + "=" * 60)
    print("ENHANCED Multilingual Handler Test Complete ✓")
    print("Ready for integration with Phase 4: Legal Extraction")
