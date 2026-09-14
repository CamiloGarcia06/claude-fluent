"""Caso de uso: pedirle al modelo una versión mejor de una nota. No escribe."""

from fluent.cards.domain.errors import AnkiNotRunning
from fluent.cards.domain.ports import CardStore, Proposer


class RepairNote:
    def __init__(self, store: CardStore, proposer: Proposer) -> None:
        self._store = store
        self._proposer = proposer

    def __call__(self, note_id: int) -> dict:
        if not self._store.is_alive():
            raise AnkiNotRunning()
        note = self._store.note_info(note_id)
        return self._proposer.propose_repair(note)
