"""OLS4/EBI REST API — ECO code verification and search."""

from __future__ import annotations

import httpx

_OLS_BASE = "https://www.ebi.ac.uk/ols4/api/ontologies/eco/terms"
_OLS_SEARCH = "https://www.ebi.ac.uk/ols4/api/search"
_TIMEOUT = 15.0


def _eco_to_iri(eco_code: str) -> str:
    """Convert 'ECO:0000006' → 'http://purl.obolibrary.org/obo/ECO_0000006'."""
    return f"http://purl.obolibrary.org/obo/{eco_code.replace(':', '_')}"


def verify_eco(eco_code: str, client: httpx.Client | None = None) -> dict:
    """Query OLS4 for a single ECO code.

    Args:
        client: optional shared httpx.Client for connection pooling.

    Returns a dict suitable for ECOVerification.model_validate().
    """
    if not eco_code or eco_code.upper() in ("UNKNOWN", ""):
        return {"suggested": eco_code or "UNKNOWN", "status": "SKIPPED"}

    iri = _eco_to_iri(eco_code)

    def _do(c: httpx.Client) -> dict:
        r = c.get(
            _OLS_BASE,
            params={"iri": iri},
            headers={"Accept": "application/json"},
        )

        r.raise_for_status()
        terms = r.json().get("_embedded", {}).get("terms", [])

        if not terms:
            return {"suggested": eco_code, "status": "NOT_FOUND"}

        term = terms[0]
        label: str = term.get("label", "")
        is_obsolete: bool = term.get("is_obsolete", False)

        return {
            "suggested": eco_code,
            "status": "OBSOLETE" if is_obsolete else "VERIFIED",
            "official_label": label,
        }

    try:
        if client:
            return _do(client)
        with httpx.Client(timeout=_TIMEOUT) as c:
            return _do(c)
    except httpx.TimeoutException:
        return {"suggested": eco_code, "status": "TIMEOUT"}
    except Exception as exc:
        return {"suggested": eco_code, "status": "ERROR", "error": str(exc)}


def search_eco_terms(
    assay_name: str,
    limit: int = 5,
    client: httpx.Client | None = None,
) -> list[dict]:
    """Search OLS4 for ECO terms matching an assay description.

    Used when eco_code is UNKNOWN but we know the assay name from the evidence.
    Returns a list of dicts with keys: eco_id, label.
    Returns an empty list on any error or timeout.
    """
    if not assay_name.strip():
        return []

    def _do(c: httpx.Client) -> list[dict]:
        r = c.get(
            _OLS_SEARCH,
            params={"q": assay_name, "ontology": "eco", "rows": limit},
            headers={"Accept": "application/json"},
        )
        if not r.is_success:
            return []
        docs = r.json().get("response", {}).get("docs", [])
        return [
            {
                "eco_id": d.get("short_form", "").replace("_", ":"),
                "label": d.get("label", ""),
            }
            for d in docs
            if d.get("short_form", "").startswith("ECO") and d.get("label")
        ]

    try:
        if client:
            return _do(client)
        with httpx.Client(timeout=_TIMEOUT) as c:
            return _do(c)
    except Exception:
        return []
