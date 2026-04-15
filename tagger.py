"""
Auto-tagger: infers creative pattern tags from ad title + description text.

Tags are assigned when any keyword in the rule matches (case-insensitive).
You can add/edit rules below to match your brand's creative vocabulary.
"""

RULES: list[tuple[str, list[str]]] = [
    ("before_after",  ["before", "after", "transformation", "changed my", "difference"]),
    ("testimonial",   ["review", "testimonial", "honest", "my experience", "tried it", "weeks later", "days later"]),
    ("hook",          ["wait", "you won't believe", "stop scrolling", "pov:", "this is why", "the reason"]),
    ("authority",     ["dentist", "doctor", "specialist", "recommended", "prescribed", "clinical", "professional"]),
    ("lifestyle",     ["routine", "morning", "night", "daily", "every day", "part of my", "my life"]),
    ("ugc",           ["unsponsored", "not sponsored", "found this", "obsessed", "i swear"]),
    ("unboxing",      ["unbox", "unboxing", "first impression", "just got", "what's inside", "opening"]),
    ("emotional",     ["pain", "relief", "headache", "stress", "anxiety", "finally", "struggle", "suffer"]),
    ("asmr",          ["asmr", "satisfying", "quiet", "sounds"]),
    ("pov",           ["pov", "point of view"]),
    ("educational",   ["why", "how to", "explain", "science", "did you know", "fact"]),
    ("social_proof",  ["everyone", "people are", "going viral", "trending", "1000s", "thousands"]),
    ("couple",        ["partner", "husband", "wife", "boyfriend", "girlfriend", "we both", "us"]),
    ("sleep",         ["sleep", "sleeping", "night guard", "bedtime", "woke up", "morning jaw"]),
]


def auto_tag(title: str, description: str) -> list[str]:
    """Return a list of tags inferred from the title and description."""
    text = (title + " " + description).lower()
    tags = []
    for tag, keywords in RULES:
        if any(kw in text for kw in keywords):
            tags.append(tag)
    return tags


def infer_tags(existing_tags: list[str], title: str, description: str) -> list[str]:
    """
    Use existing tags if present, otherwise auto-tag.
    Merges both if existing tags are partial.
    """
    if existing_tags:
        return existing_tags
    return auto_tag(title, description)
