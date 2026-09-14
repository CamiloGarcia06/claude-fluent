import pytest

from fluent.syllabi.application.freeze_syllabus import FreezeSyllabus
from fluent.syllabi.domain.errors import ModelReturnedNothing

from .fakes import FakeSyllabusModel, FakeSyllabusStore, FixedClock

STORED = {
    "skill": "Grammar",
    "level": "A1",
    "points": [{"point": "x"}],
    "drafts": 3,
    "generated": "g",
}


def test_freeze_reuses_a_stored_syllabus_without_calling_the_model():
    model = FakeSyllabusModel()
    out = FreezeSyllabus(FakeSyllabusStore(STORED), model, FixedClock())("Grammar", "A1")
    assert out["frozen"] and model.calls == []


def test_freeze_builds_and_saves_when_missing_or_regenerating():
    store, model = FakeSyllabusStore(), FakeSyllabusModel()
    out = FreezeSyllabus(store, model, FixedClock())("Grammar", "A1")
    assert model.calls == [("build", "Grammar", "A1")]
    assert out["generated"] == "2026-09-13T12:00:00" and out["edited"] is False
    FreezeSyllabus(store, model, FixedClock())("Grammar", "A1", regenerate=True)
    assert len(model.calls) == 2 and len(store.saved) == 2


def test_freeze_with_no_points_is_upstream_error():
    with pytest.raises(ModelReturnedNothing):
        FreezeSyllabus(FakeSyllabusStore(), FakeSyllabusModel(points=[]), FixedClock())(
            "Grammar", "A1"
        )
