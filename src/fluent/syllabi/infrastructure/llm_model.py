"""Adaptador del puerto SyllabusModel sobre generate.py (prompts + claude -p)."""

from fluent import generate, llm
from fluent.syllabi.domain.errors import ModelFailed


class LlmSyllabusModel:
    def build(self, skill: str, level: str) -> dict:
        try:
            return generate.build_syllabus(skill, level)
        except llm.LLMError as e:
            raise ModelFailed(f"claude -p failed: {e}") from e

    def cover(
        self, skill: str, level: str, points: list[dict], deck_topics: list[str], have: list[str]
    ) -> list[dict]:
        try:
            return generate.cover(skill, level, points, deck_topics, have)
        except llm.LLMError as e:
            raise ModelFailed(f"claude -p failed: {e}") from e
