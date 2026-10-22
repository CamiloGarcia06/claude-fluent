from fluent.shared.errors import Conflict, Invalid, NotFound, Upstream


class UnknownKind(Invalid):
    code = "unknown_kind"
    message = "ese tipo de ejercicio no existe"


class UnknownPattern(Invalid):
    code = "unknown_pattern"
    message = "ese patrón no existe"


class ItemNotFound(NotFound):
    code = "item_not_found"
    message = "ese ejercicio no está en el banco"


class BankEmpty(Conflict):
    """No queda ningún ejercicio sin hacer: la pantalla ofrece generar más."""

    code = "bank_empty"
    message = "ya hiciste todos los ejercicios del banco"


class NothingGenerated(Upstream):
    code = "nothing_generated"
    message = "el modelo no devolvió ningún ejercicio que sirva"


class ModelFailed(Upstream):
    code = "model_failed"
