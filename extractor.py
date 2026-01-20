"""
PDF to Markdown extraction using PyMuPDF
Based on the original extract_pdf.py from my-toolkit
"""

import re
from typing import Dict, Any

try:
    import pymupdf
except ImportError:
    pymupdf = None


def is_numeric_garbage(line: str) -> bool:
    """Check if a line is mostly just numbers (pixel indices, addresses, etc.)"""
    stripped = line.strip()
    if not stripped:
        return False

    # Line is just a number
    if re.match(r'^\d+$', stripped):
        return True

    # Line is a sequence of numbers separated by spaces (like "1000 1001 1002...")
    words = stripped.split()
    if len(words) >= 5:
        numeric_count = sum(1 for w in words if re.match(r'^\d+$', w))
        if numeric_count / len(words) > 0.8:  # 80%+ numbers
            return True

    # Line has very high digit ratio (>70% digits)
    if len(stripped) > 50:
        digit_count = sum(1 for c in stripped if c.isdigit())
        if digit_count / len(stripped) > 0.7:
            return True

    return False


def clean_extracted_text(text: str) -> str:
    """Basic cleanup of extracted PDF text."""
    lines = text.split('\n')
    cleaned_lines = []
    seen_lines: Dict[str, int] = {}  # Track repeated lines (headers/footers)

    # First pass: count line occurrences
    for line in lines:
        stripped = line.strip()
        if stripped and len(stripped) < 200:
            seen_lines[stripped] = seen_lines.get(stripped, 0) + 1

    # Second pass: filter out garbage
    prev_empty = False
    numeric_run = 0  # Track consecutive numeric lines

    for line in lines:
        stripped = line.strip()

        # Skip lines that appear 3+ times (headers/footers)
        if stripped and seen_lines.get(stripped, 0) >= 3:
            continue

        # Skip page number patterns
        if re.match(r'^Page\s+\d+\s+(of|/)\s+\d+\s*$', stripped, re.IGNORECASE):
            continue

        # Skip numeric garbage
        if is_numeric_garbage(stripped):
            numeric_run += 1
            if numeric_run == 3:  # After 3 numeric lines, add a placeholder
                cleaned_lines.append('[numeric data removed]')
            continue
        else:
            numeric_run = 0

        # Collapse multiple empty lines
        if not stripped:
            if not prev_empty:
                cleaned_lines.append('')
                prev_empty = True
            continue

        prev_empty = False
        cleaned_lines.append(line)

    # Collapse consecutive [numeric data removed] markers
    result = []
    prev_was_marker = False
    for line in cleaned_lines:
        if line == '[numeric data removed]':
            if not prev_was_marker:
                result.append(line)
                prev_was_marker = True
        else:
            result.append(line)
            prev_was_marker = False

    return '\n'.join(result)


def extract_pdf_to_markdown(pdf_path: str = None, pdf_bytes: bytes = None) -> Dict[str, Any]:
    """
    Extract PDF to text with basic cleanup.

    Args:
        pdf_path: Path to PDF file (for local files)
        pdf_bytes: PDF file bytes (for uploaded files)

    Returns:
        Dict with markdown, page_count, and error fields
    """
    if pymupdf is None:
        return {
            "markdown": "",
            "page_count": 0,
            "error": "PyMuPDF not installed. Run: pip install pymupdf"
        }

    try:
        # Open from bytes or path
        if pdf_bytes:
            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        elif pdf_path:
            doc = pymupdf.open(pdf_path)
        else:
            return {
                "markdown": "",
                "page_count": 0,
                "error": "No PDF provided"
            }

        page_count = len(doc)

        # Extract text from all pages
        all_text = []
        for page in doc:
            text = page.get_text()
            if text.strip():
                all_text.append(text)

        doc.close()

        # Join pages and clean up
        raw_text = '\n\n---\n\n'.join(all_text)
        cleaned_text = clean_extracted_text(raw_text)

        return {
            "markdown": cleaned_text,
            "page_count": page_count,
            "error": None
        }

    except Exception as e:
        return {
            "markdown": "",
            "page_count": 0,
            "error": str(e)
        }
