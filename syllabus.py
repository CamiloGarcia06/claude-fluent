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
import shutil
from datetime import datetime
from pathlib import Path

SYLLABUS_DIR = Path(__file__).resolve().parent / "data" / "syllabus"

# La cobertura vive **al lado** y no adentro del temario, y son tres razones.
#
# El temario es el único archivo del app que es tuyo para editar; si además
# guardara lo que el modelo midió, al abrirlo no podrías separar lo que
# decidiste vos de lo que se calculó hace dos semanas.
#
# `load()` decide "editado a mano" comparando el mtime del archivo contra su
# propio campo `generated`. Si el app le escribiera la cobertura encima, cada
# lectura movería el mtime y la pantalla diría "editado a mano" siempre, y
# "Regenerar" avisaría de perder ediciones que nunca hiciste.
#
# Y un caché tiene que poder borrarse sin perder nada: `rm -rf
# data/syllabus/coverage/` cuesta medio minuto una vez. Mezclado, costaría el
# temario.
COVERAGE_DIR = SYLLABUS_DIR / "coverage"


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
    except (OSError, json.JSONDecodeError, ValueError):
        # `OSError` y no `FileNotFoundError`: un archivo sin permiso de lectura
        # o un directorio con ese nombre reventaban la pantalla con un 500.
        # Distinguir "no existe" de "no se puede leer" es trabajo de `status`,
        # que mira el disco en vez de adivinarlo por la excepción.
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


def status(skill: str, level: str) -> str:
    """`"missing"` · `"ok"` · `"unreadable"`.

    `load()` devuelve None para dos situaciones muy distintas: el nivel que
    todavía no tiene temario —la primera vez, que no es un error— y el archivo
    que existe y no se puede leer. La pantalla las trataba igual y por eso el
    primer clic en "Ver temario" reemplazaba un archivo roto por una generación
    nueva, sin preguntar: si lo habías editado a mano, ese trabajo se iba sin
    que nada lo dijera.
    """
    try:
        path = path_for(skill, level)
    except ValueError:
        return "missing"
    if not path.exists():
        return "missing"
    return "ok" if load(skill, level) is not None else "unreadable"


def unreadable() -> list[str]:
    """`["Grammar-A1"]` — los archivos de temario que existen y no se leen.

    Lo que mira Ajustes, que es la pantalla de lo que falla en silencio. Sin
    esto, un temario roto se descubre recién cuando ya te lo regeneraron: tu
    edición "no toma", el app se ve normal, y no hay dónde enterarse.
    """
    bad = []
    for path in sorted(SYLLABUS_DIR.glob("*.json")):
        skill, _, level = path.stem.partition("-")
        try:
            if load(skill, level) is None:
                bad.append(path.stem)
        except ValueError:
            # Un archivo en esa carpeta con un nombre que no es Skill-Level: el
            # app nunca lo va a buscar, así que para vos es lo mismo que roto.
            bad.append(path.stem)
    return bad


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

    # Copia del anterior antes de pisarlo. Regenerar es la única acción
    # destructiva de esta pantalla y ya se llevó puesto un temario: un archivo
    # ilegible se trata como inexistente —a propósito, para que la pantalla no
    # se caiga— y el primer clic en "Ver temario" lo reemplaza por una
    # generación nueva sin preguntar. `data/` no está en git, así que sin esto
    # no hay de dónde volver.
    if path.exists():
        try:
            shutil.copy2(path, path.with_suffix(".json.bak"))
        except OSError:
            pass   # una copia que no se pudo hacer no puede impedir el guardado

    tmp = path.with_suffix(".json.part")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    os.replace(tmp, path)   # un corte a mitad de escritura no deja basura
    return payload


# ── La cobertura ──────────────────────────────────────────────────────
# Qué mazo tuyo cubre cada punto. Sigue siendo un hecho derivado y sigue
# cambiando con cada tarjeta que escribís — lo que cambia es la frecuencia: eso
# justifica recalcularla **cuando algo cambió**, no en cada lectura. Entre dos
# lecturas en las que no tocaste una tarjeta, esos treinta segundos no compran
# nada.
#
# Por eso se guarda junto con aquello de lo que depende: los mazos de ese nivel
# con su cantidad de tarjetas. Quien lee compara ese mapa con el de ahora y
# sabe si lo guardado todavía vale. No hay hash ni versión: dos mapas chicos y
# una comparación, que es algo que las dos puntas pueden hacer sin ponerse de
# acuerdo en un algoritmo.


def coverage_path_for(skill: str, level: str) -> Path:
    return COVERAGE_DIR / f"{_slug(skill)}-{_slug(level)}.json"


def load_coverage(skill: str, level: str, points: list[dict]) -> dict | None:
    """La cobertura guardada de este nivel, si sirve para **estos** puntos.

    Vale sólo para la lista exacta con la que se calculó: si agregaste o
    renombraste un punto, lo guardado no dice nada sobre él, y rellenar el
    hueco con "no cubierto" sería afirmar algo que nadie miró. El lado seguro
    del error acá es no tener respuesta, igual que en `cover()`.
    """
    try:
        stored = json.loads(
            coverage_path_for(skill, level).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, ValueError, OSError):
        return None
    if not isinstance(stored, dict):
        return None

    by_point = stored.get("by_point")
    decks = stored.get("decks")
    if not isinstance(by_point, dict) or not isinstance(decks, dict):
        return None
    if set(by_point) != {p["point"] for p in points}:
        return None

    return {
        "computed": stored.get("computed"),
        "decks": {str(k): int(v) for k, v in decks.items()
                  if isinstance(v, (int, float))},
        "by_point": {
            name: {
                "covered_by": str((entry or {}).get("covered_by", ""))[:120],
                "note": str((entry or {}).get("note", ""))[:200],
            }
            for name, entry in by_point.items() if isinstance(entry, dict)
        },
    }


def save_coverage(skill: str, level: str, points: list[dict],
                  decks: dict[str, int], computed: str) -> dict:
    """Guardar lo que acaba de costar medio minuto, con su fecha y sus mazos."""
    payload = {
        "skill": skill,
        "level": level,
        "computed": computed,
        # De qué depende la respuesta. Un mazo nuevo, uno borrado o una tarjeta
        # más y esto deja de coincidir, que es exactamente cuando la cobertura
        # deja de valer. Editar el frente de una tarjeta sin cambiar la cuenta
        # no se nota: es el hueco conocido de esta huella, y el precio de que
        # sea barata.
        "decks": {str(name): int(total) for name, total in decks.items()},
        "by_point": {
            p["point"]: {"covered_by": p.get("covered_by", ""),
                         "note": p.get("note", "")}
            for p in points
        },
    }

    path = coverage_path_for(skill, level)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.part")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    os.replace(tmp, path)
    return payload


def levels_held() -> list[str]:
    """`["Grammar-A1", …]` — los niveles que ya tienen temario congelado."""
    try:
        return sorted(p.stem for p in SYLLABUS_DIR.glob("*.json"))
    except OSError:
        return []
