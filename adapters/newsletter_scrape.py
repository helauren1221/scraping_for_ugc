"""
newsletter_scrape.py — HTML scraper for newsletters that don't publish RSS feeds.

Each entry in SOURCES defines how to scrape one site's archive page. To add a new
source, append a dict to SOURCES — no other code changes needed.

Usage:
    from adapters.newsletter_scrape import load_scraped_newsletter_items
    items = load_scraped_newsletter_items(week="2026-W16", days_back=14)
"""

from __future__ import annotations

import re
import sys
import uuid
import datetime
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from schema import ContentItem
from tagger import infer_tags

# ── Source definitions ─────────────────────────────────────────────────────────
#
# Each source dict has these keys:
#   name          Display name shown in the brief
#   base_url      Root of the site (used to build absolute post URLs)
#   archive_url   Page that lists recent posts
#   post_pattern  Regex that matches a post path in an href, e.g. r'/p/[\w-]+'
#   date_format   strptime format string for the date strings on the page
#   date_regex    Regex to pull the date string out of each post block
#   title_regex   Regex to extract post title from the block text (first group)
#   desc_regex    Regex to extract description from the block text (first group).
#                 Set to None to skip.
#   thumbnail_url Static fallback thumbnail when the archive page uses the same
#                 image for all posts (common on Beehiiv). Set to "" to skip.

SOURCES: list[dict] = [
    {
        "name": "UGC Ad Examples & Database",
        "base_url": "https://ugcads.beehiiv.com",
        "archive_url": "https://ugcads.beehiiv.com",
        "post_pattern": r"/p/ugc-ad-examples-\d+",
        "date_format": "%b %d, %Y",
        "date_regex": r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{2},\s+\d{4})",
        # Title is "UGC Ad Examples #NNN" — the number is in the slug
        "title_regex": r"(UGC Ad Examples #\d+)",
        # Description is the categories line that follows the title
        "desc_regex": r"UGC Ad Examples #\d+\s+(.+?)(?:\s{2,}|<|$)",
        "thumbnail_url": (
            "https://media.beehiiv.com/cdn-cgi/image/format=auto,width=800,"
            "height=421,fit=scale-down,onerror=redirect/uploads/publication/logo/"
            "628d0d4b-0eb4-4403-8ac5-6b43af5d4998/WINNING_UGC_Ad_Examples.png"
        ),
    },
    # ── Add more sources here ──────────────────────────────────────────────────
    # {
    #     "name": "Example Newsletter",
    #     "base_url": "https://example.substack.com",
    #     "archive_url": "https://example.substack.com/archive",
    #     "post_pattern": r"/p/[\w-]+",
    #     "date_format": "%B %d, %Y",
    #     "date_regex": r"((?:January|February|...) \d+, \d{4})",
    #     "title_regex": r"some-pattern-for-title",
    #     "desc_regex": None,
    #     "thumbnail_url": "",
    # },
]


# ── Helpers ────────────────────────────────────────────────────────────────────

_MONTH_ABBR = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
_MONTH_FULL = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"


def _fetch_html(url: str, timeout: int = 10) -> str | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as exc:
        print(f"    [newsletter] WARNING: could not fetch {url}: {exc}")
        return None


def _strip_tags(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&#x27;", "'", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"&nbsp;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_date(date_str: str, date_format: str) -> datetime.date | None:
    # Normalise "Apr 7" vs "Apr 07" both work with %d
    try:
        return datetime.datetime.strptime(date_str.strip(), date_format).date()
    except ValueError:
        return None


def _scrape_source(source: dict, days_back: int, week: str) -> list[ContentItem]:
    html = _fetch_html(source["archive_url"])
    if not html:
        return []

    cutoff = datetime.date.today() - datetime.timedelta(days=days_back)
    post_re = re.compile(source["post_pattern"])

    # Split the page on each post link occurrence so each chunk belongs to one post
    parts = re.split(r"(?=href=\"" + source["post_pattern"] + r"\")", html)

    seen_slugs: set[str] = set()
    items: list[ContentItem] = []

    for part in parts[1:]:
        slug_m = post_re.search(part)
        if not slug_m:
            continue
        slug = slug_m.group(0)

        # Extract date — must be present. The thumbnail-link occurrence has no
        # date, so this naturally skips it and keeps the text-card occurrence.
        date_m = re.search(source["date_regex"], part)
        if not date_m:
            continue

        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)
        post_date = _parse_date(date_m.group(1), source["date_format"])
        if post_date is None or post_date < cutoff:
            continue

        # Strip tags for text extraction
        text = _strip_tags(part)

        # Extract title
        title = ""
        if source.get("title_regex"):
            tm = re.search(source["title_regex"], text)
            title = tm.group(1).strip() if tm else ""
        if not title:
            # Fallback: grab text between date and next long gap
            after_date = text[text.find(date_m.group(1)) + len(date_m.group(1)):].strip()
            title = after_date.split("  ")[0].strip()[:100]

        # Extract description
        description = ""
        if source.get("desc_regex"):
            dm = re.search(source["desc_regex"], text)
            description = dm.group(1).strip() if dm else ""

        post_url = source["base_url"] + slug
        tags = infer_tags([], title, description)

        items.append(ContentItem(
            id=str(uuid.uuid4()),
            source="newsletter",
            title=title,
            description=description,
            url=post_url,
            thumbnail_url=source.get("thumbnail_url", ""),
            tags=tags,
            metrics={},
            notes=description,
            week=week,
        ))

    return items


# ── Public API ─────────────────────────────────────────────────────────────────

def load_scraped_newsletter_items(
    week: str,
    days_back: int = 14,
) -> list[ContentItem]:
    """
    Scrape all configured SOURCES and return posts published within `days_back` days.

    Args:
        week:      ISO week string, e.g. "2026-W16"
        days_back: How far back to look (default: 14 days to catch weekly newsletters)
    """
    all_items: list[ContentItem] = []
    for source in SOURCES:
        print(f"    Scraping {source['name']}...")
        items = _scrape_source(source, days_back, week)
        print(f"      {len(items)} post(s) found in the last {days_back} days")
        all_items.extend(items)
    return all_items
