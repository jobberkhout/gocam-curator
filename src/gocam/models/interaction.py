from typing import Literal, Optional

from pydantic import BaseModel, field_validator

_VALID_CAUSAL_TYPES = {"DIRECT", "STRUCTURAL_PREREQUISITE", "INDIRECT", "UNKNOWN"}


class Interaction(BaseModel):
    """A directed interaction between two entities extracted from text."""

    source_entity: str
    target_entity: str
    described_action: str
    quote: Optional[str] = None
    pmid: Optional[str] = None          # PMID extracted from paper header (e.g. "12345678")
    figure: Optional[str] = None        # Exact figure reference (e.g. "Fig. 3B")
    assay_described: Optional[str] = None
    causal_type: Optional[Literal["DIRECT", "STRUCTURAL_PREREQUISITE", "INDIRECT", "UNKNOWN"]] = None
    confidence_note: Optional[str] = None

    @field_validator("causal_type", mode="before")
    @classmethod
    def coerce_causal_type(cls, v: object) -> str | None:
        if v is None:
            return None
        upper = str(v).upper()
        return upper if upper in _VALID_CAUSAL_TYPES else None


class Connection(BaseModel):
    """A connection between two entities extracted from a visual source (diagram, cartoon)."""

    # Use 'from_entity' / 'to_entity' since 'from' is a Python keyword
    from_entity: str
    to_entity: str
    arrow_type: Optional[str] = None
    implied_relation: Optional[str] = None
    note: Optional[str] = None
