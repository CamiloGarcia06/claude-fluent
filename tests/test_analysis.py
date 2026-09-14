"""Tests de caracterización de analysis.py: fijan lo que hoy hace, tal cual.

Son la red antes de mover nada. Si uno falla tras un cambio, o el cambio rompió
algo o el test describía un comportamiento que decidiste cambiar: en ese caso se
actualiza el test en el mismo commit.
"""

from datetime import date, datetime

from fluent import analysis
from fluent.anki import AGAIN, Review

GOOD = 3  # cualquier botón distinto de AGAIN


def ms(d: date, hour: int = 10) -> int:
    return int(datetime(d.year, d.month, d.day, hour).timestamp() * 1000)


def review(day: date, card_id: int = 1, *, deck: str = "Reading::A1::Words", button: int = GOOD,
           duration_ms: int = 4000, new_interval: int = 3, prev_interval: int = 1,
           review_type: int = 1, hour: int = 10) -> Review:
    return Review(ms(day, hour), card_id, 0, button, new_interval, prev_interval, 2500,
                  duration_ms, review_type, deck)


TODAY = date(2026, 9, 13)


class TestStreak:
    def test_empty(self):
        assert analysis.streak([], TODAY) == {
            "days": 0, "grace_used": [], "grace_left_this_month": 1, "studied_today": False,
        }

    def test_today_in_progress_does_not_break_the_streak(self):
        rows = [review(date(2026, 9, 12)), review(date(2026, 9, 11))]
        out = analysis.streak(rows, TODAY)
        assert out["days"] == 2 and out["studied_today"] is False and out["grace_used"] == []

    def test_one_grace_day_per_month_then_break(self):
        rows = [review(date(2026, 9, 13)), review(date(2026, 9, 11)), review(date(2026, 9, 9))]
        out = analysis.streak(rows, TODAY)
        # 13 sí, 12 gracia, 11 sí, 10 sin gracia → corta
        assert out["days"] == 2
        assert out["grace_used"] == ["2026-09-12"]
        assert out["grace_left_this_month"] == 0


def test_calendar_marks_days_before_start():
    rows = [review(date(2026, 9, 12)), review(date(2026, 9, 12), card_id=2)]
    cal = analysis.calendar(rows, TODAY, days=3)
    assert [c["date"] for c in cal] == ["2026-09-11", "2026-09-12", "2026-09-13"]
    assert [c["reviews"] for c in cal] == [0, 2, 0]
    assert [c["before_start"] for c in cal] == [True, False, False]


def test_in_scope_only_the_five_skills():
    assert analysis.in_scope("Reading::A1::Words")
    assert analysis.in_scope("grammar")
    assert not analysis.in_scope("Maestría::MOT")


def test_done_today_counts_cards_and_reviews_separately():
    rows = [review(TODAY, card_id=1), review(TODAY, card_id=1, hour=11), review(TODAY, card_id=2)]
    assert analysis.done_today(rows, TODAY) == {"cards": 2, "reviews": 3}


def test_due_by_deck_sums_roots_and_lists_leaves():
    counts = [
        {"deck": "Reading", "due": 206},
        {"deck": "Reading::A1", "due": 206},
        {"deck": "Reading::A1::Words", "due": 206},
        {"deck": "Grammar", "due": 10},
        {"deck": "Maestría", "due": 99},
    ]
    out = analysis.due_by_deck(counts)
    assert out["total"] == 216
    assert [d["deck"] for d in out["decks"]] == ["Reading::A1::Words", "Grammar"]


class TestCardStats:
    def test_needs_three_attempts_and_one_failure(self):
        d = date(2026, 9, 10)
        rows = [review(d, 1), review(d, 1), review(d, 1)]  # 3 vistas, 0 fallos
        rows += [review(d, 2, button=AGAIN), review(d, 2)]  # 2 vistas, 1 fallo
        assert analysis.card_stats(rows) == []

    def test_scores(self):
        d = date(2026, 9, 10)
        rows = [
            review(d, 7, button=AGAIN, duration_ms=6000, new_interval=1, prev_interval=3),
            review(d, 7, duration_ms=2000),
            review(d, 7, duration_ms=4000),
        ]
        (card,) = analysis.card_stats(rows)
        assert card["attempts"] == 3 and card["failures"] == 1
        assert card["failure_rate"] == 0.33
        assert card["interval_drops"] == 1
        assert card["seconds_lost"] == 12.0
        assert card["avg_duration_ms"] == 4000
        assert card["score"] == round(60 * (1 / 3) + 12.0 + 8, 1)
        assert card["failing_score"] == round(60 * (1 / 3) + 6 + 0.5 * 4 + 8, 1)


def test_failing_now_ignores_learning_and_old_cards():
    old = date(2026, 8, 1)
    recent = date(2026, 9, 12)
    rows = [review(old, 1, button=AGAIN)] * 3                                 # vieja
    rows += [review(recent, 2, button=AGAIN, review_type=0)] * 3              # aprendiendo
    rows += [review(recent, 3, button=AGAIN)] * 3                             # fallada de verdad
    out = analysis.failing_now(rows, TODAY)
    assert [c["card_id"] for c in out] == [3]


def test_parse_deck_name_is_case_insensitive_and_canonical():
    assert analysis.parse_deck_name("grammar::b1::Phrasal verbs") == ("Grammar", "B1", "Phrasal verbs")
    assert analysis.parse_deck_name("Reading::A1::Deep::Nested") == ("Reading", "A1", "Deep::Nested")
    assert analysis.parse_deck_name("Reading::A1") == ("Reading", "A1", "")
    assert analysis.parse_deck_name("Reading") is None
    assert analysis.parse_deck_name("Reading::Z9::x") is None


def test_maturity_current_level_and_gaps():
    assert analysis.maturity(3, 4) == 0.75 and analysis.maturity(0, 0) == 0.0
    levels = [
        {"level": "A1", "maturity": 0.9, "total": 10},
        {"level": "A2", "maturity": 0.6, "total": 5},
        {"level": "B1", "maturity": 0.0, "total": 0},
        {"level": "B2", "maturity": 0.7, "total": 3},
        {"level": "C1", "maturity": 0.0, "total": 0},
    ]
    assert analysis.current_level(levels) == "B1"
    assert analysis.gaps(levels) == ["B1", "C1"]
    assert analysis.current_level([{"level": lv, "maturity": 1.0, "total": 1} for lv in analysis.LEVELS]) == "C1"


def test_severity_bands():
    assert analysis.severity({"failure_rate": 0.5}) == "crítica"
    assert analysis.severity({"failure_rate": 0.3}) == "alta"
    assert analysis.severity({"failure_rate": 0.29}) == "media"


def test_impact_shares():
    out = analysis.impact([{"seconds_lost": 30.0}, {"seconds_lost": 10.0}], total_cards=100, total_seconds=200.0)
    assert out == {"cards": 2, "total_cards": 100, "card_share": 0.02, "seconds": 40.0,
                   "total_seconds": 200.0, "time_share": 0.2}
    assert analysis.impact([], 0, 0.0)["card_share"] == 0.0


def test_catalog_groups_skips_scaffolding_and_finds_next_up():
    stats = [
        {"deck": "Reading", "total": 0, "seen": 0, "mature": 0},                    # andamiaje
        {"deck": "Reading::A1", "total": 0, "seen": 0, "mature": 0},                # andamiaje
        {"deck": "Reading::A1::Words", "total": 10, "seen": 10, "mature": 8},
        {"deck": "Grammar::B1::Tenses", "total": 4, "seen": 2, "mature": 0},
        {"deck": "Maestría::MOT", "total": 7, "seen": 7, "mature": 7},
    ]
    counts = [{"deck": "Reading::A1::Words", "due": 3}, {"deck": "Grammar::B1::Tenses", "due": 5}]
    cat = analysis.catalog(stats, counts)
    reading = next(s for s in cat["skills"] if s["skill"] == "Reading")
    assert reading["current_level"] == "A2"          # A1 madura al 80 %, A2 vacía
    assert reading["gaps"] == ["A2", "B1", "B2", "C1"]
    assert [d["deck"] for d in cat["unclassified"]["decks"]] == ["Maestría::MOT"]
    assert cat["total"] == 21
    # Lo que toca: hay pendientes, gana el mazo con más (Grammar B1, 5) porque en
    # Reading no hay pendientes en el nivel actual (A2).
    assert cat["next_up"]["action"] == "study" and cat["next_up"]["deck"] == "Grammar::B1::Tenses"


def test_next_up_falls_back_to_the_lowest_hole():
    skills = [
        {"skill": "Writing", "current_level": "A1", "levels": [{"level": "A1", "decks": []}], "gaps": ["B1"]},
        {"skill": "Grammar", "current_level": "A1", "levels": [{"level": "A1", "decks": []}], "gaps": ["A2"]},
    ]
    assert analysis.next_up(skills) == {"action": "generate", "skill": "Grammar", "level": "A2", "deck": None, "due": 0}
    assert analysis.next_up([]) is None


def test_summary_only_counts_english():
    rows = [review(TODAY, 1), review(TODAY, 2, deck="Maestría::MOT")]
    out = analysis.summary(rows, [{"deck": "Reading", "due": 1}], TODAY)
    assert out["done"] == {"cards": 1, "reviews": 1}
    assert out["window"]["reviews"] == 1
    assert out["due"]["total"] == 1
