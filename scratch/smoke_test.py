"""
smoke_test.py — Fast verification of all 4 fixes without loading Neo4j / TF.
Reads metadata.pkl directly and checks:
  1. graph_score safe-get (structural check of retriever code)
  2. category filter fallback — Forest Act 1927 chunks are legal_statute
  3. Hazara / uncategorized law_title fallback logic (simulate vector_search filter)
  4. Manual patch chunks have section_type='definition' and doc_cat='legal_statute'
"""
import sys
import pickle
import re

sys.path.insert(0, "E:/GL_AI/src")

METADATA_PATH = r"E:\GL_AI\data_processed\faiss_index_unified\metadata.pkl"

print("Loading metadata.pkl...")
with open(METADATA_PATH, "rb") as f:
    metadata = pickle.load(f)
print(f"Loaded {len(metadata)} chunks.\n")

LEGAL_CATEGORIES = {"legal_statute", "legal_rules", "case_law"}

# ── Helper: simulate vector_search category fallback ────────────────────────
def simulate_category_fallback(doc_cat, law_title):
    if doc_cat in ("uncategorized", None, "None", ""):
        known_legal_titles = {"Forest Act 1927", "Hazara Forest Act", "KPK Forest Ordinance"}
        if law_title in known_legal_titles:
            return "legal_statute"
        elif law_title and any(kw in law_title for kw in ["Act", "Ordinance", "Rules", "Regulation"]):
            return "legal_statute"
    return doc_cat

# ── Fix 1: Check graph_rag_retriever.py sorting line ────────────────────────
print("=" * 60)
print("FIX 1 — KeyError: graph_score (static code check)")
with open(r"E:\GL_AI\src\retrieval\graph_rag_retriever.py", encoding="utf-8") as f:
    code = f.read()

if 'x.get("graph_score", x.get("vector_score", 0.0))' in code:
    print("  [OK] graph_search sort uses safe .get() fallback")
else:
    print("  [FAIL] graph_search sort still uses direct key access")

if 'item.get("graph_score", item.get("vector_score", 0.0))' in code:
    print("  [OK] hybrid_search merge uses safe .get() fallback")
else:
    print("  [FAIL] hybrid_search merge still uses direct key access")

# ── Fix 2: Forest Act 1927 chunks — all should be legal_statute ──────────────
print("\n" + "=" * 60)
print("FIX 2 — Forest Act 1927 chunks categorized as legal_statute")
fa_chunks = [m for m in metadata if m.get("law_title") == "Forest Act 1927"]
fa_legal = [m for m in fa_chunks if m.get("document_category") in LEGAL_CATEGORIES]
print(f"  Forest Act 1927 chunks: {len(fa_chunks)}")
print(f"  Correctly categorized : {len(fa_legal)} / {len(fa_chunks)}")
if fa_chunks and len(fa_legal) == len(fa_chunks):
    print("  [OK] All Forest Act 1927 chunks are legal_statute/case_law")
else:
    bad = [m.get("document_category") for m in fa_chunks if m.get("document_category") not in LEGAL_CATEGORIES]
    print(f"  [FAIL] {len(bad)} chunks still wrong cat: {set(bad)}")

# ── Fix 3: Simulate vector_search category fallback on uncategorized chunks ──
print("\n" + "=" * 60)
print("FIX 3 — law_title fallback for uncategorized legal chunks")
unc = [m for m in metadata if m.get("document_category") in (None, "uncategorized")]
rescued = 0
for m in unc:
    lt = m.get("law_title", "")
    fixed_cat = simulate_category_fallback(m.get("document_category"), lt)
    if fixed_cat in LEGAL_CATEGORIES:
        rescued += 1
print(f"  Uncategorized/None chunks: {len(unc)}")
print(f"  Would be rescued by vector_search fallback: {rescued}")
# Show sample of still-problematic ones
still_unc = [m for m in unc if simulate_category_fallback(m.get("document_category"), m.get("law_title","")) not in LEGAL_CATEGORIES]
sample_titles = list({m.get("law_title","?") for m in still_unc})[:5]
if rescued > 0:
    print(f"  [OK] {rescued} chunks rescued in vector_search by law_title fallback")
print(f"  Remaining truly uncategorized (non-legal): {len(still_unc)}")
print(f"  Sample non-legal uncategorized titles: {sample_titles}")

# ── Fix 4: Manual patch chunks — section_type and document_category ──────────
print("\n" + "=" * 60)
print("FIX 4 — Manual patch chunks: section_type='definition', doc_cat='legal_statute'")
manual = [m for m in metadata if str(m.get("chunk_id","")).startswith("manual_")]
manual_def = [m for m in manual if m.get("section_type") == "definition"]
manual_legal = [m for m in manual if m.get("document_category") == "legal_statute"]
print(f"  Manual patch chunks total : {len(manual)}")
print(f"  With section_type='definition': {len(manual_def)} / {len(manual)}")
print(f"  With doc_cat='legal_statute'  : {len(manual_legal)} / {len(manual)}")
if manual and len(manual_def) == len(manual) and len(manual_legal) == len(manual):
    print("  [OK] All manual patch chunks correctly tagged")
else:
    print("  [FAIL] Some manual patch chunks still missing tags")
    for m in manual:
        if m.get("section_type") != "definition" or m.get("document_category") != "legal_statute":
            print(f"    chunk_id={m.get('chunk_id')} sec_type={m.get('section_type')} cat={m.get('document_category')}")

# ── Definition chunks tagged ─────────────────────────────────────────────────
print("\n" + "=" * 60)
print("FIX 4b — Definition tag presence across whole index")
def_chunks = [m for m in metadata if m.get("section_type") == "definition"]
print(f"  Chunks with section_type='definition': {len(def_chunks)}")
sample_def = [(m.get("law_title"), m.get("section"), m.get("chunk_id")) for m in def_chunks[:5]]
for title, sec, cid in sample_def:
    print(f"    {title} | {sec} | {cid}")

# ── Overall category distribution ────────────────────────────────────────────
print("\n" + "=" * 60)
print("OVERALL — Final category distribution in index")
cats = {}
for m in metadata:
    c = m.get("document_category", "MISSING")
    cats[c] = cats.get(c, 0) + 1
for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
    print(f"  {cat:<25} {count:>5}")

print("\n[DONE] Smoke test complete.")
