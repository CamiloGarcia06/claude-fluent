"""Adaptador del puerto ItemGenerator: los prompts que piden ejercicios y
enunciados con el formato del TOEFL iBT del 21-01-2026, sobre el modelo inyectado.

Devuelve dicts crudos. Validarlos es trabajo del caso de uso y de las
entidades: acá solo se descarta lo que ni siquiera tiene la forma esperada.

Los ejemplos de los prompts son los del Practice Test 1 oficial de ETS. Son la
mejor descripción del formato que existe, y mostrarlos le cuesta al modelo
menos que entender una explicación.
"""

from collections.abc import Callable

from fluent.shared.errors import Upstream
from fluent.toefl.domain.catalog import (
    DISCUSSION,
    EMAIL,
    SENTENCE,
    SENTENCE_PATTERNS,
    WORDS,
    pattern,
)
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


EMAIL_SCHEMA = {
    "type": "object",
    "properties": {
        "prompts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "situation": {"type": "string"},
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "bullets": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["situation", "to", "subject", "bullets"],
            },
        }
    },
    "required": ["prompts"],
}

DISCUSSION_SCHEMA = {
    "type": "object",
    "properties": {
        "prompts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "course": {"type": "string"},
                    "professor": {"type": "string"},
                    "posts": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "text": {"type": "string"},
                            },
                            "required": ["name", "text"],
                        },
                    },
                },
                "required": ["course", "professor", "posts"],
            },
        }
    },
    "required": ["prompts"],
}

EMAIL_PROMPT = """\
Write {count} "Write an Email" prompts for the TOEFL iBT (format from January 2026).
The test taker has 7 minutes to write the email.

Official example:
situation: "A new poetry magazine has asked its readers for submissions, and you
decided to submit two of your poems. However, you had a problem using the online
submission form, and you are not certain that your submissions were received.
Write an email to the editor of the magazine."
to: "editor@sunshinepoetrymagazine.com"
subject: "Problem using submission form"
bullets: ["Tell the editor what you like about the new magazine.",
          "Describe the problem you experienced.",
          "Ask about the status of your submissions."]

Rules:
- Everyday situations with someone the writer does not know well: a manager, a
  landlord, a professor, a company, an event organiser. Different in each prompt.
- Exactly 3 bullets, each a different action: describe, explain, ask, suggest,
  request, apologise. Each bullet one short sentence.
- The situation is 2-3 sentences and ends with "Write an email to …".
- "to" is a realistic email address; "subject" is short.
"""

DISCUSSION_PROMPT = """\
Write {count} "Write for an Academic Discussion" prompts for the TOEFL iBT
(format from January 2026). The test taker has 10 minutes and should write at
least 100 words.

Official example:
course: "social studies"
professor: "Volunteerism refers to the act of offering your time and service
without financial compensation to benefit a community, organization, or cause.
While many people volunteer mainly to help others, some institutions have
mandatory volunteer programs. High schools are one example, where students may be
required to complete a certain number of volunteer hours to graduate. What do you
think? Should high school students be required to do volunteer work? Why or why not?"
posts: [
  {{"name": "Claire", "text": "Yes, I think high schools should require volunteer
  hours because it helps students build a sense of civic responsibility. …"}},
  {{"name": "Andrew", "text": "I don't think volunteer hours should be required
  because many students already have limited free time. …"}}
]

Rules:
- The professor explains the topic in 2-3 sentences and ends with a clear
  question that has more than one reasonable answer.
- Exactly 2 student posts of 2-3 sentences each, with different opinions and
  different first names.
- Topics from university courses: education, technology, business, environment,
  psychology, urban planning, media. Different in each prompt.
"""


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

    def generate(self, kind: str, count: int, focus: str | None) -> list[dict]:
        """El foco solo se usa en los ejercicios cerrados: en writing el criterio
        débil (el tono, el desarrollo) no depende del enunciado, sino de cómo
        escribís cualquiera."""
        if kind == SENTENCE:
            prompt = SENTENCE_PROMPT.format(
                count=count, patterns=_patterns_block(), focus=_focus(focus, "items")
            )
            return _rows(self._call(prompt, SENTENCE_SCHEMA), "items")
        if kind == WORDS:
            prompt = PARAGRAPH_PROMPT.format(
                count=count, focus=_focus(focus, "second and third sentences")
            )
            return _rows(self._call(prompt, PARAGRAPH_SCHEMA), "paragraphs")
        if kind == EMAIL:
            return _rows(self._call(EMAIL_PROMPT.format(count=count), EMAIL_SCHEMA), "prompts")
        if kind == DISCUSSION:
            prompt = DISCUSSION_PROMPT.format(count=count)
            return _rows(self._call(prompt, DISCUSSION_SCHEMA), "prompts")
        return []

    def _call(self, prompt: str, schema: dict) -> dict:
        try:
            result, _ = self._generate(prompt, schema, system=SYSTEM_PROMPT)
        except Upstream as e:
            raise ModelFailed(f"claude -p failed: {e}") from e
        return result if isinstance(result, dict) else {}
