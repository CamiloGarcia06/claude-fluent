"""Caso de uso: crear las tarjetas aprobadas. La única escritura de la generación."""

from fluent.cards.domain.decks import clean_deck_name
from fluent.cards.domain.errors import (
    AnkiNotRunning,
    CardIncomplete,
    MalformedCard,
    NoCards,
    TooManyCards,
)
from fluent.cards.domain.model import MODEL_CSS, MODEL_FIELDS, MODEL_NAME, MODEL_TEMPLATES
from fluent.cards.domain.ports import CardStore
from fluent.cards.domain.text import to_field_html

# A ceiling on one write. Ten terms of three candidates is thirty cards, and
# anything far above that is a bug in the client rather than a real approval.
MAX_CARDS_PER_WRITE = 60


class WriteNotes:
    def __init__(self, store: CardStore) -> None:
        self._store = store

    def __call__(self, cards) -> dict:
        if not self._store.is_alive():
            raise AnkiNotRunning()
        if not isinstance(cards, list) or not cards:
            raise NoCards()
        if len(cards) > MAX_CARDS_PER_WRITE:
            raise TooManyCards(f"more than {MAX_CARDS_PER_WRITE} cards in one write")

        by_deck: dict[str, list[dict]] = {}
        for card in cards:
            if not isinstance(card, dict):
                raise MalformedCard()
            front = str(card.get("front", "")).strip()
            back = str(card.get("back", "")).strip()
            if not front or not back:
                raise CardIncomplete()
            deck = clean_deck_name(card.get("deck"))
            by_deck.setdefault(deck, []).append(
                {
                    "model": MODEL_NAME,
                    "tags": ["claude-fluent"],
                    # The client sends plain text; Anki stores HTML.
                    "fields": {
                        "Front": to_field_html(front),
                        "Back": to_field_html(back),
                        "Ejemplo": to_field_html(str(card.get("example", "")).strip()),
                    },
                }
            )

        model_record = self._store.ensure_model(
            MODEL_NAME, MODEL_FIELDS, MODEL_TEMPLATES, MODEL_CSS
        )

        written = []
        for deck, notes in by_deck.items():
            ids, record, refused = self._store.add_notes(deck, notes)
            # Read the result back from Anki rather than trusting the response
            # of the call that wrote it.
            verified = self._store.notes_alive(ids) if ids else 0
            written.append(
                {
                    "deck": deck,
                    "asked": len(notes),
                    "created": len(ids),
                    "verified": verified,
                    "refused": refused,
                    "record": str(record),
                }
            )

        return {
            "ok": True,
            "added": sum(w["verified"] for w in written),
            "refused": [r for w in written for r in w["refused"]],
            "decks": written,
            "model_created": str(model_record) if model_record else None,
        }
