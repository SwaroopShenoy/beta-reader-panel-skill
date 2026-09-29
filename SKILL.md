---
name: beta-reader-panel
description: Reviews the user's manuscripts chapter by chapter, in one of two modes. Lightweight/analyst mode (the default): a single continuously-updated story analysis — story type, detailed chapter summary, writing quality + rating, characters/relationships — no personas, no panel setup. Panel mode: 2-3 distinct in-character beta readers (randomly picked from an 11-persona roster spanning teens, young-adult, adult, middle-aged, older, genre-superfan, casual, and craft-critic readers), each reviewed by its own subagent for genuine context isolation so none of them bias each other. Use when the user wants a chapter summary/quality read, beta-reader reactions, reader feedback, or "what would readers think" on a chapter/manuscript — as opposed to the manuscript-editor skill, which does line-editing/copyediting, not reading/reviewing.
---

# Beta reader panel

Reviews a manuscript chapter by chapter. Two modes, same toolkit family:

- **Analyst mode (lightweight, default)** — one continuously-updated read: what kind of story
  this is, a detailed summary of the chapter, an honest read on writing quality + a rating, and
  who's involved / how relationships stand. No in-character opinions, no panel setup, and
  **written by you directly, not a subagent** — there's no second opinion to isolate from bias
  here, so the subagent isolation that panel mode needs for real doesn't apply. Reach for this
  whenever the user just wants a chapter-by-chapter record and quality read, not simulated
  reader reactions — it's cheaper and faster to start (no panel roll, no subagent spawn tax) and
  is the right default unless the user specifically wants reader reactions.
- **Panel mode** — several different readers independently reacting to the same manuscript, the
  way a real author would run parallel beta readers to avoid one opinion anchoring the others.
  Use when the user explicitly wants reader reactions / "what would readers think" / multiple
  perspectives.

Both modes are **reading/analysis, not editing** — no line edits, no prose fixes, no craft
prescriptions. If the user wants that, point them to the `manuscript-editor` skill instead.

|                    | **Analyst mode** (default)                  | **Panel mode**                              |
|--------------------|----------------------------------------------|----------------------------------------------|
| Voices             | One (you, the analyst)                        | 2-3 personas, randomly picked per manuscript  |
| Runs as            | Main conversation thread, no subagent          | One `Agent` subagent per persona (real isolation) |
| Reference file(s)  | `_story_analysis/living_reference.md` (one)    | `_beta_reviews/<slug>/living_reference.md` (one per persona) |
| History sent per chapter | Full book by default (`--history 30`)   | Last 8 chapters, older ones digested (`--history 8`) |
| Output             | One structured analysis, OPENER→SIDEBAR (see below) | One short in-character block per persona (see below) |
| Reach for it when  | "review my chapter", chapter summaries/craft notes | "what would readers think", reader reactions |

These two never share state or code paths — the only thing genuinely shared is `nw_tool.py` for
reading chapters and the general "mechanical work in Python, one LLM step, paste bundles inline"
approach. Don't let analyst-mode logic leak into panel mode's subagent-spawning steps or vice
versa; the rest of this document keeps them under clearly separate headers for that reason.

Toolkit lives in this skill's own folder. Analyst mode: `toolkit/init_analyst.py`,
`toolkit/analyst_reference_template.md`, `toolkit/build_analyst_prompt.py`,
`toolkit/record_analysis.py`. Panel mode: `toolkit/select_panel.py`, `toolkit/personas/*.md`,
`toolkit/living_reference_template.md`, `toolkit/build_persona_prompt.py`,
`toolkit/record_reaction.py`. Reads manuscripts using the `manuscript-editor` skill's
`nw_tool.py` (`$env:USERPROFILE\.claude\skills\manuscript-editor\toolkit\nw_tool.py`) — this
skill never writes back to the manuscript itself, only reads chapters.

**Token/tool-agnosticism note (panel mode):** `build_persona_prompt.py` and `record_reaction.py`
do all the mechanical work (assembling context, parsing output, updating files) as plain
deterministic Python — zero tokens, and they don't care what generates the reaction in between.
The remaining LLM step only *needs* to be a single text-in/text-out completion — no tool access
required by the task itself — which is what makes it swappable to a raw API call or a different
model/harness in principle. In practice, if that step runs via this harness's `Agent` tool,
be aware every available subagent type carries its own fixed system-prompt/tool-belt overhead
regardless of task — there's no genuinely toolless subagent on offer here (measured: ~45k tokens
per fresh spawn, regardless of task size). Given that constraint, the actual levers are: never
let the subagent go read a file itself (paste the bundle inline instead — see the spawning steps
below), and reuse a persona's subagent across a batch of chapters rather than paying that fixed
tax on every single chapter (see "Long-lived vs ad hoc"). Don't hand a persona's turn to a
heavyweight general-purpose agent that re-reads files and figures out formatting itself — that's
the fixed cost stacked with avoidable extra tool round-trips on top. This whole fixed-overhead
problem is *why panel mode needs it anyway* — real isolation is worth ~45k tokens per persona
per fresh chapter. **Analyst mode has no such need** (see below) and skips the subagent
entirely, which is where most of this problem simply doesn't apply.

## Cold start: ready to review by the user's 2nd message

When this skill is invoked without a manuscript already established in the conversation, the
whole setup has to fit in one round trip — don't turn this into a multi-question intake form.

1. **Your first reply asks exactly one thing**: which manuscript, and where it lives (a path to
   the novelWriter project folder, or to the flat `.md` file). If you already know this from
   context — the user named a project you have memory of, or one was just discussed — skip the
   question entirely and treat it as already answered; don't ask something you can already infer.
   If you're aware of a known manuscripts folder for this user, glance at it and offer a short
   list of likely candidates rather than a blank "where is it?" — faster to answer than free text.
   Don't ask which mode in this same message unless the user's phrasing is genuinely ambiguous
   (see "Picking a mode" below) — defaulting silently to analyst mode is fine and faster.
2. **The moment you have the manuscript** (the user's next message, at the latest), do
   everything below in that same turn, with no further questions unless something is genuinely
   ambiguous (the name matches more than one manuscript, or the path doesn't exist):
   - Resolve the manuscript type the same way `nw_tool.py` does (directory with `nwProject.nwx`
     vs a `.md` file).
   - **Analyst mode (default):** run `init_analyst.py` against it — creates
     `_story_analysis/living_reference.md` if it doesn't exist yet, or is a no-op if it does.
   - **Panel mode (only if the user asked for reader reactions/personas):** run `select_panel.py`
     against it — picks a panel if none exists yet for this manuscript, or reports the existing
     one if it's already set up.
   - Pick the starting chapter: use whatever the user named, or default to the manuscript's own
     first chapter (`list`/`flat-list`) and just say plainly that's where you're starting — a
     one-line thing to correct, not a blocking question.
   - Immediately run the full build → generate → record loop for that chapter in whichever mode
     applies, and present the results.

No "should I start?", no "does this panel look right?" checkpoint in between — setup and the
first chapter's review happen in the same turn once the manuscript is known.

### Picking a mode

Default to **analyst mode** — it's what most requests to "review my chapter" or "go through my
manuscript" actually want, it's cheaper (no subagent at all, no panel roll), and it's easy to switch
into panel mode later without losing anything (the two modes keep entirely separate reference
files, `_story_analysis/` vs `_beta_reviews/`, so nothing needs to be redone). Switch to **panel
mode** only when the user's own words ask for reader reactions, opinions, "what would readers
think", beta readers, or personas specifically — not just "review". If genuinely unsure which
the user wants, ask once, but don't default to asking.

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

## Analyst mode: setup (once per manuscript)

Run the initializer — safe to re-run, it's a no-op if the reference already exists:
```
python $env:USERPROFILE\.claude\skills\beta-reader-panel\toolkit\init_analyst.py <manuscript_dir>
```
This creates `_story_analysis/living_reference.md` from the template. There's no roster, no
random pick, nothing to lock in — just the one file that gets updated every chapter.

## Analyst mode: no subagent — you write the analysis yourself

Panel mode needs subagent isolation because multiple opinions would anchor on each other in a
shared context. Analyst mode has exactly one voice — there's nothing for it to be biased
*against* — so the ~45k-token fixed cost of spawning an `Agent` buys nothing here. **Generate
the analysis yourself, directly in the main conversation, every time.** This is the default; do
not spawn a subagent for analyst mode unless the user explicitly asks to keep chapter text out
of the main conversation for some reason (e.g. an extremely long batch where they'd rather it
happen off to the side) — that's a real but unusual tradeoff, not the normal path.

1. Fetch the chapter (`nw_tool.py get`/`flat-get`) into a scratch file, same as panel mode.
2. Build the bundle:
   ```
   python toolkit\build_analyst_prompt.py <review_root> <chapter_source> <chapter_ref> --chapter-file <scratch>\chapter.txt --out <scratch>\analysis_bundle.txt
   ```
   Always the full bundle — there's no fresh-spawn-vs-continuing distinction to manage once
   there's no subagent; your own conversation already carries everything from earlier chapters
   this session the same way it carries anything else you've read. `--history` defaults to 30
   (effectively the whole book — see below on why), read the chapter's `.label` sidecar back and
   use it as `<chapter_label>` in step 4, same as panel mode.
3. **Read the bundle yourself and write the analysis in your own reply**, following the same
   OPENER/STORY_TYPE/SUMMARY/QUALITY/RATING/CHARACTERS/SIDEBAR fields and the same voice
   (below) the bundle's instructions describe — you're doing the job the subagent used to do,
   not delegating it. Save your own raw `KEY: value` output to a scratch file so step 4 can parse
   it the same way it always has.
4. Record the result (mechanical, no tokens):
   ```
   python toolkit\record_analysis.py <review_root> "<label from step 2's .label file>" <scratch>\analysis_output.txt
   ```
   `record_analysis.py` also rebuilds "Running notes" from scratch each time by scanning every
   `#### Characters & relationships` and `#### Rating` block already in the chapter log plus the
   new one — mechanically, no extra LLM call. That's what keeps the character roster genuinely
   *cumulative* (a character absent from this chapter's `CHARACTERS` field isn't dropped from the
   running roster just because they didn't show up this time) and keeps "Running notes" itself
   short (a rating trend line instead of a resent copy of the full `QUALITY` paragraph) even as
   individual chapter entries get long — since Running notes goes into every future bundle in
   full regardless of `--history`, keeping it compact matters more than any other single field
   for this mode's long-run token cost.
5. Present the result per the output format below.

### Why `--history` defaults to 30 (essentially the whole book) here

Panel mode's `--history` default of 8 exists to keep a subagent's bundle small, because a fresh
subagent spawn already costs ~45k tokens and every extra chapter of full history stacks on top
of that. Analyst mode has no subagent tax to protect against, and the user's manuscripts run
~30ish chapters max per book — so digesting anything down to a title+rating line risks losing a
payoff or callback to an early chapter's specific beats for essentially no savings that matter
at this scale. Default to `--history 30` (i.e. full detail for the whole book) and only pass a
smaller number by hand for an unusually long manuscript where the full chapter log would
genuinely bloat the prompt.

## Analyst mode: voice

The analyst has a personality: witty, genuinely engaged with the material, comfortable making
comps and naming tropes, and **not sycophantic** — no "this is amazing!", no cheerleading, no
softening a real observation. `build_analyst_prompt.py`'s `INSTRUCTIONS` spell this voice out in
full even though you're the one writing it now, not a subagent — read them as your actual brief
for the reply, not background flavor text, and don't flatten it back into a dry report. This
mode's whole point is that the reply reads like commentary from someone actually paying
attention, not a form getting filled in.

## Analyst mode: output style

Six parts (of the seven fields — SIDEBAR is folded in only when present), in this order,
straight from what you wrote in step 3 — this isn't a persona block, it's one voice giving a
real read:

```
<OPENER — the witty hook line(s), no header>

### What Kinda Story Is This?
<STORY_TYPE>

### Summary
<SUMMARY — bulleted by narrative front if the chapter runs more than one>

### Writing Quality
<QUALITY>

Rating: <RATING>

### Characters & Relationships
<CHARACTERS>

### Sidebar
<SIDEBAR — only if present>
```

`SIDEBAR` is the analyst's own off-structure aside — a theory, something that bugged it, a
question for the author, a detail it loved — anything that didn't fit neatly into the boxes
above. It's genuinely optional: `record_analysis.py` drops the section entirely when there was
nothing to add (or it was left blank), so don't force a "Sidebar" heading onto an empty thought
just to fill out the shape. When it is present, keep it last, after Characters & Relationships,
and don't reformat it into the same structured tone as the rest — it's supposed to read like the
analyst went slightly off-script.

Present your own field bodies close to verbatim from what you wrote in step 3 (light cleanup
only — stray whitespace,
not rewording); they're already written in voice and may already use bullets/bold internally.
Only restate STORY_TYPE in full if it changed or this is the first chapter reviewed — otherwise
a short "(still a corporate-thriller-with-a-body-count, no surprises here)" style aside is more
in-voice than dryly noting "unchanged". `living_reference.md` is the persistent record; no
separate compiled file needed unless asked.

## Panel mode: setup (once per manuscript)

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

## Panel mode: per-chapter loop

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

## Panel mode: output style

Keep it to the point: short in-character reactions and a rating, not long-form analysis — that's
a deliberate difference from analyst mode's depth, not an oversight, since this is a gut
reaction, not a craft read. Structurally it still borrows analyst mode's conventions where they
fit a short block: a `###` header per voice, and rating on its own line rather than buried in the
header. Use this exact shape for presenting a chapter's panel results, one block per persona, in
the same order the panel was selected:

```
### <Name> — <label>
"<REACTION, verbatim>"

**Liked:** <LIKED>
**Didn't land:** <DISLIKED>
**Watching for:** <PREDICTION>

Rating: <RATING>
```

Skip empty/"none" fields rather than printing them (e.g. drop the "Watching for" line entirely
if PREDICTION was "none yet"). After all persona blocks, one short closing line is fine if there's
a genuinely interesting split (e.g. "Elsa and Wilson landed in very different places on the
pacing here") — don't manufacture a synthesis if there isn't one. The `living_reference.md`
files are the persistent record — there's no need for a separate compiled review file per
chapter unless the user asks for one.

What doesn't carry over from analyst mode, on purpose: no OPENER (the quoted REACTION already
is the hook), no SUMMARY (a reader reaction isn't a chapter record — analyst mode's Chapter log
already is that), no SIDEBAR (PREDICTION/"Watching for" already covers a persona's own forward
-looking aside; a second off-structure field would just pad a reply that's supposed to stay
gut-level short).
