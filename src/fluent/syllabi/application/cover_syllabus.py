"""Caso de uso: qué mazo de los tuyos cubre cada punto del temario.

Los puntos se leen del disco y no del cuerpo del pedido: un punto inventado
queda fuera y uno saltado aparece igual, sin cubrir. Lo único que escribe es la
cobertura, en su propio archivo."""

from fluent.cards.domain.decks import deck_totals_at, decks_at, focus_for
from fluent.collection.domain import analysis
from fluent.syllabi.domain.body import syllabus_body
from fluent.syllabi.domain.errors import AnkiNotRunning, NoSyllabusYet, UnknownSkillOrLevel
from fluent.syllabi.domain.ports import Clock, DeckReader, SyllabusModel, SyllabusStore

# How many existing cards of a level the model is shown, shared among its decks.
FRONTS_FOR_PROMPT = 60


class CoverSyllabus:
    def __init__(
        self, store: SyllabusStore, model: SyllabusModel, decks: DeckReader, clock: Clock
    ) -> None:
        self._store = store
        self._model = model
        self._decks = decks
        self._clock = clock

    def __call__(self, skill: str, level: str) -> dict:
        focus = focus_for(skill, level)
        if not focus:
            raise UnknownSkillOrLevel()
        if not self._decks.is_alive():
            raise AnkiNotRunning()
        skill, level = focus["skill"], focus["level"]
        stored = self._store.load(skill, level)
        if stored is None:
            raise NoSyllabusYet()

        catalog = analysis.catalog(self._decks.deck_card_stats(), self._decks.due_counts())
        decks = decks_at(catalog, focus)
        totals = deck_totals_at(catalog, focus)

        # Repartida entre los mazos y no por mazo: un tope por mazo dejaría al
        # último sin una sola tarjeta a la vista, e invisible se marcaría como
        # no cubierto.
        per_deck = max(4, FRONTS_FOR_PROMPT // max(1, len(decks)))
        have: list[str] = []
        for deck in decks:
            topic = deck.split("::")[-1]
            have += [f"{topic}: {front}" for front in self._decks.deck_fronts(deck, limit=per_deck)]

        points = self._model.cover(
            skill, level, stored["points"], [d.split("::")[-1] for d in decks], have
        )
        saved = self._store.save_coverage(
            skill, level, points, totals, self._clock.now().isoformat(timespec="seconds")
        )
        return syllabus_body(
            stored,
            self._store.path_for(skill, level),
            points,
            {"computed": saved["computed"], "decks": saved["decks"]},
        )
