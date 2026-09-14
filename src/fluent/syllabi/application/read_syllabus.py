"""Caso de uso: el temario congelado de un nivel, con la cobertura guardada si
sirve. Sin modelo, sin Anki: se lee del disco en milisegundos."""

from fluent.cards.domain.decks import focus_for
from fluent.syllabi.domain.body import empty_body, syllabus_body, with_coverage
from fluent.syllabi.domain.errors import UnknownSkillOrLevel
from fluent.syllabi.domain.ports import SyllabusStore


class ReadSyllabus:
    def __init__(self, store: SyllabusStore) -> None:
        self._store = store

    def __call__(self, skill: str, level: str) -> dict:
        focus = focus_for(skill, level)
        if not focus:
            raise UnknownSkillOrLevel()
        skill, level = focus["skill"], focus["level"]
        path = self._store.path_for(skill, level)

        # "No existe" y "existe y no se puede leer" son dos cosas distintas:
        # sobre un archivo roto, regenerar sería pisar trabajo tuyo.
        state = self._store.status(skill, level)
        stored = self._store.load(skill, level) if state == "ok" else None
        if stored is None:
            return empty_body(skill, level, state == "unreadable", path)

        cached = self._store.load_coverage(skill, level, stored["points"])
        if cached is None:
            return syllabus_body(stored, path)
        return syllabus_body(
            stored,
            path,
            with_coverage(stored, cached),
            {"computed": cached["computed"], "decks": cached["decks"]},
        )
