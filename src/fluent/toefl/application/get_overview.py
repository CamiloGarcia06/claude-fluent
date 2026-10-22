"""Caso de uso: la cabecera de la pantalla. Cuántos ejercicios quedan sin hacer
y, por patrón, cómo vienen los últimos intentos."""

from dataclasses import asdict

from fluent.toefl.domain.advice import stats, weakest
from fluent.toefl.domain.catalog import SENTENCE, WORDS
from fluent.toefl.domain.ports import AttemptLog, ItemBank


class GetOverview:
    def __init__(self, bank: ItemBank, log: AttemptLog) -> None:
        self._bank = bank
        self._log = log

    def __call__(self) -> dict:
        attempts = self._log.recent()
        done = {a.item_id for a in attempts}
        out = {}
        for kind, ids in (
            (SENTENCE, [i.id for i in self._bank.sentences()]),
            (WORDS, [i.id for i in self._bank.words()]),
        ):
            rows = stats(kind, attempts)
            weak = weakest(rows)
            out[kind] = {
                "total": len(ids),
                "fresh": sum(1 for i in ids if i not in done),
                "focus": weak.key if weak else None,
                "patterns": [{**asdict(r), "enough": r.enough} for r in rows],
            }
        return out
