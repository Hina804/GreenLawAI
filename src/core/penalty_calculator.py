from loguru import logger

class PenaltyCalculator:
    """
    SINGLE SOURCE OF TRUTH for all legal penalties and multipliers.
    """
    
    BASE_PENALTIES = {
        'deodar': 206000,
        'cedrus_deodara': 206000,
        'diyar': 206000,
        'chir': 98000,
        'blue_pine': 98000,
        'pinus_wallichiana': 98000,
        'spruce': 78000,
        'fir': 78000,
        'abies_pindrow': 78000,
        'walnut': 55000,
        'juglans_regia': 55000,
        'shisham': 45000,
        'dalbergia_sissoo': 45000,
        'grazing_reserved': 25000,
        'grazing_protected': 10000,
        'grazing_general': 5000
    }

    # Map each penalty to its source act and section
    PENALTY_SOURCES = {
        'deodar': {'act': 'KPK Forest Amendment Act 2022', 'section': 'Schedule-III'},
        'cedrus_deodara': {'act': 'KPK Forest Amendment Act 2022', 'section': 'Schedule-III'},
        'diyar': {'act': 'KPK Forest Amendment Act 2022', 'section': 'Schedule-III'},
        'chir': {'act': 'KPK Forest Amendment Act 2022', 'section': 'Schedule-III'},
        'blue_pine': {'act': 'KPK Forest Amendment Act 2022', 'section': 'Schedule-III'},
        'pinus_wallichiana': {'act': 'KPK Forest Amendment Act 2022', 'section': 'Schedule-III'},
        'spruce': {'act': 'KPK Forest Amendment Act 2022', 'section': 'Schedule-III'},
        'fir': {'act': 'KPK Forest Amendment Act 2022', 'section': 'Schedule-III'},
        'abies_pindrow': {'act': 'KPK Forest Amendment Act 2022', 'section': 'Schedule-III'},
        'walnut': {'act': 'KPK Forest Amendment Act 2022', 'section': 'Schedule-III'},
        'juglans_regia': {'act': 'KPK Forest Amendment Act 2022', 'section': 'Schedule-III'},
        'shisham': {'act': 'KPK Forest Amendment Act 2022', 'section': 'Schedule-III'},
        'dalbergia_sissoo': {'act': 'KPK Forest Amendment Act 2022', 'section': 'Schedule-III'},
        'grazing_reserved': {'act': 'Forest Act 1927', 'section': 'Section 26'},
        'grazing_protected': {'act': 'Forest Act 1927', 'section': 'Section 33'},
        'grazing_general': {'act': 'KPK Forest Ordinance 2002', 'section': 'Section 26/33'}
    }

    # Forest Act 1927 historical baseline (before 2022 Amendment)
    HISTORICAL_1927_PENALTIES = {
        'deodar': 500,
        'chir': 200,
        'spruce': 150,
        'fir': 150,
        'general': 100,
        'note': 'Plus possible imprisonment up to 6 months'
    }
    
    HISTORICAL_SOURCES = {
        'deodar': {'act': 'Forest Act 1927', 'section': 'Section 26'},
        'chir': {'act': 'Forest Act 1927', 'section': 'Section 26'},
        'spruce': {'act': 'Forest Act 1927', 'section': 'Section 26'},
        'fir': {'act': 'Forest Act 1927', 'section': 'Section 26'}
    }
    
    @classmethod
    def calculate(cls, species_name: str, conditions: list = None) -> dict:
        """
        Calculate final penalty based on species and conditions.
        """
        # Normalize species name
        s_key = species_name.lower().replace(' ', '_').strip()
        base = cls.BASE_PENALTIES.get(s_key, 0)
        
        # Get source act and section for this penalty
        source_info = cls.PENALTY_SOURCES.get(s_key, {'act': 'KPK Forest Amendment Act 2022', 'section': 'Schedule-III'})
        
        # If species not found, try partial match
        if base == 0:
            for k, v in cls.BASE_PENALTIES.items():
                if k in s_key or s_key in k:
                    base = v
                    s_key = k
                    source_info = cls.PENALTY_SOURCES.get(k, {'act': 'KPK Forest Amendment Act 2022', 'section': 'Schedule-III'})
                    break
        
        multiplier = 1.0
        applied_rules = []
        
        if not conditions:
            conditions = []
            
        # Convert conditions to lower strings for matching
        cond_str = " ".join([str(c).lower() for c in conditions])
        
        # Extract tree count
        import re
        tree_count = 1
        for c in conditions:
            m = re.search(r'(\d+)\s*trees?', str(c))
            if m:
                tree_count = int(m.group(1))

        # Rule 1: Night Offense (Section 73) - 2.0x
        if 'night' in cond_str:
            multiplier *= 2.0
            applied_rules.append("Section 73 (Night Multiplier)")
            source_info = {'act': 'Forest Act 1927', 'section': 'Section 73'}  # Night multiplier source
            
        # Rule 2: Repeat Offender (Section 74) - 2.0x
        if any(w in cond_str for w in ['repeat', 'previous', 'conviction', 'second']):
            multiplier *= 2.0
            applied_rules.append("Section 74 (Repeat Offender)")
            
        # Rule 3: Protected/Reserved Forest
        if 'protected' in cond_str:
            multiplier *= 10.0
            applied_rules.append("Section 3 (Protected Area 10x)")
        elif 'reserved' in cond_str:
            multiplier *= 1.0 # Base penalty is same as reserved
            applied_rules.append("Reserved Area")

        final = base * multiplier * tree_count
        
        if tree_count > 1:
            applied_rules.append(f"{tree_count} Trees Counted")

        return {
            "species": s_key.replace('_', ' ').title(),
            "base_penalty": base,
            "tree_count": tree_count,
            "multiplier": multiplier,
            "final_penalty": final,
            "rules_applied": applied_rules,
            "source_act": source_info.get('act', 'KPK Forest Amendment Act 2022'),
            "source_section": source_info.get('section', 'Schedule-III')
        }

    @classmethod
    def format_for_ui(cls, calculation: dict) -> str:
        """Helper to format calculation for display"""
        # Handle grazing violations
        if calculation.get('is_grazing'):
            return f"Rs. {calculation['final_penalty']:,} ({', '.join(calculation['rules_applied'])})"
        
        # Handle historical comparisons
        if calculation.get('is_comparison'):
            return (f"2022 Amendment: Rs. {calculation['base_penalty']:,} | "
                    f"Forest Act 1927: Rs. {calculation['historical_penalty']:,} | "
                    f"Increase: {calculation['increase_factor']}")
        
        # Standard penalty display
        if calculation['multiplier'] > 1.0:
            return f"Rs. {calculation['final_penalty']:,.0f} (Base: Rs. {calculation['base_penalty']:,} x {calculation['multiplier']:.1f})"
        return f"Rs. {calculation['final_penalty']:,.0f}"

    @classmethod
    def analyze_query(cls, query: str, species_override: str = None) -> dict:
        """Extracts species and conditions from query and returns calculation"""
        q = query.lower()
        
        # === GRAZING DETECTION ===
        if any(kw in q for kw in ['grazing', 'cattle', 'livestock', 'graze', 'cows', 'buffaloes', 'camels']):
            # Check if user wants BOTH Reserved vs Protected comparison
            has_both = ('reserved' in q and 'protected' in q) or 'vs' in q or 'compare' in q
            
            if has_both:
                return {
                    'species': 'Grazing Violation (Comparison)',
                    'base_penalty': cls.BASE_PENALTIES['grazing_reserved'],
                    'protected_penalty': cls.BASE_PENALTIES['grazing_protected'],
                    'multiplier': 1.0,
                    'final_penalty': cls.BASE_PENALTIES['grazing_reserved'],
                    'rules_applied': [
                        f"Reserved Forest (Section 26): Rs. {cls.BASE_PENALTIES['grazing_reserved']:,}",
                        f"Protected Forest (Section 33): Rs. {cls.BASE_PENALTIES['grazing_protected']:,}"
                    ],
                    'is_grazing': True,
                    'source_act': 'Forest Act 1927',
                    'source_section': 'Section 26 / Section 33'
                }
            elif 'reserved' in q:
                base = cls.BASE_PENALTIES['grazing_reserved']
                section = 'Section 26 (Reserved Forest)'
                source_act = 'Forest Act 1927'
                source_section = 'Section 26'
            elif 'protected' in q:
                base = cls.BASE_PENALTIES['grazing_protected']
                section = 'Section 33 (Protected Forest)'
                source_act = 'Forest Act 1927'
                source_section = 'Section 33'
            else:
                base = cls.BASE_PENALTIES['grazing_general']
                section = 'Section 26/33'
                source_act = 'KPK Forest Ordinance 2002'
                source_section = 'Section 26/33'
            return {
                'species': 'Grazing Violation',
                'base_penalty': base,
                'multiplier': 1.0,
                'final_penalty': base,
                'rules_applied': [section],
                'is_grazing': True,
                'source_act': source_act,
                'source_section': source_section
            }
        
        # === HISTORICAL COMPARISON DETECTION ===
        if any(kw in q for kw in ['1927', 'compare', 'historical', 'old penalty', 'original act', 'before amendment']):
            found_species = species_override or 'deodar'
            for species in cls.BASE_PENALTIES.keys():
                if species.replace('_', ' ') in q and not species.startswith('grazing'):
                    found_species = species
                    break
            current = cls.BASE_PENALTIES.get(found_species, 206000)
            historical = cls.HISTORICAL_1927_PENALTIES.get(found_species, 100)
            increase = round(current / historical) if historical > 0 else 0
            hist_source = cls.HISTORICAL_SOURCES.get(found_species, {'act': 'Forest Act 1927', 'section': 'Section 26'})
            return {
                'species': found_species.replace('_', ' ').title(),
                'base_penalty': current,
                'historical_penalty': historical,
                'multiplier': 1.0,
                'final_penalty': current,
                'increase_factor': f'{increase}x',
                'rules_applied': [f'Forest Act 1927: Rs. {historical:,}', f'2022 Amendment: Rs. {current:,}', f'Increase: {increase}x'],
                'is_comparison': True,
                'source_act': 'KPK Forest Amendment Act 2022',
                'source_section': 'Schedule-III',
                'historical_source_act': hist_source.get('act', 'Forest Act 1927'),
                'historical_source_section': hist_source.get('section', 'Section 26')
            }
        
        # === STANDARD SPECIES DETECTION ===
        found_species = species_override or "Unknown"
        source_info = {'act': 'KPK Forest Amendment Act 2022', 'section': 'Schedule-III'}
        
        if not species_override:
            for species in cls.BASE_PENALTIES.keys():
                if not species.startswith('grazing') and species.replace('_', ' ') in q:
                    found_species = species
                    source_info = cls.PENALTY_SOURCES.get(species, {'act': 'KPK Forest Amendment Act 2022', 'section': 'Schedule-III'})
                    break
            
            # Location-based default for Abbottabad/Hazara/Murree
            if found_species == "Unknown":
                if any(loc in q for loc in ["abbottabad", "hazara", "murree", "galiyat"]):
                    found_species = "deodar"
                    source_info = cls.PENALTY_SOURCES.get('deodar', {'act': 'KPK Forest Amendment Act 2022', 'section': 'Schedule-III'})
                    logger.info(f"[PenaltyCalculator] Location-based default triggered: {found_species}")
        
        conditions = []
        import re
        if 'night' in q: conditions.append('night')
        if any(w in q for w in ['repeat', 'previous', 'again', 'second']): conditions.append('repeat')
        if 'protected' in q: conditions.append('protected')
        if 'reserved' in q: conditions.append('reserved')
        
        # Extract tree count
        m = re.search(r'(\d+)\s*trees?', q)
        if m: conditions.append(f"{m.group(1)} trees")
        
        result = cls.calculate(found_species, conditions)
        # Ensure source info is included
        result['source_act'] = source_info.get('act', 'KPK Forest Amendment Act 2022')
        result['source_section'] = source_info.get('section', 'Schedule-III')
        return result