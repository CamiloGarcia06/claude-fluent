"""La práctica de escritura. Ninguno toca Anki: conversar en inglés no necesita
la colección, y heredar el guardia de 503 mataría la pantalla con Anki cerrado."""

from fastapi import APIRouter, Depends

from .deps import WritingUseCases, get_writing

router = APIRouter(prefix="/api/practice", tags=["writing"])


@router.get("/session")
def practice_session(uc: WritingUseCases = Depends(get_writing)) -> dict:
    return uc.get_practice()


@router.post("/session")
def practice_start(payload: dict | None = None, uc: WritingUseCases = Depends(get_writing)) -> dict:
    body = payload or {}
    return uc.start_session(body.get("topic", ""), body.get("level"), bool(body.get("restart")))


@router.post("/turn")
def practice_turn(payload: dict, uc: WritingUseCases = Depends(get_writing)) -> dict:
    return uc.answer_turn(
        payload.get("session_id"), payload.get("text", ""), payload.get("retry_index")
    )


@router.post("/close")
def practice_close(payload: dict, uc: WritingUseCases = Depends(get_writing)) -> dict:
    return uc.close_session(payload.get("session_id"))


@router.get("/patterns")
def practice_patterns(uc: WritingUseCases = Depends(get_writing)) -> dict:
    return uc.get_patterns()


@router.post("/patterns")
def practice_mark(payload: dict, uc: WritingUseCases = Depends(get_writing)) -> dict:
    return uc.mark_pattern(payload.get("key"), payload.get("action"))
