"""The only way anything writes to the Anki collection.

Editing notes has no undo, so every write is preceded by a copy of the previous
state on disk. `anki.call` refuses write actions unless one of the context
managers here is holding the lock, which makes the rule structural: forgetting
to snapshot raises instead of silently succeeding.

Three kinds of record live in data/snapshots/, one per kind of write:

    <note_id>-*.json   a snapshot — the previous state of a note, before it was
                       overwritten or deleted
    created-*.json     a creation record — the ids that were made, so exactly
                       those can be removed again
    model-*.json       a note type that was created — evidence only, since
                       AnkiConnect cannot delete a note type
    move-*.json        a move — the deck every card came from, before a rename
                       or a merge sent it somewhere else
"""
import json
import os
from datetime import datetime
from pathlib import Path

import anki

SNAPSHOT_DIR = Path(__file__).resolve().parent / "data" / "snapshots"


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S-%f")


def capture(note_id: int) -> Path:
    """Write the current state of a note to data/snapshots/ and return the path.

    The file is written to a temporary name and renamed into place, so a crash
    mid-write can never leave a truncated snapshot that looks valid.
    """
    note = anki.note_info(note_id)
    record = {
        "captured_at": datetime.now().isoformat(timespec="seconds"),
        "note_id": note["noteId"],
        "model": note["modelName"],
        "tags": note["tags"],
        "fields": anki.note_fields(note),
        "cards": note.get("cards", []),
        "mod": note.get("mod"),
    }

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOT_DIR / f"{note_id}-{_stamp()}.json"
    tmp = path.with_suffix(".json.part")
    tmp.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)
    return path


class guarded:
    """Snapshot the note, then allow writes to it for the duration of the block.

        with snapshot.guarded(note_id) as path:
            anki.call("updateNoteFields", note={...})

    If capture() fails, the block never runs and the lock is never taken: no
    snapshot, no write.
    """

    def __init__(self, note_id: int):
        self.note_id = note_id
        self.path: Path | None = None
        self._unlock = None

    def __enter__(self) -> Path:
        self.path = capture(self.note_id)
        self._unlock = anki.write_unlocked(str(self.path))
        self._unlock.__enter__()
        return self.path

    def __exit__(self, *exc) -> None:
        self._unlock.__exit__(*exc)


def update_note_fields(note_id: int, fields: dict[str, str]) -> Path:
    """Replace field values on a note. The only write path in the app."""
    with guarded(note_id) as path:
        anki.call("updateNoteFields", note={"id": note_id, "fields": fields})
    return path


# ── Additive writes ───────────────────────────────────────────────────
# Creating a note overwrites nothing, so there is no previous state to save.
# What it still needs is a way back, and that is a different artefact: a record
# of exactly what was created, so it can be removed again. Destructive writes
# take a snapshot; additive writes leave a creation record. Both go through
# this module, and nothing reaches Anki any other way.

def _write_creation_record(deck: str, ids: list[int], refused: list[dict]) -> Path:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOT_DIR / f"created-{_stamp()}.json"
    path.write_text(json.dumps({
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "kind": "creation",
        "deck": deck,
        "note_ids": ids,
        "refused": refused,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def add_notes(deck: str, notes: list[dict]) -> tuple[list[int], Path, list[dict]]:
    """Create notes in `deck` and record the new ids so this can be undone.

    Returns (created ids, creation record, notes Anki refused and why).

    **AnkiConnect refuses the whole batch, not the note.** `addNotes` raises for
    all of them if a single one is empty or duplicated — it does not return a
    null in that slot, whatever its documentation suggests. One duplicate would
    otherwise take thirty approved cards down with it, so every note is asked
    about first and only the acceptable ones are written.

    Duplicates are allowed on purpose. The screen already greys anything whose
    front is in the collection; what reaches here is the deliberate case —
    three senses of `nevertheless` share a front and are three real cards.
    Anki's duplicate warning is Anki's own UI concern, not a veto over a card
    you ticked.
    """
    payload = [
        {
            "deckName": deck,
            "modelName": note.get("model", "Basic"),
            "fields": note["fields"],
            "tags": note.get("tags", []),
            "options": {"allowDuplicate": True},
        }
        for note in notes
    ]
    fronts = [note["fields"].get("Front", "") for note in notes]

    with anki.write_unlocked("creation: nothing is overwritten"):
        anki.call("createDeck", deck=deck)

        checks = anki.call("canAddNotesWithErrorDetail", notes=payload)
        writable, refused = [], []
        for note, front, check in zip(payload, fronts, checks):
            if check.get("canAdd"):
                writable.append(note)
            else:
                refused.append({"front": anki.to_plain_text(front),
                                "error": check.get("error", "Anki lo rechazó")})

        # What existed before, so a failure can still be told from a success:
        # the exception takes the ids with it, and a note without a record is
        # a note with no way back.
        before = set()
        for front in fronts:
            before |= anki.notes_in_deck_with_front(deck, front)

        try:
            created = anki.call("addNotes", notes=writable) if writable else []
            ids = [note_id for note_id in created if note_id]
        except Exception:
            after = set()
            for front in fronts:
                after |= anki.notes_in_deck_with_front(deck, front)
            _write_creation_record(deck, sorted(after - before), refused)
            raise

    return ids, _write_creation_record(deck, ids, refused), refused


# ── The third kind of record: a note type ─────────────────────────────
# A note type is not a note. Its templates are shared by every card of that
# type, and AnkiConnect has no deleteModel: once created, only Anki's own GUI
# can remove it. So this record is **evidence, not a way back** — it says what
# was created and with exactly which templates, which is what you need to
# reproduce or repair it by hand. It is written before the call, so a model
# that exists in Anki always has a file describing it here.

def ensure_model(name: str, fields: list[str], templates: list[dict],
                 css: str) -> Path | None:
    """Create the note type if it is missing. Returns the record, or None when
    it already existed and nothing was written."""
    if anki.model_exists(name):
        return None

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOT_DIR / f"model-{_stamp()}.json"
    path.write_text(json.dumps({
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "kind": "model",
        "model": name,
        "fields": fields,
        "templates": templates,
        "css": css,
        "note": "AnkiConnect cannot delete a note type; remove it from Anki's "
                "own GUI if it was a mistake.",
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    with anki.write_unlocked(str(path)):
        anki.call(
            "createModel",
            modelName=name,
            inOrderFields=fields,
            css=css,
            cardTemplates=templates,
        )
    return path


def undo_creation(record_path: Path | str) -> int:
    """Delete the notes listed in a creation record.

    Each note is snapshotted first: you may have edited one since it was
    created, and deleting it would take those edits with it.
    """
    record = json.loads(Path(record_path).read_text(encoding="utf-8"))
    alive = [n for n in record["note_ids"] if anki.call("notesInfo", notes=[n])[0]]
    for note_id in alive:
        capture(note_id)

    if alive:
        with anki.write_unlocked(f"undo of {Path(record_path).name}"):
            anki.call("deleteNotes", notes=alive)
    return len(alive)


# ── The fourth kind of record: a move ─────────────────────────────────
# Renaming a deck is not one action. AnkiConnect has no renameDeck, so it is
# createDeck + changeDeck + deleteDecks, three chained writes, and the middle
# one is the dangerous one: after it runs, nothing in the collection remembers
# where each card used to live. So the card -> deck map goes to disk first.
#
# This is what makes a merge safe as well as a rename: several decks folded
# into one is the same operation, and the record puts every card back in the
# deck it came from.

def move_cards(card_ids: list[int], target: str) -> Path:
    """Move cards into `target`, recording the deck each one came from."""
    if not card_ids:
        raise ValueError("no cards to move")

    origin = {
        card["cardId"]: card["deckName"]
        for card in anki.call("cardsInfo", cards=card_ids)
    }
    missing = [c for c in card_ids if c not in origin]
    if missing:
        raise ValueError(f"cards not found in the collection: {missing[:5]}")

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOT_DIR / f"move-{_stamp()}.json"
    path.write_text(json.dumps({
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "kind": "move",
        "target": target,
        "cards": [{"card": card, "from": origin[card]} for card in card_ids],
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    with anki.write_unlocked(str(path)):
        anki.call("createDeck", deck=target)
        anki.call("changeDeck", cards=card_ids, deck=target)
    return path


def undo_move(record_path: Path | str) -> int:
    """Put every card back in the deck it came from."""
    record = json.loads(Path(record_path).read_text(encoding="utf-8"))

    back: dict[str, list[int]] = {}
    for item in record["cards"]:
        back.setdefault(item["from"], []).append(item["card"])

    moved = 0
    with anki.write_unlocked(f"undo of {Path(record_path).name}"):
        for deck, cards in back.items():
            anki.call("createDeck", deck=deck)
            anki.call("changeDeck", cards=cards, deck=deck)
            moved += len(cards)
    return moved


def delete_empty_deck(name: str) -> bool:
    """Delete a deck only once Anki itself says it holds no cards.

    The emptiness is read back rather than assumed: `deleteDecks` takes the
    cards with it, so deleting a deck that still has some is the one way this
    reorganisation could lose anything.
    """
    remaining = anki.call("findCards", query=f'deck:"{anki._escape_search(name)}"')
    if remaining:
        return False
    with anki.write_unlocked(f"deleting empty deck {name!r}"):
        anki.call("deleteDecks", decks=[name], cardsToo=True)
    return True


def restore(snapshot_path: Path | str) -> Path:
    """Put a note back to a snapshotted state.

    Restoring is itself a write, so it takes its own snapshot first: undoing an
    undo has to be possible too.
    """
    record = json.loads(Path(snapshot_path).read_text(encoding="utf-8"))
    return update_note_fields(record["note_id"], record["fields"])


def history(note_id: int) -> list[dict]:
    """Snapshots taken of one note, newest first."""
    if not SNAPSHOT_DIR.exists():
        return []
    files = sorted(SNAPSHOT_DIR.glob(f"{note_id}-*.json"), reverse=True)
    return [{"path": str(f), "captured_at": f.stem.split("-", 1)[1]} for f in files]
