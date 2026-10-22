import pytest

from fluent.toefl.domain.catalog import classify_word
from fluent.toefl.domain.entities import build_sentence_item, build_words_item, split_word

from .fakes import ETS_MISSING, ETS_PARAGRAPH, sentence, words


def test_words_follow_the_official_cut_rule():
    item = words()
    assert [g.missing for g in item.gaps] == ETS_MISSING
    assert [g.shown for g in item.gaps][:3] == ["mi", "th", "peo"]
    # El texto se reconstruye entero: partes + palabras completas.
    rebuilt = "".join(p + g.word for p, g in zip(item.parts, item.gaps, strict=False))
    assert rebuilt + item.parts[-1] == ETS_PARAGRAPH


def test_words_check_is_per_gap_and_case_blind():
    results = words().check(["GHT", " at ", "x"])
    assert results[:3] == [True, True, False]
    assert len(results) == 10 and not any(results[3:])


def test_words_skip_what_cannot_be_cut():
    text = "Intro sentence here. A b I c d e f g h i j k l m n o p q r s t u v w x y z."
    with pytest.raises(ValueError):
        build_words_item(text)  # todas de una letra: ningún hueco posible
    with pytest.raises(ValueError):
        build_words_item("Only one sentence without an end")


def test_public_words_hide_the_missing_letters():
    gap = words().public()["gaps"][0]
    assert gap == {"shown": "mi", "length": 3}


def test_split_word_keeps_the_lower_half_visible():
    assert split_word("However") == ("How", "ever")
    assert split_word("is") == ("i", "s")


def test_sentence_builds_and_grades():
    item = sentence()
    assert item.sentence() == "do you know if she will be moving to a different department?"
    assert item.is_correct(list(item.answer))
    assert not item.is_correct(list(reversed(item.answer)))
    assert not item.is_correct(list(item.answer)[:-1])


def test_shuffled_is_never_the_answer():
    item = sentence(chunks=["a", "b", "c"])
    assert item.shuffled() != list(item.answer)
    assert sorted(item.shuffled()) == sorted(item.answer)
    assert "answer" not in item.public()


def test_sentence_rejects_what_cannot_be_solved():
    with pytest.raises(ValueError):
        build_sentence_item("nope", "ctx", "", "?", ["a", "b", "c"])
    with pytest.raises(ValueError):
        build_sentence_item("passive", "ctx", "", "?", ["a", "b"])
    with pytest.raises(ValueError):
        build_sentence_item("passive", "", "", "?", ["a", "b", "c"])


def test_same_content_same_id():
    # El id es del contenido, no del patrón: el mismo ejercicio no entra dos veces.
    assert sentence().id == sentence(pattern="passive").id
    assert sentence(chunks=["x", "y", "z"]).id != sentence().id


def test_classify_word():
    assert classify_word("However") == "connector"
    assert classify_word("from") == "function_word"
    assert classify_word("dancing") == "verb_form"
    assert classify_word("only") == "adverb"
    assert classify_word("communication") == "noun_suffix"
    assert classify_word("basic") == "adjective_suffix"
    assert classify_word("record") == "content_word"
    assert classify_word("thing") == "content_word"
