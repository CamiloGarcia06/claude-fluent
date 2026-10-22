from fluent.toefl.domain.advice import WINDOW, stats, weakest
from fluent.toefl.domain.entities import Attempt

from .fakes import misses


def test_stats_cover_the_whole_catalogue():
    rows = stats("sentence", [])
    assert [r.key for r in rows] == [
        "indirect_question",
        "direct_question",
        "relative_clause",
        "passive",
    ]
    assert all(r.tries == 0 for r in rows)


def test_only_the_last_window_counts():
    old_failures = misses("sentence", "passive", wrong=WINDOW)
    recent_hits = misses("sentence", "passive", wrong=0, right=WINDOW)
    row = next(r for r in stats("sentence", old_failures + recent_hits) if r.key == "passive")
    assert (row.tries, row.misses) == (WINDOW, 0)


def test_weakest_needs_enough_attempts_and_a_miss():
    assert weakest(stats("sentence", misses("sentence", "passive", wrong=2))) is None
    assert weakest(stats("sentence", misses("sentence", "passive", wrong=0, right=5))) is None
    attempts = misses("sentence", "passive", wrong=1, right=3) + misses(
        "sentence", "indirect_question", wrong=3, right=1
    )
    weak = weakest(stats("sentence", attempts))
    assert weak is not None and weak.key == "indirect_question"


def test_kinds_do_not_mix():
    attempts = [Attempt("words", "p", "connector", False, "t")] * 5
    assert weakest(stats("sentence", attempts)) is None
    weak = weakest(stats("words", attempts))
    assert weak is not None and weak.key == "connector"
