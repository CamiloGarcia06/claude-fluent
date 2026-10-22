"""`data/toefl/` — el banco de ejercicios, los últimos intentos y las entregas
de writing.

Mismo molde que `writing/infrastructure/sessions.py`: escritura atómica,
relectura desconfiada (un renglón que ya no valida se salta, no tumba la
pantalla) y JSON legible, para que puedas borrar a mano un ejercicio malo.
"""

import json
import os
from collections.abc import Callable
from pathlib import Path

from fluent.shared.config import DATA_DIR
from fluent.toefl.domain.catalog import DISCUSSION, EMAIL, SENTENCE, WORDS
from fluent.toefl.domain.entities import Attempt, Gap, SentenceItem, WordsItem
from fluent.toefl.domain.ports import Item
from fluent.toefl.domain.writing import DiscussionPrompt, EmailPrompt, Post

TOEFL_DIR = DATA_DIR / "toefl"

# El log es la ventana de los consejos, no una historia: con 500 caben los diez
# últimos de cada patrón aunque los párrafos dejen diez intentos de golpe. Lo
# que se cae del tope vuelve a contar como ejercicio sin hacer, y está bien:
# es repaso.
MAX_ATTEMPTS = 500
# Las entregas guardan el texto entero: cincuenta alcanzan para releer lo último.
MAX_SUBMISSIONS = 50


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


def _email(row: dict) -> EmailPrompt:
    return EmailPrompt(
        id=row["id"],
        situation=row["situation"],
        to=row["to"],
        subject=row["subject"],
        bullets=tuple(row["bullets"]),
    )


def _email_row(item: EmailPrompt) -> dict:
    return {
        "id": item.id,
        "situation": item.situation,
        "to": item.to,
        "subject": item.subject,
        "bullets": list(item.bullets),
    }


def _discussion(row: dict) -> DiscussionPrompt:
    return DiscussionPrompt(
        id=row["id"],
        course=row["course"],
        professor=row["professor"],
        posts=tuple(Post(**post) for post in row["posts"]),
    )


def _discussion_row(item: DiscussionPrompt) -> dict:
    return {
        "id": item.id,
        "course": item.course,
        "professor": item.professor,
        "posts": [{"name": p.name, "text": p.text} for p in item.posts],
    }


# Por tipo: el archivo, de renglón a entidad y de entidad a renglón.
_FILES: dict[str, tuple[str, Callable[[dict], Item], Callable]] = {
    SENTENCE: ("sentences.json", _sentence, _sentence_row),
    WORDS: ("words.json", _words, _words_row),
    EMAIL: ("emails.json", _email, _email_row),
    DISCUSSION: ("discussions.json", _discussion, _discussion_row),
}


def _load(path: Path, convert: Callable[[dict], object]) -> list:
    items = []
    for row in _read(path):
        try:
            items.append(convert(row))
        except (KeyError, TypeError, ValueError):
            continue
    return items


class DiskBank:
    def __init__(self, root: Path = TOEFL_DIR) -> None:
        self._root = root

    def items(self, kind: str) -> list[Item]:
        name, from_row, _ = _FILES[kind]
        return _load(self._root / name, from_row)

    def add(self, kind: str, items: list[Item]) -> int:
        name, _, to_row = _FILES[kind]
        path = self._root / name
        stored = _read(path)
        seen = {row.get("id") for row in stored}
        fresh = []
        for item in items:
            if item.id not in seen:
                seen.add(item.id)
                fresh.append(to_row(item))
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


class DiskSubmissions:
    def __init__(self, root: Path = TOEFL_DIR) -> None:
        self._path = root / "submissions.json"

    def append(self, submission: dict) -> None:
        _write(self._path, (_read(self._path) + [submission])[-MAX_SUBMISSIONS:])

    def recent(self, kind: str) -> list[dict]:
        return [row for row in _read(self._path) if row.get("kind") == kind]
