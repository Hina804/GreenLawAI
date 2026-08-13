# src/rag/prompts/abstention.py

ABSTENTION_PROTOCOL = """
[ABSTENTION_TEMPLATE]

🌱 Simple Explanation:
This information is not available in the provided legal documents.

📘 Legal Explanation:
The retrieved sources do not contain a legal provision answering this question.

📚 Source:
Not available in current document set.
"""

ABSTENTION_MESSAGE = "Answer not available in provided legal sources."