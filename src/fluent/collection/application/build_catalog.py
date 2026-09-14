"""Caso de uso: el catálogo de mazos, skill → nivel → mazos, leído del nombre."""

from fluent.collection.domain import analysis
from fluent.collection.domain.errors import AnkiNotRunning
from fluent.collection.domain.ports import CollectionReader


class BuildCatalog:
    def __init__(self, reader: CollectionReader) -> None:
        self._reader = reader

    def __call__(self) -> dict:
        if not self._reader.is_alive():
            raise AnkiNotRunning()
        return analysis.catalog(self._reader.deck_card_stats(), self._reader.due_counts())
