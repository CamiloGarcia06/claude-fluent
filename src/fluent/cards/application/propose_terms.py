"""Caso de uso: qué vale la pena estudiar. Propone; no escribe nada."""

from fluent.cards.domain.decks import decks_at, focus_for
from fluent.cards.domain.errors import AnkiNotRunning
from fluent.cards.domain.ports import CardStore, Proposer
from fluent.collection.domain import analysis

# How many stuck cards the model is shown when asked what to study next. It
# needs the shape of the problem, not the whole list.
STUCK_FOR_PROMPT = 10

# How many existing cards of a level the model is shown before proposing more
# for it. Enough to see what is there, not so many that the prompt is a deck.
FRONTS_FOR_PROMPT = 60


class ProposeTerms:
    def __init__(self, store: CardStore, proposer: Proposer) -> None:
        self._store = store
        self._proposer = proposer

    def __call__(
        self, window_start_ms: int, skill: str = "", level: str = "", topic: str = ""
    ) -> dict:
        if not self._store.is_alive():
            raise AnkiNotRunning()
        focus = focus_for(skill, level)
        catalog = analysis.catalog(self._store.deck_card_stats(), self._store.due_counts())

        # Lo que ese nivel ya tiene, para que "enriquecer" no proponga lo que ya
        # estudiás. Sólo con foco: sin él la lista no cabría en el prompt.
        have: list[str] = []
        if focus:
            for deck in decks_at(catalog, focus):
                have += self._store.deck_fronts(deck, limit=FRONTS_FOR_PROMPT)

        return self._proposer.propose_terms(
            self._stuck_with_text(window_start_ms), catalog, focus, topic=topic, have=have
        )

    def _stuck_with_text(self, window_start_ms: int) -> list[dict]:
        """El ranking de atascos con el frente de cada tarjeta: el modelo tiene
        que leer las tarjetas, no sus ids."""
        reviews = analysis.english_only(self._store.reviews_since(window_start_ms))
        cards = analysis.struggling(reviews, limit=STUCK_FOR_PROMPT)
        details = self._store.card_summaries([c["card_id"] for c in cards])
        for card in cards:
            card["front"] = details.get(card["card_id"], {}).get("front", "")
        return cards
