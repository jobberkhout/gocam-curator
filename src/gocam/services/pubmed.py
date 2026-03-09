"""PubMed E-utilities — search and abstract fetch (no API key required for <3 req/sec)."""

from __future__ import annotations

import time

import httpx

_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_RATE_DELAY = 0.4  # seconds between requests (PubMed policy: max 3/sec without key)
_TIMEOUT = 20.0

_last_call: float = 0.0


def _rate_limit() -> None:
    """Sleep if necessary to stay under PubMed's rate limit."""
    global _last_call
    elapsed = time.monotonic() - _last_call
    if elapsed < _RATE_DELAY:
        time.sleep(_RATE_DELAY - elapsed)
    _last_call = time.monotonic()


def search(query: str, retmax: int = 5) -> list[str]:
    """Search PubMed and return a list of PMIDs (sorted by relevance).

    Args:
        query:  PubMed query string (e.g. "PICK1 AND dynamin AND endocytosis").
        retmax: Maximum number of results to return.

    Returns:
        List of PMID strings (may be empty).
    """
    _rate_limit()
    try:
        r = httpx.get(
            f"{_BASE}/esearch.fcgi",
            params={
                "db": "pubmed",
                "term": query,
                "retmax": str(retmax),
                "sort": "relevance",
                "retmode": "json",
            },
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        return r.json().get("esearchresult", {}).get("idlist", [])
    except Exception:
        return []


def fetch_abstracts(pmids: list[str]) -> str:
    """Fetch plain-text abstracts for a list of PMIDs.

    Returns a single string with all abstracts concatenated, separated by
    a blank line and a PMID header. Returns empty string on failure.
    """
    if not pmids:
        return ""
    _rate_limit()
    try:
        r = httpx.get(
            f"{_BASE}/efetch.fcgi",
            params={
                "db": "pubmed",
                "id": ",".join(pmids),
                "rettype": "abstract",
                "retmode": "text",
            },
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        return r.text
    except Exception:
        return ""


def fetch_abstract(pmid: str) -> str:
    """Fetch a plain-text abstract for a single PMID."""
    return fetch_abstracts([pmid])
