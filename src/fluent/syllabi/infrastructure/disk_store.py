"""Adaptador del puerto SyllabusStore sobre los archivos JSON de data/syllabus/
(módulo `disk`, en esta misma funcionalidad)."""

from fluent.syllabi.infrastructure import disk


class DiskSyllabusStore:
    def status(self, skill: str, level: str) -> str:
        return disk.status(skill, level)

    def load(self, skill: str, level: str) -> dict | None:
        return disk.load(skill, level)

    def save(self, skill: str, level: str, points: list[dict], drafts: int, generated: str) -> dict:
        return disk.save(skill, level, points, drafts, generated)

    def path_for(self, skill: str, level: str) -> str:
        return str(disk.path_for(skill, level))

    def load_coverage(self, skill: str, level: str, points: list[dict]) -> dict | None:
        return disk.load_coverage(skill, level, points)

    def save_coverage(
        self, skill: str, level: str, points: list[dict], decks: dict[str, int], computed: str
    ) -> dict:
        return disk.save_coverage(skill, level, points, decks, computed)
