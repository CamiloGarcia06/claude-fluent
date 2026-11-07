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
uv sync                       # crea .venv con las dependencias del pyproject
task dev                      # http://127.0.0.1:8001 con recarga (el servicio ocupa el 8000)
task check                    # ruff, pyright, pytest, hexcheck
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

Ten screens navigate: Hoy, Progreso, the five skill libraries, Mazos, Agregar,
Atascos, Ajustes, Dashboard and TOEFL. Card generation works end to end — propose
terms, three candidates each, edit in place, pick a deck, write with a creation
record. The syllabus of a level reads on the skill screens: what the level is
made of, and how much of it your decks cover.

TOEFL (`#/toefl`) trains the reading and writing tasks of the iBT (January 2026
format), tabs in exam order. Reading: Complete the Words, Read in Daily Life and
Read an Academic Passage — multiple choice with a clock against the exam pace,
and after grading the sentence that answers each question is highlighted in the
text. Writing: Build a Sentence, Write an Email (7 min) and Academic Discussion
(10 min, 100 words), the last two graded by Claude with the ETS 0-5 rubric plus
an untimed rewrite. `claude -p` fills the bank in `data/toefl/` (15-70 s a
batch) and grades writing; everything else is graded without the model. The
advice comes from the last 10 attempts of each pattern (question type, rubric
criterion), and the next exercise starts with the weakest one. Listening and
speaking are not built: they need TTS/STT dependencies.

On top of the TOEFL screen, **Camino a B1** measures the master's requirement (B1)
on what I write. Every writing submission also gets a CEFR level (A1-C1) from
the grader, and a B1 checklist found by rules, without the model (varied
connectors, contrast, reasons, present perfect, conditional, relative clause).
The path is a window, not a history: how many of my last 10 first attempts are
B1 or above, with 8 of 10 as the target. The mission for the next text is the
two checklist items missing most in the last 5. The weekly routine: Monday and
Friday a new Texto B1, Tuesday rewrite the weakest text of the week (untimed),
Wednesday nothing (PLN class), Thursday an Academic Discussion, weekend free.
The **Texto B1** tab is not TOEFL: Cambridge B1 Preliminary style tasks (email
with notes, article, story; 100 words, 20 min), because that is what the
Javeriana placement looks like.

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
