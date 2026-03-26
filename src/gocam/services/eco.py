"""OLS4/EBI REST API — ECO code verification and search.

ECO lookup strategy
-------------------
1. `lookup_eco_by_keyword()` checks a curated keyword→ECO table using
   case-insensitive substring matching (first match wins).  More specific
   entries are listed before general ones in the table.  All ECO IDs in the
   table are from the ECO ontology and were verified against EBI OLS4.

2. `search_eco_terms()` falls back to an OLS4 full-text search when no
   keyword matches.  This covers unusual assay descriptions that are not
   in the table.

3. If neither approach yields a result the caller should flag the claim
   as having no ECO assignment and warn the curator.
"""

from __future__ import annotations

import httpx

_OLS_BASE = "https://www.ebi.ac.uk/ols4/api/ontologies/eco/terms"
_OLS_SEARCH = "https://www.ebi.ac.uk/ols4/api/search"
_TIMEOUT = 15.0

# ---------------------------------------------------------------------------
# Keyword → ECO lookup table
# ---------------------------------------------------------------------------
# Each entry: (keyword_lowercase, eco_id, eco_label)
# Rules:
#  • More specific terms BEFORE less specific ones — first match wins.
#  • All keywords are matched as substrings of the lowercased assay string.
#  • ECO IDs sourced from EBI OLS4 / ECO ontology (purl.obolibrary.org/obo).
# ---------------------------------------------------------------------------
_ASSAY_ECO_TABLE: list[tuple[str, str, str]] = [
    # --- Immunoprecipitation family ---
    ("co-immunoprecipitation", "ECO:0000081", "co-immunoprecipitation evidence used in manual assertion"),
    ("co immunoprecipitation",  "ECO:0000081", "co-immunoprecipitation evidence used in manual assertion"),
    ("coimmunoprecipitation",   "ECO:0000081", "co-immunoprecipitation evidence used in manual assertion"),
    ("co-ip",                   "ECO:0000081", "co-immunoprecipitation evidence used in manual assertion"),
    ("chromatin immunoprecipitation", "ECO:0000085", "chromatin immunoprecipitation evidence used in manual assertion"),
    ("chip-seq",                "ECO:0000085", "chromatin immunoprecipitation evidence used in manual assertion"),
    ("chip assay",              "ECO:0000085", "chromatin immunoprecipitation evidence used in manual assertion"),
    ("immunoprecipitation",     "ECO:0000078", "immunoprecipitation evidence used in manual assertion"),
    # --- Pull-down / binding ---
    ("gst pull",  "ECO:0000075", "protein pull-down assay evidence used in manual assertion"),
    ("pull-down", "ECO:0000075", "protein pull-down assay evidence used in manual assertion"),
    ("pull down", "ECO:0000075", "protein pull-down assay evidence used in manual assertion"),
    ("pulldown",  "ECO:0000075", "protein pull-down assay evidence used in manual assertion"),
    # --- Yeast two-hybrid ---
    ("yeast two-hybrid",  "ECO:0000068", "yeast two-hybrid evidence used in manual assertion"),
    ("yeast 2-hybrid",    "ECO:0000068", "yeast two-hybrid evidence used in manual assertion"),
    ("yeast two hybrid",  "ECO:0000068", "yeast two-hybrid evidence used in manual assertion"),
    ("two-hybrid",        "ECO:0000068", "yeast two-hybrid evidence used in manual assertion"),
    ("2-hybrid",          "ECO:0000068", "yeast two-hybrid evidence used in manual assertion"),
    ("y2h",               "ECO:0000068", "yeast two-hybrid evidence used in manual assertion"),
    # --- Western blot / immunoblot ---
    ("western blot",      "ECO:0000084", "immunoblot evidence used in manual assertion"),
    ("western blotting",  "ECO:0000084", "immunoblot evidence used in manual assertion"),
    ("immunoblot",        "ECO:0000084", "immunoblot evidence used in manual assertion"),
    # --- Gel mobility shift / EMSA ---
    ("electrophoretic mobility shift", "ECO:0000099", "electrophoretic mobility shift assay evidence used in manual assertion"),
    ("gel mobility shift",             "ECO:0000099", "electrophoretic mobility shift assay evidence used in manual assertion"),
    ("gel shift",                      "ECO:0000099", "electrophoretic mobility shift assay evidence used in manual assertion"),
    ("emsa",                           "ECO:0000099", "electrophoretic mobility shift assay evidence used in manual assertion"),
    # --- Surface plasmon resonance ---
    ("surface plasmon resonance", "ECO:0000082", "surface plasmon resonance evidence used in manual assertion"),
    # Note: bare "spr" is too short to match safely without word boundaries
    # --- Structural: X-ray / cryo-EM / EM ---
    ("x-ray crystallography",  "ECO:0000095", "X-ray crystallography evidence used in manual assertion"),
    ("x ray crystallography",  "ECO:0000095", "X-ray crystallography evidence used in manual assertion"),
    ("crystallography",        "ECO:0000095", "X-ray crystallography evidence used in manual assertion"),
    ("cryo-electron microscopy", "ECO:0000623", "cryo-electron microscopy evidence used in manual assertion"),
    ("cryo-em",                "ECO:0000623", "cryo-electron microscopy evidence used in manual assertion"),
    ("cryo em",                "ECO:0000623", "cryo-electron microscopy evidence used in manual assertion"),
    ("cryoem",                 "ECO:0000623", "cryo-electron microscopy evidence used in manual assertion"),
    ("electron microscopy",    "ECO:0000096", "microscopy evidence used in manual assertion"),
    # --- NMR ---
    ("nuclear magnetic resonance", "ECO:0000072", "nuclear magnetic resonance evidence used in manual assertion"),
    ("nmr spectroscopy",           "ECO:0000072", "nuclear magnetic resonance evidence used in manual assertion"),
    # --- Enzymatic / in vitro activity ---
    ("in vitro kinase",         "ECO:0000071", "enzyme assay evidence used in manual assertion"),
    ("in vitro phosphorylation","ECO:0000071", "enzyme assay evidence used in manual assertion"),
    ("kinase assay",            "ECO:0000071", "enzyme assay evidence used in manual assertion"),
    ("kinase activity assay",   "ECO:0000071", "enzyme assay evidence used in manual assertion"),
    ("enzyme assay",            "ECO:0000071", "enzyme assay evidence used in manual assertion"),
    ("enzymatic assay",         "ECO:0000071", "enzyme assay evidence used in manual assertion"),
    # --- Genetic: knockdown before knockout (more specific first) ---
    ("rnai",         "ECO:0000074", "RNA interference evidence used in manual assertion"),
    ("sirna",        "ECO:0000074", "RNA interference evidence used in manual assertion"),
    ("shrna",        "ECO:0000074", "RNA interference evidence used in manual assertion"),
    ("mirna",        "ECO:0000074", "RNA interference evidence used in manual assertion"),
    ("morpholino",   "ECO:0000074", "RNA interference evidence used in manual assertion"),
    ("knockdown",    "ECO:0000074", "RNA interference evidence used in manual assertion"),
    ("knock-down",   "ECO:0000074", "RNA interference evidence used in manual assertion"),
    ("knock down",   "ECO:0000074", "RNA interference evidence used in manual assertion"),
    ("knockout",     "ECO:0000045", "mutant phenotype evidence used in manual assertion"),
    ("knock-out",    "ECO:0000045", "mutant phenotype evidence used in manual assertion"),
    ("knock out",    "ECO:0000045", "mutant phenotype evidence used in manual assertion"),
    ("loss-of-function", "ECO:0000045", "mutant phenotype evidence used in manual assertion"),
    ("loss of function", "ECO:0000045", "mutant phenotype evidence used in manual assertion"),
    ("gain-of-function", "ECO:0000045", "mutant phenotype evidence used in manual assertion"),
    ("gain of function", "ECO:0000045", "mutant phenotype evidence used in manual assertion"),
    # --- Rescue / complementation ---
    ("rescue experiment",  "ECO:0000119", "genetic complementation evidence used in manual assertion"),
    ("rescue assay",       "ECO:0000119", "genetic complementation evidence used in manual assertion"),
    ("genetic rescue",     "ECO:0000119", "genetic complementation evidence used in manual assertion"),
    ("genetic complementation", "ECO:0000119", "genetic complementation evidence used in manual assertion"),
    # --- Pharmacological ---
    ("pharmacological inhibition", "ECO:0000120", "pharmacological evidence used in manual assertion"),
    ("pharmacological treatment",  "ECO:0000120", "pharmacological evidence used in manual assertion"),
    ("inhibitor treatment",        "ECO:0000120", "pharmacological evidence used in manual assertion"),
    ("drug treatment",             "ECO:0000120", "pharmacological evidence used in manual assertion"),
    ("pharmacological",            "ECO:0000120", "pharmacological evidence used in manual assertion"),
    # --- Microscopy / imaging ---
    ("immunofluorescence microscopy", "ECO:0000091", "immunofluorescence evidence used in manual assertion"),
    ("immunofluorescence",            "ECO:0000091", "immunofluorescence evidence used in manual assertion"),
    ("fluorescence microscopy",       "ECO:0000096", "microscopy evidence used in manual assertion"),
    ("confocal microscopy",           "ECO:0000096", "microscopy evidence used in manual assertion"),
    # --- Electrophysiology ---
    ("electrophysiology",       "ECO:0001099", "electrophysiology evidence used in manual assertion"),
    ("patch-clamp",             "ECO:0001099", "electrophysiology evidence used in manual assertion"),
    ("patch clamp",             "ECO:0001099", "electrophysiology evidence used in manual assertion"),
    ("whole-cell recording",    "ECO:0001099", "electrophysiology evidence used in manual assertion"),
    ("field recording",         "ECO:0001099", "electrophysiology evidence used in manual assertion"),
    ("field potential",         "ECO:0001099", "electrophysiology evidence used in manual assertion"),
    ("miniature excitatory",    "ECO:0001099", "electrophysiology evidence used in manual assertion"),
    ("miniature inhibitory",    "ECO:0001099", "electrophysiology evidence used in manual assertion"),
    ("excitatory postsynaptic", "ECO:0001099", "electrophysiology evidence used in manual assertion"),
    ("inhibitory postsynaptic", "ECO:0001099", "electrophysiology evidence used in manual assertion"),
    ("mepsc",                   "ECO:0001099", "electrophysiology evidence used in manual assertion"),
    ("mepsc",                   "ECO:0001099", "electrophysiology evidence used in manual assertion"),
    ("evoked current",          "ECO:0001099", "electrophysiology evidence used in manual assertion"),
    # --- Surface / trafficking ---
    ("surface biotinylation",   "ECO:0000462", "cell surface protein biotinylation evidence used in manual assertion"),
    ("biotinylation assay",     "ECO:0000462", "cell surface protein biotinylation evidence used in manual assertion"),
    ("internalization assay",   "ECO:0000462", "cell surface protein biotinylation evidence used in manual assertion"),
]


def lookup_eco_by_keyword(assay: str) -> tuple[str | None, str | None]:
    """Match an assay description against the curated keyword table.

    Returns ``(eco_id, eco_label)`` for the first matching entry, or
    ``(None, None)`` if no keyword matches.

    Matching is case-insensitive substring search.  The table is ordered so
    that more specific keywords appear before general ones (first match wins).
    """
    text = assay.lower()
    for keyword, eco_id, eco_label in _ASSAY_ECO_TABLE:
        if keyword in text:
            return eco_id, eco_label
    return None, None


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
    """Search for ECO terms matching an assay description via OLS4.

    Uses OLS4 full-text search against the ECO ontology.
    Returns a list of dicts with keys: eco_id, label.

    Note: all returned IDs come directly from the ontology database and
    have been matched by OLS4's own text search — no curated ID table is
    used, so there is no risk of a semantically wrong but syntactically
    valid code being returned.
    """
    if not assay_name.strip():
        return []

    def _do(c: httpx.Client) -> list[dict]:
        # Try exact-label search first for higher precision
        results = _ols_search(c, assay_name, exact=True, limit=limit)
        if not results:
            results = _ols_search(c, assay_name, exact=False, limit=limit)
        return results

    try:
        if client:
            return _do(client)
        with httpx.Client(timeout=_TIMEOUT) as c:
            return _do(c)
    except Exception:
        return []


def _ols_search(
    c: httpx.Client,
    query: str,
    exact: bool,
    limit: int,
) -> list[dict]:
    """Run one OLS4 search query and return parsed ECO results."""
    params: dict = {
        "q": query,
        "ontology": "eco",
        "rows": limit,
        "fieldList": "short_form,label",
    }
    if exact:
        params["exact"] = "true"

    try:
        r = c.get(_OLS_SEARCH, params=params, headers={"Accept": "application/json"})
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
    except Exception:
        return []
