"""Caso de uso: leer la sesión entera de una vez y contar los patrones. Es lo
único que escribe patterns.json: el cierre es lo único que ve la sesión
completa y sabe qué se repitió."""

from fluent.writing.application.answer_turn import open_session_or_raise
from fluent.writing.domain.ports import Clock, Coach, PatternStore, SessionStore


class CloseSession:
    def __init__(
        self, sessions: SessionStore, patterns: PatternStore, coach: Coach, clock: Clock
    ) -> None:
        self._sessions = sessions
        self._patterns = patterns
        self._coach = coach
        self._clock = clock

    def __call__(self, session_id) -> dict:
        session = open_session_or_raise(self._sessions, session_id)
        done = [t for t in session["turns"] if t["state"] == "done"]

        analysis = None
        if done:
            analysis = self._coach.close(session["topic"], session["level"], session["turns"])

        session["analysis"] = analysis
        session["closed"] = True
        session["closed_at"] = self._clock.now().isoformat(timespec="seconds")
        self._sessions.save(session)

        if analysis is None:
            return {"session": session, "counted": [], "ready": []}

        stored = self._patterns.count(
            self._patterns.read(), analysis["areas"], analysis["unmatched"], session["id"]
        )
        self._patterns.write(stored)

        counted = {a["pattern"] for a in analysis["areas"] if a["pattern"]}
        rows = self._patterns.listing(stored)
        return {
            "session": session,
            "counted": [r for r in rows if r["key"] in counted],
            "ready": [r for r in rows if r["ready"]],
            "threshold": self._patterns.threshold,
        }
