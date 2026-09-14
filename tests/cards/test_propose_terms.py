from datetime import date

import pytest

from fluent.cards.application.propose_terms import ProposeTerms
from fluent.cards.domain.errors import AnkiNotRunning
from fluent.collection.domain.review import AGAIN
from tests.collection.test_analysis import review

from .fakes import FakeCardStore, FakeProposer


def test_terms_pass_stuck_with_text_focus_and_have():
    d = date(2026, 9, 10)
    store = FakeCardStore(
        reviews=[review(d, 1, button=AGAIN)] * 3,
        summaries={1: {"front": "look up", "note_id": 10}},
        stats=[{"deck": "Grammar::B1::Tenses", "total": 3, "seen": 3, "mature": 0}],
        fronts={"Grammar::B1::Tenses": ["past simple", "present perfect"]},
    )
    proposer = FakeProposer(
        terms={"terms": [{"term": "used to", "reason": "…"}], "topic": "", "duration_ms": 5}
    )
    out = ProposeTerms(store, proposer)(0, skill="grammar", level="b1", topic="modales")
    assert out["terms"][0]["term"] == "used to"
    kind, stuck, focus, topic, have = proposer.calls[0]
    assert stuck[0]["front"] == "look up"
    assert focus == {"skill": "Grammar", "level": "B1"}
    assert topic == "modales" and have == ["past simple", "present perfect"]


def test_terms_without_focus_send_no_have():
    proposer = FakeProposer()
    ProposeTerms(FakeCardStore(), proposer)(0)
    assert proposer.calls[0][2] is None and proposer.calls[0][4] == []


def test_terms_without_anki():
    with pytest.raises(AnkiNotRunning):
        ProposeTerms(FakeCardStore(alive=False), FakeProposer())(0)
