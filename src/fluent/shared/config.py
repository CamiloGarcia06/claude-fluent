"""Configuración: dónde viven los datos y la interfaz estática. El único módulo
que lee el entorno (H008).

El paquete está en `src/fluent/` (este archivo en `src/fluent/shared/`); `data/` (estado, temarios, snapshots, sesiones)
y `static/` siguen en la raíz del repo, que es donde siempre estuvieron.
FLUENT_ROOT permite apuntar a otra raíz (los tests lo usan para no tocar tus datos).
"""

import os
from pathlib import Path

ROOT = Path(os.environ.get("FLUENT_ROOT", Path(__file__).resolve().parents[3]))
DATA_DIR = ROOT / "data"
STATIC_DIR = ROOT / "static"
