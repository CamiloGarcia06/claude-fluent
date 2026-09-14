"""Adaptador del puerto Proposer: los prompts de tarjetas y de reparación sobre
el modelo inyectado (`generate`) y la colección (`client`). Un fallo del modelo
llega como ModelError (Upstream → 502); se conserva ModelFailed por nombre."""

from collections.abc import Callable
from typing import Protocol

from fluent.cards.domain.errors import ModelFailed
from fluent.cards.infrastructure import prompts, repair_prompt
from fluent.shared.errors import Upstream

Generate = Callable[..., tuple[dict, int]]


class AnkiApi(Protocol):
    def existing_with_front(self, text: str) -> list[dict]: ...
    def note_fields(self, note: dict) -> dict[str, str]: ...
    def reviews_of_card(self, card_id: int) -> list[dict]: ...


class LlmProposer:
    def __init__(self, generate: Generate, client: AnkiApi) -> None:
        self._generate = generate
        self._client = client

    def propose_terms(
        self, stuck: list[dict], catalog: dict, focus: dict | None, topic: str, have: list[str]
    ) -> dict:
        try:
            return prompts.propose_terms(
                self._generate, stuck, catalog, focus, topic=topic, have=have
            )
        except Upstream as e:
            raise ModelFailed(f"claude -p failed: {e}") from e

    def propose_cards(self, term: str, catalog: dict, focus: dict | None) -> dict:
        try:
            return prompts.propose_cards(self._generate, self._client, term, catalog, focus=focus)
        except Upstream as e:
            raise ModelFailed(f"claude -p failed: {e}") from e

    def propose_repair(self, note: dict) -> dict:
        try:
            return repair_prompt.propose(self._generate, self._client, note)
        except Upstream as e:
            raise ModelFailed(f"claude -p failed: {e}") from e
