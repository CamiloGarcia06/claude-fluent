"""Raíz de composición y, mientras dure la migración, también los endpoints.

Las funcionalidades ya migradas (collection) entran como casos de uso cableados
aquí; el resto sigue plano. Un solo traductor de errores de dominio a HTTP."""

import shutil
from datetime import date, datetime, timedelta

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from fluent import anki, state

# Con alias: `syllabus` es el nombre de la mitad del app —el endpoint, la
# pantalla, el archivo— y el módulo se lee dentro de las funciones que lo
# sirven. Sin alias, cualquier nombre local lo taparía.
from fluent import syllabus as syllabus_store
from fluent.cards.application.apply_repair import ApplyRepair
from fluent.cards.application.propose_cards import ProposeCards
from fluent.cards.application.propose_terms import ProposeTerms
from fluent.cards.application.repair_note import RepairNote
from fluent.cards.application.write_notes import WriteNotes
from fluent.cards.infrastructure.anki_store import AnkiCardStore
from fluent.cards.infrastructure.llm_proposer import LlmProposer
from fluent.collection.application.build_catalog import BuildCatalog
from fluent.collection.application.build_stuck import BuildStuck
from fluent.collection.application.build_today import BuildToday
from fluent.collection.domain import analysis
from fluent.collection.infrastructure.anki_reader import AnkiReader
from fluent.paths import STATIC_DIR
from fluent.shared.clock import SystemClock
from fluent.shared.errors import Conflict, DomainError, Invalid, NotFound, Unavailable, Upstream
from fluent.syllabi.application.cover_syllabus import CoverSyllabus
from fluent.syllabi.application.freeze_syllabus import FreezeSyllabus
from fluent.syllabi.application.read_syllabus import ReadSyllabus
from fluent.syllabi.infrastructure.disk_store import DiskSyllabusStore
from fluent.syllabi.infrastructure.llm_model import LlmSyllabusModel
from fluent.writing.application.answer_turn import AnswerTurn
from fluent.writing.application.close_session import CloseSession
from fluent.writing.application.get_patterns import GetPatterns
from fluent.writing.application.get_practice import GetPractice
from fluent.writing.application.mark_pattern import MarkPattern
from fluent.writing.application.start_session import StartSession
from fluent.writing.infrastructure.disk_practice import DiskPatterns, DiskSessions
from fluent.writing.infrastructure.llm_coach import LlmCoach

app = FastAPI(title="claude-fluent")

# --- composición: adaptadores y casos de uso de las funcionalidades migradas
_collection = AnkiReader()
build_today = BuildToday(_collection)
build_catalog = BuildCatalog(_collection)
build_stuck = BuildStuck(_collection)
_cards = AnkiCardStore()
_proposer = LlmProposer()
propose_terms_uc = ProposeTerms(_cards, _proposer)
propose_cards_uc = ProposeCards(_cards, _proposer)
write_notes_uc = WriteNotes(_cards)
repair_note_uc = RepairNote(_cards, _proposer)
apply_repair_uc = ApplyRepair(_cards)
_clock = SystemClock()
_syllabi = DiskSyllabusStore()
_syllabus_model = LlmSyllabusModel()
read_syllabus_uc = ReadSyllabus(_syllabi)
freeze_syllabus_uc = FreezeSyllabus(_syllabi, _syllabus_model, _clock)
cover_syllabus_uc = CoverSyllabus(_syllabi, _syllabus_model, _cards, _clock)
_sessions = DiskSessions()
_patterns = DiskPatterns()
_coach = LlmCoach()
get_practice_uc = GetPractice(_sessions)
start_session_uc = StartSession(_sessions, _clock)
answer_turn_uc = AnswerTurn(_sessions, _coach)
close_session_uc = CloseSession(_sessions, _patterns, _coach, _clock)
get_patterns_uc = GetPatterns(_patterns)
mark_pattern_uc = MarkPattern(_patterns)


# Un solo traductor de errores de dominio a HTTP. Lo inválido sigue siendo 400,
# como devolvían los endpoints planos; 422 es de FastAPI para cuerpos mal formados.
STATUS_BY_ERROR: tuple[tuple[type[DomainError], int], ...] = (
    (Unavailable, 503),
    (Upstream, 502),
    (NotFound, 404),
    (Conflict, 409),
    (Invalid, 400),
)


def status_for(exc: DomainError) -> int:
    for kind, status in STATUS_BY_ERROR:
        if isinstance(exc, kind):
            return status
    return 400


@app.exception_handler(DomainError)
def translate_domain_error(_: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(
        status_code=status_for(exc),
        content={"detail": exc.message or exc.code, "error": exc.code},
    )


# The Atascos screen is the whole ranking, not the head of it that Today shows.
STUCK_LIMIT = 50


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


@app.get("/api/settings")
def settings() -> dict:
    """Lo que decide el app y Anki no sabe. Hoy: la meta diaria."""
    return state.read()


@app.post("/api/settings")
def save_settings(payload: dict) -> dict:
    try:
        return state.write(payload or {})
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/health")
def health() -> dict:
    """Checked first because every failure in this system is silent: Anki
    closed or claude without a session both leave the app looking normal
    while it lies to you."""
    # Los temarios entran acá por la misma razón que Anki y `claude`: un
    # archivo que el app no puede leer se descubría recién cuando ya te lo
    # había regenerado —tu edición "no toma", la pantalla se ve normal, y no
    # hay dónde enterarse—. Cuesta milisegundos y no toca Anki ni el modelo.
    bad = syllabus_store.unreadable()
    return {
        "anki": anki.is_alive(),
        "claude": shutil.which("claude") is not None,
        "last_sync": state.read().get("last_sync"),
        "syllabus": {"total": len(syllabus_store.levels_held()), "unreadable": bad},
    }


@app.get("/api/today")
def today() -> dict:
    return build_today(date.today(), _window_start_ms(), state.read()["daily_goal"])


@app.get("/api/catalog")
def catalog() -> dict:
    """The deck catalogue, skill -> level -> decks. The classification comes
    from the deck name every time it is read; renaming a deck in Anki is the
    whole editing interface."""
    return build_catalog()


@app.get("/api/stuck")
def stuck() -> dict:
    """The full list of cards you keep failing, with severity and the minutes
    they cost. The Today screen shows the head of this same ranking."""
    return build_stuck(_window_start_ms(), STUCK_LIMIT)


@app.post("/api/study")
def study(deck: str | None = None) -> dict:
    """Hand the session over to Anki, on the deck that actually has work.

    Reviewing is Anki's job; this app only decides where to start. With no
    `deck` the busiest one wins; the Progreso screen passes the one it named,
    so the button does what the sentence above it just promised.
    """
    if not anki.is_alive():
        raise HTTPException(503, "AnkiConnect is not answering — is Anki running?")

    due = analysis.due_by_deck(anki.due_counts())
    if deck is None:
        target = next((d for d in due["decks"] if d["due"] > 0), None)
    else:
        # Never forward an unchecked name to guiDeckReview: a deck that does
        # not exist opens the reviewer on nothing and looks like a hang.
        target = next((d for d in due["decks"] if d["deck"] == deck and d["due"] > 0), None)
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


@app.post("/api/generate/terms")
def generate_terms(payload: dict | None = None) -> dict:
    """What is worth making cards for, read off the failures and the holes.
    Proposes only. Optional `{skill, level}` narrows to one hole; optional
    `{topic}` is opened into its terms."""
    body = payload or {}
    return propose_terms_uc(
        _window_start_ms(),
        skill=body.get("skill", ""),
        level=body.get("level", ""),
        topic=body.get("topic", ""),
    )


@app.get("/api/syllabus")
def syllabus_frozen(skill: str = "", level: str = "") -> dict:
    """El temario congelado de un nivel, con la cobertura guardada si sirve.
    Sin modelo, sin Anki: milisegundos. `frozen: false` es la primera vez."""
    return read_syllabus_uc(skill, level)


@app.post("/api/syllabus")
def syllabus_freeze(payload: dict | None = None) -> dict:
    """Congelar el temario de un nivel (tres borradores y una fusión, ~100 s).
    Sólo llama al modelo si no hay temario o con `{regenerate: true}`."""
    body = payload or {}
    return freeze_syllabus_uc(
        body.get("skill", ""), body.get("level", ""), bool(body.get("regenerate"))
    )


@app.post("/api/syllabus/coverage")
def syllabus_coverage(payload: dict | None = None) -> dict:
    """Qué mazo de los tuyos cubre cada punto del temario (~40 s). Sólo
    escribe la cobertura, en su propio archivo."""
    body = payload or {}
    return cover_syllabus_uc(body.get("skill", ""), body.get("level", ""))


@app.post("/api/generate/cards")
def generate_cards(payload: dict) -> dict:
    """Candidate cards for one term, and the deck they belong in. One term per
    request: each is its own `claude -p` call, so the screen fills in as they
    land and a term that fails costs only itself."""
    return propose_cards_uc(
        payload.get("term", ""), skill=payload.get("skill", ""), level=payload.get("level", "")
    )


@app.post("/api/notes")
def add_notes(payload: dict) -> dict:
    """Create the approved cards. The one write path for generation."""
    return write_notes_uc(payload.get("cards"))


@app.post("/api/repair/{note_id}")
def propose_repair(note_id: int) -> dict:
    """Ask the model for a better version of a note. Writes nothing."""
    return repair_note_uc(note_id)


@app.post("/api/apply/{note_id}")
def apply_repair(note_id: int, payload: dict) -> dict:
    """Write the approved fields back. Snapshot first, always."""
    return apply_repair_uc(note_id, payload.get("fields"))


# ── La práctica de escritura ──────────────────────────────────────────────
# Ninguno de estos seis toca Anki: conversar en inglés no necesita la colección.


@app.get("/api/practice/session")
def practice_session() -> dict:
    """La sesión abierta, la última cerrada y los temas recientes. Lee disco."""
    return get_practice_uc()


@app.post("/api/practice/session")
def practice_start(payload: dict | None = None) -> dict:
    """Abrir una sesión sobre un tema. No llama al modelo."""
    body = payload or {}
    return start_session_uc(body.get("topic", ""), body.get("level"), bool(body.get("restart")))


@app.post("/api/practice/turn")
def practice_turn(payload: dict) -> dict:
    """Responder un mensaje y corregir lo que estorbó. Una llamada, 13-21 s."""
    return answer_turn_uc(
        payload.get("session_id"), payload.get("text", ""), payload.get("retry_index")
    )


@app.post("/api/practice/close")
def practice_close(payload: dict) -> dict:
    """Leer la sesión entera de una vez y contar los patrones."""
    return close_session_uc(payload.get("session_id"))


@app.get("/api/practice/patterns")
def practice_patterns() -> dict:
    return get_patterns_uc()


@app.post("/api/practice/patterns")
def practice_mark(payload: dict) -> dict:
    return mark_pattern_uc(payload.get("key"), payload.get("action"))


# Must go last: mounted at the root, it swallows the /api routes above it.
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
