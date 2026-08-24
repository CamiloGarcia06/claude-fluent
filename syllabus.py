"""`data/syllabus/` — el temario congelado de cada nivel.

La madurez responde "¿te acordás de tus tarjetas?". El temario responde "¿tus
tarjetas cubren el nivel?", que es otra pregunta y la que nada en el app podía
hacer: Grammar A1 tiene siete mazos que son el mismo punto partido en siete, y
al 60 % de maduras se leería como nivel sostenido.

**Por qué se guarda, si todo lo demás en este app se deriva.** La regla de no
guardar existe para los hechos derivados de la colección: los nombres de mazo
cambian todo el tiempo y la derivación es instantánea y determinista. El
temario no cumple ninguna de las dos. Lo que enseña un A1 es un hecho externo y
estable, y derivarlo cuesta un minuto y **da distinto cada vez** — dos corridas
seguidas sobre Grammar A1, sin tocar nada, dieron 7/14 y 3/14. Un número que se
mueve solo no es un diagnóstico.

Lo que sí se sigue derivando en cada lectura es la **cobertura**: qué mazo
cubre qué punto. Eso sí es un hecho sobre la colección y cambia cada vez que
escribís una tarjeta.

**Y guardarlo lo vuelve tuyo.** Era el único lugar del app donde el modelo
decidía y vos no opinabas. Estos archivos son texto plano a propósito: borrá un
punto que no te interesa, agregá el que tu trabajo necesita, reordenalos. Nada
los reescribe salvo que pidas regenerar.
"""
import json
import os
import re
from datetime import datetime
from pathlib import Path

SYLLABUS_DIR = Path(__file__).resolve().parent / "data" / "syllabus"


def _slug(value: str) -> str:
    """`Grammar` → `Grammar`. Un nombre de archivo, no una ruta.

    Skill y level ya vienen validados contra `analysis.SKILLS` / `LEVELS` antes
    de llegar acá, pero esto es lo que construye una ruta en el disco: se
    verifica igual, porque el día que alguien llame a esto desde otro lado el
    error sería escribir fuera de `data/`.
    """
    cleaned = re.sub(r"[^A-Za-z0-9]", "", str(value or ""))
    if not cleaned:
        raise ValueError(f"nombre inservible para un archivo: {value!r}")
    return cleaned


def path_for(skill: str, level: str) -> Path:
    return SYLLABUS_DIR / f"{_slug(skill)}-{_slug(level)}.json"


def load(skill: str, level: str) -> dict | None:
    """El temario guardado, o None si ese nivel no tiene todavía.

    Un archivo que no se puede leer se trata como si no existiera: el temario
    se puede volver a generar, y romper la pantalla por un JSON a medio
    escribir sería peor que tardar un minuto.
    """
    try:
        stored = json.loads(path_for(skill, level).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(stored, dict) or not isinstance(stored.get("points"), list):
        return None

    # Se relee con la misma desconfianza con la que se escribió: el archivo es
    # editable a mano y ésa es la gracia, así que una entrada rota se descarta
    # en vez de tumbar la pantalla.
    points = []
    for item in stored["points"]:
        if not isinstance(item, dict):
            continue
        name = " ".join(str(item.get("point", "")).split())[:80]
        if not name:
            continue
        points.append({
            "point": name,
            "english": " ".join(str(item.get("english", "")).split())[:80],
            "drafts": item.get("drafts"),
        })
    if not points:
        return None

    return {
        "skill": skill,
        "level": level,
        "points": points,
        "drafts": stored.get("drafts"),
        "generated": stored.get("generated"),
        "edited": _edited_after(path_for(skill, level), stored.get("generated")),
    }


def _edited_after(path: Path, generated: str | None) -> bool:
    """Si el archivo se tocó después de escribirlo, lo tocaste vos.

    Sirve para no ofrecer "regenerar" como si fuera gratis sobre un temario que
    alguien editó a mano: regenerar lo pisa, y el trabajo perdido no se avisa
    solo.
    """
    if not generated:
        return False
    try:
        written = datetime.fromisoformat(generated).timestamp()
        return path.stat().st_mtime > written + 2   # margen para el propio write
    except (ValueError, OSError):
        return False


def save(skill: str, level: str, points: list[dict], drafts: int,
         generated: str) -> dict:
    """Congelar el temario de un nivel. Sobrescribe si ya había uno."""
    path = path_for(skill, level)
    payload = {
        "skill": skill,
        "level": level,
        "generated": generated,
        "drafts": drafts,
        # Sin `covered_by`: la cobertura se deriva en cada lectura y guardarla
        # sería exactamente la copia que se desincroniza.
        "points": [
            {"point": p["point"], "english": p.get("english", ""),
             "drafts": p.get("drafts")}
            for p in points
        ],
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.part")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    os.replace(tmp, path)   # un corte a mitad de escritura no deja basura
    return payload


def levels_held() -> list[str]:
    """`["Grammar-A1", …]` — los niveles que ya tienen temario congelado."""
    try:
        return sorted(p.stem for p in SYLLABUS_DIR.glob("*.json"))
    except OSError:
        return []
