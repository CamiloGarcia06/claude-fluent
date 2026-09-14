"""La fila del revlog vive en shared/types.py (la comparten dos
funcionalidades); aquí se reexporta para el dominio de la colección."""

from fluent.shared.types import (  # noqa: F401
    AGAIN,
    EASY,
    GOOD,
    HARD,
    Review,
    interval_to_seconds,
)
