from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ContentItem:
    id: str
    source: str          # "meta" | "external"
    title: str
    description: str
    url: str
    thumbnail_url: str   # used for Claude visual analysis
    tags: list[str]      # e.g. ["hook", "testimonial", "ugc", "before_after"]
    metrics: dict        # {"gmv": 0.0, "views": 0, "engagement_rate": 0.0}
    notes: str
    week: str            # "2026-W15"
    video_url: str = ""  # direct CDN video URL for inline playback (optional)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source": self.source,
            "title": self.title,
            "description": self.description,
            "url": self.url,
            "thumbnail_url": self.thumbnail_url,
            "tags": self.tags,
            "metrics": self.metrics,
            "notes": self.notes,
            "week": self.week,
            "video_url": self.video_url,
        }
