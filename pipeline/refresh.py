"""Bring the bot up to date with fnx.co.il: download the site again, rebuild the chunks,
and update Pinecone only for pages that were added, changed or removed.

Run: python -m pipeline.refresh        (about an hour - almost all of it is the polite crawl)
Then commit data/chunks.jsonl and data/last_refresh.json, so the next refresh compares against them.
"""
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI
from pinecone import Pinecone

import config
from pipeline import chunk, clean, crawl
from pipeline.index import get_index, upload

CHUNKS_PATH = Path("data/chunks.jsonl")
PREVIOUS_PATH = Path("data/chunks.previous.jsonl")   # the chunks before this refresh (kept until it finishes)
REPORT_PATH = Path("data/last_refresh.json")
DELETE_BATCH = 1000                                  # ids removed from Pinecone in one request


def read_chunks(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def page_hashes(chunks: list[dict]) -> dict[str, str]:
    """{page id: fingerprint of the page text}"""
    return {chunk["page_id"]: chunk["page_hash"] for chunk in chunks}


def main() -> None:
    if not PREVIOUS_PATH.exists():                   # if an earlier refresh stopped halfway, keep its starting point
        shutil.copy(CHUNKS_PATH, PREVIOUS_PATH)
    old = page_hashes(read_chunks(PREVIOUS_PATH))

    crawl.main(refresh=True)
    clean.main()
    chunk.main()

    new_chunks = read_chunks(CHUNKS_PATH)
    new = page_hashes(new_chunks)
    added = [page for page in new if page not in old]
    changed = [page for page in new if page in old and new[page] != old[page]]
    removed = [page for page in old if page not in new]

    index = get_index(Pinecone(api_key=config.PINECONE_API_KEY))
    in_pinecone = {item.id for page in index.list() for item in page.vectors}
    new_ids = {chunk["id"] for chunk in new_chunks}

    stale = sorted(in_pinecone - new_ids)            # chunks of removed pages, or of pages that got shorter
    for start in range(0, len(stale), DELETE_BATCH):
        index.delete(ids=stale[start:start + DELETE_BATCH])

    to_update = set(added + changed)
    fresh = [chunk for chunk in new_chunks if chunk["page_id"] in to_update or chunk["id"] not in in_pinecone]
    upload(fresh, OpenAI(api_key=config.OPENAI_API_KEY), index)

    report = {
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
        "pages": len(new), "chunks": len(new_chunks),
        "added_pages": len(added), "changed_pages": len(changed), "removed_pages": len(removed),
        "chunks_uploaded": len(fresh), "chunks_deleted": len(stale),
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    PREVIOUS_PATH.unlink()                           # finished: the next refresh starts from the new chunks
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
