"""Inspect fnx.co.il before crawling: robots.txt, sitemap, site sections, HTML vs JavaScript.

Run: python -m pipeline.inspect_site
Output: printed summary + data/site_report.json
"""
import json
import time
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree

import httpx
import trafilatura

import config

REPORT_PATH = Path("data/site_report.json")
MAX_SITEMAPS = 30          # safety limit when a sitemap index points to many sitemaps
MIN_TEXT_CHARS = 300       # less extracted text than this suggests a JavaScript-rendered page

# Markers of client-side frameworks that render content with JavaScript
JS_MARKERS = ['id="__next"', 'id="root"', "ng-app", "<app-root", "id=\"app\"", "window.__NUXT__"]


def fetch(client: httpx.Client, url: str) -> httpx.Response | None:
    """GET a URL politely; return None on network errors."""
    time.sleep(config.CRAWL_DELAY_SEC)
    try:
        response = client.get(url)
        print(f"  {response.status_code}  {url}")
        return response
    except httpx.HTTPError as error:
        print(f"  ERROR  {url}  ({error})")
        return None


def check_robots(client: httpx.Client) -> dict:
    url = f"{config.BASE_URL}/robots.txt"
    response = fetch(client, url)
    if response is None or response.status_code != 200:
        return {"found": False, "disallow": [], "sitemaps": []}

    lines = [line.strip() for line in response.text.splitlines()]
    disallow = [line.split(":", 1)[1].strip() for line in lines if line.lower().startswith("disallow:")]
    sitemaps = [line.split(":", 1)[1].strip() for line in lines if line.lower().startswith("sitemap:")]
    return {"found": True, "disallow": disallow, "sitemaps": sitemaps, "raw": response.text}


def parse_sitemap(xml_text: str) -> tuple[list[str], list[str]]:
    """Return (page_urls, child_sitemap_urls) from a sitemap or sitemap index."""
    root = ElementTree.fromstring(xml_text.encode("utf-8"))
    locs = [el.text.strip() for el in root.iter() if el.tag.endswith("loc") and el.text]
    if root.tag.endswith("sitemapindex"):
        return [], locs
    return locs, []


def collect_sitemap_urls(client: httpx.Client, start_urls: list[str]) -> list[str]:
    queue = list(start_urls) or [f"{config.BASE_URL}/sitemap.xml"]
    seen, pages = set(), []
    while queue and len(seen) < MAX_SITEMAPS:
        sitemap_url = queue.pop(0)
        if sitemap_url in seen:
            continue
        seen.add(sitemap_url)
        response = fetch(client, sitemap_url)
        if response is None or response.status_code != 200:
            continue
        try:
            page_urls, child_sitemaps = parse_sitemap(response.text)
        except ElementTree.ParseError:
            print(f"  could not parse XML: {sitemap_url}")
            continue
        pages.extend(page_urls)
        queue.extend(child_sitemaps)
    return sorted(set(pages))


def group_by_section(urls: list[str]) -> dict[str, int]:
    """Count URLs by their first path segment, e.g. /insurance/home -> 'insurance'."""
    sections = Counter()
    for url in urls:
        path = unquote(urlparse(url).path).strip("/")
        sections[path.split("/")[0] if path else "(home)"] += 1
    return dict(sections.most_common())


def check_rendering(client: httpx.Client, url: str) -> dict:
    """Check whether the page's text is present in the raw HTML or rendered by JavaScript."""
    response = fetch(client, url)
    if response is None or response.status_code != 200:
        return {"url": url, "ok": False}

    html = response.text
    text = trafilatura.extract(html) or ""
    markers = [marker for marker in JS_MARKERS if marker in html]
    return {
        "url": url,
        "ok": True,
        "html_chars": len(html),
        "extracted_text_chars": len(text),
        "js_markers": markers,
        "likely_js_rendered": len(text) < MIN_TEXT_CHARS,
        "text_preview": text[:300],
    }


def main() -> None:
    robot_parser = RobotFileParser()
    headers = {"User-Agent": config.USER_AGENT, "Accept-Language": "he-IL,he;q=0.9"}

    with httpx.Client(headers=headers, follow_redirects=True, timeout=30) as client:
        print("\n[1] robots.txt")
        robots = check_robots(client)
        if robots["found"]:
            robot_parser.parse(robots["raw"].splitlines())

        print("\n[2] sitemap")
        urls = collect_sitemap_urls(client, robots["sitemaps"])
        allowed = [url for url in urls if not robots["found"] or robot_parser.can_fetch(config.USER_AGENT, url)]

        print("\n[3] HTML vs JavaScript")
        samples = [config.BASE_URL] + allowed[len(allowed) // 2: len(allowed) // 2 + 2]
        rendering = [check_rendering(client, url) for url in samples]

    sections = group_by_section(allowed)
    report = {
        "base_url": config.BASE_URL,
        "robots": {key: value for key, value in robots.items() if key != "raw"},
        "sitemap_url_count": len(urls),
        "allowed_url_count": len(allowed),
        "sections": sections,
        "rendering": rendering,
        "sample_urls": allowed[:50],
    }
    REPORT_PATH.parent.mkdir(exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n===== SUMMARY =====")
    print(f"robots.txt found: {robots['found']}  |  disallow rules: {len(robots['disallow'])}")
    print(f"sitemap URLs: {len(urls)}  |  allowed by robots: {len(allowed)}")
    print("top sections:")
    for name, count in list(sections.items())[:20]:
        print(f"  {count:5d}  /{name}")
    for item in rendering:
        if item["ok"]:
            verdict = "JavaScript (needs Playwright)" if item["likely_js_rendered"] else "plain HTML (httpx is enough)"
            print(f"rendering: {verdict}  |  text chars: {item['extracted_text_chars']}  |  {item['url']}")
    print(f"\nfull report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
