#!/usr/bin/env python3
"""
build_analyst_prompt.py - assemble everything the lightweight "analyst" mode needs to review
one chapter into a single plain-text bundle: running notes + trimmed chapter-log history + the
chapter text + fixed output-format instructions. Same mechanical/LLM split as
build_persona_prompt.py, but there's no persona card here - this is one continuously-updated
story analysis, not an in-character reader reaction. See build_persona_prompt.py for the
general rationale (tool-agnostic single text-in/text-out step, fixed subagent overhead, etc.).

Usage:
  python build_analyst_prompt.py <review_root> <chapter_source> <chapter_ref> [--history N] [--out FILE] [--chapter-file FILE] [--continuing]

  <review_root>       folder containing (or to contain) _story_analysis/ - the novelWriter
                      project dir, or the folder holding a flat .md manuscript
  <chapter_source>    where the chapter text actually lives: same as review_root for a
                      novelWriter project, or the path to the .md file for a flat manuscript
  <chapter_ref>       handle/title (novelWriter) or heading substring (flat) identifying the
                      chapter
  --history N          how many most-recent chapter-log entries to include in full (default 8)
                      - Running notes are always included in full regardless
  --out FILE           write the bundle to a file instead of stdout (also writes FILE.label,
                      same as build_persona_prompt.py)
  --chapter-file FILE  reuse already-fetched chapter text instead of shelling out to nw_tool.py
  --continuing         lean bundle for an analyst subagent already alive from an earlier
                      chapter this session (skips the instructions restating - just chapter +
                      short reminder, since the live agent already has the format in memory)
"""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

MIN_CHAPTER_CHARS = 50

TOOLKIT_DIR = Path(__file__).parent
NW_TOOL_PATH = Path(
    os.environ.get(
        "NW_TOOL_PATH",
        Path(os.environ.get("USERPROFILE", str(Path.home())))
        / ".claude" / "skills" / "manuscript-editor" / "toolkit" / "nw_tool.py",
    )
)

INSTRUCTIONS = """\
=== INSTRUCTIONS ===
You are doing a plain analytical read of this chapter - not role-playing a reader, not an
editor doing line edits. Just: what kind of story this is, what happens in this chapter, how
well it's written, and who's involved.

Do not use any tools. Do not read any files. Do not search anything. Everything you need is
already in this prompt - just reply with plain text in the format below.

Reply with ONLY the following fields, each as "KEY: value" on its own line (a value may wrap
onto the next line as long as it doesn't start with another KEY: - keep each field tight and
concrete, not padded):

STORY_TYPE: <what kind of story this is so far - genre, tone, subgenre drift if any. One line.>
SUMMARY: <detailed summary of what actually happens in THIS chapter - scenes, beats, reveals,
  in order. This is the record of the chapter, so be thorough, not just a gist.>
QUALITY: <honest assessment of the writing itself this chapter - prose, pacing, dialogue,
  structure. Specific, not just "good" or "needs work".>
RATING: <X/10 for this chapter>
CHARACTERS: <who appears this chapter and what state their relationships are in - who's close,
  who's tense, what shifted. Note any new characters or relationship changes plainly.>

Nothing else - no preamble, no markdown headers, just those five lines.
"""

CONTINUING_REMINDER = """\
=== INSTRUCTIONS ===
Same analytical read as before - same rules, no role-play, no tools, everything you need is
already in this prompt. Reply with ONLY the same five "KEY: value" lines as before (STORY_TYPE,
SUMMARY, QUALITY, RATING, CHARACTERS), nothing else. STORY_TYPE and CHARACTERS are your running
record - update them to reflect the current state, don't just repeat last chapter's values
unchanged unless nothing has actually shifted.
"""


def extract_chapter_label(chapter_text: str, fallback: str) -> str:
    for line in chapter_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        m = re.match(r"^#{1,6}\s+(.*\S)\s*$", stripped)
        return m.group(1) if m else fallback
    return fallback


def fetch_chapter(chapter_source: str, chapter_ref: str) -> str:
    src = Path(chapter_source)
    if src.is_dir():
        cmd = [sys.executable, str(NW_TOOL_PATH), "get", str(src), chapter_ref]
    elif src.is_file():
        cmd = [sys.executable, str(NW_TOOL_PATH), "flat-get", str(src), chapter_ref]
    else:
        sys.exit(f"chapter_source not found: {chapter_source}")
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        sys.exit(f"nw_tool.py failed:\n{result.stderr}")
    return result.stdout.strip()


def check_chapter_text(chapter_text: str, chapter_ref: str):
    if len(chapter_text.strip()) < MIN_CHAPTER_CHARS:
        sys.exit(
            f"Chapter text for '{chapter_ref}' is suspiciously short "
            f"({len(chapter_text.strip())} chars) - refusing to build a bundle around what's "
            f"probably an empty fetch, a wrong chapter_ref, or a --chapter-file pointed at the "
            f"wrong file. Check the source before retrying."
        )


def trim_history(living_reference_text: str, history_n: int) -> str:
    """Same trimming approach as build_persona_prompt.py: Running notes always in full, the
    most recent N chapter-log entries in full, older ones condensed to title + rating."""
    if "## Chapter log" not in living_reference_text:
        return living_reference_text

    head, _, log = living_reference_text.partition("## Chapter log")
    entries = [e for e in log.split("\n### ") if e.strip()]
    entries = ["### " + e if not e.startswith("### ") else e for e in entries]

    if history_n <= 0 or len(entries) <= history_n:
        return head + "## Chapter log\n" + "\n".join(entries)

    omitted, recent = entries[:-history_n], entries[-history_n:]
    digest_lines = []
    for e in omitted:
        lines = e.splitlines()
        heading = lines[0][len("### "):].strip() if lines else "?"
        rating = next((l.split(":", 1)[1].strip() for l in lines if l.startswith("Rating:")), "?")
        digest_lines.append(f"- {heading} (rated {rating})")

    digest = (
        f"_Earlier chapters, condensed to title + rating only so this bundle stays small - if "
        f"this new chapter seems to be paying off or referencing one of these, treat it as a "
        f"real callback, not a fresh idea:_\n" + "\n".join(digest_lines) + "\n\n"
        f"_Full detail below is only the {len(recent)} most recent chapter(s):_\n"
    )

    return head + "## Chapter log\n" + digest + "\n".join(recent)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("review_root")
    ap.add_argument("chapter_source")
    ap.add_argument("chapter_ref")
    ap.add_argument("--history", type=int, default=8)
    ap.add_argument("--out")
    ap.add_argument("--chapter-file")
    ap.add_argument("--continuing", action="store_true")
    args = ap.parse_args()

    if args.chapter_file:
        chapter_text = Path(args.chapter_file).read_text(encoding="utf-8-sig").strip()
    else:
        chapter_text = fetch_chapter(args.chapter_source, args.chapter_ref)
    check_chapter_text(chapter_text, args.chapter_ref)
    chapter_label = extract_chapter_label(chapter_text, fallback=args.chapter_ref)

    if args.continuing:
        bundle = (
            "=== NEW CHAPTER TO ANALYZE ===\n" + chapter_text + "\n\n"
            + CONTINUING_REMINDER
        )
    else:
        lr_path = Path(args.review_root) / "_story_analysis" / "living_reference.md"
        if not lr_path.exists():
            sys.exit(
                f"No living_reference.md at {lr_path} - run analyst mode's setup "
                f"(init_analyst.py) first."
            )
        history_text = trim_history(lr_path.read_text(encoding="utf-8-sig"), args.history)

        bundle = (
            "=== YOUR ANALYSIS SO FAR ===\n" + history_text.strip() + "\n\n"
            "=== NEW CHAPTER TO ANALYZE ===\n" + chapter_text + "\n\n"
            + INSTRUCTIONS
        )

    if args.out:
        Path(args.out).write_text(bundle, encoding="utf-8")
        label_path = Path(str(args.out) + ".label")
        label_path.write_text(chapter_label, encoding="utf-8")
        print(f"Bundle written to {args.out} ({len(bundle)} chars)")
        print(f"Chapter label ({label_path}): {chapter_label}")
    else:
        sys.stdout.write(bundle)


if __name__ == "__main__":
    main()
