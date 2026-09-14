import pytest

from fluent.collection.application.open_review import OpenReview
from fluent.collection.domain.errors import AnkiNotRunning, NothingDue


class FakeLauncher:
    def __init__(self, alive=True, due=None):
        self.alive, self.due, self.opened = alive, due or [], []

    def is_alive(self):
        return self.alive

    def due_counts(self):
        return self.due

    def open_deck_review(self, deck):
        self.opened.append(deck)

    def open_add_cards(self):
        self.opened.append("add")


def test_busiest_deck_wins_and_named_deck_must_have_work():
    launcher = FakeLauncher(
        due=[
            {"deck": "Reading::A1::W", "due": 3},
            {"deck": "Grammar::B1::T", "due": 7},
            {"deck": "Reading", "due": 3},
        ]
    )
    assert OpenReview(launcher)()["deck"] == "Grammar::B1::T"
    assert OpenReview(launcher)("Reading::A1::W")["due"] == 3
    with pytest.raises(NothingDue):
        OpenReview(launcher)("Grammar::B1::Nope")
    with pytest.raises(NothingDue):
        OpenReview(FakeLauncher(due=[{"deck": "Reading", "due": 0}]))()
    with pytest.raises(AnkiNotRunning):
        OpenReview(FakeLauncher(alive=False))()
