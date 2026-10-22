from typing import Any

import pytest

from fluent.model.domain.errors import ModelError
from fluent.toefl.domain.errors import ModelFailed
from fluent.toefl.infrastructure.llm_grader import LlmGrader


def test_grader_uses_the_rubric_of_the_task():
    prompts = []

    def generate(prompt, schema, system=""):
        prompts.append(prompt)
        return {"score": 4}, 10

    grader = LlmGrader(generate)
    assert grader.grade("email", "the brief", "my text") == {"score": 4}
    assert grader.grade("discussion", "the brief", "my text") == {"score": 4}
    assert "Write an Email (0-5)" in prompts[0] and "my text" in prompts[0]
    assert "Academic Discussion (0-5)" in prompts[1]


def test_grader_translates_model_errors_and_bad_shapes():
    def broken(*args, **kwargs):
        raise ModelError("no session")

    with pytest.raises(ModelFailed):
        LlmGrader(broken).grade("email", "b", "t")

    def not_a_dict(*args, **kwargs) -> Any:
        return "text", 1

    assert LlmGrader(not_a_dict).grade("email", "b", "t") == {}
