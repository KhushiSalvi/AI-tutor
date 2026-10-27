"""Chunk every PDF in sources.yaml into data/processed/<source_id>.jsonl.

Default: skip a source if its .jsonl already exists and is newer than the PDF, so
re-running after adding one new book only chunks that new book. Pass --all to force
re-chunking of every PDF (e.g. after changing the chunking logic itself).
"""
import re
import sys
from pathlib import Path

import pymupdf

try:
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    from PIL import Image
    import io
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

from core.ingestion.manifest import load_manifest
from core.ingestion.chunk import Chunk

OUT = Path("data/processed")
OUT.mkdir(parents=True, exist_ok=True)


def clean(text: str) -> str:
    text = re.sub(r"-\n(\w)", r"\1", text)
    text = re.sub(r"\s*\n\s*", " ", text)
    return re.sub(r"\s{2,}", " ", text).strip()


def split_words(text: str, size=300, overlap=50):
    words = text.split()
    step = size - overlap
    for i in range(0, max(len(words), 1), step):
        piece = words[i:i + size]
        if len(piece) >= 40:
            yield " ".join(piece)
        if i + size >= len(words):
            break


def already_current(source):
    out_file = OUT / f"{source.id}.jsonl"
    if not out_file.exists():
        return False
    return out_file.stat().st_mtime >= Path(source.path).stat().st_mtime


MIN_TEXT_CHARS = 20  # below this, assume the page is a scan and try OCR instead


_OCR_WARNED = False


def ocr_page(page, dpi=200):
    global _OCR_WARNED
    if not OCR_AVAILABLE:
        if not _OCR_WARNED:
            print("  NOTE: pytesseract/Pillow not installed -- pip install pytesseract pillow")
            _OCR_WARNED = True
        return ""
    pix = page.get_pixmap(dpi=dpi)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    try:
        return pytesseract.image_to_string(img)
    except Exception as e:
        if not _OCR_WARNED:
            print(f"  OCR ERROR: {e}")
            print("  This usually means the Tesseract program itself isn't installed or isn't on PATH.")
            print("  Install it from https://github.com/UB-Mannheim/tesseract/wiki, then either add it")
            print("  to PATH or set: import pytesseract; pytesseract.pytesseract.tesseract_cmd = r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'")
            _OCR_WARNED = True
        return ""  # degrade to no text rather than crash the whole ingest run


def ingest(source):
    doc = pymupdf.open(source.path)
    chunks = []
    ocr_pages = 0
    for page_no, page in enumerate(doc, start=1):
        raw = page.get_text()
        if len(raw.strip()) < MIN_TEXT_CHARS:
            raw = ocr_page(page)
            if raw.strip():
                ocr_pages += 1
        text = clean(raw)
        for j, piece in enumerate(split_words(text)):
            chunks.append(Chunk(
                chunk_id=f"{source.id}_p{page_no}_{j}",
                source_id=source.id,
                text=piece,
                page=page_no,
                topics=source.topics,
                license=source.license,
                tier=source.tier,
            ))
    out_file = OUT / f"{source.id}.jsonl"
    with open(out_file, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(c.model_dump_json() + "\n")
    ocr_note = f" ({ocr_pages} page(s) via OCR)" if ocr_pages else ""
    print(f"{source.id}: {len(chunks)} chunks -> {out_file}{ocr_note}")
    if ocr_pages and not OCR_AVAILABLE:
        print(f"  NOTE: {source.id} looks scanned but pytesseract/Tesseract isn't installed; "
              f"install them to recover its text (see setup instructions).")


if __name__ == "__main__":
    force = "--all" in sys.argv
    for s in load_manifest():
        if s.type != "pdf":
            continue
        if not s.path or not Path(s.path).exists():
            print(f"SKIPPED (file missing): {s.id}")
        elif not force and already_current(s):
            print(f"SKIPPED (already up to date): {s.id}")
        else:
            ingest(s)
