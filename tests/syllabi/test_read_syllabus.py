import pytest

from fluent.syllabi.application.read_syllabus import ReadSyllabus
from fluent.syllabi.domain.errors import UnknownSkillOrLevel

from .fakes import FakeSyllabusStore

STORED = {
    "skill": "Grammar",
    "level": "A1",
    "points": [{"point": "to be"}, {"point": "articles"}],
    "drafts": 3,
    "generated": "2026-09-01T10:00:00",
}


def test_missing_level_is_not_an_error():
    out = ReadSyllabus(FakeSyllabusStore())("grammar", "a1")
    assert out["frozen"] is False and out["unreadable"] is False and out["skill"] == "Grammar"


def test_unreadable_file_is_flagged():
    assert (
        ReadSyllabus(FakeSyllabusStore(STORED, unreadable=True))("Grammar", "A1")["unreadable"]
        is True
    )


def test_frozen_without_and_with_coverage():
    out = ReadSyllabus(FakeSyllabusStore(STORED))("Grammar", "A1")
    assert (
        out["frozen"] and out["total"] == 2 and out["covered"] is None and out["coverage"] is None
    )
    cached = {
        "computed": "2026-09-02T10:00:00",
        "decks": {"Grammar::A1::Verbs": 4},
        "by_point": {
            "to be": {"covered_by": "Verbs", "note": ""},
            "articles": {"covered_by": "", "note": ""},
        },
    }
    out = ReadSyllabus(FakeSyllabusStore(STORED, coverage=cached))("Grammar", "A1")
    assert out["covered"] == 1 and out["coverage"]["decks"] == {"Grammar::A1::Verbs": 4}


def test_unknown_skill():
    with pytest.raises(UnknownSkillOrLevel):
        ReadSyllabus(FakeSyllabusStore())("Cooking", "A1")
