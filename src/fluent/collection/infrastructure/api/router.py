"""Hoy, catálogo, atascos y la entrega de la sesión a Anki."""

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends

from fluent.collection.domain import analysis

from .deps import CollectionUseCases, get_collection

router = APIRouter(prefix="/api", tags=["collection"])

# The Atascos screen is the whole ranking, not the head of it that Today shows.
STUCK_LIMIT = 50


def window_start_ms(days: int = analysis.CALENDAR_DAYS) -> int:
    """Midnight local time, `days` back. Reviews are fetched from here."""
    start = datetime.combine(date.today() - timedelta(days=days - 1), datetime.min.time())
    return int(start.timestamp() * 1000)


@router.get("/today")
def today(uc: CollectionUseCases = Depends(get_collection)) -> dict:
    return uc.today(date.today(), window_start_ms(), uc.daily_goal())  # type: ignore[operator]


@router.get("/catalog")
def catalog(uc: CollectionUseCases = Depends(get_collection)) -> dict:
    return uc.catalog()


@router.get("/stuck")
def stuck(uc: CollectionUseCases = Depends(get_collection)) -> dict:
    return uc.stuck(window_start_ms(), STUCK_LIMIT)


@router.post("/study")
def study(deck: str | None = None, uc: CollectionUseCases = Depends(get_collection)) -> dict:
    return uc.open_review(deck)


@router.post("/add-cards")
def add_cards(uc: CollectionUseCases = Depends(get_collection)) -> dict:
    return uc.open_add_cards()
