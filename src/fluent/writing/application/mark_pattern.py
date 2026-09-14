"""Caso de uso: `carded` cuando ya escribiste la tarjeta, `reset` cuando no te
importa, `uncard` para deshacer. Sin esto la fila reclama la misma tarjeta
para siempre."""

from fluent.writing.domain.errors import BadPatternAction
from fluent.writing.domain.ports import PatternStore


class MarkPattern:
    def __init__(self, patterns: PatternStore) -> None:
        self._patterns = patterns

    def __call__(self, key, action) -> dict:
        try:
            stored = self._patterns.mark(
                self._patterns.read(), str(key or ""), str(action or ""), self._patterns.stamp()
            )
        except ValueError as e:
            raise BadPatternAction(str(e)) from e
        self._patterns.write(stored)
        return {"patterns": self._patterns.listing(stored), "threshold": self._patterns.threshold}
