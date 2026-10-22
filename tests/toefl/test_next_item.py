import pytest

from fluent.toefl.application.next_item import NextItem
from fluent.toefl.domain.entities import Attempt
from fluent.toefl.domain.errors import BankEmpty, UnknownKind

from .fakes import FakeBank, FakeLog, misses, sentence, words


def test_next_prefers_the_weakest_pattern():
    indirect, passive = sentence(), sentence(pattern="passive", chunks=["x", "y", "z"])
    log = FakeLog(misses("sentence", "passive", wrong=3))
    out = NextItem(FakeBank([indirect, passive]), log)("sentence")
    assert out["item"]["id"] == passive.id and out["focus"] == "passive" and out["fresh"] == 2
    assert "answer" not in out["item"]


def test_next_skips_what_you_already_did():
    first, second = sentence(), sentence(chunks=["x", "y", "z"])
    log = FakeLog([Attempt("sentence", first.id, first.pattern, True, "t")])
    assert NextItem(FakeBank([first, second]), log)("sentence")["item"]["id"] == second.id


def test_next_words_and_empty_bank():
    out = NextItem(FakeBank(words=[words()]), FakeLog())("words")
    assert out["item"]["kind"] == "words" and len(out["item"]["gaps"]) == 10
    with pytest.raises(BankEmpty):
        NextItem(FakeBank(), FakeLog())("sentence")
    with pytest.raises(UnknownKind):
        NextItem(FakeBank(), FakeLog())("speaking")
