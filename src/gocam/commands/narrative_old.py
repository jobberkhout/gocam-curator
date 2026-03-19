"""gocam narrative — generate expert-readable validation claims."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import click

from gocam.models.evidence import EvidenceRecordsFile
from gocam.services.llm import get_llm_client
from gocam.utils.display import console, print_error, print_info, print_success, print_warning, timed_status
from gocam.utils.io import read_json
from gocam.utils.process import load_meta, resolve_process

_NARRATIVES_DIR = "narratives"


def _next_version_path(narratives_dir: Path) -> Path:
    """Return narratives/claims_v1.md, or v2, v3 … if earlier versions exist."""
    v = 1
    while True:
        candidate = narratives_dir / f"claims_v{v}.md"
        if not candidate.exists():
            return candidate
        v += 1


@click.command("narrative")
@click.option(
    "--process", "-p",
    default=None,
    help="Process name. Auto-detected if there is exactly one process.",
)
def narrative_command(process: str | None) -> None:
    """Generate an expert-readable validation document from evidence records.

    Reads evidence_records/records.json and (if available) verification/report.json,
    then uses the LLM to produce a numbered claim list for the domain expert
    to review. Saves to narratives/claims_v{N}.md (version auto-increments).

    \b
    OUTPUT  narratives/claims_v1.md  (or v2, v3 … if earlier versions exist)
      Each numbered claim states:
        - The molecular function the protein performs
        - The biological process it contributes to
        - The cellular component where it acts
        - The experimental evidence (paper, figure, assay, ECO code)
        - Verification status: CONFIRMED / NEW / needs review

    \b
    EXPERT REVIEW WORKFLOW
      1. Send the .md file to the domain expert.
      2. Ask them to respond per claim:
           OK                     Claim is correct as stated.
           WRONG — [correction]   State what is incorrect and what is right.
           UNCERTAIN              Not enough evidence to confirm or deny.
      3. Incorporate feedback, update records.json if needed, and re-run
         'gocam translate' + 'gocam narrative' to generate a revised version.

    \b
    NOTES
      - Run 'gocam verify' before 'gocam narrative' so that verification
        status (CONFIRMED / NEW) is reflected in the output.
      - Re-running always creates a new version file and never overwrites.
    """
    process_dir = resolve_process(process)
    meta = load_meta(process_dir)
    process_name: str = meta.get("process_name", process_dir.name)
    species: str = meta.get("species", "")
    expert: dict = meta.get("expert") or {}
    expert_name: str = expert.get("name", "Expert")

    records_path = process_dir / "evidence_records" / "records.json"
    if not records_path.exists():
        print_error("No records.json found. Run 'gocam translate' first.")
        raise SystemExit(1)

    records_file = EvidenceRecordsFile.model_validate(read_json(records_path))

    if not records_file.records:
        print_warning("records.json is empty — nothing to narrate.")
        raise SystemExit(0)

    # Warn if verification hasn't been run yet
    verify_path = process_dir / "verification" / "report.json"
    if not verify_path.exists():
        print_warning(
            "verification/report.json not found. "
            "Run 'gocam verify' first for accurate verification status in the narrative."
        )
        verification_note = "Note: GO/ECO/UniProt IDs have NOT been verified against live databases."
    else:
        verification_note = "GO/ECO/UniProt IDs have been checked against live databases (see verification/report.json)."

    console.print(
        f"[bold]Process:[/bold] {process_name}  "
        f"[bold]Records:[/bold] {len(records_file.records)}  "
        f"[bold]Expert:[/bold] {expert_name}"
    )

    user_msg = (
        f"Process: {process_name}\n"
        f"Species: {species}\n"
        f"Expert: {expert_name}\n"
        f"Date: {date.today().isoformat()}\n"
        f"{verification_note}\n\n"
        f"Below are the GO-CAM evidence records to convert into expert-readable claims:\n\n"
        f"```json\n"
        f"{json.dumps(records_file.model_dump(), indent=2, ensure_ascii=False)}\n"
        f"```\n\n"
        f"Generate the expert validation document following the format in your instructions."
    )

    client = get_llm_client()

    with timed_status("Generating expert validation document..."):
        try:
            narrative_md = client.call_text_markdown("narrative", user_msg)
        except Exception as exc:
            print_error(f"LLM call failed: {exc}")
            raise SystemExit(1)

    narratives_dir = process_dir / _NARRATIVES_DIR
    narratives_dir.mkdir(exist_ok=True)
    out_path = _next_version_path(narratives_dir)
    out_path.write_text(narrative_md, encoding="utf-8")

    # Pipeline count log — count numbered claims in the generated Markdown
    import re as _re
    n_claims = len(_re.findall(r"^\d+\.", narrative_md, _re.MULTILINE))
    print_info(
        f"Narrative generated [bold]{n_claims}[/bold] claims "
        f"from {len(records_file.records)} records → {out_path.name}"
    )
    print_success(f"Narrative saved → {out_path}")
    console.print(f"\n[dim]Open with: open {out_path}[/dim]")
    console.print(
        "\nSend this document to the expert and ask them to respond per claim: "
        "[bold]OK[/bold] / [bold]WRONG — [correction][/bold] / [bold]UNCERTAIN[/bold]"
    )
