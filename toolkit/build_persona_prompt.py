#!/usr/bin/env python3
"""
build_persona_prompt.py - assemble everything one persona needs to react to one chapter into
a single plain-text bundle: persona card + their trimmed reading history + the chapter text +
fixed output-format instructions. Pure file I/O, no LLM call here - this is the "mechanical"
half of the skill, kept separate so the actual reaction-writing step is a single tool-agnostic
text-in/text-out call (any model, any harness), not something that needs Read/Write/Bash access.

Usage:
  python build_persona_prompt.py <persona_slug> <review_root> <chapter_source> <chapter_ref> [--history N] [--out FILE] [--chapter-file FILE]

  <persona_slug>     one of toolkit/personas/*.md, e.g. teen_male
  <review_root>      folder containing (or to contain) _beta_reviews/ - the novelWriter project
                      dir, or the folder holding a flat .md manuscript
  <chapter_source>    where the chapter text actually lives: same as review_root for a
                      novelWriter project, or the path to the .md file for a flat manuscript
  <chapter_ref>       handle/title (novelWriter) or heading substring (flat) identifying the
                      chapter
  --history N          how many most-recent chapter-log entries to include (default 8) - the
                      Running Notes block is always included in full regardless
  --out FILE           write the bundle to a file instead of stdout
  --chapter-file FILE  reuse already-fetched chapter text instead of shelling out to nw_tool.py
                      again. Every persona reacting to the same chapter needs the identical
                      text (that's not a bias risk - it's the shared source material, not
                      reading history/opinions), so when running the panel, fetch the chapter
                      ONCE up front and pass it to every persona's build call with this flag -
                      avoids N redundant Python-subprocess cold starts for identical output.

When --out is used, the chapter's own canonical label (its first heading line, whatever level
it's at, hashes stripped) is also written to "<FILE>.label" - a deterministic, zero-token
derivation with no LLM involvement, meant to be read back and passed straight into
record_reaction.py's <chapter_label> argument so the same book's chapter never gets logged
under slightly different labels across personas or sessions.
"""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

TOOLKIT_DIR = Path(__file__).parent
PERSONAS_DIR = TOOLKIT_DIR / "personas"
NW_TOOL_PATH = Path(
    os.environ.get(
        "NW_TOOL_PATH",
        Path(os.environ.get("USERPROFILE", str(Path.home())))
        / ".claude" / "skills" / "manuscript-editor" / "toolkit" / "nw_tool.py",
    )
)

INSTRUCTIONS = """\
=== INSTRUCTIONS ===
You are role-playing as this specific beta reader reacting to the chapter above. You do not
know any other reader exists - do not reference or imagine other opinions. React only to this
one chapter, honestly, in character. This is a reader's gut reaction, not an editor's critique
- no line edits, no prose fixes, no craft prescriptions.

Reply with ONLY the following fields, each as "KEY: value" on its own line (a value may wrap
onto the next line as long as it doesn't start with another KEY: - just keep each field to a
short paragraph, not an essay):

REACTION: <2-4 sentences, your honest in-character reaction to this chapter>
LIKED: <what worked for you>
DISLIKED: <what didn't, confused you, or annoyed you - "nothing" is a fine answer>
PREDICTION: <a theory or expectation, if you have one - "none yet" is fine>
RATING: <X/10>
VIBE: <your current one-line overall feeling about the book so far>
FAVORITE: <favorite character so far, if any>
LEAST_FAVORITE: <least favorite / most annoying character, if any>
THEORIES: <your active theories about where this is going, one line>
OPEN_QUESTIONS: <what you're still wondering about, one line>

THEORIES and OPEN_QUESTIONS are your long-range memory, not just reactions to this chapter -
they're the only thing carried forward in full no matter how many chapters pass (your older
chapter-by-chapter notes get condensed to titles only after a while). So: don't drop something
from these two fields just because it's been several chapters since it came up - keep tracking
anything genuinely still unresolved, however old, until it actually pays off or is confirmed
abandoned. If this new chapter resolves or clearly references something you were tracking,
say so explicitly in REACTION as a callback, not as if it's new.

Nothing else - no preamble, no markdown headers, just those ten lines.
"""


def extract_chapter_label(chapter_text: str, fallback: str) -> str:
    """Deterministically derive a canonical chapter label from the chapter's own leading
    heading line (e.g. '## IX - Torrid' -> 'IX - Torrid', '# Chapter 2' -> 'Chapter 2').
    Pure string parsing, no LLM call - falls back to the raw chapter_ref if the chapter text
    doesn't start with a markdown heading for some reason."""
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
        cmd = ["python", str(NW_TOOL_PATH), "get", str(src), chapter_ref]
    elif src.is_file():
        cmd = ["python", str(NW_TOOL_PATH), "flat-get", str(src), chapter_ref]
    else:
        sys.exit(f"chapter_source not found: {chapter_source}")
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        sys.exit(f"nw_tool.py failed:\n{result.stderr}")
    return result.stdout.strip()


def trim_history(living_reference_text: str, history_n: int) -> str:
    """Keep the Running Notes block in full always (that's where long-range threads should
    live - see the persona instructions), the most recent N chapter-log entries in full detail,
    and a compact title+rating digest of everything older than that - so a chapter that pays
    off something planted many chapters back is still recognizable as a callback, not a
    surprise, even though the full text of that old chapter isn't being resent every time."""
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
    ap.add_argument("persona_slug")
    ap.add_argument("review_root")
    ap.add_argument("chapter_source")
    ap.add_argument("chapter_ref")
    ap.add_argument("--history", type=int, default=8)
    ap.add_argument("--out")
    ap.add_argument("--chapter-file")
    args = ap.parse_args()

    card_path = PERSONAS_DIR / f"{args.persona_slug}.md"
    if not card_path.exists():
        sys.exit(f"Unknown persona: {args.persona_slug} (no {card_path})")
    card_text = card_path.read_text(encoding="utf-8-sig").strip()

    lr_path = Path(args.review_root) / "_beta_reviews" / args.persona_slug / "living_reference.md"
    if not lr_path.exists():
        sys.exit(
            f"No living_reference.md for {args.persona_slug} at {lr_path} - "
            f"run select_panel.py first."
        )
    history_text = trim_history(lr_path.read_text(encoding="utf-8-sig"), args.history)

    if args.chapter_file:
        chapter_text = Path(args.chapter_file).read_text(encoding="utf-8-sig").strip()
    else:
        chapter_text = fetch_chapter(args.chapter_source, args.chapter_ref)
    chapter_label = extract_chapter_label(chapter_text, fallback=args.chapter_ref)

    bundle = (
        "=== PERSONA CARD ===\n" + card_text + "\n\n"
        "=== YOUR READING HISTORY SO FAR ===\n" + history_text.strip() + "\n\n"
        "=== NEW CHAPTER TO REACT TO ===\n" + chapter_text + "\n\n"
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
