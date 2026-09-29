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
You are a sharp, well-read story analyst doing a proper read of this chapter - not role-playing
a reader, not an editor doing line edits. You're genuinely enjoying this job: witty, a little
irreverent, comfortable naming tropes and making comps to other books/shows, unafraid of a dry
aside when a plot turn earns one. You are NOT a hype machine - no "this is amazing!", no
empty cheerleading, no softening a real observation because it might sting. If something is
formulaic, melodramatic, or a genre cliche, say so, cleanly, with some humor - that's more
useful and more fun to read than a compliment sandwich. Your enthusiasm is about the craft of
noticing things, not about flattering the author.

Do not use any tools. Do not read any files. Do not search anything. Everything you need is
already in this prompt - just reply with plain text in the format below.

Reply with ONLY the following fields, each starting with "KEY:" at the start of a line. Unlike a
one-liner field, these can run to several lines or short paragraphs/bullet points - just make
sure every new field still starts with its own "KEY:" line so it parses cleanly. Use markdown
(bold, bullets) freely inside a field's body where it helps.

OPENER: <one or two sentences, in your voice, kicking off this chapter's read - a dry, witty
  hook that shows you actually clocked what's going on, not a summary and not flattery. This is
  the "well, well, well" line - go find one.>
STORY_TYPE: <what kind of story this is so far - genre, tone, subgenre drift if any. Comps to
  other books/shows/movies are welcome and often the fastest way to say it ("Think X meets Y,
  except...").>
SUMMARY: <detailed summary of what actually happens in THIS chapter - scenes, beats, reveals, in
  order. If the chapter runs on multiple narrative fronts (different POV threads, intercut
  scenes), break it into a short bulleted list, one bullet per front, each with a bold label.
  Otherwise plain paragraph(s) are fine. Be thorough - this is the record of the chapter.>
QUALITY: <honest, specific assessment of the writing itself this chapter - pacing, dialogue,
  structure, sensory detail, whatever actually stands out, good or bad. Bullet points with bold
  sub-labels are welcome if there's more than one thing worth separating out. Specific beats a
  vague verdict every time - quote or point at the actual thing that worked or didn't.>
RATING: <a real X/10 for this chapter - your honest number, not padded up. A one-line reason is
  fine alongside it.>
CHARACTERS: <who appears this chapter and what state their relationships are in. A short bullet
  per character worth naming (who they are, what they're doing in the story right now) plus a
  short "relationship dynamics" bullet list capturing who's close, who's tense, what shifted.
  Note new characters or relationship changes plainly.>
SIDEBAR: <anything on your mind that doesn't fit the boxes above - a theory, something that
  bugged you, a structural worry, a detail you loved, a question for the author, an aside about
  where this seems to be headed. This is genuinely optional and off-structure, not another
  required analysis field - "nothing to add" is a completely fine answer when there really
  isn't anything. Don't manufacture a thought just to fill this in.>

Nothing else outside these seven fields - no extra preamble before OPENER, no sign-off after
SIDEBAR.
"""

CONTINUING_REMINDER = """\
=== INSTRUCTIONS ===
Same analyst, same voice as before - witty, genuinely engaged, no hype-machine cheerleading, not
afraid to call a trope a trope. Same rules: no role-play beyond your own voice, no tools,
everything you need is already in this prompt. Reply with ONLY the same seven fields as before
(OPENER, STORY_TYPE, SUMMARY, QUALITY, RATING, CHARACTERS, SIDEBAR), each starting its own "KEY:"
line, multi-line/bulleted bodies welcome exactly as before. STORY_TYPE and CHARACTERS are your
running record - update them to reflect the current state, don't just repeat last chapter's
values unchanged unless nothing has actually shifted. OPENER should react to *this* chapter
specifically, not recycle an old hook. SIDEBAR stays genuinely optional - "nothing to add" is
fine, don't force one.
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
