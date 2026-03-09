"""Extract text and images from PDF files using PyMuPDF."""

from __future__ import annotations

import re
from pathlib import Path

# Minimum consecutive citation lines required to confirm a reference section.
_MIN_CITATION_BLOCK = 5

# ---------------------------------------------------------------------------
# Method A — section header
# Standalone line (< 50 chars) containing only the section title, optionally
# preceded by a section number such as "5." or "5.1 ".
# ---------------------------------------------------------------------------
_REF_HEADER = re.compile(
    r"^(\d+[\.\d]*\s+)?"
    r"(References|Bibliography|Literature\s+Cited|Works\s+Cited)"
    r"\s*$",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Method B — numbered citation lines
# Each line starts with [N] or N. or N) (1–3 digits) followed by a capital
# letter, AND the line contains an author-name or year-in-parens signal.
# ---------------------------------------------------------------------------
_CITATION_MARKER = re.compile(r"^(\[\d+\]|\d{1,3}[\.\)])\s+[A-Z]")
_AUTHOR_OR_YEAR = re.compile(r"[A-Z][a-z]+,\s*[A-Z]\.?|\(\d{4}[a-z]?\)")


def _is_ref_header(line: str) -> bool:
    """Method A: standalone references/bibliography heading."""
    s = line.strip()
    return len(s) < 50 and bool(_REF_HEADER.match(s))


def _is_citation_line(line: str) -> bool:
    """Method B: numbered reference-list entry."""
    s = line.strip()
    return bool(_CITATION_MARKER.match(s) and _AUTHOR_OR_YEAR.search(s))


def _find_ref_cut(lines: list[str]) -> int | None:
    """Return the line index where the reference section starts, or None.

    Method A finds the first standalone heading; Method B finds the first run
    of _MIN_CITATION_BLOCK+ citation lines.  The earlier candidate is used.
    A safety pass then requires _MIN_CITATION_BLOCK consecutive citation lines
    to follow the cut point (blank lines are neutral; non-empty non-citation
    lines reset the counter).  Returns None if the safety check fails.
    """
    # Method A: first standalone header
    header_idx: int | None = None
    for i, line in enumerate(lines):
        if _is_ref_header(line):
            header_idx = i
            break

    # Method B: first run of _MIN_CITATION_BLOCK+ citation lines
    block_start_idx: int | None = None
    run = 0
    run_start = 0
    for i, line in enumerate(lines):
        if _is_citation_line(line):
            if run == 0:
                run_start = i
            run += 1
            if run >= _MIN_CITATION_BLOCK:
                block_start_idx = run_start
                break
        else:
            run = 0

    candidates = [idx for idx in (header_idx, block_start_idx) if idx is not None]
    if not candidates:
        return None

    cut = min(candidates)

    # Safety check: scan for _MIN_CITATION_BLOCK consecutive citation lines.
    # Start from the line after a header; from the block itself otherwise.
    check_from = (cut + 1) if (header_idx is not None and cut == header_idx) else cut
    consecutive = 0
    for i in range(check_from, len(lines)):
        if _is_citation_line(lines[i]):
            consecutive += 1
            if consecutive >= _MIN_CITATION_BLOCK:
                return cut
        elif lines[i].strip():  # non-empty, non-citation line resets the run
            consecutive = 0

    return None  # safety check failed — not enough citation lines found


def read_pdf(path: Path) -> tuple[str, list[bytes], str | None]:
    """Extract text and embedded images from a PDF, stopping at the references section.

    Returns:
        text: concatenated page text with [Page N] markers
        images: raw image bytes from content pages only
        skipped_msg: note if reference pages were dropped, else None
    """
    import fitz  # PyMuPDF

    doc = fitz.open(str(path))
    text_parts: list[str] = []
    images: list[bytes] = []
    seen_xrefs: set[int] = set()
    total_pages = len(doc)

    for page in doc:
        page_num = page.number + 1
        page_text = page.get_text().strip()
        if page_text:
            text_parts.append(f"[Page {page_num}]\n{page_text}")

        for img_ref in page.get_images(full=True):
            xref = img_ref[0]
            if xref in seen_xrefs:
                continue
            seen_xrefs.add(xref)
            try:
                base_image = doc.extract_image(xref)
                img_bytes = base_image.get("image")
                if img_bytes and len(img_bytes) > 1024:  # skip tiny icons
                    images.append(img_bytes)
            except Exception:
                pass

    doc.close()

    full_text = "\n\n".join(text_parts)
    lines = full_text.split("\n")
    cut_line_idx = _find_ref_cut(lines)

    if cut_line_idx is None:
        return full_text, images, None

    # Convert line index → character offset, then trim trailing whitespace.
    cut_char_offset = sum(len(line) + 1 for line in lines[:cut_line_idx])
    text_before = full_text[:cut_char_offset].rstrip()

    # Determine which page the cut falls on from the last [Page N] marker before it.
    page_markers = list(re.finditer(r"\[Page (\d+)\]", text_before))
    ref_start_page = int(page_markers[-1].group(1)) if page_markers else 1

    skipped_msg = f"Skipped pages {ref_start_page}–{total_pages} (references)"
    return text_before, images, skipped_msg
