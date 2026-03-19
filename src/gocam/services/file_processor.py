"""File type detection and content extraction dispatcher."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from gocam.services.pptx_reader import SlideContent

TEXT_EXTENSIONS: frozenset[str] = frozenset({".txt", ".md"})
IMAGE_EXTENSIONS: frozenset[str] = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp"})
PPTX_EXTENSIONS: frozenset[str] = frozenset({".pptx"})
PDF_EXTENSIONS: frozenset[str] = frozenset({".pdf"})

SUPPORTED_EXTENSIONS: frozenset[str] = (
    TEXT_EXTENSIONS | IMAGE_EXTENSIONS | PPTX_EXTENSIONS | PDF_EXTENSIONS
)


@dataclass
class FileContent:
    """Normalised content extracted from any supported file type."""

    source_path: Path
    source_type: str                              # "text" | "image" | "slide" | "pdf"
    text: str | None = None                       # textual content (text, pdf)
    images: list[bytes] = field(default_factory=list)  # raw image bytes (image, pdf)
    slides: list[SlideContent] = field(default_factory=list)  # PPTX slides
    skipped_pages_msg: str | None = None          # set when PDF reference pages are dropped
    source_doi: str | None = None                 # DOI found in the PDF (first 2 pages)


def process_file(path: Path) -> FileContent:
    """Detect file type and extract content.

    Raises:
        ValueError: if the file extension is not supported.
    """
    suffix = path.suffix.lower()

    if suffix in TEXT_EXTENSIONS:
        return FileContent(
            source_path=path,
            source_type="text",
            text=path.read_text(encoding="utf-8"),
        )

    if suffix in IMAGE_EXTENSIONS:
        return FileContent(
            source_path=path,
            source_type="image",
            images=[path.read_bytes()],
        )

    if suffix in PPTX_EXTENSIONS:
        from gocam.services.pptx_reader import read_pptx
        return FileContent(
            source_path=path,
            source_type="slide",
            slides=read_pptx(path),
        )

    if suffix in PDF_EXTENSIONS:
        from gocam.services.pdf_reader import extract_doi, read_pdf
        text, images, skipped_msg = read_pdf(path)
        # Extract the paper's own DOI from the header region only.
        # Limit to the first [Page 1] / [Page 2] block — typically title,
        # authors, journal, abstract — where the DOI stamp appears.
        # Using only 10 paragraphs avoids picking up cited papers' DOIs
        # from the introduction or body text.
        first_pages = "\n".join(text.split("\n\n")[:10]) if text else ""
        source_doi = extract_doi(first_pages)
        return FileContent(
            source_path=path,
            source_type="pdf",
            text=text,
            images=images,
            skipped_pages_msg=skipped_msg,
            source_doi=source_doi,
        )

    raise ValueError(
        f"Unsupported file type: '{suffix}'. "
        f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
    )
