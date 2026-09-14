from fluent.shared.errors import Invalid, NotFound, Unavailable, Upstream


class AnkiNotRunning(Unavailable):
    code = "anki_not_running"
    message = "AnkiConnect is not answering — is Anki running?"


class ModelFailed(Upstream):
    """`claude -p` falló o devolvió algo que no se pudo usar."""

    code = "model_failed"


class NoTerm(Invalid):
    code = "no_term"
    message = "no term"


class TermTooLong(Invalid):
    code = "term_too_long"
    message = "term too long"


class NoCards(Invalid):
    code = "no_cards"
    message = "no cards to add"


class TooManyCards(Invalid):
    code = "too_many_cards"


class MalformedCard(Invalid):
    code = "malformed_card"
    message = "malformed card"


class CardIncomplete(Invalid):
    code = "card_incomplete"
    message = "a card needs both a front and a back"


class InvalidDeckName(Invalid):
    code = "invalid_deck_name"


class NoteNotFound(NotFound):
    code = "note_not_found"


class NoFields(Invalid):
    code = "no_fields"
    message = "no fields to apply"


class UnknownFields(Invalid):
    code = "unknown_fields"
