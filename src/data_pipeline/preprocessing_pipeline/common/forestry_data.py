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

# KPK Forest Officer Hierarchy
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
}

# KPK Legal Document Types
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
}

# KPK Tree Species Legal Status
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

# Penalty structures in KPK
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
# Legal Section Patterns for KPK
LEGAL_SECTION_PATTERNS = [
    r'^(\d+)\.',                         # 1.
    r'^(\d+)\s+',                        # 1 Section
    r'^Section\s+(\d+)',                 # Section 5
    r'^(\d+)\(([^)]+)\)',               # 5(2)
    r'^(\d+)-([A-Z])',                   # 32-A
    r'^\(([^)]+)\)',                     # (a) or (1)
]
