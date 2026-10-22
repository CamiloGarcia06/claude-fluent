from fluent.toefl.application.get_overview import GetOverview
from fluent.toefl.domain.entities import Attempt

from .fakes import FakeBank, FakeLog, misses, sentence, words


def test_overview_counts_fresh_items_and_names_the_focus():
    done, fresh = sentence(), sentence(pattern="passive", chunks=["x", "y", "z"])
    log = FakeLog(
        [Attempt("sentence", done.id, done.pattern, True, "t")]
        + misses("sentence", "passive", wrong=3)
    )
    out = GetOverview(FakeBank([done, fresh], [words()]), log)()
    assert (out["sentence"]["total"], out["sentence"]["fresh"]) == (2, 1)
    assert out["sentence"]["focus"] == "passive"
    assert (out["words"]["total"], out["words"]["fresh"], out["words"]["focus"]) == (1, 1, None)
    passive = next(p for p in out["sentence"]["patterns"] if p["key"] == "passive")
    assert passive["misses"] == 3 and passive["enough"] and passive["tip"]
