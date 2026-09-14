"""`data/state.json`: lectura y escritura atómica. La validación vive en el
dominio (goal.py)."""

import json
import os

from fluent.shared.config import DATA_DIR

STATE_PATH = DATA_DIR / "state.json"


class DiskState:
    def read(self) -> dict:
        """Un archivo ilegible no tumba la pantalla: se devuelve vacío."""
        try:
            stored = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
        return stored if isinstance(stored, dict) else {}

    def write(self, state: dict) -> dict:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE_PATH.with_suffix(".json.part")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, STATE_PATH)  # un corte a mitad de escritura no deja basura
        return state
