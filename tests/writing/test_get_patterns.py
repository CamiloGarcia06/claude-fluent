from fluent.writing.application.get_patterns import GetPatterns

from .fakes import FakePatterns


def test_get_patterns_lists_with_threshold():
    out = GetPatterns(
        FakePatterns(
            {"patterns": {"articles": {"sessions": ["a"], "carded": None}}, "unmatched": {"y": 2}}
        )
    )()
    assert (
        out["patterns"][0]["key"] == "articles"
        and out["unmatched"] == {"y": 2}
        and out["threshold"] == 3
    )
