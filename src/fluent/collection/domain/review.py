"""Una fila del revlog de Anki, con nombre. Puro: lo comparten el análisis y el
cliente de AnkiConnect, que es quien las construye."""

from typing import NamedTuple

# Los cuatro botones del repaso, tal como los numera Anki.
AGAIN, HARD, GOOD, EASY = 1, 2, 3, 4


def interval_to_seconds(raw: int) -> int:
    """Revlog intervals carry their unit in their sign: positive values are
    days, negative values are seconds. Normalise both to seconds so intervals
    from different rows can be compared."""
    return raw * 86400 if raw >= 0 else -raw


class Review(NamedTuple):
    """One row of the Anki revlog, named."""

    timestamp_ms: int
    card_id: int
    usn: int
    button: int
    new_interval: int
    prev_interval: int
    factor: int
    duration_ms: int
    review_type: int
    deck: str

    @classmethod
    def from_row(cls, row: list, deck: str) -> "Review":
        return cls(*row, deck=deck)

    @property
    def failed(self) -> bool:
        return self.button == AGAIN

    @property
    def interval_dropped(self) -> bool:
        """The scheduler pulled the card back in: it was forgotten."""
        return interval_to_seconds(self.new_interval) < interval_to_seconds(self.prev_interval)
