"""Fake del puerto CollectionReader: listas en memoria, sin Anki."""

from fluent.collection.domain.review import Review


class FakeCollection:
    def __init__(
        self,
        *,
        alive: bool = True,
        reviews: list[Review] | None = None,
        due: list[dict] | None = None,
        stats: list[dict] | None = None,
        summaries: dict[int, dict] | None = None,
    ) -> None:
        self.alive = alive
        self.reviews = reviews or []
        self.due = due or []
        self.stats = stats or []
        self.summaries = summaries or {}
        self.asked_since: list[int] = []

    def is_alive(self) -> bool:
        return self.alive

    def reviews_since(self, timestamp_ms: int) -> list[Review]:
        self.asked_since.append(timestamp_ms)
        return [r for r in self.reviews if r.timestamp_ms >= timestamp_ms]

    def due_counts(self) -> list[dict]:
        return list(self.due)

    def deck_card_stats(self) -> list[dict]:
        return list(self.stats)

    def card_summaries(self, card_ids: list[int]) -> dict[int, dict]:
        return {i: self.summaries[i] for i in card_ids if i in self.summaries}
