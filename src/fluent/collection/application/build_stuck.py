"""Caso de uso: la lista entera de atascos, con severidad y lo que cuestan."""

from fluent.collection.domain import analysis
from fluent.collection.domain.errors import AnkiNotRunning
from fluent.collection.domain.ports import CollectionReader


class BuildStuck:
    def __init__(self, reader: CollectionReader) -> None:
        self._reader = reader

    def __call__(self, window_start_ms: int, limit: int) -> dict:
        if not self._reader.is_alive():
            raise AnkiNotRunning()
        reviews = analysis.english_only(self._reader.reviews_since(window_start_ms))
        cards = analysis.struggling(reviews, limit=limit)

        details = self._reader.card_summaries([c["card_id"] for c in cards])
        for card in cards:
            found = details.get(card["card_id"], {})
            card["front"] = found.get("front", "")
            card["note_id"] = found.get("note_id")
            card["severity"] = analysis.severity(card)

        total_cards = sum(
            d["total"] for d in self._reader.deck_card_stats() if analysis.in_scope(d["deck"])
        )
        total_seconds = sum(r.duration_ms for r in reviews) / 1000.0
        return {
            "cards": cards,
            "impact": analysis.impact(cards, total_cards, total_seconds),
            "window": {"days": analysis.CALENDAR_DAYS, "reviews": len(reviews)},
        }
