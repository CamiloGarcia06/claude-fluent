"""Los prompts del temario: tres borradores, una fusión y la cobertura.
`generate` es el modelo inyectado; este módulo no lo importa."""

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
    "Grammar": 'a structure or rule — "artículos a/an/the", "there is / there are"',
    "Writing": "a kind of text they can produce, or a device it needs — "
    '"un email corto de trabajo", "conectores de adición"',
    "Speaking": "a situation they can handle, or the function it needs — "
    '"presentarse en una reunión", "pedir que repitan"',
    "Listening": "what they can follow and under what conditions — "
    '"instrucciones cortas cara a cara", "números y horas"',
    "Reading": "a kind of text they can read, or the vocabulary field it needs — "
    '"señales y carteles", "vocabulario de oficina"',
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


def _clean(value, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def draft_syllabus(generate, skill: str, level: str) -> list[dict]:
    """One draft of what a level is made of. Reads nothing of the collection."""
    result, _ = generate(
        DRAFT_PROMPT.format(
            skill=skill,
            level=level,
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


def merge_drafts(generate, skill: str, level: str, drafts: list[list[dict]]) -> list[dict]:
    """The drafts folded into one list, each point carrying how many agreed.

    The drafts wobble on granularity, not on content, so the merge is what
    turns three noisy samples into one stable list — and `drafts` is what tells
    the reader where the model was unsure, which is where a person should look.
    """
    blocks = "\n\n".join(
        f"Draft {n}:\n" + "\n".join(f"  {p['point']}" for p in draft)
        for n, draft in enumerate(drafts, start=1)
    )
    result, _ = generate(
        MERGE_PROMPT.format(
            count=len(drafts),
            skill=skill,
            level=level,
            drafts=blocks,
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
        points.append(
            {
                "point": name,
                "english": _clean(item.get("english"), 80),
                "drafts": max(1, min(len(drafts), agreed)),
            }
        )
    return points


def build_syllabus(generate, skill: str, level: str, drafts: int = SYLLABUS_DRAFTS) -> dict:
    """The frozen syllabus of one level: N drafts, merged, with the agreement.

    Called once per level and then written to disk. In series and not at once,
    for the same reason card generation is: each draft is a whole `claude -p`
    process, and three at a time is three processes on this machine.
    """
    sampled = [draft_syllabus(generate, skill, level) for _ in range(max(1, drafts))]
    sampled = [d for d in sampled if d]
    if not sampled:
        return {"points": [], "drafts": 0}

    points = (
        merge_drafts(generate, skill, level, sampled)
        if len(sampled) > 1
        else [{**p, "drafts": 1} for p in sampled[0]]
    )
    return {"points": points, "drafts": len(sampled)}


def cover(
    generate,
    skill: str,
    level: str,
    points: list[dict],
    topics: list[str],
    have: list[str] | None = None,
) -> list[dict]:
    """The frozen points, each with the deck that covers it — or nothing.

    This is the half that genuinely belongs derived: it is a fact about the
    collection and it changes every time a card is written.
    """
    if not points:
        return []

    result, _ = generate(
        COVERAGE_PROMPT.format(
            skill=skill,
            level=level,
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
    verdicts = {_clean(item.get("point"), 80).lower(): item for item in result.get("points", [])}
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
        covered.append(
            {
                **point,
                "covered_by": known.get(claimed, ""),
                "note": _clean(verdict.get("note"), 200),
            }
        )
    return covered
