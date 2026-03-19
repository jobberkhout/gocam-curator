"""gocam extract-all — extract from every file in the process input/ directory."""

from __future__ import annotations

from pathlib import Path

import click

from gocam.commands.extract import (
    _build_extraction,
    _count_claims,
    _process_image,
    _process_pdf,
    _process_pptx,
    _process_text,
)
from gocam.config import get_pdf_chunk_pages
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
    """Return True if this input file already has an extraction JSON.

    For PDFs: respects the current chunk mode.  If PDF_CHUNK_PAGES is set
    (chunked mode), a previous single-call {stem}.json is NOT treated as
    done — the PDF will be re-extracted in chunks.  This lets users switch
    from single-call to chunked mode without manually deleting old files.
    """
    stem = file.stem
    suffix = file.suffix.lower()
    if suffix in TEXT_EXTENSIONS | IMAGE_EXTENSIONS:
        return (extractions_dir / f"{stem}.json").exists()
    if suffix in PDF_EXTENSIONS:
        has_chunks = any(extractions_dir.glob(f"{stem}_pages*.json"))
        has_single = (extractions_dir / f"{stem}.json").exists()
        if get_pdf_chunk_pages() is not None:
            # Chunked mode: only consider it done if chunked output exists
            return has_chunks
        else:
            # Single-call mode: done if any output exists
            return has_single or has_chunks
    if suffix in PPTX_EXTENSIONS:
        return any(extractions_dir.glob(f"{stem}_slide*.json"))
    return False


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

@click.command("extract-all")
@click.option(
    "--process", "-p",
    default=None,
    help="Process name. Auto-detected if there is exactly one process.",
)
def extract_all_command(process: str | None) -> None:
    """Extract GO-CAM claims from every supported file in input/.

    Processes .txt, .md, .pdf, .pptx, .png, and .jpg files. Files that
    already have a corresponding extraction JSON are skipped automatically.

    \b
    OUTPUT  (saved to extractions/)
      Same layout as 'gocam extract' for each file.

    \b
    EXAMPLES
      gocam extract-all
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
        f"[bold]Files:[/bold] {len(input_files)}"
    )

    # Count already-done files
    already_done = sum(1 for f in input_files if _already_extracted(extractions_dir, f))
    if already_done:
        print_info(
            f"Resuming — {already_done}/{len(input_files)} file(s) already processed, "
            f"{len(input_files) - already_done} remaining"
        )

    client = get_llm_client()
    skipped = processed = failed = 0

    for i, file in enumerate(input_files, start=1):
        print_info(f"Processing file {i}/{len(input_files)}: {file.name}")

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
                    ext = _process_text(client, content)
                out_path = extractions_dir / f"{file.stem}.json"
                write_json(out_path, ext)
                nodes, edges = _count_claims(ext)
                print_success(f"  {nodes} nodes, {edges} edges → {out_path.name}")

            elif content.source_type == "image":
                with timed_status("Extracting..."):
                    ext = _process_image(client, content)
                out_path = extractions_dir / f"{file.stem}.json"
                write_json(out_path, ext)
                nodes, edges = _count_claims(ext)
                print_success(f"  {nodes} nodes, {edges} edges → {out_path.name}")

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
    console.print("\nNext step: [bold]gocam validate[/bold] — verify all claims against databases")
