# claude-fluent

Personal app to improve my English. **Single user: me.** Not a product, will not
be scaled, will never have other users.

Anki is the spaced repetition engine and the source of truth. This app does not
schedule or run reviews: it **syncs, analyses and generates cards.**

## Run it

```bash
source .venv/bin/activate
uvicorn app:app --reload      # http://localhost:8000
```

Anki must be running with the AnkiConnect add-on (code `2055492159`), or every
endpoint that touches the collection fails. `GET /api/health` says so explicitly,
and it is the first thing to check when anything looks wrong: the failures in
this system are silent — Anki closed, `claude` without a session — and the app
looks normal while it lies to you.

## Modules

| File | Role |
|---|---|
| `app.py` | FastAPI: routes, and serves the front end. The static mount goes **last** or it swallows `/api`. |
| `anki.py` | AnkiConnect client. `call(action, **params)` and the helpers over it. Owns the write guard. |
| `analysis.py` | **Pure functions** over a list of reviews. No I/O, no clock — every function takes its data and its reference date, so it is testable without Anki. |
| `snapshot.py` | **The only write path into Anki.** Records the previous state, then holds the lock while the write happens. |
| `repair.py` | Prompt and schema for rewriting a stuck card. Proposes only, never writes. |
| `llm.py` | `claude -p` wrapper. Checks `is_error` on stdout, never uses `--bare`. |
| `seed_cards.py` | Development fixture, not part of the app. Creates deliberately defective cards in `claude-fluent-test`. |
| `spike_anki.py`, `spike_claude.py` | Phase 0 connection probes. Kept as the record that the architecture works. |
| `static/` | Plain HTML/CSS/JS. No framework, no build step. |

**`app.py` fetches, `analysis.py` computes.** Never put an AnkiConnect call
inside `analysis.py` — that separation is the only reason the analysis can be
tested without a running Anki, and it is what let the streak logic get six
cases checked in seconds.

## Endpoints

| | |
|---|---|
| `GET /api/health` | Is Anki answering, is `claude` on PATH |
| `GET /api/today` | Everything the Today screen needs, in one object |
| `POST /api/study` | Hands the session to Anki's reviewer on the deck with work. 409 when nothing is due. |
| `POST /api/add-cards` | Opens Anki's Add dialog |
| `POST /api/repair/{note_id}` | Asks the model for a better card. **Writes nothing.** |
| `POST /api/apply/{note_id}` | Snapshots, then writes the approved fields |

Reviewing and card creation both happen **in Anki**; the app only decides where
to start, via `guiDeckReview` / `guiAddCards`. Whether the Anki window comes to
the front is the window manager's call — Wayland compositors commonly block
focus stealing, so Anki changes screen but stays behind.

## Writing to Anki

`anki.call()` **refuses the 22 actions in `anki.WRITE_ACTIONS`** and raises
`WriteWithoutSnapshot` unless `snapshot.py` is holding the lock. The rule is
structural, not a convention: forgetting to record the previous state raises
instead of quietly succeeding, and the lock closes again on the way out.

```python
with snapshot.guarded(note_id) as path:      # captures first; if capture
    anki.call("updateNoteFields", note=...)  # fails, the block never runs
```

Use `snapshot.update_note_fields()` rather than opening the block by hand.
`snapshot.restore()` puts a note back and takes its own snapshot first — undoing
an undo has to be possible too.

**Two kinds of write, two kinds of record.** Overwriting or deleting can lose
data, so it saves the previous state first. Creating cannot lose anything —
there is no previous state — so it leaves a *creation record* instead: the ids
it made, so `snapshot.undo_creation()` removes exactly those and nothing else,
snapshotting each one on the way out in case it was edited since. Both live in
`data/snapshots/`: `created-*.json` are creation records, `<note_id>-*.json` are
snapshots. Additive actions still go through `snapshot.py`; nothing reaches Anki
any other way.

This has already paid for itself once: eight seeded notes were deleted by an
accidental `seed_cards.py --undo`, and every field was recoverable from disk.
That flag now refuses to fire without `--yes`.

**Fields are HTML.** Convert with `anki.to_plain_text()` on the way out and
`anki.to_field_html()` on the way in. `strip_html()` collapses newlines and is
for single-line list rows only — using it on a value you are about to write
flattens the card. Snapshots store the **raw** value so a restore is exact.

## The repair flow

`struggling` in `/api/today` ranks cards by failures, time lost and interval
drops. A card must clear both gates to appear: `MIN_ATTEMPTS` reviews and
`MIN_FAILURES` failures. Without the failure gate it is really a slowest-cards
list, and a card you have never got wrong is not one you are stuck on.

`repair.propose()` sends the card plus its review history and asks for a rewrite.
Field names come back from a language model, so they are untrusted: anything the
note does not have is dropped and reported in `rejected_fields`, and `/api/apply`
validates them again before writing. Expect 8–15 s per call.

## Front end

No framework, no build step, no npm. Save a file, reload the browser.

- Served from the **root**, not `/static`: the mount points at `static/`, so the
  page links `/styles.css`, not `/static/styles.css`.
- A middleware sets `Cache-Control: no-cache` outside `/api/`. StaticFiles sends
  ETag and Last-Modified but no Cache-Control, so browsers fall back to
  heuristic caching and keep serving a stylesheet edited minutes ago. **That
  looks exactly like the change not having worked** — it cost a whole round of
  "you didn't do it" / "yes I did" before the header was added.
- `app.js` is loaded as `type="module"`, which is what lets it import anime.js.
- anime.js v4.5.0 is **vendored** at `static/anime.esm.js`, not a CDN link. The
  app is local-only, and a module whose import fails takes the whole file down
  with it — the screen would go blank, not merely unanimated.
- Motion is a bonus, never a dependency: dynamic `import()` in a try/catch, the
  initial hidden state set by the animation rather than by CSS, and
  `prefers-reduced-motion` skips the download entirely.

## Closed decisions — do not reopen

- **Do not build a custom SRS engine.** Anki already has one, battle-tested,
  with sync and mobile for free.
- **No study planner or timeline.** In spaced repetition the algorithm decides
  when you review; planning dates means planning something it will contradict.
- **No cumulative metrics** (total time, global accuracy). Only what depends on
  showing up today: streak, cards due, 30-day calendar.
- **The streak has one grace day per month.** Breaking it is the moment of
  highest abandonment risk.
- **Never write to Anki without recording the previous state.** Editing notes
  has no undo.
- **The model proposes, I approve.** Never write to the collection automatically.

## Working rules

- All code in English: filenames, identifiers and comments. Docs in Spanish.
- No tests for now. I am the only user and I try it every day.
- No new dependencies without asking me first. Current set: `fastapi uvicorn httpx`.
- Never use `claude --bare`: it ignores the subscription login and requires an
  API key. It is announced as the future default of `-p` — if everything breaks
  after a Claude Code update, this is why.
- Failures in `claude -p` arrive on **stdout** as `is_error`, not through the
  exit code. Check the field, not the return code.
- Do not hand me a destructive command as a ready-to-run snippet in the same
  message as the one I actually asked for. That is how the seeded cards died.
- On macOS, App Nap must be disabled or AnkiConnect stops responding. (Not
  applicable on this Linux machine.)
- Do not edit notes with the Anki browser open on those same notes.

## Anki — facts that cost time to learn

A revlog row is
`[timestamp, cardId, usn, button, newInterval, prevInterval, factor, durationMs, type]`.

- **Interval signs carry the unit.** Positive values are days, negative values
  are seconds. `-330` means 330 seconds, not minus 330 days. Compare intervals
  only after normalising — `anki.interval_to_seconds()`.
- **`cardReviews` is not chronological.** It groups rows by card, ordered within
  each card. Sort by `timestamp` before reading it as a timeline, or the
  calendar puts reviews on the wrong day. `anki.reviews_since()` already sorts.
- **`getDeckStats` omits empty decks.** Merge over `deckNamesAndIds` or decks
  with nothing in them silently vanish from the response.
- **`decks()[0]` is not my deck.** `deckNames` comes back alphabetical, so
  `Default` wins and it is always empty. Never index into the deck list.
- **`factor` is 0 while a card is in learning.** It is only set once the card
  graduates, so it is useless as a struggling signal on new cards.
- **`getLatestReviewID` returns 0 for a deck never reviewed**, which makes a
  `startID` computed by subtraction go negative. AnkiConnect accepts it and
  returns everything.
- **`notesInfo` returns an empty object, not an error, for a note that no longer
  exists.** Truthiness is the check; a list of the right length proves nothing.
- **`getReviewsOfCards` needs integer ids** and returns named dicts
  (`ease`, `ivl`, `lastIvl`, `time`), which is far easier to read than the raw
  revlog rows. Strings silently return nothing.
- **Anki's GUI does not refresh when AnkiConnect writes.** Deck counts in an
  open deck browser go stale; press `d` to go back to the deck list.
- Buttons: `1 Again · 2 Hard · 3 Good · 4 Easy`.
  Types: `0 learning · 1 review · 2 relearn · 3 filtered · 4 manual`.

## Verifying a change

This machine has **no Node and no automatable browser**, so JS cannot be
executed or rendered here. What is worth checking before claiming something
works:

- Python — `python -c "import ast; ast.parse(open('x.py').read())"`, then import
  every module.
- Pure functions — call `analysis.streak` / `calendar` / `struggling` with
  synthetic `Review` rows. This is where real bugs have been caught.
- Front end — cross-check that every `$("id")` in `app.js` exists in
  `index.html`, and that no CSS selector points at a class nothing renders. A
  missing id is the usual cause of a blank page.
- Anki state — **read it back from Anki**, do not trust the response of the call
  that wrote it. `addNotes` returned eight ids for notes that were gone a minute
  later.
- Endpoints — curl them. `/api/health` first.

## Design

Wireframes live in `docs/wireframes.excalidraw`. It holds two generations: the
early Dashboard screens carry cumulative metrics and an account/plan sidebar,
both of which the closed decisions rule out. **The "v2" screens are the target**
— "Hoy" and the session cards with their Listening / Speaking / Reading /
Writing variants.

**`.interface-design/system.md` holds the design decisions — read it before
touching `static/` and hold to its values instead of reinventing them.**
Direction is "la ficha de cartón": cool card stock, graphite, borders-only
depth, 4px base. One accent, `--present` `#2a5580`, the blue-black of writing
ink — on the primary button and today's calendar mark, nowhere else. **Red is
only ever a failure of the system**, never an action and never a state of the
person: a day not studied is unmarked paper, not a hole, and a stuck card gets
no colour at all.

The `interface-design` skill is installed in `.claude/skills/`, with
`/design-review` and `/design-deslop` as commands.

## Known issues

- `spike_anki.py` still reads `decks[0]`, which is `Default` and always empty.
  The app itself no longer makes that mistake; the spike was left as written.
- `data/state.json` does not exist yet, so `/api/health` reports
  `last_sync: null` unconditionally.
- The deck and settings screens in the wireframes are not built.

## Current status

Today screen and card repair work end to end against the real collection.
Card generation (phase 3) is the next thing not built.

(Update this section after each phase.)
