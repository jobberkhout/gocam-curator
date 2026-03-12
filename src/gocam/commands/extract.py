"""gocam extract — extract entities and interactions from any input file."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import click
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn

from gocam.config import PDF_CHUNK_OVERLAP, get_pdf_chunk_pages
from gocam.models import Extraction
from gocam.services.llm import LLMClient, get_llm_client
from gocam.services.file_processor import (
    IMAGE_EXTENSIONS,
    PDF_EXTENSIONS,
    PPTX_EXTENSIONS,
    TEXT_EXTENSIONS,
    FileContent,
    process_file,
)
from gocam.services.pptx_reader import SlideContent
from gocam.utils.display import console, print_error, print_info, print_success, print_warning, timed_status
from gocam.utils.io import write_json
from gocam.utils.process import load_meta, resolve_process


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _dedup_entities(entities: list) -> list:
    """Deduplicate entities by name (case-insensitive), merging mentioned_activities.

    When merging, prefer the non-overlap copy (overlap_from_previous=False) so
    that the primary extraction's richer context is kept.
    """
    seen: dict[str, dict] = {}  # lowercase name → merged entity dict
    result: list = []
    for e in entities:
        key = (e.name or "").strip().lower()
        if not key:
            continue
        if key in seen:
            existing = seen[key]
            # Merge activities from duplicate into existing entry
            for act in e.mentioned_activities:
                if act not in existing.mentioned_activities:
                    existing.mentioned_activities.append(act)
            # If existing is overlap-only but new one isn't, swap in the richer copy
            if existing.overlap_from_previous and not getattr(e, "overlap_from_previous", False):
                idx = result.index(existing)
                # Preserve merged activities
                e.mentioned_activities = existing.mentioned_activities
                result[idx] = e
                seen[key] = e
        else:
            seen[key] = e
            result.append(e)
    return result


def _build_extraction(raw: dict, source: str, source_type: str) -> Extraction:
    """Merge Claude's response with authoritative source/timestamp fields."""
    raw["source"] = source
    raw["source_type"] = source_type
    raw["timestamp"] = _now()
    # Ensure required list fields are present
    for key in ("entities", "interactions", "connections_shown", "compartments_shown", "gaps", "questions_for_expert"):
        raw.setdefault(key, [])
    return Extraction.model_validate(raw)


def _process_text(client: LLMClient, content: FileContent) -> Extraction:
    user_msg = (
        f"Analyze the following text from: {content.source_path.name}\n\n"
        f"---\n{content.text}\n---\n\n"
        "Return extraction JSON as specified."
    )
    raw = client.call_text("extract_text", user_msg)
    return _build_extraction(raw, content.source_path.name, "text")


def _process_image(client: LLMClient, content: FileContent) -> Extraction:
    user_msg = (
        f"Source file: {content.source_path.name}\n\n"
        "Analyze the image above and return extraction JSON as specified."
    )
    raw = client.call_vision("extract_visual", user_msg, content.images)
    return _build_extraction(raw, content.source_path.name, "image")




def _split_pdf_pages(text: str) -> list[str]:
    """Split PDF text on [Page N] markers into individual page strings."""
    parts = re.split(r"(?=\[Page \d+\])", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _extract_chunk_recursive(
    client: LLMClient,
    page_texts: list[str],
    first_page_num: int,
    stem: str,
    source_name: str,
    extractions_dir: Path,
    results: list[Extraction],
    depth: int = 0,
) -> None:
    """Try to extract a chunk of pages; on failure, halve the chunk and recurse.

    Cascade: e.g. 8 → 4 → 2 → 1 pages per call.  If a single page still
    fails, log a warning and move on.
    """
    indent = "  " * depth
    n = len(page_texts)
    last_page_num = first_page_num + n - 1

    if n == 1:
        label = f"Page {first_page_num}"
        source_id = f"{stem}_page{first_page_num:02d}"
    else:
        label = f"Pages {first_page_num}–{last_page_num}"
        source_id = f"{stem}_pages{first_page_num:02d}-{last_page_num:02d}"

    chunk_text = "\n\n".join(page_texts)
    msg = (
        f"Analyze {label.lower()} of: {source_name}\n\n"
        f"Text content:\n---\n{chunk_text}\n---\n\n"
        "Return extraction JSON as specified."
    )

    try:
        raw = client.call_text("extract_text", msg)
        ext = _build_extraction(raw, source_id, "pdf")
        out = extractions_dir / f"{source_id}.json"
        write_json(out, ext)
        results.append(ext)
        print_success(
            f"{indent}{label}: {len(ext.entities)} entities"
            f", {len(ext.interactions)} interactions → {out.name}"
        )
    except Exception as exc:
        if n == 1:
            print_warning(f"{indent}{label}: failed — {exc}")
            return
        half = n // 2
        print_warning(
            f"{indent}{label}: output truncated — "
            f"splitting into sub-chunks of {half} page(s)"
        )
        for sub_start in range(0, n, half):
            sub = page_texts[sub_start : sub_start + half]
            _extract_chunk_recursive(
                client, sub, first_page_num + sub_start,
                stem, source_name, extractions_dir, results,
                depth=depth + 1,
            )


def _process_pdf(
    client: LLMClient,
    content: FileContent,
    extractions_dir: Path,
) -> list[Extraction]:
    """Extract from a PDF.

    Decision logic:
    - No text + no images  → warn and bail
    - No text + images     → scanned PDF; send images to visual prompt
    - chunk_pages is None  → single API call for the whole document (Anthropic)
    - chunk_pages = N      → split into N-page chunks (Gemini)
    """
    stem = content.source_path.stem
    total_text = content.text or ""
    pages = _split_pdf_pages(total_text)

    if content.skipped_pages_msg:
        print_info(content.skipped_pages_msg)
    else:
        print_info("No reference section detected")

    if not pages and not content.images:
        print_warning("No text or images extracted from PDF — is it a scanned (image-only) PDF?")
        return []

    # Scanned (image-only) PDF
    if not pages and content.images:
        user_msg = (
            f"Source file: {content.source_path.name}\n\n"
            f"{len(content.images)} page image(s) from the PDF are attached above.\n\n"
            "Analyze the images and return extraction JSON as specified."
        )
        raw = client.call_vision("extract_visual", user_msg, content.images)
        extraction = _build_extraction(raw, stem, "pdf")
        out = extractions_dir / f"{stem}.json"
        write_json(out, extraction)
        print_success(f"{len(extraction.entities)} entities → {out.name}")
        return [extraction]

    chunk_pages = get_pdf_chunk_pages()

    # Single-call path (chunk_pages is None → provider handles large contexts)
    if chunk_pages is None:
        images = content.images
        if images:
            img_instructions = (
                f"\n{len(images)} figure(s) extracted from the PDF are attached above.\n\n"
                "IMPORTANT — For each attached figure:\n"
                "- Record every protein/gene label visible in the figure as an entity.\n"
                "- Record every arrow, line, or spatial connection between proteins in "
                "`connections_shown` (from_entity, to_entity, arrow_type, implied_relation).\n"
                "- Record every compartment visible in the figure in `compartments_shown`.\n"
                "- Do NOT leave `connections_shown` or `compartments_shown` empty if the "
                "figures contain diagrams with arrows or labeled compartments.\n"
            )
        else:
            img_instructions = ""
        user_msg = (
            f"Analyze the following PDF: {content.source_path.name}"
            f"{img_instructions}\n\n"
            f"Text content:\n---\n{total_text}\n---\n\n"
            "Return extraction JSON as specified."
        )
        print_info(f"{len(pages)} pages, {len(total_text):,} chars — single API call")
        with timed_status("Extracting..."):
            if images:
                raw = client.call_vision("extract_text", user_msg, images)
            else:
                raw = client.call_text("extract_text", user_msg)
        extraction = _build_extraction(raw, stem, "pdf")
        out = extractions_dir / f"{stem}.json"
        write_json(out, extraction)
        print_success(
            f"{len(extraction.entities)} entities, "
            f"{len(extraction.interactions)} interactions → {out.name}"
        )
        return [extraction]

    # Chunked path (chunk_pages = N)
    overlap_chars = PDF_CHUNK_OVERLAP
    print_info(
        f"{len(pages)} pages, {len(total_text):,} chars — splitting into "
        f"chunks of {chunk_pages} pages"
        + (f" (overlap {overlap_chars} chars)" if overlap_chars else "")
    )
    chunks = [
        pages[i : i + chunk_pages]
        for i in range(0, len(pages), chunk_pages)
    ]
    results: list[Extraction] = []
    prev_chunk_text: str = ""  # used to compute overlap

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task = progress.add_task(
            f"Processing {len(pages)} pages in {len(chunks)} chunk(s)...",
            total=len(chunks),
        )

        for i, chunk in enumerate(chunks, start=1):
            start_page = (i - 1) * chunk_pages + 1
            end_page = min(i * chunk_pages, len(pages))
            chunk_text = "\n\n".join(chunk)

            # Build overlap prefix from end of previous chunk
            overlap_prefix = ""
            if i > 1 and overlap_chars and prev_chunk_text:
                tail = prev_chunk_text[-overlap_chars:]
                # Try to start at a sentence/paragraph boundary
                newline_pos = tail.find("\n")
                if newline_pos != -1 and newline_pos < len(tail) // 2:
                    tail = tail[newline_pos + 1:]
                overlap_prefix = (
                    "[OVERLAP FROM PREVIOUS CHUNK — included for context continuity. "
                    "Entities already extracted from this text should be marked "
                    "overlap_from_previous=true in your JSON output.]\n"
                    f"{tail}\n[END OVERLAP]\n\n"
                )

            prev_chunk_text = chunk_text

            # Attach images to the first chunk only
            images = content.images if i == 1 and content.images else []
            if images:
                img_note = (
                    f"\n{len(images)} figure(s) extracted from the PDF are attached above.\n\n"
                    "IMPORTANT — For each attached figure:\n"
                    "- Record every protein/gene label visible in the figure as an entity.\n"
                    "- Record every arrow, line, or spatial connection between proteins in "
                    "`connections_shown` (from_entity, to_entity, arrow_type, implied_relation).\n"
                    "- Record every compartment visible in the figure in `compartments_shown`.\n"
                )
            else:
                img_note = ""

            user_msg = (
                f"Analyze pages {start_page}–{end_page} of: {content.source_path.name}"
                f"{img_note}\n\n"
                f"Text content:\n---\n{overlap_prefix}{chunk_text}\n---\n\n"
                "Return extraction JSON as specified."
            )

            source_id = f"{stem}_pages{start_page:02d}-{end_page:02d}"

            progress.update(
                task,
                description=f"Pages {start_page}–{end_page} of {len(pages)}",
            )

            try:
                if images:
                    raw = client.call_vision("extract_text", user_msg, images)
                else:
                    raw = client.call_text("extract_text", user_msg)
                extraction = _build_extraction(raw, source_id, "pdf")
            except Exception as exc:
                if len(chunk) > 1:
                    # Recursively halve: e.g. 8→4→2→1
                    half = len(chunk) // 2
                    print_warning(
                        f"Pages {start_page}–{end_page}: output truncated — "
                        f"splitting into sub-chunks of {half} page(s)"
                    )
                    for sub_start in range(0, len(chunk), half):
                        sub = chunk[sub_start : sub_start + half]
                        _extract_chunk_recursive(
                            client, sub, start_page + sub_start,
                            stem, content.source_path.name,
                            extractions_dir, results, depth=1,
                        )
                else:
                    print_warning(f"Pages {start_page}–{end_page}: API error — {exc}")
                progress.advance(task)
                continue

            out = extractions_dir / f"{source_id}.json"
            write_json(out, extraction)
            results.append(extraction)
            print_success(
                f"Pages {start_page}–{end_page}: {len(extraction.entities)} entities"
                f", {len(extraction.interactions)} interactions → {out.name}"
            )
            progress.advance(task)

    # Programmatic summary for multi-chunk PDFs (same pattern as PPTX)
    if len(results) > 1:
        summary = Extraction(
            source=f"{stem}_summary",
            source_type="pdf",
            timestamp=_now(),
            entities=_dedup_entities([e for ext in results for e in ext.entities]),
            interactions=[i for ext in results for i in ext.interactions],
            connections_shown=[c for ext in results for c in ext.connections_shown],
            compartments_shown=list({
                comp for ext in results for comp in ext.compartments_shown
            }),
            gaps=[g for ext in results for g in ext.gaps],
            questions_for_expert=[q for ext in results for q in ext.questions_for_expert],
        )
        summary_path = extractions_dir / f"{stem}_summary.json"
        write_json(summary_path, summary)
        print_success(f"Summary saved → {summary_path.name}")

    return results


def _process_pptx(
    client: LLMClient,
    content: FileContent,
    extractions_dir: Path,
) -> list[Extraction]:
    """Process each slide individually, save per-slide JSONs, return all extractions."""
    stem = content.source_path.stem
    slides: list[SlideContent] = content.slides
    relevant: list[Extraction] = []
    notes_slides: list[SlideContent] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(
            f"Processing {len(slides)} slides...", total=len(slides)
        )

        for slide in slides:
            progress.update(task, description=f"Slide {slide.slide_number}/{len(slides)}")

            notes_note = (
                f"\nSpeaker notes:\n---\n{slide.notes}\n---"
                if slide.notes else "\nSpeaker notes: (none)"
            )
            user_msg = (
                f"Analyze slide {slide.slide_number} from: {content.source_path.name}\n\n"
                f"Slide text content:\n---\n{slide.text or '(no text)'}\n---"
                f"{notes_note}\n\n"
                + (f"{len(slide.images)} embedded image(s) are attached above.\n\n" if slide.images else "")
                + "Return extraction JSON if this slide has relevant biological content, "
                  "or {\"skip\": true, \"reason\": \"...\"} if it should be skipped."
            )

            try:
                if slide.images:
                    raw = client.call_vision("extract_slides", user_msg, slide.images)
                else:
                    raw = client.call_text("extract_slides", user_msg)
            except Exception as exc:
                print_warning(f"Slide {slide.slide_number}: API error — {exc}")
                progress.advance(task)
                continue

            if raw.get("skip") or (
                not raw.get("entities")
                and not raw.get("connections_shown")
                and not raw.get("interactions")
                and raw.get("reason")  # LLM returned a skip with reason but no skip flag
            ):
                reason = raw.get("reason", "not relevant")
                print_info(f"Slide {slide.slide_number}: skipped ({reason})")
                progress.advance(task)
                continue

            source_id = f"{stem}_slide{slide.slide_number:02d}"
            extraction = _build_extraction(raw, source_id, "slide")
            out_path = extractions_dir / f"{source_id}.json"
            write_json(out_path, extraction)
            relevant.append(extraction)
            print_success(f"Slide {slide.slide_number}: {len(extraction.entities)} entities → {out_path.name}")

            if slide.notes:
                notes_slides.append(slide)

            progress.advance(task)

    # Process consolidated notes as a text extraction
    if notes_slides:
        notes_text = "\n\n".join(
            f"[Slide {s.slide_number} notes]\n{s.notes}" for s in notes_slides
        )
        notes_msg = (
            f"Speaker notes from: {content.source_path.name}\n\n"
            f"---\n{notes_text}\n---\n\n"
            "Return extraction JSON as specified."
        )
        try:
            raw = client.call_text("extract_text", notes_msg)
            notes_ext = _build_extraction(raw, f"{stem}_notes", "text")
            notes_path = extractions_dir / f"{stem}_notes.json"
            write_json(notes_path, notes_ext)
            print_success(f"Notes: {len(notes_ext.entities)} entities → {notes_path.name}")
            relevant.append(notes_ext)
        except Exception as exc:
            print_warning(f"Notes extraction failed: {exc}")

    # Save summary (programmatic merge of all relevant extractions)
    if relevant:
        summary = Extraction(
            source=f"{stem}_summary",
            source_type="slide",
            timestamp=_now(),
            entities=_dedup_entities([e for ext in relevant for e in ext.entities]),
            interactions=[i for ext in relevant for i in ext.interactions],
            connections_shown=[c for ext in relevant for c in ext.connections_shown],
            compartments_shown=list({
                comp for ext in relevant for comp in ext.compartments_shown
            }),
            gaps=[g for ext in relevant for g in ext.gaps],
            questions_for_expert=[q for ext in relevant for q in ext.questions_for_expert],
        )
        summary_path = extractions_dir / f"{stem}_summary.json"
        write_json(summary_path, summary)
        print_success(f"Summary saved → {summary_path.name}")

    return relevant


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

@click.command("extract")
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--process", "-p",
    default=None,
    help="Process name. Auto-detected if there is exactly one process.",
)
def extract_command(file: Path, process: str | None) -> None:
    """Extract entities and interactions from FILE using the LLM.

    To process every file in input/ at once, use 'gocam extract-all'.

    \b
    SUPPORTED FILE TYPES
      .txt  .md    Sent as text to the extract_text prompt.
      .png  .jpg   Sent as images to the extract_visual prompt.
      .pdf         Text extracted with PyMuPDF; embedded figures sent as images.
                   Anthropic: single API call for the whole document.
                   Gemini:    split into 8-page chunks (halves on failure: 8→4→2→1).
                   Reference sections are detected and skipped automatically.
      .pptx        Each slide processed individually with the extract_slides prompt.
                   Speaker notes are extracted and processed as a separate text source.

    \b
    OUTPUT  (saved to extractions/)
      {stem}.json              Text or image result (single file)
      {stem}_slide01.json      Per-slide results (PPTX)
      {stem}_pages01-02.json   Per-chunk results (PDF with Gemini)
      {stem}_summary.json      Merged summary (PPTX and chunked PDF)

    \b
    EXAMPLES
      gocam extract paper.pdf
      gocam extract slides.pptx --process vesicle-fusion
      gocam extract figure1.png
    """
    process_dir = resolve_process(process)
    meta = load_meta(process_dir)
    extractions_dir = process_dir / "extractions"
    extractions_dir.mkdir(exist_ok=True)

    console.print(
        f"[bold]Process:[/bold] {meta.get('process_name', process_dir.name)}  "
        f"[bold]File:[/bold] {file.name}"
    )

    suffix = file.suffix.lower()
    if suffix not in (TEXT_EXTENSIONS | IMAGE_EXTENSIONS | PPTX_EXTENSIONS | PDF_EXTENSIONS):
        print_error(f"Unsupported file type: '{suffix}'")
        raise SystemExit(1)

    try:
        content = process_file(file)
    except Exception as exc:
        print_error(f"Could not read file: {exc}")
        raise SystemExit(1)

    client = get_llm_client()

    try:
        if content.source_type == "text":
            with timed_status("Calling Claude API..."):
                extraction = _process_text(client, content)
            out_path = extractions_dir / f"{file.stem}.json"
            write_json(out_path, extraction)
            print_success(
                f"{len(extraction.entities)} entities, "
                f"{len(extraction.interactions)} interactions → {out_path.name}"
            )

        elif content.source_type == "image":
            with timed_status("Calling Claude Vision API..."):
                extraction = _process_image(client, content)
            out_path = extractions_dir / f"{file.stem}.json"
            write_json(out_path, extraction)
            print_success(
                f"{len(extraction.entities)} entities, "
                f"{len(extraction.connections_shown)} connections → {out_path.name}"
            )

        elif content.source_type == "pdf":
            _process_pdf(client, content, extractions_dir)

        elif content.source_type == "slide":
            _process_pptx(client, content, extractions_dir)

    except ValueError as exc:
        print_error(f"API response parsing failed: {exc}")
        raise SystemExit(1)
    except Exception as exc:
        print_error(f"Extraction failed: {exc}")
        raise SystemExit(1)
