"""Caso de uso: escribir los campos aprobados. Snapshot primero, siempre."""

from fluent.cards.domain.errors import AnkiNotRunning, NoFields, UnknownFields
from fluent.cards.domain.ports import CardStore
from fluent.cards.domain.text import to_field_html, to_plain_text


class ApplyRepair:
    def __init__(self, store: CardStore) -> None:
        self._store = store

    def __call__(self, note_id: int, fields) -> dict:
        if not self._store.is_alive():
            raise AnkiNotRunning()
        if not isinstance(fields, dict) or not fields:
            raise NoFields()
        note = self._store.note_info(note_id)

        # The client does not get to invent field names either.
        known = set(self._store.note_fields(note))
        unknown = sorted(set(fields) - known)
        if unknown:
            raise UnknownFields(f"unknown fields for this note: {', '.join(unknown)}")

        # The client sends plain text; Anki stores HTML.
        encoded = {name: to_field_html(str(value)) for name, value in fields.items()}
        path = self._store.update_note_fields(note_id, encoded)

        written = self._store.note_fields(self._store.note_info(note_id))
        return {
            "ok": True,
            "note_id": note_id,
            "snapshot": str(path),
            "fields": {name: to_plain_text(value) for name, value in written.items()},
        }
