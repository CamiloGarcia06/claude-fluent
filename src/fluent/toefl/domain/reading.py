"""Read in Daily Life y Read an Academic Passage: un texto con preguntas de
opción múltiple, corregidas sin modelo.

**Cada pregunta trae la frase del texto que la responde, copiada tal cual.** Es
la parte que enseña: después de corregir, la pantalla la resalta en el texto, y
ver dónde estaba la respuesta es lo que entrena a encontrarla. También es la
mejor validación de lo que devuelve el modelo: una cita que no está en el texto
delata una pregunta inventada, y la pregunta se rechaza.

**Las opciones se barajan acá.** Los modelos ponen la correcta casi siempre en
la misma letra, y a la tercera lectura eso se aprende en vez del texto. La
posición sale del id, así que el mismo ejercicio se ve siempre igual.

**El tiempo objetivo es orientativo.** ETS no publica un tiempo por texto: se
calcula leyendo a 150 palabras por minuto, el ritmo que pide el examen a un
B1-B2, más treinta segundos por pregunta.
"""

import re
from dataclasses import dataclass

from fluent.toefl.domain.catalog import ACADEMIC, DAILY, READING_PATTERNS
from fluent.toefl.domain.entities import clean_text, content_id
from fluent.toefl.domain.writing import word_count

OPTIONS = 4
QUESTIONS = {DAILY: (2, 3), ACADEMIC: (4, 5)}
WORDS = {DAILY: (30, 220), ACADEMIC: (150, 350)}
READING_WPM = 150
SECONDS_PER_QUESTION = 30
MAX_PARAGRAPHS = 8

_KEYS = frozenset(p.key for p in READING_PATTERNS)
# "La B es falsa": las opciones se barajan al guardar, así que una explicación
# que nombra una letra apunta a otra opción. Se rechaza la pregunta.
_LETTER = re.compile(
    r"\b(?:[Ll]as? |[Oo]pci[oó]n(?:es)? |[Rr]espuesta )\(?[A-D]\)?(?![\w'’])|\([A-D]\)"
)


@dataclass(frozen=True)
class Question:
    pattern: str
    prompt: str
    options: tuple[str, ...]
    answer: int
    evidence: str
    why: str

    def __post_init__(self) -> None:
        if self.pattern not in _KEYS:
            raise ValueError(f"tipo de pregunta desconocido: {self.pattern!r}")
        if not self.prompt or not self.evidence or not self.why:
            raise ValueError("pregunta incompleta")
        if _LETTER.search(self.why):
            raise ValueError("la explicación nombra una letra")
        if len(self.options) != OPTIONS or not all(self.options):
            raise ValueError("hacen falta cuatro opciones")
        if len({o.lower() for o in self.options}) != OPTIONS:
            raise ValueError("opciones repetidas")
        if isinstance(self.answer, bool) or self.answer not in range(OPTIONS):
            raise ValueError("respuesta fuera de rango")


@dataclass(frozen=True)
class ReadingItem:
    id: str
    kind: str
    genre: str
    title: str
    paragraphs: tuple[str, ...]
    questions: tuple[Question, ...]

    def __post_init__(self) -> None:
        if self.kind not in QUESTIONS:
            raise ValueError(f"tipo de lectura desconocido: {self.kind!r}")
        if not self.paragraphs or len(self.paragraphs) > MAX_PARAGRAPHS:
            raise ValueError("párrafos fuera de rango")
        low, high = QUESTIONS[self.kind]
        if not low <= len(self.questions) <= high:
            raise ValueError("cantidad de preguntas fuera de rango")
        low, high = WORDS[self.kind]
        if not low <= self.words <= high:
            raise ValueError(f"{self.words} palabras: fuera de rango")
        for q in self.questions:
            if not any(q.evidence in p for p in self.paragraphs):
                raise ValueError(f"la cita no está en el texto: {q.evidence!r}")

    @property
    def words(self) -> int:
        return word_count(" ".join(self.paragraphs))

    @property
    def target_seconds(self) -> int:
        reading = self.words * 60 / READING_WPM
        return round(reading + SECONDS_PER_QUESTION * len(self.questions))

    def weight(self, focus: str | None) -> int:
        return sum(1 for q in self.questions if q.pattern == focus)

    def public(self) -> dict:
        """Sin respuestas, sin citas y sin el tipo de pregunta: el examen tampoco
        dice qué te está preguntando."""
        return {
            "id": self.id,
            "kind": self.kind,
            "genre": self.genre,
            "title": self.title,
            "paragraphs": list(self.paragraphs),
            "words": self.words,
            "target_seconds": self.target_seconds,
            "questions": [{"prompt": q.prompt, "options": list(q.options)} for q in self.questions],
        }

    def check(self, answers: list) -> list[bool]:
        """Una por pregunta; la que falta o no es un índice cuenta como mal."""
        padded = list(answers)[: len(self.questions)]
        padded += [None] * (len(self.questions) - len(padded))
        return [
            not isinstance(a, bool) and a == q.answer
            for a, q in zip(padded, self.questions, strict=True)
        ]


def _paragraphs(text) -> tuple[str, ...]:
    return tuple(p for p in (clean_text(line) for line in str(text or "").split("\n")) if p)


def _question(item_id: str, index: int, raw: dict) -> Question:
    options = [clean_text(o) for o in raw.get("options") or []]
    answer = raw.get("answer")
    if isinstance(answer, bool) or not isinstance(answer, int) or answer not in range(len(options)):
        raise ValueError("respuesta fuera de rango")
    # Rotar hasta que la correcta caiga en la posición que dicta el id.
    target = int(content_id(item_id, str(index)), 16) % OPTIONS
    shift = (answer - target) % max(len(options), 1)
    rotated = options[shift:] + options[:shift]
    return Question(
        pattern=str(raw.get("pattern") or ""),
        prompt=clean_text(raw.get("prompt")),
        options=tuple(rotated),
        answer=target if len(options) == OPTIONS else answer,
        evidence=clean_text(raw.get("evidence")),
        why=clean_text(raw.get("why")),
    )


def build_reading_item(kind, genre, title, text, questions) -> ReadingItem:
    paragraphs = _paragraphs(text)
    if not isinstance(questions, list):
        raise ValueError("faltan las preguntas")
    item_id = content_id(kind, *paragraphs)
    return ReadingItem(
        id=item_id,
        kind=kind,
        genre=clean_text(genre),
        title=clean_text(title),
        paragraphs=paragraphs,
        questions=tuple(_question(item_id, i, q) for i, q in enumerate(questions)),
    )
