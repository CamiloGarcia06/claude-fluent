"""Lo que el temario necesita de fuera: el disco (temario y cobertura), el
modelo, la colección (para la cobertura) y el reloj."""

from datetime import datetime
from typing import Protocol


class SyllabusStore(Protocol):
    def status(self, skill: str, level: str) -> str:
        """`"missing"` · `"ok"` · `"unreadable"`."""
        ...

    def load(self, skill: str, level: str) -> dict | None: ...

    def save(
        self, skill: str, level: str, points: list[dict], drafts: int, generated: str
    ) -> dict: ...

    def path_for(self, skill: str, level: str) -> str: ...

    def load_coverage(self, skill: str, level: str, points: list[dict]) -> dict | None: ...

    def save_coverage(
        self, skill: str, level: str, points: list[dict], decks: dict[str, int], computed: str
    ) -> dict: ...


class SyllabusModel(Protocol):
    """El modelo: redacta el temario de un nivel y juzga la cobertura."""

    def build(self, skill: str, level: str) -> dict:
        """`{"points": [...], "drafts": n}`. Lanza ModelFailed."""
        ...

    def cover(
        self, skill: str, level: str, points: list[dict], deck_topics: list[str], have: list[str]
    ) -> list[dict]: ...


class DeckReader(Protocol):
    def is_alive(self) -> bool: ...

    def deck_card_stats(self) -> list[dict]: ...

    def due_counts(self) -> list[dict]: ...

    def deck_fronts(self, deck: str, limit: int) -> list[str]: ...


class Clock(Protocol):
    def now(self) -> datetime: ...
