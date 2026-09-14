"""Caso de uso: abrir el diálogo de añadir de Anki (la puerta de escape al pie
de Agregar, no la acción principal de ninguna pantalla)."""

from fluent.collection.domain.errors import AnkiNotRunning
from fluent.collection.domain.ports import ReviewLauncher


class OpenAddCards:
    def __init__(self, launcher: ReviewLauncher) -> None:
        self._launcher = launcher

    def __call__(self) -> dict:
        if not self._launcher.is_alive():
            raise AnkiNotRunning()
        self._launcher.open_add_cards()
        return {"ok": True}
