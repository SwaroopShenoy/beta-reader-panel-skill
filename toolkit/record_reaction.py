#!/usr/bin/env python3
"""
record_reaction.py - parse a persona's raw KEY: value reaction text (as produced per the
format build_persona_prompt.py asks for) and record it into that persona's living_reference.md:
appends a new chapter-log entry, and overwrites the Running Notes block with the persona's
current state. Pure parsing/file I/O - the "mechanical" half again, so the LLM call in between
doesn't need any file-write access of its own.

Usage:
  python record_reaction.py <persona_slug> <review_root> <chapter_label> <reaction_file>

  <chapter_label>   human-readable label for the chapter log heading, e.g. "9 - Apex"
  <reaction_file>   path to a text file containing the raw KEY: value reaction output
"""
import re
import sys
from pathlib import Path

FIELDS = [
    "REACTION", "LIKED", "DISLIKED", "PREDICTION", "RATING",
    "VIBE", "FAVORITE", "LEAST_FAVORITE", "THEORIES", "OPEN_QUESTIONS",
]
KEY_RE = re.compile(r"^([A-Z_]+):\s*(.*)$")


def parse_reaction(text: str) -> dict:
    values = {k: "" for k in FIELDS}
    current = None
    for line in text.splitlines():
        m = KEY_RE.match(line.strip())
        if m and m.group(1) in FIELDS:
            current = m.group(1)
            values[current] = m.group(2).strip()
        elif current and line.strip():
            values[current] = (values[current] + " " + line.strip()).strip()
    missing = [k for k in FIELDS if not values[k]]
    if missing:
        sys.stderr.write(f"Warning: missing/empty fields in reaction: {', '.join(missing)}\n")
    return values


def render_running_notes(v: dict) -> str:
    return (
        "## Running notes\n"
        f"- Current vibe: {v['VIBE']}\n"
        f"- Favorite character: {v['FAVORITE']}\n"
        f"- Least favorite / most annoying: {v['LEAST_FAVORITE']}\n"
        f"- Active theories/predictions: {v['THEORIES']}\n"
        f"- Open questions: {v['OPEN_QUESTIONS']}\n"
    )


def render_chapter_entry(chapter_label: str, v: dict) -> str:
    return (
        f"### Ch {chapter_label}\n"
        f"Reaction: {v['REACTION']}\n"
        f"Liked: {v['LIKED']}\n"
        f"Confused/disliked: {v['DISLIKED']}\n"
        f"Prediction: {v['PREDICTION']}\n"
        f"Rating: {v['RATING']}\n"
    )


def update_living_reference(lr_path: Path, chapter_label: str, v: dict):
    text = lr_path.read_text(encoding="utf-8-sig")

    if "## Running notes" in text and "## Chapter log" in text:
        before, _, rest = text.partition("## Running notes")
        _, _, after_log_heading = rest.partition("## Chapter log")
        new_text = (
            before
            + render_running_notes(v)
            + "\n## Chapter log"
            + after_log_heading.rstrip("\n")
            + "\n\n"
            + render_chapter_entry(chapter_label, v)
        )
    else:
        # Fallback: no template structure found, just append.
        new_text = text.rstrip("\n") + "\n\n" + render_chapter_entry(chapter_label, v)

    lr_path.write_text(new_text, encoding="utf-8")


def main():
    if len(sys.argv) != 5:
        sys.exit("Usage: record_reaction.py <persona_slug> <review_root> <chapter_label> <reaction_file>")

    persona_slug, review_root, chapter_label, reaction_file = sys.argv[1:5]

    lr_path = Path(review_root) / "_beta_reviews" / persona_slug / "living_reference.md"
    if not lr_path.exists():
        sys.exit(f"No living_reference.md for {persona_slug} at {lr_path}")

    raw = Path(reaction_file).read_text(encoding="utf-8-sig")
    values = parse_reaction(raw)
    update_living_reference(lr_path, chapter_label, values)

    print(f"Recorded chapter {chapter_label} for {persona_slug} -> {lr_path}")
    print(f"  Rating: {values['RATING']}")


if __name__ == "__main__":
    main()
