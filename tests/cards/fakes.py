"""Fakes de los puertos de cards: la colección en memoria y un modelo guionado."""

from pathlib import Path

from fluent.cards.domain.errors import NoteNotFound
from fluent.collection.domain.review import Review


class FakeCardStore:
    def __init__(
        self,
        *,
        alive: bool = True,
        notes: dict[int, dict] | None = None,
        stats: list[dict] | None = None,
        due: list[dict] | None = None,
        reviews: list[Review] | None = None,
        summaries: dict[int, dict] | None = None,
        fronts: dict[str, list[str]] | None = None,
        model_exists: bool = True,
    ) -> None:
        self.alive = alive
        self.notes = notes or {}
        self.stats = stats or []
        self.due = due or []
        self.reviews = reviews or []
        self.summaries = summaries or {}
        self.fronts = fronts or {}
        self.model_exists = model_exists
        self.added: list[tuple[str, list[dict]]] = []
        self.updated: list[tuple[int, dict]] = []
        self.next_id = 1000

    def is_alive(self) -> bool:
        return self.alive

    def reviews_since(self, timestamp_ms: int) -> list[Review]:
        return [r for r in self.reviews if r.timestamp_ms >= timestamp_ms]

    def due_counts(self) -> list[dict]:
        return list(self.due)

    def deck_card_stats(self) -> list[dict]:
        return list(self.stats)

    def card_summaries(self, card_ids: list[int]) -> dict[int, dict]:
        return {i: self.summaries[i] for i in card_ids if i in self.summaries}

    def deck_fronts(self, deck: str, limit: int) -> list[str]:
        return self.fronts.get(deck, [])[:limit]

    def note_info(self, note_id: int) -> dict:
        if note_id not in self.notes:
            raise NoteNotFound(f"note {note_id} not found")
        return self.notes[note_id]

    def note_fields(self, note: dict) -> dict[str, str]:
        return {name: field["value"] for name, field in note["fields"].items()}

    def notes_alive(self, note_ids: list[int]) -> int:
        return len([i for i in note_ids if i in self.notes])

    def ensure_model(self, name, fields, templates, css) -> Path | None:
        return None if self.model_exists else Path("/tmp/model-x.json")

    def add_notes(self, deck: str, notes: list[dict]) -> tuple[list[int], Path, list[dict]]:
        self.added.append((deck, notes))
        ids = []
        for note in notes:
            if "dup" in note["fields"]["Front"]:
                continue
            self.next_id += 1
            self.notes[self.next_id] = {
                "noteId": self.next_id,
                "modelName": note["model"],
                "fields": {k: {"value": v} for k, v in note["fields"].items()},
            }
            ids.append(self.next_id)
        refused = [
            {"front": n["fields"]["Front"], "error": "dup"}
            for n in notes
            if "dup" in n["fields"]["Front"]
        ]
        return ids, Path(f"/tmp/created-{deck}.json"), refused

    def update_note_fields(self, note_id: int, fields: dict[str, str]) -> Path:
        self.updated.append((note_id, fields))
        for name, value in fields.items():
            self.notes[note_id]["fields"][name]["value"] = value
        return Path(f"/tmp/{note_id}-snap.json")


class FakeProposer:
    def __init__(
        self, terms: dict | None = None, cards: dict | None = None, repair: dict | None = None
    ) -> None:
        self.terms = terms or {"terms": [], "topic": "", "duration_ms": 1}
        self.cards = cards or {"candidates": [], "deck": None, "duration_ms": 1}
        self.repair = repair or {"proposal": {}, "duration_ms": 1}
        self.calls: list[tuple] = []

    def propose_terms(self, stuck, catalog, focus, topic, have):
        self.calls.append(("terms", stuck, focus, topic, have))
        return self.terms

    def propose_cards(self, term, catalog, focus):
        self.calls.append(("cards", term, focus))
        return self.cards

    def propose_repair(self, note):
        self.calls.append(("repair", note["noteId"]))
        return self.repair
