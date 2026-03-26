"""Pydantic v2 models for the GO-CAM claim extraction and validation pipeline."""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Discriminator, Field, Tag


# ---------------------------------------------------------------------------
# Raw extraction models (output of gocam extract)
# ---------------------------------------------------------------------------

class _ClaimBase(BaseModel):
    """Shared fields for all claim types."""
    id: str
    quote: str | None = None
    figure: str | None = None
    assay_described: str | None = None
    pmid_from_text: str | None = None
    confidence: Literal["HIGH", "MEDIUM", "LOW"] = "MEDIUM"


class NodeClaim(_ClaimBase):
    """A molecular activity node in GO-CAM."""
    type: Literal["node"] = "node"
    protein_name: str
    gene_symbol: str | None = None
    molecular_function: str | None = None
    biological_process: str | None = None
    cellular_component: str | None = None


class EdgeClaim(_ClaimBase):
    """A causal relation edge in GO-CAM."""
    type: Literal["edge"] = "edge"
    subject: str
    relation: str
    object: str
    mechanism: str | None = None


def _claim_discriminator(v: dict | BaseModel) -> str:
    if isinstance(v, dict):
        return v.get("type", "node")
    return getattr(v, "type", "node")


ClaimUnion = Annotated[
    Union[
        Annotated[NodeClaim, Tag("node")],
        Annotated[EdgeClaim, Tag("edge")],
    ],
    Discriminator(_claim_discriminator),
]


class ExtractionFile(BaseModel):
    """Container for a single extraction output file."""
    source: str
    source_type: str = "text"
    timestamp: str = ""
    source_doi: str | None = None    # DOI of the source paper (PDFs only)
    source_pmid: str | None = None   # PMID from filename (curator-controlled)
    claims: list[ClaimUnion] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Validated models (output of gocam validate)
# ---------------------------------------------------------------------------

class ValidatedGOTerm(BaseModel):
    """A GO term that has been checked against QuickGO."""
    term: str
    go_id: str | None = None
    status: Literal["VERIFIED", "OBSOLETE", "NOT_FOUND", "SKIPPED"] = "SKIPPED"
    official_label: str | None = None
    already_annotated: bool = False
    syngo_confirmed: bool = False


class ValidatedEvidence(BaseModel):
    """Evidence fields after PMID/DOI/ECO validation."""
    pmid: str | None = None
    pmid_status: Literal["VERIFIED", "INVALID", "NOT_CHECKED", "RESOLVED_FROM_DOI", "ERROR"] = "NOT_CHECKED"
    pmid_title: str | None = None
    doi: str | None = None
    figure: str | None = None
    assay: str | None = None
    eco_code: str | None = None
    eco_label: str | None = None
    eco_status: Literal["VERIFIED", "OBSOLETE", "NOT_FOUND", "SKIPPED", "ERROR"] = "SKIPPED"
    source_file: str | None = None   # which extraction file this evidence came from


class SynGOTerm(BaseModel):
    """A single SynGO-curated GO term annotation with supporting PMIDs."""
    go_id: str
    go_name: str
    domain: str       # "BP" or "CC"
    pmids: list[str] = Field(default_factory=list)


class ValidatedNodeClaim(BaseModel):
    """A fully validated node claim."""
    id: str
    type: Literal["node"] = "node"
    protein_name: str
    gene_symbol: str | None = None
    uniprot_id: str | None = None
    uniprot_status: Literal["FOUND", "NOT_FOUND", "SKIPPED"] = "SKIPPED"
    molecular_function: ValidatedGOTerm | None = None
    biological_process: ValidatedGOTerm | None = None
    cellular_component: ValidatedGOTerm | None = None
    evidence: ValidatedEvidence | None = None
    confidence: str = "MEDIUM"
    syngo_annotations: list[str] = Field(default_factory=list)   # kept for display/legacy
    syngo_enrichment: list[SynGOTerm] = Field(default_factory=list)  # structured, with PMIDs
    quote: str | None = None


class ValidatedEdgeClaim(BaseModel):
    """A fully validated edge claim."""
    id: str
    type: Literal["edge"] = "edge"
    subject: str
    relation: str
    object: str
    mechanism: str | None = None
    evidence: ValidatedEvidence | None = None
    confidence: str = "MEDIUM"
    quote: str | None = None


class ValidationReport(BaseModel):
    """Container for the full validated output of a process."""
    timestamp: str
    process_name: str
    species: str
    nodes: list[ValidatedNodeClaim] = Field(default_factory=list)
    edges: list[ValidatedEdgeClaim] = Field(default_factory=list)
