"""`data/toefl/` — el banco de ejercicios y los últimos intentos.

Mismo molde que `writing/infrastructure/sessions.py`: escritura atómica,
relectura desconfiada (un renglón que ya no valida se salta, no tumba la
pantalla) y JSON legible, para que puedas borrar a mano un ejercicio malo.
"""

import json
import os
from pathlib import Path

from fluent.shared.config import DATA_DIR
from fluent.toefl.domain.entities import Attempt, Gap, SentenceItem, WordsItem

TOEFL_DIR = DATA_DIR / "toefl"

# El log es la ventana de los consejos, no una historia: con 500 caben los diez
# últimos de cada patrón aunque los párrafos dejen diez intentos de golpe. Lo
# que se cae del tope vuelve a contar como ejercicio sin hacer, y está bien:
# es repaso.
MAX_ATTEMPTS = 500


def _read(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    return [row for row in data if isinstance(row, dict)] if isinstance(data, list) else []


def _write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.part")
    tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)  # un corte a mitad de escritura no deja basura


def _sentence(row: dict) -> SentenceItem:
    return SentenceItem(
        id=row["id"],
        pattern=row["pattern"],
        context=row["context"],
        before=row["before"],
        after=row["after"],
        answer=tuple(row["answer"]),
    )


def _sentence_row(item: SentenceItem) -> dict:
    return {
        "id": item.id,
        "pattern": item.pattern,
        "context": item.context,
        "before": item.before,
        "after": item.after,
        "answer": list(item.answer),
    }


def _words(row: dict) -> WordsItem:
    return WordsItem(
        id=row["id"],
        parts=tuple(row["parts"]),
        gaps=tuple(Gap(**gap) for gap in row["gaps"]),
    )


def _words_row(item: WordsItem) -> dict:
    return {
        "id": item.id,
        "parts": list(item.parts),
        "gaps": [
            {"word": g.word, "shown": g.shown, "missing": g.missing, "pattern": g.pattern}
            for g in item.gaps
        ],
    }


def _load(path: Path, convert) -> list:
    items = []
    for row in _read(path):
        try:
            items.append(convert(row))
        except (KeyError, TypeError, ValueError):
            continue
    return items


class DiskBank:
    def __init__(self, root: Path = TOEFL_DIR) -> None:
        self._sentences = root / "sentences.json"
        self._words = root / "words.json"

    def sentences(self) -> list[SentenceItem]:
        return _load(self._sentences, _sentence)

    def words(self) -> list[WordsItem]:
        return _load(self._words, _words)

    def add_sentences(self, items: list[SentenceItem]) -> int:
        return self._add(self._sentences, [_sentence_row(i) for i in items])

    def add_words(self, items: list[WordsItem]) -> int:
        return self._add(self._words, [_words_row(i) for i in items])

    def _add(self, path: Path, rows: list[dict]) -> int:
        stored = _read(path)
        seen = {row.get("id") for row in stored}
        fresh = []
        for row in rows:
            if row["id"] not in seen:
                seen.add(row["id"])
                fresh.append(row)
        if fresh:
            _write(path, stored + fresh)
        return len(fresh)


class DiskAttempts:
    def __init__(self, root: Path = TOEFL_DIR) -> None:
        self._path = root / "attempts.json"

    def append(self, attempts: list[Attempt]) -> None:
        rows = _read(self._path) + [
            {
                "kind": a.kind,
                "item_id": a.item_id,
                "pattern": a.pattern,
                "correct": a.correct,
                "at": a.at,
            }
            for a in attempts
        ]
        _write(self._path, rows[-MAX_ATTEMPTS:])

    def recent(self) -> list[Attempt]:
        return _load(self._path, lambda row: Attempt(**row))
