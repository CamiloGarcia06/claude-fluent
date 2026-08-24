"""`data/state.json` — lo poco que decide el app y Anki no sabe.

Anki es la fuente de verdad de todo lo demás: qué tarjetas hay, cuándo tocan,
cuáles fallás. Lo único que no vive allí es lo que este app decide sobre sí
mismo, y por ahora es una sola cosa: cuántas tarjetas te propusiste hacer hoy.

La meta vive acá y **no** en las opciones de mazo de Anki. Es a propósito: un
límite escrito en Anki cambia lo que el propio Anki te sirve en el escritorio y
en el móvil, y eso es una decisión de programación que le pertenece a él. La
meta es de este app — una intención, no un tope.
"""
import json
import os
from pathlib import Path

STATE_PATH = Path(__file__).resolve().parent / "data" / "state.json"

# Cuarenta tarjetas son unos quince minutos, que es el hueco real antes del
# trabajo. Ningún atraso justifica una meta que no entra en ese hueco.
DEFAULTS = {"daily_goal": 40}

# Una meta de cero apaga la pantalla y una de mil es el atraso otra vez.
MIN_GOAL, MAX_GOAL = 5, 300


def read() -> dict:
    """El estado, con los valores por defecto para lo que falte.

    Un archivo ilegible no tumba la pantalla: se devuelve el defecto. Este
    archivo no guarda nada que no se pueda volver a elegir en dos segundos.
    """
    try:
        stored = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        stored = {}
    if not isinstance(stored, dict):
        stored = {}
    return {**DEFAULTS, **stored}


def write(changes: dict) -> dict:
    """Validar y guardar. Devuelve el estado completo ya escrito."""
    state = read()

    if "daily_goal" in changes:
        try:
            goal = int(changes["daily_goal"])
        except (TypeError, ValueError):
            raise ValueError("la meta diaria tiene que ser un número")
        if not MIN_GOAL <= goal <= MAX_GOAL:
            raise ValueError(f"la meta diaria va entre {MIN_GOAL} y {MAX_GOAL}")
        state["daily_goal"] = goal

    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(".json.part")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, STATE_PATH)   # un corte a mitad de escritura no deja basura
    return state
