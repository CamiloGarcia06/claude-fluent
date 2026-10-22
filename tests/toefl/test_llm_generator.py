import pytest

from fluent.model.domain.errors import ModelError
from fluent.toefl.domain.errors import ModelFailed
from fluent.toefl.infrastructure.llm_generator import LlmGenerator


def test_generator_passes_focus_and_drops_malformed_rows():
    prompts = []

    def generate(prompt, schema, system=""):
        prompts.append(prompt)
        return {"items": [{"pattern": "passive"}, "junk", 3]}, 10

    rows = LlmGenerator(generate).sentences(8, "passive")
    assert rows == [{"pattern": "passive"}]
    assert "Write 8" in prompts[0] and "Focus: at least half" in prompts[0]


def test_generator_tolerates_a_wrong_shape():
    assert LlmGenerator(lambda *a, **k: ({"paragraphs": "nope"}, 1)).paragraphs(3, None) == []
    assert LlmGenerator(lambda *a, **k: ({}, 1)).sentences(8, None) == []


def test_generator_translates_model_errors():
    def broken(*args, **kwargs):
        raise ModelError("no session")

    with pytest.raises(ModelFailed):
        LlmGenerator(broken).paragraphs(3, None)
