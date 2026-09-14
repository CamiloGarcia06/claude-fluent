from fluent.shared.errors import Conflict, Invalid, Unavailable, Upstream


class AnkiNotRunning(Unavailable):
    code = "anki_not_running"
    message = "AnkiConnect is not answering — is Anki running?"


class UnknownSkillOrLevel(Invalid):
    code = "unknown_skill_or_level"
    message = "unknown skill or level"


class NoSyllabusYet(Conflict):
    code = "no_syllabus_yet"
    message = "ese nivel todavía no tiene temario congelado"


class ModelFailed(Upstream):
    code = "model_failed"


class ModelReturnedNothing(Upstream):
    code = "model_returned_nothing"
    message = "el modelo no devolvió ningún punto"
