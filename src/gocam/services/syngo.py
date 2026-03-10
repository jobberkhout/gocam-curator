"""SynGO local database service.

Loads three Excel files from data/syngo/ and provides gene/GO-term lookups.
All methods return gracefully if the data files are not present — the rest of
the pipeline continues without SynGO support and simply logs a one-time notice.

Data files (download from https://syngoportal.org):
  data/syngo/genes.xlsx           gene info (hgnc_symbol, hgnc_synonyms, …)
  data/syngo/annotations.xlsx     curated annotations (symbol, go_id, evidence, …)
  data/syngo/ontologies.xlsx      GO term hierarchy with associated genes
"""

from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path

from gocam.config import PROJECT_ROOT

_log = logging.getLogger(__name__)

SYNGO_DATA_DIR: Path = PROJECT_ROOT / "data" / "syngo"

# Expected column names (lower-cased for matching)
_GENE_COLS = ("hgnc_symbol", "hgnc_synonyms", "ensembl_id", "entrez_id")
_ANN_COLS = (
    "hgnc_symbol", "uniprot_id", "pubmed_id", "go_id", "go_name", "go_domain",
    "evidence_biological_system", "evidence_protein_targeting", "evidence_experiment_assay",
)


def _read_xlsx(path: Path) -> tuple[list[str], list[list]]:
    """Read an Excel file with openpyxl. Returns (headers, rows)."""
    import openpyxl  # lazy import — only needed when SynGO data is present

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if not rows:
        return [], []

    raw_headers = rows[0]
    headers = [str(h).strip().lower() if h is not None else "" for h in raw_headers]
    return headers, rows[1:]


def _col(headers: list[str], name: str) -> int:
    """Return column index for a header name, or -1 if not found."""
    try:
        return headers.index(name)
    except ValueError:
        # Try partial match
        for i, h in enumerate(headers):
            if name in h:
                return i
        return -1


class SynGOService:
    """Local SynGO database.

    Lazy-loads Excel files on first use. All public methods are safe to call
    even when data files are absent — they return empty results and set
    ``available = False``.
    """

    def __init__(self) -> None:
        self._loaded = False
        self._available = False
        self._notice_shown = False

        self._annotations: list[dict] = []
        self._by_symbol: dict[str, list[dict]] = defaultdict(list)
        self._by_go_id: dict[str, list[dict]] = defaultdict(list)
        self._synonym_map: dict[str, str] = {}  # lowercase → canonical HGNC symbol

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True

        ann_path = SYNGO_DATA_DIR / "annotations.xlsx"
        genes_path = SYNGO_DATA_DIR / "genes.xlsx"

        if not ann_path.exists():
            if not self._notice_shown:
                _log.debug(
                    "SynGO annotations.xlsx not found in %s — SynGO features disabled. "
                    "Download from https://syngoportal.org and place in data/syngo/.",
                    SYNGO_DATA_DIR,
                )
                self._notice_shown = True
            return

        try:
            if genes_path.exists():
                self._load_genes(genes_path)
        except Exception as exc:
            _log.debug("SynGO genes.xlsx could not be loaded: %s", exc)

        try:
            self._load_annotations(ann_path)
            self._available = True
        except Exception as exc:
            _log.debug("SynGO annotations.xlsx could not be loaded: %s", exc)

    def _load_genes(self, path: Path) -> None:
        headers, rows = _read_xlsx(path)
        sym_col = _col(headers, "hgnc_symbol")
        syn_col = _col(headers, "hgnc_synonyms")

        for row in rows:
            symbol = row[sym_col] if sym_col >= 0 and sym_col < len(row) else None
            if not symbol:
                continue
            symbol = str(symbol).strip()
            self._synonym_map[symbol.lower()] = symbol  # self-map

            if syn_col >= 0 and syn_col < len(row) and row[syn_col]:
                for syn in str(row[syn_col]).split("|"):
                    s = syn.strip()
                    if s:
                        self._synonym_map[s.lower()] = symbol

    def _load_annotations(self, path: Path) -> None:
        headers, rows = _read_xlsx(path)
        sym_col = _col(headers, "hgnc_symbol")
        go_col = _col(headers, "go_id")

        for row in rows:
            ann = {
                headers[i]: (str(v).strip() if v is not None else "")
                for i, v in enumerate(row)
                if i < len(headers)
            }
            symbol = ann.get("hgnc_symbol", "").strip()
            go_id = ann.get("go_id", "").strip()
            if not symbol or not go_id:
                continue
            self._annotations.append(ann)
            # Add self-map for symbol
            if symbol.lower() not in self._synonym_map:
                self._synonym_map[symbol.lower()] = symbol
            self._by_symbol[symbol.lower()].append(ann)
            self._by_go_id[go_id].append(ann)

    # ------------------------------------------------------------------
    # Symbol resolution
    # ------------------------------------------------------------------

    def _resolve(self, symbol: str) -> str:
        """Resolve a gene symbol to canonical HGNC form (case-insensitive)."""
        return self._synonym_map.get(symbol.strip().lower(), symbol.strip())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        self._ensure_loaded()
        return self._available

    def search_gene(self, symbol: str) -> dict:
        """Return all SynGO annotations for a gene, grouped by BP and CC.

        Returns:
            dict with keys: available, found, symbol, bp (list), cc (list), total
        """
        self._ensure_loaded()
        if not self._available:
            return {"available": False}

        canonical = self._resolve(symbol)
        annotations = self._by_symbol.get(canonical.lower(), [])

        if not annotations:
            return {"available": True, "found": False, "symbol": symbol, "canonical": canonical}

        bp = [
            a for a in annotations
            if "biological" in a.get("go_domain", "").lower()
            or a.get("go_domain", "").upper() in ("BP", "BIOLOGICAL PROCESS")
        ]
        cc = [
            a for a in annotations
            if "cellular" in a.get("go_domain", "").lower()
            or a.get("go_domain", "").upper() in ("CC", "CELLULAR COMPONENT")
        ]

        return {
            "available": True,
            "found": True,
            "symbol": canonical,
            "bp": bp,
            "cc": cc,
            "total": len(annotations),
        }

    def get_annotations_for_go_term(self, go_id: str) -> list[dict]:
        """Return all SynGO annotations for a given GO ID."""
        self._ensure_loaded()
        return list(self._by_go_id.get(go_id.strip(), []))

    def get_pmids_for_gene(self, symbol: str) -> list[str]:
        """Return all PMIDs associated with a gene in SynGO, deduplicated."""
        self._ensure_loaded()
        if not self._available:
            return []
        canonical = self._resolve(symbol)
        annotations = self._by_symbol.get(canonical.lower(), [])
        pmids: list[str] = []
        seen: set[str] = set()
        for a in annotations:
            p = str(a.get("pubmed_id", "")).strip()
            if p and p.isdigit() and p not in seen:
                pmids.append(p)
                seen.add(p)
        return pmids

    def validate_annotation(self, symbol: str, go_id: str) -> dict:
        """Check if a gene–GO combination exists in SynGO.

        Returns a dict with status:
          UNAVAILABLE         SynGO data files not loaded
          GENE_NOT_IN_SYNGO   Gene not found in SynGO at all
          SYNGO_CONFIRMED     Exact gene + GO ID match found
          SYNGO_ALTERNATIVE   Gene in SynGO but annotated to different GO term(s)
        """
        self._ensure_loaded()
        if not self._available:
            return {"status": "UNAVAILABLE"}

        canonical = self._resolve(symbol)
        gene_anns = self._by_symbol.get(canonical.lower(), [])

        if not gene_anns:
            return {"status": "GENE_NOT_IN_SYNGO", "symbol": canonical}

        # Exact GO ID match
        matches = [a for a in gene_anns if a.get("go_id") == go_id.strip()]
        if matches:
            evidence = []
            seen_pmids: set[str] = set()
            for a in matches:
                pmid = str(a.get("pubmed_id", "")).strip()
                if pmid in seen_pmids:
                    continue
                seen_pmids.add(pmid)
                evidence.append({
                    "biological_system": a.get("evidence_biological_system", ""),
                    "protein_targeting": a.get("evidence_protein_targeting", ""),
                    "assay": a.get("evidence_experiment_assay", ""),
                    "pmid": pmid,
                })
            return {
                "status": "SYNGO_CONFIRMED",
                "symbol": canonical,
                "go_id": go_id,
                "go_name": matches[0].get("go_name", ""),
                "evidence": evidence,
            }

        # Gene in SynGO but different GO terms
        seen_ids: set[str] = set()
        alternatives: list[dict] = []
        for a in gene_anns:
            gid = a.get("go_id", "")
            if gid and gid not in seen_ids:
                seen_ids.add(gid)
                alternatives.append({"go_id": gid, "go_name": a.get("go_name", "")})

        return {
            "status": "SYNGO_ALTERNATIVE",
            "symbol": canonical,
            "alternatives": alternatives[:10],
        }


# Singleton — one instance per process, loaded once on first use
_service = SynGOService()


def get_syngo() -> SynGOService:
    """Return the shared SynGO service instance."""
    return _service
