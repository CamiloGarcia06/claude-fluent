"""Caso de uso: la franja de arriba de la pantalla TOEFL. Qué toca hoy, cómo va
la semana, cuántos de tus últimos textos ya son B1 y qué meter en el próximo.

El martes toca reescribir, y para eso hace falta el enunciado entero, no solo el
id: se busca en el banco. Si el banco ya no lo tiene, o no hay nada de la semana
por reescribir, el martes se ofrece un texto nuevo en vez de dejar el día vacío.
"""

from fluent.toefl.domain.b1 import (
    NEW,
    REWRITE,
    WEEK,
    checklist,
    done_on,
    mission,
    rewrite_target,
    road,
    week,
)
from fluent.toefl.domain.catalog import B1, WRITING_KINDS
from fluent.toefl.domain.ports import Clock, ItemBank, SubmissionLog


class GetB1Path:
    def __init__(self, bank: ItemBank, submissions: SubmissionLog, clock: Clock) -> None:
        self._bank = bank
        self._submissions = submissions
        self._clock = clock

    def __call__(self) -> dict:
        today = self._clock.now().date()
        rows = [s for kind in WRITING_KINDS for s in self._submissions.recent(kind)]
        task, kind = WEEK[today.weekday()]

        rewrite = None
        if task == REWRITE:
            rewrite = self._rewrite(today, rows)
            if rewrite is None and not done_on(REWRITE, today, rows):
                task, kind = NEW, B1

        return {
            "today": {
                "date": today.isoformat(),
                "task": task,
                "kind": kind,
                "done": done_on(task, today, rows),
                "rewrite": rewrite,
            },
            "week": week(today, rows),
            "road": road(rows),
            "mission": mission(rows),
        }

    def _rewrite(self, today, rows) -> dict | None:
        target = rewrite_target(today, rows)
        if target is None:
            return None
        kind = target.get("kind")
        item = next(
            (i for i in self._bank.items(kind) if i.id == target.get("item_id")), None
        )
        if item is None:
            return None
        text = str(target.get("text") or "")
        return {
            "item": item.public(),
            "text": text,
            "score": target.get("score"),
            "level": target.get("level"),
            "checks": checklist(text),
        }
