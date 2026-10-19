"""Turn downloaded HTML pages into clean text (Markdown), one line per page in data/pages.jsonl.

Run: python -m pipeline.clean
Reads data/raw/ (made by crawl.py). The output file is rebuilt from scratch on every run.
"""
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

import trafilatura
from bs4 import BeautifulSoup
from tqdm import tqdm

RAW_DIR = Path("data/raw")              # input: pages downloaded by crawl.py
OUT_PATH = Path("data/pages.jsonl")     # output: one clean page per line
LOG_PATH = Path("data/clean_log.json")
MIN_TEXT_CHARS = 200                    # pages with less text than this are dropped (empty pages)
TITLE_SUFFIX = " | הפניקס"              # every page title ends with the site name
SITE_DOMAIN = "fnx.co.il"               # pages that redirect to another site are dropped
LAYOUT_SELECTORS = "#header, .entrance-bar, footer, nav"   # site menu, portals bar, footer, navigation


def parse_page(html: str) -> tuple[str, str, str]:
    """Return (title, breadcrumb, main content as Markdown) for one page, without the site menu and footer."""
    soup = BeautifulSoup(html, "lxml")
    tag = soup.title
    title = tag.get_text(strip=True).removesuffix(TITLE_SUFFIX).strip() if tag else ""

    crumbs = soup.select_one("nav.breadcrumbs")     # "דף הבית > קרן השתלמות > שאלות נפוצות"
    items = [li.get_text(" ", strip=True) for li in crumbs.find_all("li")] if crumbs else []
    breadcrumb = " > ".join(item for item in items if item != "דף הבית")

    for element in soup.select(LAYOUT_SELECTORS):
        element.decompose()

    text = trafilatura.extract(str(soup), output_format="markdown", include_tables=True, favor_recall=True)
    return title, breadcrumb, (text or "").strip()


def main() -> None:
    seen_urls = set()      # final addresses already written (two sitemap URLs can redirect to one page)
    seen_hashes = set()    # texts already written (the same content can live at two addresses)
    log = {"written": 0, "off_site": [], "too_short": [], "duplicate": []}

    with OUT_PATH.open("w", encoding="utf-8") as out:
        for path in tqdm(sorted(RAW_DIR.glob("*.json"))):
            page = json.loads(path.read_text(encoding="utf-8"))

            if not urlparse(page["final_url"]).hostname.endswith(SITE_DOMAIN):
                log["off_site"].append(page["url"])
                continue

            title, breadcrumb, text = parse_page(page["html"])

            if len(text) < MIN_TEXT_CHARS:
                log["too_short"].append(page["url"])
                continue

            content_hash = hashlib.sha1(text.encode("utf-8")).hexdigest()
            if page["final_url"] in seen_urls or content_hash in seen_hashes:
                log["duplicate"].append(page["url"])
                continue
            seen_urls.add(page["final_url"])
            seen_hashes.add(content_hash)

            record = {
                "id": path.stem,                      # same stable id as the raw file name
                "url": page["final_url"],             # the real address, shown to the user as the source
                "title": title,
                "breadcrumb": breadcrumb,             # where the page sits on the site, e.g. "קרן השתלמות > שאלות נפוצות"
                "section": page["section"],
                "fetched_at": page["fetched_at"],     # collection date (for refresh)
                "content_hash": content_hash,         # fingerprint of the text (refresh: did it change?)
                "text": text,
            }
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            log["written"] += 1

    LOG_PATH.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"written: {log['written']}  |  off site: {len(log['off_site'])}  |  "
          f"too short: {len(log['too_short'])}  |  duplicates: {len(log['duplicate'])}")
    print(f"output: {OUT_PATH}  |  log: {LOG_PATH}")


if __name__ == "__main__":
    main()
