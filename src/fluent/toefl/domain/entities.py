"""Los dos ejercicios del banco y el intento que deja cada respuesta.

Todo lo que llega del modelo pasa por acá antes de guardarse: un ejercicio que
no se puede resolver (piezas vacías, un hueco que no está en el párrafo) se
rechaza en `__post_init__` o en `build_words_item`, y el banco nunca lo ve.
"""

import hashlib
import re
from dataclasses import dataclass

from fluent.toefl.domain.catalog import SENTENCE, SENTENCE_PATTERNS, WORDS, classify_word

MIN_CHUNKS, MAX_CHUNKS = 3, 8
# Diez, como el examen. El mínimo y el máximo son para leer bancos viejos o
# editados a mano, no para generar.
GAPS = 10
MIN_GAPS, MAX_GAPS = 5, 12

_SENTENCE_KEYS = frozenset(p.key for p in SENTENCE_PATTERNS)
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([?.!,])")
_SENTENCE_END = re.compile(r"[.!?](?=\s)")
_WORD = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)?|\d+")


def _clean(value) -> str:
    return " ".join(str(value or "").split())


def _digest(*parts: str) -> str:
    """El id sale del contenido: el mismo ejercicio generado dos veces es uno solo."""
    return hashlib.sha1("\x1f".join(parts).encode("utf-8")).hexdigest()[:12]


def _same(a: str, b: str) -> bool:
    return _clean(a).lower() == _clean(b).lower()


@dataclass(frozen=True)
class SentenceItem:
    """Build a Sentence: ordenar las piezas entre `before` y `after`.

    `answer` son las piezas en el orden correcto. Se compara la secuencia de
    textos, no de posiciones, así que dos piezas iguales ("the" y "the") son
    intercambiables sin que el ejercicio lo sepa."""

    id: str
    pattern: str
    context: str
    before: str
    after: str
    answer: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.pattern not in _SENTENCE_KEYS:
            raise ValueError(f"patrón desconocido: {self.pattern!r}")
        if not self.context:
            raise ValueError("sin contexto")
        if not MIN_CHUNKS <= len(self.answer) <= MAX_CHUNKS:
            raise ValueError(f"{len(self.answer)} piezas")
        if any(not chunk for chunk in self.answer):
            raise ValueError("pieza vacía")

    @property
    def kind(self) -> str:
        return SENTENCE

    def sentence(self) -> str:
        text = " ".join(part for part in (self.before, *self.answer, self.after) if part)
        return _SPACE_BEFORE_PUNCT.sub(r"\1", text)

    def shuffled(self) -> list[str]:
        """Las piezas como se muestran. Orden alfabético, que es fijo y casi nunca
        el bueno; si coincide, se rota una posición. Sin azar: no hace falta un
        puerto para desordenar seis palabras."""
        chunks = sorted(self.answer, key=str.lower)
        if chunks == list(self.answer):
            chunks = chunks[1:] + chunks[:1]
        return chunks

    def public(self) -> dict:
        """Lo que viaja a la pantalla: sin `answer`."""
        return {
            "id": self.id,
            "kind": SENTENCE,
            "pattern": self.pattern,
            "context": self.context,
            "before": self.before,
            "after": self.after,
            "chunks": self.shuffled(),
        }

    def is_correct(self, chunks: list[str]) -> bool:
        return len(chunks) == len(self.answer) and all(
            _same(given, right) for given, right in zip(chunks, self.answer, strict=True)
        )


def build_sentence_item(pattern, context, before, after, chunks) -> SentenceItem:
    answer = tuple(_clean(c) for c in (chunks or []))
    before, after, context = _clean(before), _clean(after), _clean(context)
    return SentenceItem(
        id=_digest(SENTENCE, before, *answer, after),
        pattern=str(pattern or ""),
        context=context,
        before=before,
        after=after,
        answer=answer,
    )


@dataclass(frozen=True)
class Gap:
    word: str
    shown: str
    missing: str
    pattern: str


@dataclass(frozen=True)
class WordsItem:
    """Complete the Words: un párrafo con la segunda mitad de algunas palabras
    borrada. `parts` es el texto entre huecos, uno más que `gaps`."""

    id: str
    parts: tuple[str, ...]
    gaps: tuple[Gap, ...]

    def __post_init__(self) -> None:
        if not MIN_GAPS <= len(self.gaps) <= MAX_GAPS:
            raise ValueError(f"{len(self.gaps)} huecos")
        if len(self.parts) != len(self.gaps) + 1:
            raise ValueError("partes y huecos no cuadran")

    @property
    def kind(self) -> str:
        return WORDS

    def public(self) -> dict:
        """Sin las letras que faltan: de cada hueco viaja lo visible y cuántas son."""
        return {
            "id": self.id,
            "kind": WORDS,
            "parts": list(self.parts),
            "gaps": [{"shown": g.shown, "length": len(g.missing)} for g in self.gaps],
        }

    def check(self, answers: list[str]) -> list[bool]:
        """Un resultado por hueco. Lo que falta se cuenta como fallo."""
        padded = list(answers) + [""] * (len(self.gaps) - len(answers))
        return [_same(given, gap.missing) for given, gap in zip(padded, self.gaps, strict=False)]


def split_word(word: str) -> tuple[str, str]:
    """Lo que el examen muestra y lo que borra: la mitad de abajo queda a la vista.

    Es la regla de las diez respuestas del Practice Test 1: mi|ght, th|at,
    peo|ple, How|ever, i|s, dan|cing."""
    half = len(word) // 2
    return word[:half], word[half:]


def build_words_item(paragraph) -> WordsItem:
    """Los huecos los elige esta regla, no el modelo, porque es la del examen:
    la primera oración queda entera y desde la segunda se corta una palabra de
    cada dos (We **mi**ght think **th**at prehistoric **peo**ple…) hasta
    juntar `GAPS`. Una palabra que no se puede cortar (una letra, una cifra, un
    apóstrofo) pasa el corte a la siguiente.

    Un párrafo de una sola oración o demasiado corto no sirve: ValueError, y el
    banco lo descarta."""
    text = _clean(paragraph)
    first_end = _SENTENCE_END.search(text)
    if not first_end:
        raise ValueError("una sola oración")
    tokens = list(_WORD.finditer(text, first_end.end()))
    chosen: list[re.Match[str]] = []
    index = 1
    while len(chosen) < GAPS and index < len(tokens):
        word = tokens[index].group()
        if len(word) >= 2 and word.isalpha():
            chosen.append(tokens[index])
            index += 2
        else:
            index += 1
    if len(chosen) < GAPS:
        raise ValueError(f"párrafo corto: {len(chosen)} huecos")

    parts: list[str] = []
    gaps: list[Gap] = []
    cursor = 0
    for found in chosen:
        word = found.group()
        parts.append(text[cursor : found.start()])
        shown, missing = split_word(word)
        gaps.append(Gap(word, shown, missing, classify_word(word)))
        cursor = found.end()
    parts.append(text[cursor:])
    return WordsItem(id=_digest(WORDS, text), parts=tuple(parts), gaps=tuple(gaps))


@dataclass(frozen=True)
class Attempt:
    """Una respuesta a un patrón. Un párrafo de Complete the Words deja uno por
    hueco: cada hueco es un patrón distinto, y promediarlos escondería cuál falla."""

    kind: str
    item_id: str
    pattern: str
    correct: bool
    at: str
