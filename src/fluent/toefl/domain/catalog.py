"""Los patrones del TOEFL iBT (formato del 21-01-2026) que se entrenan, con el
consejo que acompaña a cada uno: los de los dos ejercicios cerrados y los
criterios de la rúbrica de writing.

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
EMAIL = "email"
DISCUSSION = "discussion"
DAILY = "daily"
ACADEMIC = "academic"
# Los que se corrigen texto contra texto, los que corrige el modelo con rúbrica
# y las lecturas con preguntas de opción múltiple (también sin modelo).
OBJECTIVE_KINDS = (SENTENCE, WORDS)
WRITING_KINDS = (EMAIL, DISCUSSION)
READING_KINDS = (DAILY, ACADEMIC)
KINDS = OBJECTIVE_KINDS + WRITING_KINDS + READING_KINDS


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

# Writing: lo que mira la rúbrica de ETS, partido en lo que se puede corregir.
# Un criterio "falla" en una entrega cuando el corrector lo marca o cuando hay
# una corrección de esa categoría; así el consejo se calcula igual que en los
# ejercicios cerrados, con una entrega como un intento.
WRITING_PATTERNS = (
    Pattern(
        "task_completion",
        "Cumplir la tarea",
        "La nota se cae primero por lo que falta, no por lo que está mal: en el email, "
        "un párrafo por viñeta y en su orden; en la discusión, tu opinión en la primera frase.",
        "Dear …, I'm writing because… [viñeta 1]. However, … [viñeta 2]. Could you…? [viñeta 3]",
    ),
    Pattern(
        "development",
        "Desarrollo",
        "Cada idea necesita su porqué y un ejemplo concreto. En la discusión, mínimo 100 "
        "palabras: opinión, dos razones, un ejemplo personal y una frase sobre otro estudiante.",
        "For example, when I… · This matters because…",
    ),
    Pattern(
        "organization",
        "Organización",
        "Conectores que digan qué relación hay entre las frases: first, also, however, "
        "for example, as a result. Una idea por oración.",
        "First, … Also, … However, … As a result, …",
    ),
    Pattern(
        "grammar",
        "Gramática",
        "Tiempos verbales, concordancia y el sujeto que en español se omite. Releé cada "
        "oración buscando su sujeto y su verbo antes de entregar.",
        "Is important → It is important · he go → he goes",
    ),
    Pattern(
        "vocabulary",
        "Vocabulario",
        "Una palabra precisa vale más que tres vagas: cambiá thing, good y very por la "
        "palabra exacta, y cuidado con los falsos amigos.",
        "actually ≠ actualmente · a very big problem → a serious problem",
    ),
    Pattern(
        "mechanics",
        "Ortografía y puntuación",
        "Mayúscula al empezar y en I, coma después de los conectores iniciales y punto "
        "al final. Son puntos que se pierden por apuro.",
        "However, … · i think → I think",
    ),
    Pattern(
        "register",
        "Tono",
        "El email es a alguien que no conocés: saludo y despedida formales, could you / "
        "I would like, nada de wanna ni abreviaturas.",
        "I want → I would like · Hi! → Dear Editor,",
    ),
)

# Reading: los seis tipos de pregunta de Read in Daily Life y Read an Academic
# Passage. El consejo es la estrategia para encontrar la respuesta, no la
# respuesta: en el examen el texto cambia y la estrategia no.
READING_PATTERNS = (
    Pattern(
        "main_idea",
        "Idea principal",
        "La respuesta resume todo el texto, no un párrafo. Descartá la opción que habla "
        "de un solo detalle (muy estrecha) y la que va más allá de lo que el texto trata "
        "(muy amplia). La primera oración de cada párrafo suele bastar.",
        "What is the passage mainly about? · What is the main purpose of the post?",
    ),
    Pattern(
        "detail",
        "Detalle",
        "Está escrito en el texto con otras palabras. Buscá la palabra clave de la "
        "pregunta, leé esa oración y la siguiente, y elegí la opción que dice lo mismo "
        "parafraseado: la que copia palabras sueltas del texto suele ser la trampa.",
        "cordial service and quality → friendly service and excellent products",
    ),
    Pattern(
        "word_meaning",
        "Palabra en contexto",
        "Poné cada opción en lugar de la palabra y releé la oración: queda la que no "
        "cambia el sentido. El significado más común de la palabra no siempre es el "
        "del texto.",
        "achieve this milestone → accomplishment (no distance)",
    ),
    Pattern(
        "inference",
        "Inferencia",
        "No está escrito, pero se deduce de algo que sí está. La correcta se apoya en una "
        "frase concreta; si para elegirla tenés que imaginar algo que el texto no dice, "
        "es incorrecta.",
        "these treats sell out fast → conviene llegar temprano",
    ),
    Pattern(
        "negative_fact",
        "NOT / EXCEPT",
        "Tres opciones son verdad y buscás la que no. Encontrá cada opción en el texto y "
        "tachala; la que no aparece es la respuesta. Leer la pregunta con calma: el "
        "EXCEPT da vuelta todo.",
        "All of the following are true about elephants EXCEPT:",
    ),
    Pattern(
        "author_purpose",
        "Para qué lo menciona",
        "La pregunta no es qué dice esa parte sino para qué está: ejemplo, contraste o "
        "prueba de una idea. Leé la oración de antes: casi siempre nombra la idea que el "
        "ejemplo apoya.",
        "Why does the author mention cleaner fish? → para mostrar que más animales…",
    ),
)

PATTERNS = {
    SENTENCE: SENTENCE_PATTERNS,
    WORDS: WORD_PATTERNS,
    EMAIL: WRITING_PATTERNS,
    DISCUSSION: WRITING_PATTERNS,
    DAILY: READING_PATTERNS,
    ACADEMIC: READING_PATTERNS,
}
_BY_KEY = {p.key: p for group in PATTERNS.values() for p in group}


def pattern(key: str) -> Pattern | None:
    return _BY_KEY.get(key)


def tip_card(key: str) -> dict:
    """El consejo de un patrón tal como lo muestra la pantalla."""
    info = _BY_KEY[key]
    return {"key": key, "label": info.label, "tip": info.tip, "example": info.example}


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
