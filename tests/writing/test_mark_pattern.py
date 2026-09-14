import pytest

from fluent.writing.application.mark_pattern import MarkPattern
from fluent.writing.domain.errors import BadPatternAction

from .fakes import FakePatterns


def test_mark_carded_and_bad_action():
    patterns = FakePatterns(
        {"patterns": {"articles": {"sessions": ["a"], "carded": None}}, "unmatched": {}}
    )
    out = MarkPattern(patterns)("articles", "carded")
    assert out["patterns"][0]["carded"] == "20260913-120000" and patterns.written
    with pytest.raises(BadPatternAction):
        MarkPattern(patterns)("articles", "explode")
    with pytest.raises(BadPatternAction):
        MarkPattern(patterns)("nope", "carded")
