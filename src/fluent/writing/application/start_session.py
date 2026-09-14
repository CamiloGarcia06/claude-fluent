"""Caso de uso: abrir una sesión sobre un tema. No llama al modelo: el saludo lo
compone el app, porque quince segundos antes de la primera palabra es donde se
abandona."""

from fluent.writing.domain.errors import NoTopic, SessionAlreadyOpen
from fluent.writing.domain.levels import clean_topic, level_or_default
from fluent.writing.domain.ports import Clock, SessionStore


class StartSession:
    def __init__(self, sessions: SessionStore, clock: Clock) -> None:
        self._sessions = sessions
        self._clock = clock

    def __call__(self, topic, level=None, restart: bool = False) -> dict:
        topic = clean_topic(topic)
        if not topic:
            raise NoTopic()
        level = level_or_default(level)

        current = self._sessions.open_session()
        if current and not restart:
            raise SessionAlreadyOpen()
        if current:
            current["closed"] = True
            current["abandoned"] = True
            current["closed_at"] = self._clock.now().isoformat(timespec="seconds")
            self._sessions.save(current)

        session = self._sessions.new_session(topic, level)
        return {"session": session, "opening": f"Let's talk about {topic}. What's on your mind?"}
