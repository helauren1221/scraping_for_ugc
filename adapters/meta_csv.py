import csv
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from schema import ContentItem
from tagger import infer_tags


def load_meta_ads(csv_path: str | Path, week: str) -> list[ContentItem]:
    """Read Ads Manager CSV export and return ContentItems sorted by GMV descending."""
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Meta ads CSV not found: {path}")

    items = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_tags = [t.strip() for t in row.get("tags", "").split(";") if t.strip()]
            title = row.get("ad_name", "").strip()
            description = row.get("description", "").strip()
            tags = infer_tags(raw_tags, title, description)
            gmv = float(row.get("gmv", 0) or 0)
            views = int(row.get("views", 0) or 0)
            spend = float(row.get("spend", 0) or 0)

            results_7d = int(row.get("results_7d", 0) or 0)
            results_total = int(row.get("results_total", 0) or 0)

            item = ContentItem(
                id=row.get("ad_id") or str(uuid.uuid4()),
                source="meta",
                title=row.get("ad_name", "").strip(),
                description=row.get("description", "").strip(),
                url=row.get("ad_url", "").strip(),
                thumbnail_url=row.get("thumbnail_url", "").strip(),
                tags=tags,
                metrics={"gmv": gmv, "views": views, "spend": spend, "results_7d": results_7d, "results_total": results_total},
                notes="",
                week=week,
                video_url=row.get("video_url", "").strip(),
            )
            items.append(item)

    # Sort by GMV descending (highest performing ads first)
    items.sort(key=lambda x: x.metrics["gmv"], reverse=True)
    return items
