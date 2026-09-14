import pytest

from fluent.collection.application.build_catalog import BuildCatalog
from fluent.collection.domain.errors import AnkiNotRunning

from .fakes import FakeCollection


def test_catalog_reads_stats_and_due():
    reader = FakeCollection(
        stats=[{"deck": "Reading::A1::Words", "total": 10, "seen": 10, "mature": 8}],
        due=[{"deck": "Reading::A1::Words", "due": 2}],
    )
    out = BuildCatalog(reader)()
    reading = next(s for s in out["skills"] if s["skill"] == "Reading")
    assert reading["due"] == 2 and out["total"] == 10


def test_catalog_without_anki():
    with pytest.raises(AnkiNotRunning):
        BuildCatalog(FakeCollection(alive=False))()
