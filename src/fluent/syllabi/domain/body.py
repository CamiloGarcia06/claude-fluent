"""La forma que devuelven las tres llamadas del temario.

Leer, congelar y cubrir hablan del mismo objeto y la pantalla lo dibuja con el
mismo código; que una devuelva una clave distinta es exactamente cómo se rompe.
`covered` es `None` mientras la cobertura no se derivó — no es cero, que querría
decir "ningún punto cubierto", que es otra cosa. Puro."""


def syllabus_body(
    stored: dict, path: str, points: list[dict] | None = None, coverage: dict | None = None
) -> dict:
    return {
        "skill": stored["skill"],
        "level": stored["level"],
        "frozen": True,
        "unreadable": False,
        "points": points if points is not None else stored["points"],
        "covered": (sum(1 for p in points if p["covered_by"]) if points is not None else None),
        "total": len(stored["points"]),
        "drafts": stored.get("drafts"),
        "generated": stored.get("generated"),
        "edited": stored.get("edited", False),
        # Cuándo se calculó la cobertura que viaja en `points`, y contra qué
        # mazos. Quien lee compara ese mapa con el de ahora y sabe si sigue
        # valiendo; el servidor no lo juzga.
        "coverage": coverage,
        "path": path,
    }


def empty_body(skill: str, level: str, unreadable: bool, path: str) -> dict:
    """Un nivel sin temario: `frozen: false` no es un error, es la primera vez."""
    return {
        "skill": skill,
        "level": level,
        "frozen": False,
        "unreadable": unreadable,
        "points": [],
        "covered": None,
        "total": 0,
        "drafts": None,
        "generated": None,
        "edited": False,
        "coverage": None,
        "path": path,
    }


def with_coverage(stored: dict, cached: dict) -> list[dict]:
    """Los puntos congelados con la cobertura guardada mezclada."""
    return [{**p, **cached["by_point"][p["point"]]} for p in stored["points"]]
