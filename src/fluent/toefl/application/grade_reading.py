"""Caso de uso: corregir las respuestas de una lectura y dejarlas en el log. Sin
modelo: la respuesta, la cita y la explicación ya están en el banco.

Cada pregunta deja un intento con su tipo, así el consejo dice qué tipo de
pregunta fallás. La lectura entera queda en las entregas con su tiempo: en
reading el reloj es la mitad del problema, y la cabecera lo muestra."""

from fluent.toefl.domain.catalog import READING_KINDS, pattern, tip_card
from fluent.toefl.domain.entities import Attempt
from fluent.toefl.domain.errors import ItemNotFound, UnknownKind
from fluent.toefl.domain.ports import AttemptLog, Clock, ItemBank, SubmissionLog
from fluent.toefl.domain.reading import ReadingItem

# Una lectura de más de media hora es una pestaña olvidada, no un tiempo.
MAX_SECONDS = 1800


def _seconds(value) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return int(value) if 0 < value <= MAX_SECONDS else None


class GradeReading:
    def __init__(
        self, bank: ItemBank, log: AttemptLog, submissions: SubmissionLog, clock: Clock
    ) -> None:
        self._bank = bank
        self._log = log
        self._submissions = submissions
        self._clock = clock

    def __call__(self, kind, item_id, answers, seconds=None) -> dict:
        if kind not in READING_KINDS:
            raise UnknownKind()
        item = next((i for i in self._bank.items(kind) if i.id == item_id), None)
        if not isinstance(item, ReadingItem):
            raise ItemNotFound()
        at = self._clock.now().isoformat(timespec="seconds")
        chosen = list(answers) if isinstance(answers, list) else []
        chosen += [None] * (len(item.questions) - len(chosen))
        results = item.check(chosen)
        seconds = _seconds(seconds)

        self._log.append(
            [
                Attempt(kind, item.id, q.pattern, ok, at)
                for q, ok in zip(item.questions, results, strict=True)
            ]
        )
        self._submissions.append(
            {
                "kind": kind,
                "item_id": item.id,
                "at": at,
                "seconds": seconds,
                "target_seconds": item.target_seconds,
                "score": sum(results),
                "total": len(results),
            }
        )
        failed = list(
            dict.fromkeys(
                q.pattern for q, ok in zip(item.questions, results, strict=True) if not ok
            )
        )
        rows = []
        for q, ok, pick in zip(item.questions, results, chosen[: len(results)], strict=True):
            info = pattern(q.pattern)
            rows.append(
                {
                    "correct": ok,
                    "chosen": pick
                    if isinstance(pick, int) and not isinstance(pick, bool)
                    else None,
                    "answer": q.answer,
                    "pattern": q.pattern,
                    "label": info.label if info else q.pattern,
                    "evidence": q.evidence,
                    "why": q.why,
                }
            )
        return {
            "score": sum(results),
            "total": len(results),
            "seconds": seconds,
            "target_seconds": item.target_seconds,
            "words": item.words,
            "results": rows,
            "tips": [tip_card(key) for key in failed],
        }
