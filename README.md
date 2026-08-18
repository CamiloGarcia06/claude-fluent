# claude-fluent

Personal app to improve my English. **Single user: me.** Not a product, will not
be scaled, will never have other users.

## Architecture

Anki is the spaced repetition engine and the source of truth. This app does not
schedule or run reviews: it **syncs, analyses and generates cards.**

- Anki + AnkiConnect at `http://127.0.0.1:8765` (Anki must be running)
- FastAPI backend, also serves the frontend
- Plain HTML/CSS/JS frontend, no framework, no build step
- Animations with anime.js v4 from CDN
- Card generation through `claude -p` on my subscription
- Local state in `data/state.json`: sync cursor, diagnostics and change history only

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

Phase 0. Nothing built yet.
(Update this line after each phase.)

## Credits

Design directly informed by **[raine/anki-llm](https://github.com/raine/anki-llm)**
(MIT) — the AnkiConnect integration path, the snapshot-before-write rule, and the
doctor/health-check-first idea all come from there. No code is shared: anki-llm is
Rust and provider-agnostic (OpenAI, Gemini, Ollama…), this app is Python and runs
on the Claude Code subscription through `claude -p`.
