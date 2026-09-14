from fluent.writing.application.answer_turn import AnswerTurn
from fluent.writing.application.close_session import CloseSession

from .fakes import FakeCoach, FakePatterns, FakeSessions, FixedClock


def test_close_without_done_turns_writes_nothing():
    sessions = FakeSessions()
    session = sessions.new_session("anime", "B1")
    patterns = FakePatterns()
    out = CloseSession(sessions, patterns, FakeCoach(), FixedClock())(session["id"])
    assert session["closed"] and session["analysis"] is None and out["counted"] == []
    assert patterns.written == []


def test_close_analyses_and_counts_patterns():
    sessions = FakeSessions()
    session = sessions.new_session("anime", "B1")
    coach = FakeCoach()
    AnswerTurn(sessions, coach)(session["id"], "hello")
    patterns = FakePatterns(
        {
            "patterns": {
                "articles": {"sessions": ["20260910-100000", "20260911-100000"], "carded": None}
            },
            "unmatched": {},
        }
    )
    out = CloseSession(sessions, patterns, coach, FixedClock())(session["id"])
    assert session["closed_at"] == "2026-09-13T12:00:00"
    assert [r["key"] for r in out["counted"]] == ["articles"]
    assert out["ready"][0]["count"] == 3 and out["threshold"] == 3
    assert patterns.stored["unmatched"] == {"x": 1}
