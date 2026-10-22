"""Caso de uso: la cabecera de la pantalla. Cuántos ejercicios quedan sin hacer
y, por patrón, cómo vienen los últimos intentos. En writing, además, las notas
de las últimas entregas."""

from dataclasses import asdict

from fluent.toefl.domain.advice import stats, weakest
from fluent.toefl.domain.catalog import KINDS, WRITING_KINDS
from fluent.toefl.domain.ports import AttemptLog, ItemBank, SubmissionLog

# Las notas que se muestran. Son las últimas, no un promedio: un promedio de
# tres semanas no se mueve aunque hoy escribas mejor.
RECENT_SCORES = 5


class GetOverview:
    def __init__(self, bank: ItemBank, log: AttemptLog, submissions: SubmissionLog) -> None:
        self._bank = bank
        self._log = log
        self._submissions = submissions

    def __call__(self) -> dict:
        attempts = self._log.recent()
        done = {a.item_id for a in attempts}
        out = {}
        for kind in KINDS:
            ids = [i.id for i in self._bank.items(kind)]
            rows = stats(kind, attempts)
            weak = weakest(rows)
            out[kind] = {
                "total": len(ids),
                "fresh": sum(1 for i in ids if i not in done),
                "focus": weak.key if weak else None,
                "patterns": [{**asdict(r), "enough": r.enough} for r in rows],
            }
            if kind in WRITING_KINDS:
                out[kind]["recent"] = [
                    {"at": s.get("at"), "score": s.get("score"), "words": s.get("words")}
                    for s in self._submissions.recent(kind)[-RECENT_SCORES:]
                ]
        return out
