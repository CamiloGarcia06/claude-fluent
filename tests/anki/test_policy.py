"""La regla estructural: sin snapshot no hay escritura. Se prueba sin red porque
`call` rechaza la acción antes de hablar con AnkiConnect."""

import pytest

from fluent.anki.domain.policy import WRITE_ACTIONS, WriteWithoutSnapshot
from fluent.anki.infrastructure import client


def test_write_actions_are_refused_without_evidence():
    assert "addNotes" in WRITE_ACTIONS and "deckNames" not in WRITE_ACTIONS
    with pytest.raises(WriteWithoutSnapshot):
        client.call("addNotes", notes=[])


def test_write_unlocked_scopes_the_evidence():
    assert client.snapshot_evidence() is None
    with client.write_unlocked("/tmp/evidence.json"):
        assert client.snapshot_evidence() == "/tmp/evidence.json"
    assert client.snapshot_evidence() is None
