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
| `syllabus.py` | `data/syllabus/*.json`: el temario congelado de cada nivel. Se genera una vez y es tuyo para editar; nada lo reescribe salvo que pidas regenerar. |
| `state.py` | `data/state.json`: lo único que decide el app y Anki no sabe. Hoy, la meta diaria. |
| `repair.py` | Prompt and schema for rewriting a stuck card. Proposes only, never writes. |
| `generate.py` | Prompts, schemas and the note type for card generation. Proposes only. Everything the model returns is treated as untrusted: the skill and the level must be ones this app knows, and the topic is scrubbed. |
| `llm.py` | `claude -p` wrapper. Checks `is_error` on stdout, never uses `--bare`. |
| `seed_cards.py` | Development fixture, not part of the app. Creates deliberately defective cards in `claude-fluent-test`. |
| `reorganize.py` | One-off, not part of the app. Put the collection under the naming convention: 12 decks folded into 5, 1315 cards moved. Dry run unless `--yes`. |
| `spike_anki.py`, `spike_claude.py` | Phase 0 connection probes. Kept as the record that the architecture works. |
| `static/index.html` | A shell: left sidebar, `#offline`, `<main id="view">`. No screen markup. |
| `static/app.js` | Entry point, three lines. Everything is in `router.js`. |
| `static/router.js` | Hash routing. Mounts a view into `#view` and marks the nav. |
| `static/ui.js` | Shared helpers: `$`, `el`, formatting, rows, `getJSON`, the catalogue cache. |
| `static/repair.js` | The repair panel, shared by Hoy and Atascos. |
| `static/views/*.js` | One module per screen, each exporting `render(root, params)` and carrying its own markup. |

**`app.py` fetches, `analysis.py` computes.** Never put an AnkiConnect call
inside `analysis.py` — that separation is the only reason the analysis can be
tested without a running Anki, and it is what let the streak logic get six
cases checked in seconds.

## Endpoints

| | |
|---|---|
| `GET /api/health` | Is Anki answering, is `claude` on PATH |
| `GET · POST /api/settings` | The daily goal. The only thing this app stores about itself |
| `GET /api/today` | Everything Hoy needs, in one object, and everything the Dashboard needs bar the catalogue. `struggling` is the head of the ranking — what Hoy lists — and `struggling_total` how long it really is, which is the figure the Dashboard strip shows: cut to twelve, 12 stuck cards and 40 would read the same. |
| `GET /api/catalog` | Skill → level → decks, with maturity, the level you stand on, the holes and what is next. Feeds Progreso, the five skill screens, Mazos and the skill meters on Hoy. |
| `GET /api/stuck` | The full stuck ranking with severity and the minutes it costs. Reads only the decks in scope |
| `POST /api/study` | Hands the session to Anki's reviewer. `?deck=` picks one; without it the busiest wins. 409 when nothing is due — including when the named deck has nothing. |
| `POST /api/add-cards` | Opens Anki's Add dialog. The escape hatch at the foot of Agregar, not a screen's main action |
| `POST /api/generate/terms` | What is worth studying next. An optional `{topic}` — whatever is in the box — is opened into its terms; without it, the stuck cards and the empty levels answer. An optional `{skill, level}` narrows either to one hole. **Writes nothing.** |
| `POST /api/generate/cards` | Candidates for **one** term plus the deck they belong in. One term per request: each is its own 8–18 s `claude -p` call. **Writes nothing.** |
| `POST /api/notes` | Creates the approved cards. Ensures the note type, then one `snapshot.add_notes` per deck. Reports what Anki refused and why, per card |
| `POST /api/syllabus` | The points that make up one `{skill, level}`, and which of them the collection covers. The syllabus is **frozen** in `data/syllabus/` on first use — three drafts and a merge, ~100 s; `{regenerate: true}` redoes it. The coverage is derived on every read, ~40 s. **Writes nothing into Anki.** |
| `POST /api/repair/{note_id}` | Asks the model for a better card. **Writes nothing.** |
| `POST /api/apply/{note_id}` | Snapshots, then writes the approved fields |

Reviewing and card creation both happen **in Anki**; the app only decides where
to start, via `guiDeckReview` / `guiAddCards`. Whether the Anki window comes to
the front is the window manager's call — Wayland compositors commonly block
focus stealing, so Anki changes screen but stays behind.

## Writing to Anki

`anki.call()` **refuses the 49 actions in `anki.WRITE_ACTIONS`** and raises
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

**Renaming and merging are the same write, and it needs a move record.**
AnkiConnect has no `renameDeck`: it is `createDeck` + `changeDeck` +
`deleteDecks`, and after the middle one nothing in the collection remembers
where each card lived. `snapshot.move_cards()` writes the card → deck map to
`move-*.json` first, `undo_move()` puts every card back where it came from, and
`delete_empty_deck()` refuses to fire until Anki itself confirms the deck holds
nothing.

**Two kinds of write, two kinds of record.** Overwriting or deleting can lose
data, so it saves the previous state first. Creating cannot lose anything —
there is no previous state — so it leaves a *creation record* instead: the ids
it made, so `snapshot.undo_creation()` removes exactly those and nothing else,
snapshotting each one on the way out in case it was edited since. A note type is a third
case again: it cannot be deleted through AnkiConnect at all, so `model-*.json`
records what was created as evidence rather than as an undo. All three live in
`data/snapshots/`: `created-*.json` are creation records, `model-*.json` note
types, `move-*.json` moves, `<note_id>-*.json` snapshots. Additive actions still go through `snapshot.py`; nothing reaches Anki
any other way.

This has already paid for itself once: eight seeded notes were deleted by an
accidental `seed_cards.py --undo`, and every field was recoverable from disk.
That flag now refuses to fire without `--yes`.

**Fields are HTML.** Convert with `anki.to_plain_text()` on the way out and
`anki.to_field_html()` on the way in. `strip_html()` collapses newlines and is
for single-line list rows only — using it on a value you are about to write
flattens the card. Snapshots store the **raw** value so a restore is exact.

## Generating cards

The flow is **propose, approve, write**, and the three steps are three
different requests. `POST /api/generate/terms` reads the stuck ranking and the
holes and says what is worth making cards for. `POST /api/generate/cards` takes
**one** term and returns up to three candidates — different senses of it, never
rewordings — plus the deck it belongs in, as `Skill::Level::Topic`. Only
`POST /api/notes` writes, and only what was ticked on the screen.

**Agregar is the only door.** Every "Agregar tarjetas" and "+ mazo nuevo" in
the app routes to `#/agregar` — Hoy and the Dashboard when nothing is due,
Progreso and the skill screens from a hole, Mazos from its header. None of them
opens Anki's Add dialog any more: a card this app creates goes through propose
→ approve → write, and a deck is created by writing its first card. Arriving
from a hole carries it in the route, `#/agregar/Grammar/A1`, and the terms are
then proposed **for that level** rather than for the collection at large. The
dialog is still reachable, as a link at the foot of that one screen.

**The box is the question.** Whatever is written in it seeds "Proponer
términos": a subject — "verbos modales" — is opened into the terms it is made
of, `can`, `could`, `must vs have to`. Empty, the failures and the holes answer
instead. Ignoring what was typed and proposing from the failures anyway is the
bug this replaced.

**A subject is not a term.** Sent to `POST /api/generate/cards`, "verbos
modales" comes back as `not_a_term` with a sentence saying which button opens
it. A card whose front reads "verbos modales" teaches nothing, and generating
one silently is worse than refusing.

**One term, one call, in series.** A batch call takes as long as the sum of its
parts with nothing to show meanwhile, and one bad term poisons the whole
answer. In series the screen fills in as each term lands, a failure costs that
term alone, and the machine never has ten `claude` processes at once.

**Deck names from the model are untrusted.** `generate.deck_for()` accepts only
a skill in `analysis.SKILLS` and a level in `analysis.LEVELS`, and scrubs `::`
out of the topic so a topic cannot invent a level of its own. Anything else
comes back as no deck at all and the screen asks you to pick one: a card filed
under a level that does not exist is worse than an unfiled card.

**A grammar card is an exercise, not a word pair.** When the model files a
term under Grammar, the three candidates become three exercises on the same
point — `Traducir:` a Spanish sentence, `Corregir:` an English one carrying
exactly the mistake a Spanish speaker makes, `Completar:` a gap with the cue —
and `Ejemplo` holds the rule in one sentence. It is the shape of the deck that
was already there, `A · traducir · B · corregir · C · completar`.

**Filling a hole and rounding out a level are different questions.** With a
focus on a level that already has decks, `/api/generate/terms` reads up to 60
of its existing cards and passes them in: the instruction is to name what is
missing, never what is there. Without that the model proposes the cards you
have been reviewing for months.

**The deck is per term, and yours to change.** The model suggests one deck
for each term — `put up with` is Grammar B1 and `nevertheless` is Writing B2,
and a single deck for the whole run breaks the convention everything else hangs
off. The picker offers the suggestion, every existing deck, and "Mazo nuevo…",
which builds the name out of skill + level + topic instead of letting you type
a path that will not classify.

**AnkiConnect refuses the batch, not the note.** `addNotes` raises for all of
them if one is empty or duplicated — it does **not** return a null in that
slot, whatever the documentation suggests. One duplicate took thirty approved
cards down with it, and the deck was left created and empty with no creation
record. `snapshot.add_notes` now asks `canAddNotesWithErrorDetail` first, writes
only what Anki will take, reports the rest with its reason, and — if the write
raises anyway — reads the deck back and records whatever landed, because a note
without a record is a note with no way back.

**Cards the person ticked are written with `allowDuplicate: True`.** Three
senses of `nevertheless` share a front and are three real cards. The screen has
already greyed anything whose front is in the collection; Anki's duplicate
warning is its own UI's concern, not a veto over a card you approved.

**Duplicates are shown, never hidden.** `anki.existing_with_front()` searches
the whole collection, not just the note type being written, because Anki's own
duplicate check only looks inside one note type and would miss every Basic card
already there. A match is offered as "ya la tenés", greyed and unticked.

### The note type

Cards are written as **`claude-fluent`** — `Front · Back · Ejemplo` — created on
first use by `snapshot.ensure_model()`. Stock Basic has nowhere to put the
example sentence, and the example is what makes a vocabulary card usable rather
than a word pair you can recite without understanding.

Creating a note type is the most delicate write in the app: templates are
shared by every card of that type, and **AnkiConnect has no `deleteModel`** —
only Anki's own GUI can remove one. So `model-*.json` is **evidence, not a way
back**: it records exactly what was created, which is what you need to
reproduce or repair it by hand.

## The repair flow

`struggling` in `/api/today` ranks cards by failures, time lost and interval
drops — the head of it on Hoy, the whole ranking on `/api/stuck`, and just the
count on the Dashboard. A card must clear both gates to appear: `MIN_ATTEMPTS`
reviews and `MIN_FAILURES` failures. Without the failure gate it is really a slowest-cards
list, and a card you have never got wrong is not one you are stuck on.

`repair.propose()` sends the card plus its review history and asks for a rewrite.
Field names come back from a language model, so they are untrusted: anything the
note does not have is dropped and reported in `rejected_fields`, and `/api/apply`
validates them again before writing. Expect 8–15 s per call.

## The deck naming convention

Everything about levels rests on one rule: a deck is named
**`Skill::Level::Topic`** — `Grammar::B1::Phrasal verbs`. Skills are the five in
`analysis.SKILLS`, levels the five in `analysis.LEVELS`; matching is
case-insensitive and the canonical spelling is what comes back.

**The name also says what belongs to this app.** `analysis.in_scope()` counts
a deck when its first component is one of the five skills, and nothing else.
The collection belongs to a person, not to an app: next to the English there
are decks for a master's degree, and counting them inflated the cards due,
would have stretched the streak with days that had no English in them, and put
Spanish NLP cards in the stuck ranking. There is no list to maintain and no
setting to remember — what this app creates is born inside the convention and
is in by construction; what is not stays out, and stays visible on Mazos, which
is where a deck the app cannot read actually matters.

**The name is the whole database.** The classification is derived on every read
and nothing is stored, so renaming a deck in Anki reclassifies it and there is
no mapping on disk that can drift. Renaming is the editing interface.

Decks that do not follow it land under "sin clasificar" rather than being
dropped — a deck the app cannot read is exactly the thing worth seeing. The one
exception is an empty parent that only holds subdecks: `Grammar` above
`Grammar::B1::…` is scaffolding, not a deck that failed to classify.

A level is **held** at `analysis.MATURITY_THRESHOLD` (60 %) of its cards mature,
where mature is Anki's own three weeks. The level you are standing on is the
first, walking A1 → C1, that is not held; an empty level is not held either, so
the walk stops there. A level with no cards is a **hole**, and holes are what to
generate next — a missing level and a weak level need different actions, and
keeping them apart is what makes Progreso a diagnosis instead of a progress bar.

## The syllabus of a level

Maturity answers **"do you remember your cards"**. It cannot answer **"do your
cards cover the level"**, and those are different questions: Grammar A1 holds
seven decks — Present simple, its negatives, its questions, Verb to be,
Questions with be, Short answers, Wh- questions — which is *one* point sliced
seven ways. Twenty-four cards, and a level that would read as held at 60 %
maturity with most of its programme never studied. That is the silent failure
this app is built to avoid, so `POST /api/syllabus` asks the other question.

**Two halves of different natures, so they live differently.**

| | What it is | How it lives |
|---|---|---|
| The syllabus | an external, stable fact — what an A1 teaches | generated **once**, frozen in `data/syllabus/`, yours to edit |
| The coverage | a fact about the collection, volatile | derived on every read |

**Deriving the syllabus every time was the first attempt and it does not
work.** Two runs over Grammar A1, minutes apart with nothing touched, returned
7/14 and 3/14. A figure that moves on its own is not a diagnosis — you cannot
tell "I covered two more points" from "the model counted differently".

**Measured, the disagreement is about granularity, not content.** Three drafts
of Grammar A1 shared eleven of eighteen points outright; most of the rest were
the same point split more finely — "Presente simple afirmativo" against
"Presente simple". And splitting more finely is exactly what moves the count,
since each point then covers less. So the fix is not a better prompt: it is to
stop asking twice.

**Three drafts and a merge, once.** `generate.build_syllabus` samples the level
`SYLLABUS_DRAFTS` times and folds the drafts into one list, each point carrying
`drafts` — how many named it. That is not the model checking itself, which
would be another sample of the same noise; it is the model measuring its own
uncertainty, and it tells a person where to look. Seventeen of eighteen at 3/3
is settled; a point at 1/3 is where your judgement is worth more than another
call.

**Asking a second model to audit it would not help.** `m98/fluent` was the
candidate and it ships **no curriculum at all** — its level is a field the
learner types, or a five-question quiz mapped to a band. Running the syllabus
past it is the same model wearing different markdown. A real external anchor
exists — Cambridge's English Grammar Profile, ~1,200 grammar points tagged by
CEFR over a learner corpus — and it is a separate project, not a prompt.

**The point of freezing is that the syllabus becomes yours.** It was the one
place in this app where the model decided and you did not get a say, which
contradicts everything else here. The files are plain JSON on purpose: delete a
point you do not care about, add the one your job needs, reorder them. Nothing
rewrites them. `syllabus.load` re-reads with the same distrust it wrote with —
a broken entry is dropped, not fatal — and compares mtime against `generated`
so a hand-edited syllabus says so, and "Regenerar" warns before overwriting
work that has no undo.

**Only `covered_by` is a claim about the collection, so it is the only thing
verified.** The coverage call receives the frozen points and returns them with
the deck that teaches each; `generate.cover` walks the **frozen** list and
indexes the answer by name, so a point the model invented is dropped and one it
skipped still appears, uncovered. A topic it names is accepted only if it
really exists. That is the safe side of the error — a gap too many proposes
work you can decline, a gap too few hides it.

**The card sample is spread across the decks, not taken per deck.** Seven decks
at sixty fronts each would be four hundred lines of prompt, and a per-deck cap
would leave the last decks with nothing visible — invisible is
indistinguishable from empty, and the model would mark them uncovered.

**What counts as a point depends on the skill.** Without saying so the model
returns grammar for all five: the first Writing A1 tried came back with
"artículos a/an/the" and "plural de los sustantivos", which is Grammar's
syllabus under another name. `generate.SYLLABUS_POINT` says what a point is for
each — a text you can produce for Writing, a situation you can handle for
Speaking.

An uncovered point carries into `#/agregar/<skill>/<level>/<topic>`, which
writes it into the box — and the box is the question, so the terms proposed are
the ones that point is made of.

## Front end

No framework, no build step, no npm. Save a file, reload the browser.

- **Nine screens, hash routing.** `#/hoy`, `#/progreso`, `#/skill/<skill>`,
  `#/mazos`, `#/agregar` (also `#/agregar/<skill>/<level>` and
  `#/agregar/<skill>/<level>/<topic>`), `#/atascos`,
  `#/ajustes`, `#/dashboard`. Hash and not path:
  `StaticFiles` is mounted at the root and knows nothing about `/progreso`, so
  reloading a path route would 404.
- **Hoy and Dashboard are two screens, not one.** Hoy is Pantalla 1 v2 of the
  wireframe — only what depends on whether you show up today: the headline, the
  streak, the 30-day calendar, the decks and the cards you keep failing. The
  Dashboard is Pantalla 1, the panorama, and it is **last in the menu on
  purpose**: you enter Hoy to start and the Dashboard to look. Merging them was
  the first attempt and it made a landing screen you had to scan before you
  could begin.
- **The Dashboard carries the four sections of the wireframe and no more**:
  the strip of four figures, Actividad semanal · Repaso de hoy · Progreso por
  habilidad · Mis mazos. Two deliberate departures, both written into
  `.interface-design/system.md`: **no Precisión and no Tiempo estudiado** —
  cumulative metrics, ruled out below — and no search or "+ Nuevo mazo" in the
  header, because searching is the Mazos screen and creating a deck is a write
  into Anki that does not exist yet. Its one primary action sits under the
  ring, where the wireframe puts it.
- **Its four sections are one grid, not two stacked columns.** `.dash` is a
  single two-column grid so its rows align; with a column per side each panel
  started where the one above it ended and "Progreso por habilidad" and "Mis
  mazos" sat at different heights, which is dizzying to read.
- `index.html` is a **shell**. Every screen carries its own markup inside its
  module in `static/views/`, and each exports `render(root, params)`.
- View modules are imported **statically** in `router.js`. They are local files
  and a dynamic import that fails leaves a blank screen with nothing to fall
  back on; that trade only makes sense for anime.js, where the page is already
  usable without it.
- `/api/catalog` is fetched **once per navigation** and shared by the skill bar
  and the screen (`ui.catalog()`); the router drops the cache on the way in,
  which is what keeps it from going stale.
- Anything thrown as `ui.ApiError` reaches the router, which paints the offline
  banner and leaves the view empty. Views do not each write their own "Anki no
  responde".
- Served from the **root**, not `/static`: the mount points at `static/`, so the
  page links `/styles.css`, not `/static/styles.css`.
- A middleware sets `Cache-Control: no-cache` outside `/api/`. StaticFiles sends
  ETag and Last-Modified but no Cache-Control, so browsers fall back to
  heuristic caching and keep serving a stylesheet edited minutes ago. **That
  looks exactly like the change not having worked** — it cost a whole round of
  "you didn't do it" / "yes I did" before the header was added.
- **Excalifont is vendored** at `static/fonts/`, SIL OFL 1.1, one 25 KB subset.
  Same rule as anime.js: local-only app, no CDN. Declared with `font-display:
  swap` and a `unicode-range`, and the system stack stays behind it in
  `--font` — a glyph outside the subset degrades to the fallback instead of
  showing tofu. Figures deliberately stay `--mono`: the animated streak
  counter needs `tabular-nums`.
- The hand-drawn look is **a skin, nothing more.** Same DOM, same buttons, same
  keyboard, same focus, same resize. Outlines take `--r-rough` /
  `--r-rough-alt` instead of `--r-md`; small squares keep `--r-sm`.
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
- **The headline is the goal, not the backlog.** 271 due is an import of a
  thousand cards, not a debt you ran up; as a headline it only discourages, and
  discouraging is the one thing this app cannot afford. The backlog stays
  visible under the bar, in grey, with its reason.
- **The goal lives in `data/state.json`, never in Anki's deck options.** A
  limit written into Anki changes what Anki itself serves, on the desktop and
  on the phone, and scheduling belongs to Anki. The goal is this app's: an
  intention, not a cap.
- **The streak has one grace day per month.** Breaking it is the moment of
  highest abandonment risk.
- **Never write to Anki without recording the previous state.** Additive
  writes leave a creation record instead, and a note type leaves evidence,
  since it cannot be deleted.
- **Nothing generated is ticked by default.** Every card is a decision. The
  model proposing thirty cards and a single "aceptar todo" is how a collection
  fills with cards nobody chose. Editing notes
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
- **`addNotes` is all-or-nothing.** One bad note raises for the whole call —
  `['cannot create note because it is a duplicate']` — instead of returning a
  null for that slot. Check with `canAddNotesWithErrorDetail` before writing.
- **Deck counts roll up into the parents.** `getDeckStats` reports the same
  206 for `Reading`, `Reading::A1` and `Reading::A1::Mil palabras`, so summing
  every row counts each card once per level of its name — 458 due cards read
  as 1147. `analysis.due_by_deck` totals the **roots** and lists the
  **leaves**: the first is what Anki will serve today, the second is what you
  can pick. They do not add up, because a parent's daily limit can be lower
  than the sum of its children.
- **The first field is not always the question.** The grammar note type opens
  with `Tipo`, so the stuck list showed six rows called "B · corregir", and
  Refold opens with a sort index. `anki.card_summaries` and `anki.deck_fronts`
  join the next field when the first is shorter than
  `anki.LABEL_LIKE_CHARS`, and drop it when it is a bare number.
- **A deck created through AnkiConnect gets the default options preset.**
  `createDeck` takes no preset, so a merge moves the cards with their
  scheduling intact — intervals, maturity, due dates — into a deck whose daily
  limits are the factory ones. `Refold Inglés-mil` served 988 reviews a day
  under its own preset; as `Reading::A1::Mil palabras` it serves 200, and the
  993 due cards look like 200 in Anki's deck browser. `getDeckStats` reports
  the capped number, which is the honest one: it is what Anki will actually
  give you today.
- **`deck:"X"` is not deck membership.** In this collection
  `findCards deck:"Refold Inglés-mil"` returned 1000 cards and six of them
  lived in another deck entirely. Confirm with `cardsInfo` and compare
  `deckName` before moving anything, or a merge quietly takes cards out of a
  deck you were not touching.
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
  every module. Neither catches a **name that no longer exists**: `TERMS_PROMPT`
  was deleted by an edit to the module's prompts and "Proponer términos" was a
  500 on every call — parsing fine, importing fine, dead at the first call. An
  AST sweep for uppercase names used but never assigned at module level finds
  it in a second, and there is no linter on this machine to do it for you.
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
early Dashboard screens carry cumulative metrics and an account/plan sidebar.
The cumulative metrics stay ruled out; the sidebar came back, but as navigation
only — never an account or a plan. **The "v2" screens are the target**
— "Hoy" and the session cards with their Listening / Speaking / Reading /
Writing variants.

**`.interface-design/system.md` holds the design decisions — read it before
touching `static/` and hold to its values instead of reinventing them.**
Direction is "la ficha de cartón": cool card stock, graphite, borders-only
depth, 4px base. One accent, `--present` `#2a5580`, the blue-black of writing
ink. It means exactly two things and nothing else: **the primary action**, and
**here and now** — today's calendar mark, the level you are standing on, the
sidebar item you are on. Nowhere else. **Red is
only ever a failure of the system**, never an action and never a state of the
person: a day not studied is unmarked paper, not a hole, and a stuck card gets
no colour at all.

The `interface-design` skill is installed in `.claude/skills/`, with
`/design-review` and `/design-deslop` as commands.

## Known issues

- `spike_anki.py` still reads `decks[0]`, which is `Default` and always empty.
  The app itself no longer makes that mistake; the spike was left as written.
- `data/state.json` now exists and holds the daily goal, which Ajustes writes.
  `last_sync` is still never written, so `/api/health` keeps reporting null.
- The collection also holds the decks of a master's degree (`PLN in Action`),
  which are not English. They are out of scope by name — see below — so they
  show on Mazos and nowhere else.
- Mazos lists and searches but cannot rename or archive yet.
- **AnkiConnect cannot build a filtered deck** — verified against `apiReflect`.
  So "30 of vocabulary plus 10 of phrasal verbs" in one session is not
  possible from here: the topic picker opens **one** deck, which is what
  `guiDeckReview` can do.
- **AnkiConnect has no `renameDeck`** — verified against the 121 actions of
  `apiReflect`. `snapshot.move_cards()` now covers it, so a rename or a merge
  is possible and reversible; what is still missing is the screen for it on
  Mazos.
- Card generation writes one note type and any number of decks, but **cannot
  rename or move** anything afterwards: that still needs the move record that
  Mazos is waiting on.

## Current status

Nine screens navigate: Hoy, Progreso, the five skill libraries, Mazos, Agregar,
Atascos, Ajustes and Dashboard. Hoy and the Dashboard read `/api/today`, and
the Dashboard also reads `/api/catalog`, as Progreso, the skill screens and
Mazos do; Atascos reads `/api/stuck`; repair works from both Hoy and Atascos.

Card generation works end to end: propose terms from the failures or from one
hole, three candidates per term in a single table, edit them in place, pick an
existing deck or build a new one, and write with a creation record. Verified against the live collection — note type
created, two cards written, read back from Anki, and undone from the record.

The syllabus reads on the five skill screens: one button per level panel,
which names what that level is made of and marks what your decks already
cover. Verified against the live collection — Grammar A1 froze at eighteen
points, seventeen of them named by all three drafts; a hand edit to the file
survives a reload and is reported as such.

Not built: rename/archive on Mazos and the exercise mode.

(Update this section after each phase.)
