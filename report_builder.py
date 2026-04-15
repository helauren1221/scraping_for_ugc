import json
from pathlib import Path
from collections import defaultdict
from schema import ContentItem

BRIEF_PATH = Path(__file__).parent / "data" / "brief.json"


def group_by_tags(items: list[ContentItem]) -> dict[str, list[ContentItem]]:
    """Group items by their tags to surface creative patterns."""
    groups: dict[str, list[ContentItem]] = defaultdict(list)
    for item in items:
        for tag in item.tags:
            groups[tag].append(item)
    return dict(sorted(groups.items(), key=lambda x: len(x[1]), reverse=True))


def generate_brief(
    meta_items: list[ContentItem],
    external_items: list[ContentItem],
    week: str,
) -> dict:
    """
    Load the weekly brief from data/brief.json.

    Edit that file each week before running generate.py.
    Returns a dict with keys: what_is_working, patterns, themes, external_spotlight.
    """
    if not BRIEF_PATH.exists():
        raise FileNotFoundError(
            f"Brief file not found: {BRIEF_PATH}\n"
            "Run generate.py once to create a starter brief.json, then edit it."
        )

    with open(BRIEF_PATH, encoding="utf-8") as f:
        brief = json.load(f)

    required = {"what_is_working", "patterns", "themes", "external_spotlight"}
    missing = required - brief.keys()
    if missing:
        raise ValueError(f"brief.json is missing keys: {missing}")

    return brief
