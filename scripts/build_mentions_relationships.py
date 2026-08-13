"""
build_mentions_relationships.py  v2
────────────────────────────────────
Builds (Chunk)-[:MENTIONS]->(Entity) relationships via text-scan.

FIXES vs v1:
  - length() → size() for Neo4j 5.x string length checks
  - id() → elementId() deprecation warning suppressed  
  - Chunk fetch uses chunk_id string match instead of internal id()
  - Dry-run actually counts pairs correctly

USAGE:
    python build_mentions_relationships.py --dry-run
    python build_mentions_relationships.py
    python build_mentions_relationships.py --batch 500
"""

from __future__ import annotations

import argparse
import time
from typing import Dict, List, Optional, Set

from neo4j import GraphDatabase


BATCH_MERGE_CQL = """
UNWIND $pairs AS pair
MATCH (c:Chunk  {chunk_id:       pair.chunk_id})
MATCH (e:Entity {canonical_name: pair.canonical})
MERGE (c)-[:MENTIONS]->(e)
"""


class MentionsBuilder:

    def __init__(self, driver, dry_run: bool = False, batch_size: int = 300):
        self.driver   = driver
        self.dry_run  = dry_run
        self.batch_size = batch_size

    # ── Audit ─────────────────────────────────────────────────────────────────

    def audit(self) -> None:
        print("\n" + "═"*60)
        print("  AUDIT")
        print("═"*60)
        with self.driver.session() as s:
            chunks   = s.run("MATCH (c:Chunk)  RETURN count(c) AS n").single()["n"]
            entities = s.run("MATCH (e:Entity) RETURN count(e) AS n").single()["n"]
            mentions = s.run(
                "MATCH ()-[r:MENTIONS]->() RETURN count(r) AS n"
            ).single()["n"]
            sample   = s.run(
                "MATCH (c:Chunk) RETURN keys(c) AS k LIMIT 1"
            ).single()
        print(f"  Chunk nodes              : {chunks:,}")
        print(f"  Entity nodes             : {entities:,}")
        print(f"  MENTIONS relationships   : {mentions:,}")
        if sample:
            print(f"  Chunk properties         : {sample['k']}")

    # ── Load entities into memory ─────────────────────────────────────────────

    def _load_term_map(self) -> Dict[str, str]:
        """
        Returns {search_term_lowercase: canonical_name} for every entity.
        Includes canonical_name, underscore↔space variants, and all aliases.
        Only terms >= 4 chars to avoid false positives on short tokens.
        """
        print("\n  Loading entities from Neo4j...")
        with self.driver.session() as s:
            # FIX: use size() not length() for string length in Neo4j 5.x
            rows = s.run("""
                MATCH (e:Entity)
                WHERE size(e.canonical_name) >= 4
                RETURN e.canonical_name AS canonical,
                       coalesce(e.aliases, []) AS aliases
            """).data()

        print(f"  Loaded {len(rows):,} entities")

        term_map: Dict[str, str] = {}
        for row in rows:
            cn = row["canonical"]
            # canonical in both forms
            for variant in (cn, cn.replace("_", " "), cn.replace(" ", "_")):
                v = variant.lower().strip()
                if len(v) >= 4:
                    term_map[v] = cn
            # all aliases
            for alias in (row["aliases"] or []):
                a = alias.lower().strip()
                if len(a) >= 4:
                    term_map[a] = cn
                    term_map[a.replace(" ", "_")] = cn
                    term_map[a.replace("_", " ")] = cn

        print(f"  Built term map: {len(term_map):,} lookup terms")
        return term_map

    # ── Text-scan ─────────────────────────────────────────────────────────────

    def build_from_text_scan(self) -> None:
        print("\n" + "═"*60)
        print("  TEXT-SCAN")
        print(f"  Mode: {'DRY-RUN' if self.dry_run else 'LIVE'}")
        print("═"*60)

        term_map = self._load_term_map()
        if not term_map:
            print("  ERROR: No entities found in Neo4j. Aborting.")
            return

        # Sort terms longest-first so "reserved forest" matches before "forest"
        sorted_terms = sorted(term_map.keys(), key=len, reverse=True)

        skip          = 0
        total_chunks  = 0
        total_created = 0
        start         = time.time()

        while True:
            with self.driver.session() as s:
                rows = s.run("""
                    MATCH (c:Chunk)
                    WHERE c.text IS NOT NULL
                    RETURN c.chunk_id AS chunk_id, c.text AS text
                    SKIP $skip LIMIT $limit
                """, skip=skip, limit=self.batch_size).data()

            if not rows:
                break

            batch_pairs: List[Dict] = []

            for row in rows:
                text     = (row.get("text") or "").lower()
                chunk_id = row.get("chunk_id")
                if not text or not chunk_id:
                    continue

                matched: Set[str] = set()
                for term in sorted_terms:
                    if term in text:
                        canonical = term_map[term]
                        if canonical not in matched:
                            matched.add(canonical)
                            batch_pairs.append({
                                "chunk_id": chunk_id,
                                "canonical": canonical,
                            })

            if not self.dry_run and batch_pairs:
                with self.driver.session() as s:
                    s.run(BATCH_MERGE_CQL, pairs=batch_pairs)

            total_chunks  += len(rows)
            total_created += len(batch_pairs)

            elapsed = time.time() - start
            rate    = total_chunks / elapsed if elapsed > 0 else 0
            print(
                f"  Chunks: {total_chunks:>6,} | "
                f"Pairs: {total_created:>7,} | "
                f"{rate:.0f} chunks/s"
            )

            skip += self.batch_size
            if len(rows) < self.batch_size:
                break

        print(f"\n  ── SUMMARY {'(DRY-RUN)' if self.dry_run else ''} ──")
        print(f"  Chunks scanned   : {total_chunks:,}")
        print(f"  MENTIONS {'would create' if self.dry_run else 'created'}: {total_created:,}")
        print(f"  Elapsed          : {time.time()-start:.1f}s")

    # ── Verify ────────────────────────────────────────────────────────────────

    def verify(self) -> None:
        print("\n" + "═"*60)
        print("  VERIFICATION")
        print("═"*60)

        with self.driver.session() as s:
            total = s.run(
                "MATCH ()-[r:MENTIONS]->() RETURN count(r) AS n"
            ).single()["n"]

            chunks_linked = s.run("""
                MATCH (c:Chunk)-[:MENTIONS]->(:Entity)
                RETURN count(DISTINCT c) AS n
            """).single()["n"]

            top = s.run("""
                MATCH (c:Chunk)-[:MENTIONS]->(e:Entity)
                RETURN e.canonical_name AS entity, count(c) AS chunks
                ORDER BY chunks DESC LIMIT 10
            """).data()

        print(f"  Total MENTIONS         : {total:,}")
        print(f"  Chunks with ≥1 link    : {chunks_linked:,}")
        print(f"\n  Top entities:")
        for row in top:
            print(f"    {row['entity']:<40} {row['chunks']:>5} chunks")

        print(f"\n  Spot-check:")
        spot = ["deodar", "chir pine", "kpk", "reserved forest",
                "forest officer", "timber", "fine", "government"]
        with self.driver.session() as s:
            for name in spot:
                r = s.run("""
                    MATCH (e:Entity)
                    WHERE toLower(e.canonical_name) = toLower($name)
                       OR any(a IN e.aliases WHERE toLower(a) = toLower($name))
                    OPTIONAL MATCH (c:Chunk)-[:MENTIONS]->(e)
                    RETURN e.canonical_name AS cn, count(c) AS n
                    LIMIT 1
                """, name=name).single()
                if r:
                    icon = "✓" if r["n"] > 0 else "✗"
                    print(f"    {icon}  {name:<25} → '{r['cn']}'  ({r['n']} chunks)")
                else:
                    print(f"    ○  {name:<25} → not in graph")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri",      default="bolt://localhost:7687")
    parser.add_argument("--user",     default="neo4j")
    parser.add_argument("--password", default="password")
    parser.add_argument("--dry-run",  action="store_true")
    parser.add_argument("--batch",    type=int, default=300)
    args = parser.parse_args()

    driver  = GraphDatabase.driver(args.uri, auth=(args.user, args.password))
    builder = MentionsBuilder(driver, dry_run=args.dry_run, batch_size=args.batch)

    try:
        builder.audit()
        builder.build_from_text_scan()
        if not args.dry_run:
            builder.verify()
    finally:
        driver.close()


if __name__ == "__main__":
    main()