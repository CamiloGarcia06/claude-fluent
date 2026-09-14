"""Lo que el análisis de la colección necesita de fuera. Lo cumple el cliente
de AnkiConnect (infrastructure/anki_reader.py) y los fakes de los tests."""

from typing import Protocol

from .review import Review


class CollectionReader(Protocol):
    def is_alive(self) -> bool: ...

    def reviews_since(self, timestamp_ms: int) -> list[Review]: ...

    def due_counts(self) -> list[dict]: ...

    def deck_card_stats(self) -> list[dict]: ...

    def card_summaries(self, card_ids: list[int]) -> dict[int, dict]:
        """Texto de la pregunta y nota dueña de cada tarjeta."""
        ...
