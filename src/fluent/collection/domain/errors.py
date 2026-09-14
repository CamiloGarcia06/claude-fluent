from fluent.shared.errors import Unavailable


class AnkiNotRunning(Unavailable):
    code = "anki_not_running"
    message = "AnkiConnect is not answering — is Anki running?"
