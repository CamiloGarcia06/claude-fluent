import pytest

from fluent.toefl.application.submit_writing import SubmitWriting
from fluent.toefl.domain.catalog import WRITING_PATTERNS
from fluent.toefl.domain.errors import (
    BadFeedback,
    ItemNotFound,
    NoText,
    TextTooLong,
    UnknownKind,
)

from .fakes import (
    FakeBank,
    FakeGrader,
    FakeLog,
    FakeSubmissions,
    FixedClock,
    discussion_prompt,
    email_prompt,
)
from .test_writing import TEXT, raw


def make(result=None):
    bank = FakeBank(emails=[email_prompt()], discussions=[discussion_prompt()])
    log, subs, grader = FakeLog(), FakeSubmissions(), FakeGrader(result or raw())
    return SubmitWriting(bank, grader, log, subs, FixedClock()), log, subs, grader


def test_submit_grades_logs_one_attempt_per_criterion_and_keeps_the_text():
    submit, log, subs, grader = make()
    prompt = email_prompt()
    out = submit("email", prompt.id, f"  {TEXT}  ", seconds=300)
    assert out["score"] == 3 and out["max_score"] == 5 and not out["revision"]
    assert [t["key"] for t in out["tips"]] == ["grammar", "mechanics"]
    assert out["criteria"][1]["label"] == "Gramática"
    assert grader.calls[0][0] == "email" and grader.calls[0][2] == TEXT
    assert len(log.attempts) == len(WRITING_PATTERNS)
    failed = {a.pattern for a in log.attempts if not a.correct}
    assert failed == {"grammar", "mechanics"}
    assert subs.rows[0]["text"] == TEXT and subs.rows[0]["seconds"] == 300


def test_revision_is_graded_but_does_not_count_for_advice():
    submit, log, subs, _ = make()
    prompt = email_prompt()
    submit("email", prompt.id, TEXT)
    before = len(log.attempts)
    out = submit("email", prompt.id, TEXT.replace("Is very", "It is very"), revision=True)
    assert out["revision"] and out["first_score"] == 3
    assert len(log.attempts) == before
    assert subs.rows[-1]["revision"] is True


def test_submit_rejects_bad_input_and_bad_feedback():
    submit, *_ = make()
    prompt = email_prompt()
    with pytest.raises(UnknownKind):
        submit("sentence", prompt.id, TEXT)
    with pytest.raises(NoText):
        submit("email", prompt.id, "   ")
    with pytest.raises(TextTooLong):
        submit("email", prompt.id, "x" * 5000)
    with pytest.raises(ItemNotFound):
        submit("email", "nope", TEXT)
    broken, log, subs, _ = make(raw(score=9))
    with pytest.raises(BadFeedback):
        broken("email", prompt.id, TEXT)
    assert log.attempts == [] and subs.rows == []
