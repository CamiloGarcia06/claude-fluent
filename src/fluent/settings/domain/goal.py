"""La meta diaria: lo único que este app decide y Anki no sabe.

La meta vive acá y **no** en las opciones de mazo de Anki: un límite escrito en
Anki cambia lo que Anki te sirve en el escritorio y en el móvil. La meta es una
intención, no un tope. Cuarenta tarjetas son unos quince minutos, que es el
hueco real antes del trabajo."""

from .errors import InvalidGoal

DEFAULTS = {"daily_goal": 40}

# Una meta de cero apaga la pantalla y una de mil es el atraso otra vez.
MIN_GOAL, MAX_GOAL = 5, 300


def with_defaults(stored: dict) -> dict:
    return {**DEFAULTS, **(stored if isinstance(stored, dict) else {})}


def apply_changes(state: dict, changes: dict) -> dict:
    """Validar y aplicar. Devuelve el estado completo nuevo."""
    state = dict(state)
    if "daily_goal" in changes:
        try:
            goal = int(changes["daily_goal"])
        except (TypeError, ValueError) as e:
            raise InvalidGoal("la meta diaria tiene que ser un número") from e
        if not MIN_GOAL <= goal <= MAX_GOAL:
            raise InvalidGoal(f"la meta diaria va entre {MIN_GOAL} y {MAX_GOAL}")
        state["daily_goal"] = goal
    return state
