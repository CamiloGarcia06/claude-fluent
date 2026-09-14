import pytest

from fluent.syllabi.application.cover_syllabus import CoverSyllabus
from fluent.syllabi.domain.errors import AnkiNotRunning, NoSyllabusYet

from .fakes import FakeDecks, FakeSyllabusModel, FakeSyllabusStore, FixedClock

STORED = {
    "skill": "Grammar",
    "level": "A1",
    "points": [{"point": "to be"}],
    "drafts": 3,
    "generated": "g",
}


def test_cover_reads_decks_of_the_level_and_saves_coverage():
    decks = FakeDecks(
        stats=[
            {"deck": "Grammar::A1::Verbs", "total": 4, "seen": 4, "mature": 1},
            {"deck": "Grammar::B1::Other", "total": 9, "seen": 0, "mature": 0},
        ],
        fronts={"Grammar::A1::Verbs": ["I am", "you are"]},
    )
    store, model = FakeSyllabusStore(STORED), FakeSyllabusModel()
    out = CoverSyllabus(store, model, decks, FixedClock())("Grammar", "A1")
    kind, topics, have = model.calls[0]
    assert topics == ["Verbs"] and have == ["Verbs: I am", "Verbs: you are"]
    assert out["covered"] == 1 and out["coverage"]["decks"] == {"Grammar::A1::Verbs": 4}
    assert store.saved == [("coverage", {"Grammar::A1::Verbs": 4})]


def test_cover_requires_anki_and_a_frozen_syllabus():
    with pytest.raises(AnkiNotRunning):
        CoverSyllabus(
            FakeSyllabusStore(STORED), FakeSyllabusModel(), FakeDecks(alive=False), FixedClock()
        )("Grammar", "A1")
    with pytest.raises(NoSyllabusYet):
        CoverSyllabus(FakeSyllabusStore(), FakeSyllabusModel(), FakeDecks(), FixedClock())(
            "Grammar", "A1"
        )
