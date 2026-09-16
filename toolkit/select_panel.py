#!/usr/bin/env python3
"""
select_panel.py - randomly pick 2-3 beta-reader personas for a manuscript and set up
their isolated living-reference files. Safe to re-run: if a panel already exists for this
manuscript, it just prints the existing panel instead of re-rolling it.

Usage:
  python select_panel.py <manuscript_dir> [count]
  python select_panel.py <manuscript_dir> --personas slug1,slug2[,slug3]
  python select_panel.py --list

  <manuscript_dir>   the novelWriter project folder, or the folder containing a flat .md
                      manuscript
  [count]             optional: force 2 or 3 readers (default: random choice of 2 or 3)
  --personas          explicit slugs instead of a random pick, e.g. when the user asks for
                      specific readers by name. 2 or 3 slugs, comma-separated, from the roster
                      below.
  --list              print the full persona roster (slug/name/label) and exit - no manuscript
                      needed. Useful for picking slugs to pass to --personas.
"""
import argparse
import datetime
import random
import sys
from pathlib import Path

ROSTER = [
    {"slug": "teen_male", "name": "Rohan", "label": "Teen (16, male)"},
    {"slug": "teen_female", "name": "Priya", "label": "Teen (16, female)"},
    {"slug": "ya", "name": "Ananya", "label": "Young adult (21, college)"},
    {"slug": "adult_late20s30s", "name": "Fatima", "label": "Adult (34)"},
    {"slug": "late20s30s_male", "name": "Arjun", "label": "Adult (29, male, genre crossover)"},
    {"slug": "middle_aged", "name": "Deepak", "label": "Middle-aged (47)"},
    {"slug": "middle_aged_female", "name": "Lakshmi", "label": "Middle-aged (45, female, avid genre reader)"},
    {"slug": "older", "name": "Meenakshi", "label": "Older reader (68)"},
    {"slug": "super_fan", "name": "Naveen", "label": "Genre super-fan (25)"},
    {"slug": "casual_reluctant", "name": "Wilson", "label": "Casual/infrequent reader (38)"},
    {"slug": "craft_critic", "name": "Elsa", "label": "Craft-focused reader (52, former editor)"},
]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("manuscript_dir", nargs="?")
    ap.add_argument("count", nargs="?", type=int)
    ap.add_argument("--personas", help="comma-separated persona slugs to use instead of a random pick")
    ap.add_argument("--list", action="store_true", help="print the roster and exit")
    args = ap.parse_args()

    if args.list:
        for p in ROSTER:
            print(f"{p['slug']:<20} {p['name']:<10} {p['label']}")
        return

    if not args.manuscript_dir:
        sys.exit("Usage: select_panel.py <manuscript_dir> [count] [--personas slug1,slug2] | select_panel.py --list")

    target = Path(args.manuscript_dir)
    if not target.exists():
        sys.exit(f"No such directory: {target}")

    reviews_dir = target / "_beta_reviews"
    panel_path = reviews_dir / "panel.md"

    if panel_path.exists():
        print("Panel already selected for this manuscript:")
        print(panel_path.read_text(encoding="utf-8-sig"))
        return

    by_slug = {p["slug"]: p for p in ROSTER}
    if args.personas:
        slugs = [s.strip() for s in args.personas.split(",") if s.strip()]
        unknown = [s for s in slugs if s not in by_slug]
        if unknown:
            sys.exit(f"Unknown persona slug(s): {', '.join(unknown)} - see --list for valid slugs")
        if not (2 <= len(slugs) <= 3):
            sys.exit(f"--personas needs 2 or 3 slugs, got {len(slugs)}")
        panel = [by_slug[s] for s in slugs]
    else:
        count = args.count if args.count else random.choice([2, 3])
        count = max(2, min(3, count))
        panel = random.sample(ROSTER, k=count)

    reviews_dir.mkdir(parents=True, exist_ok=True)

    lines = [
        f"# Beta Reader Panel",
        f"Selected: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "This panel is locked in for this manuscript - do not re-roll once chapters have been",
        "reviewed, or earlier feedback becomes hard to compare against later chapters.",
        "",
    ]
    for p in panel:
        lines.append(f"- **{p['name']}** — {p['label']} (`_beta_reviews/{p['slug']}/`)")
    panel_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    template_path = Path(__file__).parent / "living_reference_template.md"
    template_text = template_path.read_text(encoding="utf-8-sig")

    for p in panel:
        persona_dir = reviews_dir / p["slug"]
        persona_dir.mkdir(parents=True, exist_ok=True)
        lr_path = persona_dir / "living_reference.md"
        if not lr_path.exists():
            text = template_text.replace("{{NAME}}", p["name"]).replace("{{LABEL}}", p["label"])
            lr_path.write_text(text, encoding="utf-8")

    print(f"Panel selected ({len(panel)} readers):")
    for p in panel:
        print(f"  - {p['name']} ({p['label']})")


if __name__ == "__main__":
    main()
