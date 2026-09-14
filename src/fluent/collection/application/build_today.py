"""Caso de uso: todo lo que la pantalla Hoy necesita, en un objeto."""

from datetime import date

from fluent.collection.domain import analysis
from fluent.collection.domain.errors import AnkiNotRunning
from fluent.collection.domain.ports import CollectionReader


class BuildToday:
    def __init__(self, reader: CollectionReader) -> None:
        self._reader = reader

    def __call__(self, today: date, window_start_ms: int, daily_goal: int) -> dict:
        if not self._reader.is_alive():
            raise AnkiNotRunning()
        reviews = self._reader.reviews_since(window_start_ms)
        deck_counts = self._reader.due_counts()
        summary = analysis.summary(reviews, deck_counts, today)
        summary["goal"] = daily_goal

        # El análisis es puro: el texto de la tarjeta se busca aquí y se mezcla.
        details = self._reader.card_summaries([c["card_id"] for c in summary["failing"]])
        for card in summary["failing"]:
            found = details.get(card["card_id"], {})
            card["front"] = found.get("front", "")
            card["note_id"] = found.get("note_id")
        return summary
