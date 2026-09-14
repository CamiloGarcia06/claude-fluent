"""Caso de uso: entregarle la sesión a Anki, en el mazo que tiene trabajo.
Sin `deck` gana el más cargado; con uno, solo si tiene pendientes."""

from fluent.collection.domain import analysis
from fluent.collection.domain.errors import AnkiNotRunning, NothingDue
from fluent.collection.domain.ports import ReviewLauncher


class OpenReview:
    def __init__(self, launcher: ReviewLauncher) -> None:
        self._launcher = launcher

    def __call__(self, deck: str | None = None) -> dict:
        if not self._launcher.is_alive():
            raise AnkiNotRunning()
        due = analysis.due_by_deck(self._launcher.due_counts())
        if deck is None:
            target = next((d for d in due["decks"] if d["due"] > 0), None)
        else:
            # Never forward an unchecked name: a deck that does not exist opens
            # the reviewer on nothing and looks like a hang.
            target = next((d for d in due["decks"] if d["deck"] == deck and d["due"] > 0), None)
        if target is None:
            raise NothingDue()
        self._launcher.open_deck_review(target["deck"])
        return {"ok": True, "deck": target["deck"], "due": target["due"]}
