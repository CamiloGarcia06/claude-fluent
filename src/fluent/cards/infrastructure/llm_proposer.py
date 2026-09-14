"""Adaptador del puerto Proposer sobre los módulos planos generate.py y
repair.py (prompts + `claude -p`). Un LLMError se convierte en ModelFailed."""

from fluent import generate, llm, repair
from fluent.cards.domain.errors import ModelFailed


class LlmProposer:
    def propose_terms(
        self, stuck: list[dict], catalog: dict, focus: dict | None, topic: str, have: list[str]
    ) -> dict:
        try:
            return generate.propose_terms(stuck, catalog, focus, topic=topic, have=have)
        except llm.LLMError as e:
            raise ModelFailed(f"claude -p failed: {e}") from e

    def propose_cards(self, term: str, catalog: dict, focus: dict | None) -> dict:
        try:
            return generate.propose_cards(term, catalog, focus=focus)
        except llm.LLMError as e:
            raise ModelFailed(f"claude -p failed: {e}") from e

    def propose_repair(self, note: dict) -> dict:
        try:
            return repair.propose(note)
        except llm.LLMError as e:
            raise ModelFailed(f"claude -p failed: {e}") from e
