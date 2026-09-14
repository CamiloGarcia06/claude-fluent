"""Adaptador del puerto SyllabusStore sobre el módulo plano syllabus.py
(archivos JSON en data/syllabus/)."""

from fluent import syllabus


class DiskSyllabusStore:
    def status(self, skill: str, level: str) -> str:
        return syllabus.status(skill, level)

    def load(self, skill: str, level: str) -> dict | None:
        return syllabus.load(skill, level)

    def save(self, skill: str, level: str, points: list[dict], drafts: int, generated: str) -> dict:
        return syllabus.save(skill, level, points, drafts, generated)

    def path_for(self, skill: str, level: str) -> str:
        return str(syllabus.path_for(skill, level))

    def load_coverage(self, skill: str, level: str, points: list[dict]) -> dict | None:
        return syllabus.load_coverage(skill, level, points)

    def save_coverage(
        self, skill: str, level: str, points: list[dict], decks: dict[str, int], computed: str
    ) -> dict:
        return syllabus.save_coverage(skill, level, points, decks, computed)
