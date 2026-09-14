from fluent.writing.application.get_practice import GetPractice

from .fakes import FakeSessions


def test_get_practice_reads_open_last_and_topics():
    sessions = FakeSessions()
    sessions.new_session("anime", "B1")
    out = GetPractice(sessions)()
    assert out["session"]["topic"] == "anime" and out["last"] is None and out["topics"] == ["anime"]
