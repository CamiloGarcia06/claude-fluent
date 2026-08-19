"""Poner la colección bajo la convención `Skill::Level::Topic`, una sola vez.

No es parte del app: es la reorganización de arranque, escrita como script para
que se pueda leer entera antes de que toque nada. Sin `--yes` sólo cuenta lo
que haría.

Renombrar y fusionar son la misma operación — mover las tarjetas a un mazo
nuevo y borrar el viejo ya vacío — y las dos pasan por `snapshot.move_cards`,
que deja en disco de qué mazo venía cada tarjeta antes de moverla.

Un mazo creado por AnkiConnect nace con el preset **Predeterminado**: la
programación de cada tarjeta viaja intacta —intervalos, maduras, fechas— pero
los límites diarios del mazo son los de fábrica. `Refold Inglés-mil` servía 988
repasos al día con su propio preset; como `Reading::A1::Mil palabras` sirve 200.
Se arregla en las opciones del mazo, dentro de Anki.

La maestría no se toca. `PLN in Action` no es inglés y contarlo como tal es
exactamente lo que ensucia la racha, el calendario y el ranking de atascos.
"""
import argparse
import sys

import anki
import snapshot

# Skill::Level::Topic <- los mazos que se funden en él, y por qué.
PLAN = [
    {
        "target": "Reading::A1::Mil palabras",
        "sources": ["Refold Inglés-mil", "ingles poli"],
        "why": "El Refold 1K: la palabra, su definición y una frase de ejemplo. "
               "`ingles poli` son seis tarjetas del mismo mazo — mismo note "
               "type, mismos índices de ordenación — así que vuelven con las "
               "otras 994.",
    },
    {
        "target": "Grammar::A2::Gramática en contexto",
        "sources": ["EN — Gramática en contexto (A2→B1)"],
        "why": "Traducir, corregir y completar sobre presente simple vs "
               "continuo y modales. El mazo ya se llamaba A2→B1; A2 es donde "
               "cae lo que hay dentro.",
    },
    {
        "target": "Reading::B2::Vocabulario técnico Odoo",
        "sources": [
            "Odoo Vocabulary — Español → English (DRI prep)",
            "Odoo Technical — ES → EN (con frases de ejemplo)",
            "vocabulario",
        ],
        "why": "Los tres son términos ES→EN con una frase de uso: "
               "reordering rule, computed field, workflow automation. "
               "`vocabulario` trae además alguna respuesta de entrevista.",
    },
    {
        "target": "Speaking::B2::Entrevista Odoo",
        "sources": ["Odoo Interview — English (DRI Systems prep)"],
        "why": "Preguntas de entrevista con la respuesta hablada entera. Se "
               "practican diciéndolas, no leyéndolas.",
    },
    {
        "target": "Speaking::B2::Presentación y defensa",
        "sources": [
            "DRI Code Review — Idioma (EN-ES)",
            "DRI Code Review — Defensa del Código",
            "DRI Code Review — Presentación (texto completo, inglés fácil)",
        ],
        "why": "Frases para presentar, el guion completo y las respuestas a "
               "las objeciones del revisor. Es una sola actuación en tres "
               "partes.",
    },
]

# Lo que se queda como está, y por qué se dice en voz alta.
UNTOUCHED = "PLN in Action"


def cards_of(deck: str) -> list[int]:
    """Las tarjetas cuyo mazo **es** éste.

    `findCards deck:"X"` no alcanza: en esta colección `deck:"Refold Inglés-mil"`
    devuelve 1000 tarjetas y seis de ellas viven en `ingles poli`. Mover a
    ciegas lo que devuelve la búsqueda es mover tarjetas de un mazo que no
    estabas tocando, así que la pertenencia se confirma leyendo `cardsInfo`.
    """
    found = anki.call("findCards", query=f'deck:"{anki._escape_search(deck)}"')
    if not found:
        return []
    return [c["cardId"] for c in anki.call("cardsInfo", cards=found)
            if c["deckName"] == deck]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true",
                        help="escribir de verdad; sin esto sólo cuenta")
    args = parser.parse_args()

    if not anki.is_alive():
        print("AnkiConnect no responde. Abrí Anki.")
        return 1

    existing = set(anki.call("deckNames"))
    total = 0
    records = []

    for step in PLAN:
        print(f"\n{step['target']}")
        cards: list[int] = []
        for source in step["sources"]:
            if source not in existing:
                print(f"  · {source}: no existe, se salta")
                continue
            found = cards_of(source)
            print(f"  · {source}: {len(found)} tarjetas")
            cards += found

        if not cards:
            continue
        total += len(cards)

        if not args.yes:
            continue

        record = snapshot.move_cards(cards, step["target"])
        records.append(str(record))
        print(f"  → movidas {len(cards)} · registro {record.name}")

        for source in step["sources"]:
            if source in existing and snapshot.delete_empty_deck(source):
                print(f"  → borrado el mazo vacío {source}")

    print(f"\n{UNTOUCHED} no se toca: no es inglés.")

    if not args.yes:
        print(f"\nEnsayo: {total} tarjetas se moverían. "
              f"Volvé a correrlo con --yes para escribir.")
        return 0

    print(f"\nListo: {total} tarjetas movidas.")
    print("Para deshacerlo, en orden inverso:")
    for record in reversed(records):
        print(f"  python -c \"import snapshot; snapshot.undo_move('{record}')\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
