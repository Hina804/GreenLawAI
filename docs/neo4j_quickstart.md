# Neo4j Quick Start Guide

## 🚀 Quick Setup (3 Steps)

### Step 1: Install Neo4j

**Option A: Docker (Recommended)**
```bash
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest
```

**Option B: Neo4j Desktop**
- Download: https://neo4j.com/download/
- Create new database
- Set password to `password` (or update script)

### Step 2: Install Python Driver
```bash
pip install neo4j
```

### Step 3: Run Import
```bash
python scripts/setup_neo4j.py
```

---

## ✅ What This Does

1. **Checks Neo4j connection**
2. **Creates constraints** (uniqueness + indexes)
3. **Imports 38 entities** (batch: 500)
4. **Imports 103 chunks** (batch: 100)
5. **Creates relationships** (MENTIONS, CONTAINS_CLAUSE)
6. **Verifies import** (counts + sample query)

---

## 📊 Expected Results

```
✓ Entities: 38
✓ Chunks: 103
✓ Clauses: ~239
✓ MENTIONS relationships: ~733
```

---

## 🔍 Quick Queries

### Open Neo4j Browser
```
http://localhost:7474
```

### Top Entities
```cypher
MATCH (e:Entity)
RETURN e.canonical_name, e.frequency
ORDER BY e.frequency DESC
LIMIT 10
```

### Find Chunks
```cypher
MATCH (c:Chunk)
RETURN c.section, c.section_title, c.text
LIMIT 5
```

### Entity Relationships
```cypher
MATCH (c:Chunk)-[:MENTIONS]->(e:Entity)
RETURN e.canonical_name, count(c) as chunks
ORDER BY chunks DESC
LIMIT 10
```

---

## 🎯 Next: GraphRAG Queries

See `docs/neo4j_integration_guide.md` for 20+ advanced queries!
