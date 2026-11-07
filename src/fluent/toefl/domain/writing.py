"""Writing: los dos enunciados (Write an Email, Academic Discussion) y lo que
devuelve el corrector.

La devolución del modelo es no confiable como cualquier entrada: una nota fuera
de 0-5 tumba la corrección entera, y una corrección cuyo texto "mal escrito"
no aparece en lo que escribiste se descarta, porque señalaría algo que nunca
dijiste. Lo que sí se puede contar sin modelo —las palabras— se cuenta acá.
"""

import re
from dataclasses import dataclass

from fluent.toefl.domain.catalog import B1, DISCUSSION, EMAIL, WRITING_PATTERNS
from fluent.toefl.domain.entities import clean_text, content_id

# Los minutos del examen, y el mínimo que pide el enunciado. El texto B1 no es
# del TOEFL: Cambridge da 45 minutos para dos textos de unas 100 palabras.
MINUTES = {EMAIL: 7, DISCUSSION: 10, B1: 20}
MIN_WORDS = {EMAIL: 0, DISCUSSION: 100, B1: 100}
MAX_TEXT_CHARS = 4000
MAX_SCORE = 5
MAX_CORRECTIONS = 8
# El nivel del marco europeo que estima el corrector, de menor a mayor. Es lo
# que mide el requisito de la maestría (B1), no la nota de ETS.
LEVELS = ("A1", "A2", "B1", "B2", "C1")
B1_GENRES = ("email", "article", "story")

_WRITING_KEYS = frozenset(p.key for p in WRITING_PATTERNS)
_WORD = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)*|\d+")


def word_count(text: str) -> int:
    return len(_WORD.findall(text or ""))


@dataclass(frozen=True)
class EmailPrompt:
    id: str
    situation: str
    to: str
    subject: str
    bullets: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.situation or not self.subject:
            raise ValueError("enunciado incompleto")
        if len(self.bullets) != 3 or any(not b for b in self.bullets):
            raise ValueError("el email pide tres viñetas")

    @property
    def kind(self) -> str:
        return EMAIL

    def weight(self, focus: str | None) -> int:
        return 0

    def public(self) -> dict:
        return {
            "id": self.id,
            "kind": EMAIL,
            "situation": self.situation,
            "to": self.to,
            "subject": self.subject,
            "bullets": list(self.bullets),
            "minutes": MINUTES[EMAIL],
            "min_words": MIN_WORDS[EMAIL],
        }

    def brief(self) -> str:
        """El enunciado tal como lo lee el corrector."""
        bullets = "\n".join(f"- {b}" for b in self.bullets)
        return (
            f"{self.situation}\nTo: {self.to}\nSubject: {self.subject}\nIn your email:\n{bullets}"
        )


def build_email_prompt(situation, to, subject, bullets) -> EmailPrompt:
    situation, to, subject = clean_text(situation), clean_text(to), clean_text(subject)
    items = tuple(clean_text(b) for b in (bullets or []))
    return EmailPrompt(
        id=content_id(EMAIL, situation, *items),
        situation=situation,
        to=to,
        subject=subject,
        bullets=items,
    )


@dataclass(frozen=True)
class Post:
    name: str
    text: str


@dataclass(frozen=True)
class DiscussionPrompt:
    id: str
    course: str
    professor: str
    posts: tuple[Post, ...]

    def __post_init__(self) -> None:
        if not self.professor:
            raise ValueError("sin pregunta del profesor")
        if len(self.posts) != 2 or any(not p.name or not p.text for p in self.posts):
            raise ValueError("la discusión trae dos estudiantes")

    @property
    def kind(self) -> str:
        return DISCUSSION

    def weight(self, focus: str | None) -> int:
        return 0

    def public(self) -> dict:
        return {
            "id": self.id,
            "kind": DISCUSSION,
            "course": self.course,
            "professor": self.professor,
            "posts": [{"name": p.name, "text": p.text} for p in self.posts],
            "minutes": MINUTES[DISCUSSION],
            "min_words": MIN_WORDS[DISCUSSION],
        }

    def brief(self) -> str:
        posts = "\n".join(f"{p.name}: {p.text}" for p in self.posts)
        return f"Course: {self.course}\nProfessor: {self.professor}\n{posts}"


def build_discussion_prompt(course, professor, posts) -> DiscussionPrompt:
    course, professor = clean_text(course), clean_text(professor)
    items = tuple(Post(clean_text(p.get("name")), clean_text(p.get("text"))) for p in (posts or []))
    return DiscussionPrompt(
        id=content_id(DISCUSSION, professor, *(p.text for p in items)),
        course=course,
        professor=professor,
        posts=items,
    )


@dataclass(frozen=True)
class B1Prompt:
    """Un enunciado estilo Cambridge B1 Preliminary: responder un correo con
    sus notas, un artículo de opinión o una historia que empieza con una frase
    dada."""

    id: str
    genre: str
    title: str
    task: str
    notes: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.genre not in B1_GENRES:
            raise ValueError(f"género desconocido: {self.genre!r}")
        if not self.title or not self.task:
            raise ValueError("enunciado incompleto")
        if len(self.notes) > 4 or any(not n for n in self.notes):
            raise ValueError("como mucho cuatro notas, ninguna vacía")
        if self.genre == "email" and len(self.notes) < 2:
            raise ValueError("el correo trae las notas que hay que responder")

    @property
    def kind(self) -> str:
        return B1

    def weight(self, focus: str | None) -> int:
        return 0

    def public(self) -> dict:
        return {
            "id": self.id,
            "kind": B1,
            "genre": self.genre,
            "title": self.title,
            "task": self.task,
            "notes": list(self.notes),
            "minutes": MINUTES[B1],
            "min_words": MIN_WORDS[B1],
        }

    def brief(self) -> str:
        notes = "\n".join(f"- {n}" for n in self.notes)
        head = f"Cambridge B1 Preliminary writing, {self.genre}: {self.title}\n{self.task}"
        return f"{head}\nNotes to cover:\n{notes}" if notes else head


def build_b1_prompt(genre, title, task, notes) -> B1Prompt:
    genre = clean_text(genre).lower()
    title, task = clean_text(title), clean_text(task)
    items = tuple(clean_text(n) for n in (notes or []))
    return B1Prompt(
        id=content_id(B1, genre, title, task),
        genre=genre,
        title=title,
        task=task,
        notes=items,
    )


@dataclass(frozen=True)
class Criterion:
    key: str
    ok: bool
    comment: str


@dataclass(frozen=True)
class Correction:
    wrong: str
    right: str
    why: str
    category: str


@dataclass(frozen=True)
class Feedback:
    score: int
    summary: str
    criteria: tuple[Criterion, ...]
    corrections: tuple[Correction, ...]
    improved: str
    words: int
    level: str

    def flagged(self) -> list[str]:
        """Los criterios que fallaron en esta entrega, en el orden del catálogo."""
        bad = {c.key for c in self.criteria if not c.ok} | {c.category for c in self.corrections}
        return [p.key for p in WRITING_PATTERNS if p.key in bad]


def build_feedback(raw: dict, kind: str, text: str) -> Feedback:
    """Valida lo que devolvió el corrector contra lo que escribiste."""
    score = raw.get("score")
    if not isinstance(score, int) or isinstance(score, bool) or not 0 <= score <= MAX_SCORE:
        raise ValueError(f"nota inválida: {score!r}")

    level = raw.get("level")
    if level not in LEVELS:
        raise ValueError(f"nivel inválido: {level!r}")

    words = word_count(text)
    criteria = {}
    for row in raw.get("criteria") or []:
        if isinstance(row, dict) and row.get("key") in _WRITING_KEYS:
            criteria[row["key"]] = Criterion(
                row["key"], bool(row.get("ok")), clean_text(row.get("comment"))
            )
    # El mínimo de palabras no se le pregunta al modelo: se cuenta.
    if words < MIN_WORDS.get(kind, 0):
        note = f"{words} palabras: el mínimo es {MIN_WORDS[kind]}."
        old = criteria.get("development")
        criteria["development"] = Criterion(
            "development", False, f"{note} {old.comment}" if old else note
        )

    lowered = text.lower()
    corrections = []
    for row in raw.get("corrections") or []:
        if not isinstance(row, dict) or row.get("category") not in _WRITING_KEYS:
            continue
        wrong, right = clean_text(row.get("wrong")), clean_text(row.get("right"))
        if wrong and right and wrong != right and wrong.lower() in lowered:
            corrections.append(
                Correction(wrong, right, clean_text(row.get("why")), row["category"])
            )

    return Feedback(
        score=score,
        summary=clean_text(raw.get("summary")),
        criteria=tuple(criteria[p.key] for p in WRITING_PATTERNS if p.key in criteria),
        corrections=tuple(corrections[:MAX_CORRECTIONS]),
        improved=str(raw.get("improved") or "").strip(),
        words=words,
        level=level,
    )
