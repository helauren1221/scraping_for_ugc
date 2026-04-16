"""
Meta Marketing API adapter.

Pulls ad-level performance data and preview links from the Graph API,
ranks ads by purchase Results (offsite_conversion.fb_pixel_purchase).

Required env vars:
    META_ACCESS_TOKEN   — User or System User token with ads_read permission
    META_AD_ACCOUNT_ID  — Format: act_XXXXXXXXX

Optional env vars:
    META_DATE_PRESET    — Default: last_7d. Options: last_14d, last_30d,
                          this_week_sun_today, last_week_sun_sat
    META_API_VERSION    — Default: v21.0
"""

import os
import sys
import uuid
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from schema import ContentItem
from tagger import infer_tags

# Purchase action types to look for, in priority order
PURCHASE_ACTION_TYPES = [
    "offsite_conversion.fb_pixel_purchase",
    "omni_purchase",
    "purchase",
]

BASE_URL = "https://graph.facebook.com"


def _api_version() -> str:
    return os.environ.get("META_API_VERSION", "v21.0")


def _token() -> str:
    token = os.environ.get("META_ACCESS_TOKEN", "")
    if not token:
        raise EnvironmentError(
            "META_ACCESS_TOKEN not set. Add it to your .env file."
        )
    return token


def _account_id() -> str:
    account_id = os.environ.get("META_AD_ACCOUNT_ID", "")
    if not account_id:
        raise EnvironmentError(
            "META_AD_ACCOUNT_ID not set. Add it to your .env file."
        )
    # Ensure it starts with act_
    if not account_id.startswith("act_"):
        account_id = f"act_{account_id}"
    return account_id


def _paginate(url: str, params: dict) -> list[dict]:
    """Fetch all pages from a Graph API endpoint."""
    results = []
    while url:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if "error" in data:
            raise RuntimeError(
                f"Meta API error: {data['error'].get('message', data['error'])}"
            )

        results.extend(data.get("data", []))

        # Follow pagination
        paging = data.get("paging", {})
        next_url = paging.get("next")
        if next_url:
            url = next_url
            params = {}  # params are baked into the next URL
        else:
            break

    return results


def _fetch_insights(account_id: str, token: str, date_preset: str) -> dict[str, dict]:
    """
    Fetch ad-level insights for the given date range.
    Returns a dict keyed by ad_id.
    """
    url = f"{BASE_URL}/{_api_version()}/{account_id}/insights"
    params = {
        "access_token": token,
        "level": "ad",
        "date_preset": date_preset,
        "fields": "ad_id,ad_name,spend,impressions,actions",
        "limit": 100,
    }
    rows = _paginate(url, params)

    insights: dict[str, dict] = {}
    for row in rows:
        ad_id = row.get("ad_id")
        if not ad_id:
            continue

        # Extract purchase results
        results = 0
        for action in row.get("actions", []):
            if action.get("action_type") in PURCHASE_ACTION_TYPES:
                results += int(float(action.get("value", 0)))

        insights[ad_id] = {
            "results": results,
            "spend": float(row.get("spend", 0)),
            "impressions": int(row.get("impressions", 0)),
            "ad_name": row.get("ad_name", ""),
        }

    return insights


def _fetch_ads(account_id: str, token: str) -> list[dict]:
    """
    Fetch ads with their creative copy and thumbnail images.
    """
    url = f"{BASE_URL}/{_api_version()}/{account_id}/ads"
    params = {
        "access_token": token,
        "fields": "id,name,status,creative{id,body,title,image_url,thumbnail_url}",
        "limit": 100,
        "effective_status": '["ACTIVE","PAUSED","ARCHIVED"]',
    }
    return _paginate(url, params)


def _fetch_video_source(video_id: str, token: str) -> str:
    """Fetch the direct CDN video URL for a Meta video asset."""
    url = f"{BASE_URL}/{_api_version()}/{video_id}"
    params = {"access_token": token, "fields": "source"}
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        return data.get("source", "")
    except Exception:
        return ""


def _extract_creative_fields(ad: dict) -> tuple[str, str, str, str]:
    """Pull title, body text, thumbnail URL, and creative ID from the creative field."""
    creative = ad.get("creative", {})
    title = creative.get("title", "").strip()
    body = creative.get("body", "").strip()
    # Prefer image_url (full resolution) over thumbnail_url (low-res preview)
    thumbnail_url = (
        creative.get("image_url", "").strip()
        or creative.get("thumbnail_url", "").strip()
    )
    creative_id = str(creative.get("id", "")).strip()

    return title, body, thumbnail_url, creative_id


def _fetch_video_id_from_creative(creative_id: str, token: str) -> str:
    """Fetch the video_id for a creative (separate call, avoids 500 on bulk fetch)."""
    if not creative_id:
        return ""
    url = f"{BASE_URL}/{_api_version()}/{creative_id}"
    params = {"access_token": token, "fields": "video_id"}
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        return str(data.get("video_id", "")).strip()
    except Exception:
        return ""


def load_meta_ads_from_api(week: str) -> list[ContentItem]:
    """
    Fetch ads from Meta Marketing API and return ContentItems
    sorted by purchase Results descending.
    """
    token = _token()
    account_id = _account_id()
    date_preset = os.environ.get("META_DATE_PRESET", "last_7d")

    print(f"  Fetching insights ({date_preset})...")
    insights = _fetch_insights(account_id, token, date_preset)
    print(f"  Found insights for {len(insights)} ads")

    print(f"  Fetching lifetime insights...")
    insights_lifetime = _fetch_insights(account_id, token, "maximum")
    print(f"  Found lifetime insights for {len(insights_lifetime)} ads")

    print(f"  Fetching ad details...")
    ads = _fetch_ads(account_id, token)
    print(f"  Found {len(ads)} ads")

    items = []
    for ad in ads:
        ad_id = ad.get("id")
        ad_name = ad.get("name", "").strip()

        # Skip ads with no performance data this period
        if ad_id not in insights:
            continue

        ad_insights = insights[ad_id]
        creative_title, creative_body, thumbnail_url, creative_id = _extract_creative_fields(ad)

        title = ad_name
        description = creative_body or creative_title

        # Ad Library URL is fully public — no login required
        ad_library_url = f"https://www.facebook.com/ads/library/?id={ad_id}"

        tags = infer_tags([], title, description)

        lifetime = insights_lifetime.get(ad_id, {})

        item = ContentItem(
            id=ad_id or str(uuid.uuid4()),
            source="meta",
            title=title,
            description=description,
            url=ad_library_url,
            thumbnail_url=thumbnail_url,
            tags=tags,
            metrics={
                "results_7d": ad_insights["results"],
                "results_total": lifetime.get("results", 0),
                "spend": ad_insights["spend"],
                "impressions": ad_insights["impressions"],
            },
            notes="",
            week=week,
            video_url="",  # filled in below after sorting
        )
        # Store video_id temporarily so we can fetch sources for top ads only
        item._creative_id = creative_id  # type: ignore[attr-defined]
        items.append(item)

    # Sort by 7-day Results descending
    items.sort(key=lambda x: x.metrics.get("results_7d", 0), reverse=True)

    # Fetch video source URLs only for top 10 (avoid hammering the API)
    print(f"  Fetching video URLs for top ads...")
    for item in items[:10]:
        cid = getattr(item, "_creative_id", "")
        if cid:
            vid = _fetch_video_id_from_creative(cid, token)
            if vid:
                item.video_url = _fetch_video_source(vid, token)

    return items
