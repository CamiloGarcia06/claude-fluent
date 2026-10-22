"""Caso de uso: pedirle al modelo una tanda de ejercicios y guardar los que
sirven. Es la única llamada al modelo del entrenamiento: practicar no gasta
tokens, rellenar el banco sí.

Lo que devuelve el modelo es no confiable. Cada ejercicio pasa por las
entidades, y uno que no se puede resolver se cuenta como rechazado en vez de
guardarse."""

from fluent.toefl.domain.catalog import KINDS, SENTENCE, keys
from fluent.toefl.domain.entities import (
    SentenceItem,
    WordsItem,
    build_sentence_item,
    build_words_item,
)
from fluent.toefl.domain.errors import NothingGenerated, UnknownKind, UnknownPattern
from fluent.toefl.domain.ports import ItemBank, ItemGenerator

# Una llamada de 30-60 s por tanda. Ocho frases son una sesión corta; tres
# párrafos son treinta huecos.
SENTENCE_BATCH = 8
WORDS_BATCH = 3


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

        rejected = 0
        if kind == SENTENCE:
            sentences: list[SentenceItem] = []
            for raw in self._generator.sentences(SENTENCE_BATCH, focus):
                try:
                    sentences.append(
                        build_sentence_item(
                            raw.get("pattern"),
                            raw.get("context"),
                            raw.get("before"),
                            raw.get("after"),
                            raw.get("chunks"),
                        )
                    )
                except (ValueError, TypeError, AttributeError):
                    rejected += 1
            built = len(sentences)
            added = self._bank.add_sentences(sentences) if sentences else 0
        else:
            paragraphs: list[WordsItem] = []
            for raw in self._generator.paragraphs(WORDS_BATCH, focus):
                try:
                    paragraphs.append(build_words_item(raw.get("text")))
                except (ValueError, TypeError, AttributeError):
                    rejected += 1
            built = len(paragraphs)
            added = self._bank.add_words(paragraphs) if paragraphs else 0

        if not built:
            raise NothingGenerated()
        return {"added": added, "rejected": rejected, "duplicates": built - added}
