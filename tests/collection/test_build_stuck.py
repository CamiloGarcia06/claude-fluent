from datetime import date

from fluent.collection.application.build_stuck import BuildStuck
from fluent.collection.domain.review import AGAIN

from .fakes import FakeCollection
from .test_analysis import review


def test_stuck_ranks_and_annotates_cards():
    d = date(2026, 9, 10)
    reviews = [review(d, 1, button=AGAIN, duration_ms=9000)] * 3
    reviews += [review(d, 2, button=AGAIN, duration_ms=1000)] * 3
    reviews += [review(d, 3, deck="Maestría::MOT", button=AGAIN)] * 3  # fuera de alcance
    reader = FakeCollection(
        reviews=reviews,
        stats=[
            {"deck": "Reading::A1::W", "total": 50, "seen": 50, "mature": 0},
            {"deck": "Maestría::MOT", "total": 999, "seen": 0, "mature": 0},
        ],
        summaries={1: {"front": "uno", "note_id": 10}, 2: {"front": "dos", "note_id": 20}},
    )
    out = BuildStuck(reader)(0, limit=50)
    assert [c["card_id"] for c in out["cards"]] == [1, 2]
    assert out["cards"][0]["front"] == "uno" and out["cards"][0]["severity"] == "crítica"
    assert out["impact"]["total_cards"] == 50
    assert out["window"]["reviews"] == 6
