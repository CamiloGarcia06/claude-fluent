"""Los patrones del TOEFL iBT (formato del 21-01-2026) que se entrenan, con el
consejo que acompaña a cada uno.

**El consejo es texto fijo, no una llamada al modelo.** Fallar una pregunta
indirecta siempre se explica igual: el orden vuelve a ser el de una afirmación.
Pedírselo a `claude -p` costaría quince segundos y tokens por una frase que no
cambia.

**Los huecos de Complete the Words se clasifican acá, no los etiqueta el
modelo.** La palabra está a la vista y su terminación también; una regla que se
puede leer le gana a una etiqueta que hay que creerle.
"""

from typing import NamedTuple

SENTENCE = "sentence"
WORDS = "words"
KINDS = (SENTENCE, WORDS)


class Pattern(NamedTuple):
    key: str
    label: str
    tip: str
    example: str


# Build a Sentence. Las diez respuestas del Practice Test 1 caen en estos cuatro.
SENTENCE_PATTERNS = (
    Pattern(
        "indirect_question",
        "Pregunta indirecta",
        "Después de if, whether, where, how much… el orden vuelve a ser el de una "
        "afirmación: sujeto + verbo, sin do ni inversión.",
        "Do you know if she will be moving? · Can you tell me whether the cabins will be available?",
    ),
    Pattern(
        "direct_question",
        "Pregunta directa",
        "Palabra interrogativa + auxiliar (do, does, will, is) + sujeto + verbo base. "
        "El auxiliar va antes del sujeto.",
        "What time does it start? · What recipes will you learn?",
    ),
    Pattern(
        "relative_clause",
        "Oración de relativo",
        "who / that / which va pegado al sustantivo que describe, y el verbo principal "
        "de la oración llega después de cerrar ese bloque.",
        "The tour guides who showed us around the old city were fantastic.",
    ),
    Pattern(
        "passive",
        "Voz pasiva",
        "be (was, is, will be) + participio + by + quien lo hace. El objeto pasa a "
        "sujeto y quien actúa va al final.",
        "I used the study guide that was provided by the professor.",
    ),
)

# Complete the Words. El orden es el de `classify_word`: la primera regla que
# casa gana, así que "however" es conector y no termina en -ever cualquiera.
WORD_PATTERNS = (
    Pattern(
        "connector",
        "Conector",
        "However, although, therefore… Leé la frase anterior: si contrasta, es "
        "however/although; si concluye, therefore/thus.",
        "How_ _ _ _ → However",
    ),
    Pattern(
        "function_word",
        "Palabra gramatical",
        "Artículos, preposiciones, pronombres y auxiliares. Son cortas y frecuentes: "
        "decidí primero qué función falta (¿sujeto? ¿preposición?) y después la letra.",
        "th_ _ → that · fr_ _ → from · i_ → is",
    ),
    Pattern(
        "verb_form",
        "Forma verbal",
        "Mirá qué va antes: después de una preposición, -ing; después de have/was, "
        "participio (-ed); en pasado narrativo, -ed.",
        "dan_ _ _ _ → dancing · concentrat_ _ → concentrated",
    ),
    Pattern(
        "adverb",
        "Adverbio en -ly",
        "Si la palabra modifica a un verbo o a un adjetivo, casi siempre termina en -ly.",
        "on_ _ → only · rapid_ _ → rapidly",
    ),
    Pattern(
        "noun_suffix",
        "Sustantivo con sufijo",
        "Después de the, a, of o un adjetivo va un sustantivo: -tion, -ment, -ness, -ity.",
        "communica_ _ _ _ → communication",
    ),
    Pattern(
        "adjective_suffix",
        "Adjetivo con sufijo",
        "Antes de un sustantivo o después de be va un adjetivo: -al, -ic, -ous, -ive, -ful.",
        "ba_ _ _ → basic · ritualis_ _ _ → ritualistic",
    ),
    Pattern(
        "content_word",
        "Vocabulario",
        "Sin terminación que delate: usá el tema del párrafo y la palabra vecina. Es "
        "el hueco que más paga leer rápido el texto completo antes de escribir.",
        "rec_ _ _ → record · peo_ _ _ → people",
    ),
)

PATTERNS = {SENTENCE: SENTENCE_PATTERNS, WORDS: WORD_PATTERNS}
_BY_KEY = {p.key: p for group in PATTERNS.values() for p in group}


def pattern(key: str) -> Pattern | None:
    return _BY_KEY.get(key)


def keys(kind: str) -> tuple[str, ...]:
    return tuple(p.key for p in PATTERNS.get(kind, ()))


CONNECTORS = frozenset(
    "however although though therefore moreover furthermore thus hence because since "
    "while whereas unless despite instead nevertheless meanwhile otherwise also yet but "
    "and or so then finally besides indeed".split()
)

FUNCTION_WORDS = frozenset(
    "a an the this that these those there their they them it its he she his her we our "
    "us you your i me my is are was were be been being am do does did has have had will "
    "would can could may might must shall should of in on at to for from by with about "
    "into onto over under after before between through during among against without "
    "within as than such each every any some many much more most other another all both "
    "few one not no who whom whose which what when where why how if".split()
)

# Terminan en -ing o -ed y no son formas verbales.
NOT_VERB_FORMS = frozenset(
    "thing things nothing something anything everything morning evening spring "
    "string ceiling king ring wing need speed seed bed red hundred indeed".split()
)

_SUFFIXES = (
    ("noun_suffix", ("tion", "sion", "ment", "ness", "ity", "ance", "ence", "ship")),
    ("adjective_suffix", ("al", "ic", "ous", "ive", "ful", "less", "able", "ible")),
)


def classify_word(word: str) -> str:
    w = word.lower()
    if w in CONNECTORS:
        return "connector"
    if w in FUNCTION_WORDS:
        return "function_word"
    # Longitudes mínimas para que "bed" o "fly" no cuenten como sufijo.
    if w not in NOT_VERB_FORMS and (
        (len(w) >= 5 and w.endswith("ing")) or (len(w) >= 4 and w.endswith("ed"))
    ):
        return "verb_form"
    if len(w) >= 4 and w.endswith("ly"):
        return "adverb"
    for key, endings in _SUFFIXES:
        if any(len(w) > len(end) + 2 and w.endswith(end) for end in endings):
            return key
    return "content_word"
