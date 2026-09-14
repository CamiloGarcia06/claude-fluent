from fluent.shared.errors import Conflict, Invalid, NotFound, Upstream


class NoTopic(Invalid):
    code = "no_topic"
    message = "elegí un tema para conversar"


class SessionAlreadyOpen(Conflict):
    code = "session_already_open"
    message = "ya tenés una sesión abierta"


class InvalidSessionId(Invalid):
    code = "invalid_session_id"
    message = "id de sesión inválido"


class SessionNotFound(NotFound):
    code = "session_not_found"
    message = "esa sesión no existe"


class SessionClosed(Conflict):
    code = "session_closed"
    message = "esa sesión ya está cerrada"


class NoText(Invalid):
    code = "no_text"
    message = "no escribiste nada"


class TextTooLong(Invalid):
    code = "text_too_long"
    message = "el mensaje es demasiado largo"


class TooManyTurns(Conflict):
    code = "too_many_turns"


class BadRetry(Invalid):
    code = "bad_retry"


class BadPatternAction(Invalid):
    code = "bad_pattern_action"


class ModelFailed(Upstream):
    code = "model_failed"
