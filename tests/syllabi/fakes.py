from datetime import datetime


class FixedClock:
    def __init__(self, now: datetime = datetime(2026, 9, 13, 12, 0)) -> None:
        self.current = now

    def now(self) -> datetime:
        return self.current


class FakeSyllabusStore:
    def __init__(
        self, stored: dict | None = None, unreadable: bool = False, coverage: dict | None = None
    ) -> None:
        self.stored = stored
        self.unreadable = unreadable
        self.coverage = coverage
        self.saved: list[tuple] = []

    def status(self, skill, level):
        if self.unreadable:
            return "unreadable"
        return "ok" if self.stored else "missing"

    def load(self, skill, level):
        return None if self.unreadable else self.stored

    def save(self, skill, level, points, drafts, generated):
        self.stored = {
            "skill": skill,
            "level": level,
            "points": points,
            "drafts": drafts,
            "generated": generated,
        }
        self.saved.append(("syllabus", skill, level))
        return self.stored

    def path_for(self, skill, level):
        return f"/data/syllabus/{skill}-{level}.json"

    def load_coverage(self, skill, level, points):
        return self.coverage

    def save_coverage(self, skill, level, points, decks, computed):
        self.saved.append(("coverage", decks))
        return {"computed": computed, "decks": decks}


class FakeSyllabusModel:
    def __init__(self, points: list[dict] | None = None) -> None:
        self.points = points if points is not None else [{"point": "present simple"}]
        self.calls: list[tuple] = []

    def build(self, skill, level):
        self.calls.append(("build", skill, level))
        return {"points": self.points, "drafts": 3}

    def cover(self, skill, level, points, deck_topics, have):
        self.calls.append(("cover", deck_topics, have))
        return [
            {**p, "covered_by": deck_topics[0] if deck_topics else "", "note": ""} for p in points
        ]


class FakeDecks:
    def __init__(self, alive=True, stats=None, due=None, fronts=None) -> None:
        self.alive = alive
        self.stats = stats or []
        self.due = due or []
        self.fronts = fronts or {}

    def is_alive(self):
        return self.alive

    def deck_card_stats(self):
        return list(self.stats)

    def due_counts(self):
        return list(self.due)

    def deck_fronts(self, deck, limit):
        return self.fronts.get(deck, [])[:limit]
