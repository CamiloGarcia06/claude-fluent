"""Caso de uso: la sesión abierta, la última cerrada y los temas recientes."""

from fluent.writing.domain.ports import SessionStore


class GetPractice:
    def __init__(self, sessions: SessionStore) -> None:
        self._sessions = sessions

    def __call__(self) -> dict:
        return {
            "session": self._sessions.open_session(),
            "last": self._sessions.last_closed(),
            "topics": self._sessions.recent_topics(),
        }
