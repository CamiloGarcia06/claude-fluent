"""Lo que el entrenamiento del TOEFL necesita de fuera: el banco y los intentos
en disco, el modelo que genera ejercicios y el reloj."""

from datetime import datetime
from typing import Protocol

from fluent.toefl.domain.entities import Attempt, SentenceItem, WordsItem


class ItemBank(Protocol):
    def sentences(self) -> list[SentenceItem]: ...

    def words(self) -> list[WordsItem]: ...

    def add_sentences(self, items: list[SentenceItem]) -> int:
        """Guarda los que no estaban (por id) y devuelve cuántos entraron."""
        ...

    def add_words(self, items: list[WordsItem]) -> int: ...


class AttemptLog(Protocol):
    def append(self, attempts: list[Attempt]) -> None: ...

    def recent(self) -> list[Attempt]:
        """Los últimos intentos, en orden cronológico. El log tiene tope: no es
        una historia, es la ventana de la que salen los consejos."""
        ...


class ItemGenerator(Protocol):
    """Lo que devuelve es no confiable: dicts crudos que el caso de uso valida."""

    def sentences(self, count: int, focus: str | None) -> list[dict]: ...

    def paragraphs(self, count: int, focus: str | None) -> list[dict]: ...


class Clock(Protocol):
    def now(self) -> datetime: ...
