"""Proponer, escribir y reparar tarjetas. El flujo es proponer → aprobar →
escribir, y son tres peticiones distintas."""

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends

from fluent.collection.domain import analysis

from .deps import CardUseCases, get_cards

router = APIRouter(prefix="/api", tags=["cards"])


def window_start_ms(days: int = analysis.CALENDAR_DAYS) -> int:
    start = datetime.combine(date.today() - timedelta(days=days - 1), datetime.min.time())
    return int(start.timestamp() * 1000)


@router.post("/generate/terms")
def generate_terms(payload: dict | None = None, uc: CardUseCases = Depends(get_cards)) -> dict:
    body = payload or {}
    return uc.propose_terms(
        window_start_ms(),
        skill=body.get("skill", ""),
        level=body.get("level", ""),
        topic=body.get("topic", ""),
    )


@router.post("/generate/cards")
def generate_cards(payload: dict, uc: CardUseCases = Depends(get_cards)) -> dict:
    return uc.propose_cards(
        payload.get("term", ""), skill=payload.get("skill", ""), level=payload.get("level", "")
    )


@router.post("/notes")
def add_notes(payload: dict, uc: CardUseCases = Depends(get_cards)) -> dict:
    return uc.write_notes(payload.get("cards"))


@router.post("/repair/{note_id}")
def propose_repair(note_id: int, uc: CardUseCases = Depends(get_cards)) -> dict:
    return uc.repair_note(note_id)


@router.post("/apply/{note_id}")
def apply_repair(note_id: int, payload: dict, uc: CardUseCases = Depends(get_cards)) -> dict:
    return uc.apply_repair(note_id, payload.get("fields"))
