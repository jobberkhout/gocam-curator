"""QuickGO REST API — GO term verification and search."""

from __future__ import annotations

import httpx

_QUICKGO_BASE = "https://www.ebi.ac.uk/QuickGO/services/ontology/go/terms"
_QUICKGO_SEARCH = "https://www.ebi.ac.uk/QuickGO/services/ontology/go/search"
_QUICKGO_ANNOTATIONS = "https://www.ebi.ac.uk/QuickGO/services/annotation/search"
_AMIGO_SEARCH = "https://amigo.geneontology.org/amigo/search/ontology"
_TIMEOUT = 15.0

# QuickGO aspect strings → what we expect in each record field
_EXPECTED_ASPECTS = {
    "molecular_function": "molecular_function",
    "biological_process": "biological_process",
    "cellular_component": "cellular_component",
}


def verify_go_term(
    go_id: str,
    expected_aspect: str | None = None,
    client: httpx.Client | None = None,
) -> dict:
    """Query QuickGO for a single GO term.

    Args:
        go_id: e.g. "GO:0004674". Pass "UNKNOWN" or "" to skip.
        expected_aspect: "molecular_function" | "biological_process" | "cellular_component"
        client: optional shared httpx.Client for connection pooling.

    Returns a dict suitable for GOTermVerification.model_validate().
    """
    if not go_id or go_id.upper() in ("UNKNOWN", ""):
        return {"suggested": go_id or "UNKNOWN", "status": "SKIPPED"}

    def _do(c: httpx.Client) -> dict:
        r = c.get(
            f"{_QUICKGO_BASE}/{go_id}",
            headers={"Accept": "application/json"},
        )

        if r.status_code == 404:
            return {"suggested": go_id, "status": "NOT_FOUND"}

        r.raise_for_status()
        results = r.json().get("results", [])

        if not results:
            return {"suggested": go_id, "status": "NOT_FOUND"}

        term = results[0]
        aspect: str = term.get("aspect", "")
        official_label: str = term.get("name", "")
        is_obsolete: bool = term.get("isObsolete", False)

        result: dict = {
            "suggested": go_id,
            "status": "OBSOLETE" if is_obsolete else "VERIFIED",
            "official_label": official_label,
            "aspect": aspect,
        }

        if expected_aspect:
            result["aspect_match"] = (aspect == expected_aspect)

        return result

    try:
        if client:
            return _do(client)
        with httpx.Client(timeout=_TIMEOUT) as c:
            return _do(c)
    except httpx.TimeoutException:
        return {"suggested": go_id, "status": "TIMEOUT"}
    except Exception as exc:
        return {"suggested": go_id, "status": "ERROR", "error": str(exc)}


def search_go_terms(
    label: str,
    aspect: str,
    limit: int = 5,
    client: httpx.Client | None = None,
) -> list[dict]:
    """Search QuickGO for GO terms matching a label within an aspect.

    Falls back to AmiGO if QuickGO returns no results.
    Returns a list of dicts with keys: go_id, label.
    """
    _VALID_ASPECTS = {"molecular_function", "biological_process", "cellular_component"}
    if aspect not in _VALID_ASPECTS or not label.strip():
        return []

    def _do(c: httpx.Client) -> list[dict]:
        r = c.get(
            _QUICKGO_SEARCH,
            params={"query": label, "aspect": aspect, "limit": limit},
            headers={"Accept": "application/json"},
        )
        if r.is_success:
            results = r.json().get("results", [])
            hits = [
                {"go_id": t.get("id", ""), "label": t.get("name", "")}
                for t in results
                if t.get("id") and t.get("name")
            ]
            if hits:
                return hits
        return []

    try:
        if client:
            hits = _do(client)
        else:
            with httpx.Client(timeout=_TIMEOUT) as c:
                hits = _do(c)
        if hits:
            return hits
    except Exception:
        pass

    # Fallback: AmiGO ontology search
    return _search_amigo(label, limit)


def _search_amigo(label: str, limit: int = 5) -> list[dict]:
    """Search AmiGO as fallback when QuickGO returns no results."""
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            r = client.get(
                _AMIGO_SEARCH,
                params={"q": label, "rows": limit},
                headers={"Accept": "application/json"},
            )
        if not r.is_success:
            return []
        docs = r.json().get("response", {}).get("docs", [])
        return [
            {
                "go_id": d.get("annotation_class", ""),
                "label": d.get("annotation_class_label", ""),
            }
            for d in docs
            if d.get("annotation_class", "").startswith("GO:") and d.get("annotation_class_label")
        ]
    except Exception:
        return []


def _batch_go_names(go_ids: list[str]) -> dict[str, str]:
    """Fetch GO term names for a list of IDs from the QuickGO terms endpoint.

    The annotation search endpoint does not return goName, so we resolve names
    separately.  Returns a dict mapping go_id → term_name.
    """
    if not go_ids:
        return {}
    # QuickGO accepts up to ~200 comma-separated IDs in the path
    ids_str = ",".join(go_ids[:200])
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            r = client.get(
                f"{_QUICKGO_BASE}/{ids_str}",
                headers={"Accept": "application/json"},
            )
        if not r.is_success:
            return {}
        results = r.json().get("results", [])
        return {item.get("id", ""): item.get("name", "") for item in results}
    except Exception:
        return {}


def get_protein_annotations(
    uniprot_id: str,
    limit: int = 200,
    client: httpx.Client | None = None,
) -> list[dict]:
    """Fetch existing GO annotations for a protein from QuickGO.

    Returns a list of dicts with keys: go_id, label, aspect.
    Returns an empty list on any error or if uniprot_id is not set.
    """
    if not uniprot_id or uniprot_id in ("UNVERIFIED", ""):
        return []

    def _do(c: httpx.Client) -> list[dict]:
        r = c.get(
            _QUICKGO_ANNOTATIONS,
            params={
                "geneProductId": f"UniProtKB:{uniprot_id}",
                "limit": limit,
            },
            headers={"Accept": "application/json"},
        )
        if not r.is_success:
            return []
        results = r.json().get("results", [])
        seen: set[str] = set()
        annotations: list[dict] = []
        for ann in results:
            go_id = ann.get("goId", "")
            if go_id and go_id not in seen:
                seen.add(go_id)
                annotations.append({
                    "go_id": go_id,
                    "label": "",  # resolved below
                    "aspect": ann.get("goAspect", ""),
                })
        # Resolve GO term names in a single batch call
        if annotations:
            names = _batch_go_names([a["go_id"] for a in annotations])
            for a in annotations:
                a["label"] = names.get(a["go_id"], "")
        return annotations

    try:
        if client:
            return _do(client)
        with httpx.Client(timeout=_TIMEOUT) as c:
            return _do(c)
    except Exception:
        return []
