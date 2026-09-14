# 0001 — Adopta el estándar hexagonal-fastapi

**Contexto.** claude-fluent nació plano: quince módulos en la raíz y un
`app.py` con veintidós endpoints que mezclaban validación, orquestación y
acceso a Anki y al modelo. Funcionaba, pero cada cambio exigía releer todo.

**Decisión.** Migrar al estándar personal (skill `hexagonal-fastapi`,
verificador `hexcheck`) en seis sesiones sin cambiar el comportamiento: primero
tests de caracterización, luego una funcionalidad cada vez, y al final los
módulos planos a la infraestructura de su funcionalidad y los endpoints a
routers. Funcionalidades: `collection` (análisis de la colección), `cards`
(proponer, escribir y reparar tarjetas), `syllabi` (temario), `writing`
(práctica de escritura), `settings` (meta diaria), y dos de infraestructura
pura, `anki` (cliente + escritura con registro) y `model` (`claude -p`).

**Porqué.** Los mismos criterios que ya expresaba el `CLAUDE.md` viejo
("analysis.py stays pure", "un solo camino de escritura", "todo lo que devuelve
el modelo es no confiable") pasan de convenciones que había que recordar a
reglas que `hexcheck` comprueba y a puertos que los tests sustituyen por
fakes. 66 tests contra fakes sustituyen a "probar con Anki abierto".

**Descartado.** Reescribir desde cero (se habría perdido dos meses de
decisiones medidas); migrar por capas globales en vez de por funcionalidad.

**Consecuencias.** Un adaptador por dependencia externa, inyectado desde
`main.py`; la lógica de cada endpoint vive en un caso de uso con test. Los
prompts siguen siendo módulos de infraestructura (son texto, no reglas de
negocio). El servicio de usuario no cambió de comportamiento en ningún paso
(`/api/health`, `/api/settings`, el temario congelado y las sesiones de
práctica responden igual que antes de la migración).
