"""El traductor de errores de dominio: un código HTTP por familia, y lo
inválido es 400 como siempre fue."""

from fluent.main import status_for
from fluent.shared.errors import Conflict, DomainError, Invalid, NotFound, Unavailable, Upstream


def test_status_by_family():
    assert status_for(Unavailable()) == 503
    assert status_for(Upstream()) == 502
    assert status_for(NotFound()) == 404
    assert status_for(Conflict()) == 409
    assert status_for(Invalid()) == 400
    assert status_for(DomainError()) == 400


def test_subclasses_inherit_their_family():
    from fluent.cards.domain.errors import ModelFailed, NoteNotFound, TermTooLong
    from fluent.writing.domain.errors import SessionAlreadyOpen

    assert status_for(TermTooLong()) == 400
    assert status_for(NoteNotFound()) == 404
    assert status_for(ModelFailed()) == 502
    assert status_for(SessionAlreadyOpen()) == 409
