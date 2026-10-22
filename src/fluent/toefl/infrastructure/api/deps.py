from dataclasses import dataclass

from fastapi import Request

from fluent.toefl.application.get_overview import GetOverview
from fluent.toefl.application.grade_attempt import GradeAttempt
from fluent.toefl.application.next_item import NextItem
from fluent.toefl.application.refill_bank import RefillBank


@dataclass(frozen=True)
class ToeflUseCases:
    overview: GetOverview
    next_item: NextItem
    grade: GradeAttempt
    refill: RefillBank


def get_toefl(request: Request) -> ToeflUseCases:
    return request.app.state.toefl
