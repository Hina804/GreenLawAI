# src/rag/prompts/audience_protocol.py

DUAL_MODE_PROTOCOL = """
[DUAL_AUDIENCE_MODE]

Every answer MUST contain two sections:

🌱 Simple Explanation:
- Plain language
- No legal jargon
- <= 30 words
- No complex sentences
- No clauses
- No commas if possible
- No technical terms

📘 Legal Explanation:
- Legal language
- Statute wording
- Section reference
- Clause reference
- Formal structure
- <= 50 words

📚 Source:
- Document name
- Section
- Clause
- Chunk ID
"""

SIMPLE_EXPLANATION_PROTOCOL = "🌱 Simple Explanation:"
LEGAL_EXPLANATION_PROTOCOL = "📘 Legal Explanation:"