# src/data/permit_schema.py

PERMIT_REQUEST_SCHEMA = {
    "request_id": "REQ-2026-0001",
    "timestamp": "2026-04-16T10:00:00",
    "applicant": {
        "name": "Muhammad Khan",
        "cnic": "12345-6789012-3",
        "father_name": "Sher Khan",
        "address": "Village Kalam, District Swat",
        "contact": "0300-1234567",
        "land_ownership_proof": "file_hash"
    },
    "location": {
        "district": "Swat",
        "tehsil": "Kalam",
        "village": "Madyan",
        "khasra_number": "123/456",
        "coordinates": {"lat": 35.22, "lon": 72.48},
        "forest_type": "reserved"  # reserved, protected, guzara
    },
    "request": {
        "permit_type": "timber_extraction",  # timber, firewood, grazing, transit
        "tree_species": ["Deodar"],
        "number_of_trees": 5,
        "girth_sizes_cm": [120, 150, 100, 130, 110],
        "volume_cubic_ft": 250,
        "purpose": "house_construction",
        "duration_days": 30,
        "justification": "Building new house for family of 8"
    },
    "supporting_documents": {
        "land_ownership": "file_hash_1",
        "map_sketch": "file_hash_2",
        "previous_permits": []
    },
    "declaration": {
        "no_previous_violations": True,
        "no_disputed_land": True,
        "signature": "digital_signature_hash"
    }
}
