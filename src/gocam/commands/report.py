"""gocam report — synthesize all extractions into a single Markdown report."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import click

from gocam.services.llm import get_llm_client
from gocam.utils.display import console, print_error, print_success, print_warning, timed_status
from gocam.utils.io import read_json
from gocam.utils.process import load_meta, resolve_process

_REPORT_FILENAME = "REPORT.md"
_SKIP_STEMS = {"REPORT"}  # stems to exclude when loading extraction JSONs


@click.command("report")
@click.option(
    "--process", "-p",
    default=None,
    help="Process name. Auto-detected if there is exactly one process.",
)
def report_command(process: str | None) -> None:
    """Synthesize all extractions into a single reviewable Markdown report.

    Reads every .json file from extractions/ (excluding *_summary.json and
    the REPORT itself), merges and deduplicates them using the LLM, and
    saves extractions/REPORT.md.

    \b
    OUTPUT  extractions/REPORT.md  containing:
      - Entity list with synonyms resolved across sources
      - Interaction map with cross-reference confidence scores
        (1 source = LOW, 2–3 sources = MEDIUM, 4+ sources = HIGH)
      - Evidence quality assessment
      - Questions for the domain expert

    \b
    NOTES
      - Run after 'gocam extract-all' and before 'gocam translate'.
      - Re-running overwrites the existing REPORT.md.
      - If using --deep mode: run 'gocam extract-all --deep', then re-run
        'gocam report' to incorporate the second-pass findings.
      - 'gocam translate' reads REPORT.md for context and falls back to raw
        JSONs if REPORT.md does not exist.
    """
    process_dir = resolve_process(process)
    meta = load_meta(process_dir)
    process_name = meta.get("process_name", process_dir.name)
    species = meta.get("species", "unknown")
    extractions_dir = process_dir / "extractions"

    if not extractions_dir.exists():
        print_error("No extractions/ directory found. Run 'gocam extract' first.")
        raise SystemExit(1)

    # Collect all extraction JSON files (skip REPORT.md and *_summary.json)
    json_files = sorted(
        p for p in extractions_dir.glob("*.json")
        if p.stem not in _SKIP_STEMS and not p.stem.endswith("_summary")
    )

    if not json_files:
        print_error("No extraction JSON files found. Run 'gocam extract' on your input files first.")
        raise SystemExit(1)

    console.print(
        f"[bold]Process:[/bold] {process_name}  "
        f"[bold]Sources:[/bold] {len(json_files)} extraction files"
    )

    # Load and summarise each extraction
    source_summaries: list[str] = []
    for i, json_path in enumerate(json_files, start=1):
        try:
            data = read_json(json_path)
        except Exception as exc:
            print_warning(f"Could not read {json_path.name}: {exc}")
            continue

        n_entities = len(data.get("entities", []))
        n_interactions = len(data.get("interactions", []) + data.get("connections_shown", []))
        source_type = data.get("source_type", "unknown")
        source_summaries.append(
            f"## Source {i}: {json_path.name} (type: {source_type})\n"
            f"Entities: {n_entities}  |  Interactions/connections: {n_interactions}\n\n"
            f"```json\n{json.dumps(data, indent=2, ensure_ascii=False)}\n```"
        )

    if not source_summaries:
        print_error("All extraction files failed to load.")
        raise SystemExit(1)

    user_msg = (
        f"Process: {process_name}\n"
        f"Species: {species}\n"
        f"Date: {date.today().isoformat()}\n"
        f"Total sources: {len(source_summaries)}\n\n"
        + "\n\n---\n\n".join(source_summaries)
        + "\n\n---\n\nGenerate the full extraction report following the format in your instructions."
    )

    client = get_llm_client()

    with timed_status(f"Synthesizing {len(source_summaries)} sources with Claude..."):
        try:
            report_md = client.call_text_markdown("report", user_msg)
        except Exception as exc:
            print_error(f"Report generation failed: {exc}")
            raise SystemExit(1)

    out_path = extractions_dir / _REPORT_FILENAME
    out_path.write_text(report_md, encoding="utf-8")
    print_success(f"Report saved → {out_path}")
    console.print(f"\n[dim]Open with: open {out_path}[/dim]")
