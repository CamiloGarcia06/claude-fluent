"""El camino a B1: el requisito de inglés de la maestría, medido sobre lo que
escribís.

Tres piezas, todas sin modelo:

- **La lista B1.** Lo que separa un texto A2 de uno B1 (conectores variados,
  contraste, razones, presente perfecto, condicional, relativo) se puede buscar
  en el texto con reglas. Es aproximado: dice si lo intentaste, no si quedó
  bien; lo de bien o mal lo dice el corrector.
- **El camino.** De tus últimos `WINDOW` textos de primer intento, cuántos
  salieron B1 o más. Es una ventana, no un promedio de la historia: el README
  prohíbe las métricas acumuladas, y un promedio de un mes no se mueve aunque
  hoy ya escribas en B1.
- **La rutina.** Qué toca cada día de la semana. Los miércoles hay clase de PLN:
  no toca nada, y no cuenta como día perdido.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from fluent.toefl.domain.catalog import B1, DISCUSSION, WRITING_KINDS
from fluent.toefl.domain.writing import LEVELS

WINDOW = 10
TARGET = 8
TARGET_LEVEL = "B1"
# La misión sale de los últimos textos: con cinco ya se ve qué se repite, y
# sigue cambiando en cuanto empezás a usarlo.
MISSION_WINDOW = 5
MISSION_SIZE = 2


@dataclass(frozen=True)
class Check:
    key: str
    label: str
    tip: str
    example: str
    pattern: re.Pattern[str]


_PARTICIPLES = (
    "been done gone seen made taken given known written eaten found had got gotten heard "
    "met read said told thought bought brought felt kept left lost paid put run sent spent "
    "stood understood won become begun broken chosen come drunk driven fallen flown "
    "forgotten grown hidden ridden risen shown spoken stolen swum worn built learnt taught "
    "caught fought sold held slept"
).split()

CHECKS = (
    Check(
        "connectors",
        "Conectores variados",
        "Más allá de and, but y so: usá al menos dos de first, also, finally, "
        "moreover, therefore, as a result.",
        "First, … Also, … As a result, …",
        re.compile(
            r"\b(first(?:ly)?|second(?:ly)?|also|finally|moreover|furthermore|therefore|"
            r"besides|in addition|as a result|then|after that|in conclusion|to sum up)\b"
        ),
    ),
    Check(
        "contrast",
        "Contraste",
        "Una idea en contra o un matiz: however, although, on the other hand.",
        "Although it is expensive, … · However, …",
        re.compile(
            r"\b(however|although|even though|though|whereas|on the other hand|"
            r"nevertheless|despite|in spite of|instead)\b"
        ),
    ),
    Check(
        "reasons",
        "Razones y ejemplos",
        "Cada opinión con su porqué o un ejemplo: because, for example, that's why.",
        "I think …, because … For example, …",
        re.compile(
            r"\b(because|since|for example|for instance|such as|that'?s why|so that|"
            r"the reason)\b"
        ),
    ),
    Check(
        "present_perfect",
        "Presente perfecto",
        "have/has + participio para experiencias o algo que sigue: I have lived, "
        "she has never tried.",
        "I have lived here since 2020. · Have you ever tried …?",
        re.compile(
            r"\b(have|has|haven'?t|hasn'?t|i'?ve|we'?ve|you'?ve|they'?ve)\s+"
            r"(?:(?:never|ever|already|just|always|recently|not|also)\s+)?"
            rf"({'|'.join(_PARTICIPLES)}|\w+ed)\b"
        ),
    ),
    Check(
        "conditional",
        "Condicional",
        "Una hipótesis con if: if + presente, will; if + pasado, would.",
        "If I had more time, I would … · If it rains, we will …",
        re.compile(r"\b(if|unless)\b[^.!?]*\b(would|will|could|might|can|'ll|'d)\b"),
    ),
    Check(
        "relative",
        "Oración de relativo",
        "Describí con who / which / where pegado al sustantivo.",
        "The teacher who helped me … · a city where …",
        # Pegado a una palabra anterior: así no cuenta la pregunta que empieza
        # con Who o Which. Una pregunta indirecta (I know where…) sí cuenta, y
        # está bien: también es una subordinada de nivel B1.
        re.compile(r"\w,?\s+(who|which|whose|where)\b"),
    ),
)


def checklist(text: str) -> list[dict]:
    """Un renglón por punto de la lista: si el texto lo usa."""
    lowered = re.sub(r"[’`]", "'", (text or "").lower())
    return [
        {"key": c.key, "label": c.label, "ok": bool(c.pattern.search(lowered))} for c in CHECKS
    ]


def level_rank(level: str | None) -> int:
    return LEVELS.index(level) if level in LEVELS else -1


def first_attempts(submissions: list[dict]) -> list[dict]:
    """Las entregas de writing de primer intento con nivel, en orden
    cronológico. Las reescrituras no miden: tenían las correcciones a la vista."""
    rows = [
        s
        for s in submissions
        if s.get("kind") in WRITING_KINDS and not s.get("revision") and s.get("level") in LEVELS
    ]
    return sorted(rows, key=lambda s: str(s.get("at") or ""))


def road(submissions: list[dict]) -> dict:
    recent = first_attempts(submissions)[-WINDOW:]
    goal = level_rank(TARGET_LEVEL)
    at_level = sum(1 for s in recent if level_rank(s.get("level")) >= goal)
    return {
        "levels": [s.get("level") for s in recent],
        "at_level": at_level,
        "count": len(recent),
        "window": WINDOW,
        "target": TARGET,
        "target_level": TARGET_LEVEL,
        "ready": len(recent) >= WINDOW and at_level >= TARGET,
    }


def mission(submissions: list[dict]) -> list[dict]:
    """Los puntos de la lista que más te faltaron en tus últimos textos. Sin
    textos no hay misión: inventarla sería afirmar de más."""
    recent = first_attempts(submissions)[-MISSION_WINDOW:]
    if not recent:
        return []
    missing = {c.key: 0 for c in CHECKS}
    for s in recent:
        for row in checklist(str(s.get("text") or "")):
            if not row["ok"]:
                missing[row["key"]] += 1
    ranked = sorted(
        (c for c in CHECKS if missing[c.key]), key=lambda c: -missing[c.key]
    )[:MISSION_SIZE]
    return [
        {
            "key": c.key,
            "label": c.label,
            "tip": c.tip,
            "example": c.example,
            "missed": missing[c.key],
            "of": len(recent),
        }
        for c in ranked
    ]


# ── La rutina ──────────────────────────────────────────────────────────

NEW, REWRITE, REST, FREE = "new", "rewrite", "rest", "free"
DAYS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
# Lunes a domingo. Los miércoles hay clase de PLN.
WEEK: tuple[tuple[str, str | None], ...] = (
    (NEW, B1),
    (REWRITE, None),
    (REST, None),
    (NEW, DISCUSSION),
    (NEW, B1),
    (FREE, None),
    (FREE, None),
)


def _day(at) -> date | None:
    try:
        return datetime.fromisoformat(str(at)).date()
    except ValueError:
        return None


def done_on(task: str, day: date, submissions: list[dict]) -> bool | None:
    """Si la tarea de ese día se hizo. Descanso y día libre no se hacen: None."""
    if task not in (NEW, REWRITE):
        return None
    wanted = task == REWRITE
    return any(
        s.get("kind") in WRITING_KINDS
        and bool(s.get("revision")) == wanted
        and _day(s.get("at")) == day
        for s in submissions
    )


def rewrite_target(today: date, submissions: list[dict]) -> dict | None:
    """El peor primer intento de los últimos siete días que todavía no
    reescribiste: el que más tiene para enseñarte."""
    since = today - timedelta(days=7)
    revised = {
        (s.get("kind"), s.get("item_id")) for s in submissions if s.get("revision")
    }
    candidates = [
        s
        for s in first_attempts(submissions)
        if (day := _day(s.get("at"))) is not None
        and since <= day <= today
        and (s.get("kind"), s.get("item_id")) not in revised
    ]
    if not candidates:
        return None
    return min(
        candidates, key=lambda s: (level_rank(s.get("level")), s.get("score") or 0)
    )


def week(today: date, submissions: list[dict]) -> list[dict]:
    """Los siete días de esta semana. Un día anterior a tu primer texto no se
    marca como perdido: la rutina todavía no existía."""
    monday = today - timedelta(days=today.weekday())
    days = [
        d
        for s in submissions
        if s.get("kind") in WRITING_KINDS and (d := _day(s.get("at"))) is not None
    ]
    start = min(days, default=today)
    rows = []
    for offset, (task, kind) in enumerate(WEEK):
        day = monday + timedelta(days=offset)
        rows.append(
            {
                "date": day.isoformat(),
                "day": DAYS[offset],
                "task": task,
                "kind": kind,
                "today": day == today,
                "done": done_on(task, day, submissions) if start <= day <= today else None,
            }
        )
    return rows
