"""FastAPI backend. Serves the API and the static front end."""
import shutil
from datetime import date, datetime, timedelta

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

import analysis
import anki
import llm
import repair
import snapshot

app = FastAPI(title="claude-fluent")


@app.middleware("http")
async def no_stale_assets(request, call_next):
    """Serve the static files fresh.

    StaticFiles sends ETag and Last-Modified but no Cache-Control, so browsers
    fall back to heuristic caching and happily keep serving a stylesheet you
    edited minutes ago. During development that is indistinguishable from the
    change not having worked.
    """
    response = await call_next(request)
    if not request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
    return response


def _window_start_ms(days: int = analysis.CALENDAR_DAYS) -> int:
    """Midnight local time, `days` back. Reviews are fetched from here."""
    start = datetime.combine(date.today() - timedelta(days=days - 1), datetime.min.time())
    return int(start.timestamp() * 1000)


@app.get("/api/health")
def health() -> dict:
    """Checked first because every failure in this system is silent: Anki
    closed or claude without a session both leave the app looking normal
    while it lies to you."""
    return {
        "anki": anki.is_alive(),
        "claude": shutil.which("claude") is not None,
        "last_sync": None,  # data/state.json is not written yet
    }


@app.get("/api/today")
def today() -> dict:
    if not anki.is_alive():
        raise HTTPException(503, "AnkiConnect is not answering — is Anki running?")

    reviews = anki.reviews_since(_window_start_ms())
    deck_counts = anki.due_counts()
    summary = analysis.summary(reviews, deck_counts, date.today())

    # analysis.py stays pure, so the card text is looked up here and merged in.
    details = anki.card_summaries([c["card_id"] for c in summary["struggling"]])
    for card in summary["struggling"]:
        found = details.get(card["card_id"], {})
        card["front"] = found.get("front", "")
        card["note_id"] = found.get("note_id")

    return summary


@app.post("/api/study")
def study() -> dict:
    """Hand the session over to Anki, on the deck that actually has work.

    Reviewing is Anki's job; this app only decides where to start.
    """
    if not anki.is_alive():
        raise HTTPException(503, "AnkiConnect is not answering — is Anki running?")

    due = analysis.due_by_deck(anki.due_counts())
    target = next((d for d in due["decks"] if d["due"] > 0), None)
    if target is None:
        raise HTTPException(409, "No hay tarjetas pendientes hoy.")

    anki.open_deck_review(target["deck"])
    return {"ok": True, "deck": target["deck"], "due": target["due"]}


@app.post("/api/add-cards")
def add_cards() -> dict:
    """Open Anki's Add dialog. Generation with the model comes later."""
    if not anki.is_alive():
        raise HTTPException(503, "AnkiConnect is not answering — is Anki running?")
    anki.open_add_cards()
    return {"ok": True}


@app.post("/api/repair/{note_id}")
def propose_repair(note_id: int) -> dict:
    """Ask the model for a better version of a note. Writes nothing."""
    if not anki.is_alive():
        raise HTTPException(503, "AnkiConnect is not answering — is Anki running?")

    try:
        note = anki.note_info(note_id)
    except KeyError as e:
        raise HTTPException(404, str(e)) from e

    try:
        return repair.propose(note)
    except llm.LLMError as e:
        raise HTTPException(502, f"claude -p failed: {e}") from e


@app.post("/api/apply/{note_id}")
def apply_repair(note_id: int, payload: dict) -> dict:
    """Write the approved fields back. Snapshot first, always."""
    if not anki.is_alive():
        raise HTTPException(503, "AnkiConnect is not answering — is Anki running?")

    fields = payload.get("fields")
    if not isinstance(fields, dict) or not fields:
        raise HTTPException(400, "no fields to apply")

    try:
        note = anki.note_info(note_id)
    except KeyError as e:
        raise HTTPException(404, str(e)) from e

    # The client does not get to invent field names either.
    known = set(anki.note_fields(note))
    unknown = sorted(set(fields) - known)
    if unknown:
        raise HTTPException(400, f"unknown fields for this note: {', '.join(unknown)}")

    # The client sends plain text; Anki stores HTML.
    encoded = {name: anki.to_field_html(str(value)) for name, value in fields.items()}

    try:
        path = snapshot.update_note_fields(note_id, encoded)
    except anki.WriteWithoutSnapshot as e:  # cannot happen; loud if it ever does
        raise HTTPException(500, str(e)) from e

    written = anki.note_fields(anki.note_info(note_id))
    return {
        "ok": True,
        "note_id": note_id,
        "snapshot": str(path),
        "fields": {name: anki.to_plain_text(value) for name, value in written.items()},
    }


# Must go last: mounted at the root, it swallows the /api routes above it.
app.mount("/", StaticFiles(directory="static", html=True), name="static")
