"""
ocr_text_to_json.py — Rule-based heuristic parser for converting raw OCR text
into the intermediary JSON format expected by convert_to_civiform_json.

This module provides a Gemini-free path: after Tesseract extracts text from a
scanned PDF, this parser identifies form fields using pattern matching and
produces structured JSON that can be fed directly into the CiviForm converter.

This is a PROTOTYPE — heuristic parsing will not match LLM quality. It handles
common government form patterns (labeled fields, checkboxes, radio buttons,
date/email/phone/address fields) but may miss complex layouts.
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any

# ── Pattern constants ──────────────────────────────────────────────────────────

# Checkbox markers found in OCR output
_CHECKBOX_MARKERS = re.compile(
    r'[☐☑✓✗✘□■▢▣\u2610\u2611\u2612]'
    r'|\[\s*[xX]?\s*\]'
    r'|\(\s*[xX]?\s*\)',
)

# Radio button markers
_RADIO_MARKERS = re.compile(
    r'[○●◯◉]'
    r'|\(\s*\)'
    r'|\(\s*[•·]\s*\)',
)

# Underline blanks (fill-in fields): 3+ underscores or dashes
_BLANK_LINE = re.compile(r'[_]{3,}|[-]{5,}')

# Common date labels
_DATE_LABELS = re.compile(
    r'\b(date\s*(of\s*birth)?|dob|birth\s*date|expiration\s*date'
    r'|start\s*date|end\s*date|effective\s*date|mm\s*/\s*dd\s*/\s*yyyy'
    r'|month\s*/\s*day\s*/\s*year)\b',
    re.IGNORECASE,
)

# Common email labels
_EMAIL_LABELS = re.compile(
    r'\b(e[-\s]?mail(\s*address)?)\b',
    re.IGNORECASE,
)

# Common phone labels
_PHONE_LABELS = re.compile(
    r'\b(phone|telephone|cell|mobile|fax)(\s*(number|#|no\.?))?\b',
    re.IGNORECASE,
)

# Common address labels
_ADDRESS_LABELS = re.compile(
    r'\b(address|street|city\s*[,/]\s*state\s*[,/]\s*zip'
    r'|mailing\s*address|residential\s*address'
    r'|home\s*address|work\s*address)\b',
    re.IGNORECASE,
)

# Common name labels
_NAME_LABELS = re.compile(
    r'\b(full\s*name|first\s*name|last\s*name|middle\s*name'
    r'|applicant\s*name|name\s*of\s*(applicant|claimant|employee))\b',
    re.IGNORECASE,
)

# Currency labels
_CURRENCY_LABELS = re.compile(
    r'\b(amount|income|salary|wage|rent|payment|earnings|gross|net)\b'
    r'|\$',
    re.IGNORECASE,
)

# Number labels
_NUMBER_LABELS = re.compile(
    r'\b(number\s*of|how\s*many|total\s*number|count|qty|quantity|#\s*of)\b',
    re.IGNORECASE,
)

# Section header heuristics: ALL CAPS line, or line ending with colon that
# looks like a header (short, no fill-in blanks)
_SECTION_HEADER = re.compile(
    r'^(?:SECTION|PART|STEP)\s*[IVX0-9]+',
    re.IGNORECASE,
)

# Lines that are likely "For Office Use Only" etc. — skip these
_INTERNAL_USE = re.compile(
    r'\b(for\s+(office|agency|administrative|internal|official)\s+use'
    r'|use\s+only)\b',
    re.IGNORECASE,
)


def _make_id(label: str) -> str:
    """Generate a snake_case field ID from a label."""
    cleaned = re.sub(r'[^a-zA-Z0-9\s]', '', label)
    parts = cleaned.lower().split()
    field_id = '_'.join(parts[:6])  # cap at 6 words
    if not field_id:
        field_id = f'field_{uuid.uuid4().hex[:8]}'
    return field_id


def _detect_field_type(label: str) -> str:
    """Infer field type from the label text."""
    if _DATE_LABELS.search(label):
        return 'date'
    if _EMAIL_LABELS.search(label):
        return 'email'
    if _PHONE_LABELS.search(label):
        return 'phone'
    if _ADDRESS_LABELS.search(label):
        return 'address'
    if _NAME_LABELS.search(label):
        return 'name'
    if _CURRENCY_LABELS.search(label):
        return 'currency'
    if _NUMBER_LABELS.search(label):
        return 'number'
    return 'text'


def _extract_checkbox_options(lines: list[str], start_idx: int) -> tuple[list[str], int]:
    """
    Starting from a line with checkbox markers, collect all consecutive
    checkbox option lines. Returns (options_list, next_line_index).
    """
    options = []
    i = start_idx
    while i < len(lines):
        line = lines[i].strip()
        if _CHECKBOX_MARKERS.search(line):
            # Remove the marker to get the option text
            option_text = _CHECKBOX_MARKERS.sub('', line).strip()
            option_text = re.sub(r'^[\s:.\-]+', '', option_text).strip()
            if option_text:
                options.append(option_text)
            i += 1
        else:
            break
    return options, i


def _extract_radio_options(lines: list[str], start_idx: int) -> tuple[list[str], int]:
    """
    Starting from a line with radio markers, collect consecutive radio
    option lines. Returns (options_list, next_line_index).
    """
    options = []
    i = start_idx
    while i < len(lines):
        line = lines[i].strip()
        if _RADIO_MARKERS.search(line):
            option_text = _RADIO_MARKERS.sub('', line).strip()
            option_text = re.sub(r'^[\s:.\-]+', '', option_text).strip()
            if option_text:
                options.append(option_text)
            i += 1
        else:
            break
    return options, i


def _is_yes_no_line(line: str) -> bool:
    """Check if a line contains a Yes/No pattern."""
    return bool(re.search(
        r'\b(yes|no)\b\s*[/\\|]\s*\b(yes|no)\b'
        r'|\byes\b\s+\bno\b',
        line, re.IGNORECASE,
    ))


def _looks_like_section_header(line: str) -> bool:
    """Heuristic: is this line likely a section header?"""
    stripped = line.strip()
    if not stripped or len(stripped) < 3:
        return False
    # Explicit section markers
    if _SECTION_HEADER.match(stripped):
        return True
    # ALL CAPS lines that are short (likely headers)
    if stripped.isupper() and len(stripped) < 80 and not _BLANK_LINE.search(stripped):
        return True
    # Lines ending with colon, short, no blanks
    if stripped.endswith(':') and len(stripped) < 60 and not _BLANK_LINE.search(stripped):
        # But not if it looks like a field label (has a blank after it)
        return True
    return False


def ocr_text_to_intermediary_json(
    ocr_text: str,
    form_title: str = 'Untitled Form (OCR)',
) -> list[dict[str, Any]]:
    """
    Parse raw OCR text into the intermediary JSON format.

    This is a best-effort heuristic parser. It will not match LLM quality
    but produces structured output for the CiviForm conversion pipeline.

    Args:
        ocr_text:    Raw text extracted by Tesseract OCR.
        form_title:  Title to use for the form.

    Returns:
        A list containing one dict with 'title', 'sections', etc. —
        the same schema that Gemini produces.
    """
    lines = ocr_text.split('\n')
    sections: list[dict] = []
    current_section: dict | None = None
    current_fields: list[dict] = []
    skip_until_next_section = False
    field_counter = 0

    def _flush_section():
        nonlocal current_section, current_fields
        if current_section is not None and current_fields:
            current_section['fields'] = current_fields
            sections.append(current_section)
        elif current_fields:
            # Fields without a section header — create a default section
            sections.append({
                'title': 'General Information',
                'help_text': '',
                'fields': current_fields,
            })
        current_section = None
        current_fields = []

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Skip empty lines
        if not line:
            i += 1
            continue

        # Skip "For Office Use" blocks
        if _INTERNAL_USE.search(line):
            skip_until_next_section = True
            i += 1
            continue

        # Check for section headers
        if _looks_like_section_header(line):
            if skip_until_next_section:
                skip_until_next_section = False
            _flush_section()
            section_title = line.rstrip(':').strip()
            current_section = {
                'title': section_title,
                'help_text': '',
            }
            i += 1
            continue

        if skip_until_next_section:
            i += 1
            continue

        # ── Check for checkbox groups ──────────────────────────────────────
        if _CHECKBOX_MARKERS.search(line):
            # Look back for a label on the previous non-empty line
            label = 'Select all that apply'
            for j in range(i - 1, max(i - 4, -1), -1):
                prev = lines[j].strip() if j >= 0 else ''
                if prev and not _CHECKBOX_MARKERS.search(prev) and not _RADIO_MARKERS.search(prev):
                    label = prev.rstrip(':').strip()
                    break

            options, next_i = _extract_checkbox_options(lines, i)
            if options:
                field_counter += 1
                current_fields.append({
                    'label': label,
                    'type': 'checkbox',
                    'options': options,
                    'help_text': '',
                    'id': _make_id(label),
                })
            i = next_i
            continue

        # ── Check for radio button groups ──────────────────────────────────
        if _RADIO_MARKERS.search(line):
            label = 'Select one'
            for j in range(i - 1, max(i - 4, -1), -1):
                prev = lines[j].strip() if j >= 0 else ''
                if prev and not _RADIO_MARKERS.search(prev) and not _CHECKBOX_MARKERS.search(prev):
                    label = prev.rstrip(':').strip()
                    break

            options, next_i = _extract_radio_options(lines, i)
            if len(options) >= 2:
                field_counter += 1
                current_fields.append({
                    'label': label,
                    'type': 'radio_button',
                    'options': options,
                    'help_text': '',
                    'id': _make_id(label),
                })
            i = next_i
            continue

        # ── Check for Yes/No patterns ──────────────────────────────────────
        if _is_yes_no_line(line):
            # The label is usually the text before Yes/No
            label = re.split(r'\b(yes|no)\b', line, flags=re.IGNORECASE)[0].strip()
            label = label.rstrip(':').rstrip('?').strip()
            if not label:
                label = line.strip()
            field_counter += 1
            current_fields.append({
                'label': label if label else 'Yes/No question',
                'type': 'radio_button',
                'options': ['Yes', 'No'],
                'help_text': '',
                'id': _make_id(label if label else 'yes_no'),
            })
            i += 1
            continue

        # ── Check for labeled fields (line with colon or underline blanks) ─
        has_colon = ':' in line and not line.endswith(':')  # not a header
        has_blank = bool(_BLANK_LINE.search(line))

        if has_colon or has_blank:
            # Extract label (text before colon or blanks)
            if has_colon:
                label = line.split(':')[0].strip()
            elif has_blank:
                label = _BLANK_LINE.split(line)[0].strip()
            else:
                label = line.strip()

            label = label.rstrip(':').strip()
            if label and len(label) > 2:
                field_type = _detect_field_type(label)
                field_counter += 1
                current_fields.append({
                    'label': label,
                    'type': field_type,
                    'help_text': '',
                    'id': _make_id(label),
                })
            i += 1
            continue

        # ── Fallback: if the line looks like a field label ─────────────────
        # Lines that are short and followed by a blank or underline on next line
        if i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if _BLANK_LINE.match(next_line) or not next_line:
                label = line.rstrip(':').strip()
                if label and len(label) > 2 and len(label) < 80:
                    field_type = _detect_field_type(label)
                    field_counter += 1
                    current_fields.append({
                        'label': label,
                        'type': field_type,
                        'help_text': '',
                        'id': _make_id(label),
                    })
                    i += 2  # skip the blank/underline line too
                    continue

        i += 1

    # Flush the last section
    _flush_section()

    # If no fields were found at all, create a single section with the raw text
    if not sections:
        logging.warning(
            'Heuristic parser found no fields. '
            'Creating a placeholder section with raw text.'
        )
        sections.append({
            'title': 'Extracted Text',
            'help_text': 'The heuristic parser could not identify structured '
                         'form fields. The raw OCR text is below.',
            'fields': [{
                'label': 'Raw OCR text (review needed)',
                'type': 'text',
                'help_text': ocr_text[:2000],
                'id': 'raw_ocr_text',
            }],
        })

    result = {
        'title': form_title,
        'help_text': 'Extracted via Tesseract OCR with heuristic field detection. '
                     'Review and edit field types and labels as needed.',
        'Instructions': '',
        'sections': sections,
    }

    logging.info(
        f'Heuristic parser: {len(sections)} sections, '
        f'{field_counter} fields identified.'
    )

    return [result]
