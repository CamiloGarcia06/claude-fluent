"""Adaptador del puerto CollectionReader sobre el cliente plano de AnkiConnect.

Delegar y no reescribir: `fluent/anki.py` sigue siendo el único sitio que habla
con Anki (y el que guarda la regla de "no escribir sin snapshot"). Cuando ese
módulo se mueva aquí, este adaptador desaparece."""

from fluent import anki
from fluent.collection.domain.review import Review


class AnkiReader:
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
