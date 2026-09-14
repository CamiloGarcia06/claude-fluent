from fastapi import APIRouter, Depends

from .deps import SettingsUseCases, get_settings

router = APIRouter(prefix="/api", tags=["settings"])


@router.get("/settings")
def settings(uc: SettingsUseCases = Depends(get_settings)) -> dict:
    return uc.read()


@router.post("/settings")
def save_settings(
    payload: dict | None = None, uc: SettingsUseCases = Depends(get_settings)
) -> dict:
    return uc.write(payload or {})
