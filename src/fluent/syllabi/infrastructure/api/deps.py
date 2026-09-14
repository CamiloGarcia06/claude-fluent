from dataclasses import dataclass

from fastapi import Request

from fluent.syllabi.application.cover_syllabus import CoverSyllabus
from fluent.syllabi.application.freeze_syllabus import FreezeSyllabus
from fluent.syllabi.application.read_syllabus import ReadSyllabus


@dataclass(frozen=True)
class SyllabusUseCases:
    read: ReadSyllabus
    freeze: FreezeSyllabus
    cover: CoverSyllabus


def get_syllabi(request: Request) -> SyllabusUseCases:
    return request.app.state.syllabi
