"""Caso de uso: el conteo entero de patrones. `unmatched` no es un contador: es
lo que le falta al catálogo."""

from fluent.writing.domain.ports import PatternStore


class GetPatterns:
    def __init__(self, patterns: PatternStore) -> None:
        self._patterns = patterns

    def __call__(self) -> dict:
        stored = self._patterns.read()
        return {
            "patterns": self._patterns.listing(stored),
            "unmatched": stored["unmatched"],
            "threshold": self._patterns.threshold,
        }
