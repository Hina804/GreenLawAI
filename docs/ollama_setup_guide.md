# Ollama Setup Guide - 100% Free Local LLM

## What is Ollama?

Ollama lets you run large language models (LLMs) locally on your computer for **FREE**. No API keys, no payments, no internet required after download.

## Installation Steps

### Step 1: Download Ollama

**Windows**:
1. Go to: https://ollama.com/download
2. Click "Download for Windows"
3. Run the installer (OllamaSetup.exe)
4. Follow the installation wizard

**Size**: ~500MB installer

### Step 2: Install a Model

After Ollama is installed, open Command Prompt or PowerShell:

```bash
# Option 1: Llama 2 (7B) - Recommended for 4GB RAM
ollama pull llama2

# Option 2: Mistral (7B) - Faster, good quality
ollama pull mistral

# Option 3: Phi (2.7B) - Smallest, fastests
ollama pull phi
```

**Download sizes**:
- llama2: ~3.8GB
- mistral: ~4.1GB
- phi: ~1.6GB

**Recommendation for 4GB RAM**: Use `phi` (smallest) or `llama2`

### Step 3: Verify Installation

```bash
# Check if Ollama is running
ollama list

# Test a model
ollama run llama2 "Hello, how are you?"
```

You should see a response from the model.

### Step 4: Update Configuration

Already done! Your `config/rag_config.yaml` is now set to:
```yaml
llm:
  provider: "ollama"
  model: "llama2"
  base_url: "http://localhost:11434"
```

### Step 5: Test RAG Q&A

```bash
python scripts/demo_rag_qa.py
```

## System Requirements

**Minimum**:
- RAM: 4GB (for phi or llama2)
- Storage: 5GB free space
- CPU: Any modern processor

**Recommended**:
- RAM: 8GB
- GPU: Optional (speeds up inference)

## Model Comparison

| Model | Size | RAM Needed | Speed | Quality |
|-------|------|------------|-------|---------|
| phi | 1.6GB | 2-3GB | Fast | Good |
| llama2 | 3.8GB | 4-6GB | Medium | Very Good |
| mistral | 4.1GB | 4-6GB | Fast | Excellent |

## Troubleshooting

**"Ollama not found"**:
- Restart your terminal after installation
- Check if Ollama is running: `ollama list`

**"Out of memory"**:
- Use smaller model: `ollama pull phi`
- Close other applications

**"Model not found"**:
- Pull the model first: `ollama pull llama2`

## Cost Comparison

| Provider | Cost |
|----------|------|
| OpenAI GPT-4 | $0.03 per 1K tokens (~$3-5/day) |
| Anthropic Claude | $0.015 per 1K tokens (~$2-3/day) |
| **Ollama (Local)** | **$0 - 100% FREE** |

## Next Steps

1. ✅ Install Ollama
2. ✅ Download a model (`ollama pull llama2`)
3. ✅ Configuration updated
4. ✅ Test: `python scripts/demo_rag_qa.py`

**Zero cost, fully functional RAG system!** 🎉
