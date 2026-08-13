"""
identity.py - Centralized Identity Factory for GreenLawAI
Enforces deterministic, namespace-scoped node IDs for graph integrity.
Canonicalization Contract v2.2 (Production-Hardened)
"""

import hashlib
import re
from typing import Dict
from preprocessing_pipeline.common.exceptions import SemanticViolationError


class IdentityFactory:
    """
    Factory for creating and validating deterministic IDs across the pipeline.
    Ensures that the same entity in the same jurisdiction and ontological role
    always resolves to the same ID.
    """

    @staticmethod
    def normalize_name(value: str) -> str:
        """
        Normalize strings for consistent hashing.
        - Lowercase
        - Replace non-alphanumeric characters with underscores
        - Collapse multiple underscores
        """
        if not value or not isinstance(value, str):
            return "unknown"

        normalized = value.lower().strip()
        normalized = re.sub(r"[^a-z0-9_]", "_", normalized)
        normalized = re.sub(r"_+", "_", normalized)
        return normalized.strip("_")

    @staticmethod
    def canonicalize(name: str, role: str, jurisdiction: str = "kpk") -> Dict[str, str]:
        """
        Canonicalization Contract v2.2 (Hardened)

        Role is STRICTLY MANDATORY.
        Absence of role raises SemanticViolationError to prevent ontological collisions
        (e.g., Officer vs Office vs Authority).
        """

        if not name or not isinstance(name, str):
            raise SemanticViolationError(
                "Ontological Identity Failure: name must be a non-empty string."
            )

        if not role or not isinstance(role, str) or role.strip() == "":
            raise SemanticViolationError(
                f"Ontological Identity Failure: role/entity_type is strictly mandatory for '{name}'. "
                "Prevents semantic collision between Officer, Office, Authority, etc."
            )

        return {
            "canonical_name": IdentityFactory.normalize_name(name),
            "identity_role": IdentityFactory.normalize_name(role),
            "identity_namespace": IdentityFactory.normalize_name(jurisdiction),
            "display_name": name.strip(),
        }

    @staticmethod
    def generate_deterministic_id(
        namespace: str,
        label: str,
        name: str,
        role: str,
        jurisdiction: str = "kpk",
    ) -> str:
        """
        Generate a stable, deterministic, namespace-scoped ID.

        Entropy pool includes:
        - namespace
        - label
        - ontological role
        - canonical name
        - jurisdiction

        This guarantees:
        "DFO (Officer)" ≠ "DFO (Office)"
        """

        if not namespace or not label:
            raise SemanticViolationError(
                "Identity Generation Failure: namespace and label are mandatory."
            )

        spec = IdentityFactory.canonicalize(name=name, role=role, jurisdiction=jurisdiction)

        normalized_namespace = IdentityFactory.normalize_name(namespace)
        normalized_label = IdentityFactory.normalize_name(label)
        normalized_name = spec["canonical_name"]
        normalized_role = spec["identity_role"]
        normalized_jurisdiction = spec["identity_namespace"]

        base_string = (
            f"{normalized_namespace}:"
            f"{normalized_label}:"
            f"{normalized_role}:"
            f"{normalized_name}:"
            f"{normalized_jurisdiction}"
        )

        sha_hash = hashlib.sha256(base_string.encode("utf-8")).hexdigest()

        return f"{normalized_label}_{normalized_name}_{sha_hash[:12]}"

    @staticmethod
    def validate_id(node_id: str) -> bool:
        """
        Validate whether a node ID conforms to the deterministic ID format.

        Expected format:
        <label>_<canonical_name>_<12-hex-hash>
        """

        if not node_id or not isinstance(node_id, str):
            return False

        parts = node_id.split("_")
        if len(parts) < 3:
            return False

        hash_part = parts[-1]
        if len(hash_part) != 12:
            return False

        return all(c in "0123456789abcdef" for c in hash_part.lower())
