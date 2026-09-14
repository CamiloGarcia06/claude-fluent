import pytest

from fluent.cards.application.apply_repair import ApplyRepair
from fluent.cards.domain.errors import NoFields, UnknownFields

from .fakes import FakeCardStore

NOTE = {
    "noteId": 5,
    "modelName": "Basic",
    "fields": {"Front": {"value": "a"}, "Back": {"value": "b<br>c"}},
}


def test_apply_snapshots_encodes_and_reads_back():
    store = FakeCardStore(notes={5: NOTE})
    out = ApplyRepair(store)(5, {"Back": "dos\nlíneas"})
    assert out["ok"] and out["snapshot"] == "/tmp/5-snap.json"
    assert store.updated == [(5, {"Back": "dos<br>líneas"})]
    assert out["fields"] == {"Front": "a", "Back": "dos\nlíneas"}


def test_apply_validation():
    store = FakeCardStore(notes={5: NOTE})
    with pytest.raises(NoFields):
        ApplyRepair(store)(5, {})
    with pytest.raises(UnknownFields):
        ApplyRepair(store)(5, {"Nope": "x"})
    assert store.updated == []
