"""gocam verify — check all GO/ECO/UniProt IDs against live databases (no AI)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import click
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

from gocam.models.evidence import EvidenceRecordsFile
from gocam.models.verification import (
    ECOVerification,
    GOTermVerification,
    RecordVerification,
    UniProtVerification,
    VerificationReport,
    VerificationSummary,
)
from gocam.services.eco import search_eco_terms, verify_eco
from gocam.services.quickgo import get_protein_annotations, search_go_terms, verify_go_term
from gocam.services.uniprot import verify_protein
from gocam.utils.display import console, print_error, print_info, print_success, print_warning
from gocam.utils.io import read_json, write_json
from gocam.utils.process import load_meta, resolve_process

_STATUS_STYLE = {
    "VERIFIED": "green",
    "FOUND": "green",
    "OBSOLETE": "yellow",
    "NOT_FOUND": "red",
    "SKIPPED": "dim",
    "TIMEOUT": "yellow",
    "ERROR": "red",
}


def _style(status: str) -> str:
    colour = _STATUS_STYLE.get(status, "white")
    return f"[{colour}]{status}[/{colour}]"


def _label_match(suggested_term: str | None, official_label: str | None) -> bool | None:
    if not suggested_term or not official_label:
        return None
    return suggested_term.strip().lower() == official_label.strip().lower()


def _enrich_with_suggestions(
    go_result: GOTermVerification,
    suggested_term: str | None,
    aspect: str,
) -> None:
    """If label or aspect mismatches, search QuickGO for better alternatives."""
    needs_search = go_result.label_match is False or go_result.aspect_match is False
    if not needs_search or not suggested_term:
        return
    go_result.alternative_suggestions = search_go_terms(suggested_term, aspect)


def _verify_record(record, species: str) -> RecordVerification:
    rv = RecordVerification(record_id=record.id)
    protein = record.protein
    gene_symbol: str = protein.get("gene_symbol") or ""

    # GO Molecular Function
    if record.molecular_function:
        raw = verify_go_term(record.molecular_function.go_id, "molecular_function")
        rv.go_mf = GOTermVerification.model_validate(raw)
        if rv.go_mf.status == "VERIFIED":
            rv.go_mf.label_match = _label_match(
                record.molecular_function.term, rv.go_mf.official_label
            )
        _enrich_with_suggestions(rv.go_mf, record.molecular_function.term, "molecular_function")

    # GO Biological Process
    if record.biological_process:
        raw = verify_go_term(record.biological_process.go_id, "biological_process")
        rv.go_bp = GOTermVerification.model_validate(raw)
        if rv.go_bp.status == "VERIFIED":
            rv.go_bp.label_match = _label_match(
                record.biological_process.term, rv.go_bp.official_label
            )
        _enrich_with_suggestions(rv.go_bp, record.biological_process.term, "biological_process")

    # GO Cellular Component
    if record.cellular_component:
        raw = verify_go_term(record.cellular_component.go_id, "cellular_component")
        rv.go_cc = GOTermVerification.model_validate(raw)
        if rv.go_cc.status == "VERIFIED":
            rv.go_cc.label_match = _label_match(
                record.cellular_component.term, rv.go_cc.official_label
            )
        _enrich_with_suggestions(rv.go_cc, record.cellular_component.term, "cellular_component")

    # UniProt — also fetches QuickGO annotations and cross-references GO terms
    if gene_symbol:
        raw = verify_protein(gene_symbol, species)
        rv.uniprot = UniProtVerification.model_validate(raw)

        if rv.uniprot.status == "FOUND" and rv.uniprot.uniprot_id:
            rv.uniprot.quickgo_annotations = get_protein_annotations(rv.uniprot.uniprot_id)
            annotated_ids = {ann["go_id"] for ann in rv.uniprot.quickgo_annotations}

            # Mark GO terms that are already confirmed in QuickGO for this protein
            for go_field, go_record in [
                (rv.go_mf, record.molecular_function),
                (rv.go_bp, record.biological_process),
                (rv.go_cc, record.cellular_component),
            ]:
                if go_field and go_record and go_record.go_id in annotated_ids:
                    go_field.already_annotated = True

    # ECO — if UNKNOWN, search OLS4 by assay name
    if record.evidence:
        raw = verify_eco(record.evidence.eco_code)
        rv.eco = ECOVerification.model_validate(raw)
        if rv.eco.status == "SKIPPED":
            assay = (record.evidence.assay or record.evidence.eco_label or "").strip()
            if assay:
                rv.eco.eco_suggestions = search_eco_terms(assay)

    return rv


def _build_summary(details: list[RecordVerification]) -> VerificationSummary:
    go_verified = go_failed = go_obsolete = go_skipped = go_already_annotated = 0
    uniprot_confirmed = eco_verified = 0

    for rv in details:
        for go_field in (rv.go_mf, rv.go_bp, rv.go_cc):
            if go_field is None:
                continue
            s = go_field.status
            if s == "VERIFIED":
                go_verified += 1
            elif s == "OBSOLETE":
                go_obsolete += 1
            elif s == "SKIPPED":
                go_skipped += 1
            else:
                go_failed += 1
            if go_field.already_annotated:
                go_already_annotated += 1

        if rv.uniprot and rv.uniprot.status == "FOUND":
            uniprot_confirmed += 1

        if rv.eco and rv.eco.status == "VERIFIED":
            eco_verified += 1

    return VerificationSummary(
        total_records=len(details),
        go_terms_verified=go_verified,
        go_terms_failed=go_failed,
        go_terms_obsolete=go_obsolete,
        go_terms_skipped=go_skipped,
        go_terms_already_annotated=go_already_annotated,
        uniprot_confirmed=uniprot_confirmed,
        eco_verified=eco_verified,
    )


def _update_records(records_file: EvidenceRecordsFile, details: list[RecordVerification]) -> None:
    """Set verified=True and fill UniProt IDs in-place on the records model."""
    detail_map = {rv.record_id: rv for rv in details}

    for record in records_file.records:
        rv = detail_map.get(record.id)
        if not rv:
            continue

        if rv.go_mf and (rv.go_mf.status == "VERIFIED" or rv.go_mf.already_annotated) and record.molecular_function:
            record.molecular_function.verified = True

        if rv.go_bp and (rv.go_bp.status == "VERIFIED" or rv.go_bp.already_annotated) and record.biological_process:
            record.biological_process.verified = True

        if rv.go_cc and (rv.go_cc.status == "VERIFIED" or rv.go_cc.already_annotated) and record.cellular_component:
            record.cellular_component.verified = True

        if rv.uniprot and rv.uniprot.status == "FOUND" and rv.uniprot.uniprot_id:
            record.protein["uniprot_id"] = rv.uniprot.uniprot_id

        if rv.eco and rv.eco.status == "VERIFIED" and record.evidence:
            record.evidence.eco_verified = True


def _display_results(details: list[RecordVerification], summary: VerificationSummary) -> None:
    # Per-record table
    table = Table(title="Verification Results", show_lines=False)
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("Protein")
    table.add_column("GO MF", justify="center")
    table.add_column("GO BP", justify="center")
    table.add_column("GO CC", justify="center")
    table.add_column("UniProt", justify="center")
    table.add_column("ECO", justify="center")

    # We need protein names — rebuild from the records_file is cleaner but
    # we don't have it here; use record_id as the identifier.
    for rv in details:
        def _st(field) -> str:
            return _style(field.status) if field else "[dim]—[/dim]"

        table.add_row(
            rv.record_id,
            "",  # protein name added below if available
            _st(rv.go_mf),
            _st(rv.go_bp),
            _st(rv.go_cc),
            _st(rv.uniprot),
            _st(rv.eco),
        )

    console.print(table)

    # Summary grid
    grid = Table.grid(padding=(0, 3))
    grid.add_column(style="dim")
    grid.add_column()

    def _fmt(n: int, colour: str = "green") -> str:
        return f"[{colour}]{n}[/{colour}]" if n else "0"

    grid.add_row("GO terms verified", _fmt(summary.go_terms_verified))
    grid.add_row("GO terms confirmed (already annotated)", _fmt(summary.go_terms_already_annotated, "cyan"))
    grid.add_row("GO terms not found / error", _fmt(summary.go_terms_failed, "red"))
    grid.add_row("GO terms obsolete", _fmt(summary.go_terms_obsolete, "yellow"))
    grid.add_row("GO terms skipped (UNKNOWN)", _fmt(summary.go_terms_skipped, "dim"))
    grid.add_row("UniProt confirmed", _fmt(summary.uniprot_confirmed))
    grid.add_row("ECO codes verified", _fmt(summary.eco_verified))

    console.print(grid)

    # QuickGO annotation confirmations — CONFIRMED
    confirmed = [
        (rv.record_id, fname, field)
        for rv in details
        for fname, field in [("MF", rv.go_mf), ("BP", rv.go_bp), ("CC", rv.go_cc)]
        if field and field.already_annotated
    ]
    if confirmed:
        console.print("\n[bold cyan]GO term comparison against existing QuickGO annotations:[/bold cyan]")
        for rec_id, fname, field in confirmed:
            console.print(
                f"  [dim]{rec_id} {fname}[/dim]  "
                f"[cyan]{field.suggested}[/cyan]  \"{field.official_label}\"  "
                f"[green]CONFIRMED — already annotated in QuickGO[/green]"
            )

    # NEW annotations — verified by QuickGO but not yet in existing annotations for that protein
    new_annotations = [
        (rv.record_id, fname, field)
        for rv in details
        if rv.uniprot and rv.uniprot.status == "FOUND"
        for fname, field in [("MF", rv.go_mf), ("BP", rv.go_bp), ("CC", rv.go_cc)]
        if field and field.status == "VERIFIED" and not field.already_annotated
    ]
    if new_annotations:
        console.print("\n[bold yellow]NEW GO annotations (valid term, not yet in QuickGO for this protein):[/bold yellow]")
        for rec_id, fname, field in new_annotations:
            console.print(
                f"  [dim]{rec_id} {fname}[/dim]  "
                f"[yellow]{field.suggested}[/yellow]  \"{field.official_label}\"  "
                f"[yellow]NEW — not yet in QuickGO, manual review recommended[/yellow]"
            )

    # Flag label mismatches
    mismatches = [
        (rv.record_id, field_name, field)
        for rv in details
        for field_name, field in [("MF", rv.go_mf), ("BP", rv.go_bp), ("CC", rv.go_cc)]
        if field and field.label_match is False
    ]
    if mismatches:
        console.print("\n[bold yellow]Label mismatches (suggested vs. official):[/bold yellow]")
        for rec_id, field_name, field in mismatches:
            console.print(
                f"  [dim]{rec_id} {field_name}[/dim]  "
                f"[red]{field.suggested}[/red] → official: \"{field.official_label}\""
            )
            if field.alternative_suggestions:
                console.print("    [dim]Suggested alternatives:[/dim]")
                for alt in field.alternative_suggestions[:3]:
                    console.print(f"      [cyan]{alt['go_id']}[/cyan]  {alt['label']}")

    # ECO suggestions for UNKNOWN codes — log format as per spec
    eco_suggestions = [
        (rv.record_id, rv.eco)
        for rv in details
        if rv.eco and rv.eco.status == "SKIPPED" and rv.eco.eco_suggestions
    ]
    if eco_suggestions:
        console.print("\n[bold yellow]ECO suggestions for UNKNOWN codes:[/bold yellow]")
        for rec_id, eco in eco_suggestions:
            codes = ", ".join(s["eco_id"] for s in eco.eco_suggestions[:5])
            console.print(
                f"  [dim]{rec_id}[/dim]  "
                f"Assay '{eco.suggested}' → suggested ECO terms: [cyan]{codes}[/cyan]"
            )
            for s in eco.eco_suggestions[:5]:
                console.print(f"    [cyan]{s['eco_id']}[/cyan]  {s['label']}")


@click.command("verify")
@click.option(
    "--process", "-p",
    default=None,
    help="Process name. Auto-detected if there is exactly one process.",
)
def verify_command(process: str | None) -> None:
    """Check all GO/ECO/UniProt IDs in evidence records against live databases.

    No AI is used — pure REST calls to QuickGO, UniProt, and OLS4/EBI.
    Updates evidence_records/records.json in-place (sets verified=true where
    confirmed, fills UniProt accession numbers). Saves a full report to
    verification/report.json.

    \b
    APIs USED
      QuickGO  https://www.ebi.ac.uk/QuickGO    GO term validation and search
      UniProt  https://rest.uniprot.org          Protein lookup by gene symbol
      OLS4     https://www.ebi.ac.uk/ols4        ECO code validation and search

    \b
    VERIFICATION STATUSES
      VERIFIED    Term exists and is current in the ontology.
      CONFIRMED   Term is already annotated for this protein in QuickGO
                  (strong independent confirmation — verified=true is set).
      NEW         Term is valid but not yet in QuickGO for this protein
                  (manual curator review recommended).
      OBSOLETE    Term exists but is marked obsolete — needs replacement.
      NOT_FOUND   Term does not exist — likely a hallucinated LLM ID.
      SKIPPED     ID was UNKNOWN — ECO suggestions shown where available.
      TIMEOUT     API unreachable — re-run verify to retry.

    \b
    OUTPUT
      verification/report.json         Full per-record verification details.
      evidence_records/records.json    Updated in-place:
        verified=true                  Set for confirmed GO terms and ECO codes.
        uniprot_id                     Filled in for identified proteins.
    """
    process_dir = resolve_process(process)
    meta = load_meta(process_dir)
    species: str = meta.get("species", "")
    process_name: str = meta.get("process_name", process_dir.name)

    records_path = process_dir / "evidence_records" / "records.json"
    if not records_path.exists():
        print_error("No records.json found. Run 'gocam translate' first.")
        raise SystemExit(1)

    records_file = EvidenceRecordsFile.model_validate(read_json(records_path))
    records = records_file.records

    if not records:
        print_warning("records.json is empty — nothing to verify.")
        raise SystemExit(0)

    console.print(
        f"[bold]Process:[/bold] {process_name}  "
        f"[bold]Records:[/bold] {len(records)}"
    )

    details: list[RecordVerification] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task = progress.add_task("Verifying...", total=len(records))

        for record in records:
            progress.update(
                task,
                description=f"[dim]{record.id}[/dim] {record.protein.get('name', '')}",
            )
            rv = _verify_record(record, species)
            details.append(rv)
            progress.advance(task)

    summary = _build_summary(details)

    # Save verification report
    report = VerificationReport(
        timestamp=datetime.now().isoformat(timespec="seconds"),
        summary=summary,
        details=details,
    )
    (process_dir / "verification").mkdir(exist_ok=True)
    report_path = process_dir / "verification" / "report.json"
    write_json(report_path, report)

    # Update records.json in-place
    _update_records(records_file, details)
    write_json(records_path, records_file)

    _display_results(details, summary)

    # Pipeline count log
    n_verified = summary.go_terms_verified + summary.go_terms_already_annotated
    print_info(
        f"Verify checked [bold]{len(records)}[/bold] records — "
        f"{n_verified} GO terms confirmed, "
        f"{summary.go_terms_failed} not found, "
        f"{summary.go_terms_skipped} skipped"
    )

    print_success(f"Verification report → {report_path}")
    print_success(f"records.json updated with verified IDs")
    console.print(
        "\nNext step: [bold]gocam narrative[/bold] — generate expert-readable claims"
    )
