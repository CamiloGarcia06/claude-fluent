import pytest

from fluent.writing.application.start_session import StartSession
from fluent.writing.domain.errors import NoTopic, SessionAlreadyOpen

from .fakes import FakeSessions, FixedClock


def test_start_cleans_topic_and_defaults_level():
    out = StartSession(FakeSessions(), FixedClock())("  hablemos   de anime  ", level="zz")
    assert out["session"]["topic"] == "hablemos de anime" and out["session"]["level"] == "B1"
    assert out["opening"] == "Let's talk about hablemos de anime. What's on your mind?"


def test_start_refuses_a_second_session_unless_restart():
    sessions = FakeSessions()
    use_case = StartSession(sessions, FixedClock())
    first = use_case("uno")["session"]
    with pytest.raises(SessionAlreadyOpen):
        use_case("dos")
    second = use_case("dos", restart=True)["session"]
    assert first["closed"] and first["abandoned"] and first["closed_at"] == "2026-09-13T12:00:00"
    assert second["topic"] == "dos" and sessions.open_session() is second


def test_start_needs_a_topic():
    with pytest.raises(NoTopic):
        StartSession(FakeSessions(), FixedClock())("   ")
