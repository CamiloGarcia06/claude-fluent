import pytest

from fluent.toefl.application.refill_bank import BATCH, RefillBank
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
        sentence=[
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
    assert generator.calls == [("sentence", BATCH["sentence"], "passive")]
    assert len(bank.items("sentence")) == 1


def test_refill_words_and_nothing_usable():
    bank = FakeBank()
    out = RefillBank(bank, FakeGenerator(words=[{"text": ETS_PARAGRAPH}, {"text": "Short."}]))(
        "words"
    )
    assert out == {"added": 1, "rejected": 1, "duplicates": 0}
    with pytest.raises(NothingGenerated):
        RefillBank(bank, FakeGenerator(words=[{"text": "Short."}]))("words")


def test_refill_validates_kind_and_focus():
    with pytest.raises(UnknownKind):
        RefillBank(FakeBank(), FakeGenerator())("essay")
    with pytest.raises(UnknownPattern):
        RefillBank(FakeBank(), FakeGenerator())("sentence", focus="connector")


def test_refill_reading_rejects_invented_evidence():
    from .fakes import MIRROR_TEXT, mirror_questions

    good = {"genre": "biology", "title": "T", "text": MIRROR_TEXT, "questions": mirror_questions()}
    invented = {
        **good,
        "questions": [{**q, "evidence": "not in the text"} for q in mirror_questions()],
    }
    generator = FakeGenerator(academic=[good, invented])
    bank = FakeBank()
    out = RefillBank(bank, generator)("academic", focus="inference")
    assert out == {"added": 1, "rejected": 1, "duplicates": 0}
    assert generator.calls == [("academic", BATCH["academic"], "inference")]
