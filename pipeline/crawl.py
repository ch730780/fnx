"""Download every public page listed in the sitemap into data/raw/ (one JSON file per page).

Run: python -m pipeline.crawl
Re-running skips pages that were already downloaded.
"""
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from tqdm import tqdm

import config
from pipeline.inspect_site import collect_sitemap_urls

RAW_DIR = Path("data/raw")          # where downloaded pages are saved
LOG_PATH = Path("data/crawl_log.json")
RETRIES = 2                         # extra attempts after a server/network error


def url_to_id(url: str) -> str:
    """Stable short id for a URL, used as its file name."""
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def section_of(url: str) -> str:
    """First path segment of a URL, e.g. https://www.fnx.co.il/car-insurance/x -> 'car-insurance'."""
    path = unquote(urlparse(url).path).strip("/")
    return path.split("/")[0] if path else "(home)"


def select_urls(urls: list[str], robots: RobotFileParser) -> list[str]:
    """Keep only URLs we are allowed and want to crawl."""
    return [
        url for url in urls
        if "?" not in url                                   # robots.txt forbids query URLs
        and section_of(url) not in config.EXCLUDED_SECTIONS  # sections we decided to skip
        and robots.can_fetch(config.USER_AGENT, url)        # every other robots.txt rule
    ]


def download(client: httpx.Client, url: str) -> httpx.Response | None:
    """GET a URL politely, retrying on network errors and 5xx server errors."""
    for _ in range(1 + RETRIES):
        time.sleep(config.CRAWL_DELAY_SEC)
        try:
            response = client.get(url)
            if response.status_code < 500:
                return response
        except httpx.HTTPError:
            pass
    return None


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    log = {"saved": [], "already_downloaded": 0, "failed": [], "skipped_non_html": []}
    headers = {"User-Agent": config.USER_AGENT, "Accept-Language": "he-IL,he;q=0.9"}

    with httpx.Client(headers=headers, follow_redirects=True, timeout=30) as client:
        robots = RobotFileParser()
        robots.parse(client.get(f"{config.BASE_URL}/robots.txt").text.splitlines())
        urls = select_urls(collect_sitemap_urls(client, []), robots)
        print(f"{len(urls)} pages to crawl")

        for url in tqdm(urls):
            path = RAW_DIR / f"{url_to_id(url)}.json"
            if path.exists():
                log["already_downloaded"] += 1
                continue

            response = download(client, url)
            if response is None or response.status_code != 200:
                log["failed"].append({"url": url, "status": response.status_code if response else None})
                continue

            if "text/html" not in response.headers.get("content-type", ""):
                log["skipped_non_html"].append(url)
                continue

            page = {
                "url": url,                                          # address from the sitemap
                "final_url": str(response.url),                      # address after redirects
                "section": section_of(url),
                "fetched_at": datetime.now(timezone.utc).isoformat(),  # collection date (for refresh)
                "html": response.text,
            }
            path.write_text(json.dumps(page, ensure_ascii=False), encoding="utf-8")
            log["saved"].append(url)

    LOG_PATH.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved: {len(log['saved'])}  |  already downloaded: {log['already_downloaded']}  |  "
          f"failed: {len(log['failed'])}  |  non-HTML skipped: {len(log['skipped_non_html'])}")
    print(f"log: {LOG_PATH}")


if __name__ == "__main__":
    main()
