import pytest

from fluent.toefl.domain.reading import OPTIONS, build_reading_item

from .fakes import MIRROR_TEXT, mirror, mirror_questions, right_answers


def test_build_keeps_paragraphs_and_hides_the_answers():
    item = mirror()
    assert len(item.paragraphs) == 3 and item.words > 150
    public = item.public()
    assert public["paragraphs"][0].startswith("Very young children")
    assert set(public["questions"][0]) == {"prompt", "options"}
    assert "answer" not in str(public) and "evidence" not in str(public)
    # 150 palabras por minuto y 30 s por pregunta.
    assert item.target_seconds == round(item.words * 60 / 150 + 30 * 4)


def test_options_are_rotated_but_the_answer_follows_them():
    item = mirror()
    for q, raw in zip(item.questions, mirror_questions(), strict=True):
        assert q.options[q.answer] == raw["options"][raw["answer"]]
        assert sorted(q.options) == sorted(raw["options"])
    # Las cuatro correctas de ETS caen en B, A, B, A; el barajado no las deja así.
    assert [q.answer for q in item.questions] != [1, 0, 1, 0]
    assert mirror() == item  # siempre el mismo orden para el mismo texto


def test_check_counts_missing_and_bad_answers_as_wrong():
    item = mirror()
    right = right_answers(item)
    assert item.check(right) == [True] * 4
    wrong = (right[0] + 1) % OPTIONS
    assert item.check([wrong, right[1], None, True]) == [False, True, False, False]
    assert item.check([]) == [False] * 4
    assert item.weight("detail") == 1 and item.weight("inference") == 0


def _with(index, **change):
    questions = mirror_questions()
    questions[index] = {**questions[index], **change}
    return questions


@pytest.mark.parametrize(
    "questions",
    [
        _with(0, evidence="a sentence the passage never says"),
        _with(0, options=["a", "b", "c"]),
        _with(0, options=["a", "a", "b", "c"]),
        _with(0, answer=4),
        _with(0, answer=True),
        _with(0, pattern="nope"),
        _with(0, why=""),
        mirror_questions()[:2],  # una académica necesita 4 o 5
    ],
)
def test_build_rejects_what_cannot_be_trusted(questions):
    with pytest.raises(ValueError):
        build_reading_item("academic", "biology", "T", MIRROR_TEXT, questions)


def test_build_rejects_a_text_out_of_range():
    with pytest.raises(ValueError):
        build_reading_item("academic", "b", "T", "Too short.", mirror_questions())
    with pytest.raises(ValueError):
        build_reading_item("essay", "b", "T", MIRROR_TEXT, mirror_questions())


@pytest.mark.parametrize("why", ["La B es falsa.", "la opción C tienta", "(A) no", "Las A y D"])
def test_an_explanation_that_names_a_letter_is_rejected(why):
    with pytest.raises(ValueError):
        build_reading_item("academic", "b", "T", MIRROR_TEXT, _with(0, why=why))


def test_an_explanation_may_use_capital_letters_in_words():
    item = build_reading_item(
        "academic", "b", "T", MIRROR_TEXT, _with(0, why="La Antártida y La Haya están lejos.")
    )
    assert item.questions[0].why.startswith("La Antártida")
