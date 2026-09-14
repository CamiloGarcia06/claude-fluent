import pytest

from fluent.cards.application.write_notes import MAX_CARDS_PER_WRITE, WriteNotes
from fluent.cards.domain.errors import (
    CardIncomplete,
    InvalidDeckName,
    MalformedCard,
    NoCards,
    TooManyCards,
)

from .fakes import FakeCardStore


def test_write_groups_by_deck_encodes_html_and_reports():
    store = FakeCardStore(model_exists=False)
    out = WriteNotes(store)(
        [
            {
                "front": "spill the beans",
                "back": "irse de la lengua",
                "example": "He spilled\nthe beans",
                "deck": " Reading :: B1 :: Idioms ",
            },
            {"front": "dup one", "back": "x", "deck": "Reading::B1::Idioms"},
            {"front": "look up", "back": "buscar", "deck": "Grammar::A1::Verbs"},
        ]
    )
    assert out["ok"] and out["added"] == 2
    assert out["model_created"] is not None
    assert [w["deck"] for w in out["decks"]] == ["Reading::B1::Idioms", "Grammar::A1::Verbs"]
    first = out["decks"][0]
    assert first["asked"] == 2 and first["created"] == 1 and first["verified"] == 1
    assert out["refused"] == [{"front": "dup one", "error": "dup"}]
    deck, notes = store.added[0]
    assert notes[0]["fields"]["Ejemplo"] == "He spilled<br>the beans"
    assert notes[0]["model"] == "claude-fluent" and notes[0]["tags"] == ["claude-fluent"]


def test_write_validation():
    use_case = WriteNotes(FakeCardStore())
    with pytest.raises(NoCards):
        use_case([])
    with pytest.raises(TooManyCards):
        use_case([{"front": "a", "back": "b", "deck": "X"}] * (MAX_CARDS_PER_WRITE + 1))
    with pytest.raises(MalformedCard):
        use_case(["no soy un dict"])
    with pytest.raises(CardIncomplete):
        use_case([{"front": "a", "back": "  ", "deck": "X"}])
    with pytest.raises(InvalidDeckName):
        use_case([{"front": "a", "back": "b", "deck": "Reading::::Idioms"}])
