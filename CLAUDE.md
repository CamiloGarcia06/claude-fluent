# claude-fluent

Sigue la skill global `hexagonal-fastapi`: una carpeta por funcionalidad en
`src/fluent/<feature>/{domain,application,infrastructure}`, `shared/` sin
funcionalidades, `main.py` como única raíz de composición. `task check` antes
de cualquier PR; `hexcheck` dice qué capa puede importar qué. Sin excepciones.

## Particularidades

- Un solo usuario, en este portátil. Anki de escritorio con AnkiConnect (add-on
  `2055492159`) es la fuente de verdad; el app sincroniza, analiza y propone.
  Sin Anki, `/api/health` lo dice y lo que toca la colección responde 503.
- El modelo es `claude -p` con la suscripción (`model/infrastructure/claude_cli.py`,
  nunca `--bare`). Cada llamada tarda 8-35 s: se pide por término y por turno.
- Toda escritura en Anki pasa por `anki/infrastructure/snapshots.py` y deja su
  registro; `anki.domain.policy` hace que `call()` rechace las 49 acciones de
  escritura sin ese registro (ADR 0002). Los adaptadores reciben el cliente y
  los snapshots inyectados desde `main.py`; ninguna funcionalidad importa la
  infraestructura de otra.
- Lo que comparten varias funcionalidades está en `shared/types.py` (`SKILLS`,
  `LEVELS`, `Review`). El nombre del mazo `Skill::Level::Topic` es la base de
  datos: no hay mapeo en disco que pueda desactualizarse.
- `data/` y `static/` están en la raíz del repo; `shared/config.py` es el único
  que lee el entorno (`FLUENT_ROOT`, que usan los tests para no tocar tus datos).
- El servicio de usuario `claude-fluent.service` (dotfiles) arranca
  `.venv/bin/uvicorn fluent.main:app`; `task restart` solo reinicia con `check`
  en verde. Para desarrollar sin chocar con él: `task dev` (puerto 8001).
- Criterios largos y su porqué: `docs/design.md`. Decisiones: `docs/adr/`.
