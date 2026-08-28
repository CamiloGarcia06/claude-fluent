"""Conversar en inglés y que te corrijan mientras escribís.

Prompts, schemas y el parseo desconfiado de lo que devuelve el modelo. Llama a
`llm` y nada más: **cero disco, cero Anki**. Esa segunda mitad es a propósito —
la práctica de escritura no necesita la colección para nada, así que tiene que
seguir funcionando con Anki cerrado, y la forma de garantizarlo es que este
módulo no pueda importarlo aunque quiera.

Por eso `_clean` y `_canonical` están copiadas de `generate.py` en vez de
importadas: `generate` arrastra `anki`, y una importación por conveniencia ataría
la práctica al proceso de Anki por dos funciones de tres líneas.

**Dos llamadas de naturaleza distinta.** El turno responde y corrige lo justo, y
tiene que ser barato porque ocurre veinte veces por sesión. El cierre lee la
sesión entera una sola vez y es el único que afirma algo que se guarda. Por eso
el catálogo de patrones — cuarenta y pico de entradas — viaja sólo en el
segundo: pagarlo en cada turno es pagarlo veinte veces por una identidad que
sólo hace falta donde se cuenta.
"""
import re

import llm

SYSTEM_PROMPT = (
    "You are an English conversation partner and writing coach for a Spanish "
    "speaker. You answer only with the requested JSON object, with no "
    "commentary."
)

# Las ocho categorías que se muestran en pantalla junto a cada corrección. Es un
# vocabulario cerrado y chico a propósito: la etiqueta sirve para reconocer de
# qué tipo es el error de un vistazo, no para clasificarlo finamente. La
# clasificación fina es el catálogo de patrones, y ocurre en el cierre.
CATEGORIES = ("grammar", "vocabulary", "prepositions", "articles",
              "spelling", "word_order", "register", "missing")

CATEGORY_ES = {
    "grammar": "gramática", "vocabulary": "vocabulario",
    "prepositions": "preposiciones", "articles": "artículos",
    "spelling": "ortografía", "word_order": "orden",
    "register": "registro", "missing": "falta",
}

# El orden es la prioridad: se ordena por índice acá y recién después se trunca,
# o el truncado se lleva puesta la corrección que más importaba.
SEVERITIES = ("critical", "moderate", "minor")
SEVERITY_ES = {"critical": "crítico", "moderate": "moderado", "minor": "menor"}

# Las cinco miradas del análisis de cierre, que son las de `/fluent-writing`.
AREAS = ("grammar", "register", "vocabulary", "structure", "spelling")
AREA_ES = {
    "grammar": "Gramática", "register": "Registro", "vocabulary": "Vocabulario",
    "structure": "Estructura", "spelling": "Ortografía",
}

# "Don't over-correct: a session with 20 red marks kills confidence." Dos por
# turno, y el prompt pide que normalmente sean menos. Un turno sin ninguna
# corrección es una respuesta correcta y frecuente, no un fallo del modelo.
MAX_TURN_CORRECTIONS = 2

# Cuántos intercambios viajan verbatim en el prompt del turno. `claude -p`
# arranca un proceso nuevo cada vez, así que el historial se paga entero en cada
# turno: sin techo, el turno veinte cuesta el triple que el turno tres.
HISTORY_TURNS = 6

MAX_TEXT_CHARS = 1200
MAX_CLOSE_AREAS = 6


# ── El catálogo de patrones ───────────────────────────────────────────────
# El modelo **no nombra** un patrón: lo elige de esta lista. Nombrarlo en texto
# libre da "artículo faltante antes de sustantivo contable" en una sesión y
# "falta el a/an" en la siguiente, y ninguna normalización cierra esa distancia
# — no es ortografía, es con qué finura partir la misma cosa. El conteo se
# fragmentaría en veinte patrones de uno y el umbral no llegaría nunca. Es la
# misma lección que el temario: el arreglo no es un prompt mejor, es dejar de
# preguntar en abierto.
#
# La vara del tamaño de una entrada: **un patrón tiene que ser algo que una
# tarjeta pueda enseñar**, la misma vara que se le aplica a un término. Más
# fino y vuelve la fragmentación; más grueso y el umbral se alcanza en una
# sesión pidiendo una tarjeta que no se puede escribir.
#
# `skill`, `level`, `topic` y `seed` son nuestros, no del modelo: son lo que
# arma `#/agregar/<skill>/<level>/<seed>` cuando el patrón llega al umbral. La
# skill la decide **la forma de tarjeta que el patrón necesita**, porque la
# skill es lo que hace que la generación devuelva tres ejercicios o un par de
# palabras: se practica haciendo → Grammar, y su ejercicio de «corregir» carga
# exactamente el error del hispanohablante, que es literalmente este error;
# vocabulario → Reading; registro y naturalidad → Writing.
PATTERNS = (
    # ── prepositions ──
    {"key": "prep-verb-dependent", "category": "prepositions",
     "label": "La preposición que rige el verbo",
     "hint": "listen to, depend on, look forward to — the verb fixes the preposition",
     "skill": "Grammar", "level": "B1", "topic": "Verb and preposition",
     "seed": "Verbos con preposición fija: listen to, depend on, look forward to, belong to"},
    {"key": "prep-adj-dependent", "category": "prepositions",
     "label": "La preposición que rige el adjetivo",
     "hint": "interested in, good at, afraid of, married to",
     "skill": "Grammar", "level": "B1", "topic": "Adjective and preposition",
     "seed": "Adjetivos con preposición fija: interested in, good at, afraid of, proud of"},
    {"key": "prep-time-in-on-at", "category": "prepositions",
     "label": "in / on / at con el tiempo",
     "hint": "in July, on Monday, at 5pm — Spanish uses `en` for all three",
     "skill": "Grammar", "level": "A2", "topic": "Prepositions of time",
     "seed": "Preposiciones de tiempo: in, on, at — el español usa «en» para las tres"},
    {"key": "prep-place-in-on-at", "category": "prepositions",
     "label": "in / on / at con el lugar",
     "hint": "in the room, on the table, at the door",
     "skill": "Grammar", "level": "A2", "topic": "Prepositions of place",
     "seed": "Preposiciones de lugar: in, on, at — el español usa «en» para las tres"},
    {"key": "prep-extra", "category": "prepositions",
     "label": "Preposición de más, calcada del español",
     "hint": "*enter to the room, *discuss about it — the English verb takes none",
     "skill": "Grammar", "level": "B1", "topic": "Verbs with no preposition",
     "seed": "Verbos que en inglés no llevan preposición: enter, discuss, answer, phone"},

    # ── articles ──
    {"key": "art-missing-indefinite", "category": "articles",
     "label": "Falta a / an",
     "hint": "*She is teacher — English needs the indefinite article, Spanish does not",
     "skill": "Grammar", "level": "A1", "topic": "A and an",
     "seed": "a / an con profesiones y sustantivos contables en singular"},
    {"key": "art-extra-the-general", "category": "articles",
     "label": "the de más al hablar en general",
     "hint": "*The life is hard, *I like the dogs — general statements take no article",
     "skill": "Grammar", "level": "A2", "topic": "The with general nouns",
     "seed": "Cuándo NO va «the»: afirmaciones generales, plurales e incontables"},
    {"key": "art-missing-the-specific", "category": "articles",
     "label": "Falta the cuando sí es específico",
     "hint": "*I went to cinema — a specific, shared referent takes `the`",
     "skill": "Grammar", "level": "A2", "topic": "The with specific nouns",
     "seed": "Cuándo SÍ va «the»: referente específico y compartido"},
    {"key": "art-uncountable", "category": "articles",
     "label": "Incontables tratados como contables",
     "hint": "*informations, *an advice, *many furnitures",
     "skill": "Grammar", "level": "B1", "topic": "Uncountable nouns",
     "seed": "Sustantivos incontables: information, advice, furniture, news, money"},

    # ── grammar ──
    {"key": "gram-3rd-person-s", "category": "grammar",
     "label": "La -s de la tercera persona",
     "hint": "*He work here — third person singular takes -s",
     "skill": "Grammar", "level": "A1", "topic": "Third person s",
     "seed": "La -s de tercera persona del presente simple"},
    {"key": "gram-present-perfect-vs-past", "category": "grammar",
     "label": "Present perfect contra past simple",
     "hint": "*I have seen it yesterday — a finished time takes the past simple",
     "skill": "Grammar", "level": "B1", "topic": "Present perfect and past simple",
     "seed": "Present perfect contra past simple: tiempo terminado contra sin terminar"},
    {"key": "gram-since-for", "category": "grammar",
     "label": "since contra for",
     "hint": "since 2019 (point), for three years (span)",
     "skill": "Grammar", "level": "B1", "topic": "Since and for",
     "seed": "since contra for: punto de partida contra duración"},
    {"key": "gram-continuous-vs-simple", "category": "grammar",
     "label": "Continuo donde va simple",
     "hint": "*I am agreeing, *I am knowing — stative verbs do not go continuous",
     "skill": "Grammar", "level": "B1", "topic": "Stative verbs",
     "seed": "Verbos de estado que no van en continuo: know, agree, want, believe, understand"},
    {"key": "gram-tense-agreement", "category": "grammar",
     "label": "Tiempos que no concuerdan en la frase",
     "hint": "*Yesterday I go to the shop and I bought bread",
     "skill": "Grammar", "level": "A2", "topic": "Tense agreement",
     "seed": "Mantener el mismo tiempo verbal a lo largo de la frase"},
    {"key": "gram-conditional", "category": "grammar",
     "label": "La forma del condicional",
     "hint": "*If I would have time — the if-clause takes the past, not `would`",
     "skill": "Grammar", "level": "B1", "topic": "Conditionals",
     "seed": "Condicionales: qué tiempo va en la cláusula con «if»"},
    {"key": "gram-modal-form", "category": "grammar",
     "label": "La forma después de un modal",
     "hint": "*can to go, *must to study — modals take the bare infinitive",
     "skill": "Grammar", "level": "A2", "topic": "Modal verbs",
     "seed": "Verbos modales: infinitivo sin «to» detrás de can, must, should, will"},
    {"key": "gram-gerund-vs-infinitive", "category": "grammar",
     "label": "Gerundio contra infinitivo",
     "hint": "*I enjoy to read — some verbs take -ing, others take to",
     "skill": "Grammar", "level": "B1", "topic": "Gerund and infinitive",
     "seed": "Verbos que piden -ing y verbos que piden «to»: enjoy, avoid, decide, want"},
    {"key": "gram-subject-omitted", "category": "grammar",
     "label": "Sujeto omitido",
     "hint": "*Is raining, *Is very interesting — English always needs a subject",
     "skill": "Grammar", "level": "A1", "topic": "The subject is obligatory",
     "seed": "El sujeto es obligatorio en inglés: it, there, they"},
    {"key": "gram-there-is-have", "category": "grammar",
     "label": "there is donde el español dice «hay»",
     "hint": "*In my city have a park — existence is `there is`, not `have`",
     "skill": "Grammar", "level": "A1", "topic": "There is and there are",
     "seed": "«Hay» es there is / there are, nunca have"},
    {"key": "gram-do-support", "category": "grammar",
     "label": "Falta el auxiliar do en preguntas y negativas",
     "hint": "*You like it? *I not like it",
     "skill": "Grammar", "level": "A1", "topic": "Do in questions and negatives",
     "seed": "El auxiliar «do» en preguntas y negaciones del presente simple"},
    {"key": "gram-number-agreement", "category": "grammar",
     "label": "Concordancia de número",
     "hint": "*people is, *the news are — nouns that look plural and are not",
     "skill": "Grammar", "level": "B1", "topic": "Number agreement",
     "seed": "Concordancia de número: people, news, everybody, police"},
    {"key": "gram-relative-pronoun", "category": "grammar",
     "label": "El relativo who / which / that",
     "hint": "*the man which came — who for people, which for things",
     "skill": "Grammar", "level": "B1", "topic": "Relative pronouns",
     "seed": "Pronombres relativos: who, which, that, whose"},
    {"key": "gram-passive", "category": "grammar",
     "label": "La forma de la pasiva",
     "hint": "*It was writed, *The book wrote by him",
     "skill": "Grammar", "level": "B1", "topic": "The passive",
     "seed": "La voz pasiva: be + participio"},
    {"key": "gram-reported-speech", "category": "grammar",
     "label": "Estilo indirecto",
     "hint": "*He said me that he will come — say/tell and the tense shift",
     "skill": "Grammar", "level": "B2", "topic": "Reported speech",
     "seed": "Estilo indirecto: el desplazamiento de tiempo y say contra tell"},

    # ── word order ──
    {"key": "order-adj-noun", "category": "word_order",
     "label": "Adjetivo después del sustantivo",
     "hint": "*a car red — English puts the adjective first",
     "skill": "Grammar", "level": "A1", "topic": "Adjective before noun",
     "seed": "El adjetivo va antes del sustantivo, al revés que en español"},
    {"key": "order-adverb-frequency", "category": "word_order",
     "label": "Dónde va el adverbio de frecuencia",
     "hint": "*I go always — always goes before the main verb, after `be`",
     "skill": "Grammar", "level": "A2", "topic": "Adverbs of frequency",
     "seed": "Posición de always, usually, never, sometimes en la frase"},
    {"key": "order-question", "category": "word_order",
     "label": "Orden de la pregunta directa",
     "hint": "*Where you are going? — the auxiliary comes before the subject",
     "skill": "Grammar", "level": "A1", "topic": "Question word order",
     "seed": "Orden de las preguntas: auxiliar antes del sujeto"},
    {"key": "order-indirect-question", "category": "word_order",
     "label": "Orden de la pregunta indirecta",
     "hint": "*Do you know where is it? — the indirect one goes back to statement order",
     "skill": "Grammar", "level": "B1", "topic": "Indirect questions",
     "seed": "Preguntas indirectas: vuelven al orden de una afirmación"},

    # ── vocabulary ──
    {"key": "vocab-false-friend", "category": "vocabulary",
     "label": "Falso amigo",
     "hint": "actually, realize, assist, sensible, eventually, constipated",
     "skill": "Reading", "level": "B1", "topic": "False friends",
     "seed": "Falsos amigos: actually, actually vs currently, assist, sensible, eventually"},
    {"key": "vocab-do-make", "category": "vocabulary",
     "label": "do contra make",
     "hint": "make a decision, do the homework — Spanish has one verb for both",
     "skill": "Reading", "level": "A2", "topic": "Do and make",
     "seed": "do contra make: las colocaciones que el español resuelve con «hacer»"},
    {"key": "vocab-say-tell", "category": "vocabulary",
     "label": "say contra tell",
     "hint": "tell someone, say something — Spanish has one verb for both",
     "skill": "Reading", "level": "A2", "topic": "Say and tell",
     "seed": "say contra tell: las dos formas de «decir»"},
    {"key": "vocab-literal-translation", "category": "vocabulary",
     "label": "Traducción literal del español",
     "hint": "*take a decision, *make a party — the collocation does not carry over",
     "skill": "Reading", "level": "B1", "topic": "Collocations",
     "seed": "Colocaciones que no se traducen literalmente del español"},
    {"key": "vocab-phrasal-missing", "category": "vocabulary",
     "label": "Un verbo formal donde va un phrasal",
     "hint": "`tolerate` where a native says `put up with`",
     "skill": "Reading", "level": "B1", "topic": "Everyday phrasal verbs",
     "seed": "Phrasal verbs del día a día que reemplazan al verbo formal"},
    {"key": "vocab-repetition", "category": "vocabulary",
     "label": "La misma palabra una y otra vez",
     "hint": "good / thing / very repeated where a synonym would carry more",
     "skill": "Reading", "level": "B1", "topic": "Alternatives to common words",
     "seed": "Alternativas a good, bad, thing, very, nice"},

    # ── register ──
    {"key": "reg-too-informal", "category": "register",
     "label": "Demasiado informal para el contexto",
     "hint": "contractions and slang in something that should be neutral or formal",
     "skill": "Writing", "level": "B1", "topic": "Formal register",
     "seed": "Registro formal: qué cambia respecto del inglés hablado"},
    {"key": "reg-too-formal", "category": "register",
     "label": "Demasiado formal, suena a libro",
     "hint": "`I would like to inquire` in a message to a friend",
     "skill": "Writing", "level": "B1", "topic": "Informal register",
     "seed": "Registro informal: cómo se escribe a alguien de confianza"},
    {"key": "reg-direct-request", "category": "register",
     "label": "Pedido demasiado directo",
     "hint": "*I want you to send me — English softens with could/would",
     "skill": "Writing", "level": "B1", "topic": "Polite requests",
     "seed": "Pedidos corteses: could you, would you mind, I was wondering"},
    {"key": "reg-connector", "category": "register",
     "label": "Faltan conectores entre ideas",
     "hint": "sentences stacked with no however, so, although",
     "skill": "Writing", "level": "B1", "topic": "Connectors",
     "seed": "Conectores para hilar ideas: however, although, so, therefore, whereas"},

    # ── spelling ──
    # Medido en una sesión real: es el hábito más repetido, el análisis lo marcó
    # crítico, y era el único que el catálogo no sabía nombrar — así que no
    # contaba y nunca iba a ser tarjeta. Es distinto de `spell-es-calque`: ahí
    # la palabra existe y le falta una letra doble; acá se escribe de oído.
    {"key": "spell-phonetic", "category": "spelling",
     "label": "Escribís las palabras como las oís",
     "hint": "*tink, *becouse, *whithout, *figth, *bets — spelling English by ear, and in English the sound and the letters almost never agree",
     "skill": "Writing", "level": "A2", "topic": "Spelling against the ear",
     "seed": "Palabras que no se escriben como suenan: think, because, without, fight, best, character, example"},
    {"key": "spell-double-letter", "category": "spelling",
     "label": "Consonante doble",
     "hint": "*comming, *begining, *ocurred",
     "skill": "Writing", "level": "A2", "topic": "Double consonants",
     "seed": "Consonantes dobles al añadir -ing y -ed"},
    {"key": "spell-es-calque", "category": "spelling",
     "label": "Ortografía calcada del español",
     "hint": "*recomend, *diferent, *inteligent — Spanish drops the double letter",
     "skill": "Writing", "level": "A2", "topic": "Spelling against Spanish",
     "seed": "Palabras que se escriben distinto que su par en español: recommend, different, intelligent"},
    {"key": "spell-capitalisation", "category": "spelling",
     "label": "Mayúsculas",
     "hint": "*english, *monday, *january — languages, days and months take capitals",
     "skill": "Writing", "level": "A1", "topic": "Capital letters",
     "seed": "Mayúsculas en idiomas, nacionalidades, días y meses"},
    {"key": "spell-apostrophe", "category": "spelling",
     "label": "El apóstrofo",
     "hint": "its / it's, dont, the boys' books",
     "skill": "Writing", "level": "A2", "topic": "Apostrophes",
     "seed": "El apóstrofo: its contra it's, contracciones y posesivo"},

    # ── missing ──
    {"key": "missing-word", "category": "missing",
     "label": "Falta una palabra",
     "hint": "a word dropped that the sentence needs to parse",
     "skill": "Grammar", "level": "A2", "topic": "Words English does not drop",
     "seed": "Palabras que el inglés no omite y el español sí"},
    {"key": "missing-auxiliary", "category": "missing",
     "label": "Falta el auxiliar",
     "hint": "*I no like it, *She not coming",
     "skill": "Grammar", "level": "A1", "topic": "Auxiliaries in negatives",
     "seed": "El auxiliar en las negaciones: don't, doesn't, isn't, aren't"},
)

PATTERN_KEYS = tuple(p["key"] for p in PATTERNS)
PATTERN_BY_KEY = {p["key"]: p for p in PATTERNS}


# ── Guards, copied from generate.py on purpose ────────────────────────────
# Importing them would pull in `anki` through `generate`, and this module has to
# work with Anki closed. Three lines each is a cheaper price than that coupling.

# El andamiaje del propio modelo, colándose adentro de un string.
#
# Una corrida real devolvió el resumen y, pegado al final, `</summary>
# <parameter name="strengths">["Sostuviste una conversación…` — sintaxis de
# llamada a herramienta metida dentro del valor JSON. El esquema lo aceptó,
# porque el campo es un string y eso era un string, así que llegó entero a la
# pantalla; y `strengths` volvió vacío, porque el modelo creyó que ya lo había
# escrito ahí adentro.
#
# Se corta en la primera marca. Sólo estas palabras y no cualquier `<...>`:
# alguien puede escribir `<field name="x">` en una práctica sobre su trabajo, y
# eso es contenido de la conversación, no andamiaje.
_LEAK = re.compile(
    r"</?\s*(?:antml:)?(?:summary|strengths|areas|turns|parameter|parameters|"
    r"function_calls|function_results|invoke|result)\b[^>]*>",
    re.IGNORECASE)


def _clean(value, limit: int) -> str:
    text = str(value or "")
    leak = _LEAK.search(text)
    if leak:
        text = text[:leak.start()]
    return " ".join(text.split())[:limit]


def _canonical(value, allowed: tuple) -> str:
    wanted = str(value or "").strip().lower()
    for item in allowed:
        if item.lower() == wanted:
            return item
    return ""


# ── Prompt blocks ─────────────────────────────────────────────────────────

def _history_block(turns: list[dict]) -> str:
    """The last few exchanges verbatim, older ones as a single line.

    Same shape as `repair._history_block`: the model reads context as text in
    the prompt because `claude -p` has no memory between calls.
    """
    done = [t for t in turns if t.get("state") == "done"]
    if not done:
        return "  (nothing yet — this is their first message)"

    lines = []
    hidden = len(done) - HISTORY_TURNS
    if hidden > 0:
        lines.append(f"  ({hidden} earlier exchanges on the same subject, not shown)")
    for turn in done[-HISTORY_TURNS:]:
        lines.append(f"  them: {turn.get('text', '')}")
        reply = " ".join(x for x in (turn.get("reply"), turn.get("question")) if x)
        lines.append(f"  you:  {reply}")
    return "\n".join(lines)


def _corrected_block(turns: list[dict]) -> str:
    """What has already been corrected, so the same note is not repeated.

    Being told the same thing every turn reads as nagging rather than teaching,
    and it is the fastest way to make someone stop writing.
    """
    seen = []
    for turn in turns:
        for item in turn.get("corrections", []):
            line = f"  {item.get('wrote', '')} -> {item.get('correct', '')}"
            if line not in seen:
                seen.append(line)
    return "\n".join(seen[-20:]) or "  (none yet)"


def _turns_block(turns: list[dict]) -> str:
    """Everything they wrote, numbered, for the closing analysis."""
    lines = []
    for turn in turns:
        if turn.get("state") != "done" or not turn.get("text"):
            continue
        lines.append(f"  [{turn['index']}] {turn['text']}")
    return "\n".join(lines) or "  (they wrote nothing)"


def _catalogue_block() -> str:
    return "\n".join(f"  {p['key']} — {p['hint']}" for p in PATTERNS)


# ── The turn ──────────────────────────────────────────────────────────────

TURN_SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "question": {"type": "string"},
        "alternative": {"type": "string"},
        "corrections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "wrote": {"type": "string"},
                    "correct": {"type": "string"},
                    "why": {"type": "string"},
                    "category": {"type": "string"},
                    "severity": {"type": "string"},
                },
                "required": ["wrote", "correct", "why", "category", "severity"],
            },
        },
    },
    "required": ["reply", "question", "corrections"],
}

TURN_PROMPT = """You are having a written conversation in English with a
Spanish speaker who is practising their writing. They chose the subject:
{topic}. Their level is {level}.

The conversation so far (oldest first):
{history}

They have just written:

    {text}

Mistakes already corrected in this session. Do not correct them again unless
this time the message cannot be understood without it:
{corrected}

Rules for the conversation:

- `reply`: one to three sentences **in English**, reacting to **what they
  said** and never to how they said it. Say something of your own — an
  opinion, a fact, a small story — so there is something to answer. Never
  praise or mention their English here.
- `question`: exactly one question **in English**. One and no more: two
  questions in a turn and they answer the easy one.
- Stay on {topic} for three or four exchanges, then move to a neighbouring
  subject and say in `reply` that you are moving.
- Write at {level} and a little above. Do not simplify below it and do not
  show off above it.
- Never write Spanish in `reply`, `question` or `alternative`. Spanish is only
  for explaining, and the only explanation here is `why`.

Rules for the correction:

- **Communication first.** A clear message with a missed article is a better
  message than a correct one nobody understands. Correct what got in the way
  of the message and nothing else.
- At most {max_corrections} corrections, and usually fewer. A turn with five
  red marks kills the willingness to write the next one. Returning none is a
  valid and common answer.
- `wrote`: their own words, copied **exactly**, the shortest fragment that
  contains the mistake — never the whole message.
- `correct`: that same fragment as it should read.
- **Nothing may change in `correct` that `why` does not account for.** The pair
  exists so they can see exactly what changed and read why; a fix smuggled in
  beside an explained one teaches nothing, and they will make it again next
  week without ever having been told it was a mistake. This includes spelling:
  a typo you silently repair is a typo they keep.
- **One mistake per correction.** If the shortest fragment containing the
  mistake happens to contain a second, unrelated one, return two corrections
  with two narrow fragments instead of one wide fragment that fixes both.
  Two mistakes that are the same rule — the participle and the agent
  preposition of a passive, `was build for me` — are one correction, and then
  `why` names both halves.
- `why`: one sentence **in Spanish**, addressed to them, saying **why** and
  naming the rule so they can apply it elsewhere — "los verbos de estado no
  van en continuo", never "está mal". Concrete, never a scolding.
- `category`: exactly one of: {categories}. Use `missing` only when nothing
  more specific fits.
- `severity`: exactly one of: critical, moderate, minor. `critical` only when
  the sentence cannot be understood or says the opposite of what they meant.

Rules for the alternative:

- `alternative`: the **whole message** as a native speaker their age would
  have written it, **in English**, keeping their voice and their content. It
  is not a correction — it is what they could grow into.
- Empty when what they wrote was already natural. Never invent a difference
  just to have something to show."""


def parse_turn(result: dict, text: str) -> dict:
    """Clean and bound what the model returned. Pure: no model, no I/O.

    Everything here treats the answer as untrusted. The categories and
    severities are closed vocabularies, and a correction whose fragments are
    empty or identical is dropped rather than drawn as a diff of nothing.
    """
    reply = _clean(result.get("reply"), 600)
    question = _clean(result.get("question"), 200)
    alternative = _clean(result.get("alternative"), 800)

    # An "alternative" that repeats what they wrote is noise dressed as advice.
    if alternative.lower() == " ".join(str(text or "").split()).lower():
        alternative = ""

    corrections = []
    for item in result.get("corrections", []):
        if not isinstance(item, dict):
            continue
        wrote = _clean(item.get("wrote"), 200)
        correct = _clean(item.get("correct"), 200)
        if not wrote or not correct or wrote == correct:
            continue
        # An invented category leaves the label empty rather than taking the
        # correction down: the explanation is still worth reading.
        category = _canonical(item.get("category"), CATEGORIES)
        severity = _canonical(item.get("severity"), SEVERITIES) or "minor"
        corrections.append({
            "wrote": wrote,
            "correct": correct,
            "why": _clean(item.get("why"), 300),
            "category": category,
            "severity": severity,
            # The Spanish travels with the answer instead of being mapped again
            # in the view: the vocabulary is closed and defined here, and a
            # second copy of it in JavaScript is a second copy to keep in step.
            "category_es": CATEGORY_ES.get(category, ""),
            "severity_es": SEVERITY_ES[severity],
        })

    # Sort first, truncate second, or the cut takes the critical one.
    corrections.sort(key=lambda c: SEVERITIES.index(c["severity"]))
    return {
        "reply": reply,
        "question": question,
        "alternative": alternative,
        "corrections": corrections[:MAX_TURN_CORRECTIONS],
    }


def turn(topic: str, level: str, turns: list[dict], text: str) -> dict:
    """Reply to one message and correct what got in the way. Writes nothing."""
    result, duration_ms = llm.generate(
        TURN_PROMPT.format(
            topic=topic,
            level=level,
            history=_history_block(turns),
            text=_clean(text, MAX_TEXT_CHARS),
            corrected=_corrected_block(turns),
            max_corrections=MAX_TURN_CORRECTIONS,
            categories=", ".join(CATEGORIES),
        ),
        TURN_SCHEMA,
        system=SYSTEM_PROMPT,
    )
    return {**parse_turn(result, text), "duration_ms": duration_ms}


# ── The close ─────────────────────────────────────────────────────────────

CLOSE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "strengths": {"type": "array", "items": {"type": "string"}},
        "areas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "area": {"type": "string"},
                    "finding": {"type": "string"},
                    "pattern": {"type": "string"},
                    "severity": {"type": "string"},
                    # Con pares y no con fragmentos sueltos: un ejemplo que dice
                    # `tink` y nada más señala dónde te equivocaste sin decirte
                    # qué iba ahí, y veinte minutos después de escribirlo ya no
                    # tenés la frase alrededor para reconstruirlo.
                    "examples": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "wrong": {"type": "string"},
                                "right": {"type": "string"},
                            },
                            "required": ["wrong", "right"],
                        },
                    },
                },
                "required": ["area", "finding", "pattern", "severity"],
            },
        },
        "turns": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "rewritten": {"type": "string"},
                    "note": {"type": "string"},
                },
                "required": ["index", "rewritten"],
            },
        },
    },
    "required": ["summary", "areas", "turns"],
}

CLOSE_PROMPT = """A Spanish speaker practised written English by holding a
conversation about {topic}. Their level is {level}. Read everything they wrote
and give them one consolidated reading of the session.

What they wrote, turn by turn:
{turns}

The corrections already given during the conversation, which were deliberately
light — one or two per turn, only what got in the way:
{corrected}

The patterns this app counts. `pattern` must be one of these keys, copied
exactly. There is no other list and you may not invent a key:
{catalogue}

Return:

- `summary`: two or three sentences **in Spanish**, addressed to them. Open
  with what worked. Then the one thing that would change the most if they
  fixed it. No score, no mark, no verdict on their level.
- `strengths`: up to three short sentences **in Spanish**, each about
  something they actually did in this session — a tense they handled, a
  connector they used well — quoting their own text where you can.
- `areas`: what is worth working on, ordered by how much it costs them. Look
  at grammar, register, vocabulary, structure and spelling, and return only
  the areas where there is something real to say. An area with nothing to say
  is left out, not filled.
  - `area`: exactly one of: {areas}
  - `finding`: one or two sentences **in Spanish** — what the pattern is and
    why it matters, named so they can generalise it rather than memorise one
    fix.
  - `pattern`: the key from the list above that this finding is, copied
    exactly. If nothing in the list fits, return an empty string rather than
    bending a key that means something else.
  - `severity`: critical, moderate or minor.
  - `examples`: up to three cases of this pattern from the session. `wrong` is
    their own text, copied **exactly**; `right` is that same fragment as it
    should read. Never give one without the other — a fragment on its own
    points at the mistake without saying what belonged there, and by the time
    they read this the sentence around it is twenty minutes behind them.
    Keep each pair to the shortest fragment that still makes sense on its own.
- `turns`: their messages rewritten. One entry per turn worth changing, with
  `index` copied from the turn number above.
  - `rewritten`: the whole message **in English**, corrected and natural, in
    their voice. Never add content they did not write.
  - `note`: one short sentence **in Spanish** about that turn, or empty.
  - Leave out the turns you would not change. Never invent an index.

Rules:

- One pattern per finding. Two patterns are two findings.
- The same mistake made four times is **one** area, not four. What is being
  named is the habit, not the occurrence.
- Never a score, never a mark out of ten, never a verdict on their level. This
  is the reading of one session, not an exam.
- Encourage before correcting. Explain why and not only what. Name the pattern
  so it generalises."""


def parse_close(result: dict, turns: list[dict]) -> dict:
    """Clean the closing analysis. Pure: no model, no I/O.

    `unmatched` is the one thing here that is not for the screen: it collects
    the keys the model reached for and did not find, which is the list of what
    the catalogue is missing. A finding whose pattern did not match is still
    shown — it just does not count.
    """
    # 900 y no 600: el tope está para que un modelo que se va de tema no rompa
    # la pantalla, no para recortar. Tres frases en español pasan de 600 con
    # facilidad, y medido, la primera corrida se cortó a mitad de palabra.
    summary = _clean(result.get("summary"), 900)
    # Drop the empties first and cut second: cutting first spends slots on
    # blanks, the same way sorting after truncating loses the critical one.
    strengths = [s for s in (_clean(x, 200) for x in result.get("strengths", [])) if s][:3]

    areas, unmatched = [], []
    for item in result.get("areas", []):
        if not isinstance(item, dict):
            continue
        area = _canonical(item.get("area"), AREAS)
        finding = _clean(item.get("finding"), 400)
        if not area or not finding:
            continue
        claimed = _clean(item.get("pattern"), 60)
        key = _canonical(claimed, PATTERN_KEYS)
        if not key:
            # Un hallazgo sin clave no cuenta, y hasta acá eso se evaporaba: el
            # prompt pide devolver vacío antes que forzar una clave que
            # signifique otra cosa —y hace bien—, pero el vacío no dejaba el
            # rastro que `unmatched` existe para dejar. Medido: dos de cinco
            # áreas de una sesión salieron sin patrón y nadie se enteró.
            # Sin clave inventada se agrupa por área, que es lo que se lee
            # después para decidir qué entrada le falta al catálogo.
            unmatched.append(claimed or area)
        # Un ejemplo sin su par no se muestra: señalaría el error sin decir qué
        # iba en su lugar, que es exactamente lo que había que arreglar.
        examples = []
        for case in item.get("examples", []):
            if not isinstance(case, dict):
                continue
            wrong = _clean(case.get("wrong"), 200)
            right = _clean(case.get("right"), 200)
            if wrong and right and wrong != right:
                examples.append({"wrong": wrong, "right": right})
            if len(examples) == 3:
                break
        severity = _canonical(item.get("severity"), SEVERITIES) or "minor"
        areas.append({
            "area": area,
            "area_es": AREA_ES[area],
            "finding": finding,
            "pattern": key,
            "label": PATTERN_BY_KEY[key]["label"] if key else "",
            "severity": severity,
            "severity_es": SEVERITY_ES[severity],
            "examples": examples,
        })

    areas.sort(key=lambda a: SEVERITIES.index(a["severity"]))
    areas = areas[:MAX_CLOSE_AREAS]

    # Walk our own turns and index the model's answer by `index`, the way the
    # syllabus coverage walks the frozen points: an index it invented drops out,
    # and a turn it skipped still appears, with its own text and no note.
    rewritten = {}
    for item in result.get("turns", []):
        if not isinstance(item, dict):
            continue
        try:
            index = int(item.get("index"))
        except (TypeError, ValueError):
            continue
        rewritten[index] = item

    reviewed = []
    for turn_ in turns:
        if turn_.get("state") != "done" or not turn_.get("text"):
            continue
        found = rewritten.get(turn_["index"], {})
        better = _clean(found.get("rewritten"), MAX_TEXT_CHARS)
        reviewed.append({
            "index": turn_["index"],
            "text": turn_["text"],
            "rewritten": "" if better == turn_["text"] else better,
            "note": _clean(found.get("note"), 300),
        })

    return {
        "summary": summary,
        "strengths": strengths,
        "areas": areas,
        "turns": reviewed,
        "unmatched": unmatched,
    }


def close(topic: str, level: str, turns: list[dict]) -> dict:
    """Read the whole session at once. Writes nothing — the caller counts."""
    result, duration_ms = llm.generate(
        CLOSE_PROMPT.format(
            topic=topic,
            level=level,
            turns=_turns_block(turns),
            corrected=_corrected_block(turns),
            catalogue=_catalogue_block(),
            areas=", ".join(AREAS),
        ),
        CLOSE_SCHEMA,
        system=SYSTEM_PROMPT,
    )
    return {**parse_close(result, turns), "duration_ms": duration_ms}
