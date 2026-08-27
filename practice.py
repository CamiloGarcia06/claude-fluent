"""`data/practice/` — las sesiones de escritura y el conteo de patrones.

Cero modelo, cero Anki: acá sólo se lee y se escribe disco. El molde es
`syllabus.py`, y por las mismas razones — escritura atómica, relectura
desconfiada, y archivos que son tuyos para editar a mano.

**Por qué la conversación vive en disco y no en el navegador.** `llm.generate`
no tiene memoria: cada turno serializa el historial dentro del prompt, así que
el historial tiene que sobrevivir al proceso de todas formas. El archivo *es* la
conversación. Guardarla además en un dict del servidor sería una segunda copia,
y las segundas copias se desincronizan.

**El turno se escribe dos veces.** Primero tu texto, con `state: "pending"`, y
recién después se llama al modelo; cuando aterriza se reescribe el mismo índice
con `state: "done"`. Un turno tarda entre trece y veintiún segundos y recargar
en el medio es normal: sin ese primer write tu mensaje desaparece de la pantalla
y reaparece solo cuando el subprocess termina.

**El contador no es un motor de repaso.** No hay intervalo, ni facilidad, ni
cola, ni fecha de próximo repaso, ni nada que decida cuándo estudiás. Es un
diagnóstico con un disparador, y lo que dispara es abrir `#/agregar`. Anki
sigue siendo dueño de cada repaso.
"""
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

import coach

PRACTICE_DIR = Path(__file__).resolve().parent / "data" / "practice"
SESSIONS_DIR = PRACTICE_DIR / "sessions"
PATTERNS_PATH = PRACTICE_DIR / "patterns.json"

# Tres, que es lo que el diseño de la carta ya decía: "este error ya te pasó 3
# veces: se vuelve tarjeta propia". Y son tres **sesiones**, no tres veces:
# escribir "I have 25 years" tres veces en un párrafo es un hábito, no tres
# errores.
PATTERN_THRESHOLD = 3

# Una sesión de cien turnos hace un prompt de cierre enorme y un análisis vago.
MAX_TURNS = 30

MAX_EXAMPLES = 3

_ID = re.compile(r"\d{8}-\d{6}")


def _valid_id(value) -> str:
    """El id que llega del cliente construye una ruta en el disco.

    Skill y level se validan contra tuplas cerradas en otras partes del app por
    la misma razón: acá el error sería escribir fuera de `data/`.
    """
    text = str(value or "").strip()
    if not _ID.fullmatch(text):
        raise ValueError("id de sesión inválido")
    return text


def path_for(session_id: str) -> Path:
    return SESSIONS_DIR / f"{_valid_id(session_id)}.json"


def _write(path: Path, payload: dict) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.part")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    os.replace(tmp, path)   # un corte a mitad de escritura no deja basura
    return payload


# ── Sesiones ──────────────────────────────────────────────────────────────

def new_session(topic: str, level: str) -> dict:
    """Abrir una sesión nueva, sin pisar ninguna.

    El id tiene resolución de un segundo, así que dos sesiones abiertas dentro
    del mismo segundo lo compartirían y la segunda sobrescribiría el archivo de
    la primera. No es hipotético: cerrar y apretar "practicar de nuevo" es un
    clic, y el análisis recién guardado se perdía. Si el id ya existe se corre
    un segundo hacia adelante, que mantiene el formato ordenable.
    """
    now = datetime.now()
    while path_for(now.strftime("%Y%m%d-%H%M%S")).exists():
        now += timedelta(seconds=1)

    return _write(path_for(now.strftime("%Y%m%d-%H%M%S")), {
        "id": now.strftime("%Y%m%d-%H%M%S"),
        "started": now.isoformat(timespec="seconds"),
        "topic": topic,
        "level": level,
        "closed": False,
        "closed_at": None,
        "abandoned": False,
        "turns": [],
        "analysis": None,
    })


def load(session_id: str) -> dict | None:
    """Una sesión, o None si no existe o no se puede leer.

    Se relee con la misma desconfianza con la que se escribió: un turno roto se
    descarta en vez de tumbar la pantalla, porque el archivo es texto plano y
    editable a mano.
    """
    try:
        stored = json.loads(path_for(session_id).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, ValueError, OSError):
        return None
    if not isinstance(stored, dict) or not isinstance(stored.get("turns"), list):
        return None

    turns = []
    for item in stored["turns"]:
        if not isinstance(item, dict) or not str(item.get("text", "")).strip():
            continue
        try:
            index = int(item["index"])
        except (KeyError, TypeError, ValueError):
            continue
        state = item.get("state")
        turns.append({
            "index": index,
            "at": item.get("at"),
            "text": str(item["text"]),
            "state": state if state in ("pending", "done", "failed") else "failed",
            "reply": str(item.get("reply", "")),
            "question": str(item.get("question", "")),
            "alternative": str(item.get("alternative", "")),
            "corrections": [c for c in item.get("corrections", [])
                            if isinstance(c, dict)],
            "error": str(item.get("error", "")),
            "duration_ms": item.get("duration_ms"),
        })
    turns.sort(key=lambda t: t["index"])

    return {
        "id": stored.get("id", session_id),
        "started": stored.get("started"),
        "topic": str(stored.get("topic", "")),
        "level": str(stored.get("level", "")),
        "closed": bool(stored.get("closed")),
        "closed_at": stored.get("closed_at"),
        "abandoned": bool(stored.get("abandoned")),
        "turns": turns,
        "analysis": stored.get("analysis"),
    }


def save(session: dict) -> dict:
    return _write(path_for(session["id"]), session)


def open_session() -> dict | None:
    """La sesión abierta, que es la más reciente sin cerrar.

    Los nombres de archivo son `YYYYMMDD-HHMMSS`, así que el orden alfabético
    ya es el cronológico y no hace falta leer todos los archivos para ordenar.
    """
    try:
        names = sorted((p.stem for p in SESSIONS_DIR.glob("*.json")), reverse=True)
    except OSError:
        return None
    for name in names:
        session = load(name)
        if session and not session["closed"]:
            return session
    return None


def last_closed() -> dict | None:
    """La última sesión cerrada que tenga análisis.

    Sin esto el análisis es de un solo uso: se pinta al cerrar y en cuanto
    navegás a otra pantalla no hay forma de volver — aunque el archivo esté
    entero en el disco. Es la salida más valiosa de la práctica y la única que
    no se podía releer.
    """
    try:
        names = sorted((p.stem for p in SESSIONS_DIR.glob("*.json")), reverse=True)
    except OSError:
        return None
    for name in names:
        session = load(name)
        if session and session["closed"] and session["analysis"]:
            return session
    return None


def recent_topics(limit: int = 4) -> list[str]:
    """Los temas de tus últimas sesiones, del más reciente al más viejo.

    Se probó sacarlos de los mazos y no sirve: el tema de un mazo dice qué
    enseña, y en Grammar eso es una regla — «Negatives with any» no es algo
    sobre lo que se pueda conversar. Un tema que ya elegiste, en cambio, es un
    tema de conversación probado, porque conversaste sobre él.
    """
    try:
        names = sorted((p.stem for p in SESSIONS_DIR.glob("*.json")), reverse=True)
    except OSError:
        return []

    seen, topics = set(), []
    for name in names:
        session = load(name)
        if not session:
            continue
        topic = session["topic"].strip()
        key = topic.lower()
        if topic and key not in seen:
            seen.add(key)
            topics.append(topic)
        if len(topics) == limit:
            break
    return topics


def append_turn(session: dict, text: str) -> dict:
    """Persistir el mensaje antes de llamar al modelo."""
    turn = {
        "index": len(session["turns"]),
        "at": datetime.now().isoformat(timespec="seconds"),
        "text": text,
        "state": "pending",
        "reply": "", "question": "", "alternative": "",
        "corrections": [], "error": "", "duration_ms": None,
    }
    session["turns"].append(turn)
    save(session)
    return turn


def retry_turn(session: dict, index: int, text: str) -> dict:
    """Volver a intentar un turno que quedó colgado o falló.

    Reescribe ese mismo índice en vez de agregar uno nuevo: agregando, tu
    mensaje aparecería dos veces en el hilo y el fallido quedaría ahí como un
    bloque muerto.
    """
    turn = session["turns"][index]
    if turn["state"] == "done":
        raise ValueError("ese turno ya está respondido")
    turn.update(text=text, state="pending", reply="", question="",
                alternative="", corrections=[], error="", duration_ms=None)
    save(session)
    return turn


def finish_turn(session: dict, index: int, answer: dict | None,
                error: str = "") -> dict:
    """Reescribir ese mismo índice con lo que aterrizó, o con el fallo."""
    turn = session["turns"][index]
    if answer is None:
        turn["state"] = "failed"
        turn["error"] = error
    else:
        turn.update(state="done", error="", **{
            k: answer[k] for k in
            ("reply", "question", "alternative", "corrections", "duration_ms")
        })
    save(session)
    return turn


# ── Patrones ──────────────────────────────────────────────────────────────

def _empty() -> dict:
    return {"patterns": {}, "unmatched": {}}


def read_patterns() -> dict:
    """Lo guardado, saneado. Un archivo ilegible se trata como vacío.

    Una clave que no está en el catálogo se ignora: el catálogo puede encoger
    entre versiones y un contador huérfano pediría una tarjeta que ya nadie
    sabe escribir. Un `count` que dice "tres" se descarta por la misma regla.
    """
    try:
        stored = json.loads(PATTERNS_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return _empty()
    if not isinstance(stored, dict):
        return _empty()

    patterns = {}
    for key, item in (stored.get("patterns") or {}).items():
        if key not in coach.PATTERN_BY_KEY or not isinstance(item, dict):
            continue
        # Sólo ids de sesión, y todos con la misma forma: `cleared` se compara
        # con estas cadenas, y una fecha ISO mezclada acá ordenaría antes que
        # cualquier id (`-` viene antes que un dígito) y limpiaría de más.
        sessions = [s for s in item.get("sessions", [])
                    if isinstance(s, str) and _ID.fullmatch(s)]
        if not sessions:
            continue
        examples = []
        for example in item.get("examples", []):
            if isinstance(example, dict) and example.get("wrong"):
                examples.append({"wrong": str(example["wrong"])[:200],
                                 "right": str(example.get("right", ""))[:200]})
            elif isinstance(example, str) and example.strip():
                # Formato viejo: sólo el error, sin su par. Se conserva para no
                # perder el conteo de un archivo anterior a este cambio.
                examples.append({"wrong": example.strip()[:200], "right": ""})
        patterns[key] = {
            "sessions": sorted(set(sessions)),
            "occurrences": item.get("occurrences")
                if isinstance(item.get("occurrences"), int) else len(sessions),
            "examples": examples[:MAX_EXAMPLES],
            "cleared": item.get("cleared") if isinstance(item.get("cleared"), str) else None,
            "carded": item.get("carded") if isinstance(item.get("carded"), str) else None,
        }

    unmatched = {k: v for k, v in (stored.get("unmatched") or {}).items()
                 if isinstance(k, str) and isinstance(v, int)}
    return {"patterns": patterns, "unmatched": unmatched}


def count(stored: dict, areas: list[dict], unmatched: list[str],
          session_id: str) -> dict:
    """Sumar un cierre al conteo. Pura: recibe lo guardado, devuelve lo nuevo.

    Un patrón sube **como máximo uno por sesión**, aunque el mismo hábito
    aparezca en dos hallazgos: lo que se cuenta es el hábito, no la ocurrencia.
    `occurrences` guarda el total sólo como dato de color y nunca es titular.

    Lo que se guarda es el **id de la sesión** y no la fecha. Con la fecha, dos
    sesiones de la misma tarde contaban una sola vez, y la pantalla que dice
    "te pasó en 3 sesiones" habría estado mintiendo.
    """
    patterns = {k: dict(v) for k, v in stored.get("patterns", {}).items()}

    for area in areas:
        key = area.get("pattern")
        if not key or key not in coach.PATTERN_BY_KEY:
            continue
        entry = patterns.setdefault(
            key, {"sessions": [], "occurrences": 0, "examples": [],
                  "cleared": None, "carded": None})
        entry["sessions"] = sorted(set(entry["sessions"]) | {session_id})
        entry["occurrences"] += max(len(area.get("examples", [])), 1)
        # El par entero, no sólo el error: cuando este patrón se vuelva tarjeta,
        # `wrong` es literalmente el ejercicio de «corregir» y `right` su
        # respuesta. Guardar la mitad sería pedirle al modelo que reinvente algo
        # que ya tuvo delante.
        have = {e["wrong"] for e in entry["examples"]}
        for case in area.get("examples", []):
            wrong = case.get("wrong", "")
            if wrong and wrong not in have and len(entry["examples"]) < MAX_EXAMPLES:
                entry["examples"].append(
                    {"wrong": wrong, "right": case.get("right", "")})
                have.add(wrong)

    misses = dict(stored.get("unmatched", {}))
    for claimed in unmatched:
        misses[claimed] = misses.get(claimed, 0) + 1

    return {"patterns": patterns, "unmatched": misses}


def write_patterns(stored: dict) -> dict:
    return _write(PATTERNS_PATH, stored)


def _count_of(entry: dict) -> int:
    """Sesiones que cuentan: las posteriores a la última vez que se limpió.

    El contador se deriva en vez de guardarse, así que no puede discrepar de
    la lista que tiene al lado. Y limpiar no borra historia: mueve la raya.
    """
    cleared = entry.get("cleared")
    return len([s for s in entry["sessions"] if not cleared or s > cleared])


def _day(session_id: str) -> str:
    """`20260826-184448` → `2026-08-26`, para mostrar."""
    return f"{session_id[0:4]}-{session_id[4:6]}-{session_id[6:8]}"


def listing(stored: dict) -> list[dict]:
    """Los patrones, con su ficha del catálogo, para la pantalla."""
    rows = []
    for key, entry in stored.get("patterns", {}).items():
        spec = coach.PATTERN_BY_KEY[key]
        n = _count_of(entry)
        rows.append({
            "key": key,
            "label": spec["label"],
            "category": spec["category"],
            "skill": spec["skill"],
            "level": spec["level"],
            "seed": spec["seed"],
            "count": n,
            "occurrences": entry["occurrences"],
            "last_seen": _day(entry["sessions"][-1]) if entry["sessions"] else None,
            "examples": entry["examples"],
            "carded": _day(entry["carded"]) if entry["carded"] else None,
            "ready": n >= PATTERN_THRESHOLD,
        })
    # Dos pasadas y no una tupla: `count` va de mayor a menor y `last_seen` de
    # más nueva a más vieja, y un `-` no se le puede poner a una fecha ISO. El
    # sort de Python es estable, así que la segunda respeta el orden de la
    # primera dentro de cada empate.
    rows.sort(key=lambda r: r["last_seen"] or "", reverse=True)
    rows.sort(key=lambda r: r["count"], reverse=True)
    return rows


def mark(stored: dict, key: str, action: str, stamp: str) -> dict:
    """`carded` cuando ya escribiste la tarjeta, `reset` cuando no te importa.

    Sin esto la fila te reclama la misma tarjeta para siempre.
    """
    if key not in coach.PATTERN_BY_KEY:
        raise ValueError("ese patrón no está en el catálogo")
    if action not in ("carded", "reset"):
        raise ValueError("la acción tiene que ser carded o reset")
    patterns = {k: dict(v) for k, v in stored.get("patterns", {}).items()}
    entry = patterns.get(key)
    if entry is None:
        raise ValueError("ese patrón todavía no te apareció")
    entry["cleared"] = stamp
    if action == "carded":
        entry["carded"] = stamp
    return {"patterns": patterns, "unmatched": dict(stored.get("unmatched", {}))}


def stamp() -> str:
    """La misma forma que un id de sesión, para que la comparación sea una sola."""
    return datetime.now().strftime("%Y%m%d-%H%M%S")
