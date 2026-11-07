"""Adaptador del puerto Grader: corregir un email o una contribución a la
discusión con la rúbrica del TOEFL iBT, sobre el modelo inyectado.

**Las rúbricas son las de ETS, resumidas.** Las dos tareas puntúan de 0 a 5, y
lo que separa un 3 de un 4 no es la gramática sino si se cumplió la tarea y se
desarrollaron las ideas: por eso el prompt pone eso primero, y por eso la
devolución separa criterio por criterio en vez de dar solo una nota.

**Además de la nota, el nivel del marco europeo (A1-C1).** Es lo que pide el
requisito de la maestría (B1), y la nota de ETS no lo dice. El texto B1, que no
es del TOEFL, se puntúa con los criterios de Cambridge B1 Preliminary.

**La explicación va en español, las correcciones en inglés.** Quien lee es un
hispanohablante en nivel B1: el porqué tiene que entenderse a la primera.
"""

from collections.abc import Callable

from fluent.shared.errors import Upstream
from fluent.toefl.domain.catalog import B1, EMAIL, WRITING_PATTERNS
from fluent.toefl.domain.errors import ModelFailed
from fluent.toefl.domain.writing import LEVELS

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
        "level": {"type": "string", "enum": list(LEVELS)},
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
    "required": ["score", "level", "summary", "criteria", "corrections", "improved"],
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

B1_RUBRIC = """\
Cambridge B1 Preliminary writing (overall 0-5, from the four Cambridge subscales:
Content, Communicative Achievement, Organisation, Language):
5 = all content is relevant and every note or point is covered; the target reader
    is fully informed; the text is well organised with a variety of linking
    words; a range of everyday vocabulary and simple and some complex grammar
    forms used with a good degree of control; errors do not impede communication.
4 = minor omissions; reader informed; generally well organised and coherent;
    a range of vocabulary and simple grammar with some complex forms; errors
    rarely impede.
3 = relevant with some omissions; the reader is on the whole informed; connected
    using basic, high-frequency linking words; everyday vocabulary generally
    appropriate, simple grammar with a good degree of control.
2 = irrelevances or misinterpretation; reader minimally informed; basic linking
    (and, but, because); errors sometimes impede meaning.
1 = little relevant content; reader hardly informed; very limited linking;
    frequent errors that impede meaning.
0 = blank, off topic, or not in English."""

LEVEL_GUIDE = """\
CEFR level of the writing (A1, A2, B1, B2 or C1), as a Cambridge examiner would
place it:
- A2: short simple sentences joined with and, but, because; everyday vocabulary;
  errors are frequent and sometimes obscure the meaning.
- B1: a connected text in paragraphs; opinions with reasons and examples; some
  variety of tenses (past, present perfect, future, a conditional) and some
  complex sentences (who/which/that); errors are noticeable but do not stop
  the reader from understanding.
- B2: clear, detailed and well organised; a good range of linking words and
  structures; errors are rare and do not lead to misunderstanding.
Judge the language actually shown, not the effort. A text that is too short to
show B1 features cannot be B1."""

PROMPT = """\
Rate this writing response exactly as an official rater would, then teach the
writer how to raise the score.

{rubric}

{level_guide}

The task the writer saw:
---
{brief}
---

The writer's response:
---
{text}
---

Return:
- score: the official 0-5 score. Do not be generous: a B1 writer usually earns 2-3
  on the TOEFL tasks.
- level: the CEFR level from the guide above. Do not be generous.
- summary: 1-2 sentences IN SPANISH: why this score, and the single change that
  would raise it most.
- criteria: one entry for EACH of these keys: {keys}.
  ok = false when that aspect costs points in this response. comment IN SPANISH,
  one short sentence, concrete (quote the response when useful). For an academic
  discussion, judge "register" as academic tone, not email conventions.
- corrections: at most 8, the ones that cost the most points first. "wrong" must
  be copied EXACTLY from the response (a few words, not a whole paragraph);
  "right" is the corrected version; "why" IN SPANISH, one sentence, the rule.
- improved: the same response rewritten ONE CEFR level above the writer's (an
  A2 text as B1, a B1 text as B2), keeping the writer's ideas and structure,
  about the same length, so the next step is reachable. In English.
- Never invent names, places or facts the task did not give: if the recipient
  has no name, use a greeting that fits ("Dear Editor", "Dear Sir or Madam").
"""


class LlmGrader:
    def __init__(self, generate: Generate) -> None:
        self._generate = generate

    def grade(self, kind: str, brief: str, text: str) -> dict:
        rubric = {EMAIL: EMAIL_RUBRIC, B1: B1_RUBRIC}.get(kind, DISCUSSION_RUBRIC)
        prompt = PROMPT.format(
            rubric=rubric,
            level_guide=LEVEL_GUIDE,
            brief=brief,
            text=text,
            keys=", ".join(_KEYS),
        )
        try:
            result, _ = self._generate(prompt, SCHEMA, system=SYSTEM_PROMPT)
        except Upstream as e:
            raise ModelFailed(f"claude -p failed: {e}") from e
        return result if isinstance(result, dict) else {}
