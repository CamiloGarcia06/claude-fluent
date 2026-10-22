"""Caso de uso: pedirle al modelo una tanda de ejercicios y guardar los que
sirven. Practicar los ejercicios cerrados no gasta tokens; rellenar el banco sí.

Lo que devuelve el modelo es no confiable. Cada ejercicio pasa por las
entidades, y uno que no se puede resolver se cuenta como rechazado en vez de
guardarse."""

from fluent.toefl.domain.catalog import DISCUSSION, EMAIL, KINDS, SENTENCE, WORDS, keys
from fluent.toefl.domain.errors import NothingGenerated, UnknownKind, UnknownPattern
from fluent.toefl.domain.factory import BUILD_ERRORS, build_item
from fluent.toefl.domain.ports import ItemBank, ItemGenerator

# Una llamada de unos 25 s por tanda. Ocho frases son una sesión corta; tres
# párrafos son treinta huecos; tres enunciados de writing son media hora.
BATCH = {SENTENCE: 8, WORDS: 3, EMAIL: 3, DISCUSSION: 3}


class RefillBank:
    def __init__(self, bank: ItemBank, generator: ItemGenerator) -> None:
        self._bank = bank
        self._generator = generator

    def __call__(self, kind, focus=None) -> dict:
        if kind not in KINDS:
            raise UnknownKind()
        focus = focus or None
        if focus is not None and focus not in keys(kind):
            raise UnknownPattern()

        built, rejected = [], 0
        for raw in self._generator.generate(kind, BATCH[kind], focus):
            try:
                built.append(build_item(kind, raw))
            except BUILD_ERRORS:
                rejected += 1
        if not built:
            raise NothingGenerated()
        added = self._bank.add(kind, built)
        return {"added": added, "rejected": rejected, "duplicates": len(built) - added}
