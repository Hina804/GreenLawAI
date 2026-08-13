# Colab GPU LLM Setup Guide

## Overview

This guide shows you how to use Google Colab's **FREE GPU** for fast LLM inference (5-15 seconds) instead of slow local CPU (2-10 minutes).

## Architecture

```
Local PC (8GB RAM)              Google Colab (FREE GPU)
├─ Neo4j (380 nodes)            ├─ LLM Server (Phi/Llama2)
├─ Vector Store (103 chunks)    ├─ Flask API
├─ GraphRAG Retriever           └─ ngrok Tunnel
└─ RAG Client ──HTTP──────────────→ GPU Inference
```

## Setup (One-Time, 5 Minutes)

### Step 1: Get ngrok Token (Free)

1. Go to: https://ngrok.com/
2. Sign up (free account)
3. Go to: https://dashboard.ngrok.com/get-started/your-authtoken
4. Copy your auth token

### Step 2: Open Colab Notebook

1. Go to Google Colab: https://colab.research.google.com/
2. Upload: `e:\GL_AI\colab\llm_server.ipynb`
3. Or open from GitHub/Drive

### Step 3: Configure GPU

1. In Colab: **Runtime** → **Change runtime type**
2. Select: **GPU** (T4 is free)
3. Click **Save**

### Step 4: Run Notebook

1. **Cell 1**: Check GPU (should show GPU name)
2. **Cell 2**: Install dependencies (takes 1-2 min)
3. **Cell 3**: Import libraries
4. **Cell 4**: Load model (takes 2-3 min)
   - Default: Phi-2 (recommended)
   - Or choose Llama2/TinyLlama
5. **Cell 5**: Create Flask API
6. **Cell 6**: Start ngrok
   - **IMPORTANT**: Paste your ngrok token here!
   - Copy the public URL (e.g., `https://abc123.ngrok.io`)
7. **Cell 7**: Start server
8. **Cell 8**: Test (optional)

### Step 5: Update Local Config

1. Open: `e:\GL_AI\config\rag_config.yaml`
2. Find the `llm:` section
3. Update `colab_url` with your ngrok URL:

```yaml
llm:
  provider: "colab"
  colab_url: "https://abc123.ngrok.io"  # Paste your URL here!
```

4. Save the file

## Usage

### Every Session

1. **Start Colab notebook** (if not running)
   - Run all cells
   - Get new ngrok URL
   - Update `rag_config.yaml` if URL changed

2. **Run your RAG system**:
   ```bash
   set PYTHONIOENCODING=utf-8
   python scripts/demo_rag_qa.py
   ```

3. **Ask questions** - Get answers in 5-15 seconds! 🚀

### Example Session

```bash
$ python scripts/demo_rag_qa.py

LEGAL AI ASSISTANT
✓ LLM: colab (GPU)
✓ GraphRAG connected to Neo4j
✓ RAG Pipeline ready

You: What are the powers of a Forest Officer?

[Answer in 10 seconds with citations]
```

## Performance Comparison

| Setup | Response Time | Cost | GPU |
|-------|---------------|------|-----|
| Ollama (local CPU) | 2-10 min | $0 | ❌ |
| **Colab GPU** | **5-15 sec** | **$0** | ✅ |
| OpenAI API | 2-5 sec | $$ | ✅ |

## Troubleshooting

### "Cannot connect to Colab server"

**Solution**:
1. Check if Colab notebook is running
2. Verify ngrok URL is correct in `rag_config.yaml`
3. Test URL in browser: `https://your-url.ngrok.io/health`

### "Colab session disconnected"

**Solution**:
1. Colab free tier: 12 hours max
2. Just restart the notebook
3. Get new ngrok URL
4. Update `rag_config.yaml`

### "ngrok URL changed"

**Solution**:
- Free ngrok: URL changes each restart
- Update `rag_config.yaml` with new URL
- Or upgrade to ngrok paid ($8/month) for static URL

### "Fallback to Ollama"

**Reason**: Colab unavailable, using local Ollama

**Solution**:
- This is normal! System automatically falls back
- Answers will be slower but still work
- Restart Colab when ready

## Tips

### Keep Colab Alive

Colab disconnects after ~90 min of inactivity:
1. Keep browser tab open
2. Or use: https://chrome.google.com/webstore/detail/colab-alive
3. Or run a cell periodically

### Choose Right Model

| Model | Size | Speed | Quality | RAM |
|-------|------|-------|---------|-----|
| **Phi-2** | 2.7B | Fast | Good | 6GB |
| Llama-2-7B | 7B | Medium | Better | 13GB |
| TinyLlama | 1.1B | Fastest | OK | 4GB |

**Recommendation**: Phi-2 (best balance)

### Save Costs

- Colab GPU: 100% free
- ngrok: Free tier works fine
- **Total cost: $0**

## Advanced

### Use Custom Model

Edit Cell 4 in Colab notebook:
```python
MODEL_NAME = "your-model-name"
```

### Increase Timeout

If answers are long, increase timeout:
```yaml
llm:
  colab_timeout: 120  # 2 minutes
```

### Monitor Usage

Check Colab usage:
- Colab → **Runtime** → **View resources**
- Free tier: ~15 hours/week GPU

## Summary

✅ **Setup**: 5 minutes one-time  
✅ **Cost**: $0 forever  
✅ **Speed**: 100x faster than local CPU  
✅ **Quality**: Same as local, just faster  

**You now have a production-grade, zero-cost RAG system with GPU acceleration!** 🎉
