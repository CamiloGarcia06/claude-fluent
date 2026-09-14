from datetime import date

import pytest

from fluent.collection.application.build_today import BuildToday
from fluent.collection.domain.errors import AnkiNotRunning
from fluent.collection.domain.review import AGAIN

from .fakes import FakeCollection
from .test_analysis import TODAY, ms, review


def test_today_merges_goal_and_card_text():
    d = date(2026, 9, 12)
    reviews = [review(d, 7, button=AGAIN)] * 3 + [review(d, 8)]
    reader = FakeCollection(
        reviews=reviews,
        due=[{"deck": "Reading", "due": 4}],
        summaries={7: {"front": "spill the beans", "note_id": 700}},
    )
    out = BuildToday(reader)(TODAY, ms(date(2026, 9, 1)), daily_goal=25)
    assert out["goal"] == 25
    assert out["due"]["total"] == 4
    assert [c["card_id"] for c in out["failing"]] == [7]
    assert out["failing"][0]["front"] == "spill the beans"
    assert out["failing"][0]["note_id"] == 700
    assert reader.asked_since == [ms(date(2026, 9, 1))]


def test_today_without_anki_raises_domain_error():
    with pytest.raises(AnkiNotRunning):
        BuildToday(FakeCollection(alive=False))(TODAY, 0, 40)
