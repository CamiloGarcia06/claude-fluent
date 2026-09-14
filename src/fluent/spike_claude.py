"""Spike 2: can `claude -p` return schema-valid flashcards on the subscription?"""
import json
import subprocess

SCHEMA = {
    "type": "object",
    "properties": {
        "cards": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "front": {"type": "string"},
                    "back": {"type": "string"},
                    "example": {"type": "string"},
                },
                "required": ["front", "back", "example"],
            },
        }
    },
    "required": ["cards"],
}

# No --bare: that mode ignores the subscription login and demands ANTHROPIC_API_KEY
proc = subprocess.run(
    [
        "claude", "-p",
        "Generate 3 English flashcards for 'to put up with'. Backs in Spanish.",
        "--output-format", "json",
        "--json-schema", json.dumps(SCHEMA),
    ],
    capture_output=True,
    text=True,
    timeout=180,
)

result = json.loads(proc.stdout)
if result.get("is_error"):  # failures arrive on stdout, not through the exit code
    raise RuntimeError(result["result"])

print(json.dumps(result["structured_output"]["cards"], indent=2, ensure_ascii=False))
print("duration:", result["duration_ms"], "ms")
