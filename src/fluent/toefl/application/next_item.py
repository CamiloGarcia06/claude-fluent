"""Caso de uso: el próximo ejercicio sin hacer, empezando por el patrón que más
fallás. Es la mitad del consejo que se ejecuta sola: no hace falta leer el
diagnóstico para practicar lo que dice."""

from fluent.toefl.domain.advice import stats, weakest
from fluent.toefl.domain.catalog import KINDS, SENTENCE
from fluent.toefl.domain.errors import BankEmpty, UnknownKind
from fluent.toefl.domain.ports import AttemptLog, ItemBank


class NextItem:
    def __init__(self, bank: ItemBank, log: AttemptLog) -> None:
        self._bank = bank
        self._log = log

    def __call__(self, kind) -> dict:
        if kind not in KINDS:
            raise UnknownKind()
        attempts = self._log.recent()
        done = {a.item_id for a in attempts}
        weak = weakest(stats(kind, attempts))
        focus = weak.key if weak else None

        if kind == SENTENCE:
            fresh_sentences = [i for i in self._bank.sentences() if i.id not in done]
            if not fresh_sentences:
                raise BankEmpty()
            on_focus = [i for i in fresh_sentences if i.pattern == focus]
            chosen = (on_focus or fresh_sentences)[0]
            return {"item": chosen.public(), "focus": focus, "fresh": len(fresh_sentences)}

        fresh_words = [i for i in self._bank.words() if i.id not in done]
        if not fresh_words:
            raise BankEmpty()
        # El párrafo con más huecos del patrón débil; a igualdad, el más viejo.
        chosen = max(fresh_words, key=lambda i: sum(1 for g in i.gaps if g.pattern == focus))
        return {"item": chosen.public(), "focus": focus, "fresh": len(fresh_words)}
