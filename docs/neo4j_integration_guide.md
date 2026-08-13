# Neo4j Integration Guide

## 📊 Export Summary

**Successfully Exported**:
- ✅ 38 unique entities
- ✅ 103 chunks
- ✅ 733 total entity mentions
- ✅ 239 clauses segmented
- ✅ 48.2% entity reduction achieved

**Files Created**:
- `entity_registry.json` - Entity data with provenance
- `chunks_export.json` - Chunk data with metadata

---

## 🚀 Quick Start

### Step 1: Start Neo4j

```bash
# Using Docker
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest

# Or use Neo4j Desktop
# Download from: https://neo4j.com/download/
```

### Step 2: Install Python Driver

```bash
pip install neo4j
```

### Step 3: Run Import

```python
from src.indexing.neo4j_import import import_to_neo4j

import_to_neo4j(
    neo4j_uri="bolt://localhost:7687",
    username="neo4j",
    password="password",
    entity_registry_path="entity_registry.json",
    chunks_export_path="chunks_export.json"
)
```

---

## 📝 Neo4j Query Examples

### 1. Entity Lookup

```cypher
// Find all entities of type "LEGAL_ACTOR"
MATCH (e:Entity {entity_type: "LEGAL_ACTOR"})
RETURN e.canonical_name, e.frequency, e.chunk_count
ORDER BY e.frequency DESC
LIMIT 10
```

### 2. Chunk Retrieval

```cypher
// Find chunks from a specific law
MATCH (c:Chunk {law_title: "Forest Act 1927"})
RETURN c.chunk_id, c.section, c.section_title, c.text
LIMIT 5
```

### 3. Entity-Chunk Relationships

```cypher
// Find all chunks mentioning "forest officer"
MATCH (c:Chunk)-[:MENTIONS]->(e:Entity {canonical_name: "forest_officer"})
RETURN c.section, c.section_title, c.text
LIMIT 10
```

### 4. Clause-Level Retrieval

```cypher
// Find specific clauses
MATCH (c:Chunk)-[:CONTAINS_CLAUSE]->(cl:Clause)
WHERE cl.clause_marker = "(1)"
RETURN c.section_title, cl.text
LIMIT 5
```

### 5. GraphRAG: Multi-Hop Reasoning

```cypher
// Find entities co-occurring with "forest officer"
MATCH (c:Chunk)-[:MENTIONS]->(e1:Entity {canonical_name: "forest_officer"})
MATCH (c)-[:MENTIONS]->(e2:Entity)
WHERE e1 <> e2
RETURN e2.canonical_name, e2.entity_type, count(c) as co_occurrences
ORDER BY co_occurrences DESC
LIMIT 10
```

### 6. Entity Provenance

```cypher
// Get entity provenance
MATCH (e:Entity {canonical_name: "forest_officer"})
RETURN e.canonical_name,
       e.frequency,
       e.first_seen_doc,
       e.last_seen_doc,
       e.aliases
```

### 7. Section-Level Analysis

```cypher
// Find all entities in a specific section
MATCH (c:Chunk {section: "1"})-[:MENTIONS]->(e:Entity)
RETURN c.section_title, collect(DISTINCT e.canonical_name) as entities
```

### 8. Clause Hierarchy

```cypher
// Get clause hierarchy for a chunk
MATCH (c:Chunk {chunk_id: "your_chunk_id"})-[:CONTAINS_CLAUSE]->(cl:Clause)
RETURN cl.clause_marker, cl.text, cl.start_offset, cl.end_offset
ORDER BY cl.start_offset
```

---

## 🔍 Advanced Queries

### Entity Network Analysis

```cypher
// Build entity co-occurrence network
MATCH (c:Chunk)-[:MENTIONS]->(e1:Entity)
MATCH (c)-[:MENTIONS]->(e2:Entity)
WHERE e1 < e2
WITH e1, e2, count(c) as weight
WHERE weight > 2
RETURN e1.canonical_name, e2.canonical_name, weight
ORDER BY weight DESC
LIMIT 20
```

### Legal Concept Extraction

```cypher
// Find all legal concepts (entities in quotes)
MATCH (e:Entity {entity_type: "DEFINED_TERM"})
RETURN e.canonical_name, e.frequency
ORDER BY e.frequency DESC
```

### Cross-Reference Analysis

```cypher
// Find sections that reference other sections
MATCH (c:Chunk)-[:MENTIONS]->(e:Entity {entity_type: "LEGAL_REF"})
RETURN c.section, c.section_title, collect(e.canonical_name) as references
```

---

## 📊 Graph Statistics

### Get Overview

```cypher
// Count nodes and relationships
MATCH (e:Entity) WITH count(e) as entity_count
MATCH (c:Chunk) WITH entity_count, count(c) as chunk_count
MATCH (cl:Clause) WITH entity_count, chunk_count, count(cl) as clause_count
MATCH ()-[r:MENTIONS]->() WITH entity_count, chunk_count, clause_count, count(r) as mention_count
RETURN entity_count, chunk_count, clause_count, mention_count
```

### Top Entities

```cypher
// Most frequently mentioned entities
MATCH (e:Entity)
RETURN e.canonical_name, e.entity_type, e.frequency, e.chunk_count
ORDER BY e.frequency DESC
LIMIT 20
```

### Entity Type Distribution

```cypher
// Entity distribution by type
MATCH (e:Entity)
RETURN e.entity_type, count(e) as count
ORDER BY count DESC
```

---

## 🎯 GraphRAG Use Cases

### 1. Legal Question Answering

```cypher
// Q: "What are the penalties for illegal logging?"
MATCH (c:Chunk)-[:MENTIONS]->(e:Entity)
WHERE e.canonical_name IN ["fine", "imprisonment", "penalty"]
  AND c.text CONTAINS "logging"
RETURN c.section_title, c.text
LIMIT 5
```

### 2. Entity Relationship Discovery

```cypher
// Find relationships between "forest officer" and "penalty"
MATCH path = (e1:Entity {canonical_name: "forest_officer"})<-[:MENTIONS]-(c:Chunk)-[:MENTIONS]->(e2:Entity)
WHERE e2.canonical_name IN ["fine", "imprisonment", "penalty"]
RETURN c.section, c.section_title, c.text
LIMIT 5
```

### 3. Clause-Level Retrieval

```cypher
// Find specific clause types
MATCH (c:Chunk)-[:CONTAINS_CLAUSE]->(cl:Clause)
WHERE cl.clause_marker STARTS WITH "(a)"
RETURN c.section_title, cl.text
LIMIT 10
```

---

## 🛠 Maintenance Queries

### Update Entity Metadata

```cypher
// Add custom tags to entities
MATCH (e:Entity {canonical_name: "forest_officer"})
SET e.category = "Legal Actor", e.importance = "high"
RETURN e
```

### Delete Duplicates (if any)

```cypher
// Find potential duplicates
MATCH (e1:Entity), (e2:Entity)
WHERE e1.canonical_name = e2.canonical_name AND id(e1) < id(e2)
RETURN e1, e2
```

---

## 📈 Performance Tips

1. **Create Indexes** (already done by import script):
   ```cypher
   CREATE INDEX entity_canonical_name IF NOT EXISTS FOR (e:Entity) ON (e.canonical_name)
   CREATE INDEX chunk_id IF NOT EXISTS FOR (c:Chunk) ON (c.chunk_id)
   ```

2. **Use PROFILE** to analyze queries:
   ```cypher
   PROFILE MATCH (c:Chunk)-[:MENTIONS]->(e:Entity)
   RETURN count(*)
   ```

3. **Limit Results** for large graphs:
   ```cypher
   MATCH (e:Entity)
   RETURN e
   LIMIT 100
   ```

---

## 🎉 Success Verification

After import, run these checks:

```cypher
// 1. Check entity count
MATCH (e:Entity) RETURN count(e) as entities
// Expected: 38

// 2. Check chunk count
MATCH (c:Chunk) RETURN count(c) as chunks
// Expected: 103

// 3. Check relationships
MATCH ()-[r:MENTIONS]->() RETURN count(r) as mentions
// Expected: ~733

// 4. Check clauses
MATCH (cl:Clause) RETURN count(cl) as clauses
// Expected: ~239
```

---

## 🚀 Next Steps

1. ✅ Import data to Neo4j
2. ✅ Run verification queries
3. ✅ Test GraphRAG examples
4. Build custom queries for your use case
5. Integrate with RAG pipeline
6. Add visualization (Neo4j Bloom)

---

**Status**: Ready for Neo4j import!  
**Data**: 38 entities, 103 chunks, 48.2% noise reduction  
**Files**: entity_registry.json, chunks_export.json
