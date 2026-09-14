"""Lo que la práctica de escritura necesita de fuera: las sesiones y los
patrones en disco, el coach (modelo) y el reloj."""

from datetime import datetime
from typing import Protocol


class SessionStore(Protocol):
    max_turns: int

    def valid_id(self, value) -> str:
        """El id normalizado; lanza ValueError si no tiene la forma esperada."""
        ...

    def load(self, session_id: str) -> dict | None: ...

    def save(self, session: dict) -> dict: ...

    def new_session(self, topic: str, level: str) -> dict: ...

    def open_session(self) -> dict | None: ...

    def last_closed(self) -> dict | None: ...

    def recent_topics(self) -> list[str]: ...

    def append_turn(self, session: dict, text: str) -> dict: ...

    def retry_turn(self, session: dict, index: int, text: str) -> dict:
        """Lanza ValueError/IndexError si ese turno no se puede reintentar."""
        ...

    def finish_turn(
        self, session: dict, index: int, answer: dict | None, error: str = ""
    ) -> dict: ...


class PatternStore(Protocol):
    threshold: int

    def read(self) -> dict: ...

    def write(self, stored: dict) -> dict: ...

    def count(
        self, stored: dict, areas: list[dict], unmatched: list[str], session_id: str
    ) -> dict: ...

    def listing(self, stored: dict) -> list[dict]: ...

    def mark(self, stored: dict, key: str, action: str, stamp: str) -> dict:
        """Lanza ValueError si el patrón o la acción no valen."""
        ...

    def stamp(self) -> str: ...


class Coach(Protocol):
    max_text_chars: int

    def turn(self, topic: str, level: str, turns: list[dict], text: str) -> dict: ...

    def close(self, topic: str, level: str, turns: list[dict]) -> dict: ...


class Clock(Protocol):
    def now(self) -> datetime: ...
