# claude-fluent

Personal app to improve my English. **Single user: me.** Not a product, will not
be scaled, will never have other users.

## Architecture

Anki is the spaced repetition engine and the source of truth. This app does not
schedule or run reviews: it **syncs, analyses and generates cards.**

- Anki + AnkiConnect at `http://127.0.0.1:8765` (Anki must be running)
- FastAPI backend, also serves the frontend
- Plain HTML/CSS/JS frontend, no framework, no build step
- Animations with anime.js v4, **vendored** — the app is local-only and a
  module whose import fails takes the whole file down with it
- Card generation through `claude -p` on my subscription
- Local state in `data/state.json`: the daily goal, and nothing else. It is
  the only thing this app decides that Anki does not know

## Run it

```bash
source .venv/bin/activate
uvicorn app:app --reload      # http://localhost:8000
```

Anki must be running with the AnkiConnect add-on (code `2055492159`), or every
endpoint that touches the collection fails. `GET /api/health` says so
explicitly, and it is the first thing to check when anything looks wrong.

## Closed decisions — do not reopen

- **Do not build a custom SRS engine.** Anki already has one, battle-tested,
  with sync and mobile for free.
- **No study planner or timeline.** In spaced repetition the algorithm decides
  when you review; planning dates means planning something it will contradict.
- **No cumulative metrics** (total time, global accuracy). Only what depends on
  showing up today: streak, cards due, 30-day calendar.
- **The streak has one grace day per month.** Breaking it is the moment of
  highest abandonment risk.
- **Never write to Anki without saving the previous state** to `data/snapshots/`.
  Editing notes has no undo.
- **The model proposes, I approve.** Never write to the collection automatically.

## Working rules

- All code in English: filenames, identifiers and comments. Docs in Spanish.
- No tests for now. I am the only user and I try it every day.
- No new dependencies without asking me first.
- Never use `claude --bare`: it ignores the subscription login and requires an API key.
- On macOS, App Nap must be disabled or AnkiConnect stops responding.

## Current status

Nine screens navigate: Hoy, Progreso, the five skill libraries, Mazos, Agregar,
Atascos, Ajustes and Dashboard. Card generation works end to end — propose
terms, three candidates each, edit in place, pick a deck, write with a creation
record. The syllabus of a level reads on the skill screens: what the level is
made of, and how much of it your decks cover.

Not built: rename/archive on Mazos and the exercise mode.
(Update this section after each phase.)

## Licence

MIT — see `LICENSE`. Two vendored third-party files keep their own, listed in
`NOTICE`: anime.js (MIT) and Excalifont (SIL OFL 1.1).

## Credits

Design directly informed by **[raine/anki-llm](https://github.com/raine/anki-llm)**
(MIT) — the AnkiConnect integration path, the snapshot-before-write rule, and the
doctor/health-check-first idea all come from there. No code is shared: anki-llm is
Rust and provider-agnostic (OpenAI, Gemini, Ollama…), this app is Python and runs
on the Claude Code subscription through `claude -p`.
