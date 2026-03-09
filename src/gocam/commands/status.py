"""gocam status — overview table of all processes and their progress."""

from __future__ import annotations

from pathlib import Path

import click
from rich.table import Table

from gocam.config import PROCESSES_DIR
from gocam.utils.display import console
from gocam.utils.io import read_json


# ---------------------------------------------------------------------------
# Per-process introspection helpers
# ---------------------------------------------------------------------------

def _count_extractions(process_dir: Path) -> str:
    """Number of extraction JSON files (excludes *_summary.json and REPORT stem)."""
    ext_dir = process_dir / "extractions"
    if not ext_dir.exists():
        return "—"
    files = [
        p for p in ext_dir.glob("*.json")
        if p.stem != "REPORT" and not p.stem.endswith("_summary")
    ]
    return f"{len(files)} file{'s' if len(files) != 1 else ''}" if files else "—"


def _report_status(process_dir: Path) -> str:
    return "✓" if (process_dir / "extractions" / "REPORT.md").exists() else "—"


def _translation_status(process_dir: Path) -> str:
    records_path = process_dir / "evidence_records" / "records.json"
    if not records_path.exists():
        return "—"
    try:
        data = read_json(records_path)
        n = len(data.get("records", []))
        return f"{n} record{'s' if n != 1 else ''}" if n else "—"
    except Exception:
        return "?"


def _verification_status(process_dir: Path) -> str:
    report_path = process_dir / "verification" / "report.json"
    if not report_path.exists():
        return "—"
    try:
        data = read_json(report_path)
        summary = data.get("summary", {})
        total = summary.get("total_records", 0)
        if total == 0:
            return "—"
        # Count records where the MF GO term is verified
        verified = sum(
            1 for rec in data.get("details", [])
            if (rec.get("go_mf") or {}).get("status") == "VERIFIED"
        )
        return f"{verified}/{total} ✓"
    except Exception:
        return "?"


def _narrative_status(process_dir: Path) -> str:
    narratives_dir = process_dir / "narratives"
    if not narratives_dir.exists():
        return "—"
    versions = sorted(narratives_dir.glob("claims_v*.md"))
    if not versions:
        return "—"
    # Extract the highest version number from the filename
    latest = versions[-1].stem  # e.g. "claims_v3"
    version = latest.replace("claims_v", "")
    return f"v{version} draft"


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

@click.command("status")
def status_command() -> None:
    """Show an overview of all processes and their pipeline progress.

    Displays a table with one row per process showing the completion status
    of each pipeline stage:

    \b
      Extracted    Number of extraction JSON files produced by 'gocam extract-all'.
      Report       Whether extractions/REPORT.md exists.
      Translated   Number of evidence records in evidence_records/records.json.
      Verified     Fraction of MF GO terms verified (e.g. "8/10 ✓").
      Narrative    Latest narrative version (e.g. "v2 draft").
    """
    if not PROCESSES_DIR.exists():
        console.print("[dim]No processes directory found. Run 'gocam init <name>' to start.[/dim]")
        return

    processes = sorted(
        p for p in PROCESSES_DIR.iterdir()
        if p.is_dir() and (p / "meta.json").exists()
    )

    if not processes:
        console.print("[dim]No processes found. Run 'gocam init <name>' to start.[/dim]")
        return

    table = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
    table.add_column("Process", min_width=28)
    table.add_column("Complexity", justify="center")
    table.add_column("Extracted", justify="center")
    table.add_column("Report", justify="center")
    table.add_column("Translated", justify="center")
    table.add_column("Verified", justify="center")
    table.add_column("Narrative", justify="center")

    for process_dir in processes:
        try:
            meta = read_json(process_dir / "meta.json")
        except Exception:
            meta = {}

        name = process_dir.name
        complexity = meta.get("complexity", "?")

        extracted = _count_extractions(process_dir)
        report = _report_status(process_dir)
        translated = _translation_status(process_dir)
        verified = _verification_status(process_dir)
        narrative = _narrative_status(process_dir)

        # Colour-code the check columns
        def _fmt(val: str) -> str:
            if val == "✓":
                return "[green]✓[/green]"
            if val == "—":
                return "[dim]—[/dim]"
            if "✓" in val:
                return f"[green]{val}[/green]"
            return val

        table.add_row(
            name,
            complexity,
            _fmt(extracted),
            _fmt(report),
            _fmt(translated),
            _fmt(verified),
            _fmt(narrative),
        )

    console.print()
    console.print(table)
    console.print()
