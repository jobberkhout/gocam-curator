"""gocam translate — map extracted biology to GO-CAM evidence records."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

import click
from rich.table import Table

from gocam.models.evidence import EvidenceRecordsFile
from gocam.services.llm import get_llm_client
from gocam.utils.display import console, print_error, print_info, print_success, print_warning, timed_status
from gocam.utils.io import read_json, write_json
from gocam.utils.process import load_meta, resolve_process

_RECORDS_PATH = "evidence_records/records.json"
_REPORT_PATH = "extractions/REPORT.md"
_SKIP_STEMS = {"REPORT"}

# Split translate into batches when the report has more than this many interactions.
_BATCH_THRESHOLD = 25
_BATCH_SIZE = 5


# ---------------------------------------------------------------------------
# Interaction counting / extraction from REPORT.md
# ---------------------------------------------------------------------------

def _build_pmid_table(json_files: list, read_json_fn) -> str:
    """Scan all extraction JSONs and build a source→PMID hint table for the translate prompt.

    Captures ALL unique PMIDs per source file (a review PDF may cite several papers).
    Returns a Markdown table string, or empty string if no PMIDs found.
    """
    source_pmids: dict[str, list[str]] = {}
    for p in json_files:
        try:
            data = read_json_fn(p)
        except Exception:
            continue
        stem = p.stem
        seen_for_stem: set[str] = set()
        # Collect PMIDs from interaction fields
        for interaction in data.get("interactions", []):
            pmid = interaction.get("pmid")
            if pmid and pmid not in ("null", "None", "UNKNOWN"):
                # Normalise: strip "PMID:" prefix if present
                pmid = re.sub(r"(?i)^pmid:?\s*", "", str(pmid)).strip()
                if pmid.isdigit() and pmid not in seen_for_stem:
                    seen_for_stem.add(pmid)
                    source_pmids.setdefault(stem, []).append(pmid)
    if not source_pmids:
        return ""
    lines = ["## Source File → PMID Mapping (use these when filling the pmid field)", ""]
    lines.append("| Source file | PMID(s) |")
    lines.append("|-------------|---------|")
    for stem, pmids in sorted(source_pmids.items()):
        lines.append(f"| {stem} | {', '.join(pmids)} |")
    lines.append("")
    lines.append("For source files not in this table, look for the PMID in the extracted text or write null.")
    return "\n".join(lines)


def _extract_interaction_lines(report_text: str) -> list[str]:
    """Return the numbered interaction lines from the Interaction Map section."""
    match = re.search(
        r"### Interaction Map.*?\n(.*?)(?=\n###|\Z)",
        report_text,
        re.DOTALL,
    )
    if not match:
        return []
    section = match.group(1)
    return [
        line.strip()
        for line in section.splitlines()
        if re.match(r"^\d+\.", line.strip())
    ]


# ---------------------------------------------------------------------------
# Input assembly
# ---------------------------------------------------------------------------

def _load_input(process_dir: Path) -> tuple[str, str, str, str]:
    """Return (source_description, report_text, raw_json_content, pmid_table).

    Keeps report and raw JSONs separate so batching can inject subsets of
    interactions while still providing full source context.
    """
    report_path = process_dir / _REPORT_PATH
    extractions_dir = process_dir / "extractions"

    json_files = sorted(
        p for p in extractions_dir.glob("*.json")
        if p.stem not in _SKIP_STEMS and not p.stem.endswith("_summary")
    )

    if not json_files and not report_path.exists():
        raise click.UsageError(
            "No extractions found. Run 'gocam extract' (and optionally 'gocam report') first."
        )

    report_text = ""
    if report_path.exists():
        report_text = report_path.read_text(encoding="utf-8")
        source_desc = f"REPORT.md + {len(json_files)} extraction JSON(s)"
    else:
        print_warning("No REPORT.md found — using raw extraction files. "
                      "Run 'gocam report' first for better results.")
        source_desc = f"{len(json_files)} raw extraction JSON(s)"

    raw_sections: list[str] = []
    for p in json_files:
        try:
            data = read_json(p)
        except Exception as exc:
            print_warning(f"Could not read {p.name}: {exc}")
            continue
        raw_sections.append(
            f"## Source file: {p.name}\n\n"
            f"```json\n{json.dumps(data, indent=2, ensure_ascii=False)}\n```"
        )

    raw_json_content = "\n\n---\n\n".join(raw_sections)
    pmid_table = _build_pmid_table(json_files, read_json)
    return source_desc, report_text, raw_json_content, pmid_table


def _build_user_msg(
    process_name: str,
    species: str,
    report_text: str,
    raw_json_content: str,
    pmid_table: str = "",
    interaction_lines: list[str] | None = None,
    batch_info: str = "",
    id_offset: int = 0,
) -> str:
    """Assemble the user message for a translate call.

    If interaction_lines is given, the message tells the model to translate
    ONLY those interactions (batch mode). id_offset shifts the ER-NNN numbering.
    """
    context_parts: list[str] = []
    if pmid_table:
        context_parts.append(pmid_table)
    if report_text:
        context_parts.append("## Synthesis Report\n\n" + report_text)
    if raw_json_content:
        context_parts.append(raw_json_content)
    context = "\n\n---\n\n".join(context_parts)

    if interaction_lines is not None:
        numbered = "\n".join(
            f"{i + 1 + id_offset}. {line.lstrip('0123456789. ')}"
            for i, line in enumerate(interaction_lines)
        )
        batch_header = (
            f"{batch_info}\n"
            f"Number records starting from ER-{id_offset + 1:03d}.\n"
            f"Translate ONLY the {len(interaction_lines)} interactions listed below. "
            f"Do NOT produce records for any interaction not in this list.\n\n"
            f"## Interactions to translate (this batch):\n{numbered}\n\n"
        )
    else:
        batch_header = (
            "Create one EvidenceRecord for EVERY interaction and connection in the data below.\n"
            "If information is incomplete, create the record anyway with confidence=LOW and "
            "note what is missing in warnings[]. Do not skip uncertain interactions.\n\n"
        )

    return (
        f"Process: {process_name}\n"
        f"Species: {species}\n"
        f"Date: {date.today().isoformat()}\n\n"
        f"{batch_header}"
        f"---\n\n"
        f"{context}\n\n"
        f"---\n\n"
        f"Return the complete EvidenceRecordsFile JSON. "
        f"All GO IDs and ECO codes must be marked verified=false."
    )


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def _parse_records(raw: dict, species: str) -> EvidenceRecordsFile:
    """Build a validated EvidenceRecordsFile from Claude's raw response dict."""
    if isinstance(raw, list):
        raw = {"records": raw}

    raw.setdefault("timestamp", datetime.now().isoformat(timespec="seconds"))

    for rec in raw.get("records", []):
        protein = rec.get("protein")
        if isinstance(protein, dict):
            protein.setdefault("species", species)
            protein.setdefault("uniprot_id", "UNVERIFIED")

    return EvidenceRecordsFile.model_validate(raw)


# ---------------------------------------------------------------------------
# Summary display
# ---------------------------------------------------------------------------

def _display_summary(
    records_file: EvidenceRecordsFile,
    out_path: Path,
    n_report_interactions: int,
) -> None:
    records = records_file.records

    n_unknown_mf = sum(
        1 for r in records
        if r.molecular_function and r.molecular_function.go_id in ("UNKNOWN", "")
    )
    n_warnings = sum(1 for r in records if r.warnings)
    n_binding_only = sum(1 for r in records if r.molecular_function is None)

    # Pipeline count log
    if n_report_interactions:
        ratio = f"{len(records)}/{n_report_interactions}"
        colour = "green" if len(records) >= n_report_interactions else "yellow"
        print_info(
            f"Report contained [bold]{n_report_interactions}[/bold] interactions → "
            f"Translate produced [{colour}]{len(records)}[/{colour}] records"
        )
        if len(records) < n_report_interactions:
            print_warning(
                f"{n_report_interactions - len(records)} interaction(s) may have been dropped. "
                "Re-run translate or inspect records.json."
            )

    print_success(f"{len(records)} evidence records → {out_path}")

    table = Table.grid(padding=(0, 3))
    table.add_column(style="dim")
    table.add_column()
    table.add_row("Records created", str(len(records)))
    table.add_row("Unknown MF GO IDs", f"[yellow]{n_unknown_mf}[/yellow]" if n_unknown_mf else "0")
    table.add_row("Records with warnings", f"[yellow]{n_warnings}[/yellow]" if n_warnings else "0")
    table.add_row("Binding-only (no MF)", f"[yellow]{n_binding_only}[/yellow]" if n_binding_only else "0")
    console.print(table)

    if n_warnings:
        console.print("\n[bold yellow]Warnings:[/bold yellow]")
        for r in records:
            for w in r.warnings:
                console.print(f"  [dim]{r.id}[/dim]  {w}")

    console.print(
        "\nNext step: [bold]gocam verify[/bold] — check all GO/ECO/UniProt IDs against live databases"
    )


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

@click.command("translate")
@click.option(
    "--process", "-p",
    default=None,
    help="Process name. Auto-detected if there is exactly one process.",
)
def translate_command(process: str | None) -> None:
    """Map extracted biology to GO-CAM evidence records (GO terms + ECO codes).

    Reads extractions/REPORT.md (and raw extraction JSONs for verbatim quotes
    and assay metadata), then asks the LLM to assign GO terms and ECO codes.
    All IDs are marked verified=false — run 'gocam verify' to validate them.

    When the report contains more than 25 interactions the call is automatically
    split into batches of 5 to avoid output token truncation.

    \b
    OUTPUT  evidence_records/records.json
      One record per protein activity, each containing:
        molecular_function   GO MF term and ID (e.g. GO:0004674)
        biological_process   GO BP term and ID
        cellular_component   GO CC term and ID
        evidence             Paper PMID, figure, assay name, ECO code
        protein              Gene symbol, species, UniProt ID (placeholder)
        confidence           LOW / MEDIUM / HIGH
        warnings             Curator notes on ambiguous or incomplete entries

    \b
    NOTES
      - All GO IDs and ECO codes start as verified=false until 'gocam verify'.
      - Re-running overwrites the existing records.json.
      - Prefer running 'gocam report' first; translate falls back to raw JSONs
        if REPORT.md is absent but results will be lower quality.
    """
    process_dir = resolve_process(process)
    meta = load_meta(process_dir)
    process_name = meta.get("process_name", process_dir.name)
    species = meta.get("species", "unknown")

    console.print(f"[bold]Process:[/bold] {process_name}  [bold]Species:[/bold] {species}")

    out_path = process_dir / _RECORDS_PATH
    if out_path.exists():
        print_warning("records.json already exists — it will be overwritten.")

    try:
        source_desc, report_text, raw_json_content, pmid_table = _load_input(process_dir)
    except click.UsageError:
        raise
    except Exception as exc:
        print_error(f"Failed to load extractions: {exc}")
        raise SystemExit(1)

    print_info(f"Input: {source_desc}")

    # Count interactions in the report for the pipeline log
    interaction_lines = _extract_interaction_lines(report_text)
    n_report_interactions = len(interaction_lines)
    if n_report_interactions:
        print_info(f"Report contains {n_report_interactions} interactions in Interaction Map")

    client = get_llm_client()
    all_records: list[dict] = []

    # -----------------------------------------------------------------------
    # Batched translate (> _BATCH_THRESHOLD interactions)
    # -----------------------------------------------------------------------
    if n_report_interactions > _BATCH_THRESHOLD:
        batches = [
            interaction_lines[i: i + _BATCH_SIZE]
            for i in range(0, n_report_interactions, _BATCH_SIZE)
        ]
        print_info(
            f"{n_report_interactions} interactions exceed threshold ({_BATCH_THRESHOLD}) — "
            f"splitting into {len(batches)} batches of up to {_BATCH_SIZE}"
        )

        for i, batch in enumerate(batches):
            id_offset = len(all_records)  # sequential IDs based on actual records produced
            batch_info = f"BATCH {i + 1} OF {len(batches)}"
            user_msg = _build_user_msg(
                process_name, species, report_text, raw_json_content,
                pmid_table=pmid_table,
                interaction_lines=batch,
                batch_info=batch_info,
                id_offset=id_offset,
            )

            with timed_status(f"Translating batch {i + 1}/{len(batches)} ({len(batch)} interactions)..."):
                try:
                    raw = client.call_text("translate", user_msg)
                except Exception as exc:
                    print_warning(f"Batch {i + 1} failed: {exc} — skipping")
                    continue

            try:
                batch_file = _parse_records(raw, species)
                all_records.extend(r.model_dump() for r in batch_file.records)
                print_info(f"  Batch {i + 1}: {len(batch_file.records)} records")
            except Exception as exc:
                print_warning(f"Batch {i + 1} parse error: {exc} — skipping")

        merged_raw = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "records": all_records,
        }

    # -----------------------------------------------------------------------
    # Single translate call (with one retry if records < interactions)
    # -----------------------------------------------------------------------
    else:
        user_msg = _build_user_msg(process_name, species, report_text, raw_json_content, pmid_table=pmid_table)

        with timed_status("Translating biology → GO-CAM evidence records..."):
            try:
                merged_raw = client.call_text("translate", user_msg)
            except ValueError as exc:
                print_error(f"Could not parse LLM response as JSON: {exc}")
                raise SystemExit(1)
            except Exception as exc:
                print_error(f"LLM call failed: {exc}")
                raise SystemExit(1)

        # Normalise: some models return a bare list instead of {records: [...]}
        if isinstance(merged_raw, list):
            merged_raw = {"records": merged_raw}

        # Retry once if fewer records were produced than interactions in the report
        n_produced = len(merged_raw.get("records", []))
        if n_report_interactions and n_produced < n_report_interactions:
            missing = n_report_interactions - n_produced
            print_warning(
                f"First pass produced only {n_produced}/{n_report_interactions} records — "
                f"retrying with explicit interaction list to recover {missing} missing record(s)."
            )
            retry_header = (
                f"IMPORTANT: Your previous response produced only {n_produced} records but the "
                f"Interaction Map contains {n_report_interactions} interactions. "
                f"You MUST produce exactly {n_report_interactions} records — one per interaction. "
                f"Do NOT skip any interaction, even if evidence is weak.\n\n"
                f"Interactions that appear to be missing (produce records for all of them):\n"
            )
            if interaction_lines:
                # List all interactions so the model can see what it missed
                retry_header += "\n".join(f"  {line}" for line in interaction_lines)
            retry_msg = (
                f"{retry_header}\n\n"
                + _build_user_msg(process_name, species, report_text, raw_json_content, pmid_table=pmid_table)
            )
            with timed_status(f"Retry: translating all {n_report_interactions} interactions..."):
                try:
                    merged_raw = client.call_text("translate", retry_msg)
                except Exception as exc:
                    print_warning(f"Retry failed: {exc} — using first-pass results")
                    # merged_raw already has the first-pass result; continue with it

    try:
        records_file = _parse_records(merged_raw, species)
    except Exception as exc:
        print_error(f"Evidence records did not match expected schema: {exc}")
        raise SystemExit(1)

    (process_dir / "evidence_records").mkdir(exist_ok=True)
    write_json(out_path, records_file)
    _display_summary(records_file, out_path, n_report_interactions)
