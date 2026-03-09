from typing import Optional

from pydantic import BaseModel, field_validator


class GOTerm(BaseModel):
    """A Gene Ontology term suggestion (always unverified until gocam verify runs)."""

    term: str
    go_id: str = "UNKNOWN"
    verified: bool = False
    specificity_check: Optional[str] = None


class ECOEvidence(BaseModel):
    """Evidence anchoring a claim to a specific experiment in a specific paper."""

    quote: Optional[str] = None
    pmid: Optional[str] = None
    figure: Optional[str] = None

    @field_validator("pmid", mode="before")
    @classmethod
    def reject_unknown_pmid(cls, v: object) -> str | None:
        """Coerce "UNKNOWN" / empty strings to None — only real PMIDs (digits) are valid."""
        if v is None:
            return None
        s = str(v).strip()
        if not s or s.upper() in ("UNKNOWN", "NULL", "NONE", "N/A"):
            return None
        return s

    assay: Optional[str] = None
    eco_code: str = "UNKNOWN"
    eco_label: Optional[str] = None
    eco_verified: bool = False
    controls_noted: Optional[str] = None


class EvidenceRecord(BaseModel):
    """A single GO-CAM evidence record mapping one protein activity to GO/ECO terms."""

    id: str
    protein: dict  # name, gene_symbol, uniprot_id, species
    molecular_function: Optional[GOTerm] = None
    biological_process: Optional[GOTerm] = None
    cellular_component: Optional[GOTerm] = None
    relation_to_target: Optional[dict] = None   # type, target, mechanism
    relation_to_process: Optional[dict] = None  # type, target_bp
    evidence: Optional[ECOEvidence] = None
    confidence: str = "MEDIUM"
    car_test: Optional[str] = None
    warnings: list[str] = []
    de_novo_terms: list[str] = []


class EvidenceRecordsFile(BaseModel):
    """Top-level container written to evidence_records/records.json."""

    timestamp: str
    records: list[EvidenceRecord] = []
