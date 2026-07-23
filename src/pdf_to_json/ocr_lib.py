"""
ocr_lib.py — Google Cloud Vision OCR layer for pdf-to-civiform.

Adds two capabilities on top of the existing PyMuPDF + Gemini pipeline:
  1. PDF type detection: determines whether a PDF has a selectable text layer
     ("digital") or is a flat/scanned image ("scanned").
  2. Cloud Vision OCR: rasterises each page and runs DOCUMENT_TEXT_DETECTION
     for scanned PDFs, producing plain text that can be sent to Gemini.

Setup:
    pip install google-cloud-vision
    gcloud auth application-default login        # or set GOOGLE_APPLICATION_CREDENTIALS
    gcloud services enable vision.googleapis.com
"""

from __future__ import annotations

import logging
from typing import Literal

import pymupdf  # PyMuPDF — already in python_dependencies.txt

# google-cloud-vision is an optional new dependency
try:
    from google.cloud import vision  # type: ignore
    _VISION_AVAILABLE = True
except ImportError:
    _VISION_AVAILABLE = False
    logging.warning(
        "google-cloud-vision not installed. "
        "Scanned PDF support unavailable. "
        "Run: pip install google-cloud-vision"
    )

# ── Tuneable constants ─────────────────────────────────────────────────────────

# Average chars-per-page below which a PDF is classified as "scanned".
# 50 is conservative — even sparse government forms typically exceed this.
DIGITAL_TEXT_THRESHOLD_CHARS_PER_PAGE = 50

# Cloud Vision is billed per page; cap to avoid runaway costs.
MAX_OCR_PAGES = 20

# DPI for page rasterisation. 200 dpi gives Vision API enough detail without
# generating excessively large payloads.
OCR_RENDER_DPI = 200


# ── Vision client factory ──────────────────────────────────────────────────────

def _build_vision_client():
    """
    Build a Vision ImageAnnotatorClient with explicit credentials.

    Credential resolution order:
      1. GOOGLE_APPLICATION_CREDENTIALS env var (standard ADC path)
      2. ~/google_vision_key.json  (convenience path for local dev)

    Raises:
        RuntimeError with an actionable message if no credentials are found.
    """
    import os
    from pathlib import Path

    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

    if not creds_path:
        fallback = Path.home() / "google_vision_key.json"
        if fallback.exists():
            creds_path = str(fallback)
            logging.info(f"Vision: using credentials from fallback path: {creds_path}")
        else:
            raise RuntimeError(
                "No Google Cloud credentials found for Cloud Vision API.\n"
                "To fix, either:\n"
                "  a) Set GOOGLE_APPLICATION_CREDENTIALS to a service account key JSON path, or\n"
                "  b) Place a service account key at ~/google_vision_key.json\n\n"
                "To create a key:\n"
                "  gcloud iam service-accounts keys create ~/google_vision_key.json \\\n"
                "    --iam-account=<SA_EMAIL> --project=<PROJECT_ID>\n"
                "Then mount it into the container:\n"
                "  -v ~/google_vision_key.json:/home/cf-user/google_vision_key.json:ro"
            )

    from google.oauth2 import service_account  # type: ignore
    credentials = service_account.Credentials.from_service_account_file(
        creds_path,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    logging.info(f"Vision: loaded credentials from {creds_path}")
    return vision.ImageAnnotatorClient(credentials=credentials)


# ── PDF type detection ─────────────────────────────────────────────────────────

def detect_pdf_type(pdf_bytes: bytes) -> Literal["digital", "scanned"]:
    """
    Inspect the PDF's text layer to decide which extraction path to use.

    Returns:
        "digital" — PyMuPDF found enough text; use the existing Gemini PDF path.
        "scanned" — Little/no selectable text; run Cloud Vision OCR first.
    """
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    page_count = len(doc)

    if page_count == 0:
        doc.close()
        logging.warning("PDF has 0 pages — treating as scanned.")
        return "scanned"

    total_chars = sum(len(page.get_text("text").strip()) for page in doc)
    doc.close()

    avg_chars = total_chars / page_count
    logging.info(
        f"PDF type detection: {page_count} pages, "
        f"{total_chars} chars total, {avg_chars:.1f} avg chars/page"
    )

    if avg_chars >= DIGITAL_TEXT_THRESHOLD_CHARS_PER_PAGE:
        logging.info("Detected PDF type: DIGITAL (text layer present)")
        return "digital"
    else:
        logging.info("Detected PDF type: SCANNED (sparse/no text layer)")
        return "scanned"


# ── Digital text extraction (existing path, exposed for reuse) ─────────────────

def extract_digital_text(pdf_bytes: bytes, max_pages: int = MAX_OCR_PAGES) -> str:
    """
    Extract native text from a digital PDF using PyMuPDF.
    This mirrors what Gemini would receive as inline text when given the PDF
    directly, but keeps it as a plain string for logging / fallback use.
    """
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    pages: list[str] = []
    for i, page in enumerate(doc):
        if i >= max_pages:
            logging.warning(f"Text extraction capped at {max_pages} pages.")
            break
        pages.append(f"--- Page {i + 1} ---\n{page.get_text('text')}")
    doc.close()
    text = "\n".join(pages)
    logging.info(f"Extracted {len(text)} chars from digital PDF.")
    return text


# ── Cloud Vision OCR ───────────────────────────────────────────────────────────

def _render_page_png(pdf_bytes: bytes, page_index: int, dpi: int = OCR_RENDER_DPI) -> bytes:
    """Rasterise one PDF page to PNG bytes at the given DPI."""
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    page = doc[page_index]
    zoom = dpi / 72  # PyMuPDF native resolution is 72 dpi
    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), colorspace=pymupdf.csRGB)
    png = pixmap.tobytes("png")
    doc.close()
    return png


def extract_text_with_vision_ocr(
    pdf_bytes: bytes,
    max_pages: int = MAX_OCR_PAGES,
    vision_client=None,
) -> str:
    """
    OCR a scanned PDF using Google Cloud Vision DOCUMENT_TEXT_DETECTION.

    Each page is rendered to PNG and sent to Vision individually.
    Page results are concatenated with page-boundary markers so the Gemini
    prompt can still reason about form structure.

    Args:
        pdf_bytes:      Raw PDF bytes.
        max_pages:      Maximum pages to OCR (cost guard).
        vision_client:  Optional pre-built ImageAnnotatorClient (useful for
                        testing with a mock client).

    Returns:
        Concatenated OCR text across all processed pages.

    Raises:
        RuntimeError: If google-cloud-vision is not installed.
    """
    if not _VISION_AVAILABLE:
        raise RuntimeError(
            "google-cloud-vision is not installed. "
            "Run: pip install google-cloud-vision"
        )

    client = vision_client or _build_vision_client()

    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    total_pages = len(doc)
    doc.close()

    pages_to_ocr = min(total_pages, max_pages)
    if total_pages > max_pages:
        logging.warning(
            f"PDF has {total_pages} pages; only the first {max_pages} will be OCR'd."
        )

    pages_text: list[str] = []
    for idx in range(pages_to_ocr):
        logging.info(f"OCR page {idx + 1}/{pages_to_ocr} ...")
        png_bytes = _render_page_png(pdf_bytes, idx)

        image = vision.Image(content=png_bytes)
        response = client.document_text_detection(image=image)

        if response.error.message:
            logging.error(f"Vision API error (page {idx + 1}): {response.error.message}")
            pages_text.append(f"--- Page {idx + 1} [OCR ERROR] ---\n")
            continue

        page_text = (
            response.full_text_annotation.text
            if response.full_text_annotation
            else ""
        )
        pages_text.append(f"--- Page {idx + 1} ---\n{page_text}")
        logging.info(f"  Page {idx + 1}: {len(page_text)} chars extracted.")

    full_text = "\n".join(pages_text)
    logging.info(
        f"Cloud Vision OCR complete: {len(full_text)} chars from {pages_to_ocr} pages."
    )
    return full_text


# ── Unified entry point ────────────────────────────────────────────────────────

def extract_text_from_pdf(
    pdf_bytes: bytes,
    force_ocr: bool = False,
    max_pages: int = MAX_OCR_PAGES,
    vision_client=None,
) -> tuple[str, Literal["digital", "scanned"]]:
    """
    Auto-detect PDF type and extract text using the appropriate method.

    Args:
        pdf_bytes:      Raw PDF bytes.
        force_ocr:      Always use Cloud Vision OCR, skip type detection.
        max_pages:      Max pages to process.
        vision_client:  Optional pre-built Vision client.

    Returns:
        (text, pdf_type) — extracted text string and the detected type.
    """
    pdf_type: Literal["digital", "scanned"] = (
        "scanned" if force_ocr else detect_pdf_type(pdf_bytes)
    )

    if pdf_type == "digital":
        text = extract_digital_text(pdf_bytes, max_pages=max_pages)
    else:
        text = extract_text_with_vision_ocr(
            pdf_bytes, max_pages=max_pages, vision_client=vision_client
        )

    return text, pdf_type
