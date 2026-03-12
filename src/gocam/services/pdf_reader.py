"""Extract text and images from PDF files using PyMuPDF."""

from __future__ import annotations

import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Reference-section detection (per-page)
# ---------------------------------------------------------------------------

# Section headers — a line that is short and contains a reference-section title.
# Allows optional numbering (e.g. "5.", "5.1 ", "V.") and trailing whitespace.
_REF_HEADER = re.compile(
    r"^\s*"
    r"(\d+[\.\d]*\s+|[IVXLC]+[\.\s]+)?"  # optional numbering
    r"(References|Bibliography|Literature\s+Cited|Works\s+Cited|"
    r"Reference\s+List|Cited\s+Literature|Sources)"
    r"\s*$",
    re.IGNORECASE,
)

# Numbered citation: [1] Author... or 1. Author...
_NUMBERED_CITATION = re.compile(r"^\s*(\[\d+\]|\d{1,3}[\.\)])\s+[A-Z]")

# Author-year citation: Surname, I. or Surname, Initial (2004)
_AUTHOR_YEAR = re.compile(
    r"[A-Z][a-z]{1,20},\s*[A-Z][\.\w]"  # "Smith, J." style author name
)
_YEAR_PAREN = re.compile(r"\(\d{4}[a-z]?\)")  # (2004) or (2004a)

# DOI / URL patterns common in reference lists
_DOI_URL = re.compile(r"doi[:\s]|https?://|pmid|pmc\d", re.IGNORECASE)

# Journal-style volume/page: e.g. "123, 456-789" or "123: 456"
_JOURNAL_REF = re.compile(r"\b\d{1,4}\s*[,:]\s*\d{2,6}[-–]\d{2,6}\b")


def _is_ref_header_line(line: str) -> bool:
    """Check if a line is a standalone reference-section heading."""
    s = line.strip()
    return 0 < len(s) < 60 and bool(_REF_HEADER.match(s))


def _reference_score(line: str) -> float:
    """Score how likely a non-empty line is part of a reference list (0–1)."""
    s = line.strip()
    if not s:
        return 0.0

    signals = 0.0
    # Numbered citation start is a strong signal
    if _NUMBERED_CITATION.match(s):
        signals += 0.5
    # Author name pattern
    if _AUTHOR_YEAR.search(s):
        signals += 0.25
    # Year in parentheses
    if _YEAR_PAREN.search(s):
        signals += 0.25
    # DOI or URL
    if _DOI_URL.search(s):
        signals += 0.25
    # Journal volume/page pattern
    if _JOURNAL_REF.search(s):
        signals += 0.15

    return min(signals, 1.0)


def _page_is_references(page_text: str, has_header: bool = False) -> bool:
    """Decide whether a page is (part of) a reference section.

    A page counts as references if:
    - It contains a reference header, OR
    - More than 50% of its non-empty lines score as citation-like
      (lowered to 40% if a previous page already had the header).
    """
    lines = page_text.split("\n")
    non_empty = [l for l in lines if l.strip()]

    if not non_empty:
        return False

    # Check for a header on this page
    for line in non_empty[:8]:  # header is usually near the top
        if _is_ref_header_line(line):
            return True

    # Score each line
    scores = [_reference_score(l) for l in non_empty]
    avg_score = sum(scores) / len(scores)

    # If we already found the header on a previous page, be more lenient
    threshold = 0.25 if has_header else 0.35

    return avg_score >= threshold


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def read_pdf(path: Path) -> tuple[str, list[bytes], str | None]:
    """Extract text and embedded images from a PDF, dropping reference pages.

    Works per-page: once a reference page is detected, all subsequent pages
    are dropped (references are always at the end of a paper).

    Returns:
        text: concatenated page text with [Page N] markers
        images: raw image bytes from content pages only
        skipped_msg: note about which pages were dropped, or None
    """
    import fitz  # PyMuPDF

    doc = fitz.open(str(path))
    total_pages = len(doc)

    # First pass: extract text per page so we can detect references
    page_texts: list[tuple[int, str]] = []  # (1-based page num, text)
    for page in doc:
        page_num = page.number + 1
        page_text = page.get_text().strip()
        page_texts.append((page_num, page_text))

    # Find the first reference page.
    # Skip the first 3 pages — journal articles sometimes start with a
    # reference list (e.g. citing info on the cover page) that is not the
    # actual trailing reference section we want to strip.
    _SKIP_EARLY_PAGES = 3
    ref_start_page: int | None = None
    header_found = False
    for page_num, text in page_texts:
        if page_num <= _SKIP_EARLY_PAGES:
            continue
        if _page_is_references(text, has_header=header_found):
            # On the first hit, check if the header is on this page
            if not header_found:
                lines = text.split("\n")
                header_found = any(_is_ref_header_line(l) for l in lines[:8])

                # If this page has a header but also substantial non-reference
                # content above it, the references start on this page but we
                # may want to keep the top part.  For simplicity (and because
                # partial-page content before references is usually just the
                # last paragraph + the heading), we drop the whole page.

            if ref_start_page is None:
                ref_start_page = page_num
        else:
            # Reset if we haven't committed to a ref section yet.
            # This handles false positives on a single page.
            if ref_start_page is not None and not header_found:
                ref_start_page = None

    # Second pass: collect text and images only from content pages
    content_pages = (
        set(range(1, ref_start_page)) if ref_start_page else set(range(1, total_pages + 1))
    )

    text_parts: list[str] = []
    images: list[bytes] = []
    seen_xrefs: set[int] = set()

    for page in doc:
        page_num = page.number + 1
        if page_num not in content_pages:
            continue

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

    if ref_start_page is not None:
        skipped_msg = (
            f"Detected reference section starting at page {ref_start_page} — "
            f"skipped pages {ref_start_page}–{total_pages} "
            f"({total_pages - ref_start_page + 1} pages)"
        )
        return full_text, images, skipped_msg

    return full_text, images, None
