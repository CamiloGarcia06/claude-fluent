from fluent.shared.errors import Conflict, Unavailable


class AnkiNotRunning(Unavailable):
    code = "anki_not_running"
    message = "AnkiConnect is not answering — is Anki running?"


class NothingDue(Conflict):
    code = "nothing_due"
    message = "No hay tarjetas pendientes hoy."
