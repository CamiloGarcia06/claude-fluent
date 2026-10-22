import json

from fluent.toefl.domain.entities import Attempt
from fluent.toefl.infrastructure.disk_bank import MAX_ATTEMPTS, DiskAttempts, DiskBank

from .fakes import sentence, words


def test_bank_round_trip_and_dedupe(tmp_path):
    bank = DiskBank(tmp_path)
    assert bank.items("sentence") == [] and bank.items("words") == []
    assert bank.add("sentence", [sentence(), sentence()]) == 1
    assert bank.add("sentence", [sentence()]) == 0
    assert bank.add("words", [words()]) == 1
    assert bank.items("sentence") == [sentence()]
    assert bank.items("words") == [words()]


def test_bank_skips_rows_that_no_longer_validate(tmp_path):
    bank = DiskBank(tmp_path)
    bank.add("sentence", [sentence()])
    path = tmp_path / "sentences.json"
    rows = json.loads(path.read_text())
    path.write_text(json.dumps(rows + [{"id": "x", "pattern": "nope"}, "garbage"]))
    assert bank.items("sentence") == [sentence()]
    path.write_text("{not json")
    assert bank.items("sentence") == []


def test_attempts_keep_only_the_window(tmp_path):
    log = DiskAttempts(tmp_path)
    log.append(
        [Attempt("sentence", str(i), "passive", i % 2 == 0, "t") for i in range(MAX_ATTEMPTS + 5)]
    )
    recent = log.recent()
    assert len(recent) == MAX_ATTEMPTS
    assert recent[0].item_id == "5" and recent[-1].item_id == str(MAX_ATTEMPTS + 4)


def test_writing_prompts_and_submissions_round_trip(tmp_path):
    from fluent.toefl.infrastructure.disk_bank import MAX_SUBMISSIONS, DiskSubmissions

    from .fakes import discussion_prompt, email_prompt

    bank = DiskBank(tmp_path)
    assert bank.add("email", [email_prompt()]) == 1
    assert bank.add("discussion", [discussion_prompt()]) == 1
    assert bank.items("email") == [email_prompt()]
    assert bank.items("discussion") == [discussion_prompt()]

    subs = DiskSubmissions(tmp_path)
    for i in range(MAX_SUBMISSIONS + 3):
        subs.append({"kind": "email" if i % 2 else "discussion", "score": i})
    rows = subs.recent("email") + subs.recent("discussion")
    assert len(rows) == MAX_SUBMISSIONS and all(r["score"] >= 3 for r in rows)


def test_reading_items_round_trip(tmp_path):
    from .fakes import mirror

    bank = DiskBank(tmp_path)
    assert bank.add("academic", [mirror()]) == 1
    assert bank.add("academic", [mirror()]) == 0
    assert bank.items("academic") == [mirror()]
    assert bank.items("daily") == []
