"""Caso de uso: las tarjetas candidatas de UN término y el mazo que le toca."""

from fluent.cards.domain.decks import focus_for
from fluent.cards.domain.errors import AnkiNotRunning, NoTerm, TermTooLong
from fluent.cards.domain.ports import CardStore, Proposer
from fluent.collection.domain import analysis

MAX_TERM_CHARS = 80


class ProposeCards:
    def __init__(self, store: CardStore, proposer: Proposer) -> None:
        self._store = store
        self._proposer = proposer

    def __call__(self, term: str, skill: str = "", level: str = "") -> dict:
        if not self._store.is_alive():
            raise AnkiNotRunning()
        term = str(term or "").strip()
        if not term:
            raise NoTerm()
        if len(term) > MAX_TERM_CHARS:
            raise TermTooLong()
        catalog = analysis.catalog(self._store.deck_card_stats(), self._store.due_counts())
        return self._proposer.propose_cards(term, catalog, focus_for(skill, level))
