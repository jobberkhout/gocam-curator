from pydantic import BaseModel
from typing import Optional


class Entity(BaseModel):
    """A protein or gene entity extracted from text or visual sources."""

    name: str
    gene_symbol: Optional[str] = None
    mentioned_activities: list[str] = []
    context: Optional[str] = None

    # Visual-extraction fields (populated when source_type == "image" or "slide")
    label_as_shown: Optional[str] = None
    position_in_diagram: Optional[str] = None
    implied_activity: Optional[str] = None
