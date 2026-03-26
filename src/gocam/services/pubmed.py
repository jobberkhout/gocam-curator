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


def verify_pmid(pmid: str) -> dict:
    """Verify a PMID exists in PubMed and retrieve title + DOI.

    Returns a dict with keys: pmid, status, title (if found), doi (if found).
    Status is "VERIFIED", "INVALID", or "ERROR".

    Retries up to 3 times with exponential back-off (2 s, 4 s, 8 s) when
    PubMed responds with 429 Too Many Requests.
    """
    if not pmid or not pmid.strip().isdigit():
        return {"pmid": pmid or "", "status": "INVALID"}

    _rate_limit()

    _backoff = [2, 4, 8]
    for attempt in range(4):
        try:
            r = httpx.get(
                f"{_BASE}/esummary.fcgi",
                params={"db": "pubmed", "id": pmid.strip(), "retmode": "json"},
                timeout=_TIMEOUT,
            )
            if r.status_code == 429:
                if attempt < len(_backoff):
                    time.sleep(_backoff[attempt])
                    continue
                return {"pmid": pmid, "status": "ERROR", "error": "429 rate-limited after retries"}

            r.raise_for_status()
            data  = r.json().get("result", {})
            entry = data.get(pmid.strip(), {})

            if "error" in entry:
                return {"pmid": pmid, "status": "INVALID"}

            title = entry.get("title", "")
            doi: str | None = None

            # Try elocationid first (format: "doi: 10.xxxx/xxxxx")
            eloc = entry.get("elocationid", "")
            if eloc.lower().startswith("doi:"):
                doi = eloc.split(":", 1)[1].strip()

            # Fallback: check articleids list
            if not doi:
                for aid in entry.get("articleids", []):
                    if aid.get("idtype") == "doi":
                        doi = aid.get("value", "")
                        break

            return {"pmid": pmid, "status": "VERIFIED", "title": title, "doi": doi}

        except httpx.HTTPStatusError:
            raise
        except Exception as exc:
            return {"pmid": pmid, "status": "ERROR", "error": str(exc)}

    return {"pmid": pmid, "status": "ERROR", "error": "max retries exceeded"}


def resolve_pmid_from_doi(doi: str) -> str | None:
    """Look up a PMID from a DOI using PubMed esearch.

    Returns the PMID string if found, or None.
    """
    if not doi or not doi.strip():
        return None
    _rate_limit()
    try:
        r = httpx.get(
            f"{_BASE}/esearch.fcgi",
            params={
                "db": "pubmed",
                "term": f"{doi.strip()}[doi]",
                "retmode": "json",
                "retmax": "1",
            },
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        ids = r.json().get("esearchresult", {}).get("idlist", [])
        return ids[0] if ids else None
    except Exception:
        return None


def resolve_doi_from_title(title: str) -> str | None:
    """Resolve a DOI from a paper title via CrossRef (fallback when PubMed has no DOI)."""
    if not title or not title.strip():
        return None
    time.sleep(1.0)  # CrossRef rate limiting
    try:
        r = httpx.get(
            "https://api.crossref.org/works",
            params={"query.bibliographic": title.strip(), "rows": "1"},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        items = r.json().get("message", {}).get("items", [])
        if items:
            return items[0].get("DOI")
    except Exception:
        pass
    return None
