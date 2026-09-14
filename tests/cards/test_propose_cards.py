import pytest

from fluent.cards.application.propose_cards import ProposeCards
from fluent.cards.domain.errors import NoTerm, TermTooLong

from .fakes import FakeCardStore, FakeProposer


def test_cards_validates_term_and_passes_focus():
    proposer = FakeProposer(
        cards={"candidates": [{"front": "x", "back": "y"}], "deck": "Grammar::B1::x"}
    )
    use_case = ProposeCards(FakeCardStore(), proposer)
    assert use_case("  used to ", skill="Grammar", level="B1")["deck"] == "Grammar::B1::x"
    assert proposer.calls[0] == ("cards", "used to", {"skill": "Grammar", "level": "B1"})
    with pytest.raises(NoTerm):
        use_case("   ")
    with pytest.raises(TermTooLong):
        use_case("x" * 81)
