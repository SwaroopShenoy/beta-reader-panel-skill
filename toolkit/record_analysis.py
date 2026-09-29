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

FIELDS = ["OPENER", "STORY_TYPE", "SUMMARY", "QUALITY", "RATING", "CHARACTERS", "SIDEBAR"]
# SIDEBAR is genuinely optional (off-structure asides, "nothing to add" is a fine answer, and
# an empty one shouldn't count as a malformed reply the way a missing SUMMARY or RATING would).
REQUIRED_FIELDS = [f for f in FIELDS if f != "SIDEBAR"]
NONE_MARKERS = {"nothing to add", "none", "n/a", "nothing", "no notes", "-"}
KEY_RE = re.compile(r"^([A-Z_]+):\s*(.*)$")


def parse_output(text: str) -> tuple[dict, list[str]]:
    """Fields can run multi-line (paragraphs, bullet lists) - a line only starts a new field
    when it matches KEY: at the very start; everything else, blank lines included, is appended
    to whichever field is currently open so bullet structure and paragraph breaks survive."""
    values = {k: "" for k in FIELDS}
    current = None
    for line in text.splitlines():
        m = KEY_RE.match(line)
        if m and m.group(1) in FIELDS:
            current = m.group(1)
            values[current] = m.group(2).strip()
        elif current is not None:
            values[current] = (values[current] + "\n" + line.rstrip()).strip("\n") if values[current] else line.rstrip()
    for k in FIELDS:
        values[k] = values[k].strip()
    missing = [k for k in REQUIRED_FIELDS if not values[k]]
    if missing:
        sys.stderr.write(f"Warning: missing/empty fields in output: {', '.join(missing)}\n")
    return values, missing


CHAR_BULLET_RE = re.compile(r"^-\s+\*\*(.+?)\*\*\s*(.*)$")
DYNAMICS_START_RE = re.compile(r"^-\s+\*\*relationship dynamics\*\*", re.IGNORECASE)
RATING_RE = re.compile(r"(\d+(?:\.\d+)?)\s*/\s*10")
CHAPTER_ENTRY_RE = re.compile(r"^### (.+)$", re.MULTILINE)
CHARACTERS_SECTION_RE = re.compile(
    r"#### Characters & relationships\n(.*?)(?=\n#### |\n### |\Z)", re.DOTALL
)
RATING_SECTION_RE = re.compile(r"#### Rating\n(.*?)(?=\n#### |\n### |\Z)", re.DOTALL)


def parse_character_field(characters_text: str) -> tuple[dict, list[str], str]:
    """Split a CHARACTERS field's raw text into {name: bullet line} plus first-seen order, and
    the trailing 'relationship dynamics' block (if any) as one block of text. Mechanical parse
    only - no LLM call - this is what lets the roster be genuinely cumulative without resending
    every character's full history through the model each chapter."""
    chars, order, dynamics = {}, [], []
    in_dynamics = False
    for raw_line in characters_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if DYNAMICS_START_RE.match(line) or line.lower().startswith("relationship dynamics"):
            in_dynamics = True
            dynamics.append(line)
            continue
        if in_dynamics:
            dynamics.append(line)
            continue
        m = CHAR_BULLET_RE.match(line)
        if m:
            name = m.group(1).strip()
            if name not in chars:
                order.append(name)
            chars[name] = line
        elif chars:
            # a wrapped continuation of the previous character's bullet
            last = order[-1]
            chars[last] = chars[last] + " " + line
    return chars, order, "\n".join(dynamics)


def build_cumulative_roster(existing_text: str, new_chapter_label: str, new_characters: str) -> str:
    """Rebuild the full cumulative character roster by scanning every '#### Characters &
    relationships' block already in the chapter log plus the one just produced, oldest to
    newest, so a later chapter's bullet for a name overwrites an earlier one but characters
    absent from the newest chapter are NOT dropped. Dynamics block: keep only the most recent
    chapter's, since relationship *state* (not history) is what's useful in a running digest."""
    chars, order = {}, []
    dynamics = ""
    for m in CHARACTERS_SECTION_RE.finditer(existing_text):
        c_chars, c_order, c_dynamics = parse_character_field(m.group(1))
        for name in c_order:
            if name not in chars:
                order.append(name)
            chars[name] = c_chars[name]
        if c_dynamics:
            dynamics = c_dynamics
    c_chars, c_order, c_dynamics = parse_character_field(new_characters)
    for name in c_order:
        if name not in chars:
            order.append(name)
        chars[name] = c_chars[name]
    if c_dynamics:
        dynamics = c_dynamics
    lines = [chars[name] for name in order]
    if dynamics:
        lines.append(dynamics)
    return "\n  ".join(lines) if lines else new_characters


def build_rating_trend(existing_text: str, new_rating: str) -> str:
    """Mechanical rating trend (latest + running average) computed from every '#### Rating'
    block already logged plus the new one - replaces resending a full QUALITY paragraph into
    Running notes every chapter, which was the main source of bloat there."""
    ratings = [float(m.group(1)) for sec in RATING_SECTION_RE.finditer(existing_text)
               for m in RATING_RE.finditer(sec.group(1))]
    new_nums = [float(m.group(1)) for m in RATING_RE.finditer(new_rating)]
    ratings += new_nums
    latest = new_nums[0] if new_nums else (ratings[-1] if ratings else None)
    if latest is None:
        return new_rating.splitlines()[0] if new_rating else ""
    avg = sum(ratings) / len(ratings)
    return f"{latest:g}/10 latest (avg so far: {avg:.1f}/10 over {len(ratings)} chapter{'s' if len(ratings) != 1 else ''})"


def render_running_notes(existing_text: str, chapter_label: str, v: dict) -> str:
    roster = build_cumulative_roster(existing_text, chapter_label, v["CHARACTERS"])
    trend = build_rating_trend(existing_text, v["RATING"])
    return (
        "## Running notes\n"
        f"- Story type (current read): {v['STORY_TYPE']}\n"
        f"- Quality trend: {trend}\n"
        f"- Character roster & relationships (cumulative):\n  {roster}\n"
    )


def render_chapter_entry(chapter_label: str, v: dict, missing: list[str]) -> str:
    flag = ""
    if len(missing) >= 2:
        flag = (
            f"⚠ _Possibly malformed reply - {len(missing)}/{len(REQUIRED_FIELDS)} required "
            f"fields were missing ({', '.join(missing)}). Worth a manual look._\n\n"
        )
    parts = [f"### {chapter_label}", flag.rstrip("\n")] if flag else [f"### {chapter_label}"]
    if v["OPENER"]:
        parts.append(v["OPENER"])
    parts += [
        f"#### What kinda story is this?\n{v['STORY_TYPE']}",
        f"#### Summary\n{v['SUMMARY']}",
        f"#### Writing quality\n{v['QUALITY']}",
        f"#### Rating\n{v['RATING']}",
        f"#### Characters & relationships\n{v['CHARACTERS']}",
    ]
    if v["SIDEBAR"] and v["SIDEBAR"].strip().lower() not in NONE_MARKERS:
        parts.append(f"#### Sidebar\n{v['SIDEBAR']}")
    return "\n\n".join(p for p in parts if p.strip()) + "\n"


def update_living_reference(lr_path: Path, chapter_label: str, v: dict, missing: list[str]):
    text = lr_path.read_text(encoding="utf-8-sig")

    if "## Running notes" in text and "## Chapter log" in text:
        before, _, rest = text.partition("## Running notes")
        _, _, after_log_heading = rest.partition("## Chapter log")
        existing_log = after_log_heading  # prior chapter entries only, for the roster/trend scan
        new_text = (
            before
            + render_running_notes(existing_log, chapter_label, v)
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
        print(f"  WARNING: {len(missing)}/{len(REQUIRED_FIELDS)} required fields were missing - flagged in the file for review.")


if __name__ == "__main__":
    main()
