from datetime import datetime

from fluent.writing.domain.errors import ModelFailed


class FixedClock:
    def __init__(self, now: datetime = datetime(2026, 9, 13, 12, 0)) -> None:
        self.current = now

    def now(self) -> datetime:
        return self.current


def turn_dict(index: int, text: str) -> dict:
    return {
        "index": index,
        "at": "t",
        "text": text,
        "state": "pending",
        "reply": "",
        "question": "",
        "alternative": "",
        "corrections": [],
        "error": "",
        "duration_ms": None,
    }


class FakeSessions:
    max_turns = 3

    def __init__(self, sessions: dict[str, dict] | None = None) -> None:
        self.sessions = sessions or {}
        self.saved: list[str] = []
        self.counter = 0

    def valid_id(self, value) -> str:
        text = str(value or "")
        if len(text) != 15:
            raise ValueError("id de sesión inválido")
        return text

    def load(self, session_id):
        return self.sessions.get(session_id)

    def save(self, session):
        self.saved.append(session["id"])
        return session

    def new_session(self, topic, level):
        self.counter += 1
        sid = f"20260913-12000{self.counter}"
        self.sessions[sid] = {
            "id": sid,
            "topic": topic,
            "level": level,
            "closed": False,
            "closed_at": None,
            "abandoned": False,
            "turns": [],
            "analysis": None,
        }
        return self.sessions[sid]

    def open_session(self):
        return next((s for s in self.sessions.values() if not s["closed"]), None)

    def last_closed(self):
        return next((s for s in self.sessions.values() if s["closed"]), None)

    def recent_topics(self):
        return [s["topic"] for s in self.sessions.values()]

    def append_turn(self, session, text):
        turn = turn_dict(len(session["turns"]), text)
        session["turns"].append(turn)
        return turn

    def retry_turn(self, session, index, text):
        turn = session["turns"][index]
        if turn["state"] == "done":
            raise ValueError("ese turno ya está respondido")
        turn.update(text=text, state="pending", error="")
        return turn

    def finish_turn(self, session, index, answer, error=""):
        turn = session["turns"][index]
        if answer is None:
            turn.update(state="failed", error=error)
        else:
            turn.update(
                state="done",
                error="",
                **{
                    k: answer[k]
                    for k in ("reply", "question", "alternative", "corrections", "duration_ms")
                },
            )
        return turn


class FakePatterns:
    threshold = 3

    def __init__(self, stored: dict | None = None) -> None:
        self.stored = stored or {"patterns": {}, "unmatched": {}}
        self.written: list[dict] = []

    def read(self):
        return self.stored

    def write(self, stored):
        self.stored = stored
        self.written.append(stored)
        return stored

    def count(self, stored, areas, unmatched, session_id):
        patterns = {k: dict(v) for k, v in stored["patterns"].items()}
        for area in areas:
            key = area.get("pattern")
            if key:
                entry = patterns.setdefault(key, {"sessions": [], "carded": None})
                entry["sessions"] = sorted(set(entry["sessions"]) | {session_id})
        misses = dict(stored["unmatched"])
        for u in unmatched:
            misses[u] = misses.get(u, 0) + 1
        return {"patterns": patterns, "unmatched": misses}

    def listing(self, stored):
        return [
            {
                "key": k,
                "count": len(v["sessions"]),
                "ready": len(v["sessions"]) >= self.threshold,
                "carded": v.get("carded"),
            }
            for k, v in stored["patterns"].items()
        ]

    def mark(self, stored, key, action, stamp):
        if action not in ("carded", "reset", "uncard"):
            raise ValueError("la acción tiene que ser carded, reset o uncard")
        if key not in stored["patterns"]:
            raise ValueError("ese patrón todavía no te apareció")
        patterns = {k: dict(v) for k, v in stored["patterns"].items()}
        patterns[key]["carded"] = stamp if action == "carded" else None
        return {"patterns": patterns, "unmatched": dict(stored["unmatched"])}

    def stamp(self):
        return "20260913-120000"


class FakeCoach:
    max_text_chars = 20

    def __init__(self, fail: bool = False, analysis: dict | None = None) -> None:
        self.fail = fail
        self.analysis = analysis or {
            "areas": [{"pattern": "articles", "examples": []}],
            "unmatched": ["x"],
        }
        self.calls: list[tuple] = []

    def turn(self, topic, level, turns, text):
        self.calls.append(("turn", topic, level, len(turns), text))
        if self.fail:
            raise ModelFailed("claude -p failed: boom")
        return {
            "reply": f"re: {text}",
            "question": "?",
            "alternative": "",
            "corrections": [],
            "duration_ms": 5,
        }

    def close(self, topic, level, turns):
        self.calls.append(("close", len(turns)))
        return self.analysis
