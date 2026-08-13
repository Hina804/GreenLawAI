"""
Test ALL query types in your system — Species data (Hazara tree master + price list)
Prints retrieved chunks + full generated IRAC answers for every query.
Also saves a clean report to: E:/GL_AI/test_legal_report.txt
"""
import asyncio
import sys
import logging
import datetime

# ── 1. Force UTF-8 so emoji render on Windows terminals ──────────────────────
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── 2. Silence noisy DEBUG/INFO retrieval logs ────────────────────────────────
logging.basicConfig(level=logging.WARNING)
for noisy in ("retrieval", "loguru", "pipeline", "agents", "faiss", "sentence_transformers",
              "transformers", "tensorflow", "torch", "neo4j", "httpx", "httpcore"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

import loguru
loguru.logger.remove()          # remove default loguru sink
loguru.logger.add(sys.stderr, level="WARNING")  # only WARNING+ to stderr

sys.path.insert(0, "E:/GL_AI/src")

from retrieval.graph_rag_retriever import GraphRAGRetriever
from agents.law_agent import LawAgent
from core.schemas import AudienceType

# ── 3. Tee output to a report file ───────────────────────────────────────────
REPORT_PATH = "E:/GL_AI/test_legal_report.txt"

class Tee:
    """Writes to both terminal and a file simultaneously."""
    def __init__(self, *streams):
        self.streams = streams
    def write(self, data):
        for s in self.streams:
            try: s.write(data)
            except Exception: pass
    def flush(self):
        for s in self.streams:
            try: s.flush()
            except Exception: pass

_report_file = open(REPORT_PATH, "w", encoding="utf-8")
sys.stdout = Tee(sys.stdout, _report_file)

TEST_QUERIES = [
    # ── PENALTIES ──────────────────────────────────────────────────────────────
    ("Penalty Deodar", "What is the penalty for cutting Deodar?"),
    ("Penalty Chir Pine", "What is the penalty for cutting Chir Pine?"),
    ("Penalty Schedule-I", "Which species are listed under Schedule-I and what are their penalties?"),

    # ── BASIC ATTRIBUTE LOOKUP ───────────────────────────────────────────────
    ("Legal Schedule Diyar", "What is the legal schedule and conservation status of Diyar?"),
    ("Family Kail", "What plant family does Kail belong to?"),
    ("Flowering Season Fir", "What is the flowering season of Abies pindrow?"),
    ("Elevation Range Spruce", "At what elevation range does Picea smithiana grow?"),

    # ── CROSS-FILE JOIN (master + price list) ────────────────────────────────
    ("Price vs Penalty Deodar", "Compare the legal penalty and the market base rate for Deodar — which is higher and by how much?"),
    ("Reserved Forest Price Chir", "If I cut one Chir Pine in a reserved forest, what's the official compensation rate, and does that match the legal penalty for that species?"),

    # ── CALCULATIONS ──────────────────────────────────────────────────────────
    ("Calc Protected Walnut", "What would the cost be to cut 3 Walnut trees in a protected area, using the protected-area multiplier?"),
    ("Calc Reserved Shisham", "Calculate the reserved-forest compensation rate for one Shisham tree."),

    # ── CONTRADICTION / NAMING TRAPS ─────────────────────────────────────────
    ("Contradiction Wallichiana Price", "What is the price for cutting a Pinus wallichiana tree?"),
    ("Contradiction Partal Species", "What species is Partal, and what is its penalty and price?"),

    # ── DATA QUALITY / INGESTION ROBUSTNESS ──────────────────────────────────
    ("Junk Row Tor-Ghar", "What species has a conservation status of 'Tor-Ghar'?"),
    ("Junk Row Coverage Line", "Tell me about the species named '* Coverage: Hazara Division including Abbottabad'."),
    ("Unknown Placeholder 1", "What is 'Unknown species placeholder 1' and what is its penalty?"),

    # ── OUT-OF-SCOPE / NEGATIVE ───────────────────────────────────────────────
    ("OOS Baobab", "What is the penalty for cutting a Baobab tree in Hazara?"),
    ("OOS Future Status", "What is the IUCN status of Cedrus deodara in 2030?"),
    ("OOS Price Mango", "What is the market price for cutting a Mango tree?"),

    # ── MULTI-HOP REASONING ───────────────────────────────────────────────────
    ("MultiHop Pinaceae Summer", "Which Pinaceae species fruit between June and August and grow above 1500m?"),
    ("MultiHop ScheduleI Wood Uses", "List all species with Schedule-I legal protection and their wood uses."),
    ("MultiHop HighValue Schedule", "Which high-value category species in the price list also have Schedule-I legal protection?"),
]

# ── Minimal stub config (LawAgent needs no LLM — it runs deterministic) ──────
_LAW_CONFIG = {}

async def test_all():
    retriever = GraphRAGRetriever()
    law_agent = LawAgent(config=_LAW_CONFIG, llm_manager=None)

    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("=" * 80)
    print(f"  GL_AI LEGAL TEST SUITE — {ts}")
    print("  Showing: retrieved chunks + full IRAC generated answers")
    print("=" * 80)

    results_summary = []

    for name, query in TEST_QUERIES:
        print(f"\n{'='*80}")
        print(f"[{name}]  {query}")
        print("=" * 80)

        try:
            chunks = await retriever.hybrid_search(query, k=3)

            if not chunks:
                print("❌ NO RESULTS")
                results_summary.append((name, "FAIL", "No results", False))
                continue

            # ── Retrieved chunks ──────────────────────────────────────────────
            first  = chunks[0]
            chunk_id  = first.get("chunk_id", "unknown")
            law_title = first.get("metadata", {}).get("law_title", "Unknown")
            section   = first.get("metadata", {}).get("section", "Unknown")
            source    = first.get("source", "UNKNOWN")
            score     = first.get("final_score", 0.0)

            is_manual = chunk_id.startswith("manual_")
            is_eko    = chunk_id.startswith("eko_")

            status = "✅ PASS"
            if is_manual:
                status = "🔵 MANUAL"
            elif is_eko:
                status = "🟢 EKO"
            elif score < 0.3:
                status = "⚠️ LOW"

            print(f"  [1] {status} | Source: {source} | Score: {score:.2f}")
            print(f"      Law: {law_title}")
            print(f"      Section: {section}")
            print(f"      Chunk: {chunk_id[:50]}...")
            print(f"      Text: {first.get('text', '')[:150]}...")

            # Show second chunk
            if len(chunks) > 1:
                second = chunks[1]
                print(f"  [2] Source: {second.get('source', 'UNKNOWN')} | Score: {second.get('final_score', 0):.2f}")
                print(f"      Law: {second.get('metadata', {}).get('law_title', 'Unknown')}")

            # ── Generated Answer (LawAgent deterministic IRAC) ────────────────
            print(f"\n  {'─'*70}")
            print(f"  📝 GENERATED ANSWER")
            print(f"  {'─'*70}")
            try:
                response = await law_agent.run(
                    query=query,
                    retrieved_chunks=chunks,
                    audience=AudienceType.DUAL,
                )

                if response.abstain:
                    print(f"  ⚠️  ABSTAINED — {response.simple_explanation}")
                else:
                    # Print full IRAC answer (wrap long lines for readability)
                    answer_text = response.legal_explanation or response.simple_explanation or "(no answer)"
                    # Indent each line for tidy terminal output
                    for line in answer_text.splitlines():
                        print(f"  {line}")

                    # Citations summary
                    if response.citations:
                        print(f"\n  📌 Citations ({len(response.citations)}):")
                        for c in response.citations[:3]:
                            sec_str = f" § {c.section}" if c.section else ""
                            print(f"      • {c.document}{sec_str}")

                    print(f"\n  🎯 Confidence: {response.confidence:.2f}")
                    if response.confidence < 0.6:
                        print("  ⚠️ DISCLAIMER: Low confidence answer. This result may be incomplete or lack authoritative statutory grounding.")

            except Exception as ae:
                print(f"  ❌ LawAgent ERROR: {ae}")

            # NOTE: correctness heuristics (penalty keyword check)
            correct = True
            if "penalty" in query.lower() or "fine" in query.lower():
                if "206000" not in first.get("text", "") and "98" not in first.get("text", ""):
                    correct = False

            results_summary.append((name, status, f"{law_title} - {section}", correct))

        except Exception as e:
            print(f"❌ ERROR: {e}")
            results_summary.append((name, "ERROR", str(e)[:50], False))

    # ── SUMMARY ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    passed = sum(1 for r in results_summary if r[3] == True)
    failed = sum(1 for r in results_summary if r[3] == False)
    total  = len(results_summary)

    print(f"\nTotal Queries: {total}")
    print(f"✅ Pass: {passed}")
    print(f"❌ Fail: {failed}")
    print(f"📊 Success Rate: {(passed/total)*100:.1f}%\n")

    print("Detailed Results:")
    for name, status, detail, correct in results_summary:
        icon = "✅" if correct else "❌"
        print(f"  {icon} {name:<30} {status:<15} {detail[:40]}")

if __name__ == "__main__":
    asyncio.run(test_all())
    _report_file.flush()
    _report_file.close()
    print(f"\n{'='*80}")
    print(f"📄 Full report saved to: {REPORT_PATH}")
    print(f"{'='*80}")