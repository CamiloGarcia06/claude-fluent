from dataclasses import dataclass

from fastapi import Request

from fluent.settings.application.read_settings import ReadSettings
from fluent.settings.application.write_settings import WriteSettings


@dataclass(frozen=True)
class SettingsUseCases:
    read: ReadSettings
    write: WriteSettings


def get_settings(request: Request) -> SettingsUseCases:
    return request.app.state.settings
