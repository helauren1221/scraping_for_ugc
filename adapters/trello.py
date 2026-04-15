import os
import sys
import uuid
from pathlib import Path

import urllib.request
import urllib.parse
import json

sys.path.insert(0, str(Path(__file__).parent.parent))
from schema import ContentItem
from tagger import infer_tags

TRELLO_API_BASE = "https://api.trello.com/1"


def _get(path: str, params: dict) -> list | dict:
    query = urllib.parse.urlencode(params)
    url = f"{TRELLO_API_BASE}{path}?{query}"
    with urllib.request.urlopen(url) as r:
        return json.loads(r.read())


def load_trello_ideas(week: str, label_filter: str = "Ads", limit: int = 5) -> list[ContentItem]:
    """
    Fetch cards from the configured Trello board, keep only those whose
    labels include `label_filter` (case-insensitive), then sort so cards
    with a URL come first.  Returns up to `limit` ContentItems.
    """
    api_key = os.environ.get("TRELLO_API_KEY", "")
    token = os.environ.get("TRELLO_TOKEN", "")
    board_id = os.environ.get("TRELLO_BOARD_ID", "")

    if not all([api_key, token, board_id]):
        raise EnvironmentError(
            "Missing Trello credentials. Set TRELLO_API_KEY, TRELLO_TOKEN, "
            "and TRELLO_BOARD_ID in your .env file."
        )

    auth = {"key": api_key, "token": token}

    # Fetch all open cards with their attachments and labels
    cards = _get(
        f"/boards/{board_id}/cards/open",
        {**auth, "fields": "name,desc,shortUrl,labels,url", "attachments": "true"},
    )

    # Filter to cards that have the target label
    matched = [
        c for c in cards
        if any(lbl.get("name", "").strip().lower() == label_filter.lower()
               for lbl in c.get("labels", []))
    ]

    # Sort: cards with a non-empty desc URL or attachment first
    def _has_url(card: dict) -> bool:
        if card.get("attachments"):
            return True
        desc = card.get("desc", "")
        return "http://" in desc or "https://" in desc

    matched.sort(key=lambda c: (0 if _has_url(c) else 1))

    items = []
    for card in matched[:limit]:
        # Use the first image attachment as thumbnail, if any
        thumbnail_url = ""
        for att in card.get("attachments", []):
            mime = att.get("mimeType", "")
            if mime.startswith("image/") or att.get("previews"):
                # Trello attachment previews are sorted smallest→largest
                previews = att.get("previews", [])
                if previews:
                    thumbnail_url = previews[-1].get("url", "")
                else:
                    thumbnail_url = att.get("url", "")
                break

        # Pull the first URL out of the description for the card link
        url = card.get("shortUrl", "")
        desc = card.get("desc", "").strip()
        for word in desc.split():
            if word.startswith("http://") or word.startswith("https://"):
                url = word
                break

        label_names = [lbl.get("name", "") for lbl in card.get("labels", [])]
        tags = infer_tags([], card.get("name", ""), desc)

        items.append(ContentItem(
            id=str(uuid.uuid4()),
            source="trello",
            title=card.get("name", "").strip(),
            description="",
            url=url,
            thumbnail_url=thumbnail_url,
            tags=tags,
            metrics={},
            notes=desc,
            week=week,
        ))

    return items
