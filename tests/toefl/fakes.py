from datetime import datetime

from fluent.toefl.domain.entities import (
    Attempt,
    SentenceItem,
    WordsItem,
    build_sentence_item,
    build_words_item,
)
from fluent.toefl.domain.writing import build_discussion_prompt, build_email_prompt

# El párrafo del Practice Test 1 de ETS: sus diez huecos son la respuesta oficial.
ETS_PARAGRAPH = (
    "We know from drawings that have been preserved in caves for over 10,000 years "
    "that early humans performed dances as a group activity. We might think that "
    "prehistoric people concentrated only on basic survival. However, it is clear from "
    "the record that dancing was important to them. They recorded more drawings of "
    "dances than of any other group activity."
)
ETS_MISSING = ["ght", "at", "ple", "ly", "sic", "ever", "s", "om", "ord", "cing"]


class FixedClock:
    def __init__(self, now: datetime = datetime(2026, 10, 22, 18, 0)) -> None:
        self.current = now

    def now(self) -> datetime:
        return self.current


def sentence(pattern="indirect_question", chunks=None, before="", after="?") -> SentenceItem:
    return build_sentence_item(
        pattern,
        "I heard Anna got a promotion.",
        before,
        after,
        chunks or ["do", "you", "know", "if", "she will be", "moving to", "a different department"],
    )


def words(text: str = ETS_PARAGRAPH) -> WordsItem:
    return build_words_item(text)


class FakeBank:
    """Un banco en memoria por tipo. `sentences=` y `words=` son atajos."""

    def __init__(self, sentences=None, words=None, emails=None, discussions=None) -> None:
        self.stored: dict[str, list] = {
            "sentence": list(sentences or []),
            "words": list(words or []),
            "email": list(emails or []),
            "discussion": list(discussions or []),
        }

    def items(self, kind):
        return list(self.stored[kind])

    def add(self, kind, items):
        stored = self.stored[kind]
        seen = {i.id for i in stored}
        before = len(stored)
        for item in items:
            if item.id not in seen:
                seen.add(item.id)
                stored.append(item)
        return len(stored) - before


class FakeLog:
    def __init__(self, attempts=None) -> None:
        self.attempts: list[Attempt] = list(attempts or [])

    def append(self, attempts):
        self.attempts += attempts

    def recent(self):
        return list(self.attempts)


def misses(kind: str, pattern: str, wrong: int, right: int = 0) -> list[Attempt]:
    return [Attempt(kind, f"x{i}", pattern, False, "t") for i in range(wrong)] + [
        Attempt(kind, f"y{i}", pattern, True, "t") for i in range(right)
    ]


class FakeGenerator:
    def __init__(self, **by_kind) -> None:
        self._by_kind = by_kind
        self.calls: list[tuple[str, int, str | None]] = []

    def generate(self, kind, count, focus):
        self.calls.append((kind, count, focus))
        return self._by_kind.get(kind, [])


class FakeSubmissions:
    def __init__(self, rows=None) -> None:
        self.rows: list[dict] = list(rows or [])

    def append(self, submission):
        self.rows.append(submission)

    def recent(self, kind):
        return [r for r in self.rows if r.get("kind") == kind]


class FakeGrader:
    def __init__(self, result: dict) -> None:
        self.result = result
        self.calls: list[tuple[str, str, str]] = []

    def grade(self, kind, brief, text):
        self.calls.append((kind, brief, text))
        return self.result


def email_prompt():
    return build_email_prompt(
        "A new poetry magazine asked for submissions. Write an email to the editor.",
        "editor@sunshinepoetrymagazine.com",
        "Problem using submission form",
        [
            "Tell the editor what you like about the new magazine.",
            "Describe the problem you experienced.",
            "Ask about the status of your submissions.",
        ],
    )


def discussion_prompt():
    return build_discussion_prompt(
        "social studies",
        "Should high school students be required to do volunteer work? Why or why not?",
        [
            {"name": "Claire", "text": "Yes, it builds civic responsibility."},
            {"name": "Andrew", "text": "No, students already have limited free time."},
        ],
    )
