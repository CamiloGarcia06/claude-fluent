import pytest

from fluent.toefl.application.grade_reading import GradeReading
from fluent.toefl.domain.errors import ItemNotFound, UnknownKind

from .fakes import FakeBank, FakeLog, FakeSubmissions, FixedClock, mirror, right_answers


def make():
    log, subs = FakeLog(), FakeSubmissions()
    return GradeReading(FakeBank(academic=[mirror()]), log, subs, FixedClock()), log, subs


def test_grade_logs_one_attempt_per_question_and_the_time():
    grade, log, subs = make()
    item = mirror()
    answers = right_answers(item)
    answers[2] = (answers[2] + 1) % 4
    out = grade("academic", item.id, answers, seconds=200)
    assert (out["score"], out["total"], out["seconds"]) == (3, 4, 200)
    assert out["target_seconds"] == item.target_seconds
    wrong = out["results"][2]
    assert not wrong["correct"] and wrong["chosen"] == answers[2]
    assert wrong["label"] == "Detalle" and wrong["evidence"] in " ".join(item.paragraphs)
    assert [t["key"] for t in out["tips"]] == ["detail"]
    assert [(a.pattern, a.correct) for a in log.attempts][2] == ("detail", False)
    assert subs.rows == [
        {
            "kind": "academic",
            "item_id": item.id,
            "at": "2026-10-22T18:00:00",
            "seconds": 200,
            "target_seconds": item.target_seconds,
            "score": 3,
            "total": 4,
        }
    ]


def test_unanswered_questions_count_as_wrong_and_odd_times_are_dropped():
    grade, log, _ = make()
    out = grade("academic", mirror().id, [None], seconds=99999)
    assert out["score"] == 0 and out["seconds"] is None
    assert out["results"][0]["chosen"] is None and len(log.attempts) == 4


def test_grade_rejects_unknown_kind_and_item():
    grade, *_ = make()
    with pytest.raises(UnknownKind):
        grade("email", mirror().id, [])
    with pytest.raises(ItemNotFound):
        grade("academic", "nope", [])
