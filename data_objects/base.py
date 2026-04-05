"""Base classes for typed, verifiable data objects."""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class VerificationMetadata:
    """Metadata about verification of a claim."""
    verified: bool
    confidence: float  # 0.0-1.0
    computed_at: str  # ISO timestamp
    verified_at: Optional[str] = None  # ISO timestamp
    verification_details: Dict[str, Any] = field(default_factory=dict)
    verification_method: str = ""  # e.g., "statistical_test", "data_inspection"
    sample_size: int = 0  # for relationship claims
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "VerificationMetadata":
        return cls(**d)


class DataObject(ABC):
    """Base class for all typed, verifiable data outputs in the pipeline."""

    def __init__(
        self,
        verified: bool = False,
        confidence: float = 0.5,
        verification_method: str = "",
    ):
        self.verified = verified
        self.confidence = confidence
        self.computed_at = datetime.utcnow().isoformat()
        self.verified_at: Optional[str] = None
        self.verification_method = verification_method
        self.verification_details: Dict[str, Any] = {}
        self.notes: str = ""

    def mark_verified(
        self,
        method: str = "",
        details: Dict[str, Any] = None,
        notes: str = "",
    ):
        """Mark this object as verified."""
        self.verified = True
        self.verified_at = datetime.utcnow().isoformat()
        self.verification_method = method or self.verification_method
        self.verification_details = details or {}
        self.notes = notes

    def get_verification_metadata(self) -> VerificationMetadata:
        """Return verification metadata for this object."""
        return VerificationMetadata(
            verified=self.verified,
            confidence=self.confidence,
            computed_at=self.computed_at,
            verified_at=self.verified_at,
            verification_details=self.verification_details,
            verification_method=self.verification_method,
            notes=self.notes,
        )

    @abstractmethod
    def to_text_summary(self) -> str:
        """Convert to concise text for LLM context."""
        pass

    @abstractmethod
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, d: dict) -> "DataObject":
        """Deserialize from dictionary."""
        pass

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "DataObject":
        """Deserialize from JSON string."""
        d = json.loads(json_str)
        return cls.from_dict(d)

    def __repr__(self) -> str:
        verified_str = "✓" if self.verified else "?"
        return (
            f"{self.__class__.__name__}({verified_str}, "
            f"confidence={self.confidence:.2f})"
        )
