"""Los tests corren contra una raíz temporal: nunca tocan data/ del repo."""

import os
import tempfile
from pathlib import Path

_ROOT = Path(tempfile.mkdtemp(prefix="fluent-tests-"))
(_ROOT / "data").mkdir()
(_ROOT / "static").mkdir()
(_ROOT / "static" / "index.html").write_text("<!doctype html><title>fluent test</title>")
os.environ["FLUENT_ROOT"] = str(_ROOT)
