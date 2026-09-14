import pytest

from fluent.writing.application.answer_turn import AnswerTurn
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

from .fakes import FakeCoach, FakeSessions


def _open():
    sessions = FakeSessions()
    session = sessions.new_session("anime", "B1")
    return sessions, session


def test_turn_persists_then_answers():
    sessions, session = _open()
    coach = FakeCoach()
    out = AnswerTurn(sessions, coach)(session["id"], " hello ")
    assert (
        out["turn"]["state"] == "done" and out["turn"]["reply"] == "re: hello" and out["total"] == 1
    )
    assert coach.calls == [("turn", "anime", "B1", 0, "hello")]


def test_failed_turn_stays_retryable():
    sessions, session = _open()
    with pytest.raises(ModelFailed):
        AnswerTurn(sessions, FakeCoach(fail=True))(session["id"], "hello")
    assert session["turns"][0]["state"] == "failed" and "boom" in session["turns"][0]["error"]
    out = AnswerTurn(sessions, FakeCoach())(session["id"], "hello again", retry_index=0)
    assert out["turn"]["state"] == "done" and out["total"] == 1
    with pytest.raises(BadRetry):
        AnswerTurn(sessions, FakeCoach())(session["id"], "x", retry_index=0)  # ya respondido


def test_turn_validation_and_limits():
    sessions, session = _open()
    use_case = AnswerTurn(sessions, FakeCoach())
    with pytest.raises(NoText):
        use_case(session["id"], "  ")
    with pytest.raises(TextTooLong):
        use_case(session["id"], "x" * 21)
    with pytest.raises(InvalidSessionId):
        use_case("bad", "hola")
    with pytest.raises(SessionNotFound):
        use_case("20260913-999999", "hola")
    for i in range(3):
        use_case(session["id"], f"t{i}")
    with pytest.raises(TooManyTurns):
        use_case(session["id"], "t4")
    session["closed"] = True
    with pytest.raises(SessionClosed):
        use_case(session["id"], "hola")
