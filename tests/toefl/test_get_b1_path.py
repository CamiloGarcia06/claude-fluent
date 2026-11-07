from datetime import datetime

from fluent.toefl.application.get_b1_path import GetB1Path

from .fakes import FakeBank, FakeSubmissions, FixedClock, b1_email
from .test_b1 import B1_TEXT, sub


def make(rows, now):
    bank = FakeBank(b1=[b1_email()])
    return GetB1Path(bank, FakeSubmissions(rows), FixedClock(now))


def test_tuesday_brings_the_worst_text_to_rewrite_with_its_prompt():
    prompt = b1_email()
    rows = [sub("A2", at="2026-11-09T19:00:00", item_id=prompt.id, text="I like it.")]
    out = make(rows, datetime(2026, 11, 10, 7, 0))()
    today = out["today"]
    assert today["task"] == "rewrite" and today["done"] is False
    assert today["rewrite"]["item"]["id"] == prompt.id
    assert today["rewrite"]["text"] == "I like it." and today["rewrite"]["level"] == "A2"
    assert not any(c["ok"] for c in today["rewrite"]["checks"])
    assert out["road"]["levels"] == ["A2"] and out["mission"]


def test_tuesday_without_anything_to_rewrite_offers_a_new_text():
    out = make([], datetime(2026, 11, 10, 7, 0))()
    assert out["today"]["task"] == "new" and out["today"]["kind"] == "b1"
    assert out["today"]["rewrite"] is None
    assert out["mission"] == [] and out["road"]["count"] == 0


def test_tuesday_after_rewriting_says_done():
    prompt = b1_email()
    rows = [
        sub("A2", at="2026-11-09T19:00:00", item_id=prompt.id),
        sub("B1", at="2026-11-10T08:00:00", item_id=prompt.id, revision=True, text=B1_TEXT),
    ]
    today = make(rows, datetime(2026, 11, 10, 9, 0))()["today"]
    assert today["task"] == "rewrite" and today["done"] is True


def test_wednesday_is_a_rest_day():
    out = make([], datetime(2026, 11, 11, 18, 0))()
    assert out["today"]["task"] == "rest" and out["today"]["done"] is None
    assert len(out["week"]) == 7 and out["week"][2]["today"]
