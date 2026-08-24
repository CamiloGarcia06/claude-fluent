"""Generating cards with the model. Proposes only — see snapshot.py for writes.

Two questions get asked of `claude -p`, and they are asked separately:

    propose_terms()  what is worth studying, read off the cards you keep
                     failing and the levels with no deck at all
    propose_cards()  for one term, the cards themselves and where they belong

One call per term, never one call for the batch. A batch call takes as long as
the sum of its parts with nothing to show meanwhile, and one bad term poisons
the whole answer; per term, the screen fills in as each one lands and a failure
costs that term only.
"""
import re

import analysis
import anki
import llm

# The note type this app writes. Stock Basic has no room for an example
# sentence, and the example is what makes a vocabulary card usable instead of
# a word pair you can recite without understanding.
MODEL_NAME = "claude-fluent"
MODEL_FIELDS = ["Front", "Back", "Ejemplo"]

# One card per note, English -> Spanish. The reverse direction is a different
# skill and deserves its own deck rather than a second template that doubles
# every count silently.
MODEL_TEMPLATES = [{
    "Name": "Reconocer",
    "Front": "{{Front}}",
    "Back": "{{FrontSide}}\n<hr id=answer>\n{{Back}}\n"
            "{{#Ejemplo}}<div class=\"ejemplo\">{{Ejemplo}}</div>{{/Ejemplo}}",
}]

# La ficha de cartón, en Anki: papel frío, tinta grafito, sin sombras. La regla
# impresa separa la pregunta de la respuesta y el ejemplo va en gris, un paso
# por detrás de la traducción.
MODEL_CSS = """.card {
  font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
  font-size: 22px;
  line-height: 1.5;
  color: #1b1d20;
  background: #fbfbfa;
  text-align: center;
  padding: 24px 16px;
}
hr#answer {
  border: 0;
  border-top: 1px solid rgba(27, 29, 32, 0.13);
  margin: 20px auto;
  max-width: 32ch;
}
.ejemplo {
  margin-top: 16px;
  font-size: 17px;
  font-style: italic;
  color: #7c8188;
}
.card.nightMode, .nightMode .card {
  color: #e9eaec;
  background: #17181b;
}
.nightMode hr#answer { border-top-color: rgba(255, 255, 255, 0.13); }
.nightMode .ejemplo { color: #858b93; }
"""

# Ten per run, as the wireframe says. Each term is a separate call of 8-15s, so
# a run of ten already takes a couple of minutes.
MAX_TERMS = 10

TERMS_SCHEMA = {
    "type": "object",
    "properties": {
        "terms": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "term": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["term", "reason"],
            },
        },
    },
    "required": ["terms"],
}

CARDS_SCHEMA = {
    "type": "object",
    "properties": {
        "skill": {"type": "string"},
        "level": {"type": "string"},
        "topic": {"type": "string"},
        "deck_rationale": {"type": "string"},
        "not_a_term": {"type": "boolean"},
        "note": {"type": "string"},
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "front": {"type": "string"},
                    "back": {"type": "string"},
                    "example": {"type": "string"},
                    "label": {"type": "string"},
                },
                "required": ["front", "back", "example"],
            },
        },
    },
    "required": ["skill", "level", "topic", "candidates"],
}

# El temario de un nivel es un hecho público y estable: lo que enseña un A1 de
# gramática no depende de esta colección, ni cambia de una semana a la otra.
# Se genera una vez y se congela en `data/syllabus/`; lo que se deriva en cada
# lectura es la **cobertura**, que sí es un hecho sobre la colección.
#
# Derivarlo cada vez fue el primer intento y no sirve: dos corridas seguidas
# sobre Grammar A1, sin tocar nada, dieron 7/14 y 3/14. Medido después con tres
# borradores, el desacuerdo casi no es sobre qué contiene A1 —once puntos de
# dieciocho salieron en los tres— sino sobre con qué finura partirlo, y partir
# más fino mueve la cifra sin que cambie una sola tarjeta.
MAX_SYLLABUS_POINTS = 18

# Cuántos borradores se piden antes de congelar. Tres es donde el acuerdo
# empieza a distinguir lo firme de lo dudoso: con dos, un punto que aparece una
# vez es indistinguible de un empate.
SYLLABUS_DRAFTS = 3

# Qué cuenta como "punto" cambia con la habilidad, y sin decirlo el modelo
# devuelve gramática para las cinco: el primer Writing A1 probado vino con
# "artículos a/an/the" y "plural de los sustantivos", que es el temario de
# Grammar con otro nombre encima.
SYLLABUS_POINT = {
    "Grammar": "a structure or rule — \"artículos a/an/the\", \"there is / there are\"",
    "Writing": "a kind of text they can produce, or a device it needs — "
               "\"un email corto de trabajo\", \"conectores de adición\"",
    "Speaking": "a situation they can handle, or the function it needs — "
                "\"presentarse en una reunión\", \"pedir que repitan\"",
    "Listening": "what they can follow and under what conditions — "
                 "\"instrucciones cortas cara a cara\", \"números y horas\"",
    "Reading": "a kind of text they can read, or the vocabulary field it needs — "
               "\"señales y carteles\", \"vocabulario de oficina\"",
}

DRAFT_SCHEMA = {
    "type": "object",
    "properties": {
        "points": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "point": {"type": "string"},
                    "english": {"type": "string"},
                },
                "required": ["point"],
            },
        },
    },
    "required": ["points"],
}

MERGE_SCHEMA = {
    "type": "object",
    "properties": {
        "points": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "point": {"type": "string"},
                    "english": {"type": "string"},
                    "drafts": {"type": "integer"},
                },
                "required": ["point", "drafts"],
            },
        },
    },
    "required": ["points"],
}

COVERAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "points": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "point": {"type": "string"},
                    "covered_by": {"type": "string"},
                    "note": {"type": "string"},
                },
                "required": ["point", "covered_by"],
            },
        },
    },
    "required": ["points"],
}

# El borrador no mira la colección: qué enseña un A1 no depende de tus mazos.
# Sólo la cobertura los necesita, y por eso son dos llamadas distintas.
DRAFT_PROMPT = """A Spanish speaker is learning English. Name what {skill} at
level {level} is made of — the programme a course teaches at that level.

Rules:

- At most {max_points} points, in the order they are normally taught.
- A point is one teachable thing, and for {skill} that means {point_is}. Not a
  whole area like "gramática básica", and not a single word.
- Stay inside {skill}. The other four skills have their own syllabus and this
  one is not a place to list grammar rules unless {skill} is Grammar.
- `point`: its name **in Spanish**, three or four words.
- `english`: the same point as a course would label it in English — "Articles",
  "There is / there are". Empty when there is no natural label."""

MERGE_PROMPT = """{count} independent drafts of the same syllabus — {skill} at
{level} — were produced by the same model minutes apart. They disagree on
wording and on how finely to split a point, not usually on content.

{drafts}

Merge them into one list.

Rules:

- Two points that teach the same thing are **one** point, however differently
  they are worded: "Presente simple afirmativo" and "Presente simple" are the
  same point.
- When the drafts split at different granularity, keep the split a course would
  actually teach as separate lessons — and count the coarse point and its
  pieces as the same point when deciding `drafts`.
- `drafts`: in how many of the {count} drafts that point appears, 1 to {count}.
  It is the reader's signal of where to look, so do not round it up.
- `point`: its name **in Spanish**, three or four words. `english`: the label a
  course would use, or empty.
- Order as normally taught. At most {max_points} points."""

# La cobertura recibe el temario ya congelado y sólo decide qué mazo cubre qué.
# Es una tarea mucho más acotada que inventar la lista y cotejarla a la vez.
COVERAGE_PROMPT = """A Spanish speaker is learning English with Anki. Their
syllabus for {skill} at {level} is fixed and is not yours to change. Say which
of its points their decks already teach.

The syllabus:
{points}

The topics they have at this level, exactly as their decks are named:
{topics}

A sample of the cards those decks hold, because a deck called "Gramática en
contexto" does not say what is inside it:
{have}

Return **every** point of the syllabus above, in the same order, with:

- `point`: copied **exactly** as it is written above. Never reword it, never
  add a point, never drop one.
- `covered_by`: the topic from the list that already teaches it, copied exactly
  as written there. Empty when nothing covers it.
- `note`: one short sentence **in Spanish**, addressed to the student, only
  when there is something worth saying — what the gap costs them, or what the
  deck that covers it still lacks. Empty otherwise. Never a scolding.

Rules:

- Judge by the sample cards, never by the deck name. Seven decks all drilling
  the present simple cover **one** point, not seven.
- A point only half covered is not covered: leave `covered_by` empty and say
  what is missing in `note`.
- Never invent coverage. Claiming a point is covered hides it; leaving it open
  only proposes work they can decline."""



CARDS_PROMPT = """A Spanish speaker learning English wants cards for one term.

Term: {term}
{focus}
Their collection, so you can say where the cards belong:
{levels}

Decks that already exist:
{decks}

Return {count} candidate cards for this term and the deck they should go in.

Rules for the deck:

- `skill` is exactly one of: {skills}
- `level` is exactly one of: {levels_list}, judged by where this term is
  actually met — `to put up with` is B1, `nevertheless` is B2.
- `topic` is two or three words, in English, naming the family the term belongs
  to: "Phrasal verbs", "Formal connectors", "Weather vocabulary". Reuse the
  topic of an existing deck above whenever the term fits it — a new deck for
  every term is how a collection becomes unusable.
- `deck_rationale`: one sentence **in Spanish** saying why that deck.

Rules for the cards — **and they depend on the skill you just chose**.

If `skill` is anything but Grammar, these are vocabulary cards:

- Each candidate is a **different sense or use** of the term, not a rewording
  of the same one. If the term has only one real sense, return one candidate.
- `front`: the English term as it is met, plain text, no article unless it is
  part of it.
- `back`: the Spanish translation. Two or three words at most. If several
  translations are equally right the card is ambiguous — split it into separate
  candidates instead of listing synonyms.
- `example`: one English sentence using the term in that exact sense, under
  twelve words, natural enough to be said out loud.
- `label`: two or three words **in Spanish** telling this candidate apart from
  the others, or empty when there is only one.

If `skill` is Grammar, a word pair teaches nothing: grammar is drilled by
doing. Each candidate is an **exercise**, and the three candidates are three
different exercises on the same point, one of each kind:

- **Traducir** — `front`: `Traducir: ` and a Spanish sentence that can only be
  put into English by using this point. `back`: the English translation.
- **Corregir** — `front`: `Corregir: ` and an English sentence carrying exactly
  the mistake a Spanish speaker makes with this point, and no other mistake.
  `back`: the corrected sentence.
- **Completar** — `front`: `Completar: ` and an English sentence with `___`
  where the point goes, the cue in parentheses. `back`: the whole sentence
  filled in.

For those three, `example` is the rule in **one sentence in Spanish** — why
that answer and not the tempting one — and `label` is `traducir`, `corregir` or
`completar`. Sentences from real life, work included; never "the cat is on the
table".
- Plain text only. No HTML, no markdown, no quotes around the values.

If what you were given is not a single English item but a subject — "verbos
modales", "phrasal verbs", "past tenses" — or is written in Spanish, return
`not_a_term: true`, no candidates, and a `note` **in Spanish** of one sentence
saying it is a tema and that "Proponer términos" lo abre en los términos que lo
componen. A card whose front reads "verbos modales" teaches nothing."""


# Venir de un nivel es una decisión ya tomada, no una pista. El modelo elige
# dónde vive un término mirando el término, y desde `#/agregar/Grammar/A1` eso
# devolvía mazos de A2 o de Writing: la razón por la que entraste —llenar ese
# hueco— se perdía en silencio. La habilidad además decide la forma de la
# tarjeta, así que decírsela no es sólo archivarla bien.
CARDS_FOCUS = """
These cards were asked for from **{skill} {level}** — that is the level being
filled, and it is where they will be filed. Judge the card by that skill: for
Grammar they are exercises, for anything else a vocabulary card. Name the
`topic` inside it; the `skill` and `level` you return are ignored here.
"""


def _levels_block(catalog: dict) -> str:
    """The rail of every skill, as text the model can read."""
    lines = []
    for skill in catalog["skills"]:
        marks = []
        for level in skill["levels"]:
            if level["total"] == 0:
                marks.append(f"{level['level']}: hole")
            else:
                marks.append(
                    f"{level['level']}: {level['mature']}/{level['total']} mature"
                )
        lines.append(f"  {skill['skill']} (standing on {skill['current_level']}): "
                     + ", ".join(marks))
    return "\n".join(lines)


def _decks_block(catalog: dict) -> str:
    names = [
        deck["deck"]
        for skill in catalog["skills"]
        for level in skill["levels"]
        for deck in level["decks"]
    ]
    return "\n".join(f"  {name}" for name in names) or "  (none yet)"


def _stuck_block(cards: list[dict]) -> str:
    if not cards:
        return "  (nothing is stuck right now)"
    return "\n".join(
        f"  {card.get('front') or card['card_id']} — "
        f"{card['failures']} failures of {card['attempts']}, in {card['deck']}"
        for card in cards
    )


TOPIC_LINE = """
They asked for one subject in particular, written in their own words:

    {topic}

Return the terms **of that subject** worth a card each — the individual words,
verbs or structures it is made of, never the subject itself. "verbos modales"
means can, could, must, should and their neighbours, one term each. Use the
state of their collection below only to judge which level to pitch it at and
what they already have; do not wander off the subject they asked for.
"""

FOCUS_HOLE = """
Every term must belong to {skill} at level {level}: that level has no deck at
all and filling it is the whole point of this run. Ignore what would suit any
other skill or level.
"""

# Enriquecer no es llenar. Un nivel que ya se estudia tiene un hueco distinto
# —lo que le falta— y proponer lo que ya está ahí es la forma más rápida de que
# una función así deje de usarse.
FOCUS_ENRICH = """
Every term must belong to {skill} at level {level}. That level is already being
studied and the point of this run is to **round it out**: name what is missing
from it, never what is already there.

These are the cards it already holds. Do not propose any of them again, and do
not propose a variation that would be answered the same way:

{have}
"""


# A subject typed into the box is the student's own text about their own cards,
# so it is bounded rather than scrubbed.
MAX_TOPIC_CHARS = 120


def _focus_block(focus: dict | None, have: list[str]) -> str:
    if not focus:
        return ""
    if have:
        return FOCUS_ENRICH.format(
            **focus, have="\n".join(f"  {front}" for front in have))
    return FOCUS_HOLE.format(**focus)

TERMS_PROMPT = """A Spanish speaker is learning English with Anki. Read the
state of their collection and say what is worth making cards for next.
{topic}{focus}

Cards they keep failing (ranked by how much trouble they cause):
{stuck}

Levels of their collection, A1 to C1. "hole" means there is no deck at all at
that level, which is a different problem from a weak one:
{levels}

Rules:

- Return at most {max_terms} terms, fewest first if there is little to go on.
- A term is a word, a phrasal verb, a collocation or a grammar point — the
  thing a card would teach. Not a topic like "vocabulary" or "verb tenses".
- Prefer what the failures point at. If they keep failing `to put up with`,
  the neighbours of that pattern are what they need, not an unrelated word.
- A level with no deck at all is the strongest signal there is: nothing to
  review means nothing will ever come up for review.
- Never repeat a term that is already on a card above.
- `reason`: one short sentence **in Spanish**, addressed to the student,
  saying why this one. Concrete, never a scolding.

If there is genuinely nothing to go on — no failures and no holes — return an
empty list rather than inventing work."""



def propose_terms(stuck: list[dict], catalog: dict,
                  focus: dict | None = None, topic: str = "",
                  have: list[str] | None = None) -> dict:
    """What to make cards for next.

    Three ways in, and the box decides which: with a subject written in it, the
    subject is opened into its terms — "verbos modales" is can, could, must,
    not a card whose front says "verbos modales". Empty, the failures and the
    holes answer instead. `focus` narrows either one to a single level, and
    `have` — the cards that level already holds — turns filling a hole into
    rounding out a level: without it the model proposes what you have been
    reviewing for months.
    """
    topic = " ".join(str(topic or "").split())[:MAX_TOPIC_CHARS]
    result, duration_ms = llm.generate(
        TERMS_PROMPT.format(
            stuck=_stuck_block(stuck),
            levels=_levels_block(catalog),
            max_terms=MAX_TERMS,
            topic=TOPIC_LINE.format(topic=topic) if topic else "",
            focus=_focus_block(focus, have or []),
        ),
        TERMS_SCHEMA,
    )

    terms = []
    seen = set()
    for item in result.get("terms", [])[:MAX_TERMS]:
        term = str(item.get("term", "")).strip()
        key = term.lower()
        if not term or key in seen:
            continue
        seen.add(key)
        terms.append({"term": term, "reason": str(item.get("reason", "")).strip()})

    return {"terms": terms, "topic": topic, "duration_ms": duration_ms}


def _clean(value, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def draft_syllabus(skill: str, level: str) -> list[dict]:
    """One draft of what a level is made of. Reads nothing of the collection."""
    result, _ = llm.generate(
        DRAFT_PROMPT.format(
            skill=skill, level=level,
            point_is=SYLLABUS_POINT.get(skill, "one teachable thing"),
            max_points=MAX_SYLLABUS_POINTS,
        ),
        DRAFT_SCHEMA,
    )
    points, seen = [], set()
    for item in result.get("points", [])[:MAX_SYLLABUS_POINTS]:
        name = _clean(item.get("point"), 80)
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        points.append({"point": name, "english": _clean(item.get("english"), 80)})
    return points


def merge_drafts(skill: str, level: str, drafts: list[list[dict]]) -> list[dict]:
    """The drafts folded into one list, each point carrying how many agreed.

    The drafts wobble on granularity, not on content, so the merge is what
    turns three noisy samples into one stable list — and `drafts` is what tells
    the reader where the model was unsure, which is where a person should look.
    """
    blocks = "\n\n".join(
        f"Draft {n}:\n" + "\n".join(f"  {p['point']}" for p in draft)
        for n, draft in enumerate(drafts, start=1)
    )
    result, _ = llm.generate(
        MERGE_PROMPT.format(
            count=len(drafts), skill=skill, level=level, drafts=blocks,
            max_points=MAX_SYLLABUS_POINTS,
        ),
        MERGE_SCHEMA,
    )

    points, seen = [], set()
    for item in result.get("points", [])[:MAX_SYLLABUS_POINTS]:
        name = _clean(item.get("point"), 80)
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        # El conteo viene del modelo y podría venir de cualquier tamaño: se
        # recorta al rango que puede tener de verdad, porque la interfaz lo
        # dibuja como "2 de 3" y un 7 rompería la frase.
        try:
            agreed = int(item.get("drafts", 1))
        except (TypeError, ValueError):
            agreed = 1
        points.append({
            "point": name,
            "english": _clean(item.get("english"), 80),
            "drafts": max(1, min(len(drafts), agreed)),
        })
    return points


def build_syllabus(skill: str, level: str, drafts: int = SYLLABUS_DRAFTS) -> dict:
    """The frozen syllabus of one level: N drafts, merged, with the agreement.

    Called once per level and then written to disk. In series and not at once,
    for the same reason card generation is: each draft is a whole `claude -p`
    process, and three at a time is three processes on this machine.
    """
    sampled = [draft_syllabus(skill, level) for _ in range(max(1, drafts))]
    sampled = [d for d in sampled if d]
    if not sampled:
        return {"points": [], "drafts": 0}

    points = merge_drafts(skill, level, sampled) if len(sampled) > 1 else [
        {**p, "drafts": 1} for p in sampled[0]
    ]
    return {"points": points, "drafts": len(sampled)}


def cover(skill: str, level: str, points: list[dict],
          topics: list[str], have: list[str] | None = None) -> list[dict]:
    """The frozen points, each with the deck that covers it — or nothing.

    This is the half that genuinely belongs derived: it is a fact about the
    collection and it changes every time a card is written.
    """
    if not points:
        return []

    result, _ = llm.generate(
        COVERAGE_PROMPT.format(
            skill=skill, level=level,
            points="\n".join(f"  {p['point']}" for p in points),
            topics="\n".join(f"  {t}" for t in topics) or "  (none yet)",
            have="\n".join(f"  {line}" for line in (have or []))
                 or "  (this level holds no cards at all)",
        ),
        COVERAGE_SCHEMA,
    )

    # El modelo devuelve el temario tal como se lo dieron, así que su respuesta
    # se indexa por nombre y se recorre la lista congelada: si inventó un punto
    # queda fuera, y si se saltó uno igual aparece, sin cubrir.
    verdicts = {_clean(item.get("point"), 80).lower(): item
                for item in result.get("points", [])}
    known = {t.lower(): t for t in topics}

    covered = []
    for point in points:
        verdict = verdicts.get(point["point"].lower(), {})
        # `covered_by` es lo único que el modelo afirma sobre la colección, y
        # por lo tanto lo único que hay que verificar: vale sólo si nombra un
        # mazo que existe. Cualquier otra cosa se lee como no cubierto, que es
        # el lado seguro del error — un hueco de más propone trabajo que se
        # puede rechazar, uno de menos lo esconde.
        claimed = _clean(verdict.get("covered_by"), 120).lower()
        covered.append({
            **point,
            "covered_by": known.get(claimed, ""),
            "note": _clean(verdict.get("note"), 200),
        })
    return covered


# ── Everything below treats the model's answer as untrusted ───────────
# A deck name is a path in someone's collection and the fields go straight into
# Anki, so nothing here is used as it arrives: the skill and the level must be
# ones this app knows, and the topic is scrubbed of the separator that would
# otherwise let a topic invent a level of its own.

def _canonical(value: str, allowed: tuple[str, ...]) -> str | None:
    value = str(value or "").strip()
    for option in allowed:
        if value.lower() == option.lower():
            return option
    return None


def _clean_topic(value: str) -> str:
    topic = re.sub(r"\s+", " ", str(value or "")).strip(" :")
    topic = topic.replace("::", " ")   # "::" is the level separator, not text
    return topic[:60]


def deck_for(skill: str, level: str, topic: str) -> str | None:
    """`Skill::Level::Topic`, or None when the model named something this app
    does not recognise. The screen then asks for the deck instead of guessing:
    a card filed under a level that does not exist is worse than an unfiled one.
    """
    canonical_skill = _canonical(skill, analysis.SKILLS)
    canonical_level = _canonical(level, analysis.LEVELS)
    clean_topic = _clean_topic(topic)
    if not (canonical_skill and canonical_level and clean_topic):
        return None
    return f"{canonical_skill}::{canonical_level}::{clean_topic}"


def focus_for(skill: str, level: str) -> dict | None:
    """A `{skill, level}` this app recognises, or None.

    The pair arrives from the URL and ends up inside a prompt, so it is checked
    against the app's own lists: a skill nobody has heard of would ask a
    nonsense question in fluent English.
    """
    canonical_skill = _canonical(skill, analysis.SKILLS)
    canonical_level = _canonical(level, analysis.LEVELS)
    if canonical_skill and canonical_level:
        return {"skill": canonical_skill, "level": canonical_level}
    return None


def propose_cards(term: str, catalog: dict, count: int = 3,
                  focus: dict | None = None) -> dict:
    """Candidate cards for one term, plus the deck they belong in.

    With a `focus` — you came from a hole or from a point of some level's
    syllabus — that level is not a suggestion: the cards are filed there and
    the model only names the topic. Where a term is normally met is a good
    answer to a question nobody asked; you clicked "generar" on **that** level.
    The deck is still yours to change on the screen.
    """
    term = term.strip()
    result, duration_ms = llm.generate(
        CARDS_PROMPT.format(
            term=term,
            focus=CARDS_FOCUS.format(**focus) if focus else "",
            levels=_levels_block(catalog),
            decks=_decks_block(catalog),
            count=count,
            skills=", ".join(analysis.SKILLS),
            levels_list=", ".join(analysis.LEVELS),
        ),
        CARDS_SCHEMA,
    )

    proposed = deck_for(result.get("skill"), result.get("level"),
                        result.get("topic"))
    deck = proposed
    rationale = str(result.get("deck_rationale", "")).strip()
    if focus:
        deck = deck_for(focus["skill"], focus["level"], result.get("topic"))
        # Y se dice. Que el mazo no sea el que el modelo razonó y que la frase
        # de abajo siga explicando otro es cómo una pantalla miente sin querer.
        if proposed and deck and proposed != deck:
            rationale = (f"Va a {focus['skill']} {focus['level']} porque lo "
                         f"pediste desde ahí; el modelo lo habría puesto en "
                         f"{proposed.rsplit('::', 1)[0].replace('::', ' ')}.")
    existing = set(
        d["deck"]
        for skill in catalog["skills"]
        for level in skill["levels"]
        for d in level["decks"]
    ) | {d["deck"] for d in catalog["unclassified"]["decks"]}

    candidates = []
    for item in result.get("candidates", [])[:count]:
        front = anki.to_plain_text(str(item.get("front", ""))).strip()
        back = anki.to_plain_text(str(item.get("back", ""))).strip()
        if not front or not back:
            continue   # a card missing either side is not a card

        # "Ya la tenés": the same front already in the collection, in any note
        # type. Offered, never hidden — seeing that you own it is the point.
        duplicates = anki.existing_with_front(front)
        candidates.append({
            "front": front,
            "back": back,
            "example": anki.to_plain_text(str(item.get("example", ""))).strip(),
            "label": anki.to_plain_text(str(item.get("label", ""))).strip(),
            "duplicate_in": duplicates[0]["deck"] if duplicates else None,
        })

    return {
        "term": term,
        # Un tema no es una tarjeta. Si el modelo lo detecta —o si no devolvió
        # nada usable— la pantalla lo dice y te manda a abrirlo en términos.
        "not_a_term": bool(result.get("not_a_term")) or not candidates,
        "note": str(result.get("note", "")).strip(),
        "deck": deck,
        "deck_exists": deck in existing if deck else False,
        "deck_rationale": rationale,
        "candidates": candidates,
        "duration_ms": duration_ms,
    }
