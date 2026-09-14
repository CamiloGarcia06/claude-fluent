"""Adaptador del puerto Coach: los prompts de la práctica sobre el modelo
inyectado."""

from collections.abc import Callable

from fluent.shared.errors import Upstream
from fluent.writing.domain.errors import ModelFailed
from fluent.writing.infrastructure import coach

Generate = Callable[..., tuple[dict, int]]


class LlmCoach:
    max_text_chars = coach.MAX_TEXT_CHARS

    def __init__(self, generate: Generate) -> None:
        self._generate = generate

    def turn(self, topic: str, level: str, turns: list[dict], text: str) -> dict:
        try:
            return coach.turn(self._generate, topic, level, turns, text)
        except Upstream as e:
            raise ModelFailed(f"claude -p failed: {e}") from e

    def close(self, topic: str, level: str, turns: list[dict]) -> dict:
        try:
            return coach.close(self._generate, topic, level, turns)
        except Upstream as e:
            raise ModelFailed(f"claude -p failed: {e}") from e
