"""gocam extract — single-pass GO-CAM claim extraction from any input file."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import click
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn

from gocam.config import PDF_CHUNK_OVERLAP, get_pdf_chunk_pages, get_text_chunk_chars
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


# PubMed IDs are 7–9 digits; require no adjacent digit so we don't grab
# partial numbers from longer sequences (e.g. DOI registrant codes).
_PMID_DIGITS_RE = re.compile(r"(?<!\d)(\d{7,9})(?!\d)")


def _pmid_from_filename(path: Path) -> str | None:
    """Extract a PMID from the filename stem if it contains a 7–9 digit number.

    Supports naming conventions like:
      20357116.pdf          → "20357116"
      fig_20357116.png      → "20357116"
      fig-20357116.jpg      → "20357116"
    Returns None for PPTX slides, DOI-named files, etc.
    """
    m = _PMID_DIGITS_RE.search(path.stem)
    return m.group(1) if m else None


def _build_extraction(
    raw: dict,
    source: str,
    source_type: str,
    source_doi: str | None = None,
    source_pmid: str | None = None,
) -> dict:
    """Normalize the LLM response into a standard extraction dict."""
    raw["source"] = source
    raw["source_type"] = source_type
    raw["timestamp"] = _now()
    if source_doi:
        raw["source_doi"] = source_doi
    if source_pmid:
        raw["source_pmid"] = source_pmid
    raw.setdefault("claims", [])
    return raw


def _count_claims(data: dict) -> tuple[int, int]:
    """Return (node_count, edge_count) from a claims list."""
    claims = data.get("claims", [])
    nodes = sum(1 for c in claims if c.get("type") == "node")
    edges = sum(1 for c in claims if c.get("type") == "edge")
    return nodes, edges


def _split_pdf_pages(text: str) -> list[str]:
    """Split PDF text on [Page N] markers into individual page strings."""
    parts = re.split(r"(?=\[Page \d+\])", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _split_text_chunks(text: str, chunk_chars: int) -> list[str]:
    """Split text into chunks of at most chunk_chars at paragraph boundaries."""
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_chars
        if end >= len(text):
            chunks.append(text[start:])
            break
        # Prefer cutting at a paragraph break (double newline)
        cut = text.rfind("\n\n", start, end)
        if cut == -1:
            cut = text.rfind("\n", start, end)
        if cut <= start:
            cut = end
        chunks.append(text[start:cut])
        start = cut
    return [c.strip() for c in chunks if c.strip()]


# ---------------------------------------------------------------------------
# Single-call extraction (text, image, single-chunk)
# ---------------------------------------------------------------------------

def _process_text(client: LLMClient, content: FileContent) -> dict:
    """Extract from a text file, chunking when the provider needs it."""
    text = content.text or ""
    chunk_chars = get_text_chunk_chars()
    source_pmid = _pmid_from_filename(content.source_path)

    # Single-call path
    if not chunk_chars or len(text) <= chunk_chars:
        user_msg = (
            f"Source file: {content.source_path.name}\n\n"
            f"---\n{text}\n---\n\n"
            "Extract GO-CAM claims as specified."
        )
        raw = client.call_text("extract", user_msg)
        return _build_extraction(raw, content.source_path.name, "text", source_pmid=source_pmid)

    # Chunked path — merge claims from all chunks
    chunks = _split_text_chunks(text, chunk_chars)
    print_info(
        f"{len(text):,} chars — splitting into {len(chunks)} chunk(s) "
        f"of ~{chunk_chars:,} chars"
    )
    all_claims: list[dict] = []
    seen_ids: set[str] = set()

    for i, chunk in enumerate(chunks, start=1):
        user_msg = (
            f"Analyze part {i}/{len(chunks)} of: {content.source_path.name}\n\n"
            f"---\n{chunk}\n---\n\n"
            "Extract GO-CAM claims as specified."
        )
        try:
            raw = client.call_text("extract", user_msg)
        except Exception as exc:
            print_warning(f"  Part {i}/{len(chunks)}: failed — {exc}")
            continue

        for claim in raw.get("claims", []):
            cid = claim.get("id", "")
            # Re-ID to avoid collisions across chunks
            new_id = f"C{i}_{cid}" if cid in seen_ids else cid
            if cid:
                seen_ids.add(new_id)
            claim["id"] = new_id
            all_claims.append(claim)

        nodes = sum(1 for c in raw.get("claims", []) if c.get("type") == "node")
        edges = sum(1 for c in raw.get("claims", []) if c.get("type") == "edge")
        print_success(f"  Part {i}/{len(chunks)}: {nodes} nodes, {edges} edges")

    merged = {"claims": all_claims}
    return _build_extraction(merged, content.source_path.name, "text", source_pmid=source_pmid)


def _process_image(client: LLMClient, content: FileContent) -> dict:
    source_pmid = _pmid_from_filename(content.source_path)
    user_msg = (
        f"Source file: {content.source_path.name}\n\n"
        "Analyze the image(s) above and extract GO-CAM claims as specified."
    )
    raw = client.call_vision("extract", user_msg, content.images)
    return _build_extraction(raw, content.source_path.name, "image", source_pmid=source_pmid)


# ---------------------------------------------------------------------------
# Recursive chunk extraction for PDFs
# ---------------------------------------------------------------------------

def _extract_chunk_recursive(
    client: LLMClient,
    page_texts: list[str],
    first_page_num: int,
    stem: str,
    source_name: str,
    extractions_dir: Path,
    results: list[dict],
    depth: int = 0,
    source_doi: str | None = None,
    source_pmid: str | None = None,
) -> None:
    """Try to extract a chunk of pages; on failure, halve the chunk and recurse."""
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
        "Extract GO-CAM claims as specified."
    )

    try:
        raw = client.call_text("extract", msg)
        ext = _build_extraction(raw, source_id, "pdf", source_doi=source_doi, source_pmid=source_pmid)
        out = extractions_dir / f"{source_id}.json"
        write_json(out, ext)
        results.append(ext)
        nodes, edges = _count_claims(ext)
        print_success(f"{indent}{label}: {nodes} nodes, {edges} edges → {out.name}")
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
                source_doi=source_doi,
                source_pmid=source_pmid,
            )


def _process_pdf(
    client: LLMClient,
    content: FileContent,
    extractions_dir: Path,
) -> list[dict]:
    """Extract GO-CAM claims from a PDF."""
    stem = content.source_path.stem
    total_text = content.text or ""
    pages = _split_pdf_pages(total_text)

    if content.skipped_pages_msg:
        print_info(content.skipped_pages_msg)
    else:
        print_info("No reference section detected")

    source_doi = content.source_doi
    source_pmid = _pmid_from_filename(content.source_path)
    if source_pmid:
        print_info(f"Source PMID from filename: {source_pmid}")
    elif source_doi:
        print_info(f"Source DOI detected: {source_doi}")

    if not pages and not content.images:
        print_warning("No text or images extracted from PDF")
        return []

    # Scanned (image-only) PDF
    if not pages and content.images:
        user_msg = (
            f"Source file: {content.source_path.name}\n\n"
            f"{len(content.images)} page image(s) from the PDF are attached above.\n\n"
            "Analyze the images and extract GO-CAM claims as specified."
        )
        raw = client.call_vision("extract", user_msg, content.images)
        ext = _build_extraction(raw, stem, "pdf", source_doi=source_doi, source_pmid=source_pmid)
        out = extractions_dir / f"{stem}.json"
        write_json(out, ext)
        nodes, edges = _count_claims(ext)
        print_success(f"{nodes} nodes, {edges} edges → {out.name}")
        return [ext]

    chunk_pages = get_pdf_chunk_pages()

    # Single-call path
    if chunk_pages is None:
        images = content.images
        img_note = ""
        if images:
            img_note = (
                f"\n{len(images)} figure(s) extracted from the PDF are attached above.\n\n"
                "For each figure: extract visible protein labels, arrows/connections, "
                "and compartments as GO-CAM claims.\n"
            )
        user_msg = (
            f"Analyze the following PDF: {content.source_path.name}"
            f"{img_note}\n\n"
            f"Text content:\n---\n{total_text}\n---\n\n"
            "Extract GO-CAM claims as specified."
        )
        print_info(f"{len(pages)} pages, {len(total_text):,} chars — single API call")
        with timed_status("Extracting..."):
            if images:
                raw = client.call_vision("extract", user_msg, images)
            else:
                raw = client.call_text("extract", user_msg)
        ext = _build_extraction(raw, stem, "pdf", source_doi=source_doi, source_pmid=source_pmid)
        out = extractions_dir / f"{stem}.json"
        write_json(out, ext)
        nodes, edges = _count_claims(ext)
        print_success(f"{nodes} nodes, {edges} edges → {out.name}")
        return [ext]

    # Chunked path
    overlap_chars = PDF_CHUNK_OVERLAP
    print_info(
        f"{len(pages)} pages, {len(total_text):,} chars — splitting into "
        f"chunks of {chunk_pages} pages"
    )
    chunks = [pages[i : i + chunk_pages] for i in range(0, len(pages), chunk_pages)]
    results: list[dict] = []
    prev_chunk_text: str = ""

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

            # Overlap prefix
            overlap_prefix = ""
            if i > 1 and overlap_chars and prev_chunk_text:
                tail = prev_chunk_text[-overlap_chars:]
                newline_pos = tail.find("\n")
                if newline_pos != -1 and newline_pos < len(tail) // 2:
                    tail = tail[newline_pos + 1:]
                overlap_prefix = (
                    "[OVERLAP FROM PREVIOUS CHUNK — for context only, "
                    "do not extract claims already covered.]\n"
                    f"{tail}\n[END OVERLAP]\n\n"
                )
            prev_chunk_text = chunk_text

            # Images only with first chunk
            images = content.images if i == 1 and content.images else []
            img_note = ""
            if images:
                img_note = (
                    f"\n{len(images)} figure(s) from the PDF are attached above.\n"
                    "Extract visible labels, arrows, and compartments as claims.\n"
                )

            user_msg = (
                f"Analyze pages {start_page}–{end_page} of: {content.source_path.name}"
                f"{img_note}\n\n"
                f"Text content:\n---\n{overlap_prefix}{chunk_text}\n---\n\n"
                "Extract GO-CAM claims as specified."
            )

            source_id = f"{stem}_pages{start_page:02d}-{end_page:02d}"

            progress.update(
                task,
                description=f"Pages {start_page}–{end_page} of {len(pages)}",
            )

            try:
                if images:
                    raw = client.call_vision("extract", user_msg, images)
                else:
                    raw = client.call_text("extract", user_msg)
                ext = _build_extraction(raw, source_id, "pdf", source_doi=source_doi, source_pmid=source_pmid)
            except Exception:
                if len(chunk) > 1:
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
                            source_doi=source_doi,
                            source_pmid=source_pmid,
                        )
                else:
                    print_warning(f"Pages {start_page}–{end_page}: extraction failed")
                progress.advance(task)
                continue

            out = extractions_dir / f"{source_id}.json"
            write_json(out, ext)
            results.append(ext)
            nodes, edges = _count_claims(ext)
            print_success(
                f"Pages {start_page}–{end_page}: {nodes} nodes, {edges} edges → {out.name}"
            )
            progress.advance(task)

    # Summary for multi-chunk PDFs
    if len(results) > 1:
        all_claims = [c for ext in results for c in ext.get("claims", [])]
        summary = {
            "source": f"{stem}_summary",
            "source_type": "pdf",
            "timestamp": _now(),
            "claims": all_claims,
        }
        summary_path = extractions_dir / f"{stem}_summary.json"
        write_json(summary_path, summary)
        nodes, edges = _count_claims(summary)
        print_success(f"Summary: {nodes} nodes, {edges} edges → {summary_path.name}")

    return results


def _process_pptx(
    client: LLMClient,
    content: FileContent,
    extractions_dir: Path,
) -> list[dict]:
    """Process each slide individually."""
    stem = content.source_path.stem
    slides: list[SlideContent] = content.slides
    results: list[dict] = []
    source_pmid = _pmid_from_filename(content.source_path)  # None for most presentations

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
                + "Extract GO-CAM claims as specified. "
                  "Return {\"skip\": true, \"reason\": \"...\"} if no relevant biological content."
            )

            try:
                if slide.images:
                    raw = client.call_vision("extract", user_msg, slide.images)
                else:
                    raw = client.call_text("extract", user_msg)
            except Exception as exc:
                print_warning(f"Slide {slide.slide_number}: API error — {exc}")
                progress.advance(task)
                continue

            if raw.get("skip"):
                reason = raw.get("reason", "not relevant")
                print_info(f"Slide {slide.slide_number}: skipped ({reason})")
                progress.advance(task)
                continue

            source_id = f"{stem}_slide{slide.slide_number:02d}"
            ext = _build_extraction(raw, source_id, "slide", source_pmid=source_pmid)
            out_path = extractions_dir / f"{source_id}.json"
            write_json(out_path, ext)
            results.append(ext)
            nodes, edges = _count_claims(ext)
            print_success(f"Slide {slide.slide_number}: {nodes} nodes, {edges} edges → {out_path.name}")
            progress.advance(task)

    # Summary
    if results:
        all_claims = [c for ext in results for c in ext.get("claims", [])]
        summary = {
            "source": f"{stem}_summary",
            "source_type": "slide",
            "timestamp": _now(),
            "claims": all_claims,
        }
        summary_path = extractions_dir / f"{stem}_summary.json"
        write_json(summary_path, summary)
        nodes, edges = _count_claims(summary)
        print_success(f"Summary: {nodes} nodes, {edges} edges → {summary_path.name}")

    return results


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
    """Extract GO-CAM claims from FILE using the LLM.

    Single-pass extraction that outputs claims in GO-CAM structure
    (nodes = molecular activities, edges = causal relations).

    To process every file in input/ at once, use 'gocam extract-all'.

    \b
    SUPPORTED FILE TYPES
      .txt  .md    Sent as text to the extraction prompt.
      .png  .jpg   Sent as images to the extraction prompt.
      .pdf         Text extracted with PyMuPDF; embedded figures sent as images.
                   Gemini/Vertex: split into 8-page chunks (halves on failure: 8→4→2→1).
                   Reference sections are detected and skipped automatically.
      .pptx        Each slide processed individually.

    \b
    OUTPUT  (saved to extractions/)
      {stem}.json              Single-file extraction
      {stem}_slide01.json      Per-slide results (PPTX)
      {stem}_pages01-08.json   Per-chunk results (PDF, chunked)
      {stem}_summary.json      Merged claims (PPTX and chunked PDF)

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
            with timed_status("Extracting claims..."):
                ext = _process_text(client, content)
            out_path = extractions_dir / f"{file.stem}.json"
            write_json(out_path, ext)
            nodes, edges = _count_claims(ext)
            print_success(f"{nodes} nodes, {edges} edges → {out_path.name}")

        elif content.source_type == "image":
            with timed_status("Extracting claims from image..."):
                ext = _process_image(client, content)
            out_path = extractions_dir / f"{file.stem}.json"
            write_json(out_path, ext)
            nodes, edges = _count_claims(ext)
            print_success(f"{nodes} nodes, {edges} edges → {out_path.name}")

        elif content.source_type == "pdf":
            _process_pdf(client, content, extractions_dir)

        elif content.source_type == "slide":
            _process_pptx(client, content, extractions_dir)

    except ValueError as exc:
        print_error(f"Response parsing failed: {exc}")
        raise SystemExit(1)
    except Exception as exc:
        print_error(f"Extraction failed: {exc}")
        raise SystemExit(1)

    console.print("\nNext step: [bold]gocam validate[/bold] — verify all claims against databases")
