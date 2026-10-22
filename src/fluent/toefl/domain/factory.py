"""Del dict crudo del modelo al ejercicio del banco, según el tipo. Lo que no
tiene la forma esperada lanza ValueError, TypeError o AttributeError, y quien
llama lo cuenta como rechazado."""

from fluent.toefl.domain.catalog import DISCUSSION, EMAIL, SENTENCE, WORDS
from fluent.toefl.domain.entities import build_sentence_item, build_words_item
from fluent.toefl.domain.writing import build_discussion_prompt, build_email_prompt

BUILD_ERRORS = (ValueError, TypeError, AttributeError)


def build_item(kind: str, raw: dict):
    if kind == SENTENCE:
        return build_sentence_item(
            raw.get("pattern"),
            raw.get("context"),
            raw.get("before"),
            raw.get("after"),
            raw.get("chunks"),
        )
    if kind == WORDS:
        return build_words_item(raw.get("text"))
    if kind == EMAIL:
        return build_email_prompt(
            raw.get("situation"), raw.get("to"), raw.get("subject"), raw.get("bullets")
        )
    if kind == DISCUSSION:
        return build_discussion_prompt(raw.get("course"), raw.get("professor"), raw.get("posts"))
    raise ValueError(f"tipo desconocido: {kind!r}")
