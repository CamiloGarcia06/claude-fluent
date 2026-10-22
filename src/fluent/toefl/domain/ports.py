"""Lo que el entrenamiento del TOEFL necesita de fuera: el banco, los intentos y
las entregas en disco, el modelo que genera y el que corrige, y el reloj."""

from datetime import datetime
from typing import Protocol

from fluent.toefl.domain.entities import Attempt, SentenceItem, WordsItem
from fluent.toefl.domain.writing import DiscussionPrompt, EmailPrompt

Item = SentenceItem | WordsItem | EmailPrompt | DiscussionPrompt


class ItemBank(Protocol):
    """Un banco por tipo (`catalog.KINDS`). Los ejercicios salen en el orden en
    que entraron: el primero es el más viejo."""

    def items(self, kind: str) -> list[Item]: ...

    def add(self, kind: str, items: list[Item]) -> int:
        """Guarda los que no estaban (por id) y devuelve cuántos entraron."""
        ...


class AttemptLog(Protocol):
    def append(self, attempts: list[Attempt]) -> None: ...

    def recent(self) -> list[Attempt]:
        """Los últimos intentos, en orden cronológico. El log tiene tope: no es
        una historia, es la ventana de la que salen los consejos."""
        ...


class SubmissionLog(Protocol):
    """Las entregas de writing con su corrección, para volver a leerlas."""

    def append(self, submission: dict) -> None: ...

    def recent(self, kind: str) -> list[dict]:
        """Las últimas de ese tipo, la más nueva al final."""
        ...


class ItemGenerator(Protocol):
    """Lo que devuelve es no confiable: dicts crudos que el caso de uso valida."""

    def generate(self, kind: str, count: int, focus: str | None) -> list[dict]: ...


class Grader(Protocol):
    """Corrige un texto de writing con la rúbrica. Devuelve el dict crudo del
    modelo; `writing.build_feedback` lo valida."""

    def grade(self, kind: str, brief: str, text: str) -> dict: ...


class Clock(Protocol):
    def now(self) -> datetime: ...
