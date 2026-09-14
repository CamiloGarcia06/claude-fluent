"""El temario de un nivel: leerlo, congelarlo y cubrirlo con tus mazos."""

from fastapi import APIRouter, Depends

from .deps import SyllabusUseCases, get_syllabi

router = APIRouter(prefix="/api", tags=["syllabi"])


@router.get("/syllabus")
def syllabus_frozen(
    skill: str = "", level: str = "", uc: SyllabusUseCases = Depends(get_syllabi)
) -> dict:
    return uc.read(skill, level)


@router.post("/syllabus")
def syllabus_freeze(
    payload: dict | None = None, uc: SyllabusUseCases = Depends(get_syllabi)
) -> dict:
    body = payload or {}
    return uc.freeze(body.get("skill", ""), body.get("level", ""), bool(body.get("regenerate")))


@router.post("/syllabus/coverage")
def syllabus_coverage(
    payload: dict | None = None, uc: SyllabusUseCases = Depends(get_syllabi)
) -> dict:
    body = payload or {}
    return uc.cover(body.get("skill", ""), body.get("level", ""))
