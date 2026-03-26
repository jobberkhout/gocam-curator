"""gocam validate — validate all extracted claims against live databases (no AI)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import click
import httpx
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

from gocam.models.claim import (
    EdgeClaim,
    ExtractionFile,
    NodeClaim,
    ValidatedEdgeClaim,
    ValidatedEvidence,
    ValidatedGOTerm,
    ValidatedNodeClaim,
    ValidationReport,
)
from gocam.services.eco import search_eco_terms, verify_eco
from gocam.services.pubmed import resolve_doi_from_title, resolve_pmid_from_doi, verify_pmid
from gocam.services.quickgo import get_protein_annotations, search_go_terms, verify_go_term
from gocam.services.syngo import get_syngo
from gocam.services.uniprot import verify_protein
from gocam.utils.display import console, print_error, print_info, print_success, print_warning
from gocam.utils.io import read_json, write_json
from gocam.utils.process import load_meta, resolve_process

_STATUS_COLOUR = {
    "VERIFIED": "green",
    "FOUND": "green",
    "RESOLVED_FROM_DOI": "cyan",
    "OBSOLETE": "yellow",
    "NOT_FOUND": "red",
    "INVALID": "red",
    "SKIPPED": "dim",
    "NOT_CHECKED": "dim",
    "TIMEOUT": "yellow",
    "ERROR": "red",
}


def _s(status: str) -> str:
    c = _STATUS_COLOUR.get(status, "white")
    return f"[{c}]{status}[/{c}]"


# ---------------------------------------------------------------------------
# GO term lookup: search by label → verify best match
# ---------------------------------------------------------------------------

def _resolve_go_term(
    term: str | None,
    aspect: str,
    http: httpx.Client,
) -> ValidatedGOTerm | None:
    """Search for a GO term by label, verify the best hit."""
    if not term:
        return None

    hits = search_go_terms(term, aspect, limit=5, client=http)
    if not hits:
        return ValidatedGOTerm(term=term, status="NOT_FOUND")

    best = hits[0]
    go_id = best.get("go_id", "")
    vr = verify_go_term(go_id, aspect, client=http)

    return ValidatedGOTerm(
        term=term,
        go_id=go_id,
        status=vr.get("status", "NOT_FOUND"),
        official_label=vr.get("official_label") or best.get("label"),
    )


# ---------------------------------------------------------------------------
# Evidence validation: ECO + PMID + DOI
# ---------------------------------------------------------------------------

def _validate_evidence(
    claim: NodeClaim | EdgeClaim,
    http: httpx.Client,
    source_file: str | None = None,
    source_doi: str | None = None,
    source_pmid: str | None = None,
    doi_pmid_cache: dict[str, str | None] | None = None,
) -> ValidatedEvidence:
    """Validate the evidence fields of a claim.

    source_file:  which extraction file this claim came from (for traceability).
    source_pmid:  PMID extracted from the input filename (curator-controlled,
                  highest-priority fallback).
    source_doi:   DOI of the source paper; used as last-resort PMID fallback.
    doi_pmid_cache: shared dict to avoid re-resolving the same DOI repeatedly.
    """
    if doi_pmid_cache is None:
        doi_pmid_cache = {}

    ev = ValidatedEvidence(
        figure=claim.figure,
        assay=claim.assay_described,
        source_file=source_file,
    )

    # ECO code from assay description
    if claim.assay_described:
        eco_hits = search_eco_terms(claim.assay_described, limit=3, client=http)
        if eco_hits:
            best_eco = eco_hits[0]
            eco_id = best_eco.get("eco_id", "")
            eco_vr = verify_eco(eco_id, client=http)
            ev.eco_code = eco_id
            ev.eco_label = eco_vr.get("official_label") or best_eco.get("label")
            ev.eco_status = eco_vr.get("status", "NOT_FOUND")

    # PMID resolution — priority order:
    # 1. PMID from the input filename (curator-named, e.g. 20357116.pdf) — ground truth
    # 2. Explicit PMID found in the paper text by the LLM
    # 3. PMID resolved from the paper's DOI (automatic, last resort)
    if source_pmid:
        # Curator named the file with its PMID — ground truth, verify and use directly.
        pmid_result = verify_pmid(source_pmid)
        ev.pmid = source_pmid
        ev.pmid_status = pmid_result.get("status", "ERROR")
        ev.pmid_title = pmid_result.get("title")
        ev.doi = pmid_result.get("doi")

    elif claim.pmid_from_text:
        # LLM found a PMID explicitly written in the paper text.
        pmid_result = verify_pmid(claim.pmid_from_text)
        ev.pmid = claim.pmid_from_text
        ev.pmid_status = pmid_result.get("status", "ERROR")
        ev.pmid_title = pmid_result.get("title")
        ev.doi = pmid_result.get("doi")

        # Fallback: resolve DOI from title via CrossRef
        if not ev.doi and ev.pmid_title and ev.pmid_status == "VERIFIED":
            ev.doi = resolve_doi_from_title(ev.pmid_title)

    elif source_doi:
        # No claim-level or filename PMID — resolve from the paper's DOI.
        ev.doi = source_doi
        if source_doi not in doi_pmid_cache:
            doi_pmid_cache[source_doi] = resolve_pmid_from_doi(source_doi)
        resolved_pmid = doi_pmid_cache[source_doi]
        if resolved_pmid:
            pmid_result = verify_pmid(resolved_pmid)
            ev.pmid = resolved_pmid
            ev.pmid_status = "RESOLVED_FROM_DOI"
            ev.pmid_title = pmid_result.get("title")

    return ev


# ---------------------------------------------------------------------------
# Node validation
# ---------------------------------------------------------------------------

def _validate_node(
    claim: NodeClaim,
    species: str,
    protein_cache: dict[str, dict],
    http: httpx.Client,
    source_file: str | None = None,
    source_doi: str | None = None,
    source_pmid: str | None = None,
    doi_pmid_cache: dict[str, str | None] | None = None,
) -> ValidatedNodeClaim:
    """Validate a single node claim against all databases."""
    gene = claim.gene_symbol or ""

    # UniProt lookup (cached by gene_symbol)
    if gene and gene not in protein_cache:
        protein_cache[gene] = verify_protein(gene, species, client=http)
    prot = protein_cache.get(gene, {})

    uniprot_id = prot.get("uniprot_id")
    uniprot_status = prot.get("status", "SKIPPED")

    # GO term resolution
    mf = _resolve_go_term(claim.molecular_function, "molecular_function", http)
    bp = _resolve_go_term(claim.biological_process, "biological_process", http)
    cc = _resolve_go_term(claim.cellular_component, "cellular_component", http)

    # Check existing annotations in QuickGO
    if uniprot_id:
        annotations = get_protein_annotations(uniprot_id, client=http)
        annotated_ids = {a["go_id"] for a in annotations}
        for go_term in (mf, bp, cc):
            if go_term and go_term.go_id and go_term.go_id in annotated_ids:
                go_term.already_annotated = True

    # SynGO check
    syngo_annotations: list[str] = []
    syngo = get_syngo()
    if syngo.available and gene:
        sg = syngo.search_gene(gene)
        if sg.get("found"):
            for ann in sg.get("bp", []) + sg.get("cc", []):
                go_id = ann.get("go_id", "")
                go_name = ann.get("go_name", "")
                if go_id:
                    syngo_annotations.append(f"{go_name} ({go_id})")
            # Check if any of our GO terms are confirmed by SynGO
            for go_term in (mf, bp, cc):
                if go_term and go_term.go_id:
                    sv = syngo.validate_annotation(gene, go_term.go_id)
                    if sv.get("status") == "SYNGO_CONFIRMED":
                        go_term.syngo_confirmed = True

    # Evidence
    evidence = _validate_evidence(claim, http, source_file=source_file, source_doi=source_doi, source_pmid=source_pmid, doi_pmid_cache=doi_pmid_cache)

    return ValidatedNodeClaim(
        id=claim.id,
        protein_name=claim.protein_name,
        gene_symbol=claim.gene_symbol,
        uniprot_id=uniprot_id,
        uniprot_status=uniprot_status,
        molecular_function=mf,
        biological_process=bp,
        cellular_component=cc,
        evidence=evidence,
        confidence=claim.confidence,
        syngo_annotations=syngo_annotations,
        quote=claim.quote,
    )


# ---------------------------------------------------------------------------
# Edge validation
# ---------------------------------------------------------------------------

def _validate_edge(
    claim: EdgeClaim,
    http: httpx.Client,
    source_file: str | None = None,
    source_doi: str | None = None,
    source_pmid: str | None = None,
    doi_pmid_cache: dict[str, str | None] | None = None,
) -> ValidatedEdgeClaim:
    """Validate an edge claim (evidence only — proteins validated via nodes)."""
    evidence = _validate_evidence(claim, http, source_file=source_file, source_doi=source_doi, source_pmid=source_pmid, doi_pmid_cache=doi_pmid_cache)

    return ValidatedEdgeClaim(
        id=claim.id,
        subject=claim.subject,
        relation=claim.relation,
        object=claim.object,
        mechanism=claim.mechanism,
        evidence=evidence,
        confidence=claim.confidence,
        quote=claim.quote,
    )


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def _display_results(report: ValidationReport) -> None:
    """Show a Rich summary of validation results."""
    # Nodes table
    if report.nodes:
        table = Table(title="Validated Nodes", show_lines=False)
        table.add_column("ID", style="dim", no_wrap=True)
        table.add_column("Protein")
        table.add_column("UniProt", justify="center")
        table.add_column("MF", justify="center")
        table.add_column("BP", justify="center")
        table.add_column("CC", justify="center")
        table.add_column("ECO", justify="center")
        table.add_column("PMID", justify="center")

        for n in report.nodes:
            table.add_row(
                n.id,
                n.protein_name,
                _s(n.uniprot_status),
                _s(n.molecular_function.status) if n.molecular_function else "[dim]—[/dim]",
                _s(n.biological_process.status) if n.biological_process else "[dim]—[/dim]",
                _s(n.cellular_component.status) if n.cellular_component else "[dim]—[/dim]",
                _s(n.evidence.eco_status) if n.evidence else "[dim]—[/dim]",
                _s(n.evidence.pmid_status) if n.evidence else "[dim]—[/dim]",
            )
        console.print(table)

    # Edges table
    if report.edges:
        table = Table(title="Validated Edges", show_lines=False)
        table.add_column("ID", style="dim", no_wrap=True)
        table.add_column("Subject")
        table.add_column("Relation")
        table.add_column("Object")
        table.add_column("ECO", justify="center")
        table.add_column("PMID", justify="center")

        for e in report.edges:
            table.add_row(
                e.id,
                e.subject,
                e.relation,
                e.object,
                _s(e.evidence.eco_status) if e.evidence else "[dim]—[/dim]",
                _s(e.evidence.pmid_status) if e.evidence else "[dim]—[/dim]",
            )
        console.print(table)

    # Summary counts
    total_nodes = len(report.nodes)
    total_edges = len(report.edges)

    go_verified = sum(
        1 for n in report.nodes
        for gt in (n.molecular_function, n.biological_process, n.cellular_component)
        if gt and gt.status == "VERIFIED"
    )
    go_total = sum(
        1 for n in report.nodes
        for gt in (n.molecular_function, n.biological_process, n.cellular_component)
        if gt
    )
    eco_verified = sum(
        1 for c in [*report.nodes, *report.edges]
        if c.evidence and c.evidence.eco_status == "VERIFIED"
    )
    pmid_verified = sum(
        1 for c in [*report.nodes, *report.edges]
        if c.evidence and c.evidence.pmid_status in ("VERIFIED", "RESOLVED_FROM_DOI")
    )
    uniprot_found = sum(1 for n in report.nodes if n.uniprot_status == "FOUND")
    syngo_hits = sum(1 for n in report.nodes if n.syngo_annotations)

    console.print()
    grid = Table.grid(padding=(0, 3))
    grid.add_column(style="dim")
    grid.add_column()
    grid.add_row("Total claims", f"{total_nodes} nodes + {total_edges} edges")
    grid.add_row("GO terms verified", f"[green]{go_verified}[/green]/{go_total}")
    grid.add_row("ECO codes verified", f"[green]{eco_verified}[/green]/{total_nodes + total_edges}")
    grid.add_row("PMIDs verified", f"[green]{pmid_verified}[/green]/{total_nodes + total_edges}")
    grid.add_row("UniProt found", f"[green]{uniprot_found}[/green]/{total_nodes}")
    grid.add_row("SynGO matches", f"[magenta]{syngo_hits}[/magenta]/{total_nodes}")
    console.print(grid)


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

@click.command("validate")
@click.option(
    "--process", "-p",
    default=None,
    help="Process name. Auto-detected if there is exactly one process.",
)
def validate_command(process: str | None) -> None:
    """Validate all extracted claims against live databases (no AI).

    Reads every extraction JSON in extractions/, looks up each claim's
    proteins, GO terms, ECO codes, and PMIDs against real databases,
    and saves a fully validated report.

    \b
    DATABASES QUERIED
      UniProt    Protein lookup by gene symbol
      QuickGO    GO term search and verification
      OLS4/EBI   ECO code search and verification
      PubMed     PMID verification + DOI retrieval
      CrossRef   DOI fallback from paper title
      SynGO      Local synaptic gene annotation check

    \b
    OUTPUT
      validation/validated_claims.json   All claims with verified IDs and DOIs

    \b
    EXAMPLES
      gocam validate
      gocam validate -p vesicle-fusion
    """
    process_dir = resolve_process(process)
    meta = load_meta(process_dir)
    species: str = meta.get("species", "")
    process_name: str = meta.get("process_name", process_dir.name)

    extractions_dir = process_dir / "extractions"
    if not extractions_dir.exists():
        print_error("No extractions/ directory found. Run 'gocam extract' first.")
        raise SystemExit(1)

    # Load all extraction JSONs
    json_files = sorted(
        p for p in extractions_dir.glob("*.json")
        if not p.stem.endswith("_summary")
    )
    if not json_files:
        print_error("No extraction JSON files found.")
        raise SystemExit(1)

    # Collect all claims across files, tracking source file, PMID, and DOI per claim
    all_nodes: list[tuple[NodeClaim, str, str | None, str | None]] = []   # (claim, source_file, source_pmid, source_doi)
    all_edges: list[tuple[EdgeClaim, str, str | None, str | None]] = []

    for jf in json_files:
        try:
            data = read_json(jf)
            ext = ExtractionFile.model_validate(data)
            file_pmid = ext.source_pmid
            file_doi = ext.source_doi
            for claim in ext.claims:
                if isinstance(claim, NodeClaim):
                    all_nodes.append((claim, jf.name, file_pmid, file_doi))
                elif isinstance(claim, EdgeClaim):
                    all_edges.append((claim, jf.name, file_pmid, file_doi))
        except Exception as exc:
            print_warning(f"Could not parse {jf.name}: {exc}")

    total = len(all_nodes) + len(all_edges)
    doi_pmid_cache: dict[str, str | None] = {}
    if total == 0:
        print_warning("No claims found in extraction files.")
        raise SystemExit(0)

    console.print(
        f"[bold]Process:[/bold] {process_name}  "
        f"[bold]Claims:[/bold] {len(all_nodes)} nodes + {len(all_edges)} edges "
        f"from {len(json_files)} files"
    )

    # Validate
    validated_nodes: list[ValidatedNodeClaim] = []
    validated_edges: list[ValidatedEdgeClaim] = []
    protein_cache: dict[str, dict] = {}

    with httpx.Client(timeout=15.0) as http, Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task = progress.add_task("Validating...", total=total)

        for node, src_file, src_pmid, src_doi in all_nodes:
            progress.update(task, description=f"[dim]{node.id}[/dim] {node.protein_name}")
            vn = _validate_node(node, species, protein_cache, http, source_file=src_file, source_doi=src_doi, source_pmid=src_pmid, doi_pmid_cache=doi_pmid_cache)
            validated_nodes.append(vn)
            progress.advance(task)

        for edge, src_file, src_pmid, src_doi in all_edges:
            progress.update(task, description=f"[dim]{edge.id}[/dim] {edge.subject}→{edge.object}")
            ve = _validate_edge(edge, http, source_file=src_file, source_doi=src_doi, source_pmid=src_pmid, doi_pmid_cache=doi_pmid_cache)
            validated_edges.append(ve)
            progress.advance(task)

    # Build report
    report = ValidationReport(
        timestamp=datetime.now().isoformat(timespec="seconds"),
        process_name=process_name,
        species=species,
        nodes=validated_nodes,
        edges=validated_edges,
    )

    # Save
    val_dir = process_dir / "validation"
    val_dir.mkdir(exist_ok=True)
    out_path = val_dir / "validated_claims.json"
    write_json(out_path, report)

    _display_results(report)
    print_success(f"Validated claims → {out_path}")
    console.print("\nNext step: [bold]gocam narrative[/bold] — generate expert-readable document")
