"""gocam enrich — discover new literature via PubMed and extract from it.

Enrichment data is kept strictly separate from the main pipeline:
  input/enrichment/          PubMed abstract text files
  extractions/enrichment/    Extraction JSONs for enrichment files
  extractions/enrichment/ENRICHMENT_REPORT.md

The original REPORT.md, records.json, and claims.md are never modified.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import click

from gocam.commands.extract import _process_text
from gocam.config import PROCESSES_DIR
from gocam.services import pubmed as pubmed_svc
from gocam.services.file_processor import FileContent
from gocam.services.llm import get_llm_client
from gocam.services.syngo import get_syngo
from gocam.utils.display import console, print_error, print_info, print_success, print_warning, timed_status
from gocam.utils.io import read_json, write_json
from gocam.utils.process import load_meta

_MAX_PAPERS_DEFAULT = 10
_PUBMED_RETMAX = 5  # results per query


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collect_existing_pmids(process_dir: Path) -> set[str]:
    """Return all PMIDs already in evidence records or extraction JSONs."""
    pmids: set[str] = set()

    # From records.json
    records_path = process_dir / "evidence_records" / "records.json"
    if records_path.exists():
        try:
            data = read_json(records_path)
            for rec in data.get("records", []):
                ev = rec.get("evidence") or {}
                p = ev.get("pmid")
                if p and str(p).strip().isdigit():
                    pmids.add(str(p).strip())
        except Exception:
            pass

    # From extraction JSONs
    ext_dir = process_dir / "extractions"
    if ext_dir.exists():
        for jf in ext_dir.glob("*.json"):
            if jf.stem in ("REPORT",) or jf.stem.endswith("_summary"):
                continue
            try:
                data = read_json(jf)
                for interaction in data.get("interactions", []):
                    p = interaction.get("pmid")
                    if p and str(p).strip().isdigit():
                        pmids.add(str(p).strip())
            except Exception:
                pass

    return pmids


def _build_queries(records_data: dict) -> list[tuple[str, str]]:
    """Build PubMed query strings from evidence records.

    Returns list of (query_string, human_label) tuples.
    Deduplicates and skips records without enough info for a useful query.
    """
    # Words that are too generic to be useful in a PubMed query
    _STOPWORDS = {
        "protein", "activity", "complex", "subunit", "receptor",
        "signaling", "pathway", "regulation", "the", "a", "of", "and",
    }

    seen: set[str] = set()
    queries: list[tuple[str, str]] = []

    for rec in records_data.get("records", []):
        protein = rec.get("protein") or {}
        gene = protein.get("gene_symbol") or protein.get("name") or ""
        gene = gene.strip()

        relation = rec.get("relation_to_target") or {}
        target = relation.get("target", "").strip()

        bp_rel = rec.get("relation_to_process") or {}
        bp = bp_rel.get("target_bp", "").strip()

        if not gene:
            continue

        parts = [gene]
        if target:
            # Keep meaningful words from the target, drop generic filler
            target_words = [
                w for w in target.split()
                if w.lower() not in _STOPWORDS
            ]
            # Use up to the first 3 meaningful words (enough for specificity)
            target_term = " ".join(target_words[:3]) if target_words else ""
            if target_term:
                parts.append(f'"{target_term}"' if " " in target_term else target_term)
        if bp:
            bp_words = [w for w in bp.split() if w.lower() not in _STOPWORDS]
            bp_term = " ".join(bp_words[:3]) if bp_words else ""
            if bp_term:
                parts.append(f'"{bp_term}"' if " " in bp_term else bp_term)

        # Build query — at minimum we need gene
        query = " AND ".join(p for p in parts if p)
        if query in seen:
            continue
        seen.add(query)
        label = f"{gene} → {target}" if target else gene
        queries.append((query, label))

    return queries


def _already_enriched(enrich_ext_dir: Path, pmid: str) -> bool:
    return (enrich_ext_dir / f"pubmed_{pmid}.json").exists()


def _extract_enrichment_file(
    client,
    txt_file: Path,
    enrich_ext_dir: Path,
) -> int:
    """Extract from a single enrichment text file. Returns number of interactions."""
    try:
        content = FileContent(
            source_path=txt_file,
            source_type="text",
            text=txt_file.read_text(encoding="utf-8"),
        )
    except Exception as exc:
        print_warning(f"  Could not read {txt_file.name}: {exc}")
        return 0

    try:
        with timed_status(f"Extracting {txt_file.name}..."):
            extraction = _process_text(client, content)
        out = enrich_ext_dir / f"{txt_file.stem}.json"
        write_json(out, extraction)
        n = len(extraction.interactions)
        print_success(
            f"  {txt_file.name}: {len(extraction.entities)} entities, "
            f"{n} interactions → {out.name}"
        )
        return n
    except Exception as exc:
        print_warning(f"  Extraction failed for {txt_file.name}: {exc}")
        return 0


def _generate_enrichment_report(
    enrich_ext_dir: Path,
    existing_records: dict,
    process_name: str,
) -> Path:
    """Generate ENRICHMENT_REPORT.md comparing new findings against existing records."""
    # Collect existing interaction pairs for matching
    existing_pairs: set[tuple[str, str]] = set()
    for rec in existing_records.get("records", []):
        protein = rec.get("protein") or {}
        gene = (protein.get("gene_symbol") or protein.get("name") or "").lower()
        target = (rec.get("relation_to_target") or {}).get("target", "").lower()
        if gene and target:
            existing_pairs.add((gene, target.split()[0]))

    # Load enrichment extractions
    ext_files = sorted(enrich_ext_dir.glob("pubmed_*.json"))
    if not ext_files:
        return enrich_ext_dir / "ENRICHMENT_REPORT.md"

    lines: list[str] = [
        f"# Enrichment Report — {process_name}",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        f"Sources analysed: {len(ext_files)} PubMed abstract(s)",
        "",
        "---",
        "",
    ]

    total_new = total_confirming = 0

    for ext_file in ext_files:
        pmid = ext_file.stem.replace("pubmed_", "")
        try:
            data = read_json(ext_file)
        except Exception:
            continue

        interactions = data.get("interactions", [])
        entities = data.get("entities", [])
        gaps = data.get("gaps", [])

        lines.append(f"## PMID: {pmid}  ({ext_file.name})")
        lines.append("")
        lines.append(f"Entities extracted: {len(entities)}")
        lines.append(f"Interactions found: {len(interactions)}")
        lines.append("")

        if interactions:
            lines.append("### Interactions")
            lines.append("")
            for ix in interactions:
                src = (ix.get("source_entity") or "").lower()
                tgt = (ix.get("target_entity") or "").lower()
                action = ix.get("described_action", "")
                causal = ix.get("causal_type", "")
                fig = ix.get("figure", "")
                quote = ix.get("quote", "")

                # Check if this matches an existing record
                confirms = any(
                    src and tgt and
                    (src in pair[0] or pair[0] in src) and
                    (tgt.split()[0] in pair[1] or pair[1] in tgt.split()[0])
                    for pair in existing_pairs
                )

                if confirms:
                    tag = "**CONFIRMS** — supports an existing record"
                    total_confirming += 1
                else:
                    tag = "**NEW** — not in original extraction"
                    total_new += 1

                parts = [f"- {ix.get('source_entity')} → {ix.get('target_entity')}"]
                if action:
                    parts[0] += f": {action}"
                if causal:
                    parts[0] += f" ({causal})"
                if fig:
                    parts.append(f"  Figure: {fig}")
                if quote:
                    q = quote[:150] + ("…" if len(quote) > 150 else "")
                    parts.append(f"  Quote: \"{q}\"")
                parts.append(f"  → {tag}")
                lines.extend(parts)
                lines.append("")

        if gaps:
            lines.append("### Gaps / Open Questions")
            for g in gaps[:5]:
                lines.append(f"- {g}")
            lines.append("")

        lines.append("---")
        lines.append("")

    # Summary
    lines.insert(4, f"Summary: {total_new} new interactions, {total_confirming} confirming existing records")
    lines.insert(5, "")

    out = enrich_ext_dir / "ENRICHMENT_REPORT.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

@click.command("enrich")
@click.argument("process_name", metavar="PROCESS")
@click.option(
    "--max-papers",
    default=_MAX_PAPERS_DEFAULT,
    show_default=True,
    type=int,
    help="Maximum number of new PubMed abstracts to add.",
)
@click.option(
    "--queries-only",
    is_flag=True,
    default=False,
    help="Print PubMed queries but do not fetch or extract.",
)
def enrich_command(process_name: str, max_papers: int, queries_only: bool) -> None:
    """Discover additional literature via PubMed and extract from it.

    Builds PubMed queries from existing evidence records, fetches new
    abstracts, extracts interactions, and generates a separate enrichment
    report. The original pipeline outputs (REPORT.md, records.json,
    claims.md) are never modified.

    \b
    SEPARATED OUTPUT PATHS
      input/enrichment/                   PubMed abstract text files
      extractions/enrichment/             Extraction JSONs for enrichment
      extractions/enrichment/ENRICHMENT_REPORT.md

    \b
    RATE LIMITING
      Respects PubMed's policy of max 3 requests/sec by inserting a
      0.4s delay between API calls. No API key required.

    \b
    EXAMPLES
      gocam enrich ampar-endo2
      gocam enrich ampar-endo2 --max-papers 20
      gocam enrich ampar-endo2 --queries-only
    """
    process_dir = PROCESSES_DIR / process_name
    if not process_dir.exists() or not (process_dir / "meta.json").exists():
        print_error(f"Process '{process_name}' not found. Run 'gocam init {process_name}' first.")
        raise SystemExit(1)

    meta = load_meta(process_dir)
    display_name = meta.get("process_name", process_name)

    records_path = process_dir / "evidence_records" / "records.json"
    if not records_path.exists():
        print_error(
            "No evidence records found. Run 'gocam translate' first to generate records.json."
        )
        raise SystemExit(1)

    try:
        records_data = read_json(records_path)
    except Exception as exc:
        print_error(f"Could not read records.json: {exc}")
        raise SystemExit(1)

    console.print(f"[bold]Process:[/bold] {display_name}")

    # Build queries
    queries = _build_queries(records_data)
    if not queries:
        print_warning("No interactions found in records.json — cannot build PubMed queries.")
        raise SystemExit(1)

    console.print(f"[bold]PubMed queries:[/bold] {len(queries)}")
    for q, label in queries:
        console.print(f"  [dim]{label}:[/dim] {q}")

    if queries_only:
        return

    # Collect existing PMIDs to filter
    existing_pmids = _collect_existing_pmids(process_dir)
    print_info(f"Already have {len(existing_pmids)} PMID(s) in this process")

    # --- SynGO priority pass -------------------------------------------
    # Check SynGO for PMIDs associated with each gene before querying PubMed.
    # These are expert-curated references and are treated as priority sources.
    syngo = get_syngo()
    syngo_pmids: dict[str, str] = {}  # pmid -> gene label
    if syngo.available:
        console.print("\n[bold magenta]Checking SynGO for expert-curated references…[/bold magenta]")
        genes_seen: set[str] = set()
        for rec in records_data.get("records", []):
            protein = rec.get("protein") or {}
            gene = (protein.get("gene_symbol") or protein.get("name") or "").strip()
            if not gene or gene in genes_seen:
                continue
            genes_seen.add(gene)
            pmids = syngo.get_pmids_for_gene(gene)
            new = [p for p in pmids if p not in existing_pmids]
            if new:
                print_info(f"  {gene}: {len(new)} SynGO PMID(s) found")
                for p in new:
                    syngo_pmids[p] = f"{gene} (SynGO)"
        if syngo_pmids:
            print_success(
                f"SynGO contributed {len(syngo_pmids)} unique reference(s) as priority sources."
            )
        else:
            print_info("No new SynGO references found (all already in process or gene not in SynGO).")
    # ------------------------------------------------------------------

    # Search PubMed
    console.print("\n[bold]Searching PubMed…[/bold]")
    found_pmids: set[str] = set()
    for query, label in queries:
        pmids = pubmed_svc.search(query, retmax=_PUBMED_RETMAX)
        new = [p for p in pmids if p not in existing_pmids and p not in found_pmids]
        found_pmids.update(new)
        status = f"  {label}: {len(pmids)} hits, {len(new)} new"
        print_info(status)

        if len(found_pmids) >= max_papers:
            print_info(f"Reached --max-papers limit ({max_papers}). Stopping search.")
            break

    # Merge SynGO PMIDs (priority) with PubMed results — SynGO first
    all_new_pmids: list[str] = []
    seen_merged: set[str] = set()
    for p in sorted(syngo_pmids.keys()):   # SynGO first
        if p not in seen_merged:
            all_new_pmids.append(p)
            seen_merged.add(p)
    for p in sorted(found_pmids):          # then PubMed
        if p not in seen_merged:
            all_new_pmids.append(p)
            seen_merged.add(p)

    pmids_to_fetch = all_new_pmids[:max_papers]

    print_info(
        f"Found {len(found_pmids)} new PubMed paper(s) + {len(syngo_pmids)} SynGO reference(s). "
        f"Fetching {len(pmids_to_fetch)} abstract(s) (limit: {max_papers})."
    )

    if not pmids_to_fetch:
        print_warning("No new papers found. Enrichment complete (nothing to add).")
        return

    # Create enrichment directories
    enrich_input_dir = process_dir / "input" / "enrichment"
    enrich_ext_dir = process_dir / "extractions" / "enrichment"
    enrich_input_dir.mkdir(parents=True, exist_ok=True)
    enrich_ext_dir.mkdir(parents=True, exist_ok=True)

    # Fetch and save abstracts
    console.print(f"\n[bold]Fetching {len(pmids_to_fetch)} abstract(s)…[/bold]")
    saved_files: list[Path] = []
    for pmid in pmids_to_fetch:
        out = enrich_input_dir / f"pubmed_{pmid}.txt"
        if out.exists():
            print_info(f"  Already downloaded: {out.name}")
            saved_files.append(out)
            continue

        abstract = pubmed_svc.fetch_abstract(pmid)
        if not abstract.strip():
            print_warning(f"  PMID {pmid}: empty abstract, skipping")
            continue

        # Prepend provenance header so the extraction LLM and curator can see the source
        source_label = syngo_pmids.get(pmid)
        if source_label:
            header = f"[Source: SynGO (expert-curated) — {source_label}]\n\n"
        else:
            header = ""
        out.write_text(header + abstract, encoding="utf-8")
        tag = " [SynGO]" if source_label else ""
        print_success(f"  Saved PMID {pmid}{tag} → {out.name}")
        saved_files.append(out)

    if not saved_files:
        print_warning("No abstracts could be downloaded.")
        return

    # Extract from enrichment files
    console.print(f"\n[bold]Extracting from {len(saved_files)} enrichment file(s)…[/bold]")
    already_done = sum(
        1 for f in saved_files
        if _already_enriched(enrich_ext_dir, f.stem.replace("pubmed_", ""))
    )
    if already_done:
        print_info(
            f"Resuming — {already_done}/{len(saved_files)} abstract(s) already extracted, "
            f"{len(saved_files) - already_done} remaining"
        )

    client = get_llm_client()
    total_interactions = 0

    for txt_file in saved_files:
        pmid = txt_file.stem.replace("pubmed_", "")
        if _already_enriched(enrich_ext_dir, pmid):
            print_info(f"  {txt_file.name}: already extracted, skipping")
            continue
        n = _extract_enrichment_file(client, txt_file, enrich_ext_dir)
        total_interactions += n

    # Generate enrichment report
    console.print("\n[bold]Generating enrichment report…[/bold]")
    report_path = _generate_enrichment_report(enrich_ext_dir, records_data, display_name)
    print_success(f"Enrichment report → {report_path}")

    console.print()
    print_success(
        f"Enrichment complete: {len(pmids_to_fetch)} new paper(s), "
        f"{total_interactions} interaction(s) found."
    )
    console.print(
        "\n[dim]Review[/dim] [bold]extractions/enrichment/ENRICHMENT_REPORT.md[/bold] "
        "[dim]and manually promote findings to the main pipeline if appropriate.[/dim]"
    )
