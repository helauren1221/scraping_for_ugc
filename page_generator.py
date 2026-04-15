from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from schema import ContentItem


def generate_page(
    meta_items: list[ContentItem],
    external_items: list[ContentItem],
    brief: dict,
    week: str,
    output_path: str | Path = "output/index.html",
    trello_items: list[ContentItem] | None = None,
    newsletter_items: list[ContentItem] | None = None,
) -> Path:
    """Render the weekly HTML page and write to output_path."""
    template_dir = Path(__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=True)
    template = env.get_template("weekly.html")

    # Human-readable week label, e.g. "Week of Apr 7, 2026"
    week_display = _week_display(week)

    html = template.render(
        week=week,
        week_display=week_display,
        brief=brief,
        meta_items=meta_items,
        external_items=external_items,
        trello_items=trello_items or [],
        newsletter_items=newsletter_items or [],
    )

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out


def _week_display(week: str) -> str:
    """Convert '2026-W15' to 'Week of Apr 6, 2026'."""
    try:
        import datetime
        year, wnum = week.split("-W")
        # ISO week: Monday of that week
        monday = datetime.datetime.strptime(f"{year}-W{wnum}-1", "%G-W%V-%u")
        return f"Week of {monday.strftime('%b %-d, %Y')}"
    except Exception:
        return week
