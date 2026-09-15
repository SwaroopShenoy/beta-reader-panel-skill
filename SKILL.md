---
name: beta-reader-panel
description: Simulates a panel of 2-3 distinct beta readers (randomly picked from teen, young-adult, adult, middle-aged, and older personas) reading the user's manuscripts chapter by chapter, each with their own isolated memory so none of them bias each other. Use when the user wants beta-reader reactions, reader feedback, or "what would readers think" on a chapter/manuscript — as opposed to the manuscript-editor skill, which does line-editing/copyediting, not reader reactions.
---

# Beta reader panel

Simulates several different readers independently reading the same manuscript, chapter by
chapter, the way a real author would run parallel beta readers to avoid one opinion anchoring
the others. This is **reader reaction, not editing** — no line edits, no prose fixes, no craft
prescriptions. If the user wants that, point them to the `manuscript-editor` skill instead.

Toolkit lives in this skill's own folder: `toolkit/select_panel.py`, `toolkit/personas/*.md`,
`toolkit/living_reference_template.md`. Reads manuscripts using the `manuscript-editor` skill's
`nw_tool.py` (`$env:USERPROFILE\.claude\skills\manuscript-editor\toolkit\nw_tool.py`) — this
skill never writes back to the manuscript itself, only reads chapters.

## The hard rule: isolation

Each panel member has their own private `living_reference.md` under
`<manuscript>/_beta_reviews/<persona-slug>/`. This is the whole point of the skill:

1. **Never let one persona read another's `living_reference.md` or reactions.** When writing
   persona B's reaction, only ever look at persona B's own file plus the persona card and the
   chapter itself — never at what persona A just said, even earlier in the same turn.
2. **Draft each persona's reaction as a fully separate pass**, not as variations on one take.
   Reread the persona's card (`toolkit/personas/<slug>.md`) before writing their reaction, so
   the voice stays distinct and doesn't drift toward a generic "reader" tone.
3. **Never reveal future chapters to a persona.** Each reader only knows what they've "read so
   far" — their own chapter log is the ceiling of their knowledge.

## Setup (once per manuscript)

Run the panel selector — safe to re-run, it won't re-roll an existing panel:
```
python $env:USERPROFILE\.claude\skills\beta-reader-panel\toolkit\select_panel.py <manuscript_dir>
```
This picks 2 or 3 personas at random from the roster (`toolkit/personas/`: `teen_male`,
`teen_female`, `ya`, `adult_late20s30s`, `middle_aged`, `older`), records the pick in
`_beta_reviews/panel.md`, and creates each selected persona's `living_reference.md` from the
template. The panel is locked in for that manuscript from then on — don't re-roll mid-read, or
earlier reactions become impossible to compare against later ones. If the user explicitly asks
for specific personas instead of random ones, pass those directly rather than running the
random selector.

## Per-chapter loop

1. **Pull the chapter fresh** using `nw_tool.py get`/`flat-get` (read-only — same detection
   logic as `manuscript-editor`: novelWriter project vs flat `.md`).
2. **For each panel persona, in isolation:**
   - Read that persona's card (`toolkit/personas/<slug>.md`) and their own
     `_beta_reviews/<slug>/living_reference.md` (their prior chapters only).
   - Write their reaction to the new chapter, in character — gut reaction, what landed, what
     didn't, confusion, predictions. This is a reader's honest response, not a critique memo.
   - Append a concise entry to their `living_reference.md` under `## Chapter log`:
     ```
     ### Ch N — <title>
     Reaction: ...(2-4 sentences, in voice)
     Liked: ...
     Confused/disliked: ...
     Prediction: ...
     Rating: X/10
     ```
     Update the `## Running notes` block at the top (vibe, favorite/least-favorite character,
     active theories, open questions) by overwriting it — that section reflects current state,
     it doesn't accumulate. Keep every entry short; this is tracking, not an essay.
3. **Present all personas' reactions together to the user**, clearly labeled by name, after all
   of them are done — never show one persona's take before writing the next one's.

## Output style

Keep it to the point, matching how the user asked for this: short in-character reactions and a
rating, not long-form analysis. The `living_reference.md` files are the persistent record —
there's no need for a separate compiled review file per chapter unless the user asks for one.
