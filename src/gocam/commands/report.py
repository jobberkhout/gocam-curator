"""gocam report — synthesize all extractions into a single Markdown report."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import click

from gocam.services.llm import get_llm_client
from gocam.utils.display import console, print_error, print_info, print_success, print_warning, timed_status
from gocam.utils.io import read_json
from gocam.utils.process import load_meta, resolve_process

_REPORT_FILENAME = "REPORT.md"
_SKIP_STEMS = {"REPORT"}  # stems to exclude when loading extraction JSONs

# Approximate token-per-character ratio for JSON (conservative: 1 token ≈ 3 chars).
# We target batches well under the 1M token limit to leave room for the system prompt.
_MAX_BATCH_CHARS = 100_000 * 3  # ~100K tokens worth of characters


def _build_source_block(json_path: Path, index: int) -> tuple[str, int]:
    """Load one extraction JSON and return (markdown block, char count)."""
    data = read_json(json_path)
    n_entities = len(data.get("entities", []))
    n_interactions = len(data.get("interactions", []) + data.get("connections_shown", []))
    source_type = data.get("source_type", "unknown")
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    block = (
        f"## Source {index}: {json_path.name} (type: {source_type})\n"
        f"Entities: {n_entities}  |  Interactions/connections: {n_interactions}\n\n"
        f"```json\n{json_str}\n```"
    )
    return block, len(block)


def _build_batch_prompt(
    blocks: list[str],
    process_name: str,
    species: str,
    batch_label: str,
) -> str:
    """Construct the user message for a batch of source blocks."""
    return (
        f"Process: {process_name}\n"
        f"Species: {species}\n"
        f"Date: {date.today().isoformat()}\n"
        f"Batch: {batch_label}\n"
        f"Total sources in this batch: {len(blocks)}\n\n"
        + "\n\n---\n\n".join(blocks)
        + "\n\n---\n\nGenerate the full extraction report following the format in your instructions."
    )


def _build_merge_prompt(
    partial_reports: list[str],
    process_name: str,
    species: str,
) -> str:
    """Construct the user message to merge partial reports into the final report."""
    sections = []
    for i, report in enumerate(partial_reports, start=1):
        sections.append(
            f"## Partial report {i}/{len(partial_reports)}\n\n{report}"
        )
    return (
        f"Process: {process_name}\n"
        f"Species: {species}\n"
        f"Date: {date.today().isoformat()}\n\n"
        f"The extraction data was too large for a single pass, so it was split into "
        f"{len(partial_reports)} batches. Each batch produced a partial report below.\n\n"
        "Your task: merge these partial reports into ONE coherent final report. "
        "Deduplicate entities (resolve synonyms), combine interaction lists, "
        "unify confidence scores across all sources, and consolidate questions for the expert. "
        "Follow the standard report format from your instructions.\n\n"
        + "\n\n---\n\n".join(sections)
        + "\n\n---\n\nGenerate the merged final report."
    )


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

    When the combined input exceeds the model's context window, extractions
    are automatically split into batches.  Each batch produces a partial
    report, then a final merge pass combines them.

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

    # Load all source blocks and measure sizes
    source_blocks: list[tuple[str, int]] = []  # (block text, char count)
    for i, json_path in enumerate(json_files, start=1):
        try:
            block, size = _build_source_block(json_path, i)
            source_blocks.append((block, size))
        except Exception as exc:
            print_warning(f"Could not read {json_path.name}: {exc}")

    if not source_blocks:
        print_error("All extraction files failed to load.")
        raise SystemExit(1)

    # Split into batches that fit within context limits
    batches: list[list[str]] = []
    current_batch: list[str] = []
    current_size = 0

    for block, size in source_blocks:
        if current_batch and current_size + size > _MAX_BATCH_CHARS:
            batches.append(current_batch)
            current_batch = []
            current_size = 0
        current_batch.append(block)
        current_size += size

    if current_batch:
        batches.append(current_batch)

    client = get_llm_client()

    if len(batches) == 1:
        # Everything fits in one call
        user_msg = _build_batch_prompt(
            batches[0], process_name, species,
            f"1/1 (all {len(source_blocks)} sources)",
        )
        with timed_status(f"Synthesizing {len(source_blocks)} sources..."):
            try:
                report_md = client.call_text_markdown("report", user_msg)
            except Exception as exc:
                print_error(f"Report generation failed: {exc}")
                raise SystemExit(1)
    else:
        # Multi-batch: generate partial reports, then merge
        print_info(
            f"Input too large for single call — splitting into {len(batches)} batches "
            f"({', '.join(str(len(b)) for b in batches)} sources each)"
        )
        partial_reports: list[str] = []

        for batch_idx, batch in enumerate(batches, start=1):
            label = f"{batch_idx}/{len(batches)} ({len(batch)} sources)"
            user_msg = _build_batch_prompt(
                batch, process_name, species, label,
            )
            # Try twice — 499 CANCELLED is often a transient server timeout
            for attempt in range(2):
                with timed_status(f"Batch {label}{'  (retry)' if attempt else ''}..."):
                    try:
                        partial = client.call_text_markdown("report", user_msg)
                        partial_reports.append(partial)
                        print_success(f"Batch {label} done")
                        break
                    except Exception as exc:
                        if attempt == 0 and "cancel" in str(exc).lower():
                            print_warning(f"Batch {label} timed out — retrying...")
                        else:
                            print_warning(f"Batch {label} failed: {exc}")
                            break

        if not partial_reports:
            print_error("All batches failed.")
            raise SystemExit(1)
        
        if len(partial_reports) == 1:
            # Only one batch succeeded — use it directly
            report_md = partial_reports[0]
        else:
            # Merge partial reports in chunks to avoid 504 Timeouts
            with timed_status(f"Merging {len(partial_reports)} partial reports in chunks..."):
                try:
                    chunk_size = 5
                    merged_chunks = []
                    
                    # Step 1: Merge the partial reports into a few combined chunks
                    for i in range(0, len(partial_reports), chunk_size):
                        chunk = partial_reports[i : i + chunk_size]
                        print_info(f"Merging subset {i // chunk_size + 1} ({len(chunk)} reports)...")
                        
                        merge_msg = _build_merge_prompt(chunk, process_name, species)
                        merged_chunks.append(client.call_text_markdown("report", merge_msg))
                    
                    # Step 2: Merge those combined chunks into one final report
                    if len(merged_chunks) > 1:
                        print_info(f"Performing final master merge of {len(merged_chunks)} chunks...")
                        final_merge_msg = _build_merge_prompt(merged_chunks, process_name, species)
                        report_md = client.call_text_markdown("report", final_merge_msg)
                    else:
                        report_md = merged_chunks[0]

                except Exception as exc:
                    print_error(f"Merge failed: {exc}")
                    # Fall back: concatenate partial reports
                    print_warning("Falling back to concatenated partial reports")
                    report_md = (
                        f"# {process_name} — Extraction Report\n\n"
                        f"*Auto-generated from {len(partial_reports)} batches "
                        f"(merge pass failed)*\n\n"
                        + "\n\n---\n\n".join(partial_reports)
                    )

        # if len(partial_reports) == 1:
        #     # Only one batch succeeded — use it directly
        #     report_md = partial_reports[0]
        # else:
        #     # Merge partial reports
        #     with timed_status(f"Merging {len(partial_reports)} partial reports..."):
        #         try:
        #             merge_msg = _build_merge_prompt(
        #                 partial_reports, process_name, species,
        #             )
        #             report_md = client.call_text_markdown("report", merge_msg)
        #         except Exception as exc:
        #             print_error(f"Merge failed: {exc}")
        #             # Fall back: concatenate partial reports
        #             print_warning("Falling back to concatenated partial reports")
        #             report_md = (
        #                 f"# {process_name} — Extraction Report\n\n"
        #                 f"*Auto-generated from {len(partial_reports)} batches "
        #                 f"(merge pass failed)*\n\n"
        #                 + "\n\n---\n\n".join(partial_reports)
        #             )

    out_path = extractions_dir / _REPORT_FILENAME
    out_path.write_text(report_md, encoding="utf-8")
    print_success(f"Report saved → {out_path}")
    console.print(f"\n[dim]Open with: open {out_path}[/dim]")
