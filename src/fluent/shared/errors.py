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


class Upstream(DomainError):
    """Algo de fuera respondió mal: el modelo devolvió basura o falló a mitad."""

    code = "upstream"


class NotFound(DomainError):
    code = "not_found"


class Conflict(DomainError):
    code = "conflict"


class Invalid(DomainError):
    code = "invalid"
