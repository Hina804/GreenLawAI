# Memory Persistence Migration Plan (Week 8)

## Current State
- **Implementation**: `langgraph.checkpoint.sqlite.SqliteSaver`
- **Storage**: `e:/GL_AI/data/memory.db`
- **Scope**: Local session persistence.
- **Limitations**: File-based, not scalable for concurrent users, no built-in vector support.

## Migration Targets

### 1. Production Database: PostgreSQL (Recommended)
We recommend migrating to **PostgreSQL** using `langgraph-checkpoint-postgres`.
**Why**:
- Robust concurrency management.
- JSONB support for storing complex AgentState.
- Can coexist with the `Learning Store` (Feedback/Knowledge) which is also SQL-relational.

### 2. Implementation Steps

#### Step 1: Dependencies
```bash
pip install langgraph-checkpoint-postgres psycopg[binary]
```

#### Step 2: Code Changes (`src/agents/coordinator.py`)
Replace `SqliteSaver` with `PostgresSaver`.

```python
# FROM:
from langgraph.checkpoint.sqlite import SqliteSaver
self._saver_cm = SqliteSaver.from_conn_string("sqlite:///data/memory.db")

# TO:
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg import AsyncConnection

# Connection string management
DB_URI = os.getenv("POSTGRES_URI", "postgresql://user:pass@localhost:5432/gl_ai")

# In __init__:
self.conn = AsyncConnection.connect(DB_URI)
self.memory_saver = PostgresSaver(self.conn)
```

#### Step 3: Infrastructure
- Provision PostgreSQL 15+ instance.
- Run migration scripts to create checkpoint tables (handled automatically by `PostgresSaver` usually, or via `setup()` method).

### 3. Redis Alternative (High Speed)
If latency is the primary concern over durability:
- Use `langgraph-checkpoint-redis`.
- Best for short-term conversational context (24h).
- Less ideal for "Long Term Memory" unless using Redis Stack with JSON.

## Recommendation
**Stick with SQLite for Phase 3 (Development)**.
**Migrate to PostgreSQL for Phase 4 (Deployment)**.
 This aligns with the "Deep Knowledge" goal where relational integrity of legal/climate data is key.
