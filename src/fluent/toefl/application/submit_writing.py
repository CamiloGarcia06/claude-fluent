"""Caso de uso: entregar un email o una contribución a la discusión y recibir
la corrección con la rúbrica de ETS.

Una entrega cuenta como un intento por cada criterio de la rúbrica: fallado si
el corrector lo marcó o si hay una corrección de esa categoría. Así los
consejos de writing salen del mismo cálculo que los de los ejercicios cerrados,
sin un segundo sistema que mantener.

**La reescritura no cuenta para los consejos.** Volver a escribir el mismo texto
con las correcciones a la vista es donde se aprende el error, pero no mide cómo
escribís en el examen: se corrige igual, se guarda marcada, y devuelve la nota
de la primera versión para comparar. Los consejos siguen midiendo primeros
intentos, con reloj."""

from fluent.toefl.domain.catalog import WRITING_KINDS, WRITING_PATTERNS, tip_card
from fluent.toefl.domain.entities import Attempt
from fluent.toefl.domain.errors import BadFeedback, ItemNotFound, NoText, TextTooLong, UnknownKind
from fluent.toefl.domain.ports import AttemptLog, Clock, Grader, ItemBank, SubmissionLog
from fluent.toefl.domain.writing import (
    MAX_SCORE,
    MAX_TEXT_CHARS,
    DiscussionPrompt,
    EmailPrompt,
    build_feedback,
)


class SubmitWriting:
    def __init__(
        self,
        bank: ItemBank,
        grader: Grader,
        log: AttemptLog,
        submissions: SubmissionLog,
        clock: Clock,
    ) -> None:
        self._bank = bank
        self._grader = grader
        self._log = log
        self._submissions = submissions
        self._clock = clock

    def __call__(self, kind, item_id, text, seconds=None, revision=False) -> dict:
        if kind not in WRITING_KINDS:
            raise UnknownKind()
        text = str(text or "").strip()
        if not text:
            raise NoText()
        if len(text) > MAX_TEXT_CHARS:
            raise TextTooLong()
        prompt = next((i for i in self._bank.items(kind) if i.id == item_id), None)
        if not isinstance(prompt, (EmailPrompt, DiscussionPrompt)):
            raise ItemNotFound()

        raw = self._grader.grade(kind, prompt.brief(), text)
        try:
            feedback = build_feedback(raw, kind, text)
        except (ValueError, TypeError, AttributeError) as e:
            raise BadFeedback() from e

        at = self._clock.now().isoformat(timespec="seconds")
        flagged = feedback.flagged()
        revision = bool(revision)
        first = next(
            (
                row
                for row in reversed(self._submissions.recent(kind))
                if row.get("item_id") == prompt.id and not row.get("revision")
            ),
            None,
        )
        if not revision:
            self._log.append(
                [
                    Attempt(kind, prompt.id, p.key, p.key not in flagged, at)
                    for p in WRITING_PATTERNS
                ]
            )
        elapsed = seconds if isinstance(seconds, int) and seconds >= 0 else None
        self._submissions.append(
            {
                "kind": kind,
                "item_id": prompt.id,
                "at": at,
                "seconds": elapsed,
                "text": text,
                "score": feedback.score,
                "words": feedback.words,
                "flagged": flagged,
                "revision": revision,
            }
        )
        return {
            "score": feedback.score,
            "max_score": MAX_SCORE,
            "words": feedback.words,
            "summary": feedback.summary,
            "criteria": [
                {"key": c.key, "ok": c.ok, "comment": c.comment, "label": tip_card(c.key)["label"]}
                for c in feedback.criteria
            ],
            "corrections": [
                {"wrong": c.wrong, "right": c.right, "why": c.why, "category": c.category}
                for c in feedback.corrections
            ],
            "improved": feedback.improved,
            "revision": revision,
            "first_score": first.get("score") if revision and first else None,
            "tips": [tip_card(key) for key in flagged],
        }
