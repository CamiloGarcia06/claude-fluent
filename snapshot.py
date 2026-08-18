"""The only way anything writes to the Anki collection.

Editing notes has no undo, so every write is preceded by a copy of the previous
state on disk. `anki.call` refuses write actions unless one of the context
managers here is holding the lock, which makes the rule structural: forgetting
to snapshot raises instead of silently succeeding.
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

def add_notes(deck: str, notes: list[dict]) -> tuple[list[int], Path]:
    """Create notes in `deck` and record the new ids so this can be undone.

    Returns (created ids, path of the creation record). Ids come back as None
    for notes Anki refused, usually duplicates; those are kept out of the record.
    """
    payload = [
        {
            "deckName": deck,
            "modelName": note.get("model", "Basic"),
            "fields": note["fields"],
            "tags": note.get("tags", []),
            "options": {"allowDuplicate": False},
        }
        for note in notes
    ]

    with anki.write_unlocked("creation: nothing is overwritten"):
        anki.call("createDeck", deck=deck)
        created = anki.call("addNotes", notes=payload)

    ids = [note_id for note_id in created if note_id]
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOT_DIR / f"created-{_stamp()}.json"
    path.write_text(json.dumps({
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "kind": "creation",
        "deck": deck,
        "note_ids": ids,
        "rejected": sum(1 for note_id in created if not note_id),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return ids, path


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
