from fluent.shared.errors import Upstream


class ModelError(Upstream):
    """`claude -p` no está, falló, se colgó o devolvió algo inservible."""

    code = "model_error"
