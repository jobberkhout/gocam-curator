"""UniProt REST API — protein lookup and GO annotation retrieval."""

from __future__ import annotations

import httpx

_UNIPROT_BASE = "https://rest.uniprot.org/uniprotkb/search"
_TIMEOUT = 120.0

# Common model organisms: lowercase species name → NCBI taxon ID
_TAXON_MAP: dict[str, str] = {
    "mus musculus": "10090",
    "homo sapiens": "9606",
    "rattus norvegicus": "10116",
    "drosophila melanogaster": "7227",
    "caenorhabditis elegans": "6239",
    "danio rerio": "7955",
    "arabidopsis thaliana": "3702",
    "saccharomyces cerevisiae": "559292",
    "xenopus laevis": "8355",
    "xenopus tropicalis": "8364",
}


def _taxon_id(species: str) -> str | None:
    return _TAXON_MAP.get(species.lower().strip())


def verify_protein(
    gene_symbol: str,
    species: str,
    client: httpx.Client | None = None,
) -> dict:
    """Query UniProt for a protein by gene symbol and species.

    Args:
        client: optional shared httpx.Client for connection pooling.

    Returns a dict suitable for UniProtVerification.model_validate().
    """
    if not gene_symbol:
        return {"query": f"(empty) {species}", "status": "SKIPPED"}

    taxon = _taxon_id(species)
    if taxon:
        query = f"gene:{gene_symbol} AND organism_id:{taxon}"
    else:
        query = f"gene:{gene_symbol} AND organism_name:{species}"

    def _do(c: httpx.Client) -> dict:
        r = c.get(
            _UNIPROT_BASE,
            params={
                "query": query,
                "fields": "accession,gene_names,go_id",
                "format": "json",
                "size": "5",
            },
            headers={"Accept": "application/json"},
        )

        r.raise_for_status()
        results = r.json().get("results", [])

        if not results:
            return {"query": f"{gene_symbol} {species}", "status": "NOT_FOUND"}

        entry = results[0]
        uniprot_id: str = entry.get("primaryAccession", "")

        # GO cross-references — present when fields=go_id is honoured
        go_ids: list[str] = []
        for xref in entry.get("uniProtKBCrossReferences", []):
            if xref.get("database") == "GO":
                go_id = xref.get("id", "")
                if go_id:
                    go_ids.append(go_id)

        return {
            "query": f"{gene_symbol} {species}",
            "status": "FOUND",
            "uniprot_id": uniprot_id,
            "existing_go_annotations": go_ids[:20],
        }

    try:
        if client:
            return _do(client)
        with httpx.Client(timeout=_TIMEOUT) as c:
            return _do(c)
    except httpx.TimeoutException:
        return {"query": f"{gene_symbol} {species}", "status": "TIMEOUT"}
    except Exception as exc:
        return {"query": f"{gene_symbol} {species}", "status": "ERROR", "error": str(exc)}
