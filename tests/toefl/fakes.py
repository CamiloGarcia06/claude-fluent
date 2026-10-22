from datetime import datetime

from fluent.toefl.domain.entities import (
    Attempt,
    SentenceItem,
    WordsItem,
    build_sentence_item,
    build_words_item,
)

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
    def __init__(self, sentences=None, words=None) -> None:
        self._sentences: list[SentenceItem] = list(sentences or [])
        self._words: list[WordsItem] = list(words or [])

    def sentences(self):
        return list(self._sentences)

    def words(self):
        return list(self._words)

    def add_sentences(self, items):
        return self._add(self._sentences, items)

    def add_words(self, items):
        return self._add(self._words, items)

    @staticmethod
    def _add(stored, items):
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
    def __init__(self, sentences=None, paragraphs=None) -> None:
        self._sentences = sentences or []
        self._paragraphs = paragraphs or []
        self.calls: list[tuple[str, int, str | None]] = []

    def sentences(self, count, focus):
        self.calls.append(("sentences", count, focus))
        return self._sentences

    def paragraphs(self, count, focus):
        self.calls.append(("paragraphs", count, focus))
        return self._paragraphs
