"""Adaptador del puerto CardStore sobre los módulos planos anki.py y snapshot.py.

Delegar y no reescribir: snapshot.py sigue siendo el único camino de escritura
(y el que guarda la regla "sin snapshot no se escribe")."""

from pathlib import Path

from fluent import anki, snapshot
from fluent.cards.domain.errors import NoteNotFound
from fluent.collection.domain.review import Review


class AnkiCardStore:
    def is_alive(self) -> bool:
        return anki.is_alive()

    def reviews_since(self, timestamp_ms: int) -> list[Review]:
        return anki.reviews_since(timestamp_ms)

    def due_counts(self) -> list[dict]:
        return anki.due_counts()

    def deck_card_stats(self) -> list[dict]:
        return anki.deck_card_stats()

    def card_summaries(self, card_ids: list[int]) -> dict[int, dict]:
        return anki.card_summaries(card_ids)

    def deck_fronts(self, deck: str, limit: int) -> list[str]:
        return anki.deck_fronts(deck, limit=limit)

    def note_info(self, note_id: int) -> dict:
        try:
            return anki.note_info(note_id)
        except KeyError as e:
            raise NoteNotFound(str(e)) from e

    def note_fields(self, note: dict) -> dict[str, str]:
        return anki.note_fields(note)

    def notes_alive(self, note_ids: list[int]) -> int:
        return len([n for n in anki.call("notesInfo", notes=note_ids) if n])

    def ensure_model(
        self, name: str, fields: list[str], templates: list[dict], css: str
    ) -> Path | None:
        return snapshot.ensure_model(name, fields, templates, css)

    def add_notes(self, deck: str, notes: list[dict]) -> tuple[list[int], Path, list[dict]]:
        return snapshot.add_notes(deck, notes)

    def update_note_fields(self, note_id: int, fields: dict[str, str]) -> Path:
        return snapshot.update_note_fields(note_id, fields)
