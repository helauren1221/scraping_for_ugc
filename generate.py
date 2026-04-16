#!/usr/bin/env python3
"""
generate.py — yourTMJ Weekly Creator Intel Page Generator

Usage:
    python generate.py                        # API mode (default)
    python generate.py --source csv           # CSV mode
    python generate.py --week 2026-W15
    python generate.py --source csv --meta data/my_ads.csv
"""
import argparse
import datetime
import sys

from dotenv import load_dotenv

load_dotenv()


def current_week() -> str:
    today = datetime.date.today()
    return today.strftime("%G-W%V")


def main():
    parser = argparse.ArgumentParser(description="Generate yourTMJ weekly creator brief")
    parser.add_argument(
        "--week",
        default=current_week(),
        help="ISO week string, e.g. 2026-W15 (default: current week)",
    )
    parser.add_argument(
        "--source",
        choices=["api", "csv"],
        default="api",
        help="Where to pull Meta ad data from (default: api)",
    )
    parser.add_argument(
        "--meta",
        default="data/meta_ads.csv",
        help="[CSV mode] Path to Ads Manager CSV export",
    )
    parser.add_argument(
        "--external",
        default="data/external_inspo.csv",
        help="Path to external inspiration CSV (default: data/external_inspo.csv)",
    )
    parser.add_argument(
        "--output",
        default="output/index.html",
        help="Output HTML path (default: output/index.html)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=5,
        help="Number of top Meta ads to show (default: 5)",
    )
    parser.add_argument(
        "--trello",
        action="store_true",
        default=False,
        help="Pull content ideas from the Trello Ideas board (requires TRELLO_* env vars)",
    )
    parser.add_argument(
        "--trello-limit",
        type=int,
        default=5,
        help="Max number of Trello cards to show (default: 5)",
    )
    parser.add_argument(
        "--newsletter-limit",
        type=int,
        default=10,
        help="Max total newsletter posts to show (default: 10)",
    )
    args = parser.parse_args()

    print(f"  Week:   {args.week}")
    print(f"  Source: Meta Marketing API" if args.source == "api" else f"  Source: CSV ({args.meta})")
    print()

    # Step 1 — Load Meta ads
    if args.source == "api":
        from adapters.meta_api import load_meta_ads_from_api
        import requests as _requests
        print("Fetching Meta ads from Marketing API...")
        try:
            meta_items = load_meta_ads_from_api(week=args.week)
        except _requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 400:
                err = e.response.json().get("error", {})
                if err.get("code") == 80004:
                    print("\n  ERROR: Meta API rate limit hit. Wait a few minutes and try again.")
                    print(f"  (Meta error: {err.get('message', '')})")
                    sys.exit(1)
            print(f"\n  ERROR: Meta API request failed: {e}")
            sys.exit(1)
        print(f"  {len(meta_items)} ads loaded, sorted by Results")
    else:
        from adapters.meta_csv import load_meta_ads
        print("Loading Meta ads from CSV...")
        meta_items = load_meta_ads(args.meta, week=args.week)
        print(f"  {len(meta_items)} ads loaded, sorted by Results")

    meta_items = meta_items[: args.top]
    print(f"  Showing top {len(meta_items)} ads")

    # Step 2 — Load external inspiration
    from adapters.external_csv import load_external_inspo
    print("Loading external inspiration...")
    external_items = load_external_inspo(args.external, week=args.week)
    print(f"  {len(external_items)} items loaded")

    # Step 2b — Load newsletter posts (always on)
    # Pulls from RSS feeds (data/newsletter_feeds.txt) + scraped sources (SOURCES in newsletter_scrape.py)
    from adapters.newsletter_rss import load_newsletter_items
    from adapters.newsletter_scrape import load_scraped_newsletter_items
    print("Fetching newsletter posts...")
    rss_items = load_newsletter_items(week=args.week, limit=args.newsletter_limit)
    scraped_items = load_scraped_newsletter_items(week=args.week)
    newsletter_items = (rss_items + scraped_items)[: args.newsletter_limit]
    print(f"  {len(newsletter_items)} posts loaded ({len(rss_items)} RSS, {len(scraped_items)} scraped)")

    # Step 2c — Load Trello content ideas (optional, requires --trello flag)
    trello_items = []
    if args.trello:
        from adapters.trello import load_trello_ideas
        print("Fetching content ideas from Trello (label: Ads)...")
        trello_items = load_trello_ideas(week=args.week, limit=args.trello_limit)
        print(f"  {len(trello_items)} cards loaded ({sum(1 for i in trello_items if i.url)} with URLs)")

    # Step 3 — Load brief from data/brief.json
    from report_builder import generate_brief
    print("Loading brief from data/brief.json...")
    brief = generate_brief(meta_items, external_items, week=args.week)
    print(f"  {len(brief.get('themes', []))} themes, {len(brief.get('patterns', []))} patterns")

    # Step 4 — Render HTML
    from page_generator import generate_page
    print("\nRendering HTML page...")
    out_path = generate_page(
        meta_items=meta_items,
        external_items=external_items,
        trello_items=trello_items,
        newsletter_items=newsletter_items,
        brief=brief,
        week=args.week,
        output_path=args.output,
    )

    print(f"\n  Page written to: {out_path}")
    print(f"  Open with: open {out_path}")


if __name__ == "__main__":
    main()
