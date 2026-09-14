"""AnkiConnect client. Anki must be running with the AnkiConnect add-on."""

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator

import httpx

from fluent.anki.domain.policy import WRITE_ACTIONS, WriteWithoutSnapshot  # noqa: F401

# Los tipos del revlog viven en el dominio de la colección; se reexportan
# aquí para el código plano que todavía los importa de este módulo.
from fluent.cards.domain.text import (  # noqa: F401
    strip_html,
    to_field_html,
    to_plain_text,
)
from fluent.collection.domain.review import (  # noqa: F401
    AGAIN,
    EASY,
    GOOD,
    HARD,
    Review,
    interval_to_seconds,
)

ENDPOINT = "http://127.0.0.1:8765"
TIMEOUT_S = 10.0

# Writes get longer: creating a note type is a schema change, and thirty notes
# in one call is far more work than any read this app makes. A write that times
# out is the worst possible outcome — it may or may not have happened.
WRITE_TIMEOUT_S = 60.0


# Deliberately not guarded: the `gui*` actions. They open Anki's own dialogs
# and it is the person in front of Anki who then writes — handing the session
# over is the whole design of this app, not a write it performs.

# Holds the path of the snapshot that authorises the current write, or None.
_write_guard: ContextVar[str | None] = ContextVar("anki_write_guard", default=None)


@contextmanager
def write_unlocked(evidence: str) -> Iterator[None]:
    """Allow write actions for the duration of the block.

    Only `snapshot.py` may call this, and only after the previous state is on
    disk. `evidence` is the snapshot path, so a failure can point at the file
    that would have been the way back.
    """
    token = _write_guard.set(evidence)
    try:
        yield
    finally:
        _write_guard.reset(token)


def snapshot_evidence() -> str | None:
    """The snapshot authorising the current write, if any."""
    return _write_guard.get()


# Anki's own definition of a mature card: an interval of three weeks or more.
# Kept in seconds because card intervals, like revlog ones, carry their unit
# in their sign.
MATURE_SECONDS = 21 * 86400

# Por debajo de esto, el primer campo es una etiqueta y no la pregunta:
# "A · traducir", "B · corregir". Se le pega el campo siguiente para que la
# fila diga de qué tarjeta habla.
LABEL_LIKE_CHARS = 24

# Review buttons, as stored in the revlog.

# Review types, as stored in the revlog.
LEARNING, REVIEW, RELEARN, FILTERED, MANUAL = 0, 1, 2, 3, 4


def call(action: str, **params: Any) -> Any:
    """One AnkiConnect request. Raises on the error field, which is where
    AnkiConnect reports failures — the HTTP status is 200 either way.

    Write actions are refused unless snapshot.guarded() is holding the lock.
    """
    if action in WRITE_ACTIONS and _write_guard.get() is None:
        raise WriteWithoutSnapshot(
            f"'{action}' modifies the collection and Anki has no undo. "
            f"Route it through snapshot.guarded(), which saves the previous "
            f"state to data/snapshots/ first."
        )

    response = httpx.post(
        ENDPOINT,
        json={"action": action, "version": 6, "params": params},
        timeout=WRITE_TIMEOUT_S if action in WRITE_ACTIONS else TIMEOUT_S,
    )
    data = response.json()
    if data["error"]:
        raise RuntimeError(f"{action}: {data['error']}")
    return data["result"]


def is_alive() -> bool:
    """True when AnkiConnect answers. Anki closed is the most common failure
    of this whole system and it is completely silent, so callers check first."""
    try:
        return call("version") == 6
    except Exception:
        return False


def decks() -> list[str]:
    return call("deckNames")


def due_counts() -> list[dict]:
    """New / learning / review counts per deck, plus the deck total.

    getDeckStats omits decks with nothing in them, so it is merged over the
    full deck list to keep empty decks visible instead of silently missing.
    """
    ids = call("deckNamesAndIds")
    stats = call("getDeckStats", decks=list(ids))
    by_id = {str(v["deck_id"]): v for v in stats.values()}

    out = []
    for name, deck_id in sorted(ids.items()):
        s = by_id.get(str(deck_id), {})
        new = s.get("new_count", 0)
        learn = s.get("learn_count", 0)
        review = s.get("review_count", 0)
        out.append(
            {
                "deck": name,
                "new": new,
                "learning": learn,
                "review": review,
                "due": new + learn + review,
                "total": s.get("total_in_deck", 0),
            }
        )
    return out


def deck_card_stats() -> list[dict]:
    """Per deck: how many cards it has, how many have been seen, how many are
    mature. Empty decks included.

    The cards come back in one cardsInfo pass over the whole collection and are
    grouped by their own `deckName`. Asking deck by deck would be wrong: a
    findCards query for a parent matches its subdecks too, so every card would
    be counted again in each of its ancestors.
    """
    counts = {name: {"total": 0, "seen": 0, "mature": 0} for name in decks()}

    card_ids = call("findCards", query="deck:*")
    for card in call("cardsInfo", cards=card_ids) if card_ids else []:
        deck = counts.setdefault(card["deckName"], {"total": 0, "seen": 0, "mature": 0})
        deck["total"] += 1
        if card.get("reps", 0) > 0:
            deck["seen"] += 1
        if interval_to_seconds(card.get("interval", 0)) >= MATURE_SECONDS:
            deck["mature"] += 1

    return [{"deck": name, **counts[name]} for name in sorted(counts)]


def reviews_since(timestamp_ms: int) -> list[Review]:
    """Every review logged at or after `timestamp_ms`, across all decks.

    cardReviews is per-deck and returns rows grouped by card rather than in
    chronological order, so rows are tagged with their deck and the result is
    sorted by time before anyone downstream reads it as a timeline.
    """
    out: list[Review] = []
    for deck in decks():
        rows = call("cardReviews", deck=deck, startID=max(timestamp_ms, 0))
        out.extend(Review.from_row(row, deck) for row in rows)
    out.sort(key=lambda r: r.timestamp_ms)
    return out


def note_info(note_id: int) -> dict:
    """Full state of one note: model, tags, field values and its card ids."""
    found = call("notesInfo", notes=[note_id])
    if not found or not found[0]:
        raise KeyError(f"note {note_id} does not exist")
    return found[0]


def note_fields(note: dict) -> dict[str, str]:
    """Field values in their display order, name -> raw value (HTML included)."""
    ordered = sorted(note["fields"].items(), key=lambda kv: kv[1]["order"])
    return {name: field["value"] for name, field in ordered}


def reviews_of_card(card_id: int) -> list[dict]:
    """Named review rows for a single card, oldest first."""
    rows = call("getReviewsOfCards", cards=[card_id]).get(str(card_id), [])
    return sorted(rows, key=lambda r: r["id"])


def card_summaries(card_ids: list[int]) -> dict[int, dict]:
    """Question-side text and owning note for each card.

    Note fields hold HTML, so tags and entities are stripped: the Today screen
    shows a term in a list, not a rendered card.
    """
    if not card_ids:
        return {}

    out: dict[int, dict] = {}
    for card in call("cardsInfo", cards=card_ids):
        fields = card.get("fields", {})
        wanted = card.get("fieldOrder", 0)
        ordered = sorted(fields.values(), key=lambda f: f.get("order", 0))

        # El campo de la pregunta no siempre dice cuál es la tarjeta: el note
        # type de gramática abre con "Tipo", así que la lista de atascos
        # mostraba seis filas llamadas "B · corregir". Si el primero es una
        # etiqueta corta se le pega el siguiente, que es la tarjeta de verdad.
        first = next(
            (f["value"] for f in ordered if f.get("order") == wanted),
            ordered[0]["value"] if ordered else "",
        )
        text = strip_html(first)
        if len(text) < LABEL_LIKE_CHARS:
            rest = next(
                (
                    strip_html(f["value"])
                    for f in ordered
                    if strip_html(f["value"]) and strip_html(f["value"]) != text
                ),
                "",
            )
            if rest:
                # Un número de orden no es ni etiqueta ni pregunta: el mazo de
                # Refold abre con "Índice de ordenación", y "369 · bend" dice
                # menos que "bend".
                text = rest if text.isdigit() or not text else f"{text} · {rest}"

        out[card["cardId"]] = {
            "front": text,
            "note_id": card.get("note"),
        }
    return out


# GUI actions. These drive Anki's own windows and never touch the collection,
# so they are deliberately absent from WRITE_ACTIONS.


def model_names() -> list[str]:
    return call("modelNames")


def model_exists(name: str) -> bool:
    return name in model_names()


def _escape_search(value: str) -> str:
    """Quote a value for an Anki search term.

    Colons, quotes, asterisks, underscores and backslashes are all syntax
    inside an Anki query, so a card front carrying one of them would otherwise
    search for something else entirely.
    """
    return value.replace("\\", "\\\\").replace('"', '\\"')


def notes_in_deck_with_front(deck: str, text: str) -> set[int]:
    """Note ids in one deck whose Front is exactly `text`.

    Used to work out what a failed write actually created: AnkiConnect can
    refuse a batch after part of it landed, and the ids it would have returned
    are gone with the exception.
    """
    text = text.strip()
    if not text:
        return set()
    query = f'deck:"{_escape_search(deck)}" "Front:{_escape_search(text)}"'
    return set(call("findNotes", query=query))


def deck_fronts(deck: str, limit: int = 60) -> list[str]:
    """The first field of the notes in a deck, as plain text.

    Read before proposing more cards for a level you already study: without it
    the model happily proposes the twelve cards you have been reviewing for
    months.
    """
    note_ids = call("findNotes", query=f'"deck:{_escape_search(deck)}"')[:limit]
    if not note_ids:
        return []
    fronts = []
    for note in call("notesInfo", notes=note_ids):
        # No siempre el primer campo es la pregunta: el note type de gramática
        # abre con "Tipo" y devolvería sesenta veces "A · traducir". Se juntan
        # los dos primeros campos con algo escrito, que es lo que identifica la
        # tarjeta.
        values = [strip_html(v) for v in note_fields(note).values()]
        values = [v for v in values if v][:2]
        if values:
            fronts.append(" · ".join(values)[:140])
    return fronts


def existing_with_front(text: str) -> list[dict]:
    """Cards whose Front field is exactly `text`, with the deck they sit in.

    Asked before creating a card, so a term already in the collection is
    offered as "ya la tenés" instead of being added twice. Anki's own duplicate
    check only looks inside one note type, which would miss every Basic card
    already there — the whole seeded collection, to begin with.
    """
    text = text.strip()
    if not text:
        return []
    card_ids = call("findCards", query=f'"Front:{_escape_search(text)}"')
    if not card_ids:
        return []
    return [
        {"note_id": card["note"], "deck": card["deckName"]}
        for card in call("cardsInfo", cards=card_ids)
    ]


def open_deck_review(deck: str) -> None:
    """Put Anki into the reviewer on `deck`.

    Whether the Anki window actually comes to the front is the window
    manager's call, not AnkiConnect's — under Wayland compositors that block
    focus stealing, Anki changes screen but stays behind.
    """
    call("guiDeckReview", name=deck)


def open_add_cards() -> None:
    """Open Anki's Add dialog. Anything typed there is added by hand, in Anki."""
    call("guiAddCards")


class AnkiClient:
    """El cliente como objeto: main.py lo construye una vez y lo inyecta en los
    adaptadores de cada funcionalidad. Delegar mantiene un solo estado (el guarda
    de escritura) y un solo sitio que habla con AnkiConnect."""

    def call(self, action: str, **params: Any) -> Any:
        return call(action, **params)

    def is_alive(self) -> bool:
        return is_alive()

    def decks(self) -> list[str]:
        return decks()

    def due_counts(self) -> list[dict]:
        return due_counts()

    def deck_card_stats(self) -> list[dict]:
        return deck_card_stats()

    def reviews_since(self, timestamp_ms: int) -> list[Review]:
        return reviews_since(timestamp_ms)

    def note_info(self, note_id: int) -> dict:
        return note_info(note_id)

    def note_fields(self, note: dict) -> dict[str, str]:
        return note_fields(note)

    def reviews_of_card(self, card_id: int) -> list[dict]:
        return reviews_of_card(card_id)

    def card_summaries(self, card_ids: list[int]) -> dict[int, dict]:
        return card_summaries(card_ids)

    def model_names(self) -> list[str]:
        return model_names()

    def model_exists(self, name: str) -> bool:
        return model_exists(name)

    def notes_in_deck_with_front(self, deck: str, text: str) -> set[int]:
        return notes_in_deck_with_front(deck, text)

    def deck_fronts(self, deck: str, limit: int = 60) -> list[str]:
        return deck_fronts(deck, limit=limit)

    def existing_with_front(self, text: str) -> list[dict]:
        return existing_with_front(text)

    def open_deck_review(self, deck: str) -> None:
        open_deck_review(deck)

    def open_add_cards(self) -> None:
        open_add_cards()

    def notes_alive(self, note_ids: list[int]) -> int:
        return len([n for n in call("notesInfo", notes=note_ids) if n])
