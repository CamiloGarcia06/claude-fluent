import pytest

from fluent.toefl.application.refill_bank import SENTENCE_BATCH, RefillBank
from fluent.toefl.domain.errors import NothingGenerated, UnknownKind, UnknownPattern

from .fakes import ETS_PARAGRAPH, FakeBank, FakeGenerator


def raw_sentence(chunks):
    return {
        "pattern": "passive",
        "context": "ctx",
        "before": "I used",
        "after": ".",
        "chunks": chunks,
    }


def test_refill_keeps_the_valid_and_counts_the_rest():
    generator = FakeGenerator(
        sentences=[
            raw_sentence(["the guide", "that", "was provided", "by", "the professor"]),
            raw_sentence(["the guide", "that", "was provided", "by", "the professor"]),
            raw_sentence(["too", "short"]),
            {
                "pattern": "made_up",
                "context": "c",
                "before": "",
                "after": "?",
                "chunks": ["a", "b", "c"],
            },
            "not even a dict",
        ]
    )
    bank = FakeBank()
    out = RefillBank(bank, generator)("sentence", focus="passive")
    assert out == {"added": 1, "rejected": 3, "duplicates": 1}
    assert generator.calls == [("sentences", SENTENCE_BATCH, "passive")]
    assert len(bank.sentences()) == 1


def test_refill_words_and_nothing_usable():
    bank = FakeBank()
    out = RefillBank(bank, FakeGenerator(paragraphs=[{"text": ETS_PARAGRAPH}, {"text": "Short."}]))(
        "words"
    )
    assert out == {"added": 1, "rejected": 1, "duplicates": 0}
    with pytest.raises(NothingGenerated):
        RefillBank(bank, FakeGenerator(paragraphs=[{"text": "Short."}]))("words")


def test_refill_validates_kind_and_focus():
    with pytest.raises(UnknownKind):
        RefillBank(FakeBank(), FakeGenerator())("essay")
    with pytest.raises(UnknownPattern):
        RefillBank(FakeBank(), FakeGenerator())("sentence", focus="connector")
