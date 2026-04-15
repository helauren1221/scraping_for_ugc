import csv
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from schema import ContentItem
from tagger import infer_tags


def load_external_inspo(csv_path: str | Path, week: str) -> list[ContentItem]:
    """Read external inspiration CSV and return ContentItems."""
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"External inspiration CSV not found: {path}")

    items = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_tags = [t.strip() for t in row.get("tags", "").split(";") if t.strip()]
            title = row.get("title", "").strip()
            notes = row.get("notes", "").strip()
            tags = infer_tags(raw_tags, title, notes)

            item = ContentItem(
                id=str(uuid.uuid4()),
                source="external",
                title=row.get("title", "").strip(),
                description="",
                url=row.get("url", "").strip(),
                thumbnail_url=row.get("thumbnail_url", "").strip(),
                tags=tags,
                metrics={},
                notes=row.get("notes", "").strip(),
                week=week,
            )
            items.append(item)

    return items
