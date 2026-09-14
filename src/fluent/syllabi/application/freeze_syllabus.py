"""Caso de uso: congelar el temario de un nivel (tres borradores y una fusión).

Sólo llama al modelo si el nivel no tiene temario o si se pide regenerar. No
toca Anki: qué enseña un A1 no depende de tu colección."""

from fluent.cards.domain.decks import focus_for
from fluent.syllabi.domain.body import syllabus_body
from fluent.syllabi.domain.errors import ModelReturnedNothing, UnknownSkillOrLevel
from fluent.syllabi.domain.ports import Clock, SyllabusModel, SyllabusStore


class FreezeSyllabus:
    def __init__(self, store: SyllabusStore, model: SyllabusModel, clock: Clock) -> None:
        self._store = store
        self._model = model
        self._clock = clock

    def __call__(self, skill: str, level: str, regenerate: bool = False) -> dict:
        focus = focus_for(skill, level)
        if not focus:
            raise UnknownSkillOrLevel()
        skill, level = focus["skill"], focus["level"]
        path = self._store.path_for(skill, level)

        stored = None if regenerate else self._store.load(skill, level)
        if stored is not None:
            return syllabus_body(stored, path)

        built = self._model.build(skill, level)
        if not built["points"]:
            raise ModelReturnedNothing()
        stored = self._store.save(
            skill,
            level,
            built["points"],
            built["drafts"],
            self._clock.now().isoformat(timespec="seconds"),
        )
        return syllabus_body({**stored, "edited": False}, path)
