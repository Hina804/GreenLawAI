# src/rag/prompts/limits.py

LIMITS_PROTOCOL = """
[LENGTH_LIMITS]

Simple Explanation:
- Max 30 words
- Max 2 sentences

Legal Explanation:
- Max 50 words
- Max 2 sentences

Source:
- Structured only
"""

LENGTH_LIMITS = "[LENGTH_LIMITS]"