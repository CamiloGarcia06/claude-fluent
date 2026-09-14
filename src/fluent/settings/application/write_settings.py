from fluent.settings.domain.goal import apply_changes, with_defaults
from fluent.settings.domain.ports import StateStore


class WriteSettings:
    def __init__(self, store: StateStore) -> None:
        self._store = store

    def __call__(self, changes) -> dict:
        state = apply_changes(with_defaults(self._store.read()), changes or {})
        return self._store.write(state)
