"""OLS4/EBI REST API — ECO code verification and search.

ECO lookup strategy
-------------------
1. Primary  — OLS4 semantic search:
   POST/GET https://www.ebi.ac.uk/ols4/api/search?q=<assay_text>&ontology=eco&rows=3
   The top result is accepted when its Solr relevance score exceeds
   _SCORE_THRESHOLD.  This handles the diverse free-text assay descriptions
   that extraction produces without requiring an exhaustive keyword table.

2. Fallback — broad category matching:
   A single indicator word in the lowercased assay description is enough to
   assign a high-level ECO category code.  Categories are checked in order;
   more specific entries appear first.

3. If neither step produces a result, the caller warns the curator.
"""

from __future__ import annotations

import time
import httpx

_OLS_BASE   = "https://www.ebi.ac.uk/ols4/api/ontologies/eco/terms"
_OLS_SEARCH = "https://www.ebi.ac.uk/ols4/api/search"
_TIMEOUT    = 120.0
_RETRIES    = 3
_RETRY_DELAY = 2.0  # seconds between retries

# Minimum Solr relevance score to trust the OLS4 top result.
# Scores for a near-exact label match tend to be 10–30+; loose matches are 2–5.
_SCORE_THRESHOLD = 6.0

# ---------------------------------------------------------------------------
# Broad category fallback table
# ---------------------------------------------------------------------------
# Each entry: (list_of_indicator_words, eco_id, eco_label)
# Any single indicator word appearing as a substring of the lowercased assay
# text triggers a match.  More specific categories are listed first.
# ---------------------------------------------------------------------------
_CATEGORY_ECO: list[tuple[list[str], str, str]] = [
    # Electrophysiology
    (
        ["recording", "epsc", "epsp", "current", "capacitance",
         "patch", "clamp", "stimulus", "stimulati", "field potential",
         "mepsc", "mipsc", "evoked", "synaptic transmission"],
        "ECO:0006003",
        "electrophysiology evidence used in manual assertion",
    ),
    # Imaging / microscopy
    (
        ["microscop", "imaging", "confocal", "tirf", "fluorescen",
         "sted", "frap", "live cell", "live-cell", "super-resolution"],
        "ECO:0005027",
        "imaging evidence used in manual assertion",
    ),
    # In vitro biochemistry
    (
        ["in vitro", "cell-free", "recombinant", "reconstitut",
         "liposome", "purified", "cosediment", "pull-down", "pulldown",
         "kinase assay", "enzymatic", "biochemical"],
        "ECO:0000005",
        "enzyme assay evidence",
    ),
    # Genetic loss-of-function
    (
        ["knockout", "knock-out", "null mutant", "deletion mutant",
         "conditional knockout", "loss-of-function", "loss of function"],
        "ECO:0001091",
        "loss-of-function mutant phenotype evidence used in manual assertion",
    ),
    # Genetic gain-of-function
    (
        ["overexpression", "over-expression", "constitutively active",
         "gain-of-function", "gain of function"],
        "ECO:0006055",
        "gain-of-function mutant phenotype evidence used in manual assertion",
    ),
    # Genetic (general / other manipulation)
    (
        ["genetic manipulation", "mutant", "knockdown", "knock-down",
         "rnai", "sirna", "shrna", "morpholino"],
        "ECO:0006054",
        "genetic manipulation evidence used in manual assertion",
    ),
    # Binding / co-purification assays
    (
        ["binding assay", "pull-down", "co-ip", "immunoprecip",
         "cotransfect", "co-transfect", "yeast two-hybrid", "two-hybrid"],
        "ECO:0000024",
        "protein binding evidence used in manual assertion",
    ),
    # Calcium / second-messenger imaging
    (
        ["calcium imaging", "ca2+ imaging", "ca imaging", "uncaging",
         "fluo-4", "fura-2", "gcamp"],
        "ECO:0005027",
        "imaging evidence used in manual assertion",
    ),
]


def match_eco_by_category(assay: str) -> tuple[str | None, str | None]:
    """Match an assay description against broad category indicator words.

    Returns ``(eco_id, eco_label)`` for the first category whose indicator
    word appears anywhere in *assay* (case-insensitive), or
    ``(None, None)`` if no category matches.
    """
    text = assay.lower()
    for indicators, eco_id, eco_label in _CATEGORY_ECO:
        if any(word in text for word in indicators):
            return eco_id, eco_label
    return None, None


# ---------------------------------------------------------------------------
# OLS4 search (primary)
# ---------------------------------------------------------------------------

def search_eco_terms(
    assay_name: str,
    limit: int = 3,
    client: httpx.Client | None = None,
) -> list[dict]:
    """Search OLS4 for ECO terms matching *assay_name*.

    Returns a list of dicts with keys ``eco_id``, ``label``, ``score``.
    Results are ordered by OLS4 relevance score (highest first).
    Returns an empty list on any error or empty input.
    """
    if not assay_name.strip():
        return []

    def _do(c: httpx.Client) -> list[dict]:
        r = c.get(
            _OLS_SEARCH,
            params={
                "q":         assay_name,
                "ontology":  "eco",
                "rows":      limit,
                "fieldList": "short_form,label,score",
            },
            headers={"Accept": "application/json"},
        )
        if not r.is_success:
            return []
        docs = r.json().get("response", {}).get("docs", [])
        results = []
        for d in docs:
            short = d.get("short_form", "")
            if not short.startswith("ECO"):
                continue
            label = d.get("label", "")
            if not label:
                continue
            results.append({
                "eco_id": short.replace("_", ":"),
                "label":  label,
                "score":  float(d.get("score", 0)),
            })
        return results

    try:
        if client:
            return _do(client)
        with httpx.Client(timeout=_TIMEOUT) as c:
            return _do(c)
    except Exception:
        return []


def search_eco_best(
    assay_name: str,
    client: httpx.Client | None = None,
) -> tuple[str | None, str | None]:
    """Return the best OLS4 ECO match for *assay_name* if its score is
    above *_SCORE_THRESHOLD*, otherwise return ``(None, None)``.
    """
    hits = search_eco_terms(assay_name, limit=3, client=client)
    if not hits:
        return None, None
    top = hits[0]
    if top["score"] >= _SCORE_THRESHOLD:
        return top["eco_id"], top["label"]
    return None, None


# ---------------------------------------------------------------------------
# OLS4 term verification (unchanged)
# ---------------------------------------------------------------------------

def _eco_to_iri(eco_code: str) -> str:
    """Convert 'ECO:0000006' → 'http://purl.obolibrary.org/obo/ECO_0000006'."""
    return f"http://purl.obolibrary.org/obo/{eco_code.replace(':', '_')}"


def verify_eco(eco_code: str, client: httpx.Client | None = None) -> dict:
    """Query OLS4 for a single ECO code and return its status and label."""
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
        label: str       = term.get("label", "")
        is_obsolete: bool = term.get("is_obsolete", False)
        return {
            "suggested":     eco_code,
            "status":        "OBSOLETE" if is_obsolete else "VERIFIED",
            "official_label": label,
        }

    last_exc: Exception | None = None
    for attempt in range(_RETRIES):
        try:
            if client:
                return _do(client)
            with httpx.Client(timeout=_TIMEOUT) as c:
                return _do(c)
        except httpx.TimeoutException as exc:
            last_exc = exc
            if attempt < _RETRIES - 1:
                time.sleep(_RETRY_DELAY)
        except Exception as exc:
            return {"suggested": eco_code, "status": "ERROR", "error": str(exc)}
    return {"suggested": eco_code, "status": "TIMEOUT", "error": str(last_exc)}
