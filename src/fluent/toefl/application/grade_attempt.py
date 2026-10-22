"""Caso de uso: corregir una respuesta y dejarla en el log. Sin modelo: la
respuesta está en el banco y se compara texto contra texto."""

from fluent.toefl.domain.catalog import KINDS, SENTENCE, pattern
from fluent.toefl.domain.entities import Attempt
from fluent.toefl.domain.errors import ItemNotFound, UnknownKind
from fluent.toefl.domain.ports import AttemptLog, Clock, ItemBank


def _tip(key: str) -> dict:
    info = pattern(key)
    assert info is not None  # los ejercicios del banco solo llevan patrones del catálogo
    return {"key": key, "label": info.label, "tip": info.tip, "example": info.example}


def _texts(value) -> list[str]:
    return [str(v or "") for v in value] if isinstance(value, list) else []


class GradeAttempt:
    def __init__(self, bank: ItemBank, log: AttemptLog, clock: Clock) -> None:
        self._bank = bank
        self._log = log
        self._clock = clock

    def __call__(self, kind, item_id, answer) -> dict:
        if kind not in KINDS:
            raise UnknownKind()
        at = self._clock.now().isoformat(timespec="seconds")

        if kind == SENTENCE:
            sentence = next((i for i in self._bank.sentences() if i.id == item_id), None)
            if sentence is None:
                raise ItemNotFound()
            correct = sentence.is_correct(_texts(answer))
            self._log.append([Attempt(kind, sentence.id, sentence.pattern, correct, at)])
            return {
                "correct": correct,
                "sentence": sentence.sentence(),
                "answer": list(sentence.answer),
                "tip": _tip(sentence.pattern),
            }

        words = next((i for i in self._bank.words() if i.id == item_id), None)
        if words is None:
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
            "tips": [_tip(key) for key in failed],
        }
