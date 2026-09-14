import pytest

from fluent.cards.application.repair_note import RepairNote
from fluent.cards.domain.errors import NoteNotFound

from .fakes import FakeCardStore, FakeProposer

NOTE = {
    "noteId": 5,
    "modelName": "Basic",
    "fields": {"Front": {"value": "a"}, "Back": {"value": "b"}},
}


def test_repair_asks_the_model_for_an_existing_note():
    proposer = FakeProposer(repair={"proposal": {"Front": "a'"}, "duration_ms": 3})
    assert RepairNote(FakeCardStore(notes={5: NOTE}), proposer)(5)["proposal"] == {"Front": "a'"}
    assert proposer.calls == [("repair", 5)]


def test_repair_missing_note():
    with pytest.raises(NoteNotFound):
        RepairNote(FakeCardStore(), FakeProposer())(99)
