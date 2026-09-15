# beta-reader-panel

A [Claude Code](https://claude.com/claude-code) Skill that simulates a panel of 2-3 distinct
beta readers — randomly picked from a roster of teen, young-adult, adult, middle-aged, and
older personas — reading a manuscript chapter by chapter, each with their own **isolated**
memory so none of them anchor on each other's opinions.

## Why this exists

Real authors often want multiple beta readers precisely because one reader's reaction can
quietly bias how you read the next one's. Simulating that only works if the simulation respects
the same isolation: each persona here keeps its own private `living_reference.md`, and the
skill's hard rule is that no persona ever sees another's file or reaction before writing its
own.

This is reader *reaction*, not editing — no line edits, no prose fixes. For that, see the
companion skill, [manuscript-editor](https://github.com/SwaroopShenoy/manuscript-editor-skill).

## What's in this repo

- **`SKILL.md`** — the workflow: panel selection, the per-chapter isolation loop, output style.
- **`toolkit/select_panel.py`** — randomly picks 2 or 3 personas for a manuscript (idempotent —
  won't re-roll an existing panel) and scaffolds each one's living-reference file.
- **`toolkit/personas/*.md`** — six reader persona cards: `teen_male`, `teen_female`, `ya`,
  `adult_late20s30s`, `middle_aged`, `older` — each with a distinct voice and taste profile.
- **`toolkit/living_reference_template.md`** — the per-persona chapter-log template.

Reading manuscripts (novelWriter projects or flat `.md` files) is delegated to the
`manuscript-editor` skill's `nw_tool.py` — this skill only ever reads, never writes back to a
manuscript.

## Install

Requires [Python 3](https://www.python.org/) and the
[manuscript-editor](https://github.com/SwaroopShenoy/manuscript-editor-skill) skill installed
alongside it (for manuscript reading).

```
git clone https://github.com/SwaroopShenoy/beta-reader-panel-skill "%USERPROFILE%\.claude\skills\beta-reader-panel"
```

Claude Code auto-discovers skills under `~/.claude/skills/` — no further setup needed.

## Usage

> "Get the beta panel's reactions to chapter 3 of \<project\>"

First run picks 2-3 random readers and locks them in for that manuscript. Each subsequent
chapter, every panel member reacts independently, in character, based only on what they've
"read" so far — then their reaction is logged to their own private file under
`<manuscript>/_beta_reviews/<persona-slug>/living_reference.md`.
