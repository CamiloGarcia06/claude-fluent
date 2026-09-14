"""Lo que las tarjetas necesitan de fuera: la colección (leer y escribir con
snapshot) y el modelo (proponer). Los cumplen los adaptadores de
infrastructure/ y los fakes de los tests."""

from pathlib import Path
from typing import Protocol

from fluent.shared.types import Review


class CardStore(Protocol):
    """La colección de Anki vista desde las tarjetas. Toda escritura deja su
    registro (snapshot o registro de creación): es la regla de snapshot.py."""

    def is_alive(self) -> bool: ...

    # lecturas
    def reviews_since(self, timestamp_ms: int) -> list[Review]: ...

    def due_counts(self) -> list[dict]: ...

    def deck_card_stats(self) -> list[dict]: ...

    def card_summaries(self, card_ids: list[int]) -> dict[int, dict]: ...

    def deck_fronts(self, deck: str, limit: int) -> list[str]: ...

    def note_info(self, note_id: int) -> dict:
        """Lanza NoteNotFound si la nota no existe."""
        ...

    def note_fields(self, note: dict) -> dict[str, str]: ...

    def notes_alive(self, note_ids: list[int]) -> int:
        """Cuántas de esas notas existen de verdad en la colección."""
        ...

    # escrituras (siempre con registro)
    def ensure_model(
        self, name: str, fields: list[str], templates: list[dict], css: str
    ) -> Path | None: ...

    def add_notes(self, deck: str, notes: list[dict]) -> tuple[list[int], Path, list[dict]]: ...

    def update_note_fields(self, note_id: int, fields: dict[str, str]) -> Path: ...


class Proposer(Protocol):
    """El modelo. Propone; nunca escribe. Lanza ModelFailed si falla."""

    def propose_terms(
        self, stuck: list[dict], catalog: dict, focus: dict | None, topic: str, have: list[str]
    ) -> dict: ...

    def propose_cards(self, term: str, catalog: dict, focus: dict | None) -> dict: ...

    def propose_repair(self, note: dict) -> dict: ...
