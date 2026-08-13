import json
import os
import random
from datetime import datetime, timedelta
from court_schema import CourtCase

# Mock Data Configurations
JUDGES = [
    "Justice Qazi Faez Isa", "Justice Syed Mansoor Ali Shah", "Justice Munib Akhtar",
    "Justice Yahya Afridi", "Justice Amin-ud-Din Khan", "Justice Ayesha A. Malik",
    "Justice Ishtiaq Ibrahim (PHC)", "Justice Rooh-ul-Amin Khan (PHC)"
]

LOCATIONS = [
    "Abbottabad", "Swat", "Mansehra", "Dir", "Chitral", 
    "Shangla", "Kaghan Valley", "Naran", "Kalam"
]

SECTIONS = [
    "Section 33, KP Forest Ordinance 2002",
    "Section 42, KP Forest Ordinance 2002",
    "Section 9, KP Wildlife Act 2015",
    "Section 11, Pakistan Environmental Protection Act 1997"
]

def generate_mock_cases(count: int = 20) -> list:
    """Generates a dataset of synthetic environmental court cases."""
    cases = []
    
    start_date = datetime(2020, 1, 1)
    
    for i in range(1, count + 1):
        # Random attributes
        is_sc = random.random() > 0.6
        court_lvl = "Supreme Court" if is_sc else "High Court"
        court_name = "Supreme Court of Pakistan" if is_sc else "Peshawar High Court"
        
        bench_size = 3 if is_sc else random.choice([1, 2])
        bench = random.sample(JUDGES, bench_size)
        
        case_date = start_date + timedelta(days=random.randint(0, 2100))
        year = case_date.year
        
        is_night = random.random() > 0.5
        is_protected = random.random() > 0.3
        repeat = random.random() > 0.8
        
        trees = random.randint(1, 50)
        loc = random.choice(LOCATIONS)
        
        # Diverse offense categories
        offense_type = random.choice([
            "Illegal Logging", "Illegal Logging", "Illegal Logging",  # Weighted higher
            "Forest Fire", "Forest Fire",
            "Encroachment",
            "Poaching",
            "Illegal Grazing"
        ])
        
        if offense_type == "Illegal Logging":
            offense_desc = f"Unlawful cutting of {trees} trees in {loc} {'at night' if is_night else 'during the day'}."
        elif offense_type == "Forest Fire":
            offense_desc = f"Setting fire to forest area in {loc} {'during dry season' if random.random() > 0.5 else 'near residential zone'}. Approximately {random.randint(2, 20)} hectares affected."
            trees = 0
        elif offense_type == "Encroachment":
            offense_desc = f"Unauthorized construction and land clearing on {random.randint(1, 10)} kanals of reserved forest land in {loc}."
            trees = random.randint(0, 15)
        elif offense_type == "Poaching":
            species = random.choice(["Markhor", "Snow Leopard", "Himalayan Black Bear", "Musk Deer", "Common Leopard"])
            offense_desc = f"Illegal hunting of protected species ({species}) in {loc} wildlife sanctuary."
            trees = 0
        else:  # Illegal Grazing
            offense_desc = f"Unauthorized grazing of {random.randint(10, 100)} livestock in protected forest zone of {loc}."
            trees = 0
        
        # Sentencing logic (night/protected/repeat yields higher penalties)
        is_guilty = random.random() > 0.25
        verdict = random.choice(["Guilty", "Convicted"]) if is_guilty else random.choice(["Acquitted", "Not Guilty", "Dismissed"])
        
        penalty_type = "None"
        amount = 0
        months = 0
        
        if is_guilty:
            # Base fine by offense type
            base_fines = {
                "Illegal Logging": trees * 25000,
                "Forest Fire": random.randint(100000, 500000),
                "Encroachment": random.randint(50000, 300000),
                "Poaching": random.randint(200000, 1000000),
                "Illegal Grazing": random.randint(10000, 50000)
            }
            amount = base_fines.get(offense_type, 50000)
            
            if is_night: amount = int(amount * 1.5)
            if is_protected: amount = int(amount * 2.0)
            if repeat: amount = int(amount * 3.0)
            
            # Imprisonment based on severity
            if repeat or offense_type in ["Poaching", "Forest Fire"]:
                months = random.randint(3, 24)
            elif is_protected and is_night:
                months = random.randint(1, 12)
            elif random.random() > 0.6:
                months = random.randint(1, 6)
                
            penalty_type = "Fine" if months == 0 else "Fine + Imprisonment"
            amount = int(amount)
        
        # Precedents
        precedents = []
        if cases and random.random() > 0.5:
            precedents.append(random.choice(cases).citation)

        case = CourtCase(
            case_id=f"{'SC' if is_sc else 'PHC'}-{year}-{i:03d}",
            title=f"State vs. Accused_{i}",
            court_level=court_lvl,
            court_name=court_name,
            bench=bench,
            judgment_date=case_date.strftime("%Y-%m-%d"),
            citation=f"{year} {'SCMR' if is_sc else 'PLD'} {random.randint(10, 999)}",
            law_sections=random.sample(SECTIONS, random.randint(1, 2)),
            offense_category=offense_type,
            offense_details=offense_desc,
            location=loc,
            is_night_violation=is_night,
            is_protected_forest=is_protected,
            trees_cut=trees,
            verdict=verdict,
            penalty_type=penalty_type,
            penalty_amount_rs=amount,
            imprisonment_months=months,
            repeat_offender=repeat,
            prior_convictions=random.randint(1, 3) if repeat else 0,
            precedents_cited=precedents,
            judgment_summary=f"The court found the accused {verdict.lower()} regarding the {offense_desc.lower()}",
            full_text=f"This is a synthesized full judgment text for {year}...",
            keywords=[offense_type.lower().replace(" ", "_"), loc.lower()] + (["night"] if is_night else [])
        )
        
        cases.append(case)
        
    return cases

if __name__ == "__main__":
    cases = generate_mock_cases(20)
    
    # Save to processed dir
    output_dir = os.path.join(os.path.dirname(__file__), "court_cases", "processed")
    os.makedirs(output_dir, exist_ok=True)
    
    out_file = os.path.join(output_dir, "mock_cases.json")
    
    with open(out_file, "w") as f:
        json.dump([c.model_dump() for c in cases], f, indent=2)
        
    print(f"Generated {len(cases)} mock cases and saved to {out_file}")
    
    # Print the first one for validation
    print("\nSample Case:")
    print(json.dumps(cases[0].model_dump(), indent=2))
