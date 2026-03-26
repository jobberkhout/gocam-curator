"""gocam interpret — LLM-assisted suggestions from validated claims (read-only)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import click

from gocam.models.claim import ValidationReport
from gocam.services.llm import get_llm_client
from gocam.utils.display import console, print_error, print_info, print_success, print_warning, timed_status
from gocam.utils.io import read_json
from gocam.utils.process import load_meta, resolve_process

_INTERPRETATION_DIR = "interpretation"


# ---------------------------------------------------------------------------
# Build a compact text summary of validated claims to send to the LLM
# ---------------------------------------------------------------------------

def _summarise_report(report: ValidationReport) -> str:
    """Serialise validated claims into a compact, readable text block for the LLM.

    We send structured text rather than raw JSON so the model focuses on content,
    not schema navigation.
    """
    lines: list[str] = []
    lines.append(f"Process: {report.process_name}")
    lines.append(f"Species: {report.species}")
    lines.append("")

    lines.append("=== NODES ===")
    for n in report.nodes:
        lines.append(f"\nNode {n.id} — {n.protein_name} ({n.gene_symbol or 'no symbol'})")
        lines.append(f"  UniProt: {n.uniprot_id or 'not found'} [{n.uniprot_status}]")

        for label, go_term in (
            ("MF", n.molecular_function),
            ("BP", n.biological_process),
            ("CC", n.cellular_component),
        ):
            if go_term:
                go_id = go_term.go_id or "no ID"
                official = f' / official: "{go_term.official_label}"' if go_term.official_label else ""
                lines.append(
                    f"  {label}: \"{go_term.term}\" [{go_id}] status={go_term.status}{official}"
                )
            else:
                lines.append(f"  {label}: not specified")

        if n.evidence:
            ev = n.evidence
            pmid_str = f"PMID:{ev.pmid} [{ev.pmid_status}]" if ev.pmid else "no PMID"
            assay_str = f"assay: {ev.assay}" if ev.assay else "no assay"
            fig_str = f"figure: {ev.figure}" if ev.figure else ""
            lines.append(f"  Evidence: {pmid_str} | {assay_str}" + (f" | {fig_str}" if fig_str else ""))

        if n.syngo_annotations:
            lines.append(f"  SynGO: {', '.join(n.syngo_annotations[:3])}")

        if n.quote:
            snippet = n.quote[:120] + "…" if len(n.quote) > 120 else n.quote
            lines.append(f"  Quote: \"{snippet}\"")

    lines.append("")
    lines.append("=== EDGES ===")
    for e in report.edges:
        lines.append(f"\nEdge {e.id} — {e.subject} → {e.relation} → {e.object}")
        if e.mechanism:
            lines.append(f"  Mechanism: {e.mechanism}")
        if e.evidence:
            ev = e.evidence
            pmid_str = f"PMID:{ev.pmid} [{ev.pmid_status}]" if ev.pmid else "no PMID"
            assay_str = f"assay: {ev.assay}" if ev.assay else "no assay"
            lines.append(f"  Evidence: {pmid_str} | {assay_str}")
        if e.quote:
            snippet = e.quote[:120] + "…" if len(e.quote) > 120 else e.quote
            lines.append(f"  Quote: \"{snippet}\"")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

@click.command("interpret")
@click.option(
    "--process", "-p",
    default=None,
    help="Process name. Auto-detected if there is exactly one process.",
)
@click.option(
    "--model",
    default=None,
    help="Override the LLM model for this run (uses default provider model if omitted).",
)
def interpret_command(process: str | None, model: str | None) -> None:
    """Suggest GO-term alternatives, gaps, and relation fixes (AI, read-only).

    Reads validation/validated_claims.json and sends a structured summary to
    the LLM. The LLM produces three types of suggestions:

    \b
    1. GO-TERM ALTERNATIVES
       For any MF/BP/CC with status NOT_FOUND or OBSOLETE, suggests 2-3
       alternative term names to search for. Never GO IDs — names only.

    \b
    2. GAP ANALYSIS
       Identifies missing proteins or causal steps that are well-established
       for this biological process but absent from the current model.

    \b
    3. RELATION TYPE REVIEW
       Flags edges where the relation type may be wrong given the evidence
       (e.g. a knockdown experiment labelled as directly_positively_regulates).

    \b
    CRITICAL CONSTRAINTS (enforced in the prompt)
      - No PMIDs, DOIs, or paper references — only the curator finds papers.
      - No GO IDs or ECO codes — only term names; curator validates via API.
      - Every suggestion is labelled SUGGESTION:, never stated as fact.
      - Nothing in validated_claims.json is modified.

    \b
    OUTPUT
      interpretation/suggestions.md   Human-readable Markdown advice document

    \b
    WORKFLOW POSITION
      gocam validate      → validates against live databases
      gocam narrative     → assembles verified claims
      gocam interpret     → LLM reviews and suggests improvements  ← you are here
      [curator edits]     → update extraction JSON if suggestions accepted
      gocam validate      → re-verify after changes

    \b
    EXAMPLES
      gocam interpret
      gocam interpret -p vesicle-fusion
    """
    process_dir = resolve_process(process)
    meta = load_meta(process_dir)
    process_name: str = meta.get("process_name", process_dir.name)
    species: str = meta.get("species", "")

    val_path = process_dir / "validation" / "validated_claims.json"
    if not val_path.exists():
        print_error("No validated_claims.json found. Run 'gocam validate' first.")
        raise SystemExit(1)

    report = ValidationReport.model_validate(read_json(val_path))

    if not report.nodes and not report.edges:
        print_warning("No validated claims to interpret.")
        raise SystemExit(0)

    n_unresolved = sum(
        1 for n in report.nodes
        for gt in (n.molecular_function, n.biological_process, n.cellular_component)
        if gt and gt.status in ("NOT_FOUND", "OBSOLETE")
    )
    console.print(
        f"[bold]Process:[/bold] {process_name}  "
        f"[bold]Nodes:[/bold] {len(report.nodes)}  "
        f"[bold]Edges:[/bold] {len(report.edges)}  "
        f"[bold]Unresolved GO terms:[/bold] {n_unresolved}"
    )

    # Build the user message
    summary = _summarise_report(report)
    user_msg = (
        f"Below is the validated GO-CAM claim set for the process "
        f"\"{process_name}\" ({species}).\n\n"
        f"Provide suggestions following the three tasks in your instructions.\n\n"
        f"---\n{summary}\n---"
    )

    client = get_llm_client()

    print_info(
        f"Sending {len(report.nodes)} nodes and {len(report.edges)} edges to LLM for interpretation…"
    )
    with timed_status("Interpreting…"):
        suggestions_md = client.call_text_markdown("interpret", user_msg)

    if not suggestions_md or not suggestions_md.strip():
        print_warning("LLM returned an empty response.")
        raise SystemExit(1)

    # Prepend a header with metadata the LLM cannot add reliably
    header = (
        f"# Interpretation Suggestions — {process_name}\n\n"
        f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | "
        f"Source: validation/validated_claims.json | "
        f"Model: {getattr(client, 'model', 'unknown')}*\n\n"
        f"> **These are SUGGESTIONS only.** Nothing here modifies validated data.\n"
        f"> Review each item manually. Accepted suggestions should be implemented\n"
        f"> by editing extraction JSON files, then re-running `gocam validate`.\n\n"
        f"---\n\n"
    )

    # Strip the LLM's own title if it output one (we prepend our own)
    body = suggestions_md.strip()
    if body.startswith("# Interpretation Suggestions"):
        body = "\n".join(body.split("\n")[1:]).lstrip()

    full_doc = header + body + "\n"

    # Save
    interp_dir = process_dir / _INTERPRETATION_DIR
    interp_dir.mkdir(exist_ok=True)
    out_path = interp_dir / "suggestions.md"
    out_path.write_text(full_doc, encoding="utf-8")

    print_success(f"Suggestions saved → {out_path}")
    console.print(
        f"\n[dim]Review with: open {out_path}[/dim]\n"
        "[dim]To act on a GO-term suggestion: gocam search <term>[/dim]\n"
        "[dim]To act on a gap suggestion: add to input/, then gocam extract-all[/dim]"
    )
