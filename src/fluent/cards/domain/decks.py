"""Nombres de mazo: la convención Skill::Level::Topic es la base de datos.

Todo lo que llega del modelo o de la pantalla pasa por aquí antes de convertirse
en un nombre de mazo. Puro: solo `re` y las listas del dominio de la colección."""

import re

from fluent.shared.types import LEVELS, SKILLS

from .errors import InvalidDeckName

MAX_DECK_NAME = 200


def canonical(value: str, allowed: tuple[str, ...]) -> str | None:
    value = str(value or "").strip()
    for option in allowed:
        if value.lower() == option.lower():
            return option
    return None


def clean_topic(value: str) -> str:
    topic = re.sub(r"\s+", " ", str(value or "")).strip(" :")
    topic = topic.replace("::", " ")  # "::" is the level separator, not text
    return topic[:60]


def deck_for(skill: str, level: str, topic: str) -> str | None:
    """`Skill::Level::Topic`, or None when the model named something this app
    does not recognise. The screen then asks for the deck instead of guessing:
    a card filed under a level that does not exist is worse than an unfiled one.
    """
    canonical_skill = canonical(skill, SKILLS)
    canonical_level = canonical(level, LEVELS)
    topic_clean = clean_topic(topic)
    if not (canonical_skill and canonical_level and topic_clean):
        return None
    return f"{canonical_skill}::{canonical_level}::{topic_clean}"


def focus_for(skill: str, level: str) -> dict | None:
    """A `{skill, level}` this app recognises, or None.

    The pair arrives from the URL and ends up inside a prompt, so it is checked
    against the app's own lists: a skill nobody has heard of would ask a
    nonsense question in fluent English.
    """
    canonical_skill = canonical(skill, SKILLS)
    canonical_level = canonical(level, LEVELS)
    if canonical_skill and canonical_level:
        return {"skill": canonical_skill, "level": canonical_level}
    return None


def clean_deck_name(value) -> str:
    """A deck name is a path in the collection, so it is checked rather than
    trusted: no empty components, no stray separators, no runaway length."""
    raw = str(value or "")
    parts = [p.strip() for p in raw.split("::")]
    if not parts or any(not p for p in parts) or len(raw) > MAX_DECK_NAME:
        raise InvalidDeckName(f"invalid deck name: {raw!r}")
    return "::".join(parts)


def decks_at(catalog: dict, focus: dict) -> list[str]:
    """The decks of one skill and level, by full name."""
    for skill in catalog["skills"]:
        if skill["skill"] != focus["skill"]:
            continue
        for level in skill["levels"]:
            if level["level"] == focus["level"]:
                return [d["deck"] for d in level["decks"]]
    return []


def deck_totals_at(catalog: dict, focus: dict) -> dict[str, int]:
    """`{"Grammar::A1::Verb to be": 6, …}` — los mazos de un nivel y su tamaño.
    Es de lo que depende la cobertura: un mazo nuevo o una tarjeta más y lo
    guardado deja de valer."""
    for skill in catalog["skills"]:
        if skill["skill"] != focus["skill"]:
            continue
        for level in skill["levels"]:
            if level["level"] == focus["level"]:
                return {d["deck"]: int(d.get("total", 0)) for d in level["decks"]}
    return {}


# Compatibilidad con generate.py mientras siga plano.
_canonical = canonical
_clean_topic = clean_topic
