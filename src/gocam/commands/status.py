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
    """Number of extraction JSON files (excludes *_summary.json)."""
    ext_dir = process_dir / "extractions"
    if not ext_dir.exists():
        return "—"
    files = [
        p for p in ext_dir.glob("*.json")
        if not p.stem.endswith("_summary")
    ]
    return f"{len(files)} file{'s' if len(files) != 1 else ''}" if files else "—"


def _validation_status(process_dir: Path) -> str:
    """Summarise validation: nodes and edges verified."""
    val_path = process_dir / "validation" / "validated_claims.json"
    if not val_path.exists():
        return "—"
    try:
        data = read_json(val_path)
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
        total = len(nodes) + len(edges)
        if total == 0:
            return "—"
        # Count nodes where at least one GO term is verified
        go_verified = sum(
            1 for n in nodes
            for gt_key in ("molecular_function", "biological_process", "cellular_component")
            if (n.get(gt_key) or {}).get("status") == "VERIFIED"
        )
        go_total = sum(
            1 for n in nodes
            for gt_key in ("molecular_function", "biological_process", "cellular_component")
            if n.get(gt_key)
        )
        return f"{go_verified}/{go_total} GO"
    except Exception:
        return "?"


def _narrative_status(process_dir: Path) -> str:
    narratives_dir = process_dir / "narratives"
    if not narratives_dir.exists():
        return "—"
    versions = sorted(narratives_dir.glob("claims_v*.md"))
    if not versions:
        return "—"
    latest = versions[-1].stem  # e.g. "claims_v3"
    version = latest.replace("claims_v", "")
    return f"v{version} draft"


def _enrichment_status(process_dir: Path) -> str:
    """Summarise enrichment: number of papers and new interactions found."""
    enrich_ext_dir = process_dir / "extractions" / "enrichment"
    enrich_input_dir = process_dir / "input" / "enrichment"
    if not enrich_ext_dir.exists():
        return "—"

    n_papers = len(list(enrich_input_dir.glob("pubmed_*.txt"))) if enrich_input_dir.exists() else 0
    if n_papers == 0:
        return "—"

    n_interactions = 0
    for jf in enrich_ext_dir.glob("pubmed_*.json"):
        try:
            data = read_json(jf)
            n_interactions += len(data.get("interactions", []))
        except Exception:
            pass

    return f"{n_papers}p/{n_interactions}i"


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
      Validated    GO terms verified vs total (e.g. "8/10 GO").
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
    table.add_column("Validated", justify="center")
    table.add_column("Narrative", justify="center")
    table.add_column("Enrichment", justify="center")

    for process_dir in processes:
        try:
            meta = read_json(process_dir / "meta.json")
        except Exception:
            meta = {}

        name = process_dir.name
        complexity = meta.get("complexity", "?")

        extracted = _count_extractions(process_dir)
        validated = _validation_status(process_dir)
        narrative = _narrative_status(process_dir)
        enrichment = _enrichment_status(process_dir)

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
            _fmt(validated),
            _fmt(narrative),
            _fmt(enrichment),
        )

    console.print()
    console.print(table)
    console.print()
