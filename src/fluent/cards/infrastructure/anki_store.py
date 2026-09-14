"""Adaptador del puerto CardStore: la colección (cliente inyectado) más el camino
de escritura con registro (snapshots inyectados). No importa la funcionalidad
`anki`: main.py le pasa los objetos, y aquí solo se declara lo que necesita."""

from pathlib import Path
from typing import Protocol

from fluent.cards.domain.errors import NoteNotFound
from fluent.shared.types import Review


class AnkiApi(Protocol):
    def is_alive(self) -> bool: ...
    def call(self, action: str, **params) -> object: ...
    def reviews_since(self, timestamp_ms: int) -> list[Review]: ...
    def due_counts(self) -> list[dict]: ...
    def deck_card_stats(self) -> list[dict]: ...
    def card_summaries(self, card_ids: list[int]) -> dict[int, dict]: ...
    def deck_fronts(self, deck: str, limit: int = 60) -> list[str]: ...
    def note_info(self, note_id: int) -> dict: ...
    def note_fields(self, note: dict) -> dict[str, str]: ...
    def notes_alive(self, note_ids: list[int]) -> int: ...


class SnapshotApi(Protocol):
    def ensure_model(
        self, name: str, fields: list[str], templates: list[dict], css: str
    ) -> Path | None: ...
    def add_notes(self, deck: str, notes: list[dict]) -> tuple[list[int], Path, list[dict]]: ...
    def update_note_fields(self, note_id: int, fields: dict[str, str]) -> Path: ...


class AnkiCardStore:
    def __init__(self, client: AnkiApi, snapshots: SnapshotApi) -> None:
        self._anki = client
        self._snapshots = snapshots

    def is_alive(self) -> bool:
        return self._anki.is_alive()

    def reviews_since(self, timestamp_ms: int) -> list[Review]:
        return self._anki.reviews_since(timestamp_ms)

    def due_counts(self) -> list[dict]:
        return self._anki.due_counts()

    def deck_card_stats(self) -> list[dict]:
        return self._anki.deck_card_stats()

    def card_summaries(self, card_ids: list[int]) -> dict[int, dict]:
        return self._anki.card_summaries(card_ids)

    def deck_fronts(self, deck: str, limit: int) -> list[str]:
        return self._anki.deck_fronts(deck, limit=limit)

    def note_info(self, note_id: int) -> dict:
        try:
            return self._anki.note_info(note_id)
        except KeyError as e:
            raise NoteNotFound(str(e)) from e

    def note_fields(self, note: dict) -> dict[str, str]:
        return self._anki.note_fields(note)

    def notes_alive(self, note_ids: list[int]) -> int:
        return self._anki.notes_alive(note_ids)

    def ensure_model(
        self, name: str, fields: list[str], templates: list[dict], css: str
    ) -> Path | None:
        return self._snapshots.ensure_model(name, fields, templates, css)

    def add_notes(self, deck: str, notes: list[dict]) -> tuple[list[int], Path, list[dict]]:
        return self._snapshots.add_notes(deck, notes)

    def update_note_fields(self, note_id: int, fields: dict[str, str]) -> Path:
        return self._snapshots.update_note_fields(note_id, fields)
