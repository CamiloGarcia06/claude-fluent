import pytest

from fluent.toefl.application.grade_attempt import GradeAttempt
from fluent.toefl.domain.errors import ItemNotFound, UnknownKind

from .fakes import ETS_MISSING, FakeBank, FakeLog, FixedClock, sentence, words


def test_grade_sentence_logs_one_attempt():
    item, log = sentence(), FakeLog()
    out = GradeAttempt(FakeBank([item]), log, FixedClock())("sentence", item.id, list(item.answer))
    assert out["correct"] and out["sentence"].endswith("department?")
    assert out["tip"]["key"] == "indirect_question"
    assert [(a.pattern, a.correct, a.at) for a in log.attempts] == [
        ("indirect_question", True, "2026-10-22T18:00:00")
    ]


def test_grade_sentence_wrong_or_garbage_answer():
    item, log = sentence(), FakeLog()
    grade = GradeAttempt(FakeBank([item]), log, FixedClock())
    assert not grade("sentence", item.id, "not a list")["correct"]
    assert not grade("sentence", item.id, list(reversed(item.answer)))["correct"]
    assert [a.correct for a in log.attempts] == [False, False]


def test_grade_words_logs_one_attempt_per_gap_and_tips_once_per_pattern():
    item, log = words(), FakeLog()
    answer = list(ETS_MISSING)
    answer[1] = "ax"  # that → function_word
    answer[3] = "lx"  # only → adverb
    answer[7] = "ox"  # from → function_word, mismo consejo que "that"
    out = GradeAttempt(FakeBank(words=[item]), log, FixedClock())("words", item.id, answer)
    assert (out["score"], out["total"]) == (7, 10)
    assert len(log.attempts) == 10
    assert [t["key"] for t in out["tips"]] == ["function_word", "adverb"]
    assert out["results"][1] == {
        "correct": False,
        "word": "that",
        "missing": "at",
        "pattern": "function_word",
    }


def test_grade_unknown_things():
    grade = GradeAttempt(FakeBank(), FakeLog(), FixedClock())
    with pytest.raises(ItemNotFound):
        grade("sentence", "nope", [])
    with pytest.raises(ItemNotFound):
        grade("words", "nope", [])
    with pytest.raises(UnknownKind):
        grade("essay", "nope", [])
