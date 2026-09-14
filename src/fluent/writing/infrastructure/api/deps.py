from dataclasses import dataclass

from fastapi import Request

from fluent.writing.application.answer_turn import AnswerTurn
from fluent.writing.application.close_session import CloseSession
from fluent.writing.application.get_patterns import GetPatterns
from fluent.writing.application.get_practice import GetPractice
from fluent.writing.application.mark_pattern import MarkPattern
from fluent.writing.application.start_session import StartSession


@dataclass(frozen=True)
class WritingUseCases:
    get_practice: GetPractice
    start_session: StartSession
    answer_turn: AnswerTurn
    close_session: CloseSession
    get_patterns: GetPatterns
    mark_pattern: MarkPattern


def get_writing(request: Request) -> WritingUseCases:
    return request.app.state.writing
