from fluent.collection.application.open_add_cards import OpenAddCards

from .test_open_review import FakeLauncher


def test_add_cards_opens_the_dialog():
    launcher = FakeLauncher()
    assert OpenAddCards(launcher)() == {"ok": True} and launcher.opened == ["add"]
