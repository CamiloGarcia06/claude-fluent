"""El nivel al que se conversa cuando la pantalla no manda uno. **No se lee del
catálogo**: `current_level` para Writing dice A1 por ausencia y no por
diagnóstico. B1 es i+1 sobre lo que la colección sí muestra."""

from fluent.shared.types import LEVELS

PRACTICE_LEVEL = "B1"
MAX_TOPIC_CHARS = 60


def level_or_default(value, default: str = PRACTICE_LEVEL) -> str:
    wanted = str(value or "").strip().lower()
    for level in LEVELS:
        if level.lower() == wanted:
            return level
    return default


def clean_topic(value) -> str:
    return " ".join(str(value or "").split())[:MAX_TOPIC_CHARS]
