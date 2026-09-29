#!/usr/bin/env python3
"""
record_analysis.py - parse the analyst mode's raw KEY: value output (per build_analyst_prompt.py's
format) and record it into _story_analysis/living_reference.md: appends a new chapter-log entry,
and overwrites the Running notes block with the current state. Mirrors record_reaction.py.

Usage:
  python record_analysis.py <review_root> <chapter_label> <output_file>

  <chapter_label>   human-readable label for the chapter log heading, e.g. "9 - Apex"
  <output_file>     path to a text file containing the raw KEY: value analysis output
"""
import re
import sys
from pathlib import Path

FIELDS = ["STORY_TYPE", "SUMMARY", "QUALITY", "RATING", "CHARACTERS"]
KEY_RE = re.compile(r"^([A-Z_]+):\s*(.*)$")


def parse_output(text: str) -> tuple[dict, list[str]]:
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
        sys.stderr.write(f"Warning: missing/empty fields in output: {', '.join(missing)}\n")
    return values, missing


def render_running_notes(v: dict) -> str:
    return (
        "## Running notes\n"
        f"- Story type (current read): {v['STORY_TYPE']}\n"
        f"- Quality trend: {v['QUALITY']}\n"
        f"- Character roster & relationships (cumulative): {v['CHARACTERS']}\n"
    )


def render_chapter_entry(chapter_label: str, v: dict, missing: list[str]) -> str:
    flag = ""
    if len(missing) >= 2:
        flag = (
            f"⚠ _Possibly malformed reply - {len(missing)}/5 fields were missing "
            f"({', '.join(missing)}). Worth a manual look._\n"
        )
    return (
        f"### {chapter_label}\n"
        + flag
        + f"Story type: {v['STORY_TYPE']}\n"
        f"Summary: {v['SUMMARY']}\n"
        f"Writing quality: {v['QUALITY']}\n"
        f"Rating: {v['RATING']}\n"
        f"Characters & relationships: {v['CHARACTERS']}\n"
    )


def update_living_reference(lr_path: Path, chapter_label: str, v: dict, missing: list[str]):
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
            + render_chapter_entry(chapter_label, v, missing)
        )
    else:
        new_text = text.rstrip("\n") + "\n\n" + render_chapter_entry(chapter_label, v, missing)

    lr_path.write_text(new_text, encoding="utf-8")


def main():
    if len(sys.argv) != 4:
        sys.exit("Usage: record_analysis.py <review_root> <chapter_label> <output_file>")

    review_root, chapter_label, output_file = sys.argv[1:4]

    lr_path = Path(review_root) / "_story_analysis" / "living_reference.md"
    if not lr_path.exists():
        sys.exit(f"No living_reference.md at {lr_path} - run init_analyst.py first.")

    raw = Path(output_file).read_text(encoding="utf-8-sig")
    values, missing = parse_output(raw)
    update_living_reference(lr_path, chapter_label, values, missing)

    print(f"Recorded chapter {chapter_label} -> {lr_path}")
    print(f"  Rating: {values['RATING']}")
    if len(missing) >= 2:
        print(f"  WARNING: {len(missing)}/5 fields were missing - flagged in the file for review.")


if __name__ == "__main__":
    main()
