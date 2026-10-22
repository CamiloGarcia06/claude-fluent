"""Caso de uso: el próximo ejercicio sin hacer, empezando por el patrón que más
fallás. Es la mitad del consejo que se ejecuta sola: no hace falta leer el
diagnóstico para practicar lo que dice."""

from fluent.toefl.domain.advice import stats, weakest
from fluent.toefl.domain.catalog import KINDS
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

        fresh = [i for i in self._bank.items(kind) if i.id not in done]
        if not fresh:
            raise BankEmpty()
        # El que más practica el patrón débil; a igualdad, el más viejo. Un
        # enunciado de writing pesa lo mismo que cualquier otro: sale el más viejo.
        chosen = max(fresh, key=lambda i: i.weight(focus))
        return {"item": chosen.public(), "focus": focus, "fresh": len(fresh)}
