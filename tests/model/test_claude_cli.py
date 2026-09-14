"""El envoltorio de `claude -p`: los fallos llegan por stdout (`is_error`), no
por el código de salida, y sin binario en PATH se avisa antes de intentar."""

import json
import subprocess

import pytest

from fluent.model.domain.errors import ModelError
from fluent.model.infrastructure import claude_cli


class FakeProc:
    def __init__(self, stdout, returncode=0, stderr=""):
        self.stdout, self.returncode, self.stderr = stdout, returncode, stderr


def test_missing_binary(monkeypatch):
    monkeypatch.setattr(claude_cli.shutil, "which", lambda _: None)
    with pytest.raises(ModelError):
        claude_cli.generate("p", {"type": "object"})


def test_is_error_and_structured_output(monkeypatch):
    monkeypatch.setattr(claude_cli.shutil, "which", lambda _: "/usr/bin/claude")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: FakeProc(json.dumps({"is_error": True, "result": "no session"})),
    )
    with pytest.raises(ModelError):
        claude_cli.generate("p", {"type": "object"})
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: FakeProc(json.dumps({"structured_output": {"ok": 1}, "duration_ms": 7})),
    )
    result, ms = claude_cli.generate("p", {"type": "object"})
    assert result == {"ok": 1} and isinstance(ms, int)
