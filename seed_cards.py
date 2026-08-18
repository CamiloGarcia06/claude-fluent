"""Development fixture: realistic cards for testing the Today screen and repair.

Not part of the app. Every card here has a genuine defect of the kind that
produces a stuck card — several meanings behind one prompt, two concepts in one
note, or a false friend with no context to pin it down — so the repair flow has
something real to diagnose.

    python seed_cards.py                  # create them
    python seed_cards.py --undo --yes     # remove them again

Writes go through snapshot.py like everything else: creation leaves a record in
data/snapshots/, and --undo snapshots each note before deleting it.
"""
import sys

import snapshot

DECK = "claude-fluent-test"

CARDS = [
    # Several meanings behind one prompt: no single answer is correct.
    ("to get", "conseguir, obtener, llegar, volverse, entender, recibir"),
    ("to take", "tomar, llevar, coger, tardar, sacar"),
    ("to miss", "perder, echar de menos, faltar a"),
    # False friends with no context to pin them down.
    ("actually", "en realidad, de hecho"),
    ("to realize", "darse cuenta, comprender"),
    # Two or three concepts crammed into one note.
    ("efficient / effective", "eficiente / eficaz"),
    ("though / although / even though", "aunque, a pesar de, sin embargo"),
    # Direction problem: you recognise it reading, you cannot produce it.
    ("to make vs to do", "hacer (los dos)"),
]


def main() -> int:
    if "--undo" in sys.argv:
        records = sorted(snapshot.SNAPSHOT_DIR.glob("created-*.json"))
        if not records:
            print("No creation records in data/snapshots/.")
            return 1
        latest = records[-1]

        # --undo deletes cards you may be part-way through studying, and one
        # stray run costs the review history too. It does not fire on its own.
        if "--yes" not in sys.argv:
            import json
            ids = json.loads(latest.read_text())["note_ids"]
            print(f"This would delete {len(ids)} notes listed in {latest.name}.")
            print("Re-run with --yes if that is what you want.")
            return 1
        removed = snapshot.undo_creation(latest)
        print(f"Removed {removed} notes listed in {latest.name}")
        return 0

    ids, record = snapshot.add_notes(
        DECK, [{"fields": {"Front": front, "Back": back}, "tags": ["seed"]}
               for front, back in CARDS])
    print(f"Created {len(ids)} notes in '{DECK}'")
    print(f"Creation record: {record}")
    print("\nNow review them in Anki and press Otra vez on a few, three times or")
    print("more each — the struggling ranking needs real failures in the revlog.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
