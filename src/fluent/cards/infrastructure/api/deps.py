from dataclasses import dataclass

from fastapi import Request

from fluent.cards.application.apply_repair import ApplyRepair
from fluent.cards.application.propose_cards import ProposeCards
from fluent.cards.application.propose_terms import ProposeTerms
from fluent.cards.application.repair_note import RepairNote
from fluent.cards.application.write_notes import WriteNotes


@dataclass(frozen=True)
class CardUseCases:
    propose_terms: ProposeTerms
    propose_cards: ProposeCards
    write_notes: WriteNotes
    repair_note: RepairNote
    apply_repair: ApplyRepair


def get_cards(request: Request) -> CardUseCases:
    return request.app.state.cards
