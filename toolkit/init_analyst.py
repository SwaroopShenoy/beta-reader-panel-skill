#!/usr/bin/env python3
"""
init_analyst.py - set up the lightweight "analyst" mode's living_reference.md for a manuscript.
Safe to re-run: if it already exists, just reports the path instead of overwriting it. No
personas, no panel selection - this mode is a single continuously-updated story analysis.

Usage:
  python init_analyst.py <manuscript_dir>
"""
import sys
from pathlib import Path


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: init_analyst.py <manuscript_dir>")

    target = Path(sys.argv[1])
    if not target.exists():
        sys.exit(f"No such directory: {target}")

    analysis_dir = target / "_story_analysis"
    lr_path = analysis_dir / "living_reference.md"

    if lr_path.exists():
        print(f"Analyst reference already exists: {lr_path}")
        return

    analysis_dir.mkdir(parents=True, exist_ok=True)
    template_path = Path(__file__).parent / "analyst_reference_template.md"
    text = template_path.read_text(encoding="utf-8-sig").replace("{{MANUSCRIPT}}", target.name)
    lr_path.write_text(text, encoding="utf-8")
    print(f"Analyst reference created: {lr_path}")


if __name__ == "__main__":
    main()
