from datetime import datetime

from fluent.toefl.domain.entities import (
    Attempt,
    SentenceItem,
    WordsItem,
    build_sentence_item,
    build_words_item,
)
from fluent.toefl.domain.reading import ReadingItem, build_reading_item
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

    def __init__(
        self, sentences=None, words=None, emails=None, discussions=None, daily=None, academic=None
    ) -> None:
        self.stored: dict[str, list] = {
            "sentence": list(sentences or []),
            "words": list(words or []),
            "email": list(emails or []),
            "discussion": list(discussions or []),
            "daily": list(daily or []),
            "academic": list(academic or []),
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


# "The Mirror Test", del Practice Test 1 de ETS, con cuatro de sus preguntas.
MIRROR_TEXT = (
    "Very young children cannot recognize themselves in a mirror; they usually achieve "
    "this milestone around 18 months of age. The ability to recognize oneself in the "
    "mirror is considered to be a key component of self-awareness and consciousness for "
    "humans. But what about animals?\n\n"
    "For many years, scientists have known that members of the great ape family could "
    "recognize themselves in mirrors. They measured this by the mirror test, which "
    "involved putting a colored mark on an ape's body, and then showing the ape its "
    "reflection in a mirror. If the ape tried to remove the mark on its own body, the "
    "scientists knew that the ape was recognizing its reflection.\n\n"
    "Apes are close relatives of humans, but in recent years, scientists have discovered "
    "that other animals also pass the mirror test. Elephants and dolphins have shown "
    "signs of self-recognition. In a more recent experiment, a type of fish called the "
    "cleaner fish tried to scrape a mark off its body when it saw itself in the mirror. "
    "This suggests that even less intelligent animals may possess more self-awareness "
    "than previously suspected."
)


def mirror_questions() -> list[dict]:
    return [
        {
            "pattern": "main_idea",
            "prompt": "What is the passage mainly about?",
            "options": [
                "Stages of early childhood development",
                "Research on animal cognition",
                "Differences between apes, elephants, and dolphins",
                "Recent experiments on fish",
            ],
            "answer": 1,
            "evidence": "other animals also pass the mirror test",
            "why": "Los tres párrafos hablan de animales que se reconocen.",
        },
        {
            "pattern": "word_meaning",
            "prompt": 'The word "milestone" is closest in meaning to',
            "options": ["accomplishment", "distance", "weight", "discovery"],
            "answer": 0,
            "evidence": "they usually achieve this milestone around 18 months of age",
            "why": "Se logra (achieve) a cierta edad: es un logro.",
        },
        {
            "pattern": "detail",
            "prompt": "Why did scientists put colored marks on animals' bodies?",
            "options": [
                "To track the animals' movements",
                "To determine whether the animals recognized themselves",
                "To tell the animals apart",
                "To test whether animals see colors",
            ],
            "answer": 1,
            "evidence": "the scientists knew that the ape was recognizing its reflection",
            "why": "La marca servía para ver si el animal se reconocía.",
        },
        {
            "pattern": "author_purpose",
            "prompt": "Why does the author mention cleaner fish?",
            "options": [
                "To suggest that many animals may possess self-awareness",
                "To imply that ocean animals are highly intelligent",
                "To show a flaw in a recent experiment",
                "To give an example of an animal that does not recognize itself",
            ],
            "answer": 0,
            "evidence": "even less intelligent animals may possess more self-awareness",
            "why": "El pez es el ejemplo de que hasta animales menos inteligentes se reconocen.",
        },
    ]


def mirror(questions=None) -> ReadingItem:
    return build_reading_item(
        "academic", "biology", "The Mirror Test", MIRROR_TEXT, questions or mirror_questions()
    )


def right_answers(item: ReadingItem) -> list[int]:
    return [q.answer for q in item.questions]
