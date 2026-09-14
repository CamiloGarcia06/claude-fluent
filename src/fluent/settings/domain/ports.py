from typing import Protocol


class StateStore(Protocol):
    def read(self) -> dict:
        """Lo guardado, tal cual (puede faltar o venir vacío)."""
        ...

    def write(self, state: dict) -> dict: ...
