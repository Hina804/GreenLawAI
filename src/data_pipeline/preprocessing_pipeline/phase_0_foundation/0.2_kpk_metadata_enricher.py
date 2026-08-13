"""
KPK_METADATA_ENRICHER.PY - Phase 0.2: KPK-Specific Metadata Enricher
Enriches document profile with KPK-specific metadata during initial profiling.
This runs AFTER doc_profiler.py and BEFORE quality assessment.
"""

import re
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from collections import defaultdict, Counter
from datetime import datetime, date
import hashlib

# Import from common modules
try:
    from preprocessing_pipeline.common.config import PipelineConfig
    from preprocessing_pipeline.common.constants import *
    USE_COMMON_CONFIG = True
except ImportError:
    USE_COMMON_CONFIG = False
    print("Warning: common.config not found. Using default configuration.")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class KPKMetadataConfig:
    """Configuration for KPK metadata enrichment"""
    
    # KPK Forest Divisions (enhanced)
    KPK_FOREST_DIVISIONS = {
        'abbottabad': {
            'name': 'Abbottabad Forest Division',
            'ranges': ['Abbottabad', 'Mansehra', 'Murree Hills'],
            'districts': ['Abbottabad', 'Mansehra', 'Haripur', 'Battagram', 'Torghar'],
            'area_ha': 125000,
            'primary_species': ['Deodar', 'Chir Pine', 'Kail', 'Blue Pine'],
            'forest_type': 'Subtropical Pine',
        },
        'mansehra': {
            'name': 'Mansehra Forest Division',
            'ranges': ['Mansehra', 'Battagram', 'Torghar'],
            'districts': ['Mansehra', 'Battagram', 'Torghar', 'Kohistan'],
            'area_ha': 98000,
            'primary_species': ['Deodar', 'Blue Pine', 'Spruce', 'Walnut'],
            'forest_type': 'Temperate Coniferous',
        },
        'swat': {
            'name': 'Swat Forest Division',
            'ranges': ['Swat', 'Shangla', 'Buner'],
            'districts': ['Swat', 'Shangla', 'Buner'],
            'area_ha': 156000,
            'primary_species': ['Deodar', 'Fir', 'Walnut', 'Chilghoza Pine'],
            'forest_type': 'Temperate Mixed',
        },
        'dir': {
            'name': 'Dir Forest Division',
            'ranges': ['Upper Dir', 'Lower Dir', 'Chitral'],
            'districts': ['Upper Dir', 'Lower Dir', 'Chitral'],
            'area_ha': 134000,
            'primary_species': ['Deodar', 'Chilghoza Pine', 'Juniper', 'Spruce'],
            'forest_type': 'Alpine',
        },
        'malakand': {
            'name': 'Malakand Forest Division',
            'ranges': ['Malakand', 'Charsadda', 'Mardan'],
            'districts': ['Malakand', 'Charsadda', 'Mardan', 'Peshawar'],
            'area_ha': 89000,
            'primary_species': ['Shisham', 'Poplar', 'Eucalyptus', 'Kikar'],
            'forest_type': 'Subtropical Broadleaf',
        },
        'kohat': {
            'name': 'Kohat Forest Division',
            'ranges': ['Kohat', 'Hangu', 'Karak'],
            'districts': ['Kohat', 'Hangu', 'Karak'],
            'area_ha': 75000,
            'primary_species': ['Acacia', 'Kikar', 'Shisham', 'Phulai'],
            'forest_type': 'Dry Subtropical',
        },
        'bannu': {
            'name': 'Bannu Forest Division',
            'ranges': ['Bannu', 'Lakki Marwat'],
            'districts': ['Bannu', 'Lakki Marwat'],
            'area_ha': 68000,
            'primary_species': ['Acacia', 'Kikar', 'Phulai', 'Jand'],
            'forest_type': 'Desert',
        },
        'dera_ismail_khan': {
            'name': 'Dera Ismail Khan Forest Division',
            'ranges': ['D.I. Khan', 'Tank'],
            'districts': ['Dera Ismail Khan', 'Tank'],
            'area_ha': 92000,
            'primary_species': ['Kikar', 'Phulai', 'Jand', 'Poplar'],
            'forest_type': 'Riverine',
        },
    }
    
    # KPK Forest Officer Hierarchy (enhanced)
    KPK_OFFICER_HIERARCHY = {
        'chief_conservator': {
            'title': 'Chief Conservator of Forests, KPK',
            'title_urdu': 'چیف کنزرویٹر آف فارسٹس، خیبر پختونخوا',
            'responsibilities': ['Overall administration', 'Policy implementation', 'Budget allocation'],
            'jurisdiction': 'Provincial',
            'typical_signature_phrases': ['Chief Conservator of Forests', 'CCF KPK'],
        },
        'conservator': {
            'title': 'Conservator of Forests',
            'title_urdu': 'کنسرویٹر آف فارسٹس',
            'responsibilities': ['Regional administration', 'Budget management', 'Coordination'],
            'jurisdiction': 'Circle',
            'typical_signature_phrases': ['Conservator of Forests', 'CF'],
        },
        'divisional_officer': {
            'title': 'Divisional Forest Officer (DFO)',
            'title_urdu': 'ڈویژنل فارسٹ آفیسر',
            'responsibilities': ['Division management', 'Law enforcement', 'Permission granting'],
            'jurisdiction': 'Division',
            'typical_signature_phrases': ['Divisional Forest Officer', 'DFO', 'Forest Officer'],
        },
        'range_officer': {
            'title': 'Range Officer',
            'title_urdu': 'رینج آفیسر',
            'responsibilities': ['Range supervision', 'Patrol management', 'Field inspections'],
            'jurisdiction': 'Range',
            'typical_signature_phrases': ['Range Officer', 'RO'],
        },
        'beat_guard': {
            'title': 'Beat Guard / Forest Guard',
            'title_urdu': 'بیٹ گارڈ / فارسٹ گارڈ',
            'responsibilities': ['Field patrol', 'Offense detection', 'Report submission'],
            'jurisdiction': 'Beat',
            'typical_signature_phrases': ['Beat Guard', 'Forest Guard'],
        },
    }
    
    # KPK Legal Document Types (enhanced)
    KPK_DOCUMENT_TYPES = {
        'forest_act': {
            'patterns': ['forest act', 'جنگلات ایکٹ'],
            'years': ['1927', '2002', '2010'],
            'authority': 'Provincial Assembly of KPK',
            'jurisdiction': 'KPK Province',
        },
        'forest_ordinance': {
            'patterns': ['forest ordinance', 'جنگلات آرڈیننس'],
            'years': ['2002', '2015'],
            'authority': 'Governor of KPK',
            'jurisdiction': 'KPK Province',
        },
        'forest_rules': {
            'patterns': ['forest rules', 'جنگلات قواعد'],
            'authority': 'Forest Department KPK',
            'jurisdiction': 'Departmental',
        },
        'working_plan': {
            'patterns': ['working plan', 'ورکنگ پلان'],
            'typical_structure': ['compartment', 'silvicultural', 'management'],
            'jurisdiction': 'Division-specific',
        },
        'circular': {
            'patterns': ['circular', 'سرکلر'],
            'number_pattern': r'circular.*no.*(\d+)',
            'authority': 'Various department heads',
            'jurisdiction': 'Department-wide',
        },
        'notification': {
            'patterns': ['notification', 'نوٹیفیکیشن'],
            'types': ['SRO', 'GO', 'Notification'],
            'authority': 'Government of KPK',
            'jurisdiction': 'Provincial',
        },
    }
    
    # KPK Tree Species Legal Status (enhanced)
    KPK_SPECIES_STATUS = {
        'fully_protected': {
            'species': ['Deodar', 'Chilghoza Pine', 'Kail', 'Fir', 'Spruce', 'Walnut'],
            'urdu_names': ['دیودار', 'چلغوزہ', 'کائل', 'فر', 'سپروس', 'اخروٹ'],
            'cutting_permit': 'Prohibited (only dead/diseased with special permit)',
            'penalty_multiplier': 3.0,
            'conservation_status': 'Endangered/Vulnerable',
        },
        'regulated': {
            'species': ['Chir Pine', 'Blue Pine', 'Oak', 'Juniper', 'Poplar'],
            'urdu_names': ['چیر پائن', 'بلیو پائن', 'شاہ بلوط', 'جونیپر', 'پاپلر'],
            'cutting_permit': 'Required with department permission',
            'penalty_multiplier': 1.5,
            'conservation_status': 'Managed',
        },
        'non_protected': {
            'species': ['Eucalyptus', 'Shisham', 'Willow', 'Acacia', 'Kikar', 'Phulai'],
            'urdu_names': ['یوکلپٹس', 'شیشم', 'بید', 'اکیشیا', 'کیکر', 'پھلائی'],
            'cutting_permit': 'Required but easily obtained',
            'penalty_multiplier': 1.0,
            'conservation_status': 'Common',
        },
    }
    
    # KPK-specific keywords and phrases
    KPK_KEYWORDS = {
        'jurisdiction': [
            'Khyber Pakhtunkhwa', 'KPK', 'خیبر پختونخوا', 'NWFP', 'North West Frontier',
            'province of KPK', 'صوبہ خیبر پختونخوا',
        ],
        'forest_terms': [
            'reserved forest', 'protected forest', 'unclassed forest', 'guzara forest',
            'محفوظ جنگل', 'محمود جنگل', 'غیر درجہ بند جنگل', 'گزارہ جنگل',
        ],
        'legal_terms': [
            'felling', 'transport', 'transit permit', 'royalty', 'seizure',
            'کٹائی', 'ٹرانسپورٹ', 'ٹرانزٹ پرمٹ', 'رائلٹی', 'ضبطی',
        ],
        'geographic_terms': [
            'division', 'range', 'beat', 'compartment', 'block',
            'ڈویژن', 'رینج', 'بیٹ', 'کمپارٹمنٹ', 'بلاک',
        ],
    }
    
    # Penalty structures in KPK (for quick reference)
    KPK_PENALTY_STRUCTURES = {
        'unauthorized_felling': {
            'base_penalty': 50000,
            'per_tree_additional': 10000,
            'protected_species_multiplier': 3.0,
            'imprisonment_range': '1-3 years',
        },
        'illegal_transport': {
            'base_penalty': 25000,
            'per_vehicle_additional': 5000,
            'timber_value_multiplier': 0.5,
            'imprisonment_range': '6 months - 2 years',
        },
        'forest_fire': {
            'base_penalty': 100000,
            'area_damaged_multiplier': 1000,
            'negligence_multiplier': 2.0,
            'imprisonment_range': '2-5 years',
        },
        'encroachment': {
            'base_penalty': 50000,
            'per_hectare_additional': 20000,
            'duration_multiplier': 1.5,
            'imprisonment_range': '1-2 years',
        },
    }


class KPKMetadataEnricher:
    """
    Phase 0.2: KPK-Specific Metadata Enricher
    Enriches document profile with KPK-specific metadata during initial profiling.
    This runs AFTER doc_profiler.py and BEFORE quality assessment.
    """
    
    def __init__(self, 
                 config: Optional[KPKMetadataConfig] = None,
                 enable_logging: bool = True,
                 logger: Optional[logging.Logger] = None):
        """
        Initialize KPK metadata enricher.
        
        Args:
            config: Optional configuration
            enable_logging: Whether to enable logging
            logger: Optional logger instance
        """
        self.config = config or KPKMetadataConfig()
        self.enable_logging = enable_logging
        self.logger = logger or logging.getLogger(__name__)
        
        # Statistics
        self.stats = {
            'documents_enriched': 0,
            'kpk_documents_identified': 0,
            'divisions_identified': [],
            'species_detected': [],
            'enrichment_time_total': 0.0,
            'metadata_fields_added': 0,
        }
        
        # Compile patterns for efficiency
        self._compile_patterns()
        
        self.logger.info("KPKMetadataEnricher initialized")
    
    def _compile_patterns(self):
        """Compile regex patterns for efficiency"""
        # KPK jurisdiction patterns
        self.kpk_jurisdiction_patterns = [
            re.compile(r'khyber\s+pakhtunkhwa', re.IGNORECASE),
            re.compile(r'\bKPK\b', re.IGNORECASE),
            re.compile(r'خیبر\s*پختونخوا', re.IGNORECASE),
            re.compile(r'صوبہ\s*خیبر\s*پختونخوا', re.IGNORECASE),
            re.compile(r'north[-\s]west\s+frontier', re.IGNORECASE),
            re.compile(r'\bNWFP\b', re.IGNORECASE),
        ]
        
        # Division patterns
        self.division_patterns = {}
        for division_name, division_info in self.config.KPK_FOREST_DIVISIONS.items():
            patterns = [re.compile(rf'\b{division_name}\b', re.IGNORECASE)]
            # Add district patterns
            for district in division_info.get('districts', []):
                patterns.append(re.compile(rf'\b{district}\b', re.IGNORECASE))
            self.division_patterns[division_name] = patterns
        
        # Document type patterns
        self.doc_type_patterns = {}
        for doc_type, type_info in self.config.KPK_DOCUMENT_TYPES.items():
            patterns = []
            for pattern in type_info.get('patterns', []):
                patterns.append(re.compile(pattern, re.IGNORECASE))
            self.doc_type_patterns[doc_type] = patterns
        
        # Species patterns
        self.species_patterns = {}
        for status, status_info in self.config.KPK_SPECIES_STATUS.items():
            patterns = []
            for species in status_info.get('species', []):
                patterns.append(re.compile(rf'\b{species}\b', re.IGNORECASE))
            for urdu_name in status_info.get('urdu_names', []):
                patterns.append(re.compile(urdu_name))
            self.species_patterns[status] = patterns
    
    def enrich_metadata(self, document_profile: Dict, extracted_text: Optional[str] = None) -> Dict[str, Any]:
        """
        Enrich document profile with KPK-specific metadata.
        
        Args:
            document_profile: Document profile from doc_profiler.py
            extracted_text: Extracted text for analysis (if available)
            
        Returns:
            Enriched document profile with KPK metadata
        """
        import time
        start_time = time.time()
        
        try:
            # Type check: if document_profile is a string, it's likely an error message from a previous phase
            if isinstance(document_profile, str):
                self.logger.error(f"Received error string instead of profile: {document_profile}")
                return {"kpk_enrichment_error": f"Invalid profile received: {document_profile}", "is_kpk_enriched": False}

            # Create enriched profile copy
            enriched_profile = document_profile.copy()
            
            # Initialize KPK metadata section
            if 'kpk_metadata' not in enriched_profile:
                enriched_profile['kpk_metadata'] = {}
            
            kpk_metadata = enriched_profile['kpk_metadata']
            
            # Step 1: Basic KPK identification
            self._enrich_kpk_identification(kpk_metadata, document_profile, extracted_text)
            
            # Step 2: Geographic enrichment
            self._enrich_geographic_metadata(kpk_metadata, extracted_text)
            
            # Step 3: Document type specialization
            self._enrich_document_type_metadata(kpk_metadata, document_profile, extracted_text)
            
            # Step 4: Species and ecological metadata
            self._enrich_species_metadata(kpk_metadata, extracted_text)
            
            # Step 5: Legal and penalty metadata
            self._enrich_legal_metadata(kpk_metadata, extracted_text)
            
            # Step 6: Temporal and historical context
            self._enrich_temporal_metadata(kpk_metadata, document_profile)
            
            # Step 7: Authority and hierarchy metadata
            self._enrich_authority_metadata(kpk_metadata, extracted_text)
            
            # Step 8: Generate metadata summary
            self._generate_metadata_summary(kpk_metadata)
            
            # Update enrichment flags
            enriched_profile['is_kpk_enriched'] = True
            enriched_profile['kpk_enrichment_date'] = datetime.now().isoformat()
            enriched_profile['kpk_enrichment_version'] = '1.0'
            
            # Update statistics
            self.stats['documents_enriched'] += 1
            if kpk_metadata.get('is_kpk_jurisdiction', False):
                self.stats['kpk_documents_identified'] += 1
            
            # Calculate enrichment time
            enrichment_time = time.time() - start_time
            self.stats['enrichment_time_total'] += enrichment_time
            
            # Count metadata fields added
            metadata_fields = len(kpk_metadata)
            self.stats['metadata_fields_added'] += metadata_fields
            
            if self.enable_logging:
                self.logger.info(f"Enriched document: {document_profile.get('filename', 'unknown')}")
                self.logger.info(f"  - KPK jurisdiction: {kpk_metadata.get('is_kpk_jurisdiction', False)}")
                self.logger.info(f"  - Divisions identified: {len(kpk_metadata.get('identified_divisions', []))}")
                self.logger.info(f"  - Species detected: {len(kpk_metadata.get('detected_species', []))}")
                self.logger.info(f"  - Metadata fields: {metadata_fields}")
            
            return enriched_profile
            
        except Exception as e:
            error_msg = f"Error enriching KPK metadata: {str(e)}"
            if self.enable_logging:
                self.logger.error(error_msg, exc_info=True)
            
            # Return original profile with error marker
            document_profile['kpk_enrichment_error'] = error_msg
            document_profile['kpk_enrichment_complete'] = False
            return document_profile
    
    def _enrich_kpk_identification(self, kpk_metadata: Dict, profile: Dict, text: Optional[str]):
        """Enrich basic KPK identification metadata"""
        kpk_metadata['kpk_identification'] = {
            'is_kpk_jurisdiction': False,
            'identification_method': 'unknown',
            'confidence_score': 0.0,
            'supporting_evidence': [],
        }
        
        identification = kpk_metadata['kpk_identification']
        
        # Method 1: Check profile metadata
        if profile.get('is_kpk', False):
            identification['is_kpk_jurisdiction'] = True
            identification['identification_method'] = 'profile_metadata'
            identification['confidence_score'] = 0.9
            identification['supporting_evidence'].append('Profile metadata indicates KPK document')
        
        # Method 2: Check extracted text
        if text:
            text_lower = text.lower()
            
            # Check for KPK jurisdiction patterns
            kpk_matches = []
            for pattern in self.kpk_jurisdiction_patterns:
                matches = pattern.findall(text_lower)
                if matches:
                    kpk_matches.extend(matches)
            
            if kpk_matches:
                identification['is_kpk_jurisdiction'] = True
                identification['identification_method'] = 'text_pattern_matching'
                identification['confidence_score'] = max(identification['confidence_score'], 0.8)
                identification['supporting_evidence'].append(f"Found KPK patterns: {', '.join(set(kpk_matches[:5]))}")
            
            # Check for KPK government references
            gov_patterns = [
                r'government\s+of\s+kpk',
                r'kpk\s+government',
                r'حکومت\s+خیبر\s+پختونخوا',
                r'پختونخوا\s+حکومت',
            ]
            
            for pattern in gov_patterns:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    identification['is_kpk_jurisdiction'] = True
                    identification['confidence_score'] = max(identification['confidence_score'], 0.85)
                    identification['supporting_evidence'].append("Found KPK government reference")
                    break
        
        # Method 3: Check filename
        filename = profile.get('filename', '').lower()
        if any(kpk_term in filename for kpk_term in ['kpk', 'khyber', 'خیبر', 'پختونخوا']):
            identification['is_kpk_jurisdiction'] = True
            identification['confidence_score'] = max(identification['confidence_score'], 0.7)
            identification['supporting_evidence'].append(f"Filename suggests KPK: {filename}")
        
        # Set overall KPK flag
        kpk_metadata['is_kpk_jurisdiction'] = identification['is_kpk_jurisdiction']
        kpk_metadata['kpk_identification_confidence'] = identification['confidence_score']
    
    def _enrich_geographic_metadata(self, kpk_metadata: Dict, text: Optional[str]):
        """Enrich geographic metadata"""
        kpk_metadata['geographic_metadata'] = {
            'identified_divisions': [],
            'identified_districts': [],
            'geographic_scope': 'unknown',
            'forest_types_present': [],
            'geographic_confidence': 0.0,
        }
        
        geo_metadata = kpk_metadata['geographic_metadata']
        
        if not text:
            return
        
        text_lower = text.lower()
        identified_divisions = []
        identified_districts = []
        forest_types = set()
        
        # Identify divisions and districts
        for division_name, patterns in self.division_patterns.items():
            division_matches = []
            for pattern in patterns:
                matches = pattern.findall(text_lower)
                if matches:
                    division_matches.extend(matches)
            
            if division_matches:
                identified_divisions.append(division_name)
                geo_metadata['geographic_confidence'] = 0.7
                
                # Add division info
                if division_name in self.config.KPK_FOREST_DIVISIONS:
                    division_info = self.config.KPK_FOREST_DIVISIONS[division_name]
                    
                    # Add forest type
                    if 'forest_type' in division_info:
                        forest_types.add(division_info['forest_type'])
                    
                    # Add districts
                    for district in division_info.get('districts', []):
                        if district.lower() in text_lower:
                            identified_districts.append(district)
        
        # Check for geographic scope indicators
        scope_indicators = {
            'provincial': ['province', 'whole province', 'entire kpk', 'صوبہ بھر'],
            'divisional': ['division', 'entire division', 'ڈویژن بھر'],
            'district': ['district', 'entire district', 'ضلع بھر'],
            'local': ['range', 'beat', 'compartment', 'block', 'رینج', 'بیٹ'],
        }
        
        for scope, indicators in scope_indicators.items():
            for indicator in indicators:
                if indicator in text_lower:
                    geo_metadata['geographic_scope'] = scope
                    break
            if geo_metadata['geographic_scope'] != 'unknown':
                break
        
        # If no scope determined, infer from divisions
        if geo_metadata['geographic_scope'] == 'unknown':
            if len(identified_divisions) == 0:
                geo_metadata['geographic_scope'] = 'provincial'  # Assume provincial if no divisions mentioned
            elif len(identified_divisions) == 1:
                geo_metadata['geographic_scope'] = 'divisional'
            else:
                geo_metadata['geographic_scope'] = 'regional'
        
        # Update metadata
        geo_metadata['identified_divisions'] = list(set(identified_divisions))
        geo_metadata['identified_districts'] = list(set(identified_districts))
        geo_metadata['forest_types_present'] = list(forest_types)
        
        # Add division details
        geo_metadata['division_details'] = {}
        for division in geo_metadata['identified_divisions']:
            if division in self.config.KPK_FOREST_DIVISIONS:
                geo_metadata['division_details'][division] = self.config.KPK_FOREST_DIVISIONS[division]
        
        # Update stats
        self.stats['divisions_identified'].extend(identified_divisions)
    
    def _enrich_document_type_metadata(self, kpk_metadata: Dict, profile: Dict, text: Optional[str]):
        """Enrich document type with KPK specialization"""
        kpk_metadata['document_type_metadata'] = {
            'kpk_document_type': 'unknown',
            'kpk_specific_classification': {},
            'document_subtype': 'generic',
            'authority_level': 'unknown',
        }
        
        doc_metadata = kpk_metadata['document_type_metadata']
        doc_type = profile.get('document_type', 'unknown')
        
        # Map to KPK document types
        doc_type_mapping = {
            'LAW': 'forest_act',
            'ORDINANCE': 'forest_ordinance',
            'RULE': 'forest_rules',
            'WORKING_PLAN': 'working_plan',
            'CIRCULAR': 'circular',
            'GAZETTE': 'notification',
            'NOTIFICATION': 'notification',
        }
        
        if doc_type in doc_type_mapping:
            kpk_doc_type = doc_type_mapping[doc_type]
            doc_metadata['kpk_document_type'] = kpk_doc_type
            
            if kpk_doc_type in self.config.KPK_DOCUMENT_TYPES:
                type_info = self.config.KPK_DOCUMENT_TYPES[kpk_doc_type]
                doc_metadata['kpk_specific_classification'] = {
                    'patterns': type_info.get('patterns', []),
                    'authority': type_info.get('authority', 'unknown'),
                    'jurisdiction': type_info.get('jurisdiction', 'unknown'),
                }
        
        # Determine authority level
        authority_mapping = {
            'forest_act': 'legislative',
            'forest_ordinance': 'executive',
            'forest_rules': 'administrative',
            'working_plan': 'operational',
            'circular': 'directive',
            'notification': 'official',
        }
        
        if doc_metadata['kpk_document_type'] in authority_mapping:
            doc_metadata['authority_level'] = authority_mapping[doc_metadata['kpk_document_type']]
        
        # Check for specific year references in text
        if text:
            year_pattern = r'\b(19\d{2}|20\d{2})\b'
            years_found = re.findall(year_pattern, text)
            
            if years_found:
                doc_metadata['document_years'] = list(set(years_found))
                
                # Check if year matches known KPK forest law years
                known_years = ['1927', '2002', '2010', '2015', '2020']
                for year in known_years:
                    if year in years_found:
                        doc_metadata['likely_kpk_law_year'] = year
                        break
        
        # Determine document subtype based on content
        if text:
            text_lower = text.lower()
            
            if 'guzara' in text_lower or 'گزارہ' in text:
                doc_metadata['document_subtype'] = 'guzara_forest'
            elif 'reserved' in text_lower or 'محفوظ' in text:
                doc_metadata['document_subtype'] = 'reserved_forest'
            elif 'protected' in text_lower or 'محمود' in text:
                doc_metadata['document_subtype'] = 'protected_forest'
            elif 'working plan' in text_lower or 'ورکنگ پلان' in text:
                doc_metadata['document_subtype'] = 'management_plan'
            elif 'circular' in text_lower or 'سرکلر' in text:
                # Check circular number
                circular_match = re.search(r'circular.*no.*[:\s]*(\d+)', text_lower, re.IGNORECASE)
                if circular_match:
                    doc_metadata['circular_number'] = circular_match.group(1)
    
    def _enrich_species_metadata(self, kpk_metadata: Dict, text: Optional[str]):
        """Enrich species and ecological metadata"""
        kpk_metadata['species_metadata'] = {
            'detected_species': [],
            'species_by_status': {},
            'conservation_concerns': [],
            'ecological_context': {},
        }
        
        species_metadata = kpk_metadata['species_metadata']
        
        if not text:
            return
        
        text_lower = text.lower()
        detected_species = []
        species_by_status = defaultdict(list)
        
        # Detect species by status category
        for status, patterns in self.species_patterns.items():
            for pattern in patterns:
                matches = pattern.findall(text_lower)
                if matches:
                    # Get actual matched text (case preserved)
                    for match in matches:
                        if match:  # Check for non-empty matches
                            species_name = match.strip()
                            if species_name not in detected_species:
                                detected_species.append(species_name)
                                species_by_status[status].append(species_name)
        
        # Get species details
        species_details = []
        for status, species_list in species_by_status.items():
            for species in species_list:
                # Find species in config
                for status_key, status_info in self.config.KPK_SPECIES_STATUS.items():
                    if species in status_info.get('species', []):
                        species_details.append({
                            'name': species,
                            'status': status_key,
                            'cutting_permit': status_info.get('cutting_permit', 'unknown'),
                            'penalty_multiplier': status_info.get('penalty_multiplier', 1.0),
                            'conservation_status': status_info.get('conservation_status', 'unknown'),
                        })
                        break
                else:
                    # Species not in config, add with generic info
                    species_details.append({
                        'name': species,
                        'status': 'unknown',
                        'cutting_permit': 'unknown',
                        'penalty_multiplier': 1.0,
                        'conservation_status': 'unknown',
                    })
        
        # Check for conservation concerns
        conservation_patterns = [
            r'endangered',
            r'threatened',
            r'vulnerable',
            r'rare',
            r'خطرے\s+میں',
            r'نایاب',
        ]
        
        conservation_concerns = []
        for pattern in conservation_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                conservation_concerns.append(pattern)
                break
        
        # Update metadata
        species_metadata['detected_species'] = detected_species
        species_metadata['species_by_status'] = dict(species_by_status)
        species_metadata['species_details'] = species_details
        species_metadata['conservation_concerns'] = conservation_concerns
        
        # Add ecological context
        if detected_species:
            species_metadata['ecological_context'] = {
                'biodiversity_indicator': len(detected_species) > 3,
                'protected_species_present': any('fully_protected' in status for status in species_by_status),
                'commercial_species_present': any(species in ['Chir Pine', 'Deodar', 'Walnut'] for species in detected_species),
            }
        
        # Update stats
        self.stats['species_detected'].extend(detected_species)
    
    def _enrich_legal_metadata(self, kpk_metadata: Dict, text: Optional[str]):
        """Enrich legal and penalty metadata"""
        kpk_metadata['legal_metadata'] = {
            'penalty_references': [],
            'permit_types': [],
            'legal_keywords': [],
            'compliance_requirements': [],
        }
        
        legal_metadata = kpk_metadata['legal_metadata']
        
        if not text:
            return
        
        # Extract penalty references
        penalty_patterns = [
            r'Rs\.?\s*([\d,]+(?:\.\d+)?)',
            r'روپے\s*([\d,]+)',
            r'fine\s+of\s+Rs\.?\s*([\d,]+)',
            r'جرمانہ\s*:?\s*روپے\s*([\d,]+)',
            r'penalty.*?Rs\.?\s*([\d,]+)',
        ]
        
        penalty_references = []
        for pattern in penalty_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, str):
                    # Clean the amount
                    amount = match.replace(',', '').strip()
                    if amount.isdigit() or ('.' in amount and amount.replace('.', '').isdigit()):
                        penalty_references.append({
                            'amount': float(amount) if '.' in amount else int(amount),
                            'pattern': pattern,
                        })
        
        legal_metadata['penalty_references'] = penalty_references
        
        # Extract permit types
        permit_patterns = [
            (r'felling permit', 'felling'),
            (r'cutting permit', 'cutting'),
            (r'transit permit', 'transit'),
            (r'transport permit', 'transport'),
            (r'کٹائی\s+اجازت', 'cutting'),
            (r'ٹرانزٹ\s+پرمٹ', 'transit'),
        ]
        
        permit_types = set()
        for pattern, permit_type in permit_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                permit_types.add(permit_type)
        
        legal_metadata['permit_types'] = list(permit_types)
        
        # Extract legal keywords
        legal_keywords = []
        for category, keywords in self.config.KPK_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in text.lower():
                    legal_keywords.append({
                        'keyword': keyword,
                        'category': category,
                    })
        
        legal_metadata['legal_keywords'] = legal_keywords
        
        # Check for compliance requirements
        compliance_patterns = [
            r'must\s+obtain',
            r'required\s+to',
            r'obligation\s+to',
            r'لازمی\s+ہے',
            r'ضروری\s+ہے',
        ]
        
        compliance_requirements = []
        for pattern in compliance_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                # Extract context around match
                start = max(0, match.start() - 50)
                end = min(len(text), match.end() + 50)
                context = text[start:end].strip()
                compliance_requirements.append({
                    'pattern': pattern,
                    'context': context,
                })
        
        legal_metadata['compliance_requirements'] = compliance_requirements[:5]  # Limit to 5
    
    def _enrich_temporal_metadata(self, kpk_metadata: Dict, profile: Dict):
        """Enrich temporal and historical context metadata"""
        kpk_metadata['temporal_metadata'] = {
            'document_era': 'unknown',
            'historical_context': {},
            'temporal_relevance': 'unknown',
            'amendment_history_present': False,
        }
        
        temporal_metadata = kpk_metadata['temporal_metadata']
        
        # Extract year from profile
        year = None
        if 'document_number' in profile:
            # Try to extract year from document number
            year_match = re.search(r'\b(19\d{2}|20\d{2})\b', str(profile['document_number']))
            if year_match:
                year = int(year_match.group(1))
        
        if not year and 'creation_date' in profile:
            # Try to get year from creation date
            try:
                if isinstance(profile['creation_date'], str):
                    # Parse ISO format or other date format
                    date_str = profile['creation_date'][:10]  # Get YYYY-MM-DD part
                    year = int(date_str[:4])
            except (ValueError, TypeError, IndexError):
                pass
        
        if year:
            temporal_metadata['document_year'] = year
            
            # Determine document era
            if year < 1947:
                temporal_metadata['document_era'] = 'british_colonial'
                temporal_metadata['historical_context'] = {
                    'period': 'British India',
                    'significance': 'Pre-independence forest laws',
                }
            elif 1947 <= year < 1970:
                temporal_metadata['document_era'] = 'early_pakistan'
                temporal_metadata['historical_context'] = {
                    'period': 'Early Pakistan',
                    'significance': 'Post-independence consolidation',
                }
            elif 1970 <= year < 2000:
                temporal_metadata['document_era'] = 'late_20th_century'
                temporal_metadata['historical_context'] = {
                    'period': 'Late 20th Century',
                    'significance': 'Modern forest management',
                }
            elif 2000 <= year < 2010:
                temporal_metadata['document_era'] = 'early_21st_century'
                temporal_metadata['historical_context'] = {
                    'period': 'Early 21st Century',
                    'significance': 'Post-devolution reforms',
                }
            else:
                temporal_metadata['document_era'] = 'contemporary'
                temporal_metadata['historical_context'] = {
                    'period': 'Contemporary',
                    'significance': 'Current forest policies',
                }
            
            # Determine temporal relevance
            current_year = datetime.now().year
            age = current_year - year
            
            if age < 5:
                temporal_metadata['temporal_relevance'] = 'very_recent'
            elif age < 10:
                temporal_metadata['temporal_relevance'] = 'recent'
            elif age < 20:
                temporal_metadata['temporal_relevance'] = 'moderately_recent'
            elif age < 50:
                temporal_metadata['temporal_relevance'] = 'historical'
            else:
                temporal_metadata['temporal_relevance'] = 'archival'
        
        # Check for amendment indicators
        if 'amendment_count' in profile and profile['amendment_count'] > 0:
            temporal_metadata['amendment_history_present'] = True
            temporal_metadata['amendment_count'] = profile['amendment_count']
    
    def _enrich_authority_metadata(self, kpk_metadata: Dict, text: Optional[str]):
        """Enrich authority and hierarchy metadata"""
        kpk_metadata['authority_metadata'] = {
            'officers_mentioned': [],
            'authority_hierarchy': {},
            'signature_patterns': [],
            'issuing_authority': 'unknown',
        }
        
        authority_metadata = kpk_metadata['authority_metadata']
        
        if not text:
            return
        
        # Detect officers mentioned
        officers_detected = []
        for officer_type, officer_info in self.config.KPK_OFFICER_HIERARCHY.items():
            # Check for title patterns
            title = officer_info.get('title', '')
            if title.lower() in text.lower():
                officers_detected.append({
                    'type': officer_type,
                    'title': title,
                    'hierarchy_level': officer_info.get('jurisdiction', 'unknown'),
                })
            
            # Check for Urdu title
            urdu_title = officer_info.get('title_urdu', '')
            if urdu_title and urdu_title in text:
                officers_detected.append({
                    'type': officer_type,
                    'title': urdu_title,
                    'hierarchy_level': officer_info.get('jurisdiction', 'unknown'),
                    'language': 'urdu',
                })
            
            # Check for signature phrases
            for phrase in officer_info.get('typical_signature_phrases', []):
                if phrase.lower() in text.lower():
                    authority_metadata['signature_patterns'].append({
                        'phrase': phrase,
                        'officer_type': officer_type,
                    })
        
        authority_metadata['officers_mentioned'] = officers_detected
        
        # Determine issuing authority based on highest officer mentioned
        if officers_detected:
            hierarchy_order = ['chief_conservator', 'conservator', 'divisional_officer', 'range_officer', 'beat_guard']
            for officer_level in hierarchy_order:
                for officer in officers_detected:
                    if officer['type'] == officer_level:
                        authority_metadata['issuing_authority'] = officer_level
                        break
                if authority_metadata['issuing_authority'] != 'unknown':
                    break
        
        # Build authority hierarchy
        authority_metadata['authority_hierarchy'] = {
            'provincial': {
                'officer': 'Chief Conservator of Forests',
                'jurisdiction': 'Entire KPK',
            },
            'circle': {
                'officer': 'Conservator of Forests',
                'jurisdiction': 'Administrative Circle',
            },
            'division': {
                'officer': 'Divisional Forest Officer',
                'jurisdiction': 'Forest Division',
            },
            'range': {
                'officer': 'Range Officer',
                'jurisdiction': 'Forest Range',
            },
            'beat': {
                'officer': 'Beat Guard',
                'jurisdiction': 'Forest Beat',
            },
        }
    
    def _generate_metadata_summary(self, kpk_metadata: Dict):
        """Generate summary of KPK metadata"""
        summary = {
            'metadata_completeness': 0.0,
            'key_findings': [],
            'processing_implications': [],
            'confidence_level': 'low',
        }
        
        # Calculate completeness score
        sections = [
            'kpk_identification',
            'geographic_metadata',
            'document_type_metadata',
            'species_metadata',
            'legal_metadata',
            'temporal_metadata',
            'authority_metadata',
        ]
        
        present_sections = [section for section in sections if section in kpk_metadata]
        completeness = len(present_sections) / len(sections) if sections else 0.0
        summary['metadata_completeness'] = completeness
        
        # Generate key findings
        key_findings = []
        
        # KPK identification
        if kpk_metadata.get('is_kpk_jurisdiction', False):
            key_findings.append("Document has KPK jurisdiction")
        
        # Geographic findings
        geo_meta = kpk_metadata.get('geographic_metadata', {})
        if geo_meta.get('identified_divisions'):
            divisions = ', '.join(geo_meta['identified_divisions'])
            key_findings.append(f"Applies to divisions: {divisions}")
        
        # Species findings
        species_meta = kpk_metadata.get('species_metadata', {})
        if species_meta.get('detected_species'):
            species_count = len(species_meta['detected_species'])
            key_findings.append(f"References {species_count} tree species")
        
        # Legal findings
        legal_meta = kpk_metadata.get('legal_metadata', {})
        if legal_meta.get('penalty_references'):
            penalty_count = len(legal_meta['penalty_references'])
            key_findings.append(f"Contains {penalty_count} penalty references")
        
        summary['key_findings'] = key_findings
        
        # Determine processing implications
        implications = []
        
        if kpk_metadata.get('is_kpk_jurisdiction', False):
            implications.append("Apply KPK-specific processing rules")
        
        if geo_meta.get('geographic_scope') == 'divisional':
            implications.append("Map to specific forest division in graph")
        
        if species_meta.get('detected_species'):
            implications.append("Extract species for legal status analysis")
        
        summary['processing_implications'] = implications
        
        # Determine confidence level
        confidence_factors = []
        
        if kpk_metadata.get('kpk_identification_confidence', 0) > 0.8:
            confidence_factors.append(1.0)
        elif kpk_metadata.get('kpk_identification_confidence', 0) > 0.6:
            confidence_factors.append(0.7)
        else:
            confidence_factors.append(0.3)
        
        if completeness > 0.8:
            confidence_factors.append(0.9)
        elif completeness > 0.6:
            confidence_factors.append(0.7)
        elif completeness > 0.4:
            confidence_factors.append(0.5)
        else:
            confidence_factors.append(0.3)
        
        avg_confidence = sum(confidence_factors) / len(confidence_factors) if confidence_factors else 0.0
        
        if avg_confidence > 0.8:
            summary['confidence_level'] = 'high'
        elif avg_confidence > 0.6:
            summary['confidence_level'] = 'medium'
        else:
            summary['confidence_level'] = 'low'
        
        summary['confidence_score'] = avg_confidence
        
        kpk_metadata['metadata_summary'] = summary
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get enrichment statistics"""
        stats = self.stats.copy()
        
        # Calculate averages
        if stats['documents_enriched'] > 0:
            stats['average_enrichment_time'] = stats['enrichment_time_total'] / stats['documents_enriched']
            stats['average_metadata_fields'] = stats['metadata_fields_added'] / stats['documents_enriched']
        else:
            stats['average_enrichment_time'] = 0.0
            stats['average_metadata_fields'] = 0.0
        
        # Unique divisions and species
        stats['unique_divisions_identified'] = list(set(stats['divisions_identified']))
        stats['unique_species_detected'] = list(set(stats['species_detected']))
        
        # KPK document percentage
        if stats['documents_enriched'] > 0:
            stats['kpk_document_percentage'] = (stats['kpk_documents_identified'] / stats['documents_enriched']) * 100
        else:
            stats['kpk_document_percentage'] = 0.0
        
        return stats
    
    def batch_enrich_profiles(self, profiles: Dict[str, Dict], 
                             progress_callback = None) -> Dict[str, Dict]:
        """
        Enrich a batch of document profiles.
        
        Args:
            profiles: Dictionary of {document_path: profile}
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dictionary of enriched profiles
        """
        enriched_profiles = {}
        total_profiles = len(profiles)
        
        for i, (doc_path, profile) in enumerate(profiles.items()):
            try:
                # Extract text from profile if available
                extracted_text = None
                if 'extracted_text' in profile:
                    extracted_text = profile['extracted_text']
                elif 'normalized_text' in profile:
                    extracted_text = profile['normalized_text']
                
                # Enrich profile
                enriched_profile = self.enrich_profile(profile, extracted_text)
                enriched_profiles[doc_path] = enriched_profile
                
                if progress_callback:
                    progress = (i + 1) / total_profiles * 100
                    progress_callback(progress, doc_path, enriched_profile)
                    
            except Exception as e:
                self.logger.error(f"Failed to enrich profile for {doc_path}: {e}")
                # Keep original profile with error marker
                profile['kpk_enrichment_error'] = str(e)
                enriched_profiles[doc_path] = profile
        
        return enriched_profiles


# ============================================================================
# INTEGRATION FUNCTIONS
# ============================================================================

def enrich_document_profile(profile: Dict, text: Optional[str] = None) -> Dict:
    """
    Convenience function for enriching a single document profile.
    
    Args:
        profile: Document profile from doc_profiler.py
        text: Optional extracted text for analysis
        
    Returns:
        Enriched document profile
    """
    enricher = KPKMetadataEnricher()
    return enricher.enrich_profile(profile, text)


def quick_kpk_metadata(profile: Dict, text: Optional[str] = None) -> Dict[str, Any]:
    """
    Quick KPK metadata extraction for simple analysis.
    
    Returns:
        Simplified KPK metadata summary
    """
    enricher = KPKMetadataEnricher(enable_logging=False)
    enriched = enricher.enrich_profile(profile.copy(), text)
    
    kpk_metadata = enriched.get('kpk_metadata', {})
    
    return {
        'is_kpk_jurisdiction': kpk_metadata.get('is_kpk_jurisdiction', False),
        'kpk_confidence': kpk_metadata.get('kpk_identification_confidence', 0.0),
        'divisions': kpk_metadata.get('geographic_metadata', {}).get('identified_divisions', []),
        'species_count': len(kpk_metadata.get('species_metadata', {}).get('detected_species', [])),
        'penalty_references': len(kpk_metadata.get('legal_metadata', {}).get('penalty_references', [])),
        'document_era': kpk_metadata.get('temporal_metadata', {}).get('document_era', 'unknown'),
        'metadata_completeness': kpk_metadata.get('metadata_summary', {}).get('metadata_completeness', 0.0),
        'processing_implications': kpk_metadata.get('metadata_summary', {}).get('processing_implications', []),
    }


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("KPK METADATA ENRICHER - Phase 0.2")
    print("=" * 80)
    
    # Create enricher
    enricher = KPKMetadataEnricher()
    
    # Example 1: KPK Forest Ordinance
    print("\n1. EXAMPLE: KPK Forest Ordinance Document")
    
    example_profile = {
        'filename': 'KPK_Forest_Ordinance_2002.pdf',
        'document_type': 'ORDINANCE',
        'is_kpk': True,
        'document_number': 'Ord. VII of 2002',
        'creation_date': '2002-03-15',
        'amendment_count': 3,
    }
    
    example_text = """
    THE KHYBER PAKHTUNKHWA FOREST ORDINANCE, 2002
    
    Section 27: Penalties for unauthorized felling in reserved forests
    
    (1) Any person who fells any Deodar, Chilghoza Pine, or Fir tree 
    in a reserved forest without permission shall be punishable with 
    imprisonment which may extend to three years, or with fine which 
    may extend to one hundred thousand rupees, or with both.
    
    (2) For Chir Pine or Blue Pine, the fine shall not exceed fifty 
    thousand rupees.
    
    (3) This section applies to all forests in the Abbottabad and 
    Swat Forest Divisions.
    
    Issued by: Chief Conservator of Forests, KPK
    Dated: 15th March, 2002
    
    Circular No. 45/2002 for implementation.
    """
    
    enriched_profile = enricher.enrich_profile(example_profile, example_text)
    
    kpk_meta = enriched_profile.get('kpk_metadata', {})
    
    print(f"  KPK Jurisdiction: {kpk_meta.get('is_kpk_jurisdiction', False)}")
    print(f"  Confidence: {kpk_meta.get('kpk_identification_confidence', 0):.2f}")
    
    # Geographic metadata
    geo_meta = kpk_meta.get('geographic_metadata', {})
    print(f"  Divisions: {', '.join(geo_meta.get('identified_divisions', []))}")
    print(f"  Scope: {geo_meta.get('geographic_scope', 'unknown')}")
    
    # Species metadata
    species_meta = kpk_meta.get('species_metadata', {})
    print(f"  Species detected: {len(species_meta.get('detected_species', []))}")
    print(f"  Protected species: {species_meta.get('species_by_status', {}).get('fully_protected', [])}")
    
    # Legal metadata
    legal_meta = kpk_meta.get('legal_metadata', {})
    print(f"  Penalty references: {len(legal_meta.get('penalty_references', []))}")
    
    # Summary
    summary = kpk_meta.get('metadata_summary', {})
    print(f"  Metadata completeness: {summary.get('metadata_completeness', 0):.2f}")
    print(f"  Confidence level: {summary.get('confidence_level', 'unknown')}")
    print(f"  Processing implications: {summary.get('processing_implications', [])}")
    
    # Example 2: Quick metadata extraction
    print("\n2. QUICK METADATA EXTRACTION:")
    
    quick_meta = quick_kpk_metadata(example_profile, example_text)
    for key, value in quick_meta.items():
        if isinstance(value, list):
            print(f"  {key}: {', '.join(map(str, value[:3]))}{'...' if len(value) > 3 else ''}")
        else:
            print(f"  {key}: {value}")
    
    # Show statistics
    print("\n3. ENRICHER STATISTICS:")
    stats = enricher.get_statistics()
    print(f"  Documents enriched: {stats['documents_enriched']}")
    print(f"  KPK documents: {stats['kpk_documents_identified']} ({stats['kpk_document_percentage']:.1f}%)")
    print(f"  Average enrichment time: {stats['average_enrichment_time']:.3f}s")
    print(f"  Average metadata fields: {stats['average_metadata_fields']:.1f}")
    print(f"  Unique divisions: {len(stats['unique_divisions_identified'])}")
    print(f"  Unique species: {len(stats['unique_species_detected'])}")
    
    print("\n" + "=" * 80)
    print("KPK METADATA ENRICHER READY FOR INTEGRATION")
    print("=" * 80)
