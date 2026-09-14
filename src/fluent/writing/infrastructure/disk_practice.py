"""Adaptadores de SessionStore y PatternStore sobre el módulo plano practice.py
(JSON en data/practice/)."""

from fluent.writing.infrastructure import sessions as practice


class DiskSessions:
    max_turns = practice.MAX_TURNS

    def valid_id(self, value) -> str:
        return practice._valid_id(value)

    def load(self, session_id: str) -> dict | None:
        return practice.load(session_id)

    def save(self, session: dict) -> dict:
        return practice.save(session)

    def new_session(self, topic: str, level: str) -> dict:
        return practice.new_session(topic, level)

    def open_session(self) -> dict | None:
        return practice.open_session()

    def last_closed(self) -> dict | None:
        return practice.last_closed()

    def recent_topics(self) -> list[str]:
        return practice.recent_topics()

    def append_turn(self, session: dict, text: str) -> dict:
        return practice.append_turn(session, text)

    def retry_turn(self, session: dict, index: int, text: str) -> dict:
        return practice.retry_turn(session, index, text)

    def finish_turn(self, session: dict, index: int, answer: dict | None, error: str = "") -> dict:
        return practice.finish_turn(session, index, answer, error)


class DiskPatterns:
    threshold = practice.PATTERN_THRESHOLD

    def read(self) -> dict:
        return practice.read_patterns()

    def write(self, stored: dict) -> dict:
        return practice.write_patterns(stored)

    def count(self, stored: dict, areas: list[dict], unmatched: list[str], session_id: str) -> dict:
        return practice.count(stored, areas, unmatched, session_id)

    def listing(self, stored: dict) -> list[dict]:
        return practice.listing(stored)

    def mark(self, stored: dict, key: str, action: str, stamp: str) -> dict:
        return practice.mark(stored, key, action, stamp)

    def stamp(self) -> str:
        return practice.stamp()
