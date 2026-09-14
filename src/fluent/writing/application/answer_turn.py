"""Caso de uso: responder un mensaje y corregir lo que estorbó.

El turno se persiste dos veces: tu texto primero, la respuesta después. Sin ese
primer write, recargar a los cinco segundos borra lo que escribiste."""

from fluent.writing.domain.errors import (
    BadRetry,
    InvalidSessionId,
    ModelFailed,
    NoText,
    SessionClosed,
    SessionNotFound,
    TextTooLong,
    TooManyTurns,
)
from fluent.writing.domain.ports import Coach, SessionStore


def open_session_or_raise(sessions: SessionStore, session_id) -> dict:
    """La sesión que el cliente nombró, abierta y escribible, o el error."""
    try:
        sessions.valid_id(session_id)
    except ValueError as e:
        raise InvalidSessionId(str(e)) from e
    session = sessions.load(str(session_id))
    if session is None:
        raise SessionNotFound()
    if session["closed"]:
        raise SessionClosed()
    return session


class AnswerTurn:
    def __init__(self, sessions: SessionStore, coach: Coach) -> None:
        self._sessions = sessions
        self._coach = coach

    def __call__(self, session_id, text, retry_index=None) -> dict:
        session = open_session_or_raise(self._sessions, session_id)
        text = str(text or "").strip()
        if not text:
            raise NoText()
        if len(text) > self._coach.max_text_chars:
            raise TextTooLong()

        # Reintentar reescribe el turno que falló; mandar uno nuevo lo agrega.
        if retry_index is None:
            if len(session["turns"]) >= self._sessions.max_turns:
                raise TooManyTurns(
                    f"esta sesión ya llegó a {self._sessions.max_turns} turnos: cerrala y analizala"
                )
            turn = self._sessions.append_turn(session, text)
        else:
            try:
                turn = self._sessions.retry_turn(session, int(retry_index), text)
            except (TypeError, ValueError, IndexError) as e:
                raise BadRetry(f"no se puede reintentar ese turno: {e}") from e

        try:
            answer = self._coach.turn(
                session["topic"], session["level"], session["turns"][: turn["index"]], text
            )
        except ModelFailed as e:
            # El turno queda visible y reintentable: cuesta ese turno y nada más.
            self._sessions.finish_turn(session, turn["index"], None, str(e))
            raise

        return {
            "turn": self._sessions.finish_turn(session, turn["index"], answer),
            "total": len(session["turns"]),
        }
