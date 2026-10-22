"""Adaptador del puerto Grader: corregir un email o una contribución a la
discusión con la rúbrica del TOEFL iBT, sobre el modelo inyectado.

**Las rúbricas son las de ETS, resumidas.** Las dos tareas puntúan de 0 a 5, y
lo que separa un 3 de un 4 no es la gramática sino si se cumplió la tarea y se
desarrollaron las ideas: por eso el prompt pone eso primero, y por eso la
devolución separa criterio por criterio en vez de dar solo una nota.

**La explicación va en español, las correcciones en inglés.** Quien lee es un
hispanohablante en nivel B1: el porqué tiene que entenderse a la primera.
"""

from collections.abc import Callable

from fluent.shared.errors import Upstream
from fluent.toefl.domain.catalog import EMAIL, WRITING_PATTERNS
from fluent.toefl.domain.errors import ModelFailed

Generate = Callable[..., tuple[dict, int]]

SYSTEM_PROMPT = (
    "You are a certified TOEFL iBT writing rater and a patient English teacher for "
    "Spanish speakers. You answer only with the requested JSON object, with no "
    "commentary."
)

_KEYS = [p.key for p in WRITING_PATTERNS]

SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "minimum": 0, "maximum": 5},
        "summary": {"type": "string"},
        "criteria": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "enum": _KEYS},
                    "ok": {"type": "boolean"},
                    "comment": {"type": "string"},
                },
                "required": ["key", "ok", "comment"],
            },
        },
        "corrections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "wrong": {"type": "string"},
                    "right": {"type": "string"},
                    "why": {"type": "string"},
                    "category": {"type": "string", "enum": _KEYS},
                },
                "required": ["wrong", "right", "why", "category"],
            },
        },
        "improved": {"type": "string"},
    },
    "required": ["score", "summary", "criteria", "corrections", "improved"],
}

EMAIL_RUBRIC = """\
Write an Email (0-5):
5 = fully successful: all three tasks are done and elaborated; appropriate social
    conventions (greeting, closing, polite requests); varied sentences and precise
    vocabulary; almost no errors.
4 = generally successful: all three tasks done, mostly elaborated; register mostly
    appropriate; some variety; a few errors that do not obscure meaning.
3 = partially successful: the tasks are addressed but at least one is weak or
    unclear; limited elaboration; noticeable errors; register partly off.
2 = mostly unsuccessful: one task missing or the email is hard to follow;
    frequent errors.
1 = unsuccessful: very little relevant content; serious and frequent errors.
0 = blank, off topic, or not in English."""

DISCUSSION_RUBRIC = """\
Write for an Academic Discussion (0-5):
5 = fully successful: a relevant, very clearly expressed contribution; the opinion
    is well elaborated with explanations, examples and details; it adds to the
    discussion instead of repeating the students; varied syntax and precise,
    idiomatic vocabulary; almost no errors.
4 = generally successful: relevant and well elaborated; some variety; a few errors.
3 = partially successful: relevant but explanations are missing, unclear or
    repeat the other students; limited variety; noticeable errors.
2 = mostly unsuccessful: little development; frequent errors that sometimes
    obscure meaning.
1 = unsuccessful: very little relevant content; serious errors.
0 = blank, off topic, copied from the prompt, or not in English.
An effective response has at least 100 words."""

PROMPT = """\
Rate this TOEFL iBT writing response exactly as an official rater would, then
teach the writer how to raise the score.

{rubric}

The task the writer saw:
---
{brief}
---

The writer's response:
---
{text}
---

Return:
- score: the official 0-5 score. Do not be generous: a B1 writer usually earns 2-3.
- summary: 1-2 sentences IN SPANISH: why this score, and the single change that
  would raise it most.
- criteria: one entry for EACH of these keys: {keys}.
  ok = false when that aspect costs points in this response. comment IN SPANISH,
  one short sentence, concrete (quote the response when useful). For an academic
  discussion, judge "register" as academic tone, not email conventions.
- corrections: at most 8, the ones that cost the most points first. "wrong" must
  be copied EXACTLY from the response (a few words, not a whole paragraph);
  "right" is the corrected version; "why" IN SPANISH, one sentence, the rule.
- improved: the same response rewritten at level 5, keeping the writer's ideas
  and structure, about the same length. In English.
- Never invent names, places or facts the task did not give: if the recipient
  has no name, use a greeting that fits ("Dear Editor", "Dear Sir or Madam").
"""


class LlmGrader:
    def __init__(self, generate: Generate) -> None:
        self._generate = generate

    def grade(self, kind: str, brief: str, text: str) -> dict:
        prompt = PROMPT.format(
            rubric=EMAIL_RUBRIC if kind == EMAIL else DISCUSSION_RUBRIC,
            brief=brief,
            text=text,
            keys=", ".join(_KEYS),
        )
        try:
            result, _ = self._generate(prompt, SCHEMA, system=SYSTEM_PROMPT)
        except Upstream as e:
            raise ModelFailed(f"claude -p failed: {e}") from e
        return result if isinstance(result, dict) else {}
