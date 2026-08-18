"""`claude -p` wrapper. Runs on the Claude Code subscription: no API key."""
import json
import shutil
import subprocess

TIMEOUT_S = 180

# Replaces Claude Code's own system prompt. Without this every call also loads
# CLAUDE.md, skills and tool definitions — around 22k tokens for a task that
# needs none of them.
SYSTEM_PROMPT = (
    "You rewrite Anki flashcards. You answer only with the requested JSON "
    "object, with no commentary."
)


class LLMError(RuntimeError):
    pass


def generate(prompt: str, schema: dict, timeout: int = TIMEOUT_S) -> tuple[dict, int]:
    """Return (structured output, duration in ms).

    Never uses --bare: that mode ignores the subscription login and demands an
    API key. Failures arrive on stdout as `is_error`, not through the exit code,
    so the field is checked rather than the return code.
    """
    if shutil.which("claude") is None:
        raise LLMError("`claude` is not on PATH.")

    try:
        proc = subprocess.run(
            [
                "claude", "-p", prompt,
                "--output-format", "json",
                "--json-schema", json.dumps(schema),
                "--system-prompt", SYSTEM_PROMPT,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        raise LLMError(f"claude -p timed out after {timeout}s") from e

    if not proc.stdout.strip():
        raise LLMError(
            f"claude -p returned nothing (exit {proc.returncode}): "
            f"{proc.stderr[:300] or 'no stderr'}"
        )

    payload = json.loads(proc.stdout)
    if payload.get("is_error"):
        raise LLMError(str(payload.get("result", payload))[:400])

    result = payload.get("structured_output")
    if result is None:
        result = payload.get("result")
        if isinstance(result, str):
            result = json.loads(result)
    if not isinstance(result, dict):
        raise LLMError("claude -p returned no structured output")

    return result, int(payload.get("duration_ms", 0))
