"""
newsletter_rss.py — Substack/RSS adapter for the yourTMJ weekly brief.

Reads a list of RSS feed URLs from data/newsletter_feeds.txt (one URL per line,
lines starting with # are ignored). Fetches each feed, returns the N most
recent posts across all feeds as ContentItem objects with source="newsletter".

Usage:
    from adapters.newsletter_rss import load_newsletter_items
    items = load_newsletter_items(week="2026-W16", limit=10)
"""

import re
import sys
import uuid
import urllib.request
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).parent.parent))
from schema import ContentItem
from tagger import infer_tags

# Namespaces used in RSS/Atom feeds
_NS = {
    "media": "http://search.yahoo.com/mrss/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "atom": "http://www.w3.org/2005/Atom",
}

_DEFAULT_FEEDS_FILE = Path(__file__).parent.parent / "data" / "newsletter_feeds.txt"


def _load_feed_urls(feeds_file: Path) -> list[str]:
    """Read feed URLs from a text file, skipping blank lines and comments."""
    if not feeds_file.exists():
        return []
    lines = feeds_file.read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]


def _fetch_xml(url: str, timeout: int = 10) -> ET.Element | None:
    """Fetch a URL and parse it as XML. Returns None on any error."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "yourTMJ-brief/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
        return ET.fromstring(raw)
    except Exception as exc:
        print(f"    [newsletter] WARNING: could not fetch {url}: {exc}")
        return None


def _strip_html(text: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _first_img_src(html: str) -> str:
    """Extract the first <img src="..."> from an HTML string."""
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE)
    return m.group(1) if m else ""


def _parse_rss_items(root: ET.Element, feed_url: str) -> list[dict]:
    """Parse an RSS 2.0 or Atom feed into a list of raw dicts."""
    items = []

    # RSS 2.0
    for item in root.findall(".//channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        description = (item.findtext("description") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()

        # Try media:thumbnail or media:content for image
        thumbnail = ""
        media_thumb = item.find("media:thumbnail", _NS)
        if media_thumb is not None:
            thumbnail = media_thumb.get("url", "")
        if not thumbnail:
            media_content = item.find("media:content", _NS)
            if media_content is not None:
                thumbnail = media_content.get("url", "")
        # Fall back to first <img> in description
        if not thumbnail:
            thumbnail = _first_img_src(description)

        # Full content for better tag inference
        full_content = item.findtext(f"{{{_NS['content']}}}encoded") or description

        items.append({
            "title": title,
            "url": link,
            "description": _strip_html(full_content),
            "thumbnail_url": thumbnail,
            "pub_date": pub_date,
            "feed_url": feed_url,
        })

    # Atom feeds (fallback)
    if not items:
        atom_ns = _NS["atom"]
        for entry in root.findall(f"{{{atom_ns}}}entry"):
            title = (entry.findtext(f"{{{atom_ns}}}title") or "").strip()
            link_el = entry.find(f"{{{atom_ns}}}link[@rel='alternate']")
            if link_el is None:
                link_el = entry.find(f"{{{atom_ns}}}link")
            link = link_el.get("href", "") if link_el is not None else ""
            summary = (entry.findtext(f"{{{atom_ns}}}summary") or "").strip()
            content_el = entry.find(f"{{{atom_ns}}}content")
            content = content_el.text or "" if content_el is not None else summary
            pub_date = (entry.findtext(f"{{{atom_ns}}}published") or "").strip()
            thumbnail = _first_img_src(content)

            items.append({
                "title": title,
                "url": link,
                "description": _strip_html(content or summary),
                "thumbnail_url": thumbnail,
                "pub_date": pub_date,
                "feed_url": feed_url,
            })

    return items


def load_newsletter_items(
    week: str,
    limit: int = 10,
    feeds_file: Path | str | None = None,
    per_feed_limit: int = 3,
) -> list[ContentItem]:
    """
    Fetch RSS feeds and return up to `limit` ContentItems sorted newest-first.

    Args:
        week:            ISO week string, e.g. "2026-W16"
        limit:           Total items to return across all feeds
        feeds_file:      Path to feed list file (defaults to data/newsletter_feeds.txt)
        per_feed_limit:  Max items to take from any single feed (prevents one feed
                         from dominating when there are many)
    """
    path = Path(feeds_file) if feeds_file else _DEFAULT_FEEDS_FILE
    feed_urls = _load_feed_urls(path)

    if not feed_urls:
        print(f"    [newsletter] No feed URLs found in {path}")
        return []

    all_raw: list[dict] = []
    for url in feed_urls:
        root = _fetch_xml(url)
        if root is None:
            continue
        raw_items = _parse_rss_items(root, url)
        all_raw.extend(raw_items[:per_feed_limit])

    # Convert to ContentItems
    items: list[ContentItem] = []
    for raw in all_raw[:limit]:
        title = raw["title"]
        description = raw["description"]
        notes = description[:280].rstrip() + ("…" if len(description) > 280 else "")
        tags = infer_tags([], title, description)

        items.append(ContentItem(
            id=str(uuid.uuid4()),
            source="newsletter",
            title=title,
            description=description,
            url=raw["url"],
            thumbnail_url=raw["thumbnail_url"],
            tags=tags,
            metrics={},
            notes=notes,
            week=week,
        ))

    return items
