"""Jerarquía base de errores de dominio. Un solo traductor a HTTP en main.py
mientras dure la migración (después, shared/api_errors.py)."""


class DomainError(Exception):
    code = "domain_error"
    message = ""

    def __init__(self, message: str = "") -> None:
        super().__init__(message or self.message or self.code)
        if message:
            self.message = message


class Unavailable(DomainError):
    """Algo de fuera no responde: Anki cerrado, el modelo sin sesión."""

    code = "unavailable"


class Conflict(DomainError):
    code = "conflict"


class Invalid(DomainError):
    code = "invalid"
