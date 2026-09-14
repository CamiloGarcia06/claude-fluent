"""Adaptador del puerto Coach sobre coach.py (prompts + claude -p)."""

from fluent import coach, llm
from fluent.writing.domain.errors import ModelFailed


class LlmCoach:
    max_text_chars = coach.MAX_TEXT_CHARS

    def turn(self, topic: str, level: str, turns: list[dict], text: str) -> dict:
        try:
            return coach.turn(topic, level, turns, text)
        except llm.LLMError as e:
            raise ModelFailed(f"claude -p failed: {e}") from e

    def close(self, topic: str, level: str, turns: list[dict]) -> dict:
        try:
            return coach.close(topic, level, turns)
        except llm.LLMError as e:
            raise ModelFailed(f"claude -p failed: {e}") from e
