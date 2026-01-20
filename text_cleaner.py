"""
Text cleaner for PDF extractions and AI responses
Ported from Rust text_cleaner.rs

Removes: page headers/footers, data dumps, repetitive content, encoding artifacts
"""

import re
from collections import Counter
from typing import Dict, Set


def clean_text(text: str) -> str:
    """
    Clean garbage from extracted PDF text or AI-generated responses.
    Main entry point for text cleaning.
    """
    # First, strip markdown code fences if they wrap the entire response
    cleaned = text.strip()

    if cleaned.startswith("```markdown\n") or cleaned.startswith("```markdown\r\n"):
        end_pos = cleaned.rfind("```")
        if end_pos > 15:
            first_newline = cleaned.find('\n')
            if first_newline != -1:
                cleaned = cleaned[first_newline + 1:end_pos].strip()
    elif cleaned.startswith("```\n") or cleaned.startswith("```\r\n"):
        end_pos = cleaned.rfind("```")
        if end_pos > 4:
            first_newline = cleaned.find('\n')
            if first_newline != -1:
                cleaned = cleaned[first_newline + 1:end_pos].strip()

    # Collect all lines for multi-pass processing
    lines = cleaned.split('\n')

    # First pass: detect repeated lines (headers/footers)
    repeated_lines = find_repeated_lines(lines)

    # Second pass: process each line
    processed_lines = [clean_line(line, repeated_lines) for line in lines]

    result = '\n'.join(processed_lines)

    # Remove page break markers
    result = remove_page_breaks(result)

    # Collapse multiple consecutive removed/empty lines
    result = collapse_removed_lines(result)

    # Final cleanup: remove excessive newlines
    result = re.sub(r'\n{4,}', '\n\n\n', result)

    return result.strip()


def find_repeated_lines(lines: list) -> Set[str]:
    """Find lines that appear 3+ times (likely headers/footers)"""
    counts: Dict[str, int] = {}

    for line in lines:
        trimmed = line.strip()
        # Only track non-empty lines that are short enough to be headers
        if trimmed and len(trimmed) < 200:
            counts[trimmed] = counts.get(trimmed, 0) + 1

    # Return only lines that appear 3+ times
    return {line for line, count in counts.items() if count >= 3}


def remove_page_breaks(text: str) -> str:
    """Remove page break markers and clean up around them"""
    # Remove "## --- Page Break ---" style markers
    result = re.sub(r'(?m)^##?\s*-{2,}\s*Page\s*Break\s*-{2,}\s*$', '', text)
    # Also remove simple page break lines
    result = re.sub(r'(?m)^-{3,}\s*Page\s*Break\s*-{3,}\s*$', '', result)
    return result


def clean_line(line: str, repeated_lines: Set[str]) -> str:
    """Process and clean a single line"""
    trimmed = line.strip()

    # Empty lines pass through
    if not trimmed:
        return ''

    # Hard limit: no legitimate line is over 2000 chars
    if len(line) > 2000:
        return '[content removed]'

    # Remove repeated headers/footers (appear 3+ times)
    if trimmed in repeated_lines:
        # Don't remove if it's a legitimate short heading
        if not is_likely_heading(trimmed):
            return ''  # Just remove, don't mark

    # Remove page number patterns like "Page X of Y"
    if is_page_number_line(trimmed):
        return ''

    # Remove lines that are mostly contact info repeated
    if is_contact_footer(trimmed):
        return ''

    # High digit/hex ratio = likely data dump
    # Only for longer lines with VERY high digit ratio
    if len(trimmed) > 300 and get_digit_hex_ratio(trimmed) > 0.6:
        return '[data removed]'

    # Pixel pattern sequences: "Pixel 0 Pixel 1 Pixel 2..."
    if contains_pixel_sequence(trimmed):
        return '[pixel data removed]'

    # Hex address sequences: "0x0000 0x0010 0x0020..."
    if contains_hex_sequence(trimmed):
        return '[address data removed]'

    # ThGrad/ThOffset patterns with many pixel references
    if is_calibration_data_line(trimmed):
        return '[calibration data removed]'

    # Line over 500 chars with almost no spaces = garbage (binary/encoded data)
    if len(line) > 500:
        space_count = line.count(' ')
        space_ratio = space_count / len(line)
        if space_ratio < 0.05:
            return '[content removed]'

    # Single "word" over 200 chars = garbage
    if len(line) > 200 and ' ' not in line:
        return '[content removed]'

    # Repetitive pattern detection (e.g., "the the the the..." repeated)
    if len(line) > 500:
        words = line.split()
        if len(words) > 50:
            word_counts = Counter(w.lower() for w in words)
            max_count = max(word_counts.values())
            unique_count = len(word_counts)

            # If any single word is more than 40% of all words = repetitive garbage
            if max_count / len(words) > 0.4:
                return '[content removed]'

            # If unique words < 10% of total words = garbage
            if unique_count / len(words) < 0.1:
                return '[content removed]'

    return line


def is_likely_heading(line: str) -> bool:
    """Check if a line is likely a legitimate heading (short, title-case or all caps)"""
    trimmed = line.strip()
    if len(trimmed) > 80 or len(trimmed) < 3:
        return False

    # Check if it starts with ## (markdown heading)
    if trimmed.startswith('#'):
        return True

    # Check if it's mostly uppercase or title case
    letters = [c for c in trimmed if c.isalpha()]
    if not letters:
        return False

    uppercase_count = sum(1 for c in letters if c.isupper())
    return uppercase_count / len(letters) > 0.4


def is_page_number_line(line: str) -> bool:
    """Check if line is ONLY a page number (not mixed with content)"""
    trimmed = line.strip()

    # Only match SHORT lines that are purely page numbers
    if len(trimmed) > 50:
        return False  # Too long to be just a page number

    lower = trimmed.lower()

    # "Page X of Y" pattern - only if that's basically all it is
    if re.match(r'^(page\s+)?\d+\s*(of|/)\s*\d+\s*$', lower):
        return True

    return False


def is_contact_footer(line: str) -> bool:
    """Check if line is PURELY a contact footer (not mixed with real content)"""
    trimmed = line.strip()

    # If line is long and has real content mixed in, don't remove it
    if len(trimmed) > 200:
        return False  # Too long, probably has real content mixed in

    lower = trimmed.lower()

    # Must have multiple footer indicators AND be mostly footer
    footer_indicators = [
        "customer support",
        "www.heimannsensor",
        "maria-reiche-str",
        "info@heimann",
        "fax 49",
        "phone 49",
        "d-01109 dresden",
    ]

    matches = sum(1 for ind in footer_indicators if ind in lower)

    # Need 3+ indicators for a short line to be considered pure footer
    return matches >= 3


def get_digit_hex_ratio(s: str) -> float:
    """Calculate ratio of digits and hex chars in a string"""
    if not s:
        return 0.0

    digit_hex_count = sum(1 for c in s if c.isdigit() or c.lower() in 'abcdefx')
    return digit_hex_count / len(s)


def contains_pixel_sequence(line: str) -> bool:
    """Check for sequences like 'Pixel 0 Pixel 1 Pixel 2'"""
    matches = re.findall(r'Pixel\s+\d+', line)
    return len(matches) >= 5  # 5+ pixel references = likely a data sequence


def contains_hex_sequence(line: str) -> bool:
    """Check for hex address sequences like '0x0000 0x0010'"""
    matches = re.findall(r'0x[0-9A-Fa-f]{2,}', line)
    return len(matches) >= 4  # 4+ hex addresses = likely a data dump


def is_calibration_data_line(line: str) -> bool:
    """Check for calibration data patterns (ThGrad, VddComp, etc.)"""
    has_thgrad = 'ThGrad' in line or 'ThOffset' in line
    has_vddcomp = 'VddCompGrad' in line or 'VddCompOff' in line
    has_pixels = contains_pixel_sequence(line)

    return (has_thgrad or has_vddcomp) and has_pixels


def collapse_removed_lines(text: str) -> str:
    """Collapse multiple consecutive removed markers and empty lines"""
    result = []
    prev_was_removed = False
    prev_was_empty = False

    for line in text.split('\n'):
        is_removed = line.startswith('[') and line.endswith(' removed]')
        is_empty = not line.strip()

        if is_removed:
            if not prev_was_removed:
                result.append(line)
                prev_was_removed = True
            prev_was_empty = False
        elif is_empty:
            if not prev_was_empty and not prev_was_removed:
                result.append('')
            prev_was_empty = True
            prev_was_removed = False
        else:
            result.append(line)
            prev_was_removed = False
            prev_was_empty = False

    return '\n'.join(result)
