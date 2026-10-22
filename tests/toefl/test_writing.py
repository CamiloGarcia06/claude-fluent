import pytest

from fluent.toefl.domain.writing import (
    build_discussion_prompt,
    build_email_prompt,
    build_feedback,
    word_count,
)

from .fakes import discussion_prompt, email_prompt

TEXT = "Dear Editor, i love your magazine. Is very good. Could you tell me if you got my poems?"


def raw(**over):
    base = {
        "score": 3,
        "summary": "Cumple la tarea pero con errores.",
        "criteria": [
            {"key": "task_completion", "ok": True, "comment": "Las tres viñetas."},
            {"key": "grammar", "ok": False, "comment": "Falta el sujeto."},
            {"key": "invented", "ok": False, "comment": "no existe"},
        ],
        "corrections": [
            {
                "wrong": "Is very good",
                "right": "It is very good",
                "why": "Sujeto.",
                "category": "grammar",
            },
            {"wrong": "i love", "right": "I love", "why": "Mayúscula.", "category": "mechanics"},
            {"wrong": "never written", "right": "x", "why": "inventado", "category": "grammar"},
            {"wrong": "same", "right": "same", "why": "", "category": "grammar"},
            {"wrong": "Dear", "right": "Hi", "why": "", "category": "nope"},
        ],
        "improved": "Dear Editor, I love your magazine. It is very good. …",
    }
    return {**base, **over}


def test_feedback_keeps_only_what_can_be_believed():
    fb = build_feedback(raw(), "email", TEXT)
    assert fb.score == 3 and fb.words == word_count(TEXT)
    assert [c.key for c in fb.criteria] == ["task_completion", "grammar"]
    assert [(c.wrong, c.category) for c in fb.corrections] == [
        ("Is very good", "grammar"),
        ("i love", "mechanics"),
    ]
    assert fb.flagged() == ["grammar", "mechanics"]


@pytest.mark.parametrize("score", [6, -1, "4", 3.5, True, None])
def test_feedback_rejects_a_score_out_of_range(score):
    with pytest.raises(ValueError):
        build_feedback(raw(score=score), "email", TEXT)


def test_discussion_under_100_words_flags_development_by_count():
    fb = build_feedback(raw(), "discussion", TEXT)
    development = next(c for c in fb.criteria if c.key == "development")
    assert not development.ok and "el mínimo es 100" in development.comment
    assert "development" in fb.flagged()
    long_text = TEXT + " word" * 100
    assert "development" not in build_feedback(raw(), "discussion", long_text).flagged()


def test_word_count():
    assert word_count("I don't think so, 100 times.") == 6
    assert word_count("") == 0


def test_prompts_validate_and_hide_nothing_secret():
    email = email_prompt()
    assert email.public()["minutes"] == 7 and len(email.public()["bullets"]) == 3
    assert "Subject: Problem using submission form" in email.brief()
    discussion = discussion_prompt()
    assert discussion.public()["min_words"] == 100
    assert "Claire: Yes" in discussion.brief()
    with pytest.raises(ValueError):
        build_email_prompt("s", "to", "subj", ["one", "two"])
    with pytest.raises(ValueError):
        build_discussion_prompt("c", "q?", [{"name": "A", "text": "t"}])
