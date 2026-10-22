"""Caso de uso: corregir una respuesta de un ejercicio cerrado y dejarla en el
log. Sin modelo: la respuesta está en el banco y se compara texto contra texto.
Writing va por `submit_writing.py`."""

from fluent.toefl.domain.catalog import OBJECTIVE_KINDS, SENTENCE, tip_card
from fluent.toefl.domain.entities import Attempt, SentenceItem, WordsItem
from fluent.toefl.domain.errors import ItemNotFound, UnknownKind
from fluent.toefl.domain.ports import AttemptLog, Clock, ItemBank


def _texts(value) -> list[str]:
    return [str(v or "") for v in value] if isinstance(value, list) else []


class GradeAttempt:
    def __init__(self, bank: ItemBank, log: AttemptLog, clock: Clock) -> None:
        self._bank = bank
        self._log = log
        self._clock = clock

    def __call__(self, kind, item_id, answer) -> dict:
        if kind not in OBJECTIVE_KINDS:
            raise UnknownKind()
        at = self._clock.now().isoformat(timespec="seconds")

        item = next((i for i in self._bank.items(kind) if i.id == item_id), None)
        if kind == SENTENCE:
            sentence = item
            if not isinstance(sentence, SentenceItem):
                raise ItemNotFound()
            correct = sentence.is_correct(_texts(answer))
            self._log.append([Attempt(kind, sentence.id, sentence.pattern, correct, at)])
            return {
                "correct": correct,
                "sentence": sentence.sentence(),
                "answer": list(sentence.answer),
                "tip": tip_card(sentence.pattern),
            }

        words = item
        if not isinstance(words, WordsItem):
            raise ItemNotFound()
        results = words.check(_texts(answer))
        self._log.append(
            [
                Attempt(kind, words.id, g.pattern, ok, at)
                for g, ok in zip(words.gaps, results, strict=True)
            ]
        )
        failed = list(
            dict.fromkeys(g.pattern for g, ok in zip(words.gaps, results, strict=True) if not ok)
        )
        return {
            "score": sum(results),
            "total": len(results),
            "results": [
                {"correct": ok, "word": g.word, "missing": g.missing, "pattern": g.pattern}
                for g, ok in zip(words.gaps, results, strict=True)
            ],
            "tips": [tip_card(key) for key in failed],
        }
