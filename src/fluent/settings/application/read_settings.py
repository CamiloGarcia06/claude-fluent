from fluent.settings.domain.goal import with_defaults
from fluent.settings.domain.ports import StateStore


class ReadSettings:
    def __init__(self, store: StateStore) -> None:
        self._store = store

    def __call__(self) -> dict:
        return with_defaults(self._store.read())
