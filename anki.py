"""AnkiConnect client. Anki must be running with the AnkiConnect add-on."""
import html
import re
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator, NamedTuple

import httpx

ENDPOINT = "http://127.0.0.1:8765"
TIMEOUT_S = 10.0

# Writes get longer: creating a note type is a schema change, and thirty notes
# in one call is far more work than any read this app makes. A write that times
# out is the worst possible outcome — it may or may not have happened.
WRITE_TIMEOUT_S = 60.0

# Every AnkiConnect action that mutates the collection. Editing notes has no
# undo, so `call` refuses these outright unless a snapshot has been written
# first. The guarantee lives here rather than in the callers: relying on each
# call site to remember is exactly how a write slips through.
WRITE_ACTIONS = frozenset({
    # Notes and cards
    "addNote", "addNotes", "updateNote", "updateNoteFields", "updateNoteModel",
    "updateNoteTags", "addTags", "removeTags", "replaceTags",
    "replaceTagsInAllNotes", "clearUnusedTags", "deleteNotes", "removeNotes",
    "removeEmptyNotes",
    "createDeck", "deleteDecks", "changeDeck", "moveCardsToDeck",
    "setDueDate", "forgetCards", "relearnCards", "suspend", "unsuspend",
    "setSpecificValueOfCard", "setEaseFactors", "answerCards", "insertReviews",
    "storeMediaFile", "deleteMediaFile", "importPackage",

    # Note types. A card template is shared by every note that uses it, so a
    # bad edit here is not one broken card but every card of that type at once
    # — and AnkiConnect has no deleteModel, so a note type created by mistake
    # can only be removed from Anki's own GUI. These were missing while nothing
    # wrote note types; card generation is what writes them, so the list grew
    # before that landed rather than after.
    "createModel", "updateModelTemplates", "updateModelStyling",
    "modelFieldAdd", "modelFieldRemove", "modelFieldRename",
    "modelFieldReposition", "modelFieldSetDescription", "modelFieldSetFont",
    "modelFieldSetFontSize", "modelTemplateAdd", "modelTemplateRemove",
    "modelTemplateRename", "modelTemplateReposition",
    "findAndReplaceInModels",

    # Deck options. Changing a preset re-schedules every deck that uses it.
    "saveDeckConfig", "setDeckConfigId", "cloneDeckConfigId",
    "removeDeckConfigId",
})

# Deliberately not guarded: the `gui*` actions. They open Anki's own dialogs
# and it is the person in front of Anki who then writes — handing the session
# over is the whole design of this app, not a write it performs.

# Holds the path of the snapshot that authorises the current write, or None.
_write_guard: ContextVar[str | None] = ContextVar("anki_write_guard", default=None)


class WriteWithoutSnapshot(RuntimeError):
    """Raised when a write is attempted outside snapshot.guarded()."""


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

# Review buttons, as stored in the revlog.
AGAIN, HARD, GOOD, EASY = 1, 2, 3, 4

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


def interval_to_seconds(raw: int) -> int:
    """Revlog intervals carry their unit in their sign: positive values are
    days, negative values are seconds. Normalise both to seconds so intervals
    from different rows can be compared."""
    return raw * 86400 if raw >= 0 else -raw


class Review(NamedTuple):
    """One row of the Anki revlog, named."""

    timestamp_ms: int
    card_id: int
    usn: int
    button: int
    new_interval: int
    prev_interval: int
    factor: int
    duration_ms: int
    review_type: int
    deck: str

    @classmethod
    def from_row(cls, row: list, deck: str) -> "Review":
        return cls(*row, deck=deck)

    @property
    def failed(self) -> bool:
        return self.button == AGAIN

    @property
    def interval_dropped(self) -> bool:
        """The scheduler pulled the card back in: it was forgotten."""
        return interval_to_seconds(self.new_interval) < interval_to_seconds(
            self.prev_interval
        )


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
        out.append({
            "deck": name,
            "new": new,
            "learning": learn,
            "review": review,
            "due": new + learn + review,
            "total": s.get("total_in_deck", 0),
        })
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
        deck = counts.setdefault(
            card["deckName"], {"total": 0, "seen": 0, "mature": 0}
        )
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

def strip_html(value: str) -> str:
    """Collapse a field to a single line. For list rows, not for editing."""
    text = re.sub(r"<[^>]+>", " ", value)
    return " ".join(html.unescape(text).replace("\xa0", " ").split())


def to_plain_text(value: str) -> str:
    """Field value -> editable plain text, keeping the line structure.

    Anki stores fields as HTML, so line breaks live in <br> and block tags.
    Collapsing them the way strip_html does would silently flatten a card into
    one line the moment it was written back.
    """
    text = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    text = re.sub(r"</(p|div|li|tr)>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text).replace("\xa0", " ")
    return "\n".join(line.strip() for line in text.split("\n")).strip()


def to_field_html(text: str) -> str:
    """Plain text -> what Anki stores. Escaped, so a stray < cannot become
    markup, with newlines as the <br> Anki actually renders."""
    return html.escape(text, quote=False).replace("\n", "<br>")


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
        value = next(
            (f["value"] for f in fields.values() if f.get("order") == wanted),
            next((f["value"] for f in fields.values()), ""),
        )
        out[card["cardId"]] = {
            "front": strip_html(value),
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
