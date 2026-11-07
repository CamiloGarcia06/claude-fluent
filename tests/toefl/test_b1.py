from datetime import date

from fluent.toefl.domain.b1 import (
    TARGET,
    WINDOW,
    checklist,
    done_on,
    mission,
    rewrite_target,
    road,
    week,
)

A2_TEXT = "I like my city. It is big and nice. I go to the park and I play football."
B1_TEXT = (
    "I have lived in Bogotá since 2020. First, the city has a lot of parks, so I go "
    "running because it helps me relax. However, the traffic is terrible. If I had a "
    "car, I would spend hours in it. My friend Ana, who works downtown, uses the bike."
)


def sub(level, at="2026-11-02T10:00:00", kind="b1", text=A2_TEXT, revision=False, **over):
    return {
        "kind": kind,
        "item_id": over.pop("item_id", f"{kind}-{at}"),
        "at": at,
        "level": level,
        "score": over.pop("score", 3),
        "text": text,
        "revision": revision,
        **over,
    }


def ok(text):
    return {row["key"] for row in checklist(text) if row["ok"]}


def test_checklist_finds_the_b1_features():
    assert ok(B1_TEXT) == {
        "connectors",
        "contrast",
        "reasons",
        "present_perfect",
        "conditional",
        "relative",
    }
    assert ok(A2_TEXT) == set()


def test_checklist_avoids_the_usual_false_positives():
    assert "present_perfect" not in ok("I have a car and I have to work.")
    assert "present_perfect" in ok("She has never tried it. They've finished.")
    assert "relative" not in ok("Who is she? Which one do you want?")
    assert "relative" in ok("The city where I live is small.")
    assert "conditional" not in ok("If possible. I will go tomorrow.")
    assert "contrast" in ok("I like it. Although it’s expensive.")


def test_road_counts_the_last_first_attempts_at_b1():
    rows = [sub("A2", at=f"2026-10-{d:02d}T10:00:00") for d in range(1, 6)]
    rows += [sub("B1", at=f"2026-10-{d:02d}T10:00:00") for d in range(10, 20)]
    rows += [sub("A1", at="2026-10-30T10:00:00", revision=True)]  # no cuenta
    rows += [sub("B1", kind="daily", at="2026-10-31T10:00:00")]  # no es writing
    out = road(rows)
    assert out["count"] == WINDOW and out["at_level"] == WINDOW and out["ready"]
    assert out["levels"] == ["B1"] * WINDOW

    short = road([sub("B1") for _ in range(TARGET)])
    assert short["at_level"] == TARGET and not short["ready"]  # faltan textos
    assert road([])["levels"] == [] and not road([])["ready"]


def test_mission_names_what_is_missing_most():
    rows = [sub("A2", text=A2_TEXT) for _ in range(3)]
    rows += [sub("B1", at="2026-11-03T10:00:00", text=B1_TEXT.replace("However", "And"))]
    out = mission(rows)
    assert len(out) == 2
    assert out[0]["missed"] == 4 and out[0]["of"] == 4
    assert out[0]["tip"] and out[0]["example"]
    assert mission([]) == []
    assert mission([sub("B1", text=B1_TEXT)]) == []  # nada falta: no hay misión


def test_rewrite_target_is_the_worst_unrevised_text_of_the_week():
    today = date(2026, 11, 10)  # martes
    worst = sub("A2", at="2026-11-09T10:00:00", score=2, item_id="worst")
    rows = [
        sub("B1", at="2026-11-06T10:00:00", score=4, item_id="good"),
        worst,
        sub("A1", at="2026-10-20T10:00:00", item_id="old"),  # fuera de la semana
    ]
    assert rewrite_target(today, rows) == worst
    rows.append(sub("A2", at="2026-11-10T09:00:00", item_id="worst", revision=True))
    second = rewrite_target(today, rows)
    assert second is not None and second["item_id"] == "good"


def test_week_marks_what_was_done_and_rests_on_wednesday():
    today = date(2026, 11, 12)  # jueves
    rows = [
        sub("A2", at="2026-11-09T20:00:00"),  # lunes: texto nuevo
        sub("A2", at="2026-11-12T08:00:00", revision=True),  # jueves: no cuenta como nuevo
    ]
    days = week(today, rows)
    assert [d["task"] for d in days] == [
        "new",
        "rewrite",
        "rest",
        "new",
        "new",
        "free",
        "free",
    ]
    assert days[0]["done"] is True and days[1]["done"] is False
    assert days[2]["done"] is None and days[3]["today"] and days[3]["done"] is False
    assert days[4]["done"] is None  # todavía no llega
    late = week(today, [sub("A2", at="2026-11-12T08:00:00")])
    assert late[0]["done"] is None and late[1]["done"] is None  # antes de empezar
    assert done_on("rest", today, rows) is None
