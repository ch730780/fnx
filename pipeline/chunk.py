"""Split clean pages into small chunks for search, one chunk per line in data/chunks.jsonl.

Run: python -m pipeline.chunk
Reads data/pages.jsonl (made by clean.py). The output file is rebuilt from scratch on every run.
"""
import json
import re
from pathlib import Path

PAGES_PATH = Path("data/pages.jsonl")    # input: clean pages
OUT_PATH = Path("data/chunks.jsonl")     # output: one chunk per line (committed: the app needs it for keyword search)
TARGET_CHARS = 1000                      # neighbouring small parts are joined up to about this size
MAX_CHARS = 1500                         # a section bigger than this is split at its paragraphs
HEADING_START = re.compile(r"^(?=#{1,6} )", re.MULTILINE)   # the position right before a Markdown heading line


def pack(parts: list[str]) -> list[str]:
    """Join neighbouring parts in order, starting a new chunk when the next part would pass TARGET_CHARS."""
    chunks, current = [], ""
    for part in parts:
        if current and len(current) + len(part) > TARGET_CHARS:
            chunks.append(current)
            current = ""
        current = f"{current}\n\n{part}" if current else part
    if current:
        chunks.append(current)
    return chunks


def split_long(section: str) -> list[str]:
    """Split a too-big section at its paragraphs (or, inside a huge table or list, at its lines);
    every piece keeps the section heading."""
    first_line = section.split("\n", 1)[0]
    paragraphs = []
    for paragraph in section.split("\n\n"):
        if len(paragraph) > MAX_CHARS:
            paragraphs.extend(paragraph.split("\n"))    # a huge table or list: split between its rows
        else:
            paragraphs.append(paragraph)
    pieces = pack(paragraphs)
    if first_line.startswith("#"):
        pieces = pieces[:1] + [f"{first_line}\n\n{piece}" for piece in pieces[1:]]
    return pieces


def chunk_page(text: str) -> list[str]:
    """Cut a page at its headings, split big sections, then join small neighbours."""
    parts = []
    for section in HEADING_START.split(text):
        section = section.strip()
        if not section:
            continue
        if len(section) > MAX_CHARS:
            parts.extend(split_long(section))
        else:
            parts.append(section)
    return pack(parts)


def main() -> None:
    with PAGES_PATH.open(encoding="utf-8") as f:
        pages = [json.loads(line) for line in f]

    count = 0
    with OUT_PATH.open("w", encoding="utf-8") as out:
        for page in pages:
            context = " | ".join(part for part in [page["breadcrumb"], page["title"]] if part)
            for n, body in enumerate(chunk_page(page["text"])):
                chunk = {
                    "id": f"{page['id']}-{n}",                 # page id + chunk number, e.g. "09288d531986e5e2-3"
                    "page_id": page["id"],
                    "url": page["url"],
                    "title": page["title"],
                    "breadcrumb": page["breadcrumb"],
                    "section": page["section"],
                    "fetched_at": page["fetched_at"],
                    "page_hash": page["content_hash"],          # refresh: if the page changed, all its chunks are rebuilt
                    "text": f"{context}\n\n{body}",             # context line first, so search knows the product
                }
                out.write(json.dumps(chunk, ensure_ascii=False) + "\n")
                count += 1

    print(f"pages: {len(pages)}  |  chunks: {count}  |  output: {OUT_PATH}")


if __name__ == "__main__":
    main()
