"""Los prompts de las tarjetas: qué estudiar (propose_terms) y las tarjetas de
un término (propose_cards). Proponen; nunca escriben. `generate` es el modelo
inyectado y `client` la colección: este módulo no importa ni uno ni otro.

One call per term, never one call for the batch: per term the screen fills in
as each one lands and a failure costs that term only."""

from fluent.cards.domain.decks import deck_for
from fluent.cards.domain.text import to_plain_text
from fluent.shared.types import LEVELS, SKILLS

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
                marks.append(f"{level['level']}: {level['mature']}/{level['total']} mature")
        lines.append(
            f"  {skill['skill']} (standing on {skill['current_level']}): " + ", ".join(marks)
        )
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
        return FOCUS_ENRICH.format(**focus, have="\n".join(f"  {front}" for front in have))
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


def propose_terms(
    generate,
    stuck: list[dict],
    catalog: dict,
    focus: dict | None = None,
    topic: str = "",
    have: list[str] | None = None,
) -> dict:
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
    result, duration_ms = generate(
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


# ── Everything below treats the model's answer as untrusted ───────────
# A deck name is a path in someone's collection and the fields go straight into
# Anki, so nothing here is used as it arrives: the skill and the level must be
# ones this app knows, and the topic is scrubbed of the separator that would
# otherwise let a topic invent a level of its own.


def propose_cards(
    generate, client, term: str, catalog: dict, count: int = 3, focus: dict | None = None
) -> dict:
    """Candidate cards for one term, plus the deck they belong in.

    With a `focus` — you came from a hole or from a point of some level's
    syllabus — that level is not a suggestion: the cards are filed there and
    the model only names the topic. Where a term is normally met is a good
    answer to a question nobody asked; you clicked "generar" on **that** level.
    The deck is still yours to change on the screen.
    """
    term = term.strip()
    result, duration_ms = generate(
        CARDS_PROMPT.format(
            term=term,
            focus=CARDS_FOCUS.format(**focus) if focus else "",
            levels=_levels_block(catalog),
            decks=_decks_block(catalog),
            count=count,
            skills=", ".join(SKILLS),
            levels_list=", ".join(LEVELS),
        ),
        CARDS_SCHEMA,
    )

    proposed = deck_for(result.get("skill"), result.get("level"), result.get("topic"))
    deck = proposed
    rationale = str(result.get("deck_rationale", "")).strip()
    if focus:
        deck = deck_for(focus["skill"], focus["level"], result.get("topic"))
        # Y se dice. Que el mazo no sea el que el modelo razonó y que la frase
        # de abajo siga explicando otro es cómo una pantalla miente sin querer.
        if proposed and deck and proposed != deck:
            rationale = (
                f"Va a {focus['skill']} {focus['level']} porque lo "
                f"pediste desde ahí; el modelo lo habría puesto en "
                f"{proposed.rsplit('::', 1)[0].replace('::', ' ')}."
            )
    existing = set(
        d["deck"]
        for skill in catalog["skills"]
        for level in skill["levels"]
        for d in level["decks"]
    ) | {d["deck"] for d in catalog["unclassified"]["decks"]}

    candidates = []
    for item in result.get("candidates", [])[:count]:
        front = to_plain_text(str(item.get("front", ""))).strip()
        back = to_plain_text(str(item.get("back", ""))).strip()
        if not front or not back:
            continue  # a card missing either side is not a card

        # "Ya la tenés": the same front already in the collection, in any note
        # type. Offered, never hidden — seeing that you own it is the point.
        duplicates = client.existing_with_front(front)
        candidates.append(
            {
                "front": front,
                "back": back,
                "example": to_plain_text(str(item.get("example", ""))).strip(),
                "label": to_plain_text(str(item.get("label", ""))).strip(),
                "duplicate_in": duplicates[0]["deck"] if duplicates else None,
            }
        )

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
