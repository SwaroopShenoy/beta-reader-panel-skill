#!/usr/bin/env python3
"""
select_panel.py - randomly pick 2-3 beta-reader personas for a manuscript and set up
their isolated living-reference files. Safe to re-run: if a panel already exists for this
manuscript, it just prints the existing panel instead of re-rolling it.

Usage: python select_panel.py <manuscript_dir> [count]
  <manuscript_dir>  the novelWriter project folder, or the folder containing a flat .md manuscript
  [count]           optional: force 2 or 3 readers (default: random choice of 2 or 3)
"""
import datetime
import random
import sys
from pathlib import Path

ROSTER = [
    {"slug": "teen_male", "name": "Rohan", "label": "Teen (16, male)"},
    {"slug": "teen_female", "name": "Priya", "label": "Teen (16, female)"},
    {"slug": "ya", "name": "Ananya", "label": "Young adult (21, college)"},
    {"slug": "adult_late20s30s", "name": "Fatima", "label": "Adult (34)"},
    {"slug": "middle_aged", "name": "Deepak", "label": "Middle-aged (47)"},
    {"slug": "older", "name": "Meenakshi", "label": "Older reader (68)"},
]


def main():
    if len(sys.argv) < 2:
        sys.exit("Usage: select_panel.py <manuscript_dir> [count]")

    target = Path(sys.argv[1])
    if not target.exists():
        sys.exit(f"No such directory: {target}")

    reviews_dir = target / "_beta_reviews"
    panel_path = reviews_dir / "panel.md"

    if panel_path.exists():
        print("Panel already selected for this manuscript:")
        print(panel_path.read_text(encoding="utf-8"))
        return

    count = int(sys.argv[2]) if len(sys.argv) > 2 else random.choice([2, 3])
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
    template_text = template_path.read_text(encoding="utf-8")

    for p in panel:
        persona_dir = reviews_dir / p["slug"]
        persona_dir.mkdir(parents=True, exist_ok=True)
        lr_path = persona_dir / "living_reference.md"
        if not lr_path.exists():
            text = template_text.replace("{{NAME}}", p["name"]).replace("{{LABEL}}", p["label"])
            lr_path.write_text(text, encoding="utf-8")

    print(f"Panel selected ({count} readers):")
    for p in panel:
        print(f"  - {p['name']} ({p['label']})")


if __name__ == "__main__":
    main()
