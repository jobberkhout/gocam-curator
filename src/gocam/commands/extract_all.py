"""gocam extract-all — extract from every file in the process input/ directory."""

from __future__ import annotations

from pathlib import Path

import click

from gocam.commands.extract import (
    _build_extraction,
    _process_image,
    _process_pdf,
    _process_pptx,
    _process_text,
)
from gocam.services.file_processor import (
    IMAGE_EXTENSIONS,
    PDF_EXTENSIONS,
    PPTX_EXTENSIONS,
    TEXT_EXTENSIONS,
    process_file,
)
from gocam.services.llm import get_llm_client
from gocam.utils.display import console, print_error, print_info, print_success, print_warning, timed_status
from gocam.utils.io import write_json
from gocam.utils.process import load_meta, resolve_process

_ALL_EXTENSIONS = TEXT_EXTENSIONS | IMAGE_EXTENSIONS | PDF_EXTENSIONS | PPTX_EXTENSIONS


# ---------------------------------------------------------------------------
# Skip detection
# ---------------------------------------------------------------------------

def _already_extracted(extractions_dir: Path, file: Path) -> bool:
    """Return True if this input file already has a first-pass extraction JSON."""
    stem = file.stem
    suffix = file.suffix.lower()
    if suffix in TEXT_EXTENSIONS | IMAGE_EXTENSIONS:
        return (extractions_dir / f"{stem}.json").exists()
    if suffix in PDF_EXTENSIONS:
        return (extractions_dir / f"{stem}.json").exists() or any(
            extractions_dir.glob(f"{stem}_pages*.json")
        )
    if suffix in PPTX_EXTENSIONS:
        return any(extractions_dir.glob(f"{stem}_slide*.json")) or (
            extractions_dir / f"{stem}_notes.json"
        ).exists()
    return False


def _already_deep_extracted(extractions_dir: Path, stem: str) -> bool:
    """Return True if a deep-pass (_p2) extraction already exists."""
    return (extractions_dir / f"{stem}_p2.json").exists()


# ---------------------------------------------------------------------------
# Deep-pass extraction
# ---------------------------------------------------------------------------

def _process_deep(client, file: Path, extractions_dir: Path, report_text: str) -> None:
    """Second-pass: re-read source in context of what is already captured."""
    try:
        content = process_file(file)
    except Exception as exc:
        print_warning(f"Could not read {file.name}: {exc}")
        return

    stem = file.stem
    preamble = (
        "## What Has Already Been Extracted — Synthesis Report\n\n"
        f"{report_text}\n\n"
        "---\n\n"
        "Now re-read the source below. Return ONLY entities and interactions that are "
        "NOT already captured in the report above. Focus on: indirect regulators, "
        "scaffolding proteins, phosphatases, deubiquitinases, upstream signals, and "
        "negative regulators. If you find nothing new, return empty arrays.\n\n"
        "Set extraction_pass to 2 in your response.\n\n"
    )

    try:
        if content.source_type == "text":
            user_msg = (
                preamble
                + f"Source: {file.name}\n\n---\n{content.text}\n---\n\n"
                "Return extraction JSON with only MISSED content."
            )
            with timed_status("Deep extraction..."):
                raw = client.call_text("extract_deep", user_msg)

        elif content.source_type == "image":
            user_msg = (
                preamble
                + f"Source: {file.name}\n\n"
                "Analyze the image and return ONLY what was MISSED."
            )
            with timed_status("Deep extraction..."):
                raw = client.call_vision("extract_deep", user_msg, content.images)

        elif content.source_type == "pdf":
            if content.skipped_pages_msg:
                print_info(content.skipped_pages_msg)
            user_msg = (
                preamble
                + f"Source: {file.name}\n\n"
                f"Text content:\n---\n{content.text or ''}\n---\n\n"
                "Return extraction JSON with only MISSED content."
            )
            with timed_status("Deep extraction..."):
                raw = client.call_text("extract_deep", user_msg)

        elif content.source_type == "slide":
            slides_text = "\n\n".join(
                f"[Slide {s.slide_number}]\n{s.text or '(no text)'}"
                + (f"\nNotes: {s.notes}" if s.notes else "")
                for s in content.slides
            )
            user_msg = (
                preamble
                + f"Source: {file.name}\n\n"
                f"Slide content:\n---\n{slides_text}\n---\n\n"
                "Return extraction JSON with only MISSED content."
            )
            with timed_status("Deep extraction..."):
                raw = client.call_text("extract_deep", user_msg)
        else:
            print_warning(f"Unsupported source type for deep pass: {content.source_type}")
            return

        raw["extraction_pass"] = 2
        extraction = _build_extraction(raw, f"{stem}_p2", content.source_type)
        out = extractions_dir / f"{stem}_p2.json"
        write_json(out, extraction)
        n_new = len(extraction.entities) + len(extraction.interactions) + len(extraction.connections_shown)
        print_success(f"  Deep pass: {n_new} new items → {out.name}")

    except Exception as exc:
        print_warning(f"  Deep pass failed for {file.name}: {exc}")


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

@click.command("extract-all")
@click.option(
    "--process", "-p",
    default=None,
    help="Process name. Auto-detected if there is exactly one process.",
)
@click.option(
    "--deep",
    is_flag=True,
    default=False,
    help="Second-pass extraction to find entities and interactions missed in the first pass. "
         "Requires REPORT.md to exist (run 'gocam report' first).",
)
def extract_all_command(process: str | None, deep: bool) -> None:
    """Extract from every supported file in the process input/ directory.

    Processes .txt, .md, .pdf, .pptx, .png, and .jpg files. Files that
    already have a corresponding extraction JSON are skipped automatically.

    \b
    DEEP MODE  (--deep)
      Re-reads each source file in the context of what is already in
      extractions/REPORT.md. Focuses on content that is commonly missed in
      the first pass: indirect regulators, scaffolding proteins, phosphatases,
      deubiquitinases, upstream signals, and negative regulators.
      Saves additional results as {stem}_p2.json.
      Requires extractions/REPORT.md — run 'gocam report' first.

    \b
    OUTPUT  (saved to extractions/)
      Same layout as 'gocam extract' for each file, plus:
      {stem}_p2.json     Deep-pass findings (--deep only)

    \b
    EXAMPLES
      gocam extract-all
      gocam extract-all --deep
      gocam extract-all --process vesicle-fusion
    """
    process_dir = resolve_process(process)
    meta = load_meta(process_dir)
    process_name = meta.get("process_name", process_dir.name)

    input_dir = process_dir / "input"
    extractions_dir = process_dir / "extractions"
    extractions_dir.mkdir(exist_ok=True)

    if not input_dir.exists():
        print_error(
            "No input/ directory found. "
            "Place source files in processes/<name>/input/"
        )
        raise SystemExit(1)

    input_files = sorted(
        p for p in input_dir.iterdir()
        if p.is_file() and p.suffix.lower() in _ALL_EXTENSIONS
    )

    if not input_files:
        print_warning(
            "No supported files found in input/. "
            "Supported: .txt, .md, .pdf, .pptx, .png, .jpg, .jpeg"
        )
        return

    console.print(
        f"[bold]Process:[/bold] {process_name}  "
        f"[bold]Files:[/bold] {len(input_files)}  "
        f"[bold]Mode:[/bold] {'deep (second pass)' if deep else 'standard'}"
    )

    # Deep pass requires REPORT.md
    report_text: str = ""
    if deep:
        report_path = extractions_dir / "REPORT.md"
        if not report_path.exists():
            print_error("--deep requires extractions/REPORT.md. Run 'gocam report' first.")
            raise SystemExit(1)
        report_text = report_path.read_text(encoding="utf-8")
        print_info("Deep mode: searching for missed entities and interactions")

    client = get_llm_client()
    skipped = processed = failed = 0

    # Count already-done files up front so we can show a resume message
    if deep:
        already_done = sum(1 for f in input_files if _already_deep_extracted(extractions_dir, f.stem))
    else:
        already_done = sum(1 for f in input_files if _already_extracted(extractions_dir, f))
    if already_done:
        print_info(
            f"Resuming — {already_done}/{len(input_files)} file(s) already processed, "
            f"{len(input_files) - already_done} remaining"
        )

    for i, file in enumerate(input_files, start=1):
        print_info(f"Processing file {i}/{len(input_files)}: {file.name}")

        if deep:
            if _already_deep_extracted(extractions_dir, file.stem):
                print_info(f"  Skipping — deep extraction already exists")
                skipped += 1
                continue
            _process_deep(client, file, extractions_dir, report_text)
            processed += 1
            continue

        # First pass
        if _already_extracted(extractions_dir, file):
            print_info(f"  Skipping — already extracted")
            skipped += 1
            continue

        try:
            content = process_file(file)
        except Exception as exc:
            print_warning(f"  Could not read file: {exc}")
            failed += 1
            continue

        try:
            if content.source_type == "text":
                with timed_status("Extracting..."):
                    extraction = _process_text(client, content)
                out_path = extractions_dir / f"{file.stem}.json"
                write_json(out_path, extraction)
                print_success(
                    f"  {len(extraction.entities)} entities, "
                    f"{len(extraction.interactions)} interactions → {out_path.name}"
                )

            elif content.source_type == "image":
                with timed_status("Extracting..."):
                    extraction = _process_image(client, content)
                out_path = extractions_dir / f"{file.stem}.json"
                write_json(out_path, extraction)
                print_success(
                    f"  {len(extraction.entities)} entities, "
                    f"{len(extraction.connections_shown)} connections → {out_path.name}"
                )

            elif content.source_type == "pdf":
                _process_pdf(client, content, extractions_dir)

            elif content.source_type == "slide":
                _process_pptx(client, content, extractions_dir)

            processed += 1

        except Exception as exc:
            print_warning(f"  Extraction failed: {exc}")
            failed += 1

    console.print()
    print_success(f"Done — {processed} processed, {skipped} skipped, {failed} failed")
    if not deep:
        console.print("\nNext step: [bold]gocam report[/bold] — synthesize all extractions")
