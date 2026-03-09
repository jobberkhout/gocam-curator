from typing import Literal, Optional

from pydantic import BaseModel, field_validator

from .entity import Entity
from .interaction import Connection, Interaction


class Expert(BaseModel):
    """Domain expert who provided biological knowledge for this process."""

    name: str
    institution: Optional[str] = None
    email: Optional[str] = None


class Paper(BaseModel):
    """A paper associated with the process."""

    pmid: str
    role: str  # e.g. "primary_evidence", "review"


class ProcessMeta(BaseModel):
    """Metadata stored in processes/<name>/meta.json."""

    process_name: str
    species: str = "Mus musculus"
    complexity: Literal["LOW", "MID", "HIGH"] = "MID"
    expert: Optional[Expert] = None
    created: str  # ISO date string
    status: str = "extraction"
    papers: list[Paper] = []


class Extraction(BaseModel):
    """Output of gocam extract — stored in extractions/<filename>.json."""

    source: str
    source_type: Literal["text", "image", "slide", "pdf"]
    timestamp: str
    extraction_pass: int = 1              # 1 = first pass, 2 = deep/second pass
    visual_description: Optional[str] = None  # for image/slide sources
    entities: list[Entity] = []
    interactions: list[Interaction] = []      # text sources
    connections_shown: list[Connection] = []  # visual sources
    compartments_shown: list[str] = []        # visual sources
    gaps: list[str] = []
    questions_for_expert: list[str] = []

    @field_validator("entities", mode="before")
    @classmethod
    def filter_entities(cls, v: object) -> list:
        if not isinstance(v, list):
            return []
        result = []
        for item in v:
            if not isinstance(item, dict):
                continue
            if "name" not in item:
                # Promote gene_symbol or label_as_shown to name rather than dropping
                fallback = item.get("gene_symbol") or item.get("label_as_shown")
                if not fallback:
                    continue
                item = {**item, "name": fallback}
            result.append(item)
        return result

    @field_validator("interactions", mode="before")
    @classmethod
    def filter_interactions(cls, v: object) -> list:
        if not isinstance(v, list):
            return []
        required = {"source_entity", "target_entity", "described_action"}
        return [item for item in v if isinstance(item, dict) and required.issubset(item)]

    @field_validator("connections_shown", mode="before")
    @classmethod
    def filter_connections(cls, v: object) -> list:
        if not isinstance(v, list):
            return []
        required = {"from_entity", "to_entity"}
        return [item for item in v if isinstance(item, dict) and required.issubset(item)]

    @field_validator("gaps", "questions_for_expert", "compartments_shown", mode="before")
    @classmethod
    def filter_strings(cls, v: object) -> list:
        if not isinstance(v, list):
            return []
        return [item for item in v if isinstance(item, str)]
