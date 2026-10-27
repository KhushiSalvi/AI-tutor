"""Auto-detect the offset between a PDF's physical page index and its printed page number.

Usage:  python -m core.page_offset data/raw/mano_digital_design.pdf
Prints the detected offset to paste into sources.yaml. Falls back to manual entry
if the book's printed numbers can't be found (e.g. scanned front matter, roman numerals).
"""
import re
import sys
from collections import Counter

import pymupdf

NUM_RE = re.compile(r"(?<!\d)(\d{1,4})(?!\d)")


def printed_number(page):
    """Look for a lone number near the top or bottom 12% of the page (typical header/footer)."""
    h = page.rect.height
    candidates = []
    for b in page.get_text("blocks"):
        x0, y0, x1, y1, text, *_ = b
        text = text.strip()
        if not text or len(text) > 6:
            continue
        if y0 < h * 0.12 or y1 > h * 0.88:
            m = NUM_RE.fullmatch(text)
            if m:
                candidates.append(int(m.group(1)))
    return candidates


def detect_offset(pdf_path, sample=40):
    doc = pymupdf.open(pdf_path)
    n = len(doc)
    votes = Counter()
    for i in range(0, n, max(1, n // sample)):
        page = doc[i]
        for printed in printed_number(page):
            offset = (i + 1) - printed  # pdf_page(1-indexed) - printed = offset
            if -5 <= offset <= n:       # sanity bound
                votes[offset] += 1
    doc.close()
    if not votes:
        return None, 0
    offset, count = votes.most_common(1)[0]
    confidence = count / sum(votes.values())
    return offset, confidence


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m core.page_offset <path-to-pdf>")
        raise SystemExit(1)
    path = sys.argv[1]
    offset, confidence = detect_offset(path)
    if offset is None:
        print("Could not detect an offset automatically (scanned book or unusual layout).")
        print("Open the PDF, find any page, and compute: offset = pdf_page_number - printed_page_number")
        print('Then add it by hand: "<source_id>": {"offset": <value>, "min": <first content page>}')
    else:
        flag = "" if confidence >= 0.6 else "  (LOW CONFIDENCE - verify by hand)"
        print(f"Detected offset: {offset}{flag}")
        print(f"Confidence: {confidence:.0%} of sampled pages agreed")
        print(f'Paste into core/tutor.py PAGE_INFO: "<source_id>": {{"offset": {offset}, "min": 1}}')
