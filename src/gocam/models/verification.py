"""Pydantic models for the verification report (gocam verify output)."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class GOTermVerification(BaseModel):
    suggested: str
    status: str  # VERIFIED | OBSOLETE | NOT_FOUND | SKIPPED | TIMEOUT | ERROR
    official_label: Optional[str] = None
    label_match: Optional[bool] = None
    aspect: Optional[str] = None        # "molecular_function" | "biological_process" | "cellular_component"
    aspect_match: Optional[bool] = None
    already_annotated: bool = False     # protein already has this GO ID in QuickGO
    error: Optional[str] = None
    alternative_suggestions: list[dict] = []  # [{go_id, label}] when label/aspect mismatch


class UniProtVerification(BaseModel):
    query: str
    status: str  # FOUND | NOT_FOUND | SKIPPED | TIMEOUT | ERROR
    uniprot_id: Optional[str] = None
    existing_go_annotations: list[str] = []       # from UniProt cross-refs
    quickgo_annotations: list[dict] = []          # [{go_id, label, aspect}] from QuickGO
    error: Optional[str] = None


class ECOVerification(BaseModel):
    suggested: str
    status: str  # VERIFIED | OBSOLETE | NOT_FOUND | SKIPPED | TIMEOUT | ERROR
    official_label: Optional[str] = None
    eco_suggestions: list[dict] = []  # [{eco_id, label}] when eco_code is UNKNOWN
    error: Optional[str] = None


class RecordVerification(BaseModel):
    record_id: str
    go_mf: Optional[GOTermVerification] = None
    go_bp: Optional[GOTermVerification] = None
    go_cc: Optional[GOTermVerification] = None
    uniprot: Optional[UniProtVerification] = None
    eco: Optional[ECOVerification] = None


class VerificationSummary(BaseModel):
    total_records: int
    go_terms_verified: int
    go_terms_failed: int
    go_terms_obsolete: int
    go_terms_skipped: int
    go_terms_already_annotated: int   # confirmed via QuickGO existing annotations
    uniprot_confirmed: int
    eco_verified: int


class VerificationReport(BaseModel):
    timestamp: str
    summary: VerificationSummary
    details: list[RecordVerification] = []
