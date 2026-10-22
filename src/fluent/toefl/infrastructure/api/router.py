"""El entrenamiento del TOEFL. Como la práctica de escritura, no toca Anki: el
banco vive en data/toefl/ y sigue funcionando con Anki cerrado."""

from fastapi import APIRouter, Depends

from .deps import ToeflUseCases, get_toefl

router = APIRouter(prefix="/api/toefl", tags=["toefl"])


@router.get("/overview")
def toefl_overview(uc: ToeflUseCases = Depends(get_toefl)) -> dict:
    return uc.overview()


@router.get("/next/{kind}")
def toefl_next(kind: str, uc: ToeflUseCases = Depends(get_toefl)) -> dict:
    return uc.next_item(kind)


@router.post("/grade")
def toefl_grade(payload: dict, uc: ToeflUseCases = Depends(get_toefl)) -> dict:
    return uc.grade(payload.get("kind"), payload.get("item_id"), payload.get("answer"))


@router.post("/submit")
def toefl_submit(payload: dict, uc: ToeflUseCases = Depends(get_toefl)) -> dict:
    return uc.submit(
        payload.get("kind"),
        payload.get("item_id"),
        payload.get("text"),
        payload.get("seconds"),
        payload.get("revision", False),
    )


@router.post("/read")
def toefl_read(payload: dict, uc: ToeflUseCases = Depends(get_toefl)) -> dict:
    return uc.read(
        payload.get("kind"), payload.get("item_id"), payload.get("answers"), payload.get("seconds")
    )


@router.post("/refill")
def toefl_refill(payload: dict, uc: ToeflUseCases = Depends(get_toefl)) -> dict:
    return uc.refill(payload.get("kind"), payload.get("focus"))
