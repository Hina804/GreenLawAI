# RAG Application Setup Guide

## Overview

This guide explains how to set up the cloud-based RAG application with path consistency across Colab and local environments.

## Architecture

```
Colab (GPU) → Cloud Storage → Local PC (Query Only)
```

- **Colab**: Heavy processing (embeddings, chunking, entities)
- **Cloud**: Persistent storage (ChromaDB, entity registry, Neo4j exports)
- **Local**: Query interface (Neo4j + RAG pipeline)

---

## Setup Steps

### 1. Cloud Storage Setup

**Option A: Google Drive** (Recommended)
1. Create folder: `My Drive/GL_AI`
2. In Colab: Mount drive
3. On local PC: Install Google Drive Desktop
4. Map drive letter (e.g., `G:/My Drive`)

**Option B: OneDrive**
1. Create folder: `OneDrive/GL_AI`
2. Sync to local PC
3. Update `config/rag_config.yaml` with path

### 2. Colab Ingestion (First Time)

**File**: `colab/ingestion_pipeline.ipynb`

```python
# Cell 1: Mount Drive
from google.colab import drive
drive.mount('/content/drive')

# Cell 2: Install Dependencies
!pip install -r requirements_colab.txt

# Cell 3: Run Pipeline
# (See notebook for full code)
```

**Output**: Creates all artifacts in cloud storage

### 3. Local PC Setup

**Install Dependencies**:
```bash
pip install -r requirements_rag.txt
```

**Configure Paths** (`config/rag_config.yaml`):
```yaml
cloud_storage:
  provider: "gdrive"
  mount_point: "G:/My Drive"  # Update for your system
```

**Set API Key**:
```bash
# Windows
set OPENAI_API_KEY=your-key-here

# Or create .env file
echo OPENAI_API_KEY=your-key-here > .env
```

### 4. Neo4j Setup

**Load from Cloud**:
```bash
python scripts/setup_neo4j_from_cloud.py
```

This reads CSVs from cloud storage and imports to local Neo4j.

### 5. Run RAG Application

```bash
python scripts/demo_rag_qa.py
```

**Commands**:
- `<question>` - Ask a question
- `/history` - Show conversation
- `/clear` - Clear history
- `/save` - Save conversation
- `/exit` - Quit

---

## Path Consistency

### How It Works

**CloudStorageManager** automatically detects:
1. **Environment**: Colab vs Local
2. **Provider**: Google Drive, OneDrive, etc.
3. **Mount Point**: Default or custom

**All paths are generated from base**:
```python
base = "G:/My Drive/GL_AI"  # Local
base = "/content/drive/MyDrive/GL_AI"  # Colab

# Auto-generated:
chroma_db = f"{base}/chroma_db"
entity_registry = f"{base}/entity_registry.json"
# etc.
```

### Validation

Before every query:
```python
cloud.validate_artifacts()
# Checks: chroma_db, entity_registry, chunks_export
```

If missing → Error with instructions to run Colab pipeline.

---

## Troubleshooting

### "Cloud artifacts missing"
**Solution**: Run Colab ingestion pipeline first

### "Google Drive not mounted"
**Solution**: 
- Colab: Run `drive.mount('/content/drive')`
- Local: Install Google Drive Desktop

### "Neo4j connection failed"
**Solution**: 
1. Start Neo4j Desktop
2. Check URI in `config/rag_config.yaml`

### "OpenAI API key not found"
**Solution**: Set environment variable `OPENAI_API_KEY`

---

## File Structure

```
GL_AI/
├── config/
│   └── rag_config.yaml          # Main configuration
├── src/
│   └── rag/
│       ├── cloud_storage.py     # Path management
│       ├── llm_manager.py       # LLM providers
│       ├── rag_pipeline.py      # Main pipeline
│       ├── chat_manager.py      # Conversation history
│       └── prompts.py           # Prompt templates
├── scripts/
│   └── demo_rag_qa.py           # Interactive CLI
├── requirements_rag.txt         # Local dependencies
└── requirements_colab.txt       # Colab dependencies
```

**Cloud Storage** (`G:/My Drive/GL_AI/`):
```
GL_AI/
├── chroma_db/                   # Vector store
├── entity_registry.json         # Entity metadata
├── chunks_export.json           # Structured chunks
└── neo4j_imports/               # CSV files
```

---

## Next Steps

1. ✅ Set up cloud storage
2. ✅ Run Colab ingestion
3. ✅ Configure local paths
4. ✅ Import to Neo4j
5. ✅ Test RAG Q&A

**Ready to answer legal questions!** 🎉
