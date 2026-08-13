# src/rag/prompts/citation_protocol.py

CITATION_PROTOCOL = """
[CITATION_FORMAT]

Format:

📚 Source:
- Document: <name>
- Section: <section>
- Clause: <clause>
- Chunk ID: <chunk_id>

Rules:
- No placeholders
- No guesses
- No invented sections
- No invented clauses
- No invented acts
- No partial references
"""