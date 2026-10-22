"""Adaptador del puerto ItemGenerator: los prompts que piden ejercicios con el
formato del TOEFL iBT del 21-01-2026, sobre el modelo inyectado.

Devuelve dicts crudos. Validarlos es trabajo del caso de uso y de las
entidades: acá solo se descarta lo que ni siquiera tiene la forma esperada.

Los ejemplos de los prompts son los del Practice Test 1 oficial de ETS. Son la
mejor descripción del formato que existe, y mostrarlos le cuesta al modelo
menos que entender una explicación.
"""

from collections.abc import Callable

from fluent.shared.errors import Upstream
from fluent.toefl.domain.catalog import SENTENCE_PATTERNS, pattern
from fluent.toefl.domain.errors import ModelFailed

Generate = Callable[..., tuple[dict, int]]

SYSTEM_PROMPT = (
    "You write practice items for the TOEFL iBT test. You answer only with the "
    "requested JSON object, with no commentary."
)

SENTENCE_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "enum": [p.key for p in SENTENCE_PATTERNS]},
                    "context": {"type": "string"},
                    "before": {"type": "string"},
                    "after": {"type": "string"},
                    "chunks": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["pattern", "context", "before", "after", "chunks"],
            },
        }
    },
    "required": ["items"],
}

PARAGRAPH_SCHEMA = {
    "type": "object",
    "properties": {
        "paragraphs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        }
    },
    "required": ["paragraphs"],
}

SENTENCE_PROMPT = """\
Write {count} "Build a Sentence" items for the TOEFL iBT (format from January 2026).

In the test, a person says a short line (the context). The test taker must answer
by putting word chunks in order to build one grammatical sentence. Some words of
the answer can be fixed before or after the chunks.

Official examples (context / before / chunks in the RIGHT order / after):
- "What was the highlight of your trip?" / "The" / tour guides | who | showed us around | the | old city | were / "fantastic."
- "I heard Anna got a promotion." / "" / do | you | know | if | she will be | moving to | a different department / "?"
- "I'm looking forward to the concert this weekend." / "" / what | time | does | it | start / "?"
- "How did you prepare for the exam?" / "I used" / the study guide | that | was provided | by | the professor / "."

Patterns (use these keys):
{patterns}

Rules:
- Level B1-B2, everyday or campus life, natural spoken English.
- 4 to 7 chunks per item; a chunk is one word or a short phrase.
- "chunks" go in the correct order. before + chunks + after must be exactly one
  grammatical sentence, and only ONE order of the chunks may be correct.
- "after" is usually just the final punctuation ("?" or ".").
- No chunk may repeat another one.
{focus}"""

PARAGRAPH_PROMPT = """\
Write {count} short paragraphs for the TOEFL iBT "Complete the Words" task
(format from January 2026).

Each paragraph is academic, like a textbook: biology, history, psychology,
geography, art, technology. 4 or 5 sentences, 70 to 90 words, level B1-B2.
The test removes the second half of every other word starting from the second
sentence, so the second and third sentences must be long and plain.

Official example:
"We know from drawings that have been preserved in caves for over 10,000 years
that early humans performed dances as a group activity. We might think that
prehistoric people concentrated only on basic survival. However, it is clear from
the record that dancing was important to them. They recorded more drawings of
dances than of any other group activity."

Rules:
- The first sentence introduces the topic.
- In the second and third sentences: no names of people or places, no numbers,
  no abbreviations, no hyphenated words.
- Use common academic words: connectors (however, although, therefore), verb
  forms (-ing, -ed), nouns and adjectives with suffixes (-tion, -al, -ic).
- Every paragraph on a different topic.
{focus}"""


def _patterns_block() -> str:
    return "\n".join(f"- {p.key}: {p.label}. {p.example}" for p in SENTENCE_PATTERNS)


def _focus(key: str | None, what: str) -> str:
    info = pattern(key) if key else None
    if info is None:
        return "- Mix the patterns evenly."
    return (
        f"- Focus: at least half of the {what} must practise {info.key} "
        f'("{info.label}"), for example: {info.example}'
    )


def _rows(result: dict, field: str) -> list[dict]:
    rows = result.get(field)
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


class LlmGenerator:
    def __init__(self, generate: Generate) -> None:
        self._generate = generate

    def sentences(self, count: int, focus: str | None) -> list[dict]:
        prompt = SENTENCE_PROMPT.format(
            count=count, patterns=_patterns_block(), focus=_focus(focus, "items")
        )
        return _rows(self._call(prompt, SENTENCE_SCHEMA), "items")

    def paragraphs(self, count: int, focus: str | None) -> list[dict]:
        prompt = PARAGRAPH_PROMPT.format(
            count=count, focus=_focus(focus, "second and third sentences")
        )
        return _rows(self._call(prompt, PARAGRAPH_SCHEMA), "paragraphs")

    def _call(self, prompt: str, schema: dict) -> dict:
        try:
            result, _ = self._generate(prompt, schema, system=SYSTEM_PROMPT)
        except Upstream as e:
            raise ModelFailed(f"claude -p failed: {e}") from e
        return result if isinstance(result, dict) else {}
