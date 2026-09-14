"""Raíz de composición: el único módulo que conoce todas las piezas concretas.

Construye los adaptadores (Anki, snapshots, el modelo, el disco, el reloj), los
casos de uso de cada funcionalidad, los deja en `app.state` para sus routers, y
registra el único traductor de errores de dominio a HTTP. Además sirve
`/api/health` y la interfaz estática."""

from __future__ import annotations

import shutil

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from fluent.anki.infrastructure.client import AnkiClient
from fluent.anki.infrastructure.snapshots import Snapshots
from fluent.cards.application.apply_repair import ApplyRepair
from fluent.cards.application.propose_cards import ProposeCards
from fluent.cards.application.propose_terms import ProposeTerms
from fluent.cards.application.repair_note import RepairNote
from fluent.cards.application.write_notes import WriteNotes
from fluent.cards.infrastructure.anki_store import AnkiCardStore
from fluent.cards.infrastructure.api.deps import CardUseCases
from fluent.cards.infrastructure.api.router import router as cards_router
from fluent.cards.infrastructure.llm_proposer import LlmProposer
from fluent.collection.application.build_catalog import BuildCatalog
from fluent.collection.application.build_stuck import BuildStuck
from fluent.collection.application.build_today import BuildToday
from fluent.collection.application.open_add_cards import OpenAddCards
from fluent.collection.application.open_review import OpenReview
from fluent.collection.infrastructure.api.deps import CollectionUseCases
from fluent.collection.infrastructure.api.router import router as collection_router
from fluent.model.infrastructure.claude_cli import ClaudeCli
from fluent.settings.application.read_settings import ReadSettings
from fluent.settings.application.write_settings import WriteSettings
from fluent.settings.infrastructure.api.deps import SettingsUseCases
from fluent.settings.infrastructure.api.router import router as settings_router
from fluent.settings.infrastructure.disk_state import DiskState
from fluent.shared.clock import SystemClock
from fluent.shared.config import STATIC_DIR
from fluent.shared.errors import Conflict, DomainError, Invalid, NotFound, Unavailable, Upstream
from fluent.syllabi.application.cover_syllabus import CoverSyllabus
from fluent.syllabi.application.freeze_syllabus import FreezeSyllabus
from fluent.syllabi.application.read_syllabus import ReadSyllabus
from fluent.syllabi.infrastructure import disk as syllabus_disk
from fluent.syllabi.infrastructure.api.deps import SyllabusUseCases
from fluent.syllabi.infrastructure.api.router import router as syllabi_router
from fluent.syllabi.infrastructure.disk_store import DiskSyllabusStore
from fluent.syllabi.infrastructure.llm_model import LlmSyllabusModel
from fluent.writing.application.answer_turn import AnswerTurn
from fluent.writing.application.close_session import CloseSession
from fluent.writing.application.get_patterns import GetPatterns
from fluent.writing.application.get_practice import GetPractice
from fluent.writing.application.mark_pattern import MarkPattern
from fluent.writing.application.start_session import StartSession
from fluent.writing.infrastructure.api.deps import WritingUseCases
from fluent.writing.infrastructure.api.router import router as writing_router
from fluent.writing.infrastructure.disk_practice import DiskPatterns, DiskSessions
from fluent.writing.infrastructure.llm_coach import LlmCoach

# Un solo traductor de errores de dominio a HTTP. Lo inválido es 400, como
# devolvían los endpoints planos; 422 es de FastAPI para cuerpos mal formados.
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


def build_app() -> FastAPI:
    # ---- adaptadores
    anki = AnkiClient()
    snapshots = Snapshots()
    generate = ClaudeCli().generate
    clock = SystemClock()
    state = DiskState()
    syllabi_store = DiskSyllabusStore()
    sessions = DiskSessions()
    patterns = DiskPatterns()
    cards_store = AnkiCardStore(anki, snapshots)

    # ---- casos de uso por funcionalidad
    settings = SettingsUseCases(read=ReadSettings(state), write=WriteSettings(state))
    collection = CollectionUseCases(
        today=BuildToday(anki),
        catalog=BuildCatalog(anki),
        stuck=BuildStuck(anki),
        open_review=OpenReview(anki),
        open_add_cards=OpenAddCards(anki),
        daily_goal=lambda: settings.read()["daily_goal"],
    )
    proposer = LlmProposer(generate, anki)
    cards = CardUseCases(
        propose_terms=ProposeTerms(cards_store, proposer),
        propose_cards=ProposeCards(cards_store, proposer),
        write_notes=WriteNotes(cards_store),
        repair_note=RepairNote(cards_store, proposer),
        apply_repair=ApplyRepair(cards_store),
    )
    syllabus_model = LlmSyllabusModel(generate)
    syllabi = SyllabusUseCases(
        read=ReadSyllabus(syllabi_store),
        freeze=FreezeSyllabus(syllabi_store, syllabus_model, clock),
        cover=CoverSyllabus(syllabi_store, syllabus_model, cards_store, clock),
    )
    coach = LlmCoach(generate)
    writing = WritingUseCases(
        get_practice=GetPractice(sessions),
        start_session=StartSession(sessions, clock),
        answer_turn=AnswerTurn(sessions, coach),
        close_session=CloseSession(sessions, patterns, coach, clock),
        get_patterns=GetPatterns(patterns),
        mark_pattern=MarkPattern(patterns),
    )

    app = FastAPI(title="claude-fluent")
    app.state.anki = anki
    app.state.settings = settings
    app.state.collection = collection
    app.state.cards = cards
    app.state.syllabi = syllabi
    app.state.writing = writing

    @app.exception_handler(DomainError)
    def translate_domain_error(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=status_for(exc),
            content={"detail": exc.message or exc.code, "error": exc.code},
        )

    @app.middleware("http")
    async def no_stale_assets(request, call_next):
        """StaticFiles sends ETag and Last-Modified but no Cache-Control, so
        browsers keep serving a stylesheet you edited minutes ago."""
        response = await call_next(request)
        if not request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response

    @app.get("/api/health")
    def health() -> dict:
        """Checked first because every failure in this system is silent: Anki
        closed or claude without a session both leave the app looking normal."""
        return {
            "anki": anki.is_alive(),
            "claude": shutil.which("claude") is not None,
            "last_sync": settings.read().get("last_sync"),
            "syllabus": {
                "total": len(syllabus_disk.levels_held()),
                "unreadable": syllabus_disk.unreadable(),
            },
        }

    for router in (
        settings_router,
        collection_router,
        cards_router,
        syllabi_router,
        writing_router,
    ):
        app.include_router(router)
    # Must go last: mounted at the root, it swallows the /api routes above it.
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
    return app


app = build_app()
