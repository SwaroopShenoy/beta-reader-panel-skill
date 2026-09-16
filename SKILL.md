---
name: beta-reader-panel
description: Simulates a panel of 2-3 distinct beta readers (randomly picked from an 11-persona roster spanning teens, young-adult, adult, middle-aged, older, genre-superfan, casual, and craft-critic readers) reading the user's manuscripts chapter by chapter, each reviewed by its own subagent for genuine context isolation so none of them bias each other. Use when the user wants beta-reader reactions, reader feedback, or "what would readers think" on a chapter/manuscript — as opposed to the manuscript-editor skill, which does line-editing/copyediting, not reader reactions.
---

# Beta reader panel

Simulates several different readers independently reading the same manuscript, chapter by
chapter, the way a real author would run parallel beta readers to avoid one opinion anchoring
the others. This is **reader reaction, not editing** — no line edits, no prose fixes, no craft
prescriptions. If the user wants that, point them to the `manuscript-editor` skill instead.

Toolkit lives in this skill's own folder: `toolkit/select_panel.py`, `toolkit/personas/*.md`,
`toolkit/living_reference_template.md`, `toolkit/build_persona_prompt.py`,
`toolkit/record_reaction.py`. Reads manuscripts using the `manuscript-editor` skill's
`nw_tool.py` (`$env:USERPROFILE\.claude\skills\manuscript-editor\toolkit\nw_tool.py`) — this
skill never writes back to the manuscript itself, only reads chapters.

**Token/tool-agnosticism note:** `build_persona_prompt.py` and `record_reaction.py` do all the
mechanical work (assembling context, parsing output, updating files) as plain deterministic
Python — zero tokens, and they don't care what generates the reaction in between. The remaining
LLM step only *needs* to be a single text-in/text-out completion — no tool access required by
the task itself — which is what makes it swappable to a raw API call or a different
model/harness in principle. In practice, if that step runs via this harness's `Agent` tool,
be aware every available subagent type carries its own fixed system-prompt/tool-belt overhead
regardless of task — there's no genuinely toolless subagent on offer here. Given that
constraint, the actual levers are: never let the subagent go read a file itself (paste the
bundle inline instead — see the spawning steps below), and reuse a persona's subagent across a
batch of chapters rather than paying that fixed tax on every single chapter (see "Long-lived vs
ad hoc"). Don't hand a persona's turn to a heavyweight general-purpose agent that re-reads files
and figures out formatting itself — that's the fixed cost stacked with avoidable extra tool
round-trips on top.

## Cold start: ready to review by the user's 2nd message

When this skill is invoked without a manuscript already established in the conversation, the
whole setup has to fit in one round trip — don't turn this into a multi-question intake form.

1. **Your first reply asks exactly one thing**: which manuscript, and where it lives (a path to
   the novelWriter project folder, or to the flat `.md` file). If you already know this from
   context — the user named a project you have memory of, or one was just discussed — skip the
   question entirely and treat it as already answered; don't ask something you can already infer.
   If you're aware of a known manuscripts folder for this user, glance at it and offer a short
   list of likely candidates rather than a blank "where is it?" — faster to answer than free text.
2. **The moment you have the manuscript** (the user's next message, at the latest), do
   everything below in that same turn, with no further questions unless something is genuinely
   ambiguous (the name matches more than one manuscript, or the path doesn't exist):
   - Resolve the manuscript type the same way `nw_tool.py` does (directory with `nwProject.nwx`
     vs a `.md` file).
   - Run `select_panel.py` against it — picks a panel if none exists yet for this manuscript,
     or reports the existing one if it's already set up.
   - Pick the starting chapter: use whatever the user named, or default to the manuscript's own
     first chapter (`list`/`flat-list`) and just say plainly that's where you're starting — a
     one-line thing to correct, not a blocking question.
   - Immediately run the full build → generate → record loop (below) for that chapter across
     the selected panel, and present the results.

No "should I start?", no "does this panel look right?" checkpoint in between — panel selection
and the first chapter's reviews happen in the same turn once the manuscript is known.

## The hard rule: real isolation, not just discipline

Each panel member has their own private `living_reference.md` under
`<manuscript>/_beta_reviews/<persona-slug>/`. Writing all personas' reactions yourself in one
continuing context is **not sufficient isolation** — even carefully avoiding "looking back" at
persona A's reaction while writing persona B's, both were generated in the same context window,
so persona A's just-written tokens are still sitting in-context influencing persona B's
generation. That's real anchoring, not paranoia.

So: **every persona's reaction is generated by its own subagent (the Agent tool), never by you
directly.** Each subagent gets a fully self-contained prompt and starts with zero knowledge of
the other personas or their reactions — that's what actually gives you separate context
windows instead of one context pretending to be several people.

1. **Never let one persona's subagent see another's `living_reference.md`, reaction, or
   existence.** `build_persona_prompt.py` already guarantees this — its output bundle only ever
   contains one persona's own card and own history — so never paste a second persona's
   information into a bundle by hand, and never mention the panel or other readers when
   spawning the generation subagent.
2. **Launch all active personas' generation subagents in parallel** (one `Agent` call per
   persona, same message) rather than sequentially.
3. **Never reveal future chapters to a persona.** Each bundle only covers the one chapter being
   reviewed plus that persona's own prior chapter log — never anything later in the book.

### Spawning a persona's review subagent

0. **Fetch the chapter once, not per persona.** Every persona reacting to the same chapter needs
   identical source text — that's shared material, not opinion, so there's no isolation reason
   to re-fetch it N times. Run `nw_tool.py get`/`flat-get` a single time into a shared scratch
   file (e.g. `<scratch>\chapter.txt`) before touching any persona. Skipping this and letting
   each persona's build step re-fetch independently is the main reason this used to "take a
   while" — every `nw_tool.py` invocation is a fresh Python process paying full interpreter
   startup and import cost, and N personas meant paying that N times for the same output.

1. **Build each persona's bundle** (mechanical, no tokens, and now fast — no subprocess left in
   this step):
   ```
   python toolkit\build_persona_prompt.py <persona_slug> <review_root> <chapter_source> <chapter_ref> --chapter-file <scratch>\chapter.txt --out <scratch>\<slug>_bundle.txt
   ```
   `review_root` is the folder holding `_beta_reviews/` (the novelWriter project dir, or the
   folder containing a flat manuscript). `--chapter-file` points at the shared file from step 0
   — pass it every time; without it, the script falls back to fetching the chapter itself, which
   is correct but slower. Use `--history N` to cap how many prior chapters get included if a
   persona's log has grown long (default 8).

   This also writes `<scratch>\<slug>_bundle.txt.label` — the chapter's own canonical label,
   deterministically read off its own heading line (zero LLM involvement). **Always use this
   file's contents as the `<chapter_label>` in step 3**, rather than typing a label by hand —
   that's what keeps the same chapter logged under the exact same label across every persona and
   every session, with no drift.

2. **Get the reaction generated** — this is the one and only LLM step. Two things matter here,
   both because the `Agent` tool has no genuinely tool-less mode — every subagent type available
   (`general-purpose` included) carries its own fixed system prompt and tool-schema overhead no
   matter what the task needs, so the only levers actually available are avoiding *extra* tool
   calls and not paying that fixed cost more often than necessary:

   - **Read the bundle file yourself and paste its full text directly into the `Agent` prompt.**
     Never tell the subagent "go read `<scratch>\<slug>_bundle.txt>`" — that turns one completion
     into an agentic loop (Read tool call → tool result → reasoning → answer), which costs more
     and is slower. The prompt the subagent receives should already *contain* everything it
     needs. The bundle itself already tells the model not to use tools (baked into
     `INSTRUCTIONS`/`CONTINUING_REMINDER`, not something you need to add by hand) — but it's
     harmless to also say so yourself when spawning.
   - Pick the model deliberately per persona rather than defaulting to the heaviest one — each
     persona card has a `preferred_model` field (`haiku` for the teens/casual reader, `sonnet`
     for most, `opus` for `craft_critic`/Elsa, since her whole point is noticing things the
     others don't). `build_persona_prompt.py` prints the persona's `preferred_model` after
     building a fresh (non-`--continuing`) bundle — use it for that spawn's `model` param. It's
     only relevant at spawn time; a continued conversation keeps whatever model it started with.

   **"In parallel" means literally one message with multiple `Agent` tool-use blocks in it, not
   one `Agent` call per message even sent back-to-back.** Separate messages run sequentially no
   matter how quickly they're issued — the harness only parallelizes tool calls that arrive
   together in the same turn. If reviewing a 3-persona panel, that single message should contain
   three `Agent` invocations, not three consecutive tool calls across three turns.

3. **Record the result** (mechanical, no tokens):
   ```
   python toolkit\record_reaction.py <persona_slug> <review_root> "<label from step 1's .label file>" <scratch>\<slug>_reaction.txt
   ```
   where `<slug>_reaction.txt` holds the raw `KEY: value` text the subagent returned. This
   parses it and updates that persona's `living_reference.md` — both the new chapter-log entry
   and the overwritten Running Notes block — without spending any tokens on formatting. If 4 or
   more of the 10 fields came back empty (a subagent ignoring the format), it flags the entry
   with a visible `⚠` marker in the file itself, not just a console warning — worth a manual
   look if you see one, since it means that persona's reply didn't actually follow instructions.

Run step 2's subagents in the background (default) when reviewing many personas/chapters at
once so the user can keep working; run in the foreground only if the next step genuinely
depends on the result immediately (e.g. this is the only thing happening right now and the
results are needed to answer the user).

### Long-lived vs ad hoc

**Reusing a persona's subagent across chapters in the same session is the recommended default
whenever reviewing more than one chapter in a sitting** — not just an optional nicety. Two real
savings compound: the fixed per-spawn system-prompt/tool-belt tax is paid once per persona for
the whole batch instead of once per persona *per chapter*, and a continuing conversation
benefits from prompt caching on its own accumulating history, which a fresh spawn never gets.
Only fall back to ad hoc (fresh spawn per chapter) when reviewing a single chapter in isolation,
where there's no batch to amortize across.

- **First chapter of a batch (fresh spawn, always):** build the full bundle (step 1, no
  `--continuing`) and spawn the persona's subagent with it inline, per step 2. Keep track of the
  agent id/name it returns — that's the handle for every subsequent chapter in this batch.
- **Every following chapter in the same batch (reuse, don't respawn):** build a lean bundle with
  `--continuing` (skips the persona card and history sections entirely, since the live agent
  already has both in its own memory — resending them is pure duplication) and `SendMessage` it
  to that same agent id, inline in the message, same "no tools" instruction as before.
- **Refresh cadence — don't let one subagent run forever:** a long-lived agent's own context
  still grows every chapter, unboundedly, and there's no way to trim a live conversation the way
  `--history` trims a file. After roughly `--history`'s window worth of chapters (default 8),
  retire that persona's subagent and spawn a fresh one for the next batch — full bundle again,
  no `--continuing` — re-primed from its own just-updated `living_reference.md`, which is
  already the compact record. This resets growth periodically while keeping most of the
  caching/amortization win within each batch.
- **Across separate Claude Code sessions (different days), always ad hoc.** Subagents don't
  persist once a session ends — the next session always starts a fresh batch (first chapter =
  full bundle, fresh spawn) rehydrated from `living_reference.md`. That file staying the source
  of truth, updated every single chapter regardless of which mode produced the reaction, is what
  makes any of this durable across weeks or months of on-and-off reviewing.

## Setup (once per manuscript)

Run the panel selector — safe to re-run, it won't re-roll an existing panel:
```
python $env:USERPROFILE\.claude\skills\beta-reader-panel\toolkit\select_panel.py <manuscript_dir>
```
This picks 2 or 3 personas at random from the 11-persona roster (run `select_panel.py --list`
to print slug/name/label for all of them without touching any manuscript), records the pick in
`_beta_reviews/panel.md`, and creates each selected persona's `living_reference.md` from the
template. The panel is locked in for that manuscript from then on — don't re-roll mid-read, or
earlier reactions become impossible to compare against later ones. If the user explicitly asks
for specific personas instead of random ones, pass `--personas slug1,slug2[,slug3]` (2 or 3
slugs, comma-separated) rather than constructing the panel files by hand.

## Per-chapter loop

1. Fetch the chapter once (step 0 above).
2. Build every active persona's bundle (step 1) — full bundle (no `--continuing`) if this is
   each persona's first chapter in the current batch, lean `--continuing` bundle if their
   subagent is already alive from an earlier chapter this session.
3. Launch/continue every persona's generation subagent **together, in one message** (step 2) —
   `Agent` for a fresh spawn, `SendMessage` to reuse an existing one, whichever applies per
   persona, but all issued in that same single message. This is the step that actually costs
   time and tokens, so it's the one that must be truly parallel.
4. Record each persona's result as its subagent reports back (step 3) — same either way.
5. Present all personas' reactions together, per the format below — don't drip-feed one
   persona's take before the others are in, since isolation is already guaranteed by
   construction at that point.

## Output style

Keep it to the point: short in-character reactions and a rating, not long-form analysis. Use
this exact shape for presenting a chapter's panel results, one block per persona, in the same
order the panel was selected:

```
### <Name> — <label> — <RATING>
"<REACTION, verbatim>"

**Liked:** <LIKED>
**Didn't land:** <DISLIKED>
**Watching for:** <PREDICTION>
```

Skip empty/"none" fields rather than printing them (e.g. drop the "Watching for" line entirely
if PREDICTION was "none yet"). After all persona blocks, one short closing line is fine if there's
a genuinely interesting split (e.g. "Elsa and Wilson landed in very different places on the
pacing here") — don't manufacture a synthesis if there isn't one. The `living_reference.md`
files are the persistent record — there's no need for a separate compiled review file per
chapter unless the user asks for one.
