"""Adaptador del puerto SyllabusModel: los prompts del temario sobre el modelo
inyectado."""

from collections.abc import Callable

from fluent.shared.errors import Upstream
from fluent.syllabi.domain.errors import ModelFailed
from fluent.syllabi.infrastructure import prompts

Generate = Callable[..., tuple[dict, int]]


class LlmSyllabusModel:
    def __init__(self, generate: Generate) -> None:
        self._generate = generate

    def build(self, skill: str, level: str) -> dict:
        try:
            return prompts.build_syllabus(self._generate, skill, level)
        except Upstream as e:
            raise ModelFailed(f"claude -p failed: {e}") from e

    def cover(
        self, skill: str, level: str, points: list[dict], deck_topics: list[str], have: list[str]
    ) -> list[dict]:
        try:
            return prompts.cover(self._generate, skill, level, points, deck_topics, have)
        except Upstream as e:
            raise ModelFailed(f"claude -p failed: {e}") from e
