# Legacy models (kept for backward compatibility with existing commands)
from .entity import Entity
from .interaction import Interaction, Connection
from .evidence import GOTerm, ECOEvidence, EvidenceRecord, EvidenceRecordsFile
from .process import Expert, Paper, ProcessMeta, Extraction

# New claim-based models (refactored pipeline)
from .claim import (
    NodeClaim,
    EdgeClaim,
    ClaimUnion,
    ExtractionFile,
    ValidatedGOTerm,
    ValidatedEvidence,
    ValidatedNodeClaim,
    ValidatedEdgeClaim,
    ValidationReport,
)

__all__ = [
    # Legacy
    "Entity",
    "Interaction",
    "Connection",
    "GOTerm",
    "ECOEvidence",
    "EvidenceRecord",
    "EvidenceRecordsFile",
    "Expert",
    "Paper",
    "ProcessMeta",
    "Extraction",
    # New
    "NodeClaim",
    "EdgeClaim",
    "ClaimUnion",
    "ExtractionFile",
    "ValidatedGOTerm",
    "ValidatedEvidence",
    "ValidatedNodeClaim",
    "ValidatedEdgeClaim",
    "ValidationReport",
]
