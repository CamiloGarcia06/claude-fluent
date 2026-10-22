"""Humo de /api/toefl con el banco real en la raíz temporal y sin modelo."""

from fastapi.testclient import TestClient

from fluent import main as app_module
from fluent.toefl.infrastructure.disk_bank import DiskBank

from .fakes import ETS_MISSING, mirror, right_answers, sentence, words


def test_toefl_round_trip_without_anki_or_model():
    c = TestClient(app_module.app)
    assert c.get("/api/toefl/next/sentence").status_code == 409  # banco vacío
    assert c.get("/api/toefl/next/essay").status_code == 400

    bank = DiskBank()  # el mismo data/toefl/ de la raíz temporal que usa el app
    bank.add("sentence", [sentence()])
    bank.add("words", [words()])

    overview = c.get("/api/toefl/overview").json()
    assert overview["sentence"]["fresh"] == 1 and overview["words"]["fresh"] == 1

    item = c.get("/api/toefl/next/words").json()["item"]
    graded = c.post(
        "/api/toefl/grade", json={"kind": "words", "item_id": item["id"], "answer": ETS_MISSING}
    ).json()
    assert graded["score"] == 10 and graded["tips"] == []
    assert c.get("/api/toefl/overview").json()["words"]["fresh"] == 0

    assert (
        c.post("/api/toefl/refill", json={"kind": "sentence", "focus": "nope"}).status_code == 400
    )


def test_reading_round_trip():
    c = TestClient(app_module.app)
    DiskBank().add("academic", [mirror()])
    item = c.get("/api/toefl/next/academic").json()["item"]
    assert "answer" not in str(item["questions"])
    out = c.post(
        "/api/toefl/read",
        json={
            "kind": "academic",
            "item_id": item["id"],
            "answers": right_answers(mirror()),
            "seconds": 240,
        },
    ).json()
    assert out["score"] == 4 and out["tips"] == []
    recent = c.get("/api/toefl/overview").json()["academic"]["recent"]
    assert recent[-1]["seconds"] == 240
    assert (
        c.post("/api/toefl/read", json={"kind": "academic", "item_id": "nope"}).status_code == 404
    )
