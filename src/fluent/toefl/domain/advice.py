"""Qué practicar hoy, leído de los últimos intentos de cada patrón.

**Ventana por patrón, no historia.** El README prohíbe las métricas
acumuladas, y con razón: una precisión global de tres semanas no cambia aunque
hoy ya no falles las pasivas. Los últimos `WINDOW` intentos de cada patrón sí
cambian, y responden lo único que importa al abrir la pantalla: ¿en qué me
concentro ahora?
"""

from dataclasses import dataclass

from fluent.toefl.domain.catalog import keys, pattern
from fluent.toefl.domain.entities import Attempt

WINDOW = 10
# Con menos de tres intentos un fallo es mala suerte, no un patrón.
MIN_ATTEMPTS = 3


@dataclass(frozen=True)
class PatternStat:
    key: str
    label: str
    tip: str
    example: str
    tries: int
    misses: int

    @property
    def miss_rate(self) -> float:
        return self.misses / self.tries if self.tries else 0.0

    @property
    def enough(self) -> bool:
        return self.tries >= MIN_ATTEMPTS


def stats(kind: str, attempts: list[Attempt]) -> list[PatternStat]:
    """Un renglón por patrón del catálogo, también los que no tienen intentos:
    la pantalla dice "sin datos" en vez de esconderlos. `attempts` viene en
    orden cronológico."""
    rows = []
    for key in keys(kind):
        recent = [a for a in attempts if a.kind == kind and a.pattern == key][-WINDOW:]
        info = pattern(key)
        assert info is not None  # keys() sale del mismo catálogo
        rows.append(
            PatternStat(
                key=key,
                label=info.label,
                tip=info.tip,
                example=info.example,
                tries=len(recent),
                misses=sum(1 for a in recent if not a.correct),
            )
        )
    return rows


def weakest(rows: list[PatternStat]) -> PatternStat | None:
    """El patrón que más se falla con datos suficientes. Si nada falla, ninguno:
    inventar un punto débil sería afirmar de más."""
    candidates = [r for r in rows if r.enough and r.misses]
    if not candidates:
        return None
    return max(candidates, key=lambda r: (r.miss_rate, r.misses))
