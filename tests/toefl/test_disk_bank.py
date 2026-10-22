import json

from fluent.toefl.domain.entities import Attempt
from fluent.toefl.infrastructure.disk_bank import MAX_ATTEMPTS, DiskAttempts, DiskBank

from .fakes import sentence, words


def test_bank_round_trip_and_dedupe(tmp_path):
    bank = DiskBank(tmp_path)
    assert bank.sentences() == [] and bank.words() == []
    assert bank.add_sentences([sentence(), sentence()]) == 1
    assert bank.add_sentences([sentence()]) == 0
    assert bank.add_words([words()]) == 1
    assert bank.sentences() == [sentence()]
    assert bank.words() == [words()]


def test_bank_skips_rows_that_no_longer_validate(tmp_path):
    bank = DiskBank(tmp_path)
    bank.add_sentences([sentence()])
    path = tmp_path / "sentences.json"
    rows = json.loads(path.read_text())
    path.write_text(json.dumps(rows + [{"id": "x", "pattern": "nope"}, "garbage"]))
    assert bank.sentences() == [sentence()]
    path.write_text("{not json")
    assert bank.sentences() == []


def test_attempts_keep_only_the_window(tmp_path):
    log = DiskAttempts(tmp_path)
    log.append(
        [Attempt("sentence", str(i), "passive", i % 2 == 0, "t") for i in range(MAX_ATTEMPTS + 5)]
    )
    recent = log.recent()
    assert len(recent) == MAX_ATTEMPTS
    assert recent[0].item_id == "5" and recent[-1].item_id == str(MAX_ATTEMPTS + 4)
