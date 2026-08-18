"""Proposing a better version of a card that keeps being failed.

Proposes only. Nothing here writes to the collection — see snapshot.py.
"""
import anki
import llm

# The model returns fields as a list of name/value pairs rather than an object:
# field names differ per note type, and JSON Schema cannot describe an object
# whose keys are unknown ahead of time.
REPAIR_SCHEMA = {
    "type": "object",
    "properties": {
        "diagnosis": {"type": "string"},
        "fields": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "value": {"type": "string"},
                },
                "required": ["name", "value"],
            },
        },
        "rationale": {"type": "string"},
    },
    "required": ["diagnosis", "fields", "rationale"],
}

BUTTONS = {1: "Again", 2: "Hard", 3: "Good", 4: "Easy"}

PROMPT = """A Spanish speaker learning English keeps failing this Anki card.
Diagnose why and rewrite it so it stops being a stuck card.

Note type: {model}
Current fields:
{fields}

Review history (oldest first):
{history}

How to read the history: `ease` is the button pressed — 1 Again, 2 Hard,
3 Good, 4 Easy. `time` is milliseconds spent on that attempt. A long time
followed by a low button usually means the card is ambiguous rather than hard.

Rules:

- The fault is usually in the card, not the student. Common causes: several
  synonyms on the back so it is unclear which one is being asked for, two
  concepts crammed into one card, no context to disambiguate, or a prompt that
  can be answered in more than one correct way.
- Return `fields` with exactly the same field names listed above. Do not invent
  fields, do not drop any. Return every field, changed or not.
- Keep what the card was teaching. Do not swap it for a different word.
- Keep the existing direction: if the front is English and the back is Spanish,
  leave it that way.
- Plain text only. No HTML.
- `diagnosis`: one or two sentences **in Spanish** saying what is wrong with
  this card, addressed to the student. Concrete, never a scolding.
- `rationale`: one sentence **in Spanish** saying what you changed and why.

If the card is genuinely fine and the difficulty is real, say so in `diagnosis`
and return the fields unchanged."""


def _history_block(note: dict) -> str:
    """Compact review history for every card of the note."""
    lines = []
    for card_id in note.get("cards", []):
        rows = anki.reviews_of_card(card_id)
        if not rows:
            continue
        lines.append(f"  card {card_id} — {len(rows)} attempts")
        for r in rows:
            button = BUTTONS.get(r["ease"], r["ease"])
            lines.append(
                f"    ease={r['ease']} ({button})  time={r['time']}ms  "
                f"ivl={r['lastIvl']} -> {r['ivl']}  type={r['type']}"
            )
    return "\n".join(lines) or "  no reviews recorded yet"


def _fields_block(fields: dict[str, str]) -> str:
    return "\n".join(f"  {name}: {value!r}" for name, value in fields.items())


def propose(note: dict) -> dict:
    """Ask the model for a rewrite. Returns the current fields alongside the
    proposal so the caller can show them side by side."""
    # Plain text on both sides: the diff compares like with like, and the
    # model never sees or produces markup.
    current = {n: anki.to_plain_text(v) for n, v in anki.note_fields(note).items()}

    result, duration_ms = llm.generate(
        PROMPT.format(
            model=note["modelName"],
            fields=_fields_block(current),
            history=_history_block(note),
        ),
        REPAIR_SCHEMA,
    )

    # Field names come back from a language model, so they are treated as
    # untrusted: anything the note does not have is dropped and reported.
    proposed: dict[str, str] = {}
    rejected: list[str] = []
    for item in result.get("fields", []):
        name = item.get("name", "")
        if name in current:
            proposed[name] = anki.to_plain_text(str(item.get("value", "")))
        elif name:
            rejected.append(name)

    # Anything the model left out keeps its current value.
    for name, value in current.items():
        proposed.setdefault(name, value)

    return {
        "note_id": note["noteId"],
        "model": note["modelName"],
        "current": current,
        "proposal": proposed,
        "changed": [n for n in current if current[n] != proposed[n]],
        "rejected_fields": rejected,
        "diagnosis": result.get("diagnosis", ""),
        "rationale": result.get("rationale", ""),
        "duration_ms": duration_ms,
    }
