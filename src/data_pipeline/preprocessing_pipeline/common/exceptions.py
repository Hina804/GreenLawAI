"""
EXCEPTIONS.PY - Specialized Pipeline Exception Hierarchy
Defines error classes for production hardening and forensic compliance.
"""

class PipelineError(Exception):
    """Base class for all pipeline-related errors."""
    pass

class ExtractionError(PipelineError):
    """
    RECOVERABLE: Errors during data extraction (NER, OCR, LLM parsing).
    These should be logged and tracked in statistics but do not halt the run.
    """
    pass

class SemanticViolationError(PipelineError):
    """
    NON-RECOVERABLE (Node Level): Errors in ontological meaning or identity.
    Used when a node fails mandatory schema or identity constraints (e.g., missing mandatory role).
    Halts processing for the specific node/entity but may allow the rest of the batch to proceed.
    """
    pass

class ForensicIntegrityError(PipelineError):
    """
    UNRECOVERABLE (Run Level): Compliance violation related to data lineage.
    Used when mandatory forensic metadata (bbox, source_doc_id) is missing in production mode.
    This is treated as a hard stop for the entire pipeline run to prevent legally indefensible data.
    """
    pass
